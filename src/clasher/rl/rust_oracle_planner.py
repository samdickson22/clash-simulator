from __future__ import annotations

import copy
import hashlib
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol

import numpy as np

from clasher.battle import BattleState
from clasher.entities import (
    AreaEffect,
    Building,
    Entity,
    Graveyard,
    Projectile,
    RollingProjectile,
    SpawnProjectile,
    TimedExplosive,
    Troop,
)
from clasher.rust_core import ResidentRustBattle

from .action_space import DiscreteTileActionSpace
from .oracle_sampling import sample_action_subset
from .reward_model import OBJECTIVE_V1, REWARD_PROFILES, reward_win_prob_p0
from .rust_oracle_leaf import reward_win_prob_from_projection


class RustOracleMode(str, Enum):
    OFF = "off"
    SHADOW = "shadow"
    ON = "on"


@dataclass(frozen=True)
class RustOracleMetrics:
    requested_mode: str
    active_backend: str
    fallback_reason: str | None
    shadow_checks: int
    shadow_mismatches: int
    trace_sha256: str | None


class _OracleState(Protocol):
    def fork(self) -> _OracleState: ...

    def legal_actions(self, player_id: int) -> np.ndarray: ...

    def state_key(self) -> tuple: ...

    def apply_ordered_interval(
        self,
        action0: int,
        action1: int,
        first_player: int,
        ticks: int,
    ) -> None: ...

    @property
    def game_over(self) -> bool: ...

    def leaf_prob_p0(self) -> float: ...


def _quantize(value: float, scale: float) -> int:
    return round(float(value) * scale)


def _entity_kind(entity: Entity) -> int:
    if isinstance(entity, Building):
        return 0
    if isinstance(entity, Troop):
        return 1
    if isinstance(entity, (Projectile, SpawnProjectile, RollingProjectile)):
        return 2
    if isinstance(entity, (AreaEffect, TimedExplosive, Graveyard)):
        return 3
    return 4


@dataclass
class _PythonOracleState:
    battle: BattleState
    action_space: DiscreteTileActionSpace
    reward_profile: str

    def fork(self) -> _PythonOracleState:
        return type(self)(self.battle.clone(), self.action_space, self.reward_profile)

    def legal_actions(self, player_id: int) -> np.ndarray:
        mask = self.action_space.legal_action_mask(self.battle, player_id)
        legal = np.flatnonzero(mask).astype(np.int64, copy=False)
        if legal.size == 0:
            return np.asarray([self.action_space.no_op_action], dtype=np.int64)
        return legal

    def state_key(self) -> tuple:
        p0 = self.battle.players[0]
        p1 = self.battle.players[1]
        base = (
            int(self.battle.tick),
            _quantize(self.battle.time, 10.0),
            int(self.battle.double_elixir),
            int(self.battle.triple_elixir),
            int(self.battle.overtime),
            _quantize(p0.elixir, 10.0),
            _quantize(p1.elixir, 10.0),
            _quantize(p0.left_tower_hp, 1.0),
            _quantize(p0.right_tower_hp, 1.0),
            _quantize(p0.king_tower_hp, 1.0),
            _quantize(p1.left_tower_hp, 1.0),
            _quantize(p1.right_tower_hp, 1.0),
            _quantize(p1.king_tower_hp, 1.0),
        )
        entities = []
        for entity in self.battle.entities.values():
            if not entity.is_alive:
                continue
            max_hp = max(1.0, float(getattr(entity, "max_hitpoints", 1.0) or 1.0))
            entities.append(
                (
                    _entity_kind(entity),
                    int(entity.player_id),
                    _quantize(entity.position.x, 2.0),
                    _quantize(entity.position.y, 2.0),
                    _quantize(float(entity.hitpoints) / max_hp, 20.0),
                )
            )
        entities.sort()
        if len(entities) > 96:
            entities = entities[:96]
        return base + (tuple(entities),)

    def apply_ordered_interval(
        self,
        action0: int,
        action1: int,
        first_player: int,
        ticks: int,
    ) -> None:
        for player_id in (first_player, 1 - first_player):
            action = action0 if player_id == 0 else action1
            self.action_space.apply_action(self.battle, player_id, int(action))
        for _ in range(ticks):
            if self.battle.game_over:
                break
            self.battle.step()

    @property
    def game_over(self) -> bool:
        return bool(self.battle.game_over)

    def leaf_prob_p0(self) -> float:
        return reward_win_prob_p0(self.battle, self.reward_profile)


