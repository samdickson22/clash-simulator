"""Per card/scenario verdict and first differences, using the fidelity harness's own compare().
Usage: diffs.py RESULTS.jsonl [CARD ...] [--n N]"""
import json, sys
from pathlib import Path
sys.path[:0] = [str(Path(__file__).resolve().parent), str(Path(__file__).resolve().parent)]
from summarize import compare
args = sys.argv[1:]
n = 6
if '--n' in args:
    i = args.index('--n'); n = int(args[i+1]); del args[i:i+2]
path, cards = args[0], set(args[1:])
for l in open(path):
    r = json.loads(l)
    if cards and r['card'] not in cards:
        continue
    v, d = compare(r)
    print(f"{r['card']:18s} {r['scenario']:8s} {v:5s} ndiff={len(d)}", ' | '.join(f"{x['metric']} {x['ours']}/{x['royalesim']}" for x in d[:n]))
