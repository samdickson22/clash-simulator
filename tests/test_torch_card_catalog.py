import json
from pathlib import Path

import pytest

from clasher.card_aliases import resolve_card_name
from clasher.data import CardDataLoader
from clasher.kinematics import tiles_to_logic_units
from clasher.torch_sim.catalog import (
    EFFECT_OPCODE,
    MECHANIC_OPCODE,
    CardKindOpcode,
    TensorCardCatalog,
)


def _enabled_names(loader: CardDataLoader) -> set[str]:
    definitions = loader.load_card_definitions()
    decks = json.loads(Path("decks.json").read_text())["decks"]
    return {
        resolve_card_name(card, definitions) for deck in decks for card in deck["cards"]
    }


def test_catalog_compiles_every_enabled_card_from_serialized_data() -> None:
    loader = CardDataLoader()
    names = _enabled_names(loader)
    catalog = TensorCardCatalog.compile(loader, names)

    assert len(names) == 66
    assert catalog.card_count == 66
    assert catalog.names[0] == ""
    assert set(catalog.names[1:]) == names

    kind_opcode = {
        "troop": CardKindOpcode.TROOP,
        "building": CardKindOpcode.BUILDING,
        "spell": CardKindOpcode.SPELL,
        "champion": CardKindOpcode.CHAMPION,
    }
    definitions = loader.load_card_definitions()
    for name in names:
        card_id = catalog.name_to_id[name]
        definition = definitions[name]
        stats = loader.get_card(name)
        assert stats is not None
        assert int(catalog.kind[card_id]) == int(kind_opcode[definition.kind])
        assert int(catalog.elixir[card_id]) == definition.elixir
        assert int(catalog.range_units[card_id]) == tiles_to_logic_units(
            stats.range or 0.0
        )
        assert int(catalog.sight_range_units[card_id]) == tiles_to_logic_units(
            stats.sight_range or 0.0
        )
        assert int(catalog.collision_radius_units[card_id]) == tiles_to_logic_units(
            stats.collision_radius or 0.0
        )
        assert int(catalog.mechanic_count[card_id]) == len(definition.mechanics)
        assert int(catalog.effect_count[card_id]) == len(definition.effects)
        assert catalog.mechanic_opcode[
            card_id, : len(definition.mechanics)
        ].tolist() == [
            MECHANIC_OPCODE[type(mechanic).__name__]
            for mechanic in definition.mechanics
        ]
        assert catalog.effect_opcode[card_id, : len(definition.effects)].tolist() == [
            EFFECT_OPCODE[type(effect).__name__] for effect in definition.effects
        ]


def test_catalog_opcode_registry_covers_complete_factory_inventory() -> None:
    loader = CardDataLoader()
    definitions = loader.load_card_definitions()

    catalog = TensorCardCatalog.compile(loader, definitions)

    assert catalog.card_count > 66
    assert not catalog.mechanic_opcode.lt(0).any()
    assert not catalog.effect_opcode.lt(0).any()


def test_catalog_compiles_shared_mechanic_parameters_without_card_switches() -> None:
    loader = CardDataLoader()
    catalog = TensorCardCatalog.compile(loader, _enabled_names(loader))

    shield_parameter = catalog.mechanic_parameter_names.index("shield_hp")
    shield_opcode = MECHANIC_OPCODE["Shield"]
    shield_rows = (catalog.mechanic_opcode == shield_opcode).nonzero()

    assert shield_rows.shape[0] == 2
    for card_id, mechanic_slot in shield_rows.tolist():
        assert (
            catalog.mechanic_parameters[card_id, mechanic_slot, shield_parameter].item()
            > 0
        )


def test_catalog_rejects_missing_card_definition() -> None:
    with pytest.raises(ValueError, match="missing card definitions"):
        TensorCardCatalog.compile(CardDataLoader(), ["DefinitelyMissingCard"])
