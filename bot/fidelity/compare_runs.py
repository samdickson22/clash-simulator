"""Compare two clasher harness runs and apply the calibration acceptance gate.

    python -m bot.fidelity.compare_runs BASE_OUT NEW_OUT [--split train] [--min-ut 8000] [--cards a,b]

Gate (reports/bot/calibration/BATCH1.md): no-tower ≤¼ tile and no-tower HP exact must not
decrease, and no card with ≥ min-ut unit-ticks (in BASE) may lose more than 1 pp on ≤¼ tile.
Per-fixture paired deltas are bootstrapped over fixtures (2000 draws, seed 0).
For each card that fails, the leave-one-fixture-out (LOO) delta is also printed: the card's
delta after removing the single fixture whose removal helps it most. A failure that vanishes
under LOO is one fixture's cascade (e.g. an earlier sudden-death crown freezing our state).
"""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path


def load(d: Path, engine: str, split: str, view: str = "standard") -> dict:
    out = {}
    for p in sorted((d / engine).glob("*.json")):
        r = json.loads(p.read_text())
        if split == "all" or r["split"] == split:
            if view == "live":  # score only ticks up to our battle's end (run.py "live")
                r["no_towers"], r["per_card"] = r["live"]["no_towers"], r["live"]["per_card"]
            out[p.stem] = r
    return out


def pct(rows, k):
    n = sum(r[k] for r in rows)
    d = sum(r["unit_ticks"] for r in rows)
    return 100.0 * n / d if d else float("nan")


def cards(rs: dict) -> dict:
    by = defaultdict(list)
    for r in rs.values():
        for c, row in r["per_card"].items():
            by[c].append(row)
    return {c: {"ut": sum(x["unit_ticks"] for x in v), "w250": pct(v, "w250"), "hp": pct(v, "hp_exact")}
            for c, v in by.items()}


def loo_delta(A: dict, B: dict, card: str) -> tuple[float, str]:
    """Best card ≤¼ delta after dropping one fixture from both runs, and that fixture."""
    rows = {e: (A[e]["per_card"].get(card), B[e]["per_card"].get(card)) for e in A}
    rows = {e: (x or {"unit_ticks": 0, "w250": 0}, y or {"unit_ticks": 0, "w250": 0})
            for e, (x, y) in rows.items() if x or y}
    na, da = sum(x["w250"] for x, _ in rows.values()), sum(x["unit_ticks"] for x, _ in rows.values())
    nb, db = sum(y["w250"] for _, y in rows.values()), sum(y["unit_ticks"] for _, y in rows.values())
    best = (-1e9, "")
    for e, (x, y) in rows.items():
        a_, b_ = da - x["unit_ticks"], db - y["unit_ticks"]
        if a_ and b_:
            d = 100.0 * (nb - y["w250"]) / b_ - 100.0 * (na - x["w250"]) / a_
            best = max(best, (d, e))
    return best


