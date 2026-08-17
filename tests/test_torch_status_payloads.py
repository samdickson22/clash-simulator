from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.card_aliases import resolve_card_name
from clasher.data import CardDataLoader
from clasher.entities import Building, Troop
from clasher.kinematics import tiles_to_logic_units
from clasher.torch_sim.catalog import CardKindOpcode, TensorCardCatalog
from clasher.torch_sim.status import TensorStatusState, tick_building_lifetime
from clasher.torch_sim.status_payloads import (
    StatusEffectOpcode,
    StatusTriggerOpcode,
    TensorStatusPayloadCatalog,
    apply_status_payloads,
)


def _enabled_names(loader: CardDataLoader) -> set[str]:
    definitions = loader.load_card_definitions()
    decks = json.loads(Path("decks.json").read_text())["decks"]
    return {
        resolve_card_name(card, definitions) for deck in decks for card in deck["cards"]
    }


def _spawn_plain_target(battle: BattleState) -> Troop:
    definitions = battle.card_loader.load_card_definitions()
    name = next(
        name
        for name, definition in definitions.items()
        if definition.kind == "troop" and not definition.mechanics
    )
    stats = battle.card_loader.get_card(name)
    assert stats is not None
    return battle._spawn_entity(Troop, Position(9.0, 12.0), 1, stats)


def _serialized_aura_loader(tmp_path: Path) -> CardDataLoader:
    data_file = tmp_path / "serialized_aura_gamedata.json"
    data_file.write_text(
        json.dumps(
            {
                "items": {
                    "spells": [
                        {
                            "id": 9_990_001,
                            "name": "SerializedAuraFixture",
                            "rarity": "Common",
                            "manaCost": 1,
                            "tidType": "TID_CARD_TYPE_CHARACTER",
                            "summonCharacterData": {
                                "name": "SerializedAuraFixtureCharacter",
                                "hitpoints": 100,
                                "damage": 0,
                                "range": 0,
                                "hitSpeed": 1000,
                                "sightRange": 5000,
                                "collisionRadius": 500,
                                "speed": 60,
                                "deployTime": 0,
                                "slowData": {
                                    "radius": 2500,
                                    "multiplier": 0.6,
                                },
                            },
                        }
                    ]
                }
            }
        )
    )
    return CardDataLoader(data_file)


def test_status_payload_catalog_resolves_nested_runtime_attach_data() -> None:
    loader = CardDataLoader()
    definitions = loader.load_card_definitions()
    catalog = TensorStatusPayloadCatalog.compile(loader, definitions)

    expected_count = 0
    for name, definition in definitions.items():
        status_mechanics = [
            mechanic
            for mechanic in definition.mechanics
            if type(mechanic).__name__
            in {"SerializedOnHitBuff", "Stun", "FreezeDebuff"}
        ]
        card_id = catalog.name_to_id[name]
        assert catalog.count[card_id].item() == len(status_mechanics)
        expected_count += len(status_mechanics)
        stats = loader.get_card(name)
        assert stats is not None
        for slot, mechanic in enumerate(status_mechanics):
            mechanic_name = type(mechanic).__name__
            if mechanic_name == "SerializedOnHitBuff":
                mechanic.on_attach(SimpleNamespace(card_stats=stats))
                assert catalog.trigger[card_id, slot].item() == int(
                    StatusTriggerOpcode.ATTACK_HIT
                )
                expected_effect = (
                    StatusEffectOpcode.STUN
                    if max(
                        mechanic.movement_multiplier,
                        mechanic.attack_multiplier,
                        mechanic.spawn_multiplier,
                    )
                    <= 0.0
                    else StatusEffectOpcode.SLOW
                )
                assert catalog.effect[card_id, slot].item() == int(expected_effect)
                assert catalog.duration_ms[card_id, slot].item() == mechanic.duration_ms
                assert (
                    catalog.movement_multiplier[card_id, slot].item()
                    == mechanic.movement_multiplier
                )
                assert (
                    catalog.attack_multiplier[card_id, slot].item()
                    == mechanic.attack_multiplier
                )
                assert (
                    catalog.spawn_multiplier[card_id, slot].item()
                    == mechanic.spawn_multiplier
                )
            elif mechanic_name == "Stun":
                assert catalog.effect[card_id, slot].item() == int(
                    StatusEffectOpcode.STUN
                )
                assert (
                    catalog.duration_ms[card_id, slot].item()
                    == mechanic.stun_duration_ms
                )
                assert catalog.chance[card_id, slot].item() == mechanic.stun_chance
            else:
                assert catalog.trigger[card_id, slot].item() == int(
                    StatusTriggerOpcode.AURA_TICK
                    if mechanic.aura_effect
                    else StatusTriggerOpcode.PADDING
                )
                assert catalog.duration_from_tick[card_id, slot]
                assert catalog.radius_units[
                    card_id, slot
                ].item() == tiles_to_logic_units(mechanic.radius_tiles)

    assert expected_count > 0


