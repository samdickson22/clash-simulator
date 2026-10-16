from __future__ import annotations

import math

import torch
from torch import Tensor, nn


class StructuredPublicStateTracker(nn.Module):
    """Exact model-owned bookkeeping over current-frame public observations.

    The tracker deliberately has no trainable parameters and never queries the
    simulator.  Its recurrent tensor is part of the policy state, so deployed
    inference only needs a current clock observation and a current opponent
    card-play event from the visual front end.

    Eight revealed-card slots are enough for a legal Clash Royale deck.  Each
    slot stores the card ID, the number of subsequent confirmed plays (clipped
    at four), and whether the card can therefore have returned to hand.
    """

    EVENT_ID_INDEX = 0
    EVENT_LATCH_INDEX = 1
    PUBLIC_CLOCK_INDEX = 2
    PUBLIC_CLOCK_CONFIDENCE_INDEX = 3
    RESOURCE_CONFIDENCE_INDEX = 4
    MISSED_PLAY_LOWER_BOUND_INDEX = 5
    REVEALED_COUNT_INDEX = 6
    UNCERTAIN_EVENT_MASS_INDEX = 7
    CARD_IDS_START = 8
    CYCLE_COUNTS_START = 16
    AVAILABLE_START = 24
    CARD_SLOTS = 8
    REQUIRED_STATE_SIZE = AVAILABLE_START + CARD_SLOTS

    def __init__(
        self,
        state_size: int,
        *,
        clock_horizon_steps: int,
        event_confidence_threshold: float = 0.5,
        clock_confidence_threshold: float = 0.5,
    ) -> None:
        super().__init__()
        if state_size < self.REQUIRED_STATE_SIZE:
            raise ValueError(
                "structured deterministic public state requires at least "
                f"{self.REQUIRED_STATE_SIZE} channels"
            )
        if clock_horizon_steps <= 0:
            raise ValueError("clock_horizon_steps must be positive")
        if not 0.0 <= event_confidence_threshold <= 1.0:
            raise ValueError("event confidence threshold must be in [0, 1]")
        if not 0.0 <= clock_confidence_threshold <= 1.0:
            raise ValueError("clock confidence threshold must be in [0, 1]")
        self.state_size = int(state_size)
        self.clock_horizon_steps = int(clock_horizon_steps)
        self.event_confidence_threshold = float(event_confidence_threshold)
        self.clock_confidence_threshold = float(clock_confidence_threshold)

    def initial_state(
        self,
        batch_size: int,
        *,
        dtype: torch.dtype,
        device: torch.device,
    ) -> Tensor:
        state = torch.zeros(
            (batch_size, self.state_size),
            dtype=dtype,
            device=device,
        )
        state[:, self.RESOURCE_CONFIDENCE_INDEX] = 1.0
        return state

    def forward(
        self,
        previous_state: Tensor,
        event_ids: Tensor,
        event_confidence: Tensor,
        clock_observation: Tensor,
        clock_confidence: Tensor,
    ) -> tuple[Tensor, Tensor, Tensor, Tensor]:
        """Advance bookkeeping and return state, pulse, old clock, new clock."""

        if previous_state.ndim != 2 or previous_state.shape[-1] != self.state_size:
            raise ValueError("public-state recurrent tensor has the wrong shape")
        expected = previous_state.shape[:-1]
        for name, value in (
            ("event IDs", event_ids),
            ("event confidence", event_confidence),
            ("clock observation", clock_observation),
            ("clock confidence", clock_confidence),
        ):
            if value.shape != expected:
                raise ValueError(f"{name} shape does not match public state")

        dtype = previous_state.dtype
        state = previous_state.clone()
        previous_clock = previous_state[:, self.PUBLIC_CLOCK_INDEX]
        fallback_clock = (previous_clock + 1.0 / self.clock_horizon_steps).clamp(
            0.0, 2.0
        )
        clock_is_usable = (
            (clock_confidence >= self.clock_confidence_threshold)
            & torch.isfinite(clock_observation)
            & (clock_observation >= previous_clock - 1e-7)
        )
        current_clock = torch.where(
            clock_is_usable,
            clock_observation.clamp(0.0, 2.0),
            fallback_clock,
        )
        state[:, self.PUBLIC_CLOCK_INDEX] = current_clock
        state[:, self.PUBLIC_CLOCK_CONFIDENCE_INDEX] = torch.where(
            clock_is_usable,
            clock_confidence.clamp(0.0, 1.0),
            previous_state[:, self.PUBLIC_CLOCK_CONFIDENCE_INDEX]
            * torch.tensor(0.99, dtype=dtype, device=state.device),
        )

        event_ids = event_ids.clamp_min(0)
        event_visible = event_ids > 0
        event_is_confident = event_confidence >= self.event_confidence_threshold
        event_active = event_visible & event_is_confident
        previous_latched = previous_state[:, self.EVENT_LATCH_INDEX] > 0.5
        previous_event_id = previous_state[:, self.EVENT_ID_INDEX].long()
        new_event = event_active & (
            (~previous_latched) | (event_ids != previous_event_id)
        )
        state[:, self.EVENT_ID_INDEX] = torch.where(
            event_active,
            event_ids.to(dtype),
            torch.zeros_like(event_ids, dtype=dtype),
        )
        state[:, self.EVENT_LATCH_INDEX] = event_active.to(dtype)

        uncertain = event_visible & (~event_is_confident)
        state[:, self.UNCERTAIN_EVENT_MASS_INDEX] = previous_state[
            :, self.UNCERTAIN_EVENT_MASS_INDEX
        ] + uncertain.to(dtype) * (1.0 - event_confidence.clamp(0.0, 1.0))
        state[:, self.RESOURCE_CONFIDENCE_INDEX] = torch.where(
            uncertain,
            torch.minimum(
                previous_state[:, self.RESOURCE_CONFIDENCE_INDEX],
                event_confidence.clamp(0.0, 1.0),
            ),
            previous_state[:, self.RESOURCE_CONFIDENCE_INDEX],
        )

        card_ids = previous_state[
            :, self.CARD_IDS_START : self.CARD_IDS_START + self.CARD_SLOTS
        ].long()
        cycle_counts = previous_state[
            :, self.CYCLE_COUNTS_START : self.CYCLE_COUNTS_START + self.CARD_SLOTS
        ]
        matching = card_ids == event_ids.unsqueeze(-1)
        found = matching.any(dim=-1) & (event_ids > 1)
        matched_count = torch.where(
            matching,
            cycle_counts,
            torch.full_like(cycle_counts, 4.0),
        ).amin(dim=-1)
        missing_before_repeat = torch.where(
            new_event & found,
            (4.0 - matched_count).clamp_min(0.0),
            torch.zeros_like(matched_count),
        )
        state[:, self.MISSED_PLAY_LOWER_BOUND_INDEX] = (
            previous_state[:, self.MISSED_PLAY_LOWER_BOUND_INDEX]
            + missing_before_repeat
        )
        has_missed_play = missing_before_repeat > 0
        state[:, self.RESOURCE_CONFIDENCE_INDEX] = torch.where(
            has_missed_play,
            torch.zeros_like(previous_state[:, self.RESOURCE_CONFIDENCE_INDEX]),
            state[:, self.RESOURCE_CONFIDENCE_INDEX],
        )

        advance = (1.0 + missing_before_repeat).unsqueeze(-1)
        updated_counts = torch.where(
            new_event.unsqueeze(-1) & (card_ids > 0),
            (cycle_counts + advance).clamp_max(4.0),
            cycle_counts,
        )
        updated_counts = torch.where(
            new_event.unsqueeze(-1) & matching,
            torch.zeros_like(updated_counts),
            updated_counts,
        )

        new_known_card = new_event & (~found) & (event_ids > 1)
        empty = card_ids == 0
        first_empty = empty.to(torch.int64).argmax(dim=-1)
        has_empty = empty.any(dim=-1)
        insert = new_known_card & has_empty
        insert_mask = torch.nn.functional.one_hot(
            first_empty,
            num_classes=self.CARD_SLOTS,
        ).to(torch.bool)
        card_ids = torch.where(
            insert.unsqueeze(-1) & insert_mask,
            event_ids.unsqueeze(-1),
            card_ids,
        )
        updated_counts = torch.where(
            insert.unsqueeze(-1) & insert_mask,
            torch.zeros_like(updated_counts),
            updated_counts,
        )
        state[:, self.CARD_IDS_START : self.CARD_IDS_START + self.CARD_SLOTS] = (
            card_ids.to(dtype)
        )
        state[
            :, self.CYCLE_COUNTS_START : self.CYCLE_COUNTS_START + self.CARD_SLOTS
        ] = updated_counts
        state[:, self.AVAILABLE_START : self.AVAILABLE_START + self.CARD_SLOTS] = (
            (card_ids > 0) & (updated_counts >= 4.0)
        ).to(dtype)
        state[:, self.REVEALED_COUNT_INDEX] = (card_ids > 0).sum(dim=-1, dtype=dtype)

        unknown_confirmed = new_event & (event_ids <= 1)
        overflow = new_known_card & (~has_empty)
        state[:, self.RESOURCE_CONFIDENCE_INDEX] = torch.where(
            unknown_confirmed | overflow,
            torch.zeros_like(state[:, self.RESOURCE_CONFIDENCE_INDEX]),
            state[:, self.RESOURCE_CONFIDENCE_INDEX],
        )
        return state, new_event, previous_clock, current_clock


