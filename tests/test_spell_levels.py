"""Level-sensitive spell construction and delayed spawn regressions."""

import json

import pytest

from clasher.balance import apply_entry_overrides
from clasher.dynamic_spells import create_spell_from_json
from clasher.gamedata_normalization import build_object_registry
from clasher.paths import gamedata_path


@pytest.fixture(scope="module")
def entries():
    data = json.loads(gamedata_path().read_text())
    registry = build_object_registry(data)
    return {
        e["name"]: apply_entry_overrides(e, registry)
        for e in data["items"]["spells"]
        if e.get("tidType") == "TID_CARD_TYPE_SPELL"
    }


@pytest.mark.parametrize(
    "name,damage,crown",
    [
        ("Fireball", 755, 189),
        ("Zap", 210, 53),
        ("Arrows", 134, 27),
        ("Log", 295, 39),
    ],
)
def test_level_12_damage_uses_raw_base_before_crown_rounding(
    entries, name, damage, crown
):
    spell = create_spell_from_json(entries[name], level=12)
    assert spell.damage == damage
    assert spell.crown_tower_damage == crown


def test_different_levels_do_not_mutate_shared_entry(entries):
    entry = entries["Fireball"]
    before = json.dumps(entry, sort_keys=True)
    high = create_spell_from_json(entry, level=12)
    normal = create_spell_from_json(entry)
    assert (normal.damage, high.damage) == (688, 755)
    assert json.dumps(entry, sort_keys=True) == before


@pytest.mark.parametrize("name", ["Earthquake", "Poison", "Tornado"])
def test_unreconciled_tournament_overrides_are_explicit(entries, name):
    with pytest.raises(ValueError, match="level.*override"):
        create_spell_from_json(entries[name], level=12)


@pytest.mark.parametrize("level", [0, 21, 1.5, True])
def test_invalid_levels_are_rejected_even_for_zero_damage(entries, level):
    with pytest.raises((TypeError, ValueError)):
        create_spell_from_json(entries["Graveyard"], level=level)


@pytest.mark.parametrize(
    "name", ["GoblinBarrel", "BarbLog", "RoyalDelivery", "Graveyard"]
)
def test_delayed_spell_children_keep_level_across_battle_copy(entries, name):
    import copy

    from clasher.arena import Position
    from clasher.battle import BattleState
    from clasher.entities import Troop

    battle = BattleState()
    spell = create_spell_from_json(entries[name], level=12)
    assert spell.cast(battle, 0, Position(8, 10))
    copied = copy.deepcopy(battle)
    for state in (battle, copied):
        for _ in range(140):
            state.step()
        children = [e for e in state.entities.values() if isinstance(e, Troop)]
        assert children
        assert all(e.card_stats.level == 12 for e in children)
        assert all(
            e.max_hitpoints == e.card_stats.get_scaled_stat(e.card_stats.hitpoints, 12)
            for e in children
        )
        assert all(
            e.damage == e.card_stats.get_scaled_stat(e.card_stats.damage, 12)
            for e in children
        )
    assert [(e.id, e.hitpoints) for e in battle.entities.values()] == [
        (e.id, e.hitpoints) for e in copied.entities.values()
    ]
