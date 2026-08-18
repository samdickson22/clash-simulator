"""Long exact traces that document the resident movement frontier.

These are not complete-episode parity claims. Each case proves a reviewed exact
prefix through ordinary 50 ms deployment ticks, then either names the first
currently divergent field or records a finite exact horizon. When a kernel
closes one frontier, its boundary must move later or become a longer horizon.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.resident_engine import TensorResidentEngine


@dataclass(frozen=True)
class ExpectedTrace:
    ticks: int
    boundary_field: str | None
    boundary_kind: str = "divergent"


EXPECTED_TRACES = {
    # The retained StopMovementAfterMS/WaitMS clock now remains exact through
    # fifteen seconds of mirrored movement and melee combat.
    "Giant": ExpectedTrace(300, None),
    # Runtime entry now matches the state-six boundary exactly. Resident
    # refresh still needs to retain the active jump support plane next tick.
    "HogRider": ExpectedTrace(28, "resident_phase", "unsupported"),
    "RoyalHogs": ExpectedTrace(28, "resident_phase", "unsupported"),
    # Prince accumulates native charge work from its first movement frame.
    "Prince": ExpectedTrace(21, "native_charge_progress"),
    # Resident projectile integration independently closed the old tick-56
    # direct-hit boundary; the mirrored trace is exact through fifteen seconds.
    "Bats": ExpectedTrace(300, None),
}


BUILDING_TARGETERS = frozenset({"Giant", "HogRider", "RoyalHogs"})


def _source_and_target(
    card_name: str,
    owner: int,
) -> tuple[BattleState, int, int]:
    battle = BattleState(
        fast_path=False,
        rng=random.Random(960_000 + owner),
    )
    source_y, target_y = (14.25, 18.75) if owner == 0 else (17.75, 13.25)
    source_x = 3.5 if card_name == "Giant" else 9.0
    source_stats = battle.card_loader.get_card(card_name)
    assert source_stats is not None

    if card_name in BUILDING_TARGETERS:
        target_id = 4 if owner == 0 else 1
        target = battle.entities[target_id]
        target.position = Position(source_x, target_y)
        target._tower_active = False  # type: ignore[attr-defined]
        target.attack_cooldown = 0.0
        target.damage = 0.0
        target.stun_timer = 100.0
        battle._spawn_unit_at_position(
            Position(source_x, source_y),
            owner,
            source_stats,
            snap_to_valid=False,
        )
        source_id = 7
    else:
        battle.entities.clear()
        battle.next_entity_id = 1
        battle._spawn_unit_at_position(
            Position(source_x, source_y),
            owner,
            source_stats,
            snap_to_valid=False,
        )
        target_stats = battle.card_loader.get_card("Knight")
        assert target_stats is not None
        battle._spawn_unit_at_position(
            Position(source_x, target_y),
            1 - owner,
            target_stats,
            deploy_delay_override=0.0,
            snap_to_valid=False,
        )
        source_id = 1
        target_id = 2
        target = battle.entities[target_id]
        target.stun_timer = 100.0
        target.attack_cooldown = 10.0

    source = battle.entities[source_id]
    assert source.deploy_delay_remaining == 1.0
    # Every requested card reaches the resident boundary without an attached
    # factory mechanic; their uncovered behavior is serialized character data.
    assert not source.mechanics
    return battle, source_id, target_id


def _runtime_target_id(
    engine: TensorResidentEngine,
    row: int,
    source_slot: int,
) -> int | None:
    target_slot = int(engine.runtime.phases.target_slot[row, source_slot].item())
    if target_slot < 0:
        return None
    target_id = int(engine.runtime.battle.entity_id[row, target_slot].item())
    return None if target_id == 0 else target_id


def _first_relevant_difference(
    engine: TensorResidentEngine,
    oracle: BattleState,
    *,
    row: int,
    source_id: int,
    target_id: int,
) -> str | None:
    runtime_ids = engine.runtime.battle.entity_id[row].tolist()
    runtime_entity_ids = {entity_id for entity_id in runtime_ids if entity_id}
    if runtime_entity_ids != set(oracle.entities):
        return "entity_identity"
    source_slot = runtime_ids.index(source_id)
    expected = oracle.entities[source_id]
    actual_position = (
        int(engine.runtime.battle.entity_x_units[row, source_slot].item()),
        int(engine.runtime.battle.entity_y_units[row, source_slot].item()),
    )
    expected_position = (
        round(expected.position.x * 1_000),
        round(expected.position.y * 1_000),
    )
    if actual_position != expected_position:
        return "position_units"
    if engine.runtime.battle.entity_hp[row, source_slot].item() != expected.hitpoints:
        return "hitpoints"
    if _runtime_target_id(engine, row, source_slot) != expected.target_id:
        return "target_id"
    if (
        engine.combat.attack_cooldown[row, source_slot].item()
        != expected.attack_cooldown
    ):
        return "attack_cooldown"
    if (
        engine.runtime.battle.entity_deploy_delay[row, source_slot].item()
        != expected.deploy_delay_remaining
    ):
        return "deploy_delay_remaining"
    if engine.movement.movement_phase_elapsed_ms[row, source_slot].item() != getattr(
        expected, "movement_phase_elapsed_ms", 0
    ):
        return "movement_phase_elapsed_ms"
    if engine.movement.native_charge_progress[row, source_slot].item() != getattr(
        expected, "_native_charge_progress", 0
    ):
        return "native_charge_progress"
    if engine.movement.river_jump_active[row, source_slot].item() is not bool(
        getattr(expected, "_river_jump_active", False)
    ):
        return "river_jump_active"

    target_slot = runtime_ids.index(target_id)
    expected_target = oracle.entities[target_id]
    actual_target_position = (
        int(engine.runtime.battle.entity_x_units[row, target_slot].item()),
        int(engine.runtime.battle.entity_y_units[row, target_slot].item()),
    )
    expected_target_position = (
        round(expected_target.position.x * 1_000),
        round(expected_target.position.y * 1_000),
    )
    if actual_target_position != expected_target_position:
        return "target_position_units"
    if (
        engine.runtime.battle.entity_hp[row, target_slot].item()
        != expected_target.hitpoints
    ):
        return "target_hitpoints"
    if (
        engine.combat.attack_cooldown[row, target_slot].item()
        != expected_target.attack_cooldown
    ):
        return "target_attack_cooldown"
    if (
        engine.runtime.status.stun_timer[row, target_slot].item()
        != expected_target.stun_timer
    ):
        return "target_stun_timer"
    return None


@pytest.mark.parametrize("card_name", tuple(EXPECTED_TRACES))
def test_current_first_resident_movement_boundary_after_exact_deployment_prefix(
    card_name: str,
) -> None:
    cases = [_source_and_target(card_name, owner) for owner in (0, 1)]
    oracle = [battle.clone() for battle, _, _ in cases]
    engine = TensorResidentEngine.from_battles(
        [battle for battle, _, _ in cases],
        max_entities=16,
        max_objects=16,
        event_capacity=256,
    )
    expected_trace = EXPECTED_TRACES[card_name]
    observed: list[tuple[str, int, str]] = []
    no_op = torch.full((2, 2), NO_OP_ACTION, dtype=torch.int64)

    for tick in range(1, expected_trace.ticks + 1):
        for battle in oracle:
            player_order = [0, 1]
            battle.rng.shuffle(player_order)
            battle.step_logic_ticks(1)
        result = engine.step(no_op)
        for row, ((_, source_id, target_id), expected) in enumerate(
            zip(cases, oracle, strict=True)
        ):
            if not bool(result.committed[row].item()):
                observed.append(("unsupported", tick, "resident_phase"))
                continue
            difference = _first_relevant_difference(
                engine,
                expected,
                row=row,
                source_id=source_id,
                target_id=target_id,
            )
            if difference is not None:
                observed.append(("divergent", tick, difference))

        if observed:
            break

        # The prefix includes all twenty standard deployment frames; battle
        # clocks/RNG remain exact and no tiebreak boundary is accelerated.
        assert engine.runtime.battle.tick.tolist() == [tick, tick]
        assert engine.runtime.battle.time.tolist() == [battle.time for battle in oracle]
        assert [engine.runtime.battle.rng.python_state(row) for row in range(2)] == [
            battle.rng.getstate() for battle in oracle
        ]

    if expected_trace.boundary_field is None:
        assert observed == []
    else:
        assert observed == [
            (
                expected_trace.boundary_kind,
                expected_trace.ticks,
                expected_trace.boundary_field,
            ),
            (
                expected_trace.boundary_kind,
                expected_trace.ticks,
                expected_trace.boundary_field,
            ),
        ]
    assert expected_trace.ticks > 20
