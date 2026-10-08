"""Summarize plumbing completion, legality and latency without outcome claims."""
import argparse
import json
from pathlib import Path
import numpy as np


def main():
    p=argparse.ArgumentParser();p.add_argument('folder',type=Path);p.add_argument('--games',type=int,required=True)
    p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    rows=[json.loads(p.read_text()) for p in sorted(args.folder.glob('game-*.json'))]
    values=np.array([t for row in rows for t in row.get('timings_ms',[])])
    result=dict(plumbing_only=True,expected_games=args.games,completed_games=len(rows),
                complete=len(rows)==args.games and all(r['terminal'] for r in rows),
                illegal_actions=sum(sum(r.get('illegal',[0,0])) for r in rows),
                rejected_commands=sum(sum(r.get('rejected',[0,0])) for r in rows),
                skew_rows=sum(r.get('skew_checks',r.get('rows',0)) for r in rows),
                decisions=len(values))
    if len(values):
        result.update(p50_ms=float(np.quantile(values,.5)),p99_ms=float(np.quantile(values,.99)),
                      max_ms=float(values.max()),over_250_ms=int((values>250).sum()))
    with open(args.output,'x') as stream:json.dump(result,stream,indent=2)
    print(json.dumps(result,indent=2))


if __name__=='__main__': main()
