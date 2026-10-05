"""Build tests/fixtures/native_frozen_stop_route_15_535_86.json from scenario 7.

Offline only (no emulator): extracts the scenario-7 setup (seed, native initial
deck/hand/cycle/elixir, identical static commands) and the per-tick native
positions/HP of owner 1's Giant recorded on emulator-5582 by
s7_freeze_reacquire_route.py (s7_freeze_reacquire_route.json).

Native facts pinned (all ten variants, every tick from 300 while the Giant is alive):
  * control_no_goblins: a Giant that stopped on the Princess Tower, was frozen
    by an Ice Spirit (target dropped), re-acquired the tower standing in its
    stop cell and was then pushed out of range walks its retained stop route
    (head (28,16)), not a route rebuilt from the restart cell;
  * the other nine: displaced out of the stop cell before the re-acquisition,
    or with the retained head already inside the reached distance there, it
    rebuilds from the restart cell (the pre-existing scalar behaviour).
Usage: build_frozen_stop_route_fixture.py
"""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SOURCE = HERE / "s7_freeze_reacquire_route.json"
FIXTURE = ROOT / "tests/fixtures/native_frozen_stop_route_15_535_86.json"
FIRST_TICK = 300  # every stop is at 342..446; earlier walking frames are omitted


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    res = json.loads(SOURCE.read_text())
    variants = {}
    for name, row in res["variants"].items():
        assert row["first_divergence_vs_native"]["main"] is None, name
        restart = next((e for e in row["main"]["events"] if e.get("restart")), None)
        variants[name] = {
            "commands": [{"tick": c["tick"], "owner": c["owner"], "card": c["card"], "xy": list(c["xy"])}
                         for c in row["commands"]],
            "revert_first_divergence": row["first_divergence_vs_native"]["revert"],
            "giant": [r[:4] for r in row["native"]["giant"] if r[0] >= FIRST_TICK],
        }
    fixture = {
        "role": "development",
        "scope": "Opened native 15.535.86 scenario evidence (s7_freeze_reacquire_route.py, emulator-5582). "
                 "A building-targeting troop frozen while stopped on its navigation target, which "
                 "re-acquires it standing in its stop cell, resumes its unconsumed stop route when later "
                 "pushed out of range; displaced or already-reached cases rebuild from the restart cell.",
        "sources": {str(p.relative_to(ROOT)): sha(p) for p in (
            SOURCE, HERE / "s7_freeze_reacquire_route.py", HERE / "s7_candidate_models.py", HERE / "nm_lib.py")},
        "gamedata_sha256": res["provenance"]["gamedata_sha256"],
        "seed": res["seed"],
        "decks": {"0": ["Fireball", "Log", "HogRider", "Prince", "Giant", "Goblins", "Knight", "IceSpirit"],
                  "1": ["Zap", "Knight", "Goblins", "Cannon", "Musketeer", "IceGolem", "Archers", "Giant"]},
        "initial": {"players": [{k: p[k] for k in ("owner", "elixir", "deck", "hand", "cycle")}
                                for p in res["initial"]["players"]]},
        "giant_owner": 1,
        "variants": variants,
    }
    tracks = {}
    for name, row in variants.items():  # one line per Giant track
        tracks[name] = json.dumps(row["giant"], separators=(",", ":"))
        row["giant"] = f"@@{name}@@"
    text = json.dumps(fixture, indent=1)
    for name, track in tracks.items():
        text = text.replace(f'"@@{name}@@"', track)
    FIXTURE.write_text(text + "\n")
    print(FIXTURE, sha(FIXTURE))


if __name__ == "__main__":
    main()