@dataclass
class _ResidentOracleState:
    resident: ResidentRustBattle
    reward_profile: str

    @classmethod
    def from_battle(
        cls,
        battle: BattleState,
        reward_profile: str,
    ) -> _ResidentOracleState:
        resident = ResidentRustBattle.from_battle(battle)
        state = cls(resident, reward_profile)
        state.legal_actions(0)
        state.legal_actions(1)
        resident.resident_oracle_leaf_projection()
        return state

    def fork(self) -> _ResidentOracleState:
        return type(self)(self.resident.fork(), self.reward_profile)

    def legal_actions(self, player_id: int) -> np.ndarray:
        return np.asarray(
            self.resident.resident_legal_action_ids(player_id),
            dtype=np.int64,
        )

    def state_key(self) -> tuple:
        return self.resident.resident_oracle_state_key()

    def apply_ordered_interval(
        self,
        action0: int,
        action1: int,
        first_player: int,
        ticks: int,
    ) -> None:
        self.resident.apply_resident_ordered_interval(
            action0,
            action1,
            first_player,
            ticks,
        )

    @property
    def game_over(self) -> bool:
        return bool(self.resident.outcome_state().game_over)

    def leaf_prob_p0(self) -> float:
        return reward_win_prob_from_projection(
            self.resident.resident_oracle_leaf_projection(),
            self.reward_profile,
        )


@dataclass
class _PlayerBandit:
    alpha: dict[int, float] = field(default_factory=dict)
    beta: dict[int, float] = field(default_factory=dict)

    def ensure_actions(self, actions: Iterable[int]) -> None:
        for action in actions:
            if action not in self.alpha:
                self.alpha[action] = 1.0
                self.beta[action] = 1.0

    def sample_action(self, legal_actions: np.ndarray, rng: np.random.Generator) -> int:
        actions = legal_actions.tolist()
        self.ensure_actions(actions)
        best_action = int(actions[0])
        best_sample = -1.0
        for action in actions:
            sample = float(rng.beta(self.alpha[action], self.beta[action]))
            if sample > best_sample:
                best_sample = sample
                best_action = action
        return best_action

    def greedy_action(self, legal_actions: np.ndarray) -> int:
        actions = legal_actions.tolist()
        self.ensure_actions(actions)
        best_action = int(actions[0])
        best_mean = -1.0
        for action in actions:
            mean = self.alpha[action] / (self.alpha[action] + self.beta[action])
            if mean > best_mean:
                best_mean = mean
                best_action = action
        return best_action

    def greedy_visited_action(self, legal_actions: np.ndarray) -> int | None:
        best_action: int | None = None
        best_mean = -1.0
        for action in legal_actions.tolist():
            alpha = self.alpha.get(action)
            beta = self.beta.get(action)
            if alpha is None or beta is None or alpha + beta <= 2.0:
                continue
            mean = alpha / (alpha + beta)
            if mean > best_mean:
                best_mean = mean
                best_action = int(action)
        return best_action

    def update(self, action: int, reward_prob: float) -> None:
        self.ensure_actions([action])
        probability = float(np.clip(reward_prob, 0.0, 1.0))
        self.alpha[action] += probability
        self.beta[action] += 1.0 - probability


@dataclass
class _PlannerNode:
    by_player: dict[int, _PlayerBandit] = field(
        default_factory=lambda: {0: _PlayerBandit(), 1: _PlayerBandit()}
    )


@dataclass(frozen=True)
class _PlannerRun:
    actions: dict[int, int]
    trace: tuple[tuple[tuple, int, int, str], ...]

    def trace_sha256(self) -> str:
        return hashlib.sha256(repr(self.trace).encode("utf-8")).hexdigest()


