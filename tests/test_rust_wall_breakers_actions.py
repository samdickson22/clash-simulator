from __future__ import annotations

import random
from collections import deque

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building, Projectile, Troop
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rust_core import (
    ResidentRustBattle,
    compare_point_projectile_phase,
    rust_core_available,
)
from clasher.rust_differential import python_resident_semantic_snapshot
from clasher.rust_publication import ResidentPublicationError
from clasher.rust_runtime import (
    ResidentCompleteTickRuntime,
    RustBattleMode,
)

pytestmark = pytest.mark.skipif(
    not rust_core_available(), reason="optional Rust extension is not installed"
)


def _ready(entity: Troop | Building) -> None:
    entity.deploy_delay_remaining = 0.0
    entity.placement_pending = False
    entity._spawn_hook_pending = False
    entity._spawn_hook_fired = True
    entity.attack_cooldown = 0.0


def _death_nova_recheck_fixture() -> tuple[
    BattleState,
    Troop,
    Troop,
    Troop,
    Building,
]:
    battle = BattleState(rng=random.Random(114_400), fast_path=True)

    def spawn_troop(
        card_name: str,
        player_id: int,
        position: Position,
    ) -> Troop:
        card_stats = battle.card_loader.get_card(card_name)
        assert card_stats is not None
        prior_ids = set(battle.entities)
        battle._spawn_unit_at_position(position, player_id, card_stats)
        return next(
            entity
            for entity_id, entity in battle.entities.items()
            if entity_id not in prior_ids and isinstance(entity, Troop)
        )

    wall = spawn_troop("Wallbreakers", 0, Position(9.0, 15.0))
    # A neutral synthetic owner makes the Golem death nova hostile to the
    # later Knight while both remain hostile to the projectile. Resident
    # entity semantics intentionally permit non-player actor owners.
    golem = spawn_troop("Golem", 2, Position(9.0, 16.0))
    knight = spawn_troop("Knight", 1, Position(9.1, 16.0))
    cannon_stats = battle.card_loader.get_card("Cannon")
    assert cannon_stats is not None
    cannon = battle._spawn_entity(
        Building,
        Position(9.0, 16.0),
        1,
        cannon_stats,
    )
    assert isinstance(cannon, Building)
    for entity, position in (
        (wall, Position(9.0, 15.0)),
        (golem, Position(9.0, 16.0)),
        (knight, Position(9.1, 16.0)),
        (cannon, Position(9.0, 16.0)),
    ):
        _ready(entity)
        entity.position = position
    golem.hitpoints = 1
    golem.deploy_delay_remaining = 1.0
    golem.placement_pending = True
    golem._spawn_hook_pending = True
    golem._spawn_hook_fired = False
    knight.hitpoints = 200
    knight.attack_cooldown = 10.0
    cannon.attack_cooldown = 10.0
    wall.target_id = cannon.id
    wall._last_combat_target_id = cannon.id
    return battle, wall, golem, knight, cannon


def test_wall_breakers_aliases_are_the_only_new_structural_family() -> None:
    resident = ResidentRustBattle.from_battle(BattleState())
    supported = set(resident.resident_supported_action_cards())

    assert {"Wallbreakers", "Wall Breakers"} <= supported
    assert resident.resident_action_card_capability_reasons("Wallbreakers") == ()
    assert resident.resident_action_card_capability_reasons("Wall Breakers") == ()
    for near_match in (
        "FireSpirits",
        "BattleRam",
        "SkeletonBalloon",
        "SuspiciousBush",
    ):
        assert resident.resident_action_card_capability_reasons(near_match)


