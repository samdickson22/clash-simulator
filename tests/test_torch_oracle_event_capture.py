from __future__ import annotations

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building, Troop
from clasher.torch_sim.oracle_event_capture import (
    OraclePayloadKind,
    PythonOracleEventCapture,
)
from clasher.torch_sim.runtime_state import RuntimeEventOpcode, TickPhase

RANGED_CARDS = (
    "BabyDragon",
    "Bomber",
    "Princess",
    "SpearGoblins",
    "Minions",
)
DELAYED_SPELLS = (
    "Arrows",
    "Fireball",
    "GiantSnowball",
    "GoblinBarrel",
    "Rocket",
    "Zap",
)
ROLLING_AND_ROYAL_SPELLS = (
    "BarbarianBarrel",
    "Log",
    "RoyalDelivery",
)


def _spawn_one(
    battle: BattleState,
    name: str,
    player: int,
    position: Position,
) -> Troop:
    stats = battle.card_loader.get_card(name)
    assert stats is not None
    entity = battle._spawn_entity(Troop, position, player, stats)
    assert isinstance(entity, Troop)
    entity.deploy_delay_remaining = 0.0
    entity.placement_pending = False
    entity._spawn_hook_pending = False
    entity._spawn_hook_fired = True
    return entity


def _empty_battle() -> BattleState:
    battle = BattleState(fast_path=False)
    battle.entities.clear()
    battle.next_entity_id = 1
    return battle


def _set_hand(battle: BattleState, card_name: str) -> None:
    player = battle.players[0]
    player.hand = [card_name, None, None, None]
    player.deck = [card_name]
    player.cycle_queue.clear()
    player.elixir = 20.0


def test_command_deployment_spawn_is_not_a_projectile_allocation() -> None:
    battle = _empty_battle()
    _set_hand(battle, "Knight")
    original_entities = battle.entities

    with PythonOracleEventCapture(battle) as capture:
        assert capture.deploy_card(0, "Knight", Position(9.0, 10.0))
        assert len(capture.events) == 1
        event = capture.events[0]
        assert event.phase == TickPhase.COMMANDS
        assert event.opcode == RuntimeEventOpcode.SPAWN
        assert event.payload_kind == OraclePayloadKind.COMMAND_DEPLOYMENT
        assert event.payload == "Knight"
        assert event.payload_scalar_kind == "str"
        assert event.source_id > 0
        assert event.target_id == 0

    assert battle.entities is original_entities
    assert len(battle.entities) == 1


@pytest.mark.parametrize("card_name", RANGED_CARDS)
def test_combat_projectile_creation_and_impact_use_actual_phase_and_source(
    card_name: str,
) -> None:
    battle = _empty_battle()
    source = _spawn_one(battle, card_name, 0, Position(9.0, 10.0))
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 11.0))
    source.target_id = target.id
    source.attack_cooldown = 0.0
    source.last_attack_time = -10.0
    target.speed = 0.0
    target.damage = 0.0
    target.attack_cooldown = 10.0

    with PythonOracleEventCapture(battle) as capture:
        for _ in range(40):
            capture.step_logic_ticks()
            if any(
                event.opcode == RuntimeEventOpcode.DAMAGE
                and event.target_id == target.id
                for event in capture.events
            ):
                break

        projectile = next(
            event
            for event in capture.events
            if event.payload_kind == OraclePayloadKind.COMBAT_PROJECTILE
        )
        damage = next(
            event
            for event in capture.events
            if event.opcode == RuntimeEventOpcode.DAMAGE
            and event.target_id == target.id
        )
        assert projectile.phase == TickPhase.COMBAT
        assert projectile.opcode == RuntimeEventOpcode.PROJECTILE
        assert projectile.source_id == source.id
        assert projectile.target_id > target.id
        assert projectile.payload == card_name
        impact = next(
            event
            for event in capture.events
            if event.payload_kind == OraclePayloadKind.PROJECTILE_IMPACT
        )
        assert impact.phase == TickPhase.OBJECTS
        assert impact.source_id == projectile.target_id
        assert damage.phase == TickPhase.OBJECTS
        assert damage.source_id == projectile.target_id
        assert damage.payload == card_name
        assert damage.amount_kind == "float"
        assert projectile.sequence < impact.sequence < damage.sequence