class RustBackendFixedDepthThompsonOracle:
    """Accepted fixed-depth oracle over interchangeable Python/Rust states."""

    def __init__(
        self,
        action_space: DiscreteTileActionSpace | None = None,
        *,
        decision_interval_ticks: int = 8,
        plan_depth: int = 10,
        num_simulations: int = 48,
        rollout_action_samples: int = 96,
        seed: int | None = None,
        reward_profile: str = OBJECTIVE_V1,
        stable_root_candidates: bool = False,
        rust_mode: RustOracleMode | str = RustOracleMode.OFF,
    ) -> None:
        if reward_profile not in REWARD_PROFILES:
            raise ValueError(f"unknown reward profile {reward_profile!r}")
        self.action_space = action_space or DiscreteTileActionSpace(
            canonical_perspective=True
        )
        self.decision_interval_ticks = decision_interval_ticks
        self.plan_depth = plan_depth
        self.num_simulations = num_simulations
        self.rollout_action_samples = rollout_action_samples
        self.rng = np.random.default_rng(seed)
        self.reward_profile = reward_profile
        self.stable_root_candidates = stable_root_candidates
        self.rust_mode = RustOracleMode(rust_mode)
        self.metrics = RustOracleMetrics(
            requested_mode=self.rust_mode.value,
            active_backend="python",
            fallback_reason=None,
            shadow_checks=0,
            shadow_mismatches=0,
            trace_sha256=None,
        )

    def select_actions(self, battle: BattleState) -> dict[int, int]:
        if self.rust_mode is RustOracleMode.OFF:
            run = self._select_actions_with_state(
                _PythonOracleState(battle, self.action_space, self.reward_profile)
            )
            self.metrics = RustOracleMetrics(
                requested_mode=self.rust_mode.value,
                active_backend="python",
                fallback_reason=None,
                shadow_checks=0,
                shadow_mismatches=0,
                trace_sha256=run.trace_sha256(),
            )
            return run.actions

        try:
            resident_state = _ResidentOracleState.from_battle(
                battle,
                self.reward_profile,
            )
        except (RuntimeError, ValueError) as error:
            run = self._select_actions_with_state(
                _PythonOracleState(battle, self.action_space, self.reward_profile)
            )
            self.metrics = RustOracleMetrics(
                requested_mode=self.rust_mode.value,
                active_backend="python",
                fallback_reason=str(error),
                shadow_checks=0,
                shadow_mismatches=0,
                trace_sha256=run.trace_sha256(),
            )
            return run.actions

        if self.rust_mode is RustOracleMode.ON:
            run = self._select_actions_with_state(resident_state)
            self.metrics = RustOracleMetrics(
                requested_mode=self.rust_mode.value,
                active_backend="rust",
                fallback_reason=None,
                shadow_checks=0,
                shadow_mismatches=0,
                trace_sha256=run.trace_sha256(),
            )
            return run.actions

        initial_rng = copy.deepcopy(self.rng.bit_generator.state)
        python_run = self._select_actions_with_state(
            _PythonOracleState(battle, self.action_space, self.reward_profile)
        )
        authoritative_rng = copy.deepcopy(self.rng.bit_generator.state)
        self.rng.bit_generator.state = initial_rng
        rust_run = self._select_actions_with_state(resident_state)
        rust_rng = copy.deepcopy(self.rng.bit_generator.state)
        self.rng.bit_generator.state = authoritative_rng
        mismatch = python_run != rust_run or authoritative_rng != rust_rng
        self.metrics = RustOracleMetrics(
            requested_mode=self.rust_mode.value,
            active_backend="python+rust-shadow",
            fallback_reason=None,
            shadow_checks=1,
            shadow_mismatches=int(mismatch),
            trace_sha256=python_run.trace_sha256(),
        )
        if mismatch:
            raise RuntimeError("resident oracle shadow mismatch")
        return python_run.actions

    def _sample_actions(self, legal: np.ndarray) -> np.ndarray:
        return sample_action_subset(
            legal,
            sample_limit=self.rollout_action_samples,
            no_op_action=self.action_space.no_op_action,
            rng=self.rng,
        )

    def _select_actions_with_state(self, state: _OracleState) -> _PlannerRun:
        tree: dict[tuple, _PlannerNode] = {}
        root_key = state.state_key()
        root_legal = {
            player_id: state.legal_actions(player_id) for player_id in (0, 1)
        }
        root_candidates = (
            {
                player_id: self._sample_actions(root_legal[player_id])
                for player_id in (0, 1)
            }
            if self.stable_root_candidates
            else None
        )
        trace: list[tuple[tuple, int, int, str]] = []
        for _ in range(self.num_simulations):
            sim = state.fork()
            path: list[tuple[_PlannerNode, tuple, int, int]] = []
            for depth in range(self.plan_depth):
                key = root_key if depth == 0 else sim.state_key()
                node = tree.get(key)
                if node is None:
                    node = _PlannerNode()
                    tree[key] = node

                legal0 = (
                    root_candidates[0]
                    if depth == 0 and root_candidates is not None
                    else self._sample_actions(
                        root_legal[0] if depth == 0 else sim.legal_actions(0)
                    )
                )
                action0 = node.by_player[0].sample_action(legal0, self.rng)
                legal1 = (
                    root_candidates[1]
                    if depth == 0 and root_candidates is not None
                    else self._sample_actions(
                        root_legal[1] if depth == 0 else sim.legal_actions(1)
                    )
                )
                action1 = node.by_player[1].sample_action(legal1, self.rng)
                path.append((node, key, action0, action1))
                order = [0, 1]
                self.rng.shuffle(order)
                sim.apply_ordered_interval(
                    action0,
                    action1,
                    order[0],
                    self.decision_interval_ticks,
                )
                if sim.game_over:
                    break

            value_prob_p0 = sim.leaf_prob_p0()
            for node, key, action0, action1 in path:
                trace.append((key, action0, action1, float(value_prob_p0).hex()))
                node.by_player[0].update(action0, value_prob_p0)
                node.by_player[1].update(action1, 1.0 - value_prob_p0)

        root = tree.get(root_key)
        actions: dict[int, int] = {}
        for player_id in (0, 1):
            legal = (
                root_candidates[player_id]
                if root_candidates is not None
                else self._sample_actions(root_legal[player_id])
            )
            if root is None:
                actions[player_id] = int(self.rng.choice(legal))
            elif root_candidates is not None:
                visited = root.by_player[player_id].greedy_visited_action(legal)
                actions[player_id] = (
                    visited if visited is not None else int(self.rng.choice(legal))
                )
            else:
                actions[player_id] = root.by_player[player_id].greedy_action(legal)
        return _PlannerRun(actions=actions, trace=tuple(trace))
