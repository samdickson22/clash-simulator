"""Native King wake-up under Zap stun and Ice Spirit freeze (15.535.86).

Fixture: opened development controls recorded by
reports/strategy_council_20260928/m0/native-mechanics-20260928/ (s1b, s1c).
Native facts pinned here:
  * a Zap anywhere in the first ~3.3 s of the wake-up adds no delay;
  * a Zap in the last ~0.7 s (or an Ice Spirit freeze there) delays the first
    shot, because the remaining first-hit phase is retained, not advanced.
"""

import gzip
import json
import random
from collections import deque
from pathlib import Path

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.data import CardDataLoader
from clasher.player import PlayerState

FIXTURES = Path(__file__).parent / "fixtures"
REFERENCE = json.loads((FIXTURES / "native_king_wakeup_stun_15_535_86.json").read_text())
SWEEP = REFERENCE["zap_sweep"]
ICE = REFERENCE["ice_spirit"]
KING_XY = (9.0, 3.0)
LEFT_PRINCESS_XY = (3.5, 6.5)


@pytest.fixture(scope="module")
def loader(tmp_path_factory):
    path = tmp_path_factory.mktemp("gamedata") / "gamedata.json"
    path.write_bytes(
        gzip.decompress((FIXTURES / "native_gamedata_15_535_86_daa58b28.json.gz").read_bytes())
    )
    return CardDataLoader(path)


def _battle(section, loader):
    players = []
    for owner in (0, 1):
        state = section["initial"][str(owner)]
        players.append(PlayerState(
            owner, deck=list(state["deck"]), hand=list(state["hand"]),
            cycle_queue=deque(state["cycle"]), elixir=state["elixir"],
        ))
    return BattleState(players=players, rng=random.Random(section["seed"]), card_loader=loader)


def _owner0_tower_at(battle, xy):
    return next(
        (e for e in battle.entities.values()
         if e.player_id == 0 and e.is_alive and e.card_stats is not None
         and "Tower" in e.card_stats.name
         and (round(e.position.x, 3), round(e.position.y, 3)) == xy),
        None,
    )


def _run(battle, commands, end, policy=None):
    king = _owner0_tower_at(battle, KING_XY)
    seen = set(battle.entities)
    by_tick = {}
    for c in commands:
        by_tick.setdefault(c["tick"], []).append(c)
    first_shot = None
    while battle.tick < end and first_shot is None:
        todo = list(by_tick.get(battle.tick, []))
        if policy is not None:
            todo += policy(battle)
        for c in todo:
            assert battle.deploy_card(c["owner"], c["card"], Position(*c["xy"])), c
        battle.step()
        for entity_id, entity in battle.entities.items():
            if entity_id in seen:
                continue
            seen.add(entity_id)
            source = getattr(entity, "source_id", None)
            if source is None:
                source = getattr(getattr(entity, "source_entity", None), "id", None)
            if source == king.id:
                first_shot = battle.tick
    return first_shot


def _zap_first_shot(row, loader):
    commands = list(SWEEP["base_commands"])
    if row["zap_cast_tick"] is not None:
        commands.append({"tick": row["zap_cast_tick"], "owner": 1, "card": "Zap",
                         "xy": SWEEP["zap_target"]})
    return _run(_battle(SWEEP, loader), commands, 470)


ROWS = {row["zap_cast_tick"]: row for row in SWEEP["rows"]}
CONTROL = ROWS[None]


@pytest.mark.parametrize("zap_tick", [286, 295, 310, 331, 349])
def test_zap_during_wake_up_delay_adds_no_delay(zap_tick, loader):
    row = ROWS[zap_tick]
    shot = _zap_first_shot(row, loader)
    native_delay = row["native_first_shot_tick"] - row["native_activation_tick"]
    # Native: the first shot stays 80 ticks after the activating hit.
    assert native_delay == 80
    # Scalar Fireball contact lands one tick after native in this geometry.
    assert shot - row["native_first_shot_tick"] in (0, 1)
    if zap_tick >= 295:
        assert shot == _zap_first_shot(CONTROL, loader)


@pytest.mark.parametrize("zap_tick", [355, 361, 367, 370])
def test_zap_late_in_wake_up_delays_first_shot_like_native(zap_tick, loader):
    row = ROWS[zap_tick]
    shot = _zap_first_shot(row, loader)
    control = _zap_first_shot(CONTROL, loader)
    assert row["native_first_shot_tick"] > CONTROL["native_first_shot_tick"]
    assert shot > control
    # Small residual: native reacquires at thaw with a 0.45 s load; scalar
    # resumes its retained 0.7 s first-hit phase. At most 4 ticks apart.
    assert abs(shot - row["native_first_shot_tick"]) <= 4


def test_ice_spirit_freeze_at_end_of_wake_up_matches_native(loader):
    results = {}
    for name, case in ICE["cases"].items():
        battle = _battle(ICE, loader)
        state = {"fall": None, "done": case["test"] is None}

        def policy(b, case=case, state=state):
            if state["fall"] is None and _owner0_tower_at(b, LEFT_PRINCESS_XY) is None:
                state["fall"] = b.tick
            if not state["done"] and state["fall"] is not None:
                card, xy, delay = case["test"]
                if b.tick >= state["fall"] + delay:
                    state["done"] = True
                    return [{"tick": b.tick, "owner": 1, "card": card, "xy": xy}]
            return []

        results[name] = (_run(battle, ICE["prefix"], 900, policy), state["fall"])
    for name, case in ICE["cases"].items():
        shot, fall = results[name]
        assert fall == case["native_fall_tick"]
        assert shot == case["native_first_shot_tick"], name