def test_xbow_projectile_lifetime_and_impact_follow_scalar_phase_order() -> None:
    battle = _empty_battle()
    stats = battle.card_loader.get_card("Xbow")
    assert stats is not None
    source = battle._spawn_entity(Building, Position(9.0, 10.0), 0, stats)
    assert isinstance(source, Building)
    source.deploy_delay_remaining = 0.0
    source.placement_pending = False
    source._spawn_hook_pending = False
    source._spawn_hook_fired = True
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 14.0))
    source.target_id = target.id
    source.attack_cooldown = 0.0
    source.last_attack_time = -10.0
    target.speed = 0.0
    target.damage = 0.0
    target.attack_cooldown = 10.0

    with PythonOracleEventCapture(battle) as capture:
        for _ in range(40):
            capture.step_logic_ticks()
            if any(
                event.opcode == RuntimeEventOpcode.DAMAGE
                and event.phase == TickPhase.OBJECTS
                and event.target_id == target.id
                for event in capture.events
            ):
                break

    launch = next(
        event
        for event in capture.events
        if event.payload_kind == OraclePayloadKind.COMBAT_PROJECTILE
    )
    lifetime = next(
        event
        for event in capture.events
        if event.phase == TickPhase.BUILDING_LIFETIME
        and event.opcode == RuntimeEventOpcode.DAMAGE
        and event.target_id == source.id
    )
    impact = next(
        event
        for event in capture.events
        if event.payload_kind == OraclePayloadKind.PROJECTILE_IMPACT
    )
    damage = next(
        event
        for event in capture.events
        if event.phase == TickPhase.OBJECTS
        and event.opcode == RuntimeEventOpcode.DAMAGE
        and event.target_id == target.id
    )
    assert lifetime.amount_kind == "int"
    assert launch.sequence < lifetime.sequence < impact.sequence < damage.sequence


