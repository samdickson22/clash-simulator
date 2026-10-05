"""Scenario 1c: Ice Spirit freeze on a waking King (native vs scalar models).

Owner-1 Giant (3.5,17.5) at tick 100 destroys the owner-0 left Princess Tower,
which activates the owner-0 King. One tick (and, in other variants, several
ticks) after each engine's own destruction tick, owner 1 deploys an Ice Spirit
in the new pocket; it jumps on the King and freezes it at different points of
the wake-up. Scalar models: current / T1 / T2 / M (see s1b_zap_sweep.py and
README). Records the King first-shot tick and King rich timeline rows.

Usage: s1c_icespirit_freeze.py <emulator-serial>
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nm_lib as L  # noqa: E402
import s1b_zap_sweep as Z  # noqa: E402
import s5_lane_after_tower as F  # noqa: E402
from clasher.entities import Building  # noqa: E402

SERIAL = sys.argv[1] if len(sys.argv) > 1 else "emulator-5580"
PORT = L.PORTS[SERIAL]
PREFIX = [{"tick": 100, "owner": 1, "card": "Giant", "xy": (3.5, 17.5)}]
VARIANTS = {"none": None,
            "ice_f1_x6.5": ("IceSpirit", (6.5, 11.5), 1),
            "ice_f1_x3.5": ("IceSpirit", (3.5, 11.5), 1),
            "ice_f30_x6.5": ("IceSpirit", (6.5, 11.5), 30),
            "ice_f45_x6.5": ("IceSpirit", (6.5, 11.5), 45)}
END = 900


def hook_m(battle):
    for e in battle.entities.values():
        if getattr(e, "_is_king_tower", False):
            e.activation_delay_seconds = 3.55
            e.activation_first_hit_delay_seconds = 0.45


def main():
    assert L.free_gib() > 8
    seed, config, initial = L.find_seed(PORT, F.D0, F.D1, need1=("Giant", "IceSpirit"))
    res = {"scenario": "king_wakeup_icespirit_freeze", "serial": SERIAL, "seed": seed, "config": config,
           "prefix": PREFIX, "variants": {}}
    for name, test in VARIANTS.items():
        row = {"test": test}
        for model in ("current", "T1", "T2", "M"):
            Building._update_active_combat = Z.ORIGINAL if model == "current" else Z.make_patch(
                "T1" if model == "T1" else "T2")
            try:
                state = {}
                sc = L.run_scalar(initial, config, [F.D0, F.D1], PREFIX, END, policy=F.make_policy(test, state),
                                  battle_hook=hook_m if model == "M" else None)
            finally:
                Building._update_active_combat = Z.ORIGINAL
            s = F.summarize(sc["frames"])
            row[model] = {"fall": s["fall_tick"], "king_first_hp_loss": s["king_first_hp_loss"],
                          "first_shot": s["king_first_shot"], "issued": sc["issued"], "rejected": sc["rejected"],
                          "policy": state.get("scalar")}
        state = {}
        na = L.run_native(PORT, config, PREFIX, END, rich=True, policy=F.make_policy(test, state))
        s = F.summarize(na["frames"])
        king = []
        for f in na["frames"]:
            if s["fall_tick"] and s["fall_tick"] <= f["tick"] <= s["fall_tick"] + 120:
                k = next(o for o in f["objects"] if o["id"] == 5000000)
                king.append([f["tick"], k.get("target"), k.get("timeline"), k.get("load"), k["hp"], k.get("effects")])
        row["native"] = {"fall": s["fall_tick"], "king_first_hp_loss": s["king_first_hp_loss"],
                         "first_shot": s["king_first_shot"], "receipts": na["receipts"],
                         "policy": state.get("native"), "king_rich": king,
                         "units": s["units"]}
        res["variants"][name] = row
        print(name, "native", row["native"]["fall"], row["native"]["king_first_hp_loss"],
              row["native"]["first_shot"]["tick"] if row["native"]["first_shot"] else None,
              {m: (row[m]["king_first_hp_loss"], row[m]["first_shot"]["tick"] if row[m]["first_shot"] else None,
                   len(row[m]["rejected"])) for m in ("current", "T1", "T2", "M")}, flush=True)
    res["provenance"] = L.provenance()
    L.dump("s1c_icespirit_freeze.json", res)


if __name__ == "__main__":
    main()
