"""Opt-in mask regression, fair-input invariance and engine/Rust differentials."""
import json
from dataclasses import replace

import numpy as np
import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building, Troop
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.contract_v5 import ContractV5ActionMaskBuilder, ContractV5ObservationBuilder, CachedContractV5ActionMask
from clasher.rl.public_action_mask import PublicActionMaskInput


@pytest.fixture(scope="module")
def builder():
    return ContractV5ObservationBuilder()


def request(builder, battle, seat):
    return PublicActionMaskInput.from_confidence_observation(builder.build_public(battle, seat))


def compare(builder, battle, seat):
    public = ContractV5ActionMaskBuilder(builder, mask_version=2).build(request(builder, battle, seat))
    exact = DiscreteTileActionSpace().legal_action_mask(battle, seat, fast_path=False)
    bad = np.flatnonzero(public[:2304] != exact[:2304])
    assert not len(bad), (seat, battle.players[seat].hand, bad[:25].tolist(),
        [(e.card_stats.name, builder.token_names[builder._entity_row(e,seat)[0]], e.card_stats.collision_radius)
         for e in battle.entities.values() if e.is_alive and isinstance(e,Building)])
    fast = DiscreteTileActionSpace(mask_version=2).legal_action_mask(battle, seat, fast_path=True)
    assert np.array_equal(exact[:2304], fast[:2304])
    return public


@pytest.mark.parametrize("seat", [0, 1])
@pytest.mark.parametrize("source", [None, "Balloon", "BombTower", "SkeletonBarrel"])
def test_all_placements_against_scalar_guards(builder, seat, source):
    b = BattleState(fast_path=True)
    b.players[seat].hand = ["BombTower", "Tesla", "RoyalHogs", "Balloon"]
    b.players[seat].elixir = 10
    b._spawn_entity(Building, Position(3.5, 11.5 if seat == 0 else 20.5), seat,
                    b.card_loader.get_card("Cannon"))
    if source:
        e = b._spawn_entity(Building if source == "BombTower" else Troop,
                            Position(8.5, 12.5 if seat == 0 else 19.5), 1-seat,
                            b.card_loader.get_card(source))
        e.deploy_delay_remaining = 0
        e.placement_pending = False
        e.take_damage(e.hitpoints)
    compare(builder, b, seat)


@pytest.mark.parametrize("seat", [0, 1])
def test_spells_miner_mirror_and_expanded_bridge(builder, seat):
    b = BattleState()
    b.players[seat].hand = ["Graveyard", "RoyalDelivery", "Miner", "Mirror"]
    b.players[seat].last_played_card = "Tesla"
    b.players[seat].last_played_card_cost = 4
    b.players[seat].elixir = 10
    for e in b.entities.values():
        if e.player_id != seat and e.card_stats.name == "Tower":
            e.hitpoints = 0
            e.is_alive = False
    b.players[1-seat].left_tower_hp = b.players[1-seat].right_tower_hp = 0
    compare(builder, b, seat)


def test_default_is_frozen_and_v2_cache_includes_payloads(builder):
    b = BattleState()
    b.players[0].hand = ["Knight", "Cannon", "Fireball", "Log"]
    b.players[0].elixir = 10
    before = builder.build_public(b, 0)
    legacy = ContractV5ActionMaskBuilder(builder)
    assert np.array_equal(legacy.build(request(builder, b, 0)),
                          ContractV5ActionMaskBuilder(builder, mask_version=1).build(request(builder, b, 0)))
    cache = CachedContractV5ActionMask(builder, mask_version=2)
    old = cache.build(before)
    e = b._spawn_entity(Troop, Position(9.5, 12.5), 1, b.card_loader.get_card("Balloon"))
    e.deploy_delay_remaining = 0
    e.placement_pending = False
    e.take_damage(e.hitpoints)
    after = builder.build_public(b, 0)
    new = cache.build(after)
    assert not np.array_equal(new, old)
    assert np.array_equal(new, ContractV5ActionMaskBuilder(builder, mask_version=2).build(request(builder, b, 0)))
    # Living bodies don't reserve deployment merely because their deploy timer runs.
    obs = request(builder, b, 0)
    changed = obs.entity_features.copy()
    changed[:, 12:23] = 1
    assert np.array_equal(new, ContractV5ActionMaskBuilder(builder, mask_version=2).build(
        replace(obs, entity_features=changed)))


def test_unknown_version_fails(builder):
    for version in (0, 3, True, "2"):
        with pytest.raises(ValueError):
            ContractV5ActionMaskBuilder(builder, mask_version=version)


