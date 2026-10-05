"""Scenario 4: Log pushback on Giant, Ice Golem and Hog Rider (native vs scalar).

Owner-1 unit at the left bridge (3.5,17.5) at tick 100 walks toward the owner-0
left Princess Tower. Owner-0 casts the Log at (3.5, 9.5) (it rolls toward +y)
at a fixed tick chosen once from the scalar control run (tick at which the unit
first reaches y <= 13.0). The same static commands run on both engines, plus a
no-Log control on both engines. Measured: per-tick unit position; displacement
versus the same engine's control at matching ticks; Log damage.

Usage: s4_log_pushback.py <emulator-serial>
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nm_lib as L  # noqa: E402

SERIAL = sys.argv[1] if len(sys.argv) > 1 else "emulator-5580"
PORT = L.PORTS[SERIAL]
D0 = ["Log", "Knight", "Fireball", "Zap", "Giant", "Musketeer", "Cannon", "Arrows"]
D1 = ["Giant", "IceGolem", "HogRider", "Knight", "IceSpirit", "Tesla", "DarkPrince", "Skeletons"]
UNITS = {"Giant": "Giant", "IceGolem": "IceGolemite", "HogRider": "HogRider"}
END_AFTER_LOG = 80


def unit_rows(frames, scalar_name):
    rows = []
    for f in frames:
        for o in f["objects"]:
            if o["name"] in (scalar_name, "IceGolem" if scalar_name == "IceGolemite" else scalar_name):
                rows.append([f["tick"], o["x"], o["y"], o["hp"], o.get("target")])
    return rows


def main():
    assert L.free_gib() > 8
    res = {"scenario": "log_pushback", "serial": SERIAL, "cases": {}}
    for unit, sname in UNITS.items():
        seed, config, initial = L.find_seed(PORT, D0, D1, need0=("Log",), need1=(unit,))
        deploy = {"tick": 100, "owner": 1, "card": unit, "xy": (3.5, 17.5)}
        ctrl_plan = L.run_scalar(initial, config, [D0, D1], [deploy], 700)
        rows = unit_rows(ctrl_plan["frames"], sname)
        log_tick = next(r[0] for r in rows if r[2] <= 13000)
        end = log_tick + END_AFTER_LOG
        log = {"tick": log_tick, "owner": 0, "card": "Log", "xy": (3.5, 9.5)}
        case = {"seed": seed, "config": config, "log_command": log, "deploy": deploy}
        for variant, cmds in (("control", [deploy]), ("log", [deploy, log])):
            sc = L.run_scalar(initial, config, [D0, D1], cmds, end)
            na = L.run_native(PORT, config, cmds, end, rich=True)
            case[variant] = {"scalar_rejected": sc["rejected"], "native_receipts": na["receipts"],
                             "scalar": unit_rows(sc["frames"], sname),
                             "native": unit_rows(na["frames"], sname)}
        summary = {}
        for eng in ("scalar", "native"):
            c = {r[0]: r for r in case["control"][eng]}
            lg = {r[0]: r for r in case["log"][eng]}
            ticks = [t for t in sorted(lg) if t >= log_tick and t in c]
            disp = [[t, lg[t][1] - c[t][1], lg[t][2] - c[t][2]] for t in ticks]
            hp_loss = [c[t][3] - lg[t][3] for t in ticks]
            summary[eng] = {"displacement_mm": disp,
                            "max_dy_mm": max((d[2] for d in disp), default=None),
                            "final_dy_mm": disp[-1][2] if disp else None,
                            "first_push_tick": next((d[0] for d in disp if abs(d[2]) > 0 or abs(d[1]) > 0), None),
                            "log_damage": max(hp_loss) if hp_loss else None}
        case["summary"] = summary
        res["cases"][unit] = case
        print(unit, "log tick", log_tick, {e: {k: v for k, v in s.items() if k != "displacement_mm"}
                                           for e, s in summary.items()}, flush=True)
    res["provenance"] = L.provenance()
    L.dump("s4_log_pushback.json", res)


if __name__ == "__main__":
    main()
