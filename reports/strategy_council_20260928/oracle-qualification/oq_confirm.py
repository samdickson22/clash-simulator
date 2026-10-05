"""Pre-registered analysis of the 256-game confirmation (see PROGRESS.md PRE-REGISTRATION).

Plain python3. Writes confirm256.json and prints markdown.
"""

from __future__ import annotations

import json
from collections import defaultdict

import oq_report as R

PLAYER = "srp_xm_c256"
REF = "ckpt2903"
CELLS = {
    "holdout": {"balanced": (70000019, 86), "pressure": (71000022, 86), "defense": (72000025, 84)},
    "hog26": {"balanced": (73000028, 22), "pressure": (74000031, 22), "defense": (75000034, 20)},
}


def load(player):
    out = {}
    for path in (R.OQ / "games" / player).glob("*.json"):
        if path.name.endswith(".error.json"):
            continue
        r = json.loads(path.read_text())
        s = r["spec"]
        out[(s["role"], s["opponent"], s["seed"], s["game"])] = r
    return out


def complete_prefix(recs, role):
    """Largest even k such that games 0..k-1 exist in every cell of the role (capped at plan)."""
    ks = []
    for style, (seed, n) in CELLS[role].items():
        k = 0
        while k < n and (role, style, seed, k) in recs:
            k += 1
        ks.append(k)
    return ks


def main():
    P, F = load(PLAYER), load(REF)
    result = {}
    for role in ("holdout", "hog26"):
        ks = complete_prefix(P, role)
        planned = [n for _s, (_seed, n) in CELLS[role].items()]
        if ks == planned:
            use = planned
            note = "complete"
        else:
            # pre-registered cut rule: same 2k prefix in every cell
            k = min(ks) // 2 * 2
            use = [k] * 3
            note = f"incomplete: using games 0..{k - 1} per cell (completed per cell: {ks})"
        sel = {
            style: [P[(role, style, seed, g)] for g in range(n)]
            for (style, (seed, _)), n in zip(CELLS[role].items(), use)
        }
        allrecs = [r for v in sel.values() for r in v]
        if not allrecs:
            continue
        res = {"note": note, "cells": {}, "pooled": R.summarise(allrecs)}
        for style, recs in sel.items():
            res["cells"][style] = R.summarise(recs)
        # paired difference vs reference on identical games
        clusters = defaultdict(list)
        base = []
        for r in allrecs:
            s = r["spec"]
            key = (s["role"], s["opponent"], s["seed"], s["game"])
            if key in F:
                d = R.SCORE[r["outcome"]] - R.SCORE[F[key]["outcome"]]
                clusters[(s["opponent"], r["matchup_seed"])].append(d)
                base.append(R.SCORE[F[key]["outcome"]])
        if base:
            lo, hi = R.boot(list(clusters.values()))
            res["paired_vs_ckpt"] = {"n": len(base), "ckpt_score": sum(base) / len(base),
                                     "diff": sum(sum(c) for c in clusters.values()) / len(base),
                                     "diff_boot95": [lo, hi]}
        ref_recs = [F[k] for k in F if k[0] == role and k[2] == CELLS[role][k[1]][0]] if F else []
        if ref_recs:
            res["ckpt_alone"] = R.summarise(ref_recs)
        if role == "holdout":
            pooled, dfn = res["pooled"], res["cells"]["defense"]
            a = pooled["score"] >= 0.55 and pooled["score_boot95"][0] > 0.5
            b = dfn["score"] >= 0.55 and dfn["score_boot95"][0] > 0.5
            res["verdict"] = {"pooled_ok": a, "defense_ok": b, "PASS": bool(a and b),
                              "analysed_games": len(allrecs)}
        result[role] = res
        print(f"\n### {role} ({note})\n")
        print("| cell | n | W-D-L | score | score 95% (matchup bootstrap) | win rate 95% (Wilson) | crown diff |")
        print("|---|---|---|---|---|---|---|")
        for style, s in res["cells"].items():
            print(f"| {style} | {s['n']} | {R.fmt(s)} |")
        s = res["pooled"]
        print(f"| pooled | {s['n']} | {R.fmt(s)} |")
        if "paired_vs_ckpt" in res:
            p = res["paired_vs_ckpt"]
            print(f"\npaired vs seed-2903 1M checkpoint on the same games (n={p['n']}): checkpoint score "
                  f"{p['ckpt_score']:.3f}, difference {p['diff']:+.3f} [{p['diff_boot95'][0]:+.3f}, {p['diff_boot95'][1]:+.3f}]")
        if "verdict" in res:
            print(f"\nverdict: {res['verdict']}")
        c = res["pooled"]
        print(f"cost: {c['planner_calls_per_game']:.0f} calls/game, {c['planner_cpu_seconds_per_call']:.2f} core-s/call, "
              f"{c['cpu_seconds_per_game']:.0f} core-s/game")
    (R.OQ / "confirm256.json").write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