def test_every_serialized_on_hit_buff_dispatch_matches_python_mechanic() -> None:
    loader = CardDataLoader()
    definitions = loader.load_card_definitions()
    names = {
        name
        for name, definition in definitions.items()
        if any(
            type(mechanic).__name__ == "SerializedOnHitBuff"
            for mechanic in definition.mechanics
        )
    }
    catalog = TensorStatusPayloadCatalog.compile(loader, names)

    for name in sorted(names):
        battle = BattleState()
        target = _spawn_plain_target(battle)
        stats = loader.get_card(name)
        assert stats is not None
        source = SimpleNamespace(card_stats=stats, battle_state=battle)
        mechanics = [
            mechanic
            for mechanic in definitions[name].mechanics
            if type(mechanic).__name__ == "SerializedOnHitBuff"
        ]
        for mechanic in mechanics:
            mechanic.on_attach(source)
            mechanic.on_attack_hit(source, target)

        tensor = TensorStatusState.empty(1, 1)
        apply_status_payloads(
            tensor,
            catalog,
            torch.tensor([[catalog.name_to_id[name]]]),
            trigger=StatusTriggerOpcode.ATTACK_HIT,
        )

        assert tensor.stun_timer.item() == target.stun_timer
        assert tensor.slow_timer.item() == target.slow_timer
        assert tensor.slow_multiplier.item() == target.slow_multiplier
        assert (
            tensor.attack_speed_debuff_multiplier.item()
            == target.attack_speed_debuff_multiplier
        )
        assert (
            tensor.spawn_speed_debuff_multiplier.item()
            == target.spawn_speed_debuff_multiplier
        )
        assert sorted(
            zip(
                tensor.slow_remaining[0, 0][tensor.slow_active[0, 0]].tolist(),
                tensor.slow_movement[0, 0][tensor.slow_active[0, 0]].tolist(),
                tensor.slow_attack[0, 0][tensor.slow_active[0, 0]].tolist(),
                tensor.slow_spawn[0, 0][tensor.slow_active[0, 0]].tolist(),
            )
        ) == sorted(target._slow_effects)


