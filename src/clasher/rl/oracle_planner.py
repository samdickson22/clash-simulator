from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, Optional

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
from clasher.torch_sim import (
    SimulatorBackend,
    TensorBattleFork,
    TorchBattleExecutor,
)

from .action_space import DiscreteTileActionSpace
from .reward_model import objective_win_prob_p0


def _quantize(value: float, scale: float) -> int:
    return int(round(float(value) * scale))


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
    alpha: Dict[int, float] = field(default_factory=dict)
    beta: Dict[int, float] = field(default_factory=dict)

    def ensure_actions(self, actions: Iterable[int]) -> None:
        for action in actions:
            if action not in self.alpha:
                self.alpha[action] = 1.0
                self.beta[action] = 1.0

    def sample_action(self, legal_actions: np.ndarray, rng: np.random.Generator) -> int:
        self.ensure_actions(legal_actions.tolist())
        best_action = int(legal_actions[0])
        best_sample = -1.0
        for action in legal_actions.tolist():
            sample = float(rng.beta(self.alpha[action], self.beta[action]))
            if sample > best_sample:
                best_sample = sample
                best_action = action
        return best_action

    def greedy_action(self, legal_actions: np.ndarray) -> int:
        self.ensure_actions(legal_actions.tolist())
        best_action = int(legal_actions[0])
        best_mean = -1.0
        for action in legal_actions.tolist():
            mean = self.alpha[action] / (self.alpha[action] + self.beta[action])
            if mean > best_mean:
                best_mean = mean
                best_action = action
        return best_action

    def update(self, action: int, reward_prob: float) -> None:
        self.ensure_actions([action])
        p = float(np.clip(reward_prob, 0.0, 1.0))
        self.alpha[action] += p
        self.beta[action] += 1.0 - p


@dataclass
class _PlannerNode:
    by_player: Dict[int, _PlayerBandit] = field(
        default_factory=lambda: {0: _PlayerBandit(), 1: _PlayerBandit()}
    )


class FixedDepthThompsonOracle:
    """Rooted fixed-depth tree search with decoupled Thompson sampling per player."""

    def __init__(
        self,
        action_space: Optional[DiscreteTileActionSpace] = None,
        *,
        decision_interval_ticks: int = 8,
        plan_depth: int = 10,
        num_simulations: int = 48,
        rollout_action_samples: int = 96,
        seed: Optional[int] = None,
        simulation_backend: str = "python",
        simulation_device: str = "cpu",
    ) -> None:
        self.action_space = action_space or DiscreteTileActionSpace(
            canonical_perspective=True
        )
        self.decision_interval_ticks = decision_interval_ticks
        self.plan_depth = plan_depth
        self.num_simulations = num_simulations
        self.rollout_action_samples = rollout_action_samples
        self.rng = np.random.default_rng(seed)
        self.simulation_backend = SimulatorBackend(simulation_backend)
        self._simulator = TorchBattleExecutor(
            self.simulation_backend,
            device=simulation_device,
        )
        self._tensor_forks = 0

    def select_actions(self, battle: BattleState) -> Dict[int, int]:
        tree: Dict[tuple, _PlannerNode] = {}
        root_tensor_fork = self._capture_tensor_fork(battle)
        for _ in range(self.num_simulations):
            sim = self._clone_for_search(battle, root_tensor_fork)
            path: list[tuple[tuple, Dict[int, int]]] = []
            for _depth in range(self.plan_depth):
                key = self._state_key(sim)
                node = tree.setdefault(key, _PlannerNode())
                chosen: Dict[int, int] = {}
                for player_id in (0, 1):
                    legal = self._sample_legal_actions(sim, player_id)
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

        root_key = self._state_key(battle)
        root = tree.get(root_key)
        out: Dict[int, int] = {}
        for player_id in (0, 1):
            legal = self._sample_legal_actions(battle, player_id)
            if root is None:
                out[player_id] = int(self.rng.choice(legal))
            else:
                out[player_id] = root.by_player[player_id].greedy_action(legal)
        return out

    def _capture_tensor_fork(
        self,
        battle: BattleState,
    ) -> TensorBattleFork | None:
        if self.simulation_backend is not SimulatorBackend.PYTORCH:
            return None
        return TensorBattleFork.capture([battle], device=self._simulator.device)

    def _clone_for_search(
        self,
        battle: BattleState,
        root_tensor_fork: TensorBattleFork | None,
    ) -> BattleState:
        sim = battle.clone()
        if root_tensor_fork is not None:
            self._simulator.prime_tensor_fork([sim], root_tensor_fork)
            self._tensor_forks += 1
        return sim

    def _advance_simulation(self, battle: BattleState) -> None:
        if self.simulation_backend is SimulatorBackend.PYTHON:
            for _ in range(self.decision_interval_ticks):
                if battle.game_over:
                    break
                battle.step()
            return
        self._simulator.step_logic_ticks(battle, self.decision_interval_ticks)

    def simulator_backend_metrics(self) -> dict[str, float]:
        return {
            **self._simulator.metrics_dict(),
            "tensor_forks": float(self._tensor_forks),
        }

    def _sample_legal_actions(self, battle: BattleState, player_id: int) -> np.ndarray:
        mask = self.action_space.legal_action_mask(battle, player_id)
        legal = np.flatnonzero(mask).astype(np.int64)
        if legal.size == 0:
            return np.asarray([self.action_space.no_op_action], dtype=np.int64)
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
        self, battle: BattleState, joint_actions: Dict[int, int]
    ) -> None:
        order = [0, 1]
        self.rng.shuffle(order)
        for player_id in order:
            self.action_space.apply_action(
                battle, player_id, int(joint_actions[player_id])
            )
        self._advance_simulation(battle)

    def _evaluate_state_prob(self, battle: BattleState) -> Dict[int, float]:
        p0_prob = objective_win_prob_p0(battle)
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
