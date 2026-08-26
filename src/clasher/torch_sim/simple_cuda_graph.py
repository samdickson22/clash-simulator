"""CUDA Graph execution boundary for the fixed-shape practical Gym.

``SimpleGymRuntime`` deliberately keeps its eager implementation readable and
independently testable.  This wrapper captures one bound runtime tick and then
replays it with a static action buffer, reducing thousands of eager host kernel
submissions to one graph submission without duplicating game mechanics.
"""

from __future__ import annotations

import torch

from .simple_actions import FastActionKernel, FastActionState
from .simple_outcomes import FastOutcomeTracker
from .simple_projection import SimpleProjectedObservation, SimpleTensorProjector
from .simple_runtime import SimpleGymRuntime, SimpleGymRuntimeStep
from .simple_spawn_blueprints import FastSpawnBlueprintCatalog
from .simple_state import FastGymState


class SimpleCudaGraphRunner:
    """Replay a fixed-shape ``SimpleGymRuntime`` tick as one CUDA Graph.

    Capture records the tick but does not commit a transition.  Each
    ``step_tick`` call copies the caller's actions into a stable device buffer
    and replays the graph once.  The returned object and all of its tensor
    fields are static graph outputs and are overwritten by the next replay;
    collectors that retain transitions must copy them into rollout storage.
    """

    def __init__(
        self,
        runtime: SimpleGymRuntime,
        example_action_ids: torch.Tensor,
    ) -> None:
        if runtime.device.type != "cuda" or not torch.cuda.is_available():
            raise ValueError("SimpleCudaGraphRunner requires a CUDA runtime")
        self.runtime = runtime
        self._validate_actions(example_action_ids)
        self._action_ids = example_action_ids.clone()
        self._graph = torch.cuda.CUDAGraph()

        torch.cuda.synchronize(runtime.device)
        with torch.cuda.device(runtime.device), torch.cuda.graph(self._graph):
            self._step = runtime.step_tick(self._action_ids)
        torch.cuda.synchronize(runtime.device)

    @property
    def device(self) -> torch.device:
        return self.runtime.device

    @property
    def batch_size(self) -> int:
        return self.runtime.batch_size

    @property
    def state(self) -> FastGymState:
        return self.runtime.state

    @property
    def outcomes(self) -> FastOutcomeTracker:
        return self.runtime.outcomes

    @property
    def action_state(self) -> FastActionState:
        return self.runtime.action_state

    @property
    def action_kernel(self) -> FastActionKernel:
        return self.runtime.action_kernel

    @property
    def projector(self) -> SimpleTensorProjector:
        return self.runtime.projector

    @property
    def tick_seconds(self) -> float:
        return self.runtime.tick_seconds

    @property
    def double_elixir_tick(self) -> int | None:
        return self.runtime.double_elixir_tick

    @property
    def triple_elixir_tick(self) -> int | None:
        return self.runtime.triple_elixir_tick

    @property
    def spawn_blueprints(self) -> FastSpawnBlueprintCatalog | None:
        return self.runtime.spawn_blueprints

    def _validate_actions(self, action_ids: torch.Tensor) -> None:
        if action_ids.shape != (self.batch_size, 2):
            raise ValueError("action_ids must have shape [batch, 2]")
        if action_ids.device != self.device:
            raise ValueError("action_ids must use the runtime device")
        if action_ids.dtype != torch.int64:
            raise ValueError("action_ids must be int64")

    def step_tick(self, action_ids: torch.Tensor) -> SimpleGymRuntimeStep:
        """Copy dynamic actions and enqueue one captured runtime transition."""

        self._validate_actions(action_ids)
        self._action_ids.copy_(action_ids)
        self._graph.replay()
        return self._step

    def observe(self) -> SimpleProjectedObservation:
        """Project current state outside the graph without advancing it."""

        return self.runtime.observe()

    def reset_rows(
        self,
        reset_mask: torch.Tensor,
        deck_ids: torch.Tensor | None = None,
    ) -> SimpleProjectedObservation:
        """Reset selected rows while retaining the captured tensor addresses."""

        return self.runtime.reset_rows(reset_mask, deck_ids=deck_ids)


__all__ = ["SimpleCudaGraphRunner"]
