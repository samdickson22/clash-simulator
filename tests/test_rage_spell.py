import copy

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import BuffAreaEffect, DeathAreaEffectContainer
from clasher.spells import SPELL_REGISTRY


def spawn(battle, owner, name="Knight"):
    first = battle.next_entity_id
    battle._spawn_troop(Position(8, 10), owner, battle.card_loader.get_card(name))
    return battle.entities[first]


def test_rage_registry_materializes_delayed_buff_and_one_shot_damage():
    battle = BattleState()
    ally = spawn(battle, 0)
    enemy = spawn(battle, 1)
    hp = enemy.hitpoints
    base_damage = ally.damage
    assert SPELL_REGISTRY["Rage"].cast(battle, 0, Position(8, 10))
    container = next(
        e for e in battle.entities.values() if isinstance(e, DeathAreaEffectContainer)
    )
    container.update(0.45, battle)
    assert enemy.hitpoints == hp
    container.update(0.05, battle)
    effect = next(e for e in battle.entities.values() if isinstance(e, BuffAreaEffect))
    effect.update(0.3, battle)
    assert enemy.hitpoints == hp - 179
    assert ally.movement_speed_buff_multiplier == 1.3
    assert ally.attack_speed_buff_multiplier == 1.3
    assert ally.spawn_speed_buff_multiplier == 1.3
    assert enemy.movement_speed_buff_multiplier == 1
    assert ally.damage == base_damage
    effect.update(0.3, battle)
    assert enemy.hitpoints == hp - 179
    ally.position = Position(1, 1)
    ally.update_buff_component(1.1)
    assert ally.movement_speed_buff_multiplier == 1
    assert ally.attack_speed_buff_multiplier == 1


def test_played_rage_kills_skeletons_after_command_delay_and_survives_copy():
    battle = BattleState()
    skeleton = spawn(battle, 1, "Skeletons")
    for entity in battle.entities.values():
        if entity.card_stats.name == "Skeletons":
            entity.position = Position(8, 23)
    battle.players[0].hand = ["Rage"]
    battle.players[0].elixir = 10
    assert battle.deploy_card(0, "Rage", Position(8, 23))
    assert battle.players[0].elixir == 8
    copied = copy.deepcopy(battle)
    for state in (battle, copied):
        for _ in range(19):
            state.step()
        assert state.entities[skeleton.id].is_alive
        for _ in range(14):
            state.step()
        assert (
            skeleton.id not in state.entities
            or not state.entities[skeleton.id].is_alive
        )


def test_rage_level_changes_damage_but_not_duration_or_haste():
    import json

    from clasher.balance import apply_entry_overrides
    from clasher.dynamic_spells import create_spell_from_json
    from clasher.paths import gamedata_path

    data = json.loads(gamedata_path().read_text())
    entry = apply_entry_overrides(
        next(e for e in data["items"]["spells"] if e["name"] == "Rage")
    )
    for level, troop_damage, crown_damage in ((11, 179, 45), (12, 196, 49)):
        battle = BattleState()
        enemy = spawn(battle, 1)
        hp = enemy.hitpoints
        spell = create_spell_from_json(entry, level=level)
        spell.cast(battle, 0, enemy.position)
        container = next(
            e
            for e in battle.entities.values()
            if isinstance(e, DeathAreaEffectContainer)
        )
        container.update(0.5, battle)
        effect = next(
            e for e in battle.entities.values() if isinstance(e, BuffAreaEffect)
        )
        effect.update(0.05, battle)
        assert enemy.hitpoints == hp - troop_damage
        assert effect.duration == 4.5
        assert effect.movement_multiplier == 1.3
        tower = next(
            e
            for e in battle.entities.values()
            if e.player_id == 1
            and e.card_stats is not None
            and e.card_stats.name == "Tower"
        )
        tower_hp = tower.hitpoints
        spell.cast(battle, 0, tower.position)
        container = battle.entities[battle.next_entity_id - 1]
        container.update(0.5, battle)
        effect = battle.entities[battle.next_entity_id - 1]
        effect.update(0.05, battle)
        assert tower.hitpoints == tower_hp - crown_damage


def test_repeated_rage_refreshes_without_multiplying_haste():
    battle = BattleState()
    ally = spawn(battle, 0)
    for _ in range(2):
        SPELL_REGISTRY["Rage"].cast(battle, 0, ally.position)
        container = battle.entities[battle.next_entity_id - 1]
        container.update(0.5, battle)
        effect = battle.entities[battle.next_entity_id - 1]
        effect.update(0.3, battle)
    assert ally.attack_speed_buff_multiplier == 1.3
    assert len(ally._haste_effects) == 1
