"""Print the per-card markdown table from aggregate JSON: python -m bot.fidelity.percard_table AGG.json [min_unit_ticks]"""
import json
import sys

a = json.load(open(sys.argv[1]))
mn = int(sys.argv[2]) if len(sys.argv) > 2 else 2000
E = ["clasher", "rsim15535", "rsim16402"]
cards = sorted(a["clasher"]["per_card"], key=lambda c: -a["clasher"]["per_card"][c]["unit_ticks"])
print("| card | fixtures | unit-ticks (ours) | ours ≤¼ tile | RS 15.535 ≤¼ | RS 16.402 ≤¼ | ours HP exact | RS 15.535 HP exact | RS 16.402 HP exact | ours first-5 s ≤¼ | RS 15.535 first-5 s ≤¼ |")
print("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
for c in cards:
    r = [a[e]["per_card"].get(c) for e in E]
    if r[0]["unit_ticks"] < mn:
        continue
    f = lambda x, k: "%.1f" % x[k] if x else "-"
    print(f"| {c} | {r[0]['fixtures']} | {r[0]['unit_ticks']} | {f(r[0],'w250')} | {f(r[1],'w250')} | {f(r[2],'w250')} | "
          f"{f(r[0],'hp_exact')} | {f(r[1],'hp_exact')} | {f(r[2],'hp_exact')} | {f(r[0],'early_w250')} | {f(r[1],'early_w250')} |")
