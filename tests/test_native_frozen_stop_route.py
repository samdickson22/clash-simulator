"""A frozen troop that re-acquires its tower standing resumes its stop route (15.535.86).

Fixture: opened development evidence recorded on emulator-5582 by
reports/strategy_council_20260928/m0/native-mechanics-20260928/s7_freeze_reacquire_route.py
and extracted by build_frozen_stop_route_fixture.py (pilot cards only: Giant,
Ice Spirit, Goblins, towers; identical static commands on both engines).

Native facts pinned here, per tick for owner 1's Giant (position and HP):
  * control_no_goblins: the Giant stops on the Princess Tower, is frozen by an
    Ice Spirit (target dropped), re-acquires the tower standing in its stop
    cell and is pushed out of range by owner 0's Giant. It walks its retained
    stop route (head (28,16)), not a route rebuilt from the restart cell;
  * the nine other variants displace it out of its stop cell before the
    re-acquisition, or leave the retained head inside the reached distance
    there. It then rebuilds from the restart cell (the pre-existing rule);
    these rule out "always resume" and "always rebuild at re-acquisition".
This resolves the open detail of
readiness/tier-a-fresh-v6/review/episode-24-mechanism.md.
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
from clasher.entities import Troop
from clasher.player import PlayerState

FIXTURES = Path(__file__).parent / "fixtures"
CASE = json.loads((FIXTURES / "native_frozen_stop_route_15_535_86.json").read_text())


@pytest.fixture(scope="module")
def loader(tmp_path_factory):
    path = tmp_path_factory.mktemp("gamedata") / "gamedata.json"
    path.write_bytes(
        gzip.decompress((FIXTURES / "native_gamedata_15_535_86_daa58b28.json.gz").read_bytes())
    )
    return CardDataLoader(path)


def _battle(loader, fast_path):
    names = {
        loader.get_card(name)._raw_entry["id"]: name
        for deck in CASE["decks"].values()
        for name in deck
    }
    players = []
    for owner in (0, 1):
        native = next(p for p in CASE["initial"]["players"] if p["owner"] == owner)
        players.append(PlayerState(
            owner,
            deck=[names[c["cardId"]] for c in native["deck"]],
            hand=[names[c["cardId"]] for c in sorted(native["hand"], key=lambda c: c["handIndex"])],
            cycle_queue=deque(
                names[c["cardId"]] for c in sorted(native["cycle"], key=lambda c: c["cycleIndex"])
            ),
            elixir=native["elixir"],
        ))
    battle = BattleState(players=players, rng=random.Random(CASE["seed"]), card_loader=loader)
    battle.fast_path = fast_path
    return battle


def _giant(battle):
    return next(
        (e for e in battle.entities.values()
         if e.player_id == CASE["giant_owner"] and e.card_stats.name == "Giant" and e.hitpoints > 0),
        None,
    )


@pytest.mark.parametrize("fast_path", [False, True])
@pytest.mark.parametrize("variant", sorted(CASE["variants"]))
def test_frozen_stop_route_matches_native_giant_track(loader, fast_path, variant):
    case = CASE["variants"][variant]
    battle = _battle(loader, fast_path)
    commands = {}
    for command in case["commands"]:
        commands.setdefault(command["tick"], []).append(command)
    track = {row[0]: row[1:] for row in case["giant"]}
    last = max(track)
    while battle.tick < last:
        for c in commands.get(battle.tick, []):
            assert battle.deploy_card(c["owner"], c["card"], Position(*c["xy"]))
        battle.step()
        if battle.tick in track:
            giant = _giant(battle)
            assert giant is not None, battle.tick
            got = [round(giant.position.x * 1000), round(giant.position.y * 1000),
                   round(giant.hitpoints)]
            assert got == track[battle.tick], (variant, battle.tick)


# ---- tier-a-fresh-v6 episode-24 regression (closed-loop scalar branch) ----
#
# Scalar job-00780 (alternate_card, balanced/balanced) re-runs the frozen v6
# branch plan with its controllers. Owner 1's Giant stops on owner 0's right
# Princess Tower at 1409, is frozen by an Ice Spirit 1439-1461, re-acquires the
# tower standing at 1462 and is pushed out of range by deploying Goblins at
# 1530. Native reference job-00781 (per-tick replay on emulator-5582) walks the
# retained stop route (30,16) from 1531; the rebuilt route (30,17) diverged by
# 0.0036 tiles and flipped the branch from a native loss to a scalar win.
ROOT = Path(__file__).resolve().parents[1]
V6 = ROOT / "reports/strategy_council_20260928/m0/readiness/tier-a-fresh-v6"
EP24_SCALAR_JOB = 780
EP24_NATIVE_GIANT = {1530: (15390, 9378), 1531: (15460, 9376), 1532: (15529, 9371)}
EP24_NATIVE_RESULT = (0.0, 7876.0, 7653.0, 1)  # job-00781 score, own, enemy, winner


@pytest.mark.skipif(not (V6 / "branch-plan.json").exists(), reason="v6 readiness artifacts absent")
def test_episode24_alternate_card_branch_matches_native_route_and_outcome(monkeypatch, tmp_path):
    import argparse
    import contextlib
    import importlib
    import time

    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    runner = importlib.import_module("run_readiness_v2")
    from clasher.rl.readiness_execution import ExecutionPlan, jobs

    plan = ExecutionPlan.model_validate_json((V6 / "branch-plan.json").read_text())
    job = jobs(plan)[EP24_SCALAR_JOB]
    assert (job.family_id, job.condition, job.candidate_role, job.engine) == (
        "m260928909-episode-24", "balanced/balanced", "alternate_card", "scalar")
    seen = {}
    waypoints = []
    stepping = {"tick": None}
    original_step = BattleState.step
    original_waypoint = Troop._native_movement_waypoint

    def waypoint(self, target_entity, battle_state=None):
        result = original_waypoint(self, target_entity, battle_state)
        if stepping["tick"] == 1531 and self.player_id == 1 and self.card_stats.name == "Giant":
            waypoints.append((round(result.x * 1000), round(result.y * 1000)))
        return result

    def step(self, *args, **kwargs):
        stepping["tick"] = self.tick + 1
        result = original_step(self, *args, **kwargs)
        if self.tick in EP24_NATIVE_GIANT:
            giant = min(
                (e for e in self.entities.values()
                 if e.player_id == 1 and e.card_stats is not None
                 and e.card_stats.name == "Giant" and e.hitpoints > 0),
                key=lambda e: abs(e.position.x - 15.4) + abs(e.position.y - 9.4),
            )
            seen[self.tick] = (
                (round(giant.position.x * 1000), round(giant.position.y * 1000)),
                [tuple(c) for c in getattr(giant, "_native_ground_route_cells", None) or []],
            )
        return result

    monkeypatch.setattr(BattleState, "step", step)
    monkeypatch.setattr(Troop, "_native_movement_waypoint", waypoint)
    output = tmp_path / "job"
    output.mkdir()
    args = argparse.Namespace(deadline=time.monotonic() + 3600, port=None)
    with contextlib.ExitStack() as stack:
        result = runner._execute_job_body(plan, job, output, args, stack, [], None)
    assert {t: xy for t, (xy, _) in seen.items()} == EP24_NATIVE_GIANT
    # The restart step heads for node (30,16) (centre (15.25, 8.25)), which
    # alone reproduces native's (+70, -2) step; the rebuilt (30,17) does not.
    assert waypoints and set(waypoints) == {(15250, 8250)}
    assert seen[1531][1][:1] == [(30, 16)]
    assert (result["score"], result["own_remaining_hp"], result["enemy_remaining_hp"],
            result["winner"]) == EP24_NATIVE_RESULT
