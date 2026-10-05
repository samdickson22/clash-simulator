"""Compare digest lists of two es_pure result files: identical => bit-identical trajectories."""
import json, sys
from es_common import RESULTS
a, b = (json.load(open(RESULTS / f"pure_{x}.json")) for x in sys.argv[1:3])
ok = True
for i, (ma, mb) in enumerate(zip(a["matches"], b["matches"])):
    da, db = ma["digests"], mb["digests"]
    first = next((j for j, (x, y) in enumerate(zip(da, db)) if x != y), None)
    same = first is None and len(da) == len(db) and ma.get("final_digest") == mb.get("final_digest")
    ok &= same
    print(f"match {i}: {'IDENTICAL' if same else f'DIVERGES at digest {first} of {len(da)}/{len(db)}'}")
print("ALL IDENTICAL" if ok else "MISMATCH",
      f"| step-only t/s cpu {a['step_only_ticks_per_s_cpu']:.0f} vs {b['step_only_ticks_per_s_cpu']:.0f}"
      f" ({b['step_only_ticks_per_s_cpu']/a['step_only_ticks_per_s_cpu']:.2f}x)")
