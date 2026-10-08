"""Train/validation-only timing coverage audit. No model or heldout payloads."""
import argparse
from collections import Counter
import json
from pathlib import Path
import numpy as np
from execution_clock_v4 import ExecutionClock
from formal_guard import SPLIT_SHA, digest


def audit(source, split):
    if digest(split) != SPLIT_SHA:
        raise ValueError('Frozen split changed')
    members = {r['seed']:r for r in json.loads(split.read_text())['matches']}
    matches, widths, counts = [], [], Counter()
    for path in sorted(source.glob('*/receipt.json')):
        receipt = json.loads(path.read_text())
        if receipt.get('split') not in ('train', 'validation'):
            continue
        member = members[receipt['seed']]
        if (receipt['split'], receipt['decks']) != (member['split'], member['decks']):
            raise ValueError('Frozen membership mismatch')
        rows = {}
        for name in ('frames.jsonl', 'events.jsonl'):
            file = path.parent/name
            if digest(file) != receipt['files'][name]:
                raise ValueError('Timing audit payload changed')
            rows[name] = [json.loads(line) for line in file.read_text().splitlines()]
        if len(rows['frames.jsonl']) != receipt['frames']:
            raise ValueError('Frame count differs from receipt')
        clock = ExecutionClock(rows['frames.jsonl'])
        accepted = [e for e in rows['events.jsonl'] if e['accepted']]
        if len(accepted) != receipt['accepted_events']:
            raise ValueError('Accepted-event count differs from receipt')
        missing, local = [], []
        for event in accepted:
            try:
                mapped = clock.map_tick(event['exec_tick'])
            except ValueError as exc:
                missing.append(dict(event_id=event['event_id'], exec_tick=event['exec_tick'], reason=str(exc)))
            else:
                lo, hi = mapped['event_time_interval_ms']
                local.append(hi-lo)
        widths.extend(local)
        counts.update({receipt['split']+'_matches':1, 'accepted_events':len(accepted),
                       'mapped_events':len(local), 'unenclosed_events':len(missing)})
        matches.append(dict(episode=receipt['episode'], split=receipt['split'],
            receipt_sha256=digest(path), accepted_events=len(accepted), mapped_events=len(local),
            unenclosed=missing, maximum_interval_ms=max(local) if local else None))
    if not matches:
        raise ValueError('No admitted train/validation matches')
    return dict(schema='clasher.v4.execution-clock-audit.v1', counts=dict(counts),
        interval_p95_ms=float(np.quantile(widths, .95)) if widths else None,
        maximum_interval_ms=max(widths) if widths else None, per_match=matches,
        timing_certified=False, heldout_payloads_opened=False,
        scope='empirical timing coverage only; no prediction scoring or gate certification')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('source', 'split', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.source, args.split)
    with args.output.open('x') as f:
        json.dump(result, f, indent=2, allow_nan=False)
    print(json.dumps({k:v for k,v in result.items() if k != 'per_match'}), flush=True)