def paired(a: dict, b: dict, k: str):
    d = []
    for e in sorted(set(a) & set(b)):
        x, y = a[e]["no_towers"], b[e]["no_towers"]
        if x["unit_ticks"] and y["unit_ticks"]:
            d.append(100.0 * y[k] / y["unit_ticks"] - 100.0 * x[k] / x["unit_ticks"])
    rng = random.Random(0)
    bs = sorted(sum(rng.choice(d) for _ in d) / len(d) for _ in range(2000))
    return sum(d) / len(d), bs[50], bs[1949], sum(1 for x in d if x > 0), sum(1 for x in d if x < 0), len(d)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("new")
    ap.add_argument("--engine", default="clasher")
    ap.add_argument("--split", default="train")
    ap.add_argument("--min-ut", type=int, default=8000)
    ap.add_argument("--cards", default="", help="extra cards to always print")
    ap.add_argument("--json", default="")
    ap.add_argument("--view", default="standard", choices=["standard", "live"])
    a = ap.parse_args()
    A, B = load(Path(a.base), a.engine, a.split, a.view), load(Path(a.new), a.engine, a.split, a.view)
    assert set(A) == set(B), (len(A), len(B))
    res = {"split": a.split, "fixtures": len(A)}
    for view in ("no_towers", "towers"):
        ra, rb = [r[view] for r in A.values()], [r[view] for r in B.values()]
        res[view] = {k: (pct(ra, k), pct(rb, k)) for k in ("w250", "w1000", "hp_exact", "alive_mismatch")}
    res["paired_w250"] = paired(A, B, "w250")
    res["paired_hp"] = paired(A, B, "hp_exact")
    res["winner_agrees"] = (sum(r["winner_agrees"] for r in A.values()), sum(r["winner_agrees"] for r in B.values()))
    ca, cb = cards(A), cards(B)
    rows = []
    extra = set(filter(None, a.cards.split(",")))
    for c in sorted(ca, key=lambda c: -ca[c]["ut"]):
        n = cb.get(c, {"ut": 0, "w250": float("nan"), "hp": float("nan")})
        rows.append((c, ca[c]["ut"], n["ut"], ca[c]["w250"], n["w250"], ca[c]["hp"], n["hp"]))
    big = [r for r in rows if r[1] >= a.min_ut and r[0] != "Tower"]
    worst = min(big, key=lambda r: r[4] - r[3])
    regress = [r for r in big if r[4] - r[3] < -1.0]
    nt = res["no_towers"]
    ok = nt["w250"][1] >= nt["w250"][0] and nt["hp_exact"][1] >= nt["hp_exact"][0] and not regress
    res.update(worst=worst, regressions=regress, accept=ok)
    print(f"split={a.split} view={a.view} fixtures={len(A)}")
    for view in ("no_towers", "towers"):
        print(f"  {view:9s} " + "  ".join(f"{k} {x:.2f}->{y:.2f} ({y - x:+.2f})" for k, (x, y) in res[view].items()))
    m, lo, hi, w, l, n = res["paired_w250"]
    print(f"  paired no-tower ≤¼: {m:+.2f} pp [{lo:+.2f}, {hi:+.2f}], better {w} / worse {l} of {n}")
    m, lo, hi, w, l, n = res["paired_hp"]
    print(f"  paired no-tower HP: {m:+.2f} pp [{lo:+.2f}, {hi:+.2f}], better {w} / worse {l} of {n}")
    print(f"  winner agrees {res['winner_agrees'][0]} -> {res['winner_agrees'][1]}")
    print("  | card | ut base | ut new | ≤¼ base | ≤¼ new | Δ | HP base | HP new | Δ |")
    for r in rows:
        if r[1] >= a.min_ut or r[0] in extra or abs(r[4] - r[3]) >= 1.0 and r[1] >= 1000:
            print(f"  | {r[0]} | {r[1]} | {r[2]} | {r[3]:.1f} | {r[4]:.1f} | {r[4] - r[3]:+.1f} | {r[5]:.1f} | {r[6]:.1f} | {r[6] - r[5]:+.1f} |")
    print(f"  worst ≥{a.min_ut} card: {worst[0]} {worst[4] - worst[3]:+.2f} pp; regressions >1pp: {[r[0] for r in regress]}")
    res["loo"] = {}
    for r in regress:
        d, e = loo_delta(A, B, r[0])
        res["loo"][r[0]] = (d, e)
        print(f"  LOO {r[0]}: {d:+.2f} pp without {e} ({'one-fixture cascade' if d >= -1.0 else 'ROBUST regression'})")
    overall = nt["w250"][1] >= nt["w250"][0] and nt["hp_exact"][1] >= nt["hp_exact"][0]
    res["accept_loo"] = overall and all(d >= -1.0 for d, _ in res["loo"].values())
    print(f"  GATE: {'ACCEPT' if ok else 'REJECT'}   GATE-LOO: {'ACCEPT' if res['accept_loo'] else 'REJECT'}")
    if a.json:
        Path(a.json).write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
