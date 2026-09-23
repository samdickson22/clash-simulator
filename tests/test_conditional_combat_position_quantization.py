from __future__ import annotations

import random

import pytest

from clasher import battle as battle_module
from clasher.battle import BattleState
from clasher.entities import Building, Entity


def _step_with_combat_delta(
    monkeypatch: pytest.MonkeyPatch,
    *,
    conditional: bool,
    delta: float,
) -> tuple[tuple[tuple[int, float, float], ...], int]:
    battle = BattleState(rng=random.Random(2301), fast_path=True)
    quantize_calls = 0
    original_quantize = Entity.quantize_logic_position

    def update_combat_component(
        entity: Building,
        _dt: float,
        _battle: BattleState,
    ) -> None:
        entity.position.x += delta

    def count_quantize(entity: Entity) -> None:
        nonlocal quantize_calls
        quantize_calls += 1
        original_quantize(entity)

    monkeypatch.setattr(
        battle_module,
        "_USE_CONDITIONAL_COMBAT_POSITION_QUANTIZATION",
        conditional,
    )
    monkeypatch.setattr(Building, "update_combat_component", update_combat_component)
    monkeypatch.setattr(Entity, "quantize_logic_position", count_quantize)
    battle._step_logic_tick()
    positions = tuple(
        (entity.id, entity.position.x, entity.position.y)
        for entity in battle.entities.values()
    )
    return positions, quantize_calls


@pytest.mark.parametrize("delta", [0.0, 0.0006])
def test_combat_position_quantization_skips_only_unchanged_entities(
    monkeypatch: pytest.MonkeyPatch,
    delta: float,
) -> None:
    with monkeypatch.context() as reference_patch:
        reference_positions, reference_calls = _step_with_combat_delta(
            reference_patch,
            conditional=False,
            delta=delta,
        )
    with monkeypatch.context() as candidate_patch:
        candidate_positions, candidate_calls = _step_with_combat_delta(
            candidate_patch,
            conditional=True,
            delta=delta,
        )

    assert candidate_positions == reference_positions
    if delta == 0.0:
        assert candidate_calls < reference_calls
    else:
        assert candidate_calls == reference_calls
