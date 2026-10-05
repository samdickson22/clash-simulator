"""Cheap screen (PLAN 2b): open-loop re-simulation of all saved tier-(a) payload pools
(g66 1500 + s120 400) with the pre-change engine; per-match first contradiction.
Resumable: appends one JSON line per match to resim_screen.jsonl and skips done tags.
Run from repo root:
  nohup nice -n 10 env OMP_NUM_THREADS=1 PYTHONPATH=reports/strategy_council_20260928/c56/engine/baseline-src \
    .venv/bin/python reports/strategy_council_20260928/c56/engine/screen/run_screen_resim.py &
"""
import contextlib, gzip, io, json, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
SCAN = HERE.parents[2] / "m0/human-prior-scan"
sys.path.insert(0, str(SCAN))
import resim_pilot  # noqa: E402

out = HERE / "resim_screen.jsonl"
done = set()
if out.exists():
    done = {json.loads(l)["tag"] for l in out.open() if l.strip()}
with out.open("a") as sink:
    for pool in ("s120", "g66"):
        with gzip.open(SCAN / f"payloads_{pool}_tier_a.jsonl.gz", "rt") as f:
            for line in f:
                rec = json.loads(line)
                if rec["tag"] in done or rec["payload"]["battle"]["result"] not in ("victory", "defeat", "draw"):
                    continue
                t = time.time()
                try:
                    with contextlib.redirect_stdout(io.StringIO()):
                        r = resim_pilot.run_match(rec)
                except Exception as exc:
                    r = {"tag": rec["tag"], "error": f"{type(exc).__name__}: {exc}"}
                r["pool"] = pool
                r["seconds"] = round(time.time() - t, 2)
                sink.write(json.dumps(r) + "\n"); sink.flush()
                done.add(rec["tag"])
print("done", len(done))
