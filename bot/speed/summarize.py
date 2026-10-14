"""python -m bot.speed.summarize DIR : ticks/s and clone cost per engine (bootstrap 95% CI over fixtures)."""
import json
import random
import statistics
import sys
from pathlib import Path

d = Path(sys.argv[1])
for e in ("py", "rs", "rsim15535", "rsim16402"):
    p = d / f"bench-{e}.json"
    if not p.exists():
        continue
    rs = [r for r in json.loads(p.read_text()) if "error" not in r]
    errs = [r for r in json.loads(p.read_text()) if "error" in r]
    tps = lambda s: sum(r["ticks"] for r in s) / sum(r["step_s"] + r["deploy_s"] for r in s)
    rng = random.Random(0)
    bs = sorted(tps([rng.choice(rs) for _ in rs]) for _ in range(2000))
    cl = [c for r in rs for c in r["clones"]]
    clone = statistics.median(c["clone_us"] for c in cl) if cl else float("nan")
    extra = ""
    if cl and "save_us" in cl[0]:
        extra = (f" save {statistics.median(c['save_us'] for c in cl):.1f}us load {statistics.median(c['load_us'] for c in cl):.1f}us"
                 f" state_json+parse {statistics.median(c['state_json_parse_us'] for c in cl):.0f}us blob {statistics.median(c['blob_bytes'] for c in cl):.0f}B")
    print(f"{e:10s} fixtures {len(rs)} (errors {len(errs)}) ticks {sum(r['ticks'] for r in rs)} "
          f"ticks/s {tps(rs):,.0f} [{bs[50]:,.0f}, {bs[1949]:,.0f}]  clone(median) {clone:.1f}us{extra}"
          f"  deploys ok/failed {sum(r['deploys_ok'] for r in rs)}/{sum(r['deploys_failed'] for r in rs)}")
    for r in errs[:3]:
        print("   err", r["episode"], r["error"][:160])
