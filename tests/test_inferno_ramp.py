import pytest

from clasher.battle import BattleState
from clasher.arena import Position
from clasher.entities import Building, Projectile, Troop
from clasher.factory.dynamic_factory import troop_from_character_data
from clasher.spells import SPELL_REGISTRY


def _spawn_one(battle, name, player_id, position):
    stats = battle.card_loader.get_card(name)
    assert stats is not None
    before = set(battle.entities)
    battle._spawn_troop(position, player_id, stats)
    troop = next(
        entity
        for entity_id, entity in battle.entities.items()
        if entity_id not in before and isinstance(entity, Troop)
    )
    troop.deploy_delay_remaining = 0.0
    troop.placement_pending = False
    troop.placement_pending = False
    troop.on_spawn()
    return troop


def test_inferno_ramp_only_advances_while_beam_is_connected():
    battle = BattleState()
    dragon = _spawn_one(battle, "InfernoDragon", 0, Position(9.0, 10.0))
    giant = _spawn_one(battle, "Giant", 1, Position(9.0, 20.0))
    ramp = next(mechanic for mechanic in dragon.mechanics if type(mechanic).__name__ == "DamageRamp")
    base_damage = ramp._get_damage_for_time(0)
    dragon.target_id = giant.id

    ramp.on_target_observed(dragon, giant, 5000)
    assert dragon.damage == base_damage
    assert ramp._current_target_ms == 0

    giant.position = Position(9.0, 13.0)
    ramp.on_target_observed(dragon, giant, 33)
    ramp.on_target_observed(dragon, giant, 2000)
    ramp.on_attack_start(dragon, giant)
    assert dragon.damage > base_damage

    giant.position = Position(9.0, 20.0)
    ramp.on_target_observed(dragon, giant, 33)
    assert dragon.damage == base_damage
    assert ramp._current_target_ms == 0


def test_inferno_stages_scale_each_serialized_damage_stat_independently():
    battle = BattleState()
    dragon = _spawn_one(battle, "InfernoDragon", 0, Position(9.0, 10.0))
    dragon_ramp = next(
        mechanic
        for mechanic in dragon.mechanics
        if type(mechanic).__name__ == "DamageRamp"
    )
    dragon_data = dragon.card_stats._raw_entry["summonCharacterData"]
    assert dragon_data["variableDamageTime1"] == 2000
    assert dragon_data["variableDamageTime2"] == 2000
    assert dragon_ramp.stages == [(0, 35), (2000, 120), (4000, 422)]

    stats = battle.card_loader.get_card("InfernoTower")
    assert stats is not None
    tower = battle._spawn_entity(Building, Position(9.0, 14.0), 0, stats)
    tower_ramp = next(
        mechanic
        for mechanic in tower.mechanics
        if type(mechanic).__name__ == "DamageRamp"
    )
    tower_data = tower.card_stats._raw_entry["summonCharacterData"]
    assert tower_data["variableDamageTime1"] == 2000
    assert tower_data["variableDamageTime2"] == 2000
    assert tower_ramp.stages == [(0, 43), (2000, 158), (4000, 847)]

def test_fireball_knockback_breaks_inferno_dragon_ramp_even_if_target_stays_in_range():
    battle = BattleState()
    dragon = _spawn_one(battle, "InfernoDragon", 1, Position(9.0, 15.0))
    giant = _spawn_one(battle, "Giant", 0, Position(9.0, 12.0))
    ramp = next(
        mechanic
        for mechanic in dragon.mechanics
        if type(mechanic).__name__ == "DamageRamp"
    )
    dragon.target_id = giant.id
    ramp.on_target_observed(dragon, giant, 33)
    ramp.on_target_observed(dragon, giant, 4_000)
    ramp.on_attack_start(dragon, giant)
    assert dragon.damage > ramp._get_damage_for_time(0)

    impact = Position(8.0, 15.0)
    assert SPELL_REGISTRY["Fireball"].cast(battle, 0, impact)
    fireball = max(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Projectile)
    )
    fireball.position = Position(impact.x, impact.y)
    fireball.update(0.01, battle)

    assert dragon.position == Position(9.0, 15.0)
    dragon.update_movement_component(battle.dt, battle)
    assert dragon.position == Position(9.2, 15.0)
    assert dragon.can_attack_target(giant)
    assert dragon.target_id is None
    assert ramp._current_target_ms == 0
    assert dragon.damage == ramp._get_damage_for_time(0)