@pytest.mark.parametrize("seat", [0, 1])
def test_deploy_card_itself_and_public_only_inputs(builder, seat, monkeypatch):
    b = BattleState()
    b.players[seat].hand = ["Cannon", "Tesla", "RoyalHogs", "Balloon"]
    b.players[seat].elixir = 10
    b._spawn_entity(Building, Position(3.5, 11.5), 0, b.card_loader.get_card("Cannon"))
    e = b._spawn_entity(Troop, Position(9.5, 12.5), 1, b.card_loader.get_card("Balloon"))
    e.deploy_delay_remaining = 0
    e.placement_pending = False
    e.take_damage(e.hitpoints)
    expected = compare(builder, b, seat)
    # All rejection guards precede the first resource mutation. Intercept that
    # boundary instead of cloning 2,304 times or duplicating the engine guards.
    class Accepted(Exception):
        pass
    def commit(*_):
        raise Accepted
    monkeypatch.setattr(b.players[seat], "play_card", commit)
    space = DiscreteTileActionSpace()
    for action in range(2304):
        decoded = space.decode_action(action, seat)
        try:
            actual = b.deploy_card(seat, b.players[seat].hand[decoded.slot], decoded.position)
        except Accepted:
            actual = True
        assert actual == expected[action], (seat, action)
    # Opponent-private state has no path into mask computation.
    b.players[1-seat].hand = ["Mirror"]*4
    b.players[1-seat].deck = ["Mirror"]*8
    b.rng.seed(923)
    assert np.array_equal(expected, ContractV5ActionMaskBuilder(builder, mask_version=2).build(request(builder,b,seat)))


def test_v2_simulator_mask_restores_expanded_bridge_and_terminal_guard(builder):
    b = BattleState()
    b.players[0].hand = ["Knight", "Log", "Cannon", "Fireball"]
    b.players[0].elixir = 10
    for e in b.entities.values():
        if e.player_id == 1 and e.card_stats.name == "Tower" and e.position.x < 9:
            e.is_alive = False
            e.hitpoints = 0
    b.players[1].left_tower_hp = 0
    old = DiscreteTileActionSpace()
    new = DiscreteTileActionSpace(mask_version=2)
    bridge = 15*18+3
    assert not old.legal_action_mask(b,0,fast_path=True)[bridge]
    assert new.legal_action_mask(b,0,fast_path=True)[bridge]
    compare(builder,b,0)
    b.game_over = True
    assert np.flatnonzero(new.legal_action_mask(b,0)).tolist() == [2304]


@pytest.mark.parametrize("name", ["GoblinHut", "Elixir Collector", "BarbarianHut", "Tombstone", "GoblinCage"])
@pytest.mark.parametrize("seat", [0, 1])
def test_serialized_building_body_radii(builder, name, seat):
    b=BattleState()
    b.players[seat].hand=[name,"Cannon","Tesla","Balloon"]
    b.players[seat].elixir=10
    b._spawn_entity(Building,Position(8.5,11.5 if seat==0 else 22.5),seat,b.card_loader.get_card(name))
    compare(builder,b,seat)


def test_v2_simulator_building_guard_does_not_use_stale_candidate_cache(builder):
    b=BattleState(fast_path=False)
    b.players[0].hand=["Cannon"]
    b.players[0].elixir=10
    e=b._spawn_entity(Building,Position(7.5,11.5),0,b.card_loader.get_card("GoblinDrill"))
    old=DiscreteTileActionSpace()
    old.legal_action_mask(b,0,fast_path=True)
    e.position=Position(12.5,12.5)
    scalar=old.legal_action_mask(b,0,fast_path=False)
    assert not np.array_equal(old.legal_action_mask(b,0,fast_path=True),scalar)
    assert np.array_equal(DiscreteTileActionSpace(mask_version=2).legal_action_mask(b,0,fast_path=True),scalar)


def test_rust_python_placements(builder):
    core = pytest.importorskip("clasher_core")
    from c56_controller import metadata, CARDS
    from differential import config, snapshot
    cfg = config(CARDS)
    native = core.NativeScripts(json.dumps(metadata(builder, mask_version=2)))
    for seat in (0, 1):
        b = BattleState()
        b.players[seat].hand = ["BombTower", "Tesla", "RoyalHogs", "Balloon"]
        b.players[seat].elixir = 10
        e = b._spawn_entity(Troop, Position(9.5, 12.5), 1, b.card_loader.get_card("Balloon"))
        e.deploy_delay_remaining = 0
        e.placement_pending = False
        e.take_damage(e.hitpoints)
        expected = compare(builder, b, seat)
        actual = native.public_mask(core.BattleState(snapshot(b, cfg)), seat)
        assert np.array_equal(expected[:2304], actual[:2304])


def test_search_requires_consistent_mask_version(builder):
    from types import SimpleNamespace
    from clasher.rl.public_scripted_opponent import PublicScriptedOpponent
    from clasher.rl.c56_rollout_planner import C56RolloutPlanner
    old = PublicScriptedOpponent(builder,card_scope="c56")
    new = PublicScriptedOpponent(builder,card_scope="c56",mask_version=2)
    with pytest.raises(ValueError,match="every rollout"):
        C56RolloutPlanner(builder,{"balanced":new,"pressure":old})
    with pytest.raises(ValueError,match="native rollout"):
        C56RolloutPlanner(builder,{"balanced":new},backend="native",
                         native=SimpleNamespace(mask_version=1),native_config={})
    planner=C56RolloutPlanner(builder,{"balanced":new})
    assert planner.space.mask_version==2
