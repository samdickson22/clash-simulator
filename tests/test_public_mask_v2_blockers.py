"""Deployment-capability census and every current public payload spawn route."""
import inspect
import json
from dataclasses import fields, is_dataclass

import numpy as np
import pytest

from clasher import entities
from clasher.arena import Position
from clasher.battle import BattleState
from clasher.cards.c56_champions import MightyMinerSwitch
from clasher.rl.public_placement_v2 import payload_radii
from test_public_mask_v2 import builder, compare, request


SOURCES = ("Balloon", "GiantSkeleton", "BombTower", "SkeletonBalloon",
           "SkeletonBarrel", "Skeleton Barrel", "MightyMiner")


def test_all_blocking_classes_and_source_routes_are_reviewed(builder):
    # A newly introduced capability owner must get a public visibility review,
    # identity/radius mapping and geometry tests; it cannot silently evade v2.
    owners = set()
    for name, cls in vars(entities).items():
        if inspect.isclass(cls) and issubclass(cls, entities.Entity) and is_dataclass(cls):
            if any(f.name == "blocks_deployment" and f.default is True for f in fields(cls)):
                owners.add(name)
    assert owners == {"TimedExplosive"}
    death_sources = set()
    for name in builder.loader.load_card_definitions():
        stats = builder.loader.get_card(name)
        body = (getattr(stats, "_raw_entry", {}) or {}).get("summonCharacterData") or {}
        child = body.get("deathSpawnCharacterData") or {}
        if child.get("deathDamage") is not None and not child.get("hitpoints"):
            death_sources.add(name)
    assert death_sources == set(SOURCES) - {"MightyMiner"}
    assert {builder.token_names[k]: v for k, v in payload_radii(builder).items()} == {
        "Balloon": .45, "GiantSkeleton": .45, "BombTower": .45,
        "SkeletonBalloon": .5, "MightyMiner": .5,
    }
    assert entities.DeathAreaEffectContainer.blocks_deployment is False


def spawn_payload(battle, source, owner, position, clone):
    stats = battle.card_loader.get_card(source)
    parent = battle._spawn_entity(
        entities.Building if source == "BombTower" else entities.Troop,
        position, owner, stats)
    parent.deploy_delay_remaining = 0
    parent.placement_pending = False
    parent.is_clone = clone
    if source == "MightyMiner":
        ability = next(m for m in parent.mechanics if isinstance(m, MightyMinerSwitch))
        # Exercise the engine's actual bomb creation, without waiting through
        # unrelated combat. This state is a test fixture, never a mask input.
        ability.pending_ms = 0
        ability.on_object_tick(parent, 50)
    else:
        parent.take_damage(parent.hitpoints)
    payloads = [e for e in battle.entities.values()
                if e.is_alive and getattr(e, "blocks_deployment", False)]
    assert len(payloads) == 1
    return payloads[0]


@pytest.mark.parametrize("source", SOURCES)
@pytest.mark.parametrize("seat", [0, 1])
def test_every_payload_route_python_engine_and_rust(builder, source, seat):
    core = pytest.importorskip("clasher_core")
    from c56_controller import CARDS, metadata
    from differential import config, snapshot

    b = BattleState()
    b.players[seat].hand = ["BombTower", "RoyalHogs", "Balloon", "Fireball"]
    b.players[seat].elixir = 10
    pos = Position(8.5, 12.5 if seat == 0 else 19.5)
    payload = spawn_payload(b, source, 1-seat, pos, False)
    assert builder._actor_visible(payload, seat)
    expected = compare(builder, b, seat)
    cfg = config(tuple(sorted(set(CARDS) | {source})))
    native = core.NativeScripts(json.dumps(metadata(builder, mask_version=2)))
    actual = native.public_mask(core.BattleState(snapshot(b, cfg)), seat)
    assert np.array_equal(expected[:2304], actual[:2304]), source
    # Removing the effect must release both troop and building placements;
    # spell legality must not depend on it. This catches vacuous comparisons.
    payload.is_alive = False
    cleared = compare(builder, b, seat)
    assert np.any(cleared[:576] & ~expected[:576])
    assert np.any(cleared[576:1152] & ~expected[576:1152])
    assert np.array_equal(cleared[1728:2304], expected[1728:2304])


@pytest.mark.parametrize("source", SOURCES[:-1])
def test_cloned_payloads_keep_public_identity_and_geometry(builder, source):
    b = BattleState()
    b.players[0].hand = ["BombTower", "RoyalHogs", "Balloon", "Fireball"]
    b.players[0].elixir = 10
    payload = spawn_payload(b, source, 1, Position(8.5, 12.5), True)
    assert payload.is_clone and builder._actor_visible(payload, 0)
    compare(builder, b, 0)


def test_visible_living_parent_does_not_impersonate_ability_payload(builder):
    from clasher.rl.contract_v5 import ContractV5ActionMaskBuilder
    b = BattleState()
    b.players[0].hand = ["BombTower", "RoyalHogs", "Balloon", "Fireball"]
    b.players[0].elixir = 10
    mask = ContractV5ActionMaskBuilder(builder, mask_version=2)
    before = mask.build(request(builder, b, 0))
    b._spawn_entity(entities.Troop, Position(8.5, 12.5), 1,
                    b.card_loader.get_card("MightyMiner"))
    assert np.array_equal(before, mask.build(request(builder, b, 0)))
