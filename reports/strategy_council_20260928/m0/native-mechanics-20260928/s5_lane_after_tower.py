"""Scenario 5: lane choice after a Princess Tower falls (native vs scalar).

Prefix (identical static commands): owner-1 Giant (3.5,17.5) at tick 100 and Hog
(3.5,17.5) at tick 170 destroy the owner-0 left Princess Tower unopposed.
Then, per engine, 20 ticks after that engine's own tower-destruction tick (and
once elixir suffices), owner 1 deploys one test unit. Variants cover Knight,
Giant and Hog in the lane, at a centre-left spot, in the pocket, and an Ice
Spirit in the pocket that jumps on the waking King (freeze during wake-up).
Measured: tower fall tick, King activation/first shot, every owner-1 unit's
target label sequence and path.

Usage: s5_lane_after_tower.py <emulator-serial> [variant ...]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nm_lib as L  # noqa: E402

SERIAL = sys.argv[1] if len(sys.argv) > 1 else "emulator-5582"
PORT = L.PORTS[SERIAL]
ONLY = set(sys.argv[2:])
D0 = ["Skeletons", "Knight", "Fireball", "Zap", "Giant", "Musketeer", "Cannon", "Arrows"]
D1 = ["Giant", "HogRider", "Knight", "IceSpirit", "Log", "IceGolem", "Tesla", "DarkPrince"]
PREFIX = [{"tick": 100, "owner": 1, "card": "Giant", "xy": (3.5, 17.5)},
          {"tick": 170, "owner": 1, "card": "HogRider", "xy": (3.5, 17.5)}]
# Giant/Hog test cards cannot be replayed from hand right after the prefix used
# them, so those variants destroy the tower with a different pair.
PREFIX_FOR = {
    "Giant": [{"tick": 100, "owner": 1, "card": "IceGolem", "xy": (3.5, 17.5)},
              {"tick": 104, "owner": 1, "card": "HogRider", "xy": (3.5, 17.5)},
              {"tick": 280, "owner": 1, "card": "DarkPrince", "xy": (3.5, 17.5)}],
    "HogRider": [{"tick": 100, "owner": 1, "card": "Giant", "xy": (3.5, 17.5)},
                 {"tick": 230, "owner": 1, "card": "DarkPrince", "xy": (3.5, 17.5)}],
}
COST = {"Knight": 3, "Giant": 5, "HogRider": 4, "IceSpirit": 1}
VARIANTS = {
    "none": None,
    "knight_lane": ("Knight", (3.5, 17.5)),
    "giant_lane": ("Giant", (3.5, 17.5)),
    "hog_lane": ("HogRider", (3.5, 17.5)),
    "knight_centre": ("Knight", (8.5, 17.5)),
    "hog_centre": ("HogRider", (8.5, 17.5)),
    "giant_centre": ("Giant", (8.5, 17.5)),
    "knight_pocket": ("Knight", (3.5, 12.5)),
    "hog_pocket": ("HogRider", (4.5, 12.5)),
    "icespirit_pocket": ("IceSpirit", (5.5, 11.5)),
    "icespirit_pocket_early": ("IceSpirit", (6.5, 10.5), 1),
    "icespirit_pocket_early_b": ("IceSpirit", (8.5, 10.5), 1),
}
TOWER = (3500, 6500)
END_AFTER = 360


def label_map(frames):
    labels = {}
    names = {(9000, 3000): "King0", (3500, 6500): "PrincessL0", (14500, 6500): "PrincessR0",
             (9000, 29000): "King1", (3500, 25500): "PrincessL1", (14500, 25500): "PrincessR1"}
    for f in frames:
        for o in f["objects"]:
            if o["id"] in labels:
                continue
            if (o.get("hp") is not None and (o["x"], o["y"]) in names
                    and (o["name"] == "tower" or "Tower" in o["name"])):
                labels[o["id"]] = names[(o["x"], o["y"])]
            else:
                labels[o["id"]] = f"{o['name']}#{o['owner']}"
    return labels


def summarize(frames):
    labels = label_map(frames)
    fall = None
    king_prev, activation, first_shot = None, None, None
    seen = set()
    units = {}
    for f in frames:
        objs = f["objects"]
        tower = next((o for o in objs if o.get("hp") is not None and o["owner"] == 0 and (o["x"], o["y"]) == TOWER), None)
        if (tower is None or tower["hp"] <= 0) and fall is None and f["tick"] > 0:
            fall = f["tick"]
        king = next((o for o in objs if o.get("hp") is not None and o["owner"] == 0 and (o["x"], o["y"]) == (9000, 3000)), None)
        for o in objs:
            if o["id"] not in seen:
                seen.add(o["id"])
                src = o.get("source", o.get("source_id"))
                if king is not None and src == king["id"] and first_shot is None:
                    first_shot = {"tick": f["tick"], "target": labels.get(o.get("target"), o.get("target"))}
            if o["owner"] == 1 and o["name"] in ("Giant", "HogRider", "Knight", "IceSpirits", "IceSpirit"):
                units.setdefault(f"{o['name']}@{o['id']}", []).append(
                    [f["tick"], o["x"], o["y"], o["hp"], labels.get(o.get("target"), o.get("target"))])
        if king is not None:
            if king_prev is not None and king["hp"] < king_prev and activation is None:
                activation = f["tick"]
            king_prev = king["hp"]
    out = {"fall_tick": fall, "king_first_hp_loss": activation, "king_first_shot": first_shot, "units": {}}
    for key, rows in units.items():
        seq = []
        for r in rows:
            if r[4] is not None and (not seq or seq[-1][1] != r[4]):
                seq.append([r[0], r[4]])
        out["units"][key] = {"first": rows[0], "last": rows[-1], "target_sequence": seq,
                             "path_every_10": rows[::10]}
    return out


def make_policy(test, state):
    def policy(engine, tick, frame):
        st = state.setdefault(engine, {"fall": None, "done": False})
        if frame is None or test is None or st["done"]:
            return []
        tower = next((o for o in frame["objects"] if o.get("hp") is not None and o["owner"] == 0
                      and (o["x"], o["y"]) == TOWER), None)
        if st["fall"] is None and (tower is None or tower["hp"] <= 0) and tick > 0:
            st["fall"] = tick
        delay = test[2] if len(test) > 2 else 20
        if st["fall"] is not None and tick >= st["fall"] + delay:
            p1 = next(p for p in frame["players"] if p["owner"] == 1)
            card, xy = test[:2]
            if p1["elixir"] >= COST[card]:
                st["done"] = True
                st["tick"] = tick
                return [{"tick": tick, "owner": 1, "card": card, "xy": xy}]
        return []
    return policy


def main():
    assert L.free_gib() > 8
    res = {"scenario": "lane_choice_after_princess_falls", "serial": SERIAL, "variants": {}}
    for name, test in VARIANTS.items():
        if ONLY and name not in ONLY:
            continue
        prefix = PREFIX_FOR.get(test[0], PREFIX) if test else PREFIX
        need = sorted({c["card"] for c in prefix if c["tick"] < 110} | ({test[0]} if test else set()))
        seed, config, initial = L.find_seed(PORT, D0, D1, need1=tuple(need))
        # the Giant/Hog test cards need a second copy in hand: they cycle back after 4 plays.
        state = {}
        sc = L.run_scalar(initial, config, [D0, D1], prefix, 900,
                          policy=make_policy(test, state))
        na = L.run_native(PORT, config, prefix, 900, rich=True,
                          policy=make_policy(test, state))
        v = {"seed": seed, "test": test, "prefix": prefix, "policy_state": state,
             "scalar_rejected": sc["rejected"], "scalar_issued": sc["issued"],
             "native_receipts": na["receipts"],
             "scalar": summarize(sc["frames"]), "native": summarize(na["frames"])}
        res["variants"][name] = v
        for eng in ("scalar", "native"):
            s = v[eng]
            print(name, eng, "fall", s["fall_tick"], "king hp-loss", s["king_first_hp_loss"], "first shot", s["king_first_shot"],
                  {k: u["target_sequence"] for k, u in s["units"].items()}, flush=True)
        L.dump("s5_lane_after_tower.json" if not ONLY else f"s5_lane_after_tower_part_{SERIAL}.json", res)
    res["provenance"] = L.provenance()
    L.dump("s5_lane_after_tower.json" if not ONLY else f"s5_lane_after_tower_part_{SERIAL}.json", res)


if __name__ == "__main__":
    main()
