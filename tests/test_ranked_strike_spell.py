import copy

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.spells import SPELL_REGISTRY


def spawn(battle, hp, owner=1):
    key = battle.next_entity_id
    battle._spawn_troop(Position(8, 10), owner, battle.card_loader.get_card("Knight"))
    entity = battle.entities[key]
    entity.hitpoints = hp
    return entity


def test_lightning_strikes_three_distinct_highest_current_hp_targets():
    b = BattleState()
    targets = [spawn(b, hp) for hp in (1400, 3000, 1800, 2400)]
    ally = spawn(b, 4000, owner=0)
    SPELL_REGISTRY["Lightning"].cast(b, 0, Position(8, 10))
    effect = b.entities[b.next_entity_id - 1]
    effect.update(0.45, b)
    assert [e.hitpoints for e in targets] == [1400, 3000, 1800, 2400]
    effect.update(0.05, b)
    assert targets[1].hitpoints == 1943
    assert targets[1].stun_timer == 0.5
    copied = copy.deepcopy(b)
    for state in (b, copied):
        area = state.entities[effect.id]
        area.update(1, state)
        assert [state.entities[e.id].hitpoints for e in targets] == [
            1400,
            1943,
            743,
            1343,
        ]
        assert state.entities[ally.id].hitpoints == 4000
        area.update(1, state)
        assert state.entities[targets[1].id].hitpoints == 1943


def test_lightning_does_not_repeat_on_lone_target():
    b = BattleState()
    target = spawn(b, 4000)
    SPELL_REGISTRY["Lightning"].cast(b, 0, target.position)
    effect = b.entities[b.next_entity_id - 1]
    effect.update(1.5, b)
    assert target.hitpoints == 2943


def test_lightning_can_be_blocked_from_low_hp_tower_by_three_troops():
    b = BattleState()
    tower = next(
        e
        for e in b.entities.values()
        if e.player_id == 1 and e.card_stats.name == "Tower"
    )
    tower.hitpoints = 100
    targets = [spawn(b, 2000 + i) for i in range(3)]
    for e in targets:
        e.position = Position(tower.position.x, tower.position.y)
    SPELL_REGISTRY["Lightning"].cast(b, 0, tower.position)
    b.entities[b.next_entity_id - 1].update(1.5, b)
    assert tower.hitpoints == 100
    assert all(e.hitpoints < 1000 for e in targets)


def test_lightning_damage_scales_and_crown_damage_uses_current_modifier():
    import json

    from clasher.balance import apply_entry_overrides
    from clasher.dynamic_spells import create_spell_from_json
    from clasher.paths import gamedata_path

    data = json.loads(gamedata_path().read_text())
    entry = apply_entry_overrides(
        next(e for e in data["items"]["spells"] if e["name"] == "Lightning")
    )
    for level, damage, crown in ((11, 1057, 265), (12, 1160, 290)):
        b = BattleState()
        tower = next(
            e
            for e in b.entities.values()
            if e.player_id == 1 and e.card_stats.name == "Tower"
        )
        hp = tower.hitpoints
        spell = create_spell_from_json(entry, level=level)
        assert spell.damage == damage
        spell.cast(b, 0, tower.position)
        b.entities[b.next_entity_id - 1].update(1.5, b)
        assert tower.hitpoints == hp - crown
