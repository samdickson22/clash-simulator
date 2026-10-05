"""Scenario 2: Dark Prince shield (native vs scalar).

Variants (identical static commands on both engines):
  duel_left   owner-0 Knight (3.5,13.5) vs owner-1 Dark Prince (3.5,18.5), both at
              tick 100; they meet at the left bridge outside Princess range.
  duel_right  mirrored lane (14.5), different approach geometry.
  fireball    owner-1 Dark Prince at (14.5,21.5) at tick 100; owner-0 Fireball at
              (14.5,21.0) at tick 100 (a single direct hit larger than the shield).
  zap         same, with Zap (a single hit smaller than the shield), then Fireball
              at tick 160 to break what remains.
Measured: per-tick HP and shield for both units, hits, winner and remaining HP.

Usage: s2_shield.py <emulator-serial>
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nm_lib as L  # noqa: E402

SERIAL = sys.argv[1] if len(sys.argv) > 1 else "emulator-5582"
PORT = L.PORTS[SERIAL]
D0 = ["Knight", "Fireball", "Zap", "Giant", "Skeletons", "Musketeer", "Cannon", "Arrows"]
D1 = ["DarkPrince", "HogRider", "Knight", "Log", "IceSpirit", "Giant", "IceGolem", "Tesla"]
VARIANTS = {
    "duel_left": ([{"tick": 100, "owner": 0, "card": "Knight", "xy": (3.5, 13.5)},
                   {"tick": 100, "owner": 1, "card": "DarkPrince", "xy": (3.5, 18.5)}], 700),
    "duel_right": ([{"tick": 100, "owner": 0, "card": "Knight", "xy": (14.5, 13.5)},
                    {"tick": 100, "owner": 1, "card": "DarkPrince", "xy": (14.5, 18.5)}], 700),
    "fireball": ([{"tick": 100, "owner": 1, "card": "DarkPrince", "xy": (14.5, 21.5)},
                  {"tick": 100, "owner": 0, "card": "Fireball", "xy": (14.5, 21.0)}], 200),
    "zap_then_fireball": ([{"tick": 100, "owner": 1, "card": "DarkPrince", "xy": (14.5, 21.5)},
                           {"tick": 100, "owner": 0, "card": "Zap", "xy": (14.5, 21.5)},
                           {"tick": 140, "owner": 0, "card": "Fireball", "xy": (14.5, 20.5)}], 220),
}
UNITS = ("DarkPrince", "Knight")


def trajectory(frames):
    """Per-unit [tick, x, y, hp, shield, target] rows, and HP/shield change events."""
    out = {}
    for f in frames:
        for o in f["objects"]:
            if o["name"] in UNITS:
                out.setdefault(o["name"], []).append(
                    [f["tick"], o["x"], o["y"], o["hp"], o.get("shield"), o.get("target")])
    events = {}
    for name, rows in out.items():
        ev, prev = [], None
        for r in rows:
            if prev is not None and (r[3] != prev[3] or r[4] != prev[4]):
                ev.append({"tick": r[0], "hp": r[3], "shield": r[4],
                           "hp_delta": (r[3] or 0) - (prev[3] or 0),
                           "shield_delta": (r[4] or 0) - (prev[4] or 0)})
            prev = r
        events[name] = ev
    final = {name: rows[-1] for name, rows in out.items()}
    last_tick = frames[-1]["tick"]
    alive = {name: rows[-1][0] == last_tick for name, rows in out.items()}
    first = {name: rows[0] for name, rows in out.items()}
    return {"rows": out, "events": events, "final": final, "alive_at_end": alive, "first": first}


def main():
    assert L.free_gib() > 8
    seed, config, initial = L.find_seed(PORT, D0, D1, need0=("Knight", "Fireball", "Zap"),
                                        need1=("DarkPrince",))
    res = {"scenario": "dark_prince_shield", "serial": SERIAL, "seed": seed, "config": config,
           "variants": {}}
    for name, (cmds, end) in VARIANTS.items():
        sc = L.run_scalar(initial, config, [D0, D1], cmds, end)
        na = L.run_native(PORT, config, cmds, end, rich=True)
        res["variants"][name] = {"commands": cmds, "scalar_rejected": sc["rejected"],
                                 "native_receipts": na["receipts"],
                                 "scalar": trajectory(sc["frames"]), "native": trajectory(na["frames"])}
        v = res["variants"][name]
        print(name, "scalar final", v["scalar"]["final"], v["scalar"]["alive_at_end"],
              "| native final", v["native"]["final"], v["native"]["alive_at_end"], flush=True)
    res["provenance"] = L.provenance()
    L.dump("s2_shield.json", res)


if __name__ == "__main__":
    main()
