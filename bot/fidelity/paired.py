"""Paired per-fixture comparison of two engines: python -m bot.fidelity.paired OUT_DIR A B"""
import json
import random
import sys
from pathlib import Path

out, A, B = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
ra = {p.stem: json.loads(p.read_text()) for p in (out / A).glob("*.json")}
rb = {p.stem: json.loads(p.read_text()) for p in (out / B).glob("*.json")}
eps = sorted(set(ra) & set(rb))
def f(r, k="w250"):
    x = r["no_towers"]
    return 100.0 * x[k] / x["unit_ticks"] if x["unit_ticks"] else None
for k in ("w250", "hp_exact"):
    d = [f(rb[e], k) - f(ra[e], k) for e in eps if f(ra[e], k) is not None and f(rb[e], k) is not None]
    rng = random.Random(0)
    bs = sorted(sum(rng.choice(d) for _ in d) / len(d) for _ in range(2000))
    wins = sum(1 for x in d if x > 0)
    print(f"{k}: {B} - {A} per-fixture mean {sum(d)/len(d):+.1f} pp [{bs[50]:+.1f}, {bs[1949]:+.1f}], {B} better in {wins}/{len(d)} fixtures")