def test_hook_displacement_breaks_inferno_ramp_through_shared_movement_contract():
    battle = BattleState()
    dragon = _spawn_one(battle, "InfernoDragon", 1, Position(9.0, 15.0))
    giant = _spawn_one(battle, "Giant", 0, Position(9.0, 12.0))
    ramp = next(
        mechanic
        for mechanic in dragon.mechanics
        if type(mechanic).__name__ == "DamageRamp"
    )
    dragon.target_id = giant.id
    ramp.on_target_observed(dragon, giant, 33)
    ramp.on_target_observed(dragon, giant, 4_000)
    ramp.on_attack_start(dragon, giant)
    assert dragon.damage > ramp._get_damage_for_time(0)

    dragon.interrupt_by_forced_movement(
        source_kind="Fisherman",
        movement_kind="hook",
    )

    assert dragon.target_id is None
    assert ramp._current_target_ms == 0
    assert dragon.damage == ramp._get_damage_for_time(0)


def test_bandit_dash_keeps_inferno_lock_but_resets_its_damage_channel():
    battle = BattleState()
    inferno = _spawn_one(battle, "InfernoDragon", 0, Position(3.5, 12.0))
    bandit = _spawn_one(battle, "Bandit", 1, Position(3.5, 15.0))
    ramp = next(
        mechanic
        for mechanic in inferno.mechanics
        if type(mechanic).__name__ == "DamageRamp"
    )
    inferno.target_id = bandit.id
    ramp.on_target_observed(inferno, bandit, 33)
    ramp.on_target_observed(inferno, bandit, 4_000)
    ramp.on_attack_start(inferno, bandit)
    assert inferno.damage > ramp._get_damage_for_time(0)

    bandit._bandit_dashing = True
    ramp.on_target_observed(inferno, bandit, 33)

    assert inferno.target_id == bandit.id
    assert ramp._current_target_id is None
    assert ramp._current_target_ms == 0
    assert inferno.damage == ramp._get_damage_for_time(0)

    bandit._bandit_dashing = False
    ramp.on_target_observed(inferno, bandit, 33)
    assert ramp._current_target_id == bandit.id
    assert ramp._current_target_ms == 33


def test_inferno_lock_and_ramp_continue_through_a_river_jump():
    battle = BattleState()
    hog = _spawn_one(battle, "HogRider", 0, Position(9.0, 14.9))
    inferno = _spawn_one(battle, "InfernoDragon", 1, Position(9.0, 18.0))
    assert hog._try_start_river_jump(
        battle.entities[6].position,
        Position(9.0, battle.arena.RIVER_Y1),
        battle,
    )
    inferno.target_id = hog.id
    ramp = next(
        mechanic
        for mechanic in inferno.mechanics
        if type(mechanic).__name__ == "DamageRamp"
    )

    ramp.on_target_observed(inferno, hog, 33)
    ramp.on_target_observed(inferno, hog, 2_000)
    ramp.on_attack_start(inferno, hog)
    inferno.update(battle.dt, battle)

    assert inferno.target_id == hog.id
    assert ramp._current_target_id == hog.id
    assert ramp._current_target_ms > 2_000
    assert inferno.damage > ramp._get_damage_for_time(0)


def test_inferno_tower_ramp_resets_on_retarget():
    battle = BattleState()
    p0 = battle.players[0]
    p1 = battle.players[1]
    p0.elixir = 20.0
    p1.elixir = 20.0
    p0.hand = ["InfernoTower"]
    p0.deck = ["InfernoTower"]
    p0.cycle_queue.clear()
    p1.hand = ["Giant", "Giant"]
    p1.deck = ["Giant", "Giant"]
    p1.cycle_queue.clear()

    assert battle.deploy_card(0, "InfernoTower", Position(9.0, 14.0))
    assert battle.deploy_card(1, "Giant", Position(9.0, 20.0))

    inferno = next(
        e for e in battle.entities.values()
        if isinstance(e, Building) and e.player_id == 0 and e.card_stats.name == "InfernoTower"
    )
    # Let inferno lock target long enough to ramp.
    # Reach the second damage stage while the first Giant is still alive.
    for _ in range(100):
        battle.step()
    ramped_damage = inferno.damage
    assert ramped_damage > 100

    # Kill current target, force retarget.
    first_target = battle.entities.get(inferno.target_id)
    assert isinstance(first_target, Troop)
    first_target.take_damage(first_target.hitpoints)
    battle.step()
    assert battle.deploy_card(1, "Giant", Position(9.0, 20.0))

    # Within first few frames after retarget, damage should reset near base stage.
    for _ in range(5):
        battle.step()
    assert inferno.damage < ramped_damage


