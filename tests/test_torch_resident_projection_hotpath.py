from __future__ import annotations

import inspect
import random
from collections import deque
from dataclasses import fields

import pytest
import torch

from clasher.battle import BattleState
from clasher.rl.obs_cv import CvObservationBuilder
from clasher.rl.structured_obs import (
    EntityCapacityError,
    StructuredObservationBuilder,
)
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.catalog import TensorCardCatalog
from clasher.torch_sim.observations import (
    TensorCvObservation,
    TensorObservationProjector,
    TensorStructuredObservation,
)
from clasher.torch_sim.resident_engine import TensorResidentEngine
from clasher.torch_sim.resident_outputs import (
    ResidentOutputProjector,
    TensorResidentProjectionBundle,
)
from clasher.torch_sim.resident_selfplay import TensorResidentSelfPlay
from clasher.torch_sim.state import TensorBattleState


def _device(requested: str) -> str:
    if requested == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    return requested


def _safe_battle(seed: int) -> BattleState:
    battle = BattleState(rng=random.Random(seed))
    for player in battle.players:
        player.deck = []
        player.hand = [None, None, None, None]
        player.cycle_queue = deque()
        player.elixir = 5.0
    return battle


def _catalog(device: str) -> TensorCardCatalog:
    battle = BattleState()
    return TensorCardCatalog.compile(battle.card_loader, ["Knight"], device=device)


def _projection(
    battles: list[BattleState], device: str
) -> tuple[TensorResidentEngine, ResidentOutputProjector]:
    engine = TensorResidentEngine.from_battles(
        battles,
        device=device,
        max_entities=16,
        max_objects=16,
        catalog=_catalog(device),
    )
    projector = ResidentOutputProjector.from_engine(
        engine,
        battles,
        structured_builder=StructuredObservationBuilder(card_vocab=[], max_entities=16),
        cv_builder=CvObservationBuilder(card_vocab=[]),
    )
    return engine, projector


def _assert_dataclass_tensors_equal(actual: object, expected: object) -> None:
    assert type(actual) is type(expected)
    for descriptor in fields(actual):  # type: ignore[arg-type]
        assert torch.equal(
            getattr(actual, descriptor.name), getattr(expected, descriptor.name)
        ), descriptor.name


def test_live_entity_capacity_is_rejected_during_projector_construction() -> None:
    battle = BattleState()
    state = TensorBattleState.from_battles([battle], max_entities=16)

    with pytest.raises(
        EntityCapacityError,
        match=r"alive entity count 6 exceeds configured max_entities=5",
    ):
        TensorObservationProjector(
            state,
            [battle],
            structured_builder=StructuredObservationBuilder(
                card_vocab=[], max_entities=5
            ),
            cv_builder=CvObservationBuilder(card_vocab=[]),
        )


