from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest
import torch
from torch import nn

from clasher.rl.model import ClasherPolicy, PolicyConfig, PolicyInputs
from clasher.rl.structured_memory import (
    StructuredBeliefCell,
    StructuredPublicStateTracker,
)
from clasher.rl.structured_obs import StructuredObservationBuilder
from clasher.rl.train_recurrent import _current_opponent_play_events


def test_structured_belief_cell_initializes_clock_and_elixir() -> None:
    cell = StructuredBeliefCell(16, 16, clock_horizon_steps=100)

    state = cell.initial_state(
        3,
        dtype=torch.float32,
        device=torch.device("cpu"),
    )

    assert state.shape == (3, 16)
    assert torch.equal(state[:, 0], torch.zeros(3))
    assert torch.equal(state[:, 1], torch.ones(3))
    assert not torch.count_nonzero(state[:, 2:])


def test_structured_belief_clock_advances_and_resets_inside_policy() -> None:
    builder = StructuredObservationBuilder(card_vocab=["Knight"], max_entities=8)
    model = ClasherPolicy(
        PolicyConfig(
            num_tokens=builder.spec.num_tokens,
            max_entities=builder.spec.max_entities,
            d_model=16,
            num_heads=4,
            actor_layers=1,
            critic_layers=1,
            memory_size=16,
            memory_kind="structured",
            structured_clock_horizon_steps=100,
        ),
        builder.card_stat_features,
    )
    global_context = torch.zeros((1, 4, model.config.d_model))
    previous_actions = torch.full((1, 4), model.num_actions - 2, dtype=torch.long)
    previous_rewards = torch.zeros((1, 4))
    episode_starts = torch.tensor([[True, False, False, True]])

    memory, next_state = model._run_memory(
        global_context,
        previous_actions,
        previous_rewards,
        episode_starts,
        state=None,
    )

    assert torch.allclose(
        memory[0, :, StructuredBeliefCell.CLOCK_INDEX],
        torch.tensor([0.01, 0.02, 0.03, 0.01]),
    )
    assert torch.equal(
        memory[0, :, StructuredBeliefCell.OPPONENT_ELIXIR_INDEX],
        torch.ones(4),
    )
    assert torch.equal(next_state[0], memory[:, -1])
    assert torch.equal(next_state[1], memory[:, -1])


def test_structured_belief_has_no_lstm_or_gru_recurrence() -> None:
    cell = StructuredBeliefCell(32, 32)

    assert not any(
        isinstance(module, (nn.LSTM, nn.LSTMCell, nn.GRU, nn.GRUCell))
        for module in cell.modules()
    )


def test_structured_opponent_elixir_channel_is_bounded_and_trainable() -> None:
    torch.manual_seed(7)
    cell = StructuredBeliefCell(16, 16)
    state = cell.initial_state(
        2,
        dtype=torch.float32,
        device=torch.device("cpu"),
    )
    inputs = torch.randn((2, 16))

    result = cell(inputs, state)
    elixir = result[:, StructuredBeliefCell.OPPONENT_ELIXIR_INDEX]
    loss = (elixir - torch.tensor([0.2, 0.7])).square().mean()
    loss.backward()

    assert bool(((0.0 <= elixir) & (elixir <= 1.0)).all())
    assert cell.opponent_spend_projection.weight.grad is not None
    assert torch.isfinite(cell.opponent_spend_projection.weight.grad).all()


def test_structured_elixir_auxiliary_gradient_crosses_full_boundary() -> None:
    cell = StructuredBeliefCell(16, 16)
    state = cell.initial_state(
        1,
        dtype=torch.float32,
        device=torch.device("cpu"),
    )

    elixir = cell(torch.zeros((1, 16)), state)[
        :, StructuredBeliefCell.OPPONENT_ELIXIR_INDEX
    ]
    (elixir - 0.2).square().mean().backward()

    assert torch.equal(elixir, torch.ones_like(elixir))
    assert cell.opponent_spend_projection.bias.grad is not None
    assert float(cell.opponent_spend_projection.bias.grad.abs().item()) > 0.0


def test_structured_memory_config_rejects_too_few_channels() -> None:
    with pytest.raises(ValueError, match="memory_size >= 8"):
        PolicyConfig(
            num_tokens=4,
            max_entities=8,
            memory_kind="structured",
            memory_size=7,
        )


