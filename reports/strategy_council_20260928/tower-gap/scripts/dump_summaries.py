"""Dump per-perspective summaries from completed engine-v2b units + payload facts (tower HP, levels).
Output: data/perspectives.jsonl.gz (one line per perspective), data/payload_facts.jsonl.gz (one per match).
Read-only on c56/."""
import gzip, json, sys, zipfile, io
from pathlib import Path
import numpy as np
C = Path(__file__).resolve().parents[2] / "c56/data"
OUT = Path(__file__).resolve().parents[1] / "data"
rows = []
for phase in ("s117", "s122"):
    d = C / "recon/engine-v2b" / phase
    for side in sorted(d.glob("shard-*.json")):
        npz = side.with_suffix(".npz")
        if not npz.exists():
            continue
        with zipfile.ZipFile(npz) as z:
            header = json.loads(str(np.load(io.BytesIO(z.read("header_json.npy")), allow_pickle=False)))
        for p in header["perspectives"]:
            p = dict(p); p["phase"] = phase; p["unit"] = side.stem
            rows.append(p)
with gzip.open(OUT / "perspectives.jsonl.gz", "wt") as f:
    for r in rows:
        f.write(json.dumps(r) + "\n")
print("perspectives", len(rows))
if "--payloads" in sys.argv:
    with gzip.open(OUT / "payload_facts.jsonl.gz", "wt") as f:
        n = 0
        for shard in range(52):
            with gzip.open(C / f"payloads/shard-{shard:03d}.jsonl.gz", "rt") as s:
                for idx, line in enumerate(s):
                    rec = json.loads(line); b = rec["payload"]["battle"]
                    fact = {"tag": rec["tag"], "shard": shard, "index": idx, "c56_sides": rec["c56_sides"],
                            "s117_sides": rec["s117_sides"], "timeline_seconds": rec["payload"]["replay"]["duration"]["timeline_seconds"]}
                    for sd in ("team", "opponent"):
                        pl = b[sd]["players"][0]
                        fact[sd] = {"final": pl["final_tower_hitpoints"], "tower_card": pl.get("tower_card"),
                                    "levels": [c["level"] for c in pl["deck"]], "keys": [c["card_key"] for c in pl["deck"]],
                                    "crowns": b[sd]["crowns"]}
                    f.write(json.dumps(fact) + "\n"); n += 1
    print("matches", n)