@pytest.mark.parametrize("spell_name", DELAYED_SPELLS)
def test_delayed_spell_execution_allocation_and_effect_order_is_observed(
    spell_name: str,
) -> None:
    battle = _empty_battle()
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 14.0))
    target.speed = 0.0
    target.damage = 0.0
    target.attack_cooldown = 10.0
    target.hitpoints = 1_000 if spell_name == "Rocket" else 5_000
    target.max_hitpoints = target.hitpoints
    _set_hand(battle, spell_name)

    with PythonOracleEventCapture(battle) as capture:
        assert capture.deploy_card(0, spell_name, Position(9.0, 14.0))
        assert capture.events == []
        for _ in range(19):
            capture.step_logic_ticks()
        assert not any(
            event.payload_kind == OraclePayloadKind.SPELL_EXECUTION
            for event in capture.events
        )
        capture.step_logic_ticks()
        execution = next(
            event
            for event in capture.events
            if event.payload_kind == OraclePayloadKind.SPELL_EXECUTION
        )
        assert execution.tick == 20
        assert execution.phase == TickPhase.COMMANDS
        assert execution.opcode == RuntimeEventOpcode.COMMAND
        assert execution.payload_scalar_kind == "str"

        for _ in range(100):
            capture.step_logic_ticks()
            has_terminal_effect = (
                any(
                    event.target_id == target.id
                    and event.opcode
                    in {
                        RuntimeEventOpcode.DAMAGE,
                        RuntimeEventOpcode.STATUS,
                        RuntimeEventOpcode.DEATH,
                    }
                    for event in capture.events
                )
                if spell_name != "GoblinBarrel"
                else any(
                    event.payload_kind == OraclePayloadKind.OBJECT_CHARACTER
                    for event in capture.events
                )
            )
            if has_terminal_effect:
                break

        assert [event.sequence for event in capture.events] == list(
            range(len(capture.events))
        )
        if spell_name == "Zap":
            damage = next(
                event
                for event in capture.events
                if event.opcode == RuntimeEventOpcode.DAMAGE
            )
            status = next(
                event
                for event in capture.events
                if event.payload_kind == OraclePayloadKind.STUN
            )
            assert damage.phase == status.phase == TickPhase.COMMANDS
            assert execution.sequence < damage.sequence < status.sequence
            assert damage.source_id == status.source_id == 0
        else:
            allocation = next(
                event
                for event in capture.events
                if event.payload_kind == OraclePayloadKind.SPELL_PROJECTILE
            )
            assert allocation.phase == TickPhase.COMMANDS
            assert allocation.opcode == RuntimeEventOpcode.PROJECTILE
            assert allocation.source_id == 0
            assert execution.sequence < allocation.sequence
            impact = next(
                event
                for event in capture.events
                if event.payload_kind == OraclePayloadKind.PROJECTILE_IMPACT
            )
            impact_allocation = next(
                event
                for event in capture.events
                if event.payload_kind == OraclePayloadKind.SPELL_PROJECTILE
                and event.target_id == impact.source_id
            )
            assert impact.phase == TickPhase.OBJECTS
            assert impact_allocation.sequence < impact.sequence
            if spell_name == "GoblinBarrel":
                child = next(
                    event
                    for event in capture.events
                    if event.payload_kind == OraclePayloadKind.OBJECT_CHARACTER
                )
                assert child.phase == TickPhase.OBJECTS
                assert child.source_id == allocation.target_id
                assert impact.sequence < child.sequence
            else:
                damage = next(
                    event
                    for event in capture.events
                    if event.opcode == RuntimeEventOpcode.DAMAGE
                    and event.target_id == target.id
                )
                assert damage.phase == TickPhase.OBJECTS
                assert damage.source_id > 0
                assert impact.sequence < damage.sequence
                if spell_name == "GiantSnowball":
                    slow = next(
                        event
                        for event in capture.events
                        if event.payload_kind == OraclePayloadKind.SLOW
                    )
                    assert damage.sequence < slow.sequence
                    assert slow.phase == TickPhase.OBJECTS
                if spell_name == "Rocket":
                    death = next(
                        event
                        for event in capture.events
                        if event.opcode == RuntimeEventOpcode.DEATH
                        and event.target_id == target.id
                    )
                    assert damage.sequence < death.sequence
                    assert death.phase == TickPhase.OBJECTS


@pytest.mark.parametrize("spell_name", ROLLING_AND_ROYAL_SPELLS)
def test_rolling_and_royal_carrier_allocation_uses_exact_callsite_kind(
    spell_name: str,
) -> None:
    battle = _empty_battle()
    _set_hand(battle, spell_name)

    with PythonOracleEventCapture(battle) as capture:
        assert capture.deploy_card(0, spell_name, Position(9.0, 14.0))
        for _ in range(25):
            capture.step_logic_ticks()
            if any(
                event.payload_kind
                in {
                    OraclePayloadKind.OBJECT_CHARACTER,
                    OraclePayloadKind.SPELL_PROJECTILE,
                }
                for event in capture.events
            ):
                break

    command = next(
        event
        for event in capture.events
        if event.payload_kind == OraclePayloadKind.SPELL_EXECUTION
    )
    carrier = next(
        event
        for event in capture.events
        if event.payload_kind
        in {
            OraclePayloadKind.OBJECT_CHARACTER,
            OraclePayloadKind.SPELL_PROJECTILE,
        }
    )
    assert carrier.payload == command.payload
    assert command.phase == carrier.phase == TickPhase.COMMANDS
    assert command.sequence < carrier.sequence
    assert carrier.source_id == 0
    assert carrier.target_id > 0
    if spell_name == "RoyalDelivery":
        assert carrier.opcode == RuntimeEventOpcode.PROJECTILE
        assert carrier.payload_kind == OraclePayloadKind.SPELL_PROJECTILE
    else:
        assert carrier.opcode == RuntimeEventOpcode.SPAWN
        assert carrier.payload_kind == OraclePayloadKind.OBJECT_CHARACTER