def test_deterministic_public_state_rejects_external_history_contract() -> None:
    with pytest.raises(ValueError, match="not accumulated public history"):
        PolicyConfig(
            num_tokens=8,
            max_entities=8,
            memory_kind="structured",
            memory_size=32,
            public_history_slots=1,
            structured_deterministic_resource_enabled=True,
        )


def test_structured_memory_policy_forward_is_finite() -> None:
    builder = StructuredObservationBuilder(card_vocab=["Knight"], max_entities=8)
    model = ClasherPolicy(
        PolicyConfig(
            num_tokens=builder.spec.num_tokens,
            max_entities=builder.spec.max_entities,
            d_model=16,
            num_heads=4,
            actor_layers=1,
            critic_layers=1,
            memory_size=16,
            memory_kind="structured",
        ),
        builder.card_stat_features,
    ).eval()
    batch = 2
    sequence = 3
    action_mask = torch.zeros(
        (batch, sequence, model.num_actions),
        dtype=torch.bool,
    )
    action_mask[..., -2] = True
    inputs = PolicyInputs(
        entity_ids=torch.zeros((batch, sequence, 8), dtype=torch.long),
        entity_features=torch.zeros((batch, sequence, 8, 32)),
        entity_mask=torch.zeros((batch, sequence, 8), dtype=torch.bool),
        hand_ids=torch.zeros((batch, sequence, 5), dtype=torch.long),
        global_features=torch.zeros((batch, sequence, 18)),
        action_mask=action_mask,
        previous_actions=torch.full(
            (batch, sequence),
            model.num_actions - 2,
            dtype=torch.long,
        ),
        previous_rewards=torch.zeros((batch, sequence)),
        episode_starts=torch.tensor([[True, False, False], [True, False, False]]),
    )

    with torch.no_grad():
        output = model(inputs)
        changed_globals = inputs.global_features.clone()
        changed_globals[..., :5] = torch.rand_like(changed_globals[..., :5])
        changed_clock = model(replace(inputs, global_features=changed_globals))

    assert output.joint_logits.shape == (batch, sequence, model.num_actions)
    assert output.next_state[0].shape == (batch, model.config.memory_size)
    assert torch.isfinite(output.joint_logits[inputs.action_mask]).all()
    assert np.isfinite(output.opponent_elixir.detach().numpy()).all()
    torch.testing.assert_close(
        output.opponent_elixir[:, -1],
        output.next_state[0][
            :,
            StructuredBeliefCell.OPPONENT_ELIXIR_INDEX,
        ],
    )
    torch.testing.assert_close(changed_clock.joint_logits, output.joint_logits)
    torch.testing.assert_close(changed_clock.next_state[0], output.next_state[0])


def test_structured_resource_policy_gate_preserves_policy_until_opened() -> None:
    builder = StructuredObservationBuilder(card_vocab=["Knight"], max_entities=8)
    config = PolicyConfig(
        num_tokens=builder.spec.num_tokens,
        max_entities=builder.spec.max_entities,
        d_model=16,
        num_heads=4,
        actor_layers=1,
        critic_layers=1,
        memory_size=16,
        memory_kind="structured",
    )
    parent = ClasherPolicy(config, builder.card_stat_features).eval()
    gated = ClasherPolicy(
        replace(config, structured_resource_policy_gate_enabled=True),
        builder.card_stat_features,
    ).eval()
    incompatible = gated.load_state_dict(parent.state_dict(), strict=False)
    assert not incompatible.unexpected_keys
    assert incompatible.missing_keys == ["structured_resource_policy_gate"]
    assert isinstance(gated.memory, StructuredBeliefCell)
    with torch.no_grad():
        gated.memory.opponent_spend_projection.bias.fill_(10.0)

    action_mask = torch.zeros((1, 3, parent.num_actions), dtype=torch.bool)
    action_mask[..., -2] = True
    inputs = PolicyInputs(
        entity_ids=torch.zeros((1, 3, 8), dtype=torch.long),
        entity_features=torch.zeros((1, 3, 8, 32)),
        entity_mask=torch.zeros((1, 3, 8), dtype=torch.bool),
        hand_ids=torch.zeros((1, 3, 5), dtype=torch.long),
        global_features=torch.zeros((1, 3, 18)),
        action_mask=action_mask,
        previous_actions=torch.full((1, 3), parent.num_actions - 2, dtype=torch.long),
        previous_rewards=torch.zeros((1, 3)),
        episode_starts=torch.tensor([[True, False, False]]),
    )

    with torch.no_grad():
        parent_output = parent(inputs)
        closed_output = gated(inputs)

    assert torch.equal(parent_output.joint_logits, closed_output.joint_logits)
    assert torch.equal(
        parent_output.opponent_hand_logits,
        closed_output.opponent_hand_logits,
    )
    assert not torch.equal(
        parent_output.opponent_elixir,
        closed_output.opponent_elixir,
    )

    assert gated.structured_resource_policy_gate is not None
    with torch.no_grad():
        gated.structured_resource_policy_gate.fill_(10.0)
        opened_output = gated(inputs)
    assert not torch.equal(
        parent_output.action_type_logits,
        opened_output.action_type_logits,
    )