@pytest.mark.parametrize("requested_device", ["cpu", "cuda"])
def test_project_all_is_bit_exact_and_refreshes_structured_state_once(
    requested_device: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    device = _device(requested_device)
    _, projector = _projection([_safe_battle(90_001), _safe_battle(90_002)], device)
    expected_public = projector.project_public_structured()
    expected_critic = projector.project_privileged_critic()
    expected_cv = projector.project_cv()

    calls = {"refresh": 0, "structured": 0, "cv": 0}
    original_refresh = projector._refresh_from_engine
    original_structured = projector.observations.project_structured
    original_cv = projector.observations.project_cv

    def counted_refresh() -> None:
        calls["refresh"] += 1
        original_refresh()

    def counted_structured() -> TensorStructuredObservation:
        calls["structured"] += 1
        return original_structured()

    def counted_cv() -> TensorCvObservation:
        calls["cv"] += 1
        return original_cv()

    monkeypatch.setattr(projector, "_refresh_from_engine", counted_refresh)
    monkeypatch.setattr(
        projector.observations, "project_structured", counted_structured
    )
    monkeypatch.setattr(projector.observations, "project_cv", counted_cv)

    actual = projector.project_all(include_privileged_critic=True)

    assert calls == {"refresh": 1, "structured": 1, "cv": 1}
    assert actual.privileged_critic is not None
    _assert_dataclass_tensors_equal(actual.public_structured, expected_public)
    _assert_dataclass_tensors_equal(actual.privileged_critic, expected_critic)
    _assert_dataclass_tensors_equal(actual.cv, expected_cv)
    assert not hasattr(actual.public_structured, "card_ids")


@pytest.mark.parametrize("requested_device", ["cpu", "cuda"])
def test_projection_constants_are_retained_and_forked_batch_buffers_are_exact(
    requested_device: str,
) -> None:
    device = _device(requested_device)
    _, projector = _projection([_safe_battle(91_001), _safe_battle(91_002)], device)
    observations = projector.observations
    pointers = {
        name: getattr(observations, name).data_ptr()
        for name in (
            "_entity_perspectives",
            "_player_indices",
            "_enemy_player_indices",
            "_entity_slot_order",
            "_cv_ones",
        )
    }
    event_pointers = (
        projector._event_slots.data_ptr(),
        projector._event_perspectives.data_ptr(),
    )

    first = projector.project_all(include_privileged_critic=True)
    second = projector.project_all(include_privileged_critic=True)
    for name, pointer in pointers.items():
        assert getattr(observations, name).data_ptr() == pointer
    assert event_pointers == (
        projector._event_slots.data_ptr(),
        projector._event_perspectives.data_ptr(),
    )
    _assert_dataclass_tensors_equal(first.public_structured, second.public_structured)
    _assert_dataclass_tensors_equal(first.cv, second.cv)

    forked = projector.fork([1, 0, 1])
    forked_all = forked.project_all(include_privileged_critic=True)
    assert forked.observations._entity_slot_order.shape[0] == 3
    assert forked.observations._cv_ones.shape[0] == 3
    assert torch.equal(
        forked_all.public_structured.entity_ids[0],
        first.public_structured.entity_ids[1],
    )
    assert torch.equal(
        forked_all.public_structured.entity_ids[2],
        first.public_structured.entity_ids[1],
    )


def test_projection_hot_methods_do_not_rebuild_indices_or_sync_capacity() -> None:
    pack_source = inspect.getsource(TensorObservationProjector._pack_entities)
    assert ".item(" not in pack_source
    assert "counts.max" not in pack_source
    for method in (
        TensorObservationProjector._perspective_entity_features,
        TensorObservationProjector._structured_globals,
        TensorObservationProjector._cv_hud,
        TensorObservationProjector.project_cv,
        ResidentOutputProjector.project_public_events,
    ):
        assert "torch.arange" not in inspect.getsource(method), method.__name__
    capture_source = inspect.getsource(ResidentOutputProjector.capture_tick_events)
    assert "torch.arange" not in capture_source
    assert ".item(" not in capture_source


@pytest.mark.parametrize("requested_device", ["cpu", "cuda"])
def test_selfplay_observe_and_step_use_one_fused_projection(
    requested_device: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    device = _device(requested_device)
    battle = _safe_battle(92_001)
    bridge = TensorResidentSelfPlay.from_battles(
        [battle],
        device=device,
        decision_interval_ticks=1,
        max_ticks=1,
        max_entities=16,
        max_objects=16,
        catalog=_catalog(device),
        structured_builder=StructuredObservationBuilder(card_vocab=[], max_entities=16),
        cv_builder=CvObservationBuilder(card_vocab=[]),
        include_privileged_critic=True,
    )
    calls = 0
    original = bridge.outputs.project_all

    def counted_project_all(
        *, include_privileged_critic: bool = False
    ) -> TensorResidentProjectionBundle:
        nonlocal calls
        calls += 1
        return original(include_privileged_critic=include_privileged_critic)

    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("self-play used a duplicate legacy projection")

    monkeypatch.setattr(bridge.outputs, "project_all", counted_project_all)
    monkeypatch.setattr(bridge.outputs, "project_public", forbidden)
    monkeypatch.setattr(bridge.outputs, "project_public_structured", forbidden)
    monkeypatch.setattr(bridge.outputs, "project_privileged_critic", forbidden)
    monkeypatch.setattr(bridge.outputs, "project_cv", forbidden)

    public, critic, _ = bridge.observe()
    result = bridge.step(
        torch.full((1, 2), NO_OP_ACTION, dtype=torch.int64, device=device)
    )

    assert calls == 2
    assert critic is not None and result.privileged_critic is not None
    assert public.structured.entity_ids.device.type == device
    assert result.public.cv.board.device.type == device
    assert not hasattr(result.public.structured, "card_ids")
