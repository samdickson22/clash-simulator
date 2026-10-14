"""Aggregate per-fixture fidelity JSONs into overall and per-card tables.

    python -m bot.fidelity.aggregate OUT_DIR [--engines a,b] [--split train|validation|all] [--md FILE]

Fixture-level 95% intervals come from a percentile bootstrap over fixtures (2000 draws,
seed 0): unit-ticks within a battle are not independent, battles are.
"""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

from .score import add_rows

COLS = [("w250", "≤¼ tile"), ("w1000", "≤1 tile"), ("hp_exact", "HP exact"), ("alive_mismatch", "alive mismatch")]


def load(out: Path, engine: str, split: str):
    rs = []
    for p in sorted((out / engine).glob("*.json")):
        r = json.loads(p.read_text())
        if split == "all" or r["split"] == split:
            rs.append(r)
    return rs


def frac(rows, num, den="unit_ticks"):
    n = sum(r[num] for r in rows)
    d = sum(r[den] for r in rows)
    return 100.0 * n / d if d else float("nan")


def boot(rows, num, den="unit_ticks", draws=2000, seed=0):
    rng = random.Random(seed)
    k = len(rows)
    vals = []
    for _ in range(draws):
        s = [rows[rng.randrange(k)] for _ in range(k)]
        vals.append(frac(s, num, den))
    vals.sort()
    return vals[int(0.025 * draws)], vals[int(0.975 * draws) - 1]


def with_towers(r):
    return add_rows(dict(r["towers"]), r["no_towers"])


def summarize(rs):
    out = {}
    views = {"all units (with towers)": [with_towers(r) for r in rs], "no towers": [r["no_towers"] for r in rs]}
    for name, rows in views.items():
        d = {"unit_ticks": sum(x["unit_ticks"] for x in rows)}
        for col, _ in COLS:
            d[col] = (frac(rows, col), boot(rows, col))
        d["moving_w250"] = (frac(rows, "moving_w250", "moving_ticks"), boot(rows, "moving_w250", "moving_ticks"))
        d["early_w250"] = (frac(rows, "early_w250", "early_ticks"), boot(rows, "early_w250", "early_ticks"))
        d["early_hp_exact"] = (frac(rows, "early_hp_exact", "early_ticks"), boot(rows, "early_hp_exact", "early_ticks"))
        out[name] = d
    per_card = defaultdict(list)
    for r in rs:
        for c, row in r["per_card"].items():
            per_card[c].append(row)
    out["per_card"] = {c: {"fixtures": len(v), "unit_ticks": sum(x["unit_ticks"] for x in v),
                           **{col: frac(v, col) for col, _ in COLS},
                           "early_w250": frac(v, "early_w250", "early_ticks")} for c, v in per_card.items()}
    out["fixtures"] = len(rs)
    out["winner_agrees"] = sum(1 for r in rs if r.get("winner_agrees"))
    out["crowns_equal"] = sum(1 for r in rs if r.get("crowns_equal"))
    out["engine_ended_early"] = sum(1 for r in rs if r["deploy"].get("engine_game_end_tick"))
    out["deploys"] = {k: sum(r["deploy"].get(k, 0) for r in rs) for k in ("issued", "retried", "dropped")}
    counters = defaultdict(int)
    for r in rs:
        for k, v in r["counters"].items():
            counters[k] += v
    out["counters"] = dict(counters)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--engines", default="")
    ap.add_argument("--split", default="all")
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    out = Path(a.out)
    engines = a.engines.split(",") if a.engines else sorted(p.name for p in out.iterdir() if p.is_dir())
    res = {}
    for e in engines:
        rs = load(out, e, a.split)
        if not rs:
            continue
        res[e] = summarize(rs)
        s = res[e]
        print(f"== {e}: {s['fixtures']} fixtures, winner agrees {s['winner_agrees']}, crowns equal {s['crowns_equal']}, engine ended early in {s['engine_ended_early']}, deploys {s['deploys']}, counters {s['counters']}")
        for view in ("all units (with towers)", "no towers"):
            d = s[view]
            cells = "  ".join(f"{lab} {d[c][0]:.1f} [{d[c][1][0]:.1f},{d[c][1][1]:.1f}]" for c, lab in COLS)
            print(f"  {view:24s} ut={d['unit_ticks']:>9d}  {cells}  early≤¼ {d['early_w250'][0]:.1f}  earlyHP {d['early_hp_exact'][0]:.1f}")
    if a.json:
        Path(a.json).write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