def _public_tracker() -> StructuredPublicStateTracker:
    return StructuredPublicStateTracker(32, clock_horizon_steps=750)


def _advance_public_tracker(
    tracker: StructuredPublicStateTracker,
    state: torch.Tensor,
    *,
    card_id: int = 0,
    event_confidence: float = 0.0,
    clock: float = 0.0,
    clock_confidence: float = 1.0,
) -> tuple[torch.Tensor, bool]:
    updated, pulse, _, _ = tracker(
        state,
        torch.tensor([card_id]),
        torch.tensor([event_confidence]),
        torch.tensor([clock]),
        torch.tensor([clock_confidence]),
    )
    return updated, bool(pulse.item())


def test_model_owned_public_state_deduplicates_a_persistent_play_event() -> None:
    tracker = _public_tracker()
    state = tracker.initial_state(
        1,
        dtype=torch.float32,
        device=torch.device("cpu"),
    )

    state, first = _advance_public_tracker(
        tracker, state, card_id=7, event_confidence=1.0
    )
    state, duplicate = _advance_public_tracker(
        tracker, state, card_id=7, event_confidence=1.0
    )

    assert first
    assert not duplicate
    assert state[0, StructuredPublicStateTracker.REVEALED_COUNT_INDEX] == 1
    assert state[0, StructuredPublicStateTracker.CYCLE_COUNTS_START] == 0


def test_simulator_teacher_adapter_emits_only_current_frame_event_pulse() -> None:
    observations = [
        SimpleNamespace(
            opponent_history_ids=np.asarray([7]),
            opponent_history_ages=np.asarray([0.01], dtype=np.float32),
        ),
        SimpleNamespace(
            opponent_history_ids=np.asarray([8]),
            opponent_history_ages=np.asarray([0.02], dtype=np.float32),
        ),
        SimpleNamespace(
            opponent_history_ids=np.zeros((0,), dtype=np.int64),
            opponent_history_ages=np.zeros((0,), dtype=np.float32),
        ),
    ]

    ids, confidence = _current_opponent_play_events(observations)  # type: ignore[arg-type]

    np.testing.assert_array_equal(ids, np.asarray([7, 0, 0]))
    np.testing.assert_array_equal(confidence, np.asarray([1.0, 0.0, 0.0]))


def test_model_owned_public_state_marks_four_card_return_exactly() -> None:
    tracker = _public_tracker()
    state = tracker.initial_state(
        1,
        dtype=torch.float32,
        device=torch.device("cpu"),
    )
    for card_id in (7, 8, 9, 10, 11):
        state, pulse = _advance_public_tracker(
            tracker,
            state,
            card_id=card_id,
            event_confidence=1.0,
        )
        assert pulse

    assert state[0, StructuredPublicStateTracker.CARD_IDS_START] == 7
    assert state[0, StructuredPublicStateTracker.CYCLE_COUNTS_START] == 4
    assert state[0, StructuredPublicStateTracker.AVAILABLE_START] == 1