@pytest.mark.parametrize("lookup_name", ["Wallbreakers", "Wall Breakers"])
@pytest.mark.parametrize("player_id", [0, 1])
def test_wall_breakers_action_ingress_matches_exact_two_member_formation(
    lookup_name: str,
    player_id: int,
) -> None:
    battle = BattleState(rng=random.Random(114_200 + player_id))
    battle.players[player_id].hand = [lookup_name, None, None, None]
    battle.players[player_id].elixir = battle.players[player_id].max_elixir
    resident = ResidentRustBattle.from_battle(battle)
    action_space = DiscreteTileActionSpace()
    world_y = 10 if player_id == 0 else 21
    action = action_space.encode_action(0, 8, world_y, player_id)
    actions = [action_space.no_op_action, action_space.no_op_action]
    actions[player_id] = action

    order = [0, 1]
    battle.rng.shuffle(order)
    expected: dict[int, bool] = {}
    for ordered_player in order:
        expected[ordered_player] = action_space.apply_action(
            battle, ordered_player, actions[ordered_player]
        )
    actual, actual_order = resident.apply_resident_joint_actions(*actions)

    assert actual_order == tuple(order)
    assert actual == expected == {0: True, 1: True}
    spawned = [
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Troop)
        and entity.card_stats is not None
        and entity.card_stats.name == "Wallbreakers"
    ]
    assert len(spawned) == 2
    assert [entity.deploy_delay_remaining for entity in spawned] == [1.0, 1.1]
    assert spawned[0].card_stats is spawned[1].card_stats
    assert spawned[0].mechanics[0] is not spawned[1].mechanics[0]
    assert resident.next_entity_id == battle.next_entity_id
    assert resident.entity_state_bytes() == ResidentRustBattle.from_battle(
        battle
    ).entity_state_bytes()
    assert resident.rng_state_bytes() == ResidentRustBattle.from_battle(
        battle
    ).rng_state_bytes()


def test_demolition_launches_before_self_death_and_publishes_piercing_tombstone() -> None:
    candidate = BattleState(rng=random.Random(114_250), fast_path=True)
    wall_stats = candidate.card_loader.get_card("Wallbreakers")
    cannon_stats = candidate.card_loader.get_card("Cannon")
    assert wall_stats is not None and cannon_stats is not None
    before = set(candidate.entities)
    candidate._spawn_unit_at_position(Position(9.0, 15.0), 0, wall_stats)
    wall = next(
        entity
        for entity_id, entity in candidate.entities.items()
        if entity_id not in before and isinstance(entity, Troop)
    )
    cannon = candidate._spawn_entity(
        Building, Position(9.0, 16.0), 1, cannon_stats
    )
    assert isinstance(cannon, Building)
    wall.position = Position(9.0, 15.0)
    _ready(wall)
    _ready(cannon)
    next_id = candidate.next_entity_id
    cannon_hp = cannon.hitpoints
    control = candidate.clone()
    runtime = ResidentCompleteTickRuntime(candidate, RustBattleMode.ON)

    assert runtime.advance_ticks(1) == control.step_logic_ticks(1) == 1
    assert python_resident_semantic_snapshot(candidate) == (
        python_resident_semantic_snapshot(control)
    )

    registry = runtime._entity_registry
    published_wall = registry[wall.id]
    projectile = registry[next_id]
    assert isinstance(projectile, Projectile)
    assert not published_wall.is_alive
    assert published_wall.mechanics[0]._triggered is True
    assert projectile.pierces is True
    assert projectile.projectile_range == pytest.approx(0.001)
    assert projectile.hit_entity_ids == {cannon.id}
    assert not projectile.is_alive
    assert candidate.next_entity_id == next_id + 1
    assert cannon.hitpoints < cannon_hp


