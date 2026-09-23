from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

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

from .action_space import DiscreteTileActionSpace
from .reward_model import OBJECTIVE_V1, REWARD_PROFILES, reward_win_prob_p0


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
        """Return the best sampled action, excluding untouched prior-only arms."""

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
        p = float(np.clip(reward_prob, 0.0, 1.0))
        self.alpha[action] += p
        self.beta[action] += 1.0 - p


@dataclass
class _PlannerNode:
    by_player: dict[int, _PlayerBandit] = field(
        default_factory=lambda: {0: _PlayerBandit(), 1: _PlayerBandit()}
    )


class FixedDepthThompsonOracle:
    """Rooted fixed-depth tree search with decoupled Thompson sampling per player."""

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

    def select_actions(self, battle: BattleState) -> dict[int, int]:
        tree: dict[tuple, _PlannerNode] = {}
        root_key = self._state_key(battle)
        root_legal = {
            player_id: self._legal_actions(battle, player_id)
            for player_id in (0, 1)
        }
        root_candidates = (
            {
                player_id: self._sample_actions(root_legal[player_id])
                for player_id in (0, 1)
            }
            if self.stable_root_candidates
            else None
        )
        for _ in range(self.num_simulations):
            sim = battle.clone()
            path: list[tuple[tuple, dict[int, int]]] = []
            for _depth in range(self.plan_depth):
                key = root_key if _depth == 0 else self._state_key(sim)
                node = tree.get(key)
                if node is None:
                    node = _PlannerNode()
                    tree[key] = node
                chosen: dict[int, int] = {}
                for player_id in (0, 1):
                    if _depth == 0 and root_candidates is not None:
                        legal = root_candidates[player_id]
                    elif _depth == 0:
                        legal = self._sample_actions(root_legal[player_id])
                    else:
                        legal = self._sample_actions(
                            self._legal_actions(sim, player_id)
                        )
                    chosen[player_id] = node.by_player[player_id].sample_action(
                        legal, self.rng
                    )
                path.append((key, chosen))
                self._apply_joint_action(sim, chosen)
                if sim.game_over:
                    break

            value_probs = self._evaluate_state_prob(sim)
            for key, chosen in path:
                node = tree[key]
                node.by_player[0].update(chosen[0], value_probs[0])
                node.by_player[1].update(chosen[1], value_probs[1])

        root = tree.get(root_key)
        out: dict[int, int] = {}
        for player_id in (0, 1):
            legal = (
                root_candidates[player_id]
                if root_candidates is not None
                else self._sample_actions(root_legal[player_id])
            )
            if root is None:
                out[player_id] = int(self.rng.choice(legal))
            elif root_candidates is not None:
                visited = root.by_player[player_id].greedy_visited_action(legal)
                out[player_id] = (
                    visited if visited is not None else int(self.rng.choice(legal))
                )
            else:
                out[player_id] = root.by_player[player_id].greedy_action(legal)
        return out

    def _sample_legal_actions(self, battle: BattleState, player_id: int) -> np.ndarray:
        return self._sample_actions(self._legal_actions(battle, player_id))

    def _legal_actions(self, battle: BattleState, player_id: int) -> np.ndarray:
        mask = self.action_space.legal_action_mask(battle, player_id)
        return self._legal_actions_from_mask(mask)

    def _legal_actions_from_mask(self, mask: np.ndarray) -> np.ndarray:
        legal = np.flatnonzero(mask).astype(np.int64, copy=False)
        if legal.size == 0:
            return np.asarray([self.action_space.no_op_action], dtype=np.int64)
        return legal

    def _sample_actions(self, legal: np.ndarray) -> np.ndarray:
        if legal.size <= self.rollout_action_samples:
            return legal

        no_op = int(self.action_space.no_op_action)
        selected = {no_op}
        other = legal[legal != no_op]
        needed = max(0, self.rollout_action_samples - len(selected))
        if needed > 0 and other.size > 0:
            picks = self.rng.choice(other, size=min(needed, other.size), replace=False)
            selected.update(int(x) for x in picks.tolist())
        return np.asarray(sorted(selected), dtype=np.int64)

    def _apply_joint_action(
        self, battle: BattleState, joint_actions: dict[int, int]
    ) -> None:
        order = [0, 1]
        self.rng.shuffle(order)
        for player_id in order:
            self.action_space.apply_action(
                battle, player_id, int(joint_actions[player_id])
            )
        for _ in range(self.decision_interval_ticks):
            if battle.game_over:
                break
            battle.step()

    def _evaluate_state_prob(self, battle: BattleState) -> dict[int, float]:
        p0_prob = reward_win_prob_p0(battle, self.reward_profile)
        return {0: p0_prob, 1: 1.0 - p0_prob}

    def _state_key(self, battle: BattleState) -> tuple:
        p0 = battle.players[0]
        p1 = battle.players[1]
        base = (
            int(battle.tick),
            _quantize(battle.time, 10.0),
            int(battle.double_elixir),
            int(battle.triple_elixir),
            int(battle.overtime),
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
        for entity in battle.entities.values():
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
