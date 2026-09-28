import copy

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building, Troop
from clasher.mechanics.shared.shield import Shield
from clasher.spells import SPELL_REGISTRY


def spawn(battle, name, owner=0):
    before = set(battle.entities)
    battle._spawn_troop(Position(8, 10), owner, battle.card_loader.get_card(name))
    return [entity for key, entity in battle.entities.items() if key not in before]


def clones(battle):
    return [e for e in battle.entities.values() if getattr(e, "is_clone", False)]


@pytest.mark.parametrize("name", ["Knight", "Giant", "Balloon", "Skeletons"])
def test_clones_are_fragile_and_bound_to_the_battle(name):
    battle = BattleState()
    originals = spawn(battle, name)
    assert SPELL_REGISTRY["Clone"].cast(battle, 0, Position(8, 10))
    copied = clones(battle)
    assert len(copied) == len(originals)
    for source, clone in zip(originals, copied, strict=True):
        assert clone.hitpoints == clone.max_hitpoints == 1
        assert clone.damage == source.damage
        assert clone.battle_state is battle
        clone.take_damage(1)
        assert not clone.is_alive
        assert source.is_alive


def test_clones_cannot_be_cloned_again():
    battle = BattleState()
    spawn(battle, "Knight")
    for _ in range(2):
        SPELL_REGISTRY["Clone"].cast(battle, 0, Position(8, 10))
    assert len(clones(battle)) == 2


def test_clone_excludes_enemy_units_and_buildings():
    battle = BattleState()
    spawn(battle, "Knight", owner=1)
    battle._spawn_entity(Building, Position(8, 10), 0, battle.card_loader.get_card("Cannon"))
    assert not SPELL_REGISTRY["Clone"].cast(battle, 0, Position(8, 10))
    assert not clones(battle)


@pytest.mark.parametrize("broken", [False, True])
def test_clone_shield_has_one_hit_without_restoring_a_broken_shield(broken):
    battle = BattleState()
    source = spawn(battle, "DarkPrince")[0]
    original_shield = next(m for m in source.mechanics if isinstance(m, Shield))
    if broken:
        source.take_damage(original_shield.current_shield)
    SPELL_REGISTRY["Clone"].cast(battle, 0, Position(8, 10))
    clone = clones(battle)[0]
    shield = next(m for m in clone.mechanics if isinstance(m, Shield))
    assert shield is not original_shield
    assert shield.current_shield == (0 if broken else 1)
    clone.take_damage(10000)
    assert clone.is_alive is not broken
    if not broken:
        assert clone.hitpoints == 1
        clone.take_damage(1)
        assert not clone.is_alive


def test_cloned_golem_retains_death_spawn_with_fragile_children():
    battle = BattleState()
    spawn(battle, "Golem")
    SPELL_REGISTRY["Clone"].cast(battle, 0, Position(8, 10))
    clone = clones(battle)[0]
    before = set(battle.entities)
    clone.take_damage(1)
    children = [e for i, e in battle.entities.items() if i not in before and isinstance(e, Troop)]
    assert len(children) == 2
    assert all(e.is_clone and e.hitpoints == e.max_hitpoints == 1 for e in children)


def test_cloned_champion_cannot_own_an_activated_ability():
    battle = BattleState()
    spawn(battle, "ArcherQueen")
    SPELL_REGISTRY["Clone"].cast(battle, 0, Position(8, 10))
    assert battle._champion_ability_pair(clones(battle)[0]) is None


def test_cloned_balloon_keeps_its_delayed_death_bomb():
    battle = BattleState()
    spawn(battle, "Balloon")
    SPELL_REGISTRY["Clone"].cast(battle, 0, Position(8, 10))
    clone = clones(battle)[0]
    before = set(battle.entities)
    clone.take_damage(1)
    bombs = [e for i, e in battle.entities.items() if i not in before]
    assert len(bombs) == 1
    assert bombs[0].is_clone
    assert bombs[0].explosion_damage > 0


def test_clone_does_not_repeat_electro_wizard_deploy_damage():
    battle = BattleState()
    wizard = spawn(battle, "ElectroWizard")[0]
    victim = spawn(battle, "Giant", owner=1)[0]
    hp_before = victim.hitpoints
    SPELL_REGISTRY["Clone"].cast(battle, 0, Position(8, 10))
    clone = clones(battle)[0]
    clone.on_spawn()
    assert victim.hitpoints == hp_before
    assert wizard.mechanics and clone.mechanics


def test_clone_state_and_death_children_survive_a_scalar_fork():
    battle = BattleState()
    spawn(battle, "Golem")
    SPELL_REGISTRY["Clone"].cast(battle, 0, Position(8, 10))
    fork = copy.deepcopy(battle)
    clone = clones(fork)[0]
    assert clone.battle_state is fork
    clone.take_damage(1)
    assert len([e for e in clones(fork) if e.is_alive]) == 2
    assert len([e for e in clones(battle) if e.is_alive]) == 1


def test_cloned_spawner_produces_fragile_marked_children():
    battle = BattleState()
    spawn(battle, "Witch")
    SPELL_REGISTRY["Clone"].cast(battle, 0, Position(8, 10))
    clone = clones(battle)[0]
    spawner = next(m for m in clone.mechanics if type(m).__name__ == "PeriodicSpawner")
    before = set(battle.entities)
    spawner._spawn_units(clone, count=1, start_index=0, wave_size=1)
    children = [e for i, e in battle.entities.items() if i not in before]
    assert len(children) == 1
    assert children[0].is_clone
    assert children[0].hitpoints == children[0].max_hitpoints == 1
