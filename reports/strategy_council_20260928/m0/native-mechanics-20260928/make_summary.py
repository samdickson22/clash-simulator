"""Recompute the per-scenario verdict numbers from the recorded JSON files."""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(name):
    return json.loads((HERE / name).read_text())


def per_tick_max_diff(a_rows, b_rows, cols=(1, 2)):
    a = {r[0]: r for r in a_rows}
    b = {r[0]: r for r in b_rows}
    common = sorted(set(a) & set(b))
    return (max((max(abs(a[t][c] - b[t][c]) for c in cols) for t in common), default=None), len(common))


def main():
    out = {}
    pre = load("s1b_zap_sweep_pre_repair.json")
    post = load("s1b_zap_sweep_models_only.json")
    post_by = {r["zap_cast_tick"]: r["current"]["first_shot"] for r in post["rows"]}
    rows = []
    for r in pre["rows"]:
        n = r["native"]["first_shot"]
        rows.append({"zap_cast_tick": r["zap_cast_tick"], "native": n,
                     "scalar_pre_repair": r["current"]["first_shot"],
                     "scalar_post_repair": post_by[r["zap_cast_tick"]],
                     "triage_T1": r["T1"]["first_shot"]})
    err = lambda k: [x[k] - x["native"] for x in rows]  # noqa: E731
    ice_pre = load("s1c_icespirit_freeze_pre_repair.json")["variants"]["ice_f1_x6.5"]
    ice_post = load("s1c_icespirit_freeze.json")["variants"]["ice_f1_x6.5"]
    out["1_king_wakeup_stun"] = {
        "native_control_first_shot_after_activation_ticks": 80,
        "zap_sweep": rows,
        "max_abs_error_ticks": {"pre_repair": max(map(abs, err("scalar_pre_repair"))),
                                "post_repair": max(map(abs, err("scalar_post_repair"))),
                                "triage_T1": max(map(abs, err("triage_T1")))},
        "ice_spirit_freeze_end_of_wake_up": {"native": ice_pre["native"]["first_shot"]["tick"],
                                             "scalar_pre_repair": ice_pre["current"]["first_shot"]["tick"],
                                             "scalar_post_repair": ice_post["current"]["first_shot"]["tick"],
                                             "triage_T1": ice_pre["T1"]["first_shot"]["tick"],
                                             "control_native": 748},
        "verdict_pre_repair": "consequential/systematic: every Zap in the first 3.3 s of a King wake-up delayed the scalar first shot by 10-11 ticks (0.5-0.55 s) where native adds none",
        "verdict_post_repair": "small dynamics difference: <=4 ticks (0.2 s) in the last 0.7 s; exact (+/-1 baseline) elsewhere; Ice Spirit case exact",
    }
    s2 = load("s2_shield.json")["variants"]
    out["2_shield"] = {}
    for name, v in s2.items():
        rec = {}
        for unit in v["native"]["rows"]:
            d, n = per_tick_max_diff(v["native"]["rows"][unit], v["scalar"]["rows"][unit], cols=(1, 2, 3))
            rec[unit] = {"max_abs_diff_xy_hp": d, "ticks": n,
                         "native_events": [(e["tick"], e["hp"], e["shield"]) for e in v["native"]["events"][unit]],
                         "scalar_events": [(e["tick"], e["hp"], e["shield"]) for e in v["scalar"]["events"][unit]]}
        out["2_shield"][name] = rec
    out["2_shield"]["verdict"] = ("match: breaking hit fully absorbed natively (no spill into HP), Knight dies at tick 319 "
                                  "with the Dark Prince on 190 HP in both; only Fireball contact is 1 tick earlier in scalar")
    s3 = load("s3_hog_skeletons.json")["variants"]
    out["3_hog_skeletons"] = {}
    for name, v in s3.items():
        d, n = per_tick_max_diff(v["native"]["hog"], v["scalar"]["hog"], cols=(1, 2, 3))
        out["3_hog_skeletons"][name] = {
            "hog_max_abs_diff_xy_hp": d, "ticks": n,
            **{f"{eng}_{k}": v[eng][k] for eng in ("native", "scalar")
               for k in ("first_tower_hit_tick", "n_tower_hits", "tower_damage", "hog_death_tick")}}
    out["3_hog_skeletons"]["verdict"] = "match: tick-exact Hog path/HP, hits (7 unblocked, 2 blocked), no retarget in either"
    s4 = load("s4_log_pushback.json")["cases"]
    out["4_log_pushback"] = {}
    for unit, c in s4.items():
        d, n = per_tick_max_diff(c["log"]["native"], c["log"]["scalar"], cols=(1, 2, 3))
        out["4_log_pushback"][unit] = {"max_abs_diff_xy_hp": d, "ticks": n,
                                       **{f"{e}_{k}": c["summary"][e][k] for e in ("native", "scalar")
                                          for k in ("max_dy_mm", "final_dy_mm", "first_push_tick", "log_damage")}}
    out["4_log_pushback"]["verdict"] = "match: tick-exact pushback on Giant, Ice Golem and Hog"
    s5 = load("s5_lane_after_tower.json")["variants"]
    out["5_lane_after_tower"] = {}
    for name, v in s5.items():
        units = {}
        for (kn, un), (ks, us) in zip(sorted(v["native"]["units"].items(), key=lambda x: x[1]["first"][0]),
                                      sorted(v["scalar"]["units"].items(), key=lambda x: x[1]["first"][0])):
            d, n = per_tick_max_diff(un["path_every_10"], us["path_every_10"])
            units[kn.split("@")[0]] = {"native_targets": [t for _, t in un["target_sequence"]],
                                       "scalar_targets": [t for _, t in us["target_sequence"]],
                                       "path_max_abs_diff_mm_10tick": d}
        out["5_lane_after_tower"][name] = {"fall": [v["native"]["fall_tick"], v["scalar"]["fall_tick"]],
                                           "king_first_shot": [v["native"]["king_first_shot"],
                                                               v["scalar"]["king_first_shot"]],
                                           "units": units, "scalar_rejected": v["scalar_rejected"]}
    out["5_lane_after_tower"]["verdict"] = ("match: identical fall ticks, targets and paths; lane/pocket units go to the King, "
                                            "a Hog at x=8.5 goes to the surviving Princess in both. Side note: native "
                                            "snaps an out-of-zone pocket placement (y=10.5) to y=11.5; scalar rejects it")
    (HERE / "summary.json").write_text(json.dumps(out, indent=1, default=str) + "\n")
    print(json.dumps({k: v.get("verdict", v.get("verdict_post_repair")) for k, v in out.items()}, indent=1))
    print(out["1_king_wakeup_stun"]["max_abs_error_ticks"], out["1_king_wakeup_stun"]["ice_spirit_freeze_end_of_wake_up"])


if __name__ == "__main__":
    main()
