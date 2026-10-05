"""Scenario 3: Hog Rider body-blocked by three Skeletons (native vs scalar).

Owner-1 Hog at the left bridge (3.5,17.5) at tick 100 runs at the owner-0 left
Princess Tower. Owner-0 Skeletons are dropped in its path with different
timings/offsets. Identical static commands on both engines.
Measured: Hog trajectory and target per tick, first Hog hit on the tower,
number of Hog tower hits until the Hog dies, skeleton lifetimes.

Usage: s3_hog_skeletons.py <emulator-serial>
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nm_lib as L  # noqa: E402

SERIAL = sys.argv[1] if len(sys.argv) > 1 else "emulator-5580"
PORT = L.PORTS[SERIAL]
D0 = ["Skeletons", "Knight", "Fireball", "Zap", "Giant", "Musketeer", "Cannon", "Arrows"]
D1 = ["HogRider", "Knight", "Log", "IceSpirit", "Giant", "IceGolem", "Tesla", "DarkPrince"]
HOG = {"tick": 100, "owner": 1, "card": "HogRider", "xy": (3.5, 17.5)}
END = 600
VARIANTS = {
    "unblocked": [HOG],
    "skel_path_y11.5_t140": [HOG, {"tick": 140, "owner": 0, "card": "Skeletons", "xy": (3.5, 11.5)}],
    "skel_path_y12.5_t150": [HOG, {"tick": 150, "owner": 0, "card": "Skeletons", "xy": (3.5, 12.5)}],
    "skel_early_y10.5_t120": [HOG, {"tick": 120, "owner": 0, "card": "Skeletons", "xy": (3.5, 10.5)}],
    "skel_offset_x4.5_y11.5_t140": [HOG, {"tick": 140, "owner": 0, "card": "Skeletons", "xy": (4.5, 11.5)}],
}
TOWER_XY = (3500, 6500)


def summarize(frames):
    hog_rows, skel, tower_hp, targets = [], {}, [], []
    for f in frames:
        tower = next((o for o in f["objects"] if o.get("hp") is not None and o["owner"] == 0
                      and (o["x"], o["y"]) == TOWER_XY), None)
        tower_hp.append([f["tick"], tower["hp"] if tower else 0])
        for o in f["objects"]:
            if o["name"] == "HogRider":
                hog_rows.append([f["tick"], o["x"], o["y"], o["hp"], o.get("target")])
            elif o["name"] == "Skeletons":
                skel.setdefault(o["id"], []).append([f["tick"], o["x"], o["y"], o["hp"]])
    hits = [(tower_hp[i][0], tower_hp[i - 1][1] - tower_hp[i][1]) for i in range(1, len(tower_hp))
            if tower_hp[i][1] < tower_hp[i - 1][1]]
    hog_death = hog_rows[-1][0] if hog_rows and hog_rows[-1][0] < frames[-1]["tick"] else None
    targets = sorted({r[4] for r in hog_rows if r[4] is not None})
    return {"hog": hog_rows, "hog_death_tick": hog_death, "tower_hits": hits,
            "first_tower_hit_tick": hits[0][0] if hits else None, "n_tower_hits": len(hits),
            "tower_damage": sum(h for _, h in hits), "hog_target_ids": targets,
            "skeleton_last_tick": {k: v[-1][0] for k, v in skel.items()},
            "skeletons": skel}


def main():
    assert L.free_gib() > 8
    seed, config, initial = L.find_seed(PORT, D0, D1, need0=("Skeletons",), need1=("HogRider",))
    res = {"scenario": "hog_vs_three_skeletons", "serial": SERIAL, "seed": seed, "config": config,
           "variants": {}}
    for name, cmds in VARIANTS.items():
        sc = L.run_scalar(initial, config, [D0, D1], cmds, END)
        na = L.run_native(PORT, config, cmds, END, rich=True)
        v = {"commands": cmds, "scalar_rejected": sc["rejected"], "native_receipts": na["receipts"],
             "scalar": summarize(sc["frames"]), "native": summarize(na["frames"])}
        res["variants"][name] = v
        for eng in ("scalar", "native"):
            s = v[eng]
            print(name, eng, "first hit", s["first_tower_hit_tick"], "hits", s["n_tower_hits"],
                  "dmg", s["tower_damage"], "hog death", s["hog_death_tick"], "targets", s["hog_target_ids"],
                  "skel last", sorted(s["skeleton_last_tick"].values()), flush=True)
    res["provenance"] = L.provenance()
    L.dump("s3_hog_skeletons.json", res)


if __name__ == "__main__":
    main()