def test_wall_breakers_on_episode_matches_python_through_demolition() -> None:
    control = BattleState(rng=random.Random(114_300), fast_path=True)
    candidate = control.clone()
    for battle in (control, candidate):
        for player in battle.players:
            player.deck = ["Wallbreakers"] * 8
            player.hand = ["Wallbreakers"] * 4
            player.cycle_queue = deque(["Wallbreakers"] * 4)
            player.elixir = player.max_elixir
    action_space = DiscreteTileActionSpace()
    action = action_space.encode_action(0, 8, 14, 0)
    no_op = action_space.no_op_action

    order = [0, 1]
    control.rng.shuffle(order)
    for player_id in order:
        action_space.apply_action(
            control, player_id, (action, no_op)[player_id]
        )
    control.step_logic_ticks(1)
    runtime = ResidentCompleteTickRuntime(
        candidate, RustBattleMode.ON, action_ingress=True
    )

    result = runtime.apply_joint_actions_and_advance(action, no_op, 1)
    assert result.action_order == tuple(order)
    assert result.action_success == {0: True, 1: True}
    assert python_resident_semantic_snapshot(candidate) == (
        python_resident_semantic_snapshot(control)
    )

    for _ in range(23):
        assert runtime.advance_ticks(8) == control.step_logic_ticks(8) == 8
        assert python_resident_semantic_snapshot(candidate) == (
            python_resident_semantic_snapshot(control)
        )

    tombstones = [
        entity
        for entity in runtime._entity_registry.values()
        if isinstance(entity, Troop)
        and entity.card_stats is not None
        and entity.card_stats.name == "Wallbreakers"
    ]
    assert any(
        not entity.is_alive and entity.mechanics[0]._triggered is True
        for entity in tombstones
    )


def test_wall_breakers_commit_failure_restores_mechanic_and_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from clasher import rust_publication

    battle = BattleState(rng=random.Random(114_350), fast_path=True)
    wall_stats = battle.card_loader.get_card("Wallbreakers")
    cannon_stats = battle.card_loader.get_card("Cannon")
    assert wall_stats is not None and cannon_stats is not None
    before_ids = set(battle.entities)
    battle._spawn_unit_at_position(Position(9.0, 15.0), 0, wall_stats)
    wall = next(
        entity
        for entity_id, entity in battle.entities.items()
        if entity_id not in before_ids and isinstance(entity, Troop)
    )
    cannon = battle._spawn_entity(
        Building, Position(9.0, 16.0), 1, cannon_stats
    )
    assert isinstance(cannon, Building)
    _ready(wall)
    _ready(cannon)
    runtime = ResidentCompleteTickRuntime(battle, RustBattleMode.ON)
    resident = runtime.resident
    assert resident is not None
    semantic_before = python_resident_semantic_snapshot(battle)
    active_before = tuple(battle.entities.items())
    registry_before = tuple(runtime.entity_registry.items())
    rng_before = battle.rng.getstate()
    next_id_before = battle.next_entity_id
    wall_position = wall.position
    wall_mechanic = wall.mechanics[0]
    wall_mechanic_state = dict(vars(wall_mechanic))
    cannon_hp = cannon.hitpoints

    def fail_live_commit(*args: object, **kwargs: object) -> None:
        raise ResidentPublicationError("injected Wall Breakers commit failure")

    monkeypatch.setattr(
        rust_publication,
        "_after_typed_publication_commit",
        fail_live_commit,
    )

    with pytest.raises(RuntimeError, match="runtime is now poisoned"):
        runtime.advance_ticks(1)

    assert python_resident_semantic_snapshot(battle) == semantic_before
    assert tuple(battle.entities.items()) == active_before
    assert tuple(runtime.entity_registry.items()) == registry_before
    assert battle.rng.getstate() == rng_before
    assert battle.next_entity_id == next_id_before
    assert wall.position is wall_position
    assert wall.mechanics[0] is wall_mechanic
    assert vars(wall_mechanic) == wall_mechanic_state
    assert cannon.hitpoints == cannon_hp
    assert runtime.resident is resident