def test_model_owned_public_state_handles_uncertain_and_missed_events() -> None:
    tracker = _public_tracker()
    state = tracker.initial_state(
        1,
        dtype=torch.float32,
        device=torch.device("cpu"),
    )

    state, uncertain = _advance_public_tracker(
        tracker,
        state,
        card_id=7,
        event_confidence=0.4,
    )
    assert not uncertain
    assert state[0, StructuredPublicStateTracker.REVEALED_COUNT_INDEX] == 0
    assert state[
        0, StructuredPublicStateTracker.UNCERTAIN_EVENT_MASS_INDEX
    ] == pytest.approx(0.6)
    assert state[
        0, StructuredPublicStateTracker.RESOURCE_CONFIDENCE_INDEX
    ] == pytest.approx(0.4)

    state, confirmed = _advance_public_tracker(
        tracker,
        state,
        card_id=7,
        event_confidence=1.0,
    )
    assert confirmed
    state, _ = _advance_public_tracker(tracker, state)
    state, repeated = _advance_public_tracker(
        tracker,
        state,
        card_id=7,
        event_confidence=1.0,
    )
    assert repeated
    assert state[0, StructuredPublicStateTracker.MISSED_PLAY_LOWER_BOUND_INDEX] == 4
    assert state[0, StructuredPublicStateTracker.RESOURCE_CONFIDENCE_INDEX] == 0


def test_deterministic_resource_cell_starts_at_six_spends_and_caps() -> None:
    cell = StructuredBeliefCell(32, 32, deterministic_resource=True)
    state = cell.initial_state(
        1,
        dtype=torch.float32,
        device=torch.device("cpu"),
    )
    assert state[0, StructuredBeliefCell.OPPONENT_ELIXIR_INDEX] == pytest.approx(0.6)

    spent = cell(
        torch.zeros((1, 32)),
        state,
        observed_spend=torch.tensor([[0.4]]),
        deterministic_regen=torch.tensor([[0.0]]),
    )
    assert spent[0, StructuredBeliefCell.OPPONENT_ELIXIR_INDEX].item() == pytest.approx(
        0.2
    )

    spent[:, StructuredBeliefCell.OPPONENT_ELIXIR_INDEX] = 0.98
    capped = cell(
        torch.zeros((1, 32)),
        spent,
        observed_spend=torch.tensor([[0.0]]),
        deterministic_regen=torch.tensor([[0.05]]),
    )
    assert capped[0, StructuredBeliefCell.OPPONENT_ELIXIR_INDEX].item() == 1


def test_deterministic_resource_integrates_single_double_and_triple_elixir() -> None:
    builder = StructuredObservationBuilder(card_vocab=["Knight"], max_entities=8)
    model = ClasherPolicy(
        PolicyConfig(
            num_tokens=builder.spec.num_tokens,
            max_entities=builder.spec.max_entities,
            d_model=16,
            num_heads=4,
            actor_layers=1,
            critic_layers=1,
            memory_size=32,
            memory_kind="structured",
            structured_deterministic_resource_enabled=True,
        ),
        builder.card_stat_features,
    )
    previous = torch.tensor([0.0, 0.4, 0.8])
    current = previous + 1.0 / 300.0
    regen = model._structured_resource_regen(
        previous,
        current,
        torch.zeros(3, dtype=torch.bool),
    )

    torch.testing.assert_close(
        regen,
        torch.tensor([[1.0 / 2.8 / 10.0], [1.0 / 1.4 / 10.0], [1.0 / 0.93 / 10.0]]),
    )


def test_policy_resource_uses_internal_card_cost_and_deduplicates_event() -> None:
    builder = StructuredObservationBuilder(card_vocab=["Knight"], max_entities=8)
    model = ClasherPolicy(
        PolicyConfig(
            num_tokens=builder.spec.num_tokens,
            max_entities=builder.spec.max_entities,
            d_model=16,
            num_heads=4,
            actor_layers=1,
            critic_layers=1,
            memory_size=32,
            memory_kind="structured",
            structured_deterministic_resource_enabled=True,
        ),
        builder.card_stat_features,
    )
    knight = builder.token_id("Knight")
    clocks = torch.tensor([[0.0, 1.0 / 300.0, 2.0 / 300.0]])
    memory, _ = model._run_memory(
        torch.zeros((1, 3, model.config.d_model)),
        torch.full((1, 3), model.num_actions - 2, dtype=torch.long),
        torch.zeros((1, 3)),
        torch.tensor([[True, False, False]]),
        None,
        torch.tensor([[0, knight, knight]]),
        torch.tensor([[0.0, 1.0, 1.0]]),
        clocks,
        torch.ones_like(clocks),
    )

    one_second_regen = 1.0 / 2.8 / 10.0
    assert memory[
        0, 1, StructuredBeliefCell.OPPONENT_ELIXIR_INDEX
    ].item() == pytest.approx(0.6 + one_second_regen - 0.3)
    assert memory[
        0, 2, StructuredBeliefCell.OPPONENT_ELIXIR_INDEX
    ].item() == pytest.approx(0.6 + 2.0 * one_second_regen - 0.3)


