"""Scenario 1: King wake-up under Zap stun (native vs scalar).

Owner 1 (attacker) deploys a Hog Rider at the left bridge; the Hog attacks the
left owner-0 Princess Tower from a spot inside King range. A Fireball on the
dormant owner-0 King activates it shortly before the Hog arrives, so the King's
first shot is bounded by its wake-up clocks. Variants add a Zap on the King
during the wake-up window. All commands are identical on both engines (static
ticks). Measured: King activation tick (first King HP loss), King first-shot
tick (first new projectile/object owned by 0 born at the King, or first King
target HP damage), per engine and variant.

Usage: s1_king_wakeup_stun.py <emulator-serial>
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nm_lib as L  # noqa: E402

SERIAL = sys.argv[1] if len(sys.argv) > 1 else "emulator-5582"
PORT = L.PORTS[SERIAL]
D0 = ["Knight", "Giant", "Skeletons", "DarkPrince", "IceGolem", "Musketeer", "Cannon", "Arrows"]
D1 = ["HogRider", "Fireball", "Zap", "Knight", "Log", "IceSpirit", "DarkPrince", "Giant"]
END = 520

HOG_TICK = 250
FIREBALL_TICK = 250   # lands ~45 ticks later
VARIANTS = {
    "control": [],
    # Zap cast during the activation delay (King asleep -> waking)
    "zap_early": [{"tick": 305, "owner": 1, "card": "Zap", "xy": (9.0, 3.0)}],
    # Zap cast during the late part of the wake-up (first-hit phase region)
    "zap_late": [{"tick": 355, "owner": 1, "card": "Zap", "xy": (9.0, 3.0)}],
}
BASE = [
    {"tick": HOG_TICK, "owner": 1, "card": "HogRider", "xy": (3.5, 17.5)},
    {"tick": FIREBALL_TICK, "owner": 1, "card": "Fireball", "xy": (9.0, 3.0)},
]


def king_events(frames, engine):
    """Activation (first King HP drop), first King shot, and Zap/stun ticks."""
    out = {"activation_tick": None, "first_shot_tick": None, "first_shot_evidence": None,
           "king_hp": [], "hog": []}
    king_prev = None
    seen = set()
    for f in frames:
        objs = f["objects"]
        king = next((o for o in objs if o["owner"] == 0 and o["x"] == 9000 and o["y"] == 3000
                     and o.get("hp") is not None), None)
        if king is None:
            continue
        if king_prev is not None and king["hp"] < king_prev and out["activation_tick"] is None:
            out["activation_tick"] = f["tick"]
        king_prev = king["hp"]
        out["king_hp"].append([f["tick"], king["hp"]])
        hog = next((o for o in objs if o["name"] == "HogRider"), None)
        if hog:
            out["hog"].append([f["tick"], hog["x"], hog["y"], hog["hp"], hog.get("target")])
        for o in objs:
            if o["id"] in seen:
                continue
            seen.add(o["id"])
            src = o.get("source", o.get("source_id"))
            if src == king["id"] and out["first_shot_tick"] is None:
                out["first_shot_tick"] = f["tick"]
                out["first_shot_evidence"] = {k: o.get(k) for k in ("id", "name", "x", "y", "target")}
    return out


def main():
    assert L.free_gib() > 8
    seed, config, initial = L.find_seed(PORT, D0, D1, need1=("HogRider", "Fireball", "Zap"))
    results = {"scenario": "king_wakeup_stun", "serial": SERIAL, "seed": seed, "config": config,
               "initial_hands": {p["owner"]: [L.NAME_OF_ID.get(c["cardId"], c["cardId"]) for c in p["hand"]]
                                 for p in initial["players"]},
               "variants": {}}
    for name, extra in VARIANTS.items():
        cmds = BASE + extra
        sc = L.run_scalar(initial, config, [D0, D1], cmds, END)
        na = L.run_native(PORT, config, cmds, END, rich=True)
        results["variants"][name] = {
            "commands": cmds,
            "scalar_rejected": sc["rejected"],
            "native_receipts": na["receipts"],
            "scalar": king_events(sc["frames"], "scalar"),
            "native": king_events(na["frames"], "native"),
        }
        # compact trajectories of towers + Hog + projectiles near the King, ticks 280..END
        def compact(frames):
            rows = []
            for f in frames:
                if f["tick"] < 280:
                    continue
                rows.append([f["tick"], [
                    {k: o.get(k) for k in ("id", "owner", "name", "x", "y", "hp", "target", "stage",
                                            "timeline", "load", "stun_timer", "activation_delay_remaining",
                                            "activation_first_hit_delay_remaining",
                                            "_freeze_target_pause_remaining", "_tower_active")
                     if o.get(k) is not None}
                    for o in f["objects"]
                    if o["owner"] == 0 and o["y"] <= 9000 or o["name"] in ("HogRider", "Zap")]])
            return rows
        results["variants"][name]["scalar_trajectory"] = compact(sc["frames"])
        results["variants"][name]["native_trajectory"] = compact(na["frames"])
        s, n = results["variants"][name]["scalar"], results["variants"][name]["native"]
        print(name, "scalar act/shot", s["activation_tick"], s["first_shot_tick"],
              "native act/shot", n["activation_tick"], n["first_shot_tick"], flush=True)
    results["provenance"] = L.provenance()
    L.dump("s1_king_wakeup_stun.json", results)


if __name__ == "__main__":
    main()
