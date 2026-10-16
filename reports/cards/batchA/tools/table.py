"""Per card/scenario verdicts (harness compare()) across fidelity runs, as markdown rows.
Usage: table.py RUN.jsonl [RUN.jsonl ...] -- CARD ...   (one column per run: verdict (number of differences) + first one)"""
import json, sys
from pathlib import Path
sys.path[:0] = [str(Path(__file__).resolve().parent), str(Path(__file__).resolve().parents[2] / 'fidelity')]
from summarize import compare

i = sys.argv.index('--')
runs, cards = sys.argv[1:i], sys.argv[i + 1:]
data = []
for p in runs:
    d = {}
    for l in open(p):
        r = json.loads(l)
        d[r['card'], r['scenario']] = compare(r)
    data.append(d)
cell = lambda v: f"{v[0]} ({len(v[1])})" + (f" {v[1][0]['metric']} {v[1][0]['ours']}/{v[1][0]['royalesim']}" if v[1] else '')
for c in cards:
    for k in [k for k in data[-1] if k[0] == c]:
        print('| ' + ' | '.join([c, k[1]] + [cell(d[k]).replace('|', '/') for d in data]) + ' |')