def test_deterministic_public_state_resets_inside_policy_sequence() -> None:
    builder = StructuredObservationBuilder(
        card_vocab=["Knight", "Archers"],
        max_entities=8,
    )
    model = ClasherPolicy(
        PolicyConfig(
            num_tokens=builder.spec.num_tokens,
            max_entities=builder.spec.max_entities,
            d_model=16,
            num_heads=4,
            actor_layers=1,
            critic_layers=1,
            memory_size=32,
            memory_kind="structured",
            structured_deterministic_resource_enabled=True,
        ),
        builder.card_stat_features,
    )
    knight = builder.token_id("Knight")
    events = torch.tensor([[0, knight, knight]])
    confidence = torch.tensor([[0.0, 1.0, 1.0]])
    clocks = torch.tensor([[0.0, 1.0 / 300.0, 0.0]])
    starts = torch.tensor([[True, False, True]])

    _, (public_state, resource_state) = model._run_memory(
        torch.zeros((1, 3, model.config.d_model)),
        torch.full((1, 3), model.num_actions - 2, dtype=torch.long),
        torch.zeros((1, 3)),
        starts,
        None,
        events,
        confidence,
        clocks,
        torch.ones_like(clocks),
    )

    assert public_state[0, StructuredPublicStateTracker.REVEALED_COUNT_INDEX] == 0
    assert public_state[0, StructuredPublicStateTracker.PUBLIC_CLOCK_INDEX] == 0
    assert resource_state[
        0, StructuredBeliefCell.OPPONENT_ELIXIR_INDEX
    ].item() == pytest.approx(0.6)


def test_deterministic_upgrade_is_action_exact_with_closed_resource_gate() -> None:
    torch.manual_seed(719)
    builder = StructuredObservationBuilder(
        card_vocab=["Knight", "Archers"],
        max_entities=8,
    )
    parent_config = PolicyConfig(
        num_tokens=builder.spec.num_tokens,
        max_entities=builder.spec.max_entities,
        d_model=16,
        num_heads=4,
        actor_layers=1,
        critic_layers=1,
        memory_size=32,
        memory_kind="structured",
        structured_resource_policy_gate_enabled=True,
    )
    parent = ClasherPolicy(parent_config, builder.card_stat_features).eval()
    upgraded = ClasherPolicy(
        replace(
            parent_config,
            structured_deterministic_resource_enabled=True,
        ),
        builder.card_stat_features,
    ).eval()
    upgraded.load_state_dict(parent.state_dict(), strict=True)

    sequence = 5
    mask = torch.zeros((1, sequence, parent.num_actions), dtype=torch.bool)
    mask[..., -2] = True
    globals_ = torch.zeros((1, sequence, 18))
    globals_[0, :, 0] = torch.arange(sequence) / 750.0
    inputs = PolicyInputs(
        entity_ids=torch.zeros((1, sequence, 8), dtype=torch.long),
        entity_features=torch.zeros((1, sequence, 8, 32)),
        entity_mask=torch.zeros((1, sequence, 8), dtype=torch.bool),
        hand_ids=torch.zeros((1, sequence, 5), dtype=torch.long),
        global_features=globals_,
        action_mask=mask,
        previous_actions=torch.full(
            (1, sequence), parent.num_actions - 2, dtype=torch.long
        ),
        previous_rewards=torch.zeros((1, sequence)),
        episode_starts=torch.tensor([[True, False, False, False, False]]),
        opponent_play_event_ids=torch.tensor(
            [[0, builder.token_id("Knight"), builder.token_id("Knight"), 0, 0]]
        ),
        opponent_play_event_confidence=torch.tensor([[0.0, 1.0, 1.0, 0.0, 0.0]]),
    ).with_exact_actor_confidence()

    with torch.no_grad():
        parent_output = parent(inputs)
        upgraded_output = upgraded(inputs)

    torch.testing.assert_close(
        upgraded_output.joint_logits,
        parent_output.joint_logits,
        rtol=0,
        atol=0,
    )
    assert not torch.equal(
        upgraded_output.opponent_elixir,
        parent_output.opponent_elixir,
    )