def test_piercing_rechecks_after_synchronous_death_nova_before_each_hit() -> None:
    control, _, control_golem, control_knight, control_cannon = (
        _death_nova_recheck_fixture()
    )
    candidate = control.clone()
    runtime = ResidentCompleteTickRuntime(candidate, RustBattleMode.ON)
    projectile_id = candidate.next_entity_id

    assert runtime.advance_ticks(1) == control.step_logic_ticks(1) == 1
    assert python_resident_semantic_snapshot(candidate) == (
        python_resident_semantic_snapshot(control)
    )

    projectile = runtime.entity_registry[projectile_id]
    assert isinstance(projectile, Projectile)
    assert projectile.hit_entity_ids == {control_golem.id, control_cannon.id}
    assert control_knight.id not in projectile.hit_entity_ids
    assert not runtime.entity_registry[control_golem.id].is_alive
    assert not runtime.entity_registry[control_knight.id].is_alive
    assert not projectile.is_alive


def test_death_nova_recheck_commit_failure_restores_all_tombstone_inputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from clasher import rust_publication

    battle, wall, golem, knight, cannon = _death_nova_recheck_fixture()
    runtime = ResidentCompleteTickRuntime(battle, RustBattleMode.ON)
    resident = runtime.resident
    assert resident is not None
    semantic_before = python_resident_semantic_snapshot(battle)
    active_before = tuple(battle.entities.items())
    registry_before = tuple(runtime.entity_registry.items())
    rng_before = battle.rng.getstate()
    next_id_before = battle.next_entity_id
    identities = tuple(map(id, (wall, golem, knight, cannon, wall.mechanics[0])))

    def fail_live_commit(*args: object, **kwargs: object) -> None:
        raise ResidentPublicationError("injected death-nova commit failure")

    monkeypatch.setattr(
        rust_publication,
        "_after_typed_publication_commit",
        fail_live_commit,
    )

    with pytest.raises(RuntimeError, match="runtime is now poisoned"):
        runtime.advance_ticks(1)

    assert python_resident_semantic_snapshot(battle) == semantic_before
    assert tuple(battle.entities.items()) == active_before
    assert tuple(runtime.entity_registry.items()) == registry_before
    assert battle.rng.getstate() == rng_before
    assert battle.next_entity_id == next_id_before
    assert tuple(map(id, (wall, golem, knight, cannon, wall.mechanics[0]))) == identities
    assert runtime.resident is resident


def test_hydrated_piercing_projectile_honors_ignore_buildings() -> None:
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    knight_stats = battle.card_loader.get_card("Knight")
    cannon_stats = battle.card_loader.get_card("Cannon")
    assert knight_stats is not None and cannon_stats is not None
    cannon = battle._spawn_entity(
        Building,
        Position(9.0, 10.001),
        1,
        cannon_stats,
    )
    assert isinstance(cannon, Building)
    prior_ids = set(battle.entities)
    battle._spawn_unit_at_position(Position(9.1, 10.001), 1, knight_stats)
    knight = next(
        entity
        for entity_id, entity in battle.entities.items()
        if entity_id not in prior_ids and isinstance(entity, Troop)
    )
    projectile = Projectile(
        id=battle.next_entity_id,
        position=Position(9.0, 10.0),
        player_id=0,
        card_stats=knight_stats,
        hitpoints=1,
        max_hitpoints=1,
        damage=42,
        range=5.0,
        sight_range=1.0,
        target_position=Position(9.0, 10.001),
        travel_speed=20.0,
        splash_radius=1.5,
        hits_air=True,
        hits_ground=True,
        ignore_buildings=True,
        source_name="piercing-ignore-buildings-fixture",
        primary_target=knight,
        tracks_target=False,
        pierces=True,
        projectile_range=0.001,
    )
    projectile.start_collision_resolved = True
    battle.entities[projectile.id] = projectile
    battle.next_entity_id += 1
    resident = ResidentRustBattle.from_battle(battle)
    cannon_hp = cannon.hitpoints
    knight_hp = knight.hitpoints

    assert resident.supports_point_projectile_phase
    resident.advance_point_projectile_phase()
    projectile.update(battle.dt, battle)
    projectile.quantize_logic_position()
    compare_point_projectile_phase(battle, resident)

    assert cannon.hitpoints == cannon_hp
    assert knight.hitpoints < knight_hp
    assert projectile.hit_entity_ids == {knight.id}
