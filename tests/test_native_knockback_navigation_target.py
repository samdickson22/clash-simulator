"""A pushed troop that retargets during the push walks its current target's route (15.535.86).

Fixture: opened development evidence from tier-a-fresh-v4 episode-03
(alternate_card Fireball, native job-00101 / scalar job-00100), built by
reports/strategy_council_20260928/m0/native-mechanics-20260928/build_knockback_navigation_fixture.py
from the read-only per-tick native replay described in
readiness/tier-a-fresh-v4/review/episode-03-mechanism.md.

Native facts pinned here:
  * the owner-1 Musketeer is pushed by the root Fireball, retargets to owner
    0's Cannon during the push (197) and back to Princess Tower 2 (198);
  * the push reset-hit route build must record its navigation target, so the
    switch back to the tower rebuilds the tower route (first cell (28,32));
  * the first post-push steps (207-210) and the downstream Archer position at
    297 equal native exactly.
"""

import gzip
import importlib
import json
from pathlib import Path

import pytest

from clasher.arena import Position
from clasher.data import CardDataLoader
from clasher.entities import Troop

FIXTURES = Path(__file__).parent / "fixtures"
CASE = json.loads(
    (FIXTURES / "native_knockback_navigation_target_15_535_86.json").read_text()
)


@pytest.fixture(scope="module")
def loader(tmp_path_factory):
    path = tmp_path_factory.mktemp("gamedata") / "gamedata.json"
    path.write_bytes(
        gzip.decompress((FIXTURES / "native_gamedata_15_535_86_daa58b28.json.gz").read_bytes())
    )
    return CardDataLoader(path)


def _bodies(battle):
    return sorted(
        [e.player_id, round(e.position.x * 1000), round(e.position.y * 1000), round(e.hitpoints)]
        for e in battle.entities.values()
        if isinstance(e, Troop) and e.hitpoints > 0
    )


@pytest.mark.parametrize("fast_path", [False, True])
def test_pushed_musketeer_retarget_uses_current_target_route(monkeypatch, loader, fast_path):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(root / "scripts"))
    scalar_initial = importlib.import_module("compare_reacting_public_branches").scalar_initial
    from clasher.rl.native_public_observation import PUBLIC_REFERENCE_CARDS

    names = {loader.get_card(n)._raw_entry["id"]: n for n in PUBLIC_REFERENCE_CARDS}
    battle = scalar_initial(CASE["initial"], names, CASE["config"], loader)
    battle.fast_path = fast_path
    commands = {}
    for command in CASE["commands"]:
        commands.setdefault(command["submitted_tick"], []).append(command)
    spec = CASE["musketeer"]
    track = {int(t): v for t, v in spec["xyhp"].items()}
    bodies = {int(t): v for t, v in CASE["bodies"].items()}
    route_cell = tuple(spec["push_route_first_cell"])
    musketeer = None
    seen = {"cannon": False}
    last = max(max(track), max(bodies))
    while battle.tick < last:
        for c in commands.get(battle.tick, []):
            assert battle.deploy_card(c["owner"], c["name"], Position(*c["xy"]))
        battle.step()
        tick = battle.tick
        if musketeer is None:
            musketeer = next(
                (e for e in battle.entities.values()
                 if e.player_id == spec["owner"] and e.card_stats.name == "Musketeer"),
                None,
            )
        if tick == spec["cannon_retarget_tick"]:
            # Precondition: retargeted to the Cannon while being pushed.
            assert musketeer._knockback_target is not None
            assert battle.entities[musketeer.target_id].card_stats.name == "Cannon"
            seen["cannon"] = True
        if spec["tower_retarget_tick"] <= tick < 207:
            # Back on the tower during the push: the tower route is rebuilt
            # and retained (no nodes are consumed while pushed).
            assert musketeer.target_id == spec["tower_id_scalar"], tick
            assert musketeer._native_navigation_target_id == spec["tower_id_scalar"], tick
            assert tuple(musketeer._native_ground_route_cells[0]) == route_cell, tick
        if tick in track:
            x, y, hp = track[tick]
            got = [round(musketeer.position.x * 1000), round(musketeer.position.y * 1000),
                   round(musketeer.hitpoints)]
            assert got == [x, y, hp], tick
        if tick in bodies:
            assert _bodies(battle) == bodies[tick], tick
    assert seen["cannon"]
    archer = CASE["archer_297"]["xy"]
    assert [archer[0], archer[1]] in [b[1:3] for b in bodies[297]]
