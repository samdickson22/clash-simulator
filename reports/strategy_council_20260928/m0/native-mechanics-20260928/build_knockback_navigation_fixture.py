"""Build tests/fixtures/native_knockback_navigation_target_15_535_86.json.

Offline only (no emulator): extracts the tier-a-fresh-v4 episode-03 setup
(capture initial state, config, prefix commands) and the alternate_card branch
command stream of native reference job-00101 (Fireball at (13.5, 14.5) on the
root tick 175), plus per-tick native positions recorded by the read-only
per-tick replay of job-00101 (/tmp/ep03v4/native-101/native_ticks.jsonl.gz,
review/episode-03-mechanism.md). All commands before tick 395 are identical in
native job-00101 and scalar job-00100.

Native facts pinned:
  * the owner-1 Musketeer (native 5000010) is pushed by the Fireball, retargets
    to owner 0's Cannon during the push (197) and back to Princess Tower 2
    (198); its first post-push steps (207-210) follow the tower route
    (first node (28,32)), not the Cannon route;
  * Archer 5000016 position at 297 (downstream of the Musketeer's route).
Usage: build_knockback_navigation_fixture.py [native_ticks.jsonl.gz]
"""

import gzip
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
TIER = ROOT / "reports/strategy_council_20260928/m0/readiness/tier-a-fresh-v4"
CAPTURE = TIER / "prefixes/episode-03"
NATIVE_JOB = TIER / "branches-reference-shard2-of8/job-00101"
TICKS = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/ep03v4/native-101/native_ticks.jsonl.gz")
FIXTURE = ROOT / "tests/fixtures/native_knockback_navigation_target_15_535_86.json"
MUSKETEER, ARCHER = 5000010, 5000016
TRACK = range(195, 216)
BODY_TICKS = (207, 208, 209, 210, 297)
LAST_TICK = 300


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    from clasher.data import CardDataLoader

    from clasher.rl.native_public_observation import PUBLIC_REFERENCE_CARDS

    loader = CardDataLoader(CAPTURE / "gamedata.json")

    names = {loader.get_card(n)._raw_entry["id"]: n for n in PUBLIC_REFERENCE_CARDS}
    root_tick = 175
    prefix = [
        {"owner": c["owner"], "name": c["name"], "xy": c["xy"], "submitted_tick": c["submitted_tick"]}
        for c in json.loads((CAPTURE / "result.json").read_text())["commands"]
        if c["submitted_tick"] < root_tick
    ]
    branch = []
    for line in gzip.open(NATIVE_JOB / "transport.jsonl.gz", "rt"):
        record = json.loads(line)
        for command in record["commands"]:
            _, owner, card, x, y, execute = command.split()
            assert int(execute) == record["tick"] + 1
            if record["tick"] <= LAST_TICK:
                branch.append({"owner": int(owner), "name": names[int(card)],
                               "xy": [int(x) / 1000, int(y) / 1000], "submitted_tick": record["tick"]})
    frames = {}
    for line in gzip.open(TICKS, "rt"):
        record = json.loads(line)
        frames[record["tick"]] = record["ordinary"]["objects"]
    def body(o):
        return [o["owner"], o["x"], o["y"], o["hp"]]
    musketeer = {}
    for tick in TRACK:
        o = next(o for o in frames[tick] if o["nativeObjectId"] == MUSKETEER)
        musketeer[str(tick)] = [o["x"], o["y"], o["hp"]]
    archer = next(o for o in frames[297] if o["nativeObjectId"] == ARCHER)
    bodies = {}
    for tick in BODY_TICKS:
        bodies[str(tick)] = sorted(
            body(o) for o in frames[tick]
            if o["cardId"] > 0 and o["hp"] is not None and o["hp"] > 0
            and o["cardId"] // 1000000 == 26
        )
    fixture = {
        "role": "development",
        "scope": "Opened native 15.535.86 branch evidence. A pushed troop whose target changes "
                 "during the push (Cannon, then back to Princess Tower) walks the route of its "
                 "current target after the push; the push reset-hit route build records its "
                 "navigation target.",
        "sources": {
            str(p.relative_to(ROOT)): sha(p)
            for p in (CAPTURE / "initial.json", CAPTURE / "plan.json", CAPTURE / "result.json",
                      CAPTURE / "gamedata.json", NATIVE_JOB / "transport.jsonl.gz",
                      NATIVE_JOB / "decisions.jsonl.gz")
        },
        "native_ticks": {"path": str(TICKS), "sha256": sha(TICKS)},
        "gamedata_sha256": sha(CAPTURE / "gamedata.json"),
        "initial": json.loads((CAPTURE / "initial.json").read_text()),
        "config": json.loads((CAPTURE / "plan.json").read_text())["config"],
        "root_tick": root_tick,
        "commands": prefix + branch,
        "musketeer": {"native_id": MUSKETEER, "owner": 1, "tower_id_scalar": 2,
                      "cannon_retarget_tick": 197, "tower_retarget_tick": 198,
                      "push_route_first_cell": [28, 32], "xyhp": musketeer},
        "archer_297": {"native_id": ARCHER, "owner": 1, "xy": [archer["x"], archer["y"]]},
        "bodies": bodies,
    }
    FIXTURE.write_text(json.dumps(fixture, indent=1) + "\n")
    print(FIXTURE, sha(FIXTURE))


if __name__ == "__main__":
    main()
