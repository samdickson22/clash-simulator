"""CUDA Graph execution boundary for the fixed-shape practical Gym.

``SimpleGymRuntime`` deliberately keeps its eager implementation readable and
independently testable.  This wrapper captures one bound runtime tick and then
replays it with a static action buffer, reducing thousands of eager host kernel
submissions to one graph submission without duplicating game mechanics.
"""

from __future__ import annotations

import torch

from clasher.rl.common import NUM_HAND_SLOTS

from .simple_actions import FastActionKernel, FastActionState
from .simple_outcomes import FastOutcomeTracker
from .simple_projection import SimpleProjectedObservation, SimpleTensorProjector
from .simple_runtime import SimpleGymRuntime, SimpleGymRuntimeStep
from .simple_spawn_blueprints import FastSpawnBlueprintCatalog
from .simple_state import FastGymState


class SimpleCudaGraphRunner:
    """Replay a fixed-shape ``SimpleGymRuntime`` tick as one CUDA Graph.

    Capture records the tick and both selective-reset variants with semantic
    no-op inputs, so construction does not mutate the episode.  Each hot-path
    call copies dynamic inputs into stable device buffers and replays one graph.
    Returned objects and all of their tensor fields are static graph outputs;
    consumers that retain transitions or reset observations must copy them.
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
        self._reset_mask = torch.zeros(
            self.batch_size,
            dtype=torch.bool,
            device=self.device,
        )
        self._reset_deck_ids = torch.cat(
            (runtime.action_state.hand_ids, runtime.action_state.cycle_ids),
            dim=2,
        ).clone()
        self._reset_graph = torch.cuda.CUDAGraph()
        self._reset_with_decks_graph = torch.cuda.CUDAGraph()

        torch.cuda.synchronize(runtime.device)
        with torch.cuda.device(runtime.device):
            with torch.cuda.graph(self._graph):
                self._step = runtime.step_tick(self._action_ids)
            with torch.cuda.graph(self._reset_graph):
                self._reset_observation = runtime.reset_rows(self._reset_mask)
            with torch.cuda.graph(self._reset_with_decks_graph):
                # ``SimpleGymRuntime.reset_rows`` validates public deck IDs with
                # a host-side boolean reduction.  Runtime callers are validated
                # before replay below; capture therefore performs the ordinary
                # reset first and applies the already-validated dynamic decks
                # through the same three dense row-select mutations.
                runtime.reset_rows(self._reset_mask)
                hand = self._reset_deck_ids[:, :, :NUM_HAND_SLOTS]
                cycle = self._reset_deck_ids[:, :, NUM_HAND_SLOTS:]
                runtime._restore_rows_(
                    runtime.action_state.hand_ids,
                    hand,
                    self._reset_mask,
                )
                runtime._restore_rows_(
                    runtime.action_state.cycle_ids,
                    cycle,
                    self._reset_mask,
                )
                projected_hand = torch.cat(
                    (
                        runtime.action_state.hand_ids,
                        runtime.action_state.own_next[..., None],
                    ),
                    dim=2,
                )
                runtime._restore_rows_(
                    runtime._projection_hand_ids,
                    projected_hand,
                    self._reset_mask,
                )
                self._reset_with_decks_observation = runtime.projector.project(
                    runtime._legal_action_mask()
                )
        torch.cuda.synchronize(runtime.device)

    @property
    def device(self) -> torch.device:
        return self.runtime.device

    @property
    def batch_size(self) -> int:
        return int(self.runtime.batch_size)

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
        return float(self.runtime.tick_seconds)

    @property
    def double_elixir_tick(self) -> int | None:
        value = self.runtime.double_elixir_tick
        return None if value is None else int(value)

    @property
    def triple_elixir_tick(self) -> int | None:
        value = self.runtime.triple_elixir_tick
        return None if value is None else int(value)

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

    def _validate_reset_mask(self, reset_mask: torch.Tensor) -> None:
        if reset_mask.shape != (self.batch_size,):
            raise ValueError("reset_mask must have shape [batch]")
        if reset_mask.device != self.device:
            raise ValueError("reset_mask must use the runtime device")
        if reset_mask.dtype != torch.bool:
            raise ValueError("reset_mask must be bool")

    def _validate_reset_decks(self, deck_ids: torch.Tensor) -> None:
        if deck_ids.shape != (self.batch_size, 2, 8):
            raise ValueError("deck_ids must have shape [batch, 2, 8]")
        if deck_ids.device != self.device:
            raise ValueError("deck_ids must use the runtime device")
        if deck_ids.dtype != torch.int64:
            raise ValueError("deck_ids must be int64")
        if self.spawn_blueprints is None:
            return
        size = self.action_kernel.catalog.size
        safe_deck = deck_ids.clamp(0, size - 1)
        public_deck = (
            (deck_ids >= 0)
            & (deck_ids < size)
            & self.spawn_blueprints.public_card_mask[safe_deck]
        )
        if not bool(public_deck.all()):
            raise ValueError("deck_ids may contain only public catalog rows")

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
        """Replay a captured selective reset without eager per-plane launches."""

        self._validate_reset_mask(reset_mask)
        if deck_ids is not None:
            self._validate_reset_decks(deck_ids)
        self._reset_mask.copy_(reset_mask)
        if deck_ids is None:
            self._reset_graph.replay()
            return self._reset_observation
        self._reset_deck_ids.copy_(deck_ids)
        self._reset_with_decks_graph.replay()
        return self._reset_with_decks_observation


__all__ = ["SimpleCudaGraphRunner"]