def _spawn_shielded_target(battle, card_name):
    if card_name == "DeliveryRecruit":
        delivery = battle.card_loader.get_card("RoyalDelivery")
        assert delivery is not None
        recruit_data = delivery._raw_entry["areaEffectObjectData"][
            "projectileData"
        ]["spawnCharacterData"]
        stats = troop_from_character_data(
            "DeliveryRecruit",
            recruit_data,
            elixir=0,
            rarity=recruit_data.get("rarity", "Common"),
        )
    else:
        stats = battle.card_loader.get_card(card_name)
        assert stats is not None
    target = battle._spawn_entity(
        Troop,
        Position(9.0, 16.0),
        1,
        stats,
    )
    target.deploy_delay_remaining = 0.0
    target.placement_pending = False
    target.on_spawn()
    return target


@pytest.mark.parametrize("fast_path", [False, True])
@pytest.mark.parametrize("attacker_name", ["InfernoDragon", "InfernoTower"])
@pytest.mark.parametrize(
    "target_name",
    ["DarkPrince", "Guards", "DeliveryRecruit"],
)
def test_inferno_ramp_resets_when_any_enabled_shield_breaks(
    fast_path,
    attacker_name,
    target_name,
):
    battle = BattleState(fast_path=fast_path)
    battle.entities.clear()
    battle.next_entity_id = 1
    stats = battle.card_loader.get_card(attacker_name)
    assert stats is not None
    inferno = battle._spawn_entity(
        Building if attacker_name == "InfernoTower" else Troop,
        Position(9.0, 14.0),
        0,
        stats,
    )
    inferno.deploy_delay_remaining = 0.0
    inferno.placement_pending = False
    inferno.on_spawn()
    target = _spawn_shielded_target(battle, target_name)
    ramp = next(
        mechanic
        for mechanic in inferno.mechanics
        if type(mechanic).__name__ == "DamageRamp"
    )

    hp_before = target.hitpoints
    for _ in range(180):
        battle.step()
        if getattr(target, "_shield_break_count", 0):
            break

    assert target.hitpoints == hp_before
    assert getattr(target, "_shield_break_count", 0) == 1
    assert inferno.damage == ramp._get_damage_for_time(0)


def test_shield_loss_broadcast_filters_target_and_obeys_global(monkeypatch):
    battle = BattleState()
    inferno = _spawn_one(
        battle,
        "InfernoDragon",
        0,
        Position(9.0, 14.0),
    )
    target = _spawn_shielded_target(battle, "DarkPrince")
    other = _spawn_shielded_target(battle, "Guards")
    ramp = next(
        mechanic
        for mechanic in inferno.mechanics
        if type(mechanic).__name__ == "DamageRamp"
    )
    inferno.target_id = target.id
    ramp._current_target_id = target.id
    ramp._current_target_ms = 4_000.0
    inferno.damage = ramp.stages[-1][1]

    other.broadcast_shield_lost()
    assert ramp._current_target_ms == 4_000.0
    assert inferno.damage == ramp.stages[-1][1]

    monkeypatch.setattr(
        "clasher.entities.LOGIC_INFERNO_RESET_ON_SHIELD_LOST",
        False,
    )
    target.broadcast_shield_lost()
    assert ramp._current_target_ms == 4_000.0
    assert inferno.damage == ramp.stages[-1][1]


@pytest.mark.parametrize("fast_path", [False, True])
@pytest.mark.parametrize("attacker_name", ["InfernoDragon", "InfernoTower"])
def test_zap_resets_every_enabled_inferno_channel(fast_path, attacker_name):
    battle = BattleState(fast_path=fast_path)
    battle.entities.clear()
    battle.next_entity_id = 1
    stats = battle.card_loader.get_card(attacker_name)
    assert stats is not None
    inferno = battle._spawn_entity(
        Building if attacker_name == "InfernoTower" else Troop,
        Position(9.0, 14.0),
        0,
        stats,
    )
    inferno.deploy_delay_remaining = 0.0
    inferno.placement_pending = False
    inferno.on_spawn()
    target = _spawn_one(battle, "Golem", 1, Position(9.0, 16.0))
    ramp = next(
        mechanic
        for mechanic in inferno.mechanics
        if type(mechanic).__name__ == "DamageRamp"
    )
    ramp.on_target_observed(inferno, target, 4_100)
    ramp.on_attack_start(inferno, target)
    assert inferno.damage > ramp._get_damage_for_time(0)

    assert SPELL_REGISTRY["Zap"].cast(
        battle,
        1,
        Position(inferno.position.x, inferno.position.y),
    )

    assert inferno.stun_timer == pytest.approx(0.5)
    assert inferno.target_id is None
    assert ramp._current_target_id is None
    assert ramp._current_target_ms == 0.0
    assert inferno.damage == ramp._get_damage_for_time(0)