class StructuredBeliefCell(nn.Module):
    """Small model-owned state update without dense recurrent mixing.

    State channel zero is a deterministic decision clock. Channel one is an
    opponent-elixir belief trained through the existing privileged auxiliary
    target, but updated at inference only from the current encoded public
    observation and the cell's previous private state. Remaining channels are
    independent leaky accumulators with learned, input-only update gates.

    Unlike an LSTM/GRU, no learned matrix mixes the previous hidden state into
    a new candidate state. This makes the persistent mechanisms explicit while
    leaving the downstream policy feed-forward over current tokens plus state.
    """

    CLOCK_INDEX = 0
    OPPONENT_ELIXIR_INDEX = 1
    RESERVED_CHANNELS = 2

    def __init__(
        self,
        input_size: int,
        state_size: int,
        *,
        clock_horizon_steps: int = 750,
        deterministic_resource: bool = False,
    ) -> None:
        super().__init__()
        if input_size <= 0:
            raise ValueError("input_size must be positive")
        if state_size < 8:
            raise ValueError("structured belief state must have at least 8 channels")
        if clock_horizon_steps <= 0:
            raise ValueError("clock_horizon_steps must be positive")
        self.input_size = int(input_size)
        self.state_size = int(state_size)
        self.clock_horizon_steps = int(clock_horizon_steps)
        self.deterministic_resource = bool(deterministic_resource)

        learned_size = state_size - self.RESERVED_CHANNELS
        self.candidate_projection = nn.Linear(input_size, learned_size)
        self.input_retention_projection = nn.Linear(input_size, learned_size)

        # Cover immediate tactical context through roughly two minutes of
        # decision history. These are learned further, but begin as an
        # interpretable bank of independent exponential timescales.
        timescales = torch.logspace(
            math.log10(2.0),
            math.log10(300.0),
            learned_size,
        )
        retention = torch.exp(-1.0 / timescales).clamp(1e-4, 1.0 - 1e-4)
        self.retention_logits = nn.Parameter(torch.logit(retention))

        # The elixir channel is an actual bounded accumulator. The learned
        # spend detector sees the current encoded observation and the previous
        # leaky belief bank, but never privileged state at inference.
        self.opponent_spend_projection = nn.Linear(
            input_size + learned_size,
            1,
        )
        nn.init.zeros_(self.opponent_spend_projection.weight)
        nn.init.constant_(self.opponent_spend_projection.bias, -7.0)
        self.opponent_regen_logit = nn.Parameter(
            torch.tensor(math.log(0.015 / (1.0 - 0.015)))
        )

    def initial_state(
        self,
        batch_size: int,
        *,
        dtype: torch.dtype,
        device: torch.device,
    ) -> Tensor:
        state = torch.zeros(
            (batch_size, self.state_size),
            dtype=dtype,
            device=device,
        )
        # Standard 1v1 begins at six elixir. Legacy learned-resource checkpoints
        # retain their historical full-value initialization for compatibility.
        state[:, self.OPPONENT_ELIXIR_INDEX] = (
            0.6 if self.deterministic_resource else 1.0
        )
        return state

    def forward(
        self,
        inputs: Tensor,
        previous_state: Tensor,
        observed_spend: Tensor | None = None,
        deterministic_regen: Tensor | None = None,
    ) -> Tensor:
        if inputs.shape[-1] != self.input_size:
            raise ValueError("structured belief input width does not match cell")
        if previous_state.shape[:-1] != inputs.shape[:-1]:
            raise ValueError("structured belief batch shape does not match input")
        if previous_state.shape[-1] != self.state_size:
            raise ValueError("structured belief state width does not match cell")
        for name, value in (
            ("observed spend", observed_spend),
            ("deterministic regen", deterministic_regen),
        ):
            if value is not None and value.shape != inputs.shape[:-1] + (1,):
                raise ValueError(f"{name} shape does not match structured input")
        if self.deterministic_resource and (
            observed_spend is None or deterministic_regen is None
        ):
            raise ValueError(
                "deterministic resource requires observed spend and regeneration"
            )

        previous_learned = previous_state[..., self.RESERVED_CHANNELS :]
        candidate = torch.tanh(self.candidate_projection(inputs))
        input_retention = 0.5 * torch.tanh(self.input_retention_projection(inputs))
        retention = torch.sigmoid(self.retention_logits + input_retention)
        learned = retention * previous_learned + (1.0 - retention) * candidate

        clock_delta = 1.0 / float(self.clock_horizon_steps)
        clock = (
            previous_state[..., self.CLOCK_INDEX : self.CLOCK_INDEX + 1] + clock_delta
        ).clamp(0.0, 2.0)

        if self.deterministic_resource:
            assert observed_spend is not None
            assert deterministic_regen is not None
            spend = observed_spend
            regen = deterministic_regen
        else:
            spend = torch.sigmoid(
                self.opponent_spend_projection(torch.cat([inputs, learned], dim=-1))
            )
            regen = torch.sigmoid(self.opponent_regen_logit)
        raw_opponent_elixir = (
            previous_state[
                ...,
                self.OPPONENT_ELIXIR_INDEX : self.OPPONENT_ELIXIR_INDEX + 1,
            ]
            + regen
            - spend
        )
        # Preserve a physically bounded inference state without killing the
        # auxiliary gradient when the accumulator begins saturated at full
        # elixir. The forward value is exactly clamped; backward uses the
        # identity derivative through the boundary.
        clamped_opponent_elixir = raw_opponent_elixir.clamp(0.0, 1.0)
        opponent_elixir = (
            raw_opponent_elixir
            + (clamped_opponent_elixir - raw_opponent_elixir).detach()
        )
        return torch.cat([clock, opponent_elixir, learned], dim=-1)
