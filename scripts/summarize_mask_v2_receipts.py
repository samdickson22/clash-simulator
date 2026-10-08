"""Summarize existing S5/S6 rejection receipts without rerunning policies."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--input',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    cells=defaultdict(Counter)
    digests={}
    for path in sorted(args.input.glob('*.json')):
        data=path.read_bytes();r=json.loads(data)
        c=cells[r['variant']]
        c.update(games=1,submitted_actions=r['action_count'],
                 candidate_rejections=r['rejected'][0], opponent_rejections=r['rejected'][1],
                 decisions=r['timing']['decisions'])
        c['receipts_with_recorded_actions']+=isinstance(r.get('actions'),list)
        digests[path.name]=hashlib.sha256(data).hexdigest()
    total=sum(cells.values(),Counter())
    result=dict(schema='clasher.mask-v2-receipt-summary.v1',counts=total,per_variant=cells,
        source=str(args.input),files=len(digests),
        source_aggregate_sha256=hashlib.sha256(json.dumps(digests,sort_keys=True).encode()).hexdigest(),
        limitation='Rejections include stale/noisy/delayed command effects. Only an action hash survives; no decision boards, proposal IDs or per-card rejection guards. These are total execution-rejection rates, not identified mask-occupancy errors.')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2))


if __name__=='__main__':main()
