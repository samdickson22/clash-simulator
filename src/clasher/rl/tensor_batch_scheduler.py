"""Per-actor batching for tensor-backed simulator decision windows."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from clasher.torch_sim import SimulatorBackend, TorchBattleExecutor

from .selfplay_env import SelfPlayBattleEnv, StepInfo

StepResult = tuple[dict[int, float], bool, StepInfo]


@dataclass
class BatchScheduleMetrics:
    """Scheduling counters separate from simulator fallback/parity counters."""

    step_calls: int = 0
    battle_windows: int = 0
    tensor_batches: int = 0
    max_batch_size: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "step_calls": self.step_calls,
            "battle_windows": self.battle_windows,
            "tensor_batches": self.tensor_batches,
            "max_batch_size": self.max_batch_size,
        }


class TensorBatchScheduler:
    """Coalesce one worker's environment shard into retained tensor batches.

    Process boundaries remain the outer production partition: each actor worker
    owns one scheduler and batches only its assigned environments. Python mode
    keeps the established per-environment advancement path. PyTorch modes apply
    actions in environment order, group equal-length tick windows, and issue one
    step_battles call per group before finalizing rewards in the same order.
    """

    def __init__(self, envs: Sequence[SelfPlayBattleEnv]) -> None:
        if not envs:
            raise ValueError("at least one environment is required")
        self.envs = tuple(envs)
        backends = {env.simulation_backend for env in self.envs}
        if len(backends) != 1:
            raise ValueError("scheduled environments must use one simulator backend")
        self.backend = next(iter(backends))
        devices = {env._simulator.device for env in self.envs}
        if len(devices) != 1:
            raise ValueError("scheduled environments must use one simulator device")
        self._device = next(iter(devices))
        self._executor = TorchBattleExecutor(
            self.backend,
            device=self._device,
        )
        self._simulator_metrics: dict[str, float] = defaultdict(float)
        self.metrics = BatchScheduleMetrics()

    def step(
        self,
        actions: Sequence[dict[int, int]],
        *,
        pre_action_masks: Sequence[dict[int, np.ndarray] | None] | None = None,
    ) -> list[StepResult]:
        """Advance one decision window for every scheduled environment."""

        if len(actions) != len(self.envs):
            raise ValueError("actions must contain one mapping per environment")
        masks: tuple[dict[int, np.ndarray] | None, ...] = (
            tuple(None for _ in self.envs)
            if pre_action_masks is None
            else tuple(pre_action_masks)
        )
        if len(masks) != len(self.envs):
            raise ValueError(
                "pre_action_masks must contain one mapping per environment"
            )

        prepared = [
            env.prepare_step(action, pre_action_masks=mask)
            for env, action, mask in zip(self.envs, actions, masks)
        ]
        self.metrics.step_calls += 1
        self.metrics.battle_windows += len(self.envs)

        if self.backend is SimulatorBackend.PYTHON:
            advanced = [
                env.advance_prepared_step(step)
                for env, step in zip(self.envs, prepared)
            ]
            self._simulator_metrics["python_ticks"] += float(sum(advanced))
        else:
            # Action ingress mutates player/entity state without advancing the
            # battle clock. The current executor cache validates clocks only,
            # so carrying it across decision windows could resurrect the
            # pre-action tensor state. Rebuild after every prepare phase until
            # BattleState exposes mutation-version validation.
            for key, value in self._executor.metrics_dict().items():
                self._simulator_metrics[key] += value
            self._executor = TorchBattleExecutor(
                self.backend,
                device=self._device,
            )
            advanced = [0 for _ in self.envs]
            groups: dict[int, list[int]] = defaultdict(list)
            for index, step in enumerate(prepared):
                if step.remaining_ticks > 0:
                    groups[step.remaining_ticks].append(index)
            for ticks in sorted(groups):
                indices = groups[ticks]
                battles = []
                for index in indices:
                    battle = self.envs[index].battle
                    assert battle is not None
                    battles.append(battle)
                counts = self._executor.step_battles(battles, ticks)
                for index, count in zip(indices, counts):
                    advanced[index] = count
                self.metrics.tensor_batches += 1
                self.metrics.max_batch_size = max(
                    self.metrics.max_batch_size,
                    len(indices),
                )

        return [
            env.finish_prepared_step(step, ticks)
            for env, step, ticks in zip(self.envs, prepared, advanced)
        ]

    def metrics_dict(self) -> dict[str, int | float]:
        simulator_metrics = dict(self._simulator_metrics)
        for key, value in self._executor.metrics_dict().items():
            simulator_metrics[key] = simulator_metrics.get(key, 0.0) + value
        return {**self.metrics.as_dict(), **simulator_metrics}
