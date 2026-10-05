"""Build tests/fixtures/native_king_activation_target_lock_15_535_86.json.

Offline only (no emulator): extracts the owner-1 King and the two Goblins whose
distance order swaps during the King's 700 ms first-hit phase from recorded
native branch tier-a-fresh-v3 job-00161 (episode-05, balanced/pressure,
immediate_play action 1796), 5-tick decision frames 2350..2375, plus the
episode-05 scalar replay setup (job-00160 recorded actions) used by
tests/test_native_king_activation_target_lock.py.
Usage: build_king_target_lock_fixture.py
"""

import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
TIER = ROOT / "reports/strategy_council_20260928/m0/readiness/tier-a-fresh-v3"
NATIVE = TIER / "branches-reference-shard0-of8/job-00161/decisions.jsonl.gz"
SCALAR = TIER / "branches-scalar/job-00160/decisions.jsonl.gz"
CAPTURE = TIER / "prefixes/episode-05"
FIXTURE = ROOT / "tests/fixtures/native_king_activation_target_lock_15_535_86.json"
KING, LOCKED, NEARER = 5000003, 5000046, 5000045
TICKS = range(2350, 2380, 5)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(frame):
    rich = {o["nativeObjectId"]: o for o in frame["rich"]["objects"]}
    out = {"king": None, "goblins": {}, "king_projectiles": []}
    for o in frame["ordinary"]["objects"]:
        r = rich.get(o["nativeObjectId"], {})
        target = (r.get("targetEntityKey") or [None, None, None])[2]
        base = {"id": o["nativeObjectId"], "xy": [o["x"], o["y"]], "hp": o["hp"], "target": target}
        if o["nativeObjectId"] == KING:
            base["attack_timeline_ms"] = (r.get("phaseRuntime") or {}).get("attackTimelineMs")
            out["king"] = base
        elif o["nativeObjectId"] in (LOCKED, NEARER):
            out["goblins"][str(o["nativeObjectId"])] = base
        projectile = r.get("projectile")
        if projectile and (projectile.get("sourceEntityKey") or [0, 0, 0])[2] == KING:
            out["king_projectiles"].append(
                {"id": o["nativeObjectId"], "xy": [o["x"], o["y"]],
                 "target": (projectile.get("targetEntityKey") or [None, None, None])[2]})
    return out


def main():
    frames = {}
    for line in gzip.open(NATIVE, "rt"):
        record = json.loads(line)
        if record["tick"] in TICKS:
            frames[str(record["tick"])] = rows(record["native_frame"])
    fixture = {
        "role": "development",
        "scope": "Opened native 15.535.86 branch evidence. After activation the King locks its "
                 "first target during the 700 ms first-hit phase and keeps it when another unit "
                 "becomes nearer; the first shot goes to the locked unit.",
        "sources": {str(NATIVE.relative_to(ROOT)): sha(NATIVE),
                    str(SCALAR.relative_to(ROOT)): sha(SCALAR)},
        "gamedata_sha256": sha(CAPTURE / "gamedata.json"),
        "king_owner": 1,
        "king_xy": [9000, 29000],
        "activation_delay_end_tick": 2355,
        "first_shot_tick": 2369,
        "locked_goblin": LOCKED,
        "nearer_goblin": NEARER,
        "frames": frames,
        "episode_05_replay": {
            "capture": str(CAPTURE.relative_to(ROOT)),
            "capture_sha256": {name: sha(CAPTURE / name)
                               for name in ("initial.json", "plan.json", "result.json", "gamedata.json")},
            "root_tick": 1185,
            "actions": str(SCALAR.relative_to(ROOT)),
            "native_king_hp_2375": frames["2375"]["king"]["hp"],
        },
    }
    FIXTURE.write_text(json.dumps(fixture, indent=1) + "\n")
    print("wrote", FIXTURE, FIXTURE.stat().st_size)


if __name__ == "__main__":
    main()