def test_serialized_freeze_debuff_aura_tick_matches_python_mechanic(
    tmp_path: Path,
) -> None:
    loader = _serialized_aura_loader(tmp_path)
    definitions = loader.load_card_definitions()
    name = next(iter(definitions))
    definition = definitions[name]
    mechanic = next(
        mechanic
        for mechanic in definition.mechanics
        if type(mechanic).__name__ == "FreezeDebuff"
    )
    catalog = TensorStatusPayloadCatalog.compile(loader, definitions)
    card_id = catalog.name_to_id[name]
    assert catalog.trigger[card_id, 0].item() == int(StatusTriggerOpcode.AURA_TICK)
    assert catalog.effect[card_id, 0].item() == int(StatusEffectOpcode.SLOW)
    assert catalog.radius_units[card_id, 0].item() == 2500

    battle = BattleState()
    inside = _spawn_plain_target(battle)
    outside = _spawn_plain_target(battle)
    source_position = Position(9.0, 12.0)
    inside.position = Position(source_position.x, source_position.y)
    outside.position = Position(source_position.x + 3.0, source_position.y)
    source = SimpleNamespace(
        battle_state=battle,
        player_id=0,
        position=source_position,
    )
    mechanic.on_tick(source, 50)

    radius_units = catalog.radius_units[card_id, 0]
    target_x_units = torch.tensor(
        [
            [
                tiles_to_logic_units(inside.position.x - source_position.x),
                tiles_to_logic_units(outside.position.x - source_position.x),
            ]
        ],
        dtype=torch.int32,
    )
    eligible = target_x_units.abs() <= radius_units
    tensor = TensorStatusState.empty(1, 2)
    apply_status_payloads(
        tensor,
        catalog,
        torch.full((1, 2), card_id, dtype=torch.int64),
        trigger=StatusTriggerOpcode.AURA_TICK,
        eligible=eligible,
        tick_duration_seconds=0.05,
    )

    assert tensor.slow_timer.tolist() == [[inside.slow_timer, outside.slow_timer]]
    assert tensor.slow_multiplier.tolist() == [
        [inside.slow_multiplier, outside.slow_multiplier]
    ]
    assert inside.slow_timer == 0.05
    assert outside.slow_timer == 0.0

    inside.update_status_effects(0.05)
    outside.update_status_effects(0.05)
    tensor.tick(0.05)
    assert tensor.slow_timer.tolist() == [[inside.slow_timer, outside.slow_timer]]
    assert tensor.slow_multiplier.tolist() == [
        [inside.slow_multiplier, outside.slow_multiplier]
    ]
    assert not tensor.slow_active.any()


def test_enabled_building_lifetime_kernel_uses_card_catalog_plane() -> None:
    loader = CardDataLoader()
    names = _enabled_names(loader)
    cards = TensorCardCatalog.compile(loader, names)
    building_ids = torch.where(
        (cards.kind == int(CardKindOpcode.BUILDING)) & (cards.lifetime_ms > 0)
    )[0]
    assert building_ids.numel() > 0

    battle = BattleState()
    battle.entities.clear()
    buildings = []
    for offset, card_id in enumerate(building_ids.tolist()):
        stats = loader.get_card(cards.names[card_id])
        assert stats is not None
        buildings.append(
            battle._spawn_entity(
                Building,
                Position(2.0 + offset * 2.0, 12.0),
                offset % 2,
                stats,
            )
        )

    shape = (1, len(buildings))
    result = tick_building_lifetime(
        hitpoints=torch.tensor(
            [[building.hitpoints for building in buildings]], dtype=torch.float64
        ),
        max_hitpoints=torch.tensor(
            [[building.max_hitpoints for building in buildings]], dtype=torch.float64
        ),
        lifetime_ms=cards.lifetime_ms[building_ids][None, :].to(torch.int64),
        lifetime_elapsed=torch.zeros(shape, dtype=torch.float64),
        lifetime_decay_work=torch.zeros(shape, dtype=torch.int64),
        lifetime_tick_carry_ms=torch.zeros(shape, dtype=torch.float64),
        is_alive=torch.ones(shape, dtype=torch.bool),
        dt=0.05,
    )
    for index, building in enumerate(buildings):
        building.update_hitpoint_component(0.05)
        assert result.hitpoints[0, index].item() == building.hitpoints
        assert (
            result.lifetime_decay_work[0, index].item() == building.lifetime_decay_work
        )


def test_probabilistic_status_payload_requires_explicit_oracle_rolls() -> None:
    loader = CardDataLoader()
    definitions = loader.load_card_definitions()
    names = {
        name
        for name, definition in definitions.items()
        if any(
            type(mechanic).__name__ == "Stun" and mechanic.stun_chance < 1.0
            for mechanic in definition.mechanics
        )
    }
    if not names:
        pytest.skip("serialized inventory has no probabilistic Stun payload")
    catalog = TensorStatusPayloadCatalog.compile(loader, names)
    tensor = TensorStatusState.empty(1, 1)
    with pytest.raises(ValueError, match="random_rolls is required"):
        apply_status_payloads(
            tensor,
            catalog,
            torch.tensor([[catalog.name_to_id[next(iter(names))]]]),
            trigger=StatusTriggerOpcode.ATTACK_HIT,
        )
