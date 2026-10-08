"""Inspect timing edge cases only in admitted local train/validation matches."""
import argparse
import json
from pathlib import Path
from formal_guard import SPLIT_SHA, digest


def main():
    parser = argparse.ArgumentParser()
    for name in ('source', 'split', 'audit', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    if digest(args.split) != SPLIT_SHA:
        raise ValueError('Frozen split changed')
    members = {m['seed']:m for m in json.loads(args.split.read_text())['matches']}
    audit = json.loads(args.audit.read_text())
    results, absent = [], []
    for match in audit['per_match']:
        if not match['unenclosed']:
            continue
        root = args.source/match['episode']
        if not (root/'receipt.json').exists():
            absent.append(match['episode'])
            continue
        receipt = json.loads((root/'receipt.json').read_text())
        member = members[receipt['seed']]
        if receipt['split'] not in ('train', 'validation') or receipt['split'] != member['split']:
            raise ValueError('Split isolation failure')
        if receipt['decks'] != member['decks'] or digest(root/'receipt.json') != match['receipt_sha256']:
            raise ValueError('Admission drift')
        if digest(root/'frames.jsonl') != receipt['files']['frames.jsonl']:
            raise ValueError('Frame metadata changed')
        frames = [json.loads(line) for line in (root/'frames.jsonl').read_text().splitlines()]
        nonextra = [f for f in frames if not f['bracket_extrapolated']]
        fields = ('seq', 'produced_at', 'tick_lo', 'tick_hi', 'bracket_extrapolated')
        short = lambda f:{k:f[k] for k in fields}
        for event in match['unenclosed']:
            tick = event['exec_tick']
            before = [f for f in frames if f['tick_hi'] < tick]
            after = [f for f in frames if f['tick_lo'] >= tick]
            results.append(dict(episode=match['episode'], split=receipt['split'], event=event,
                first_frame=short(frames[0]), last_frame=short(frames[-1]),
                first_nonextrapolated=short(nonextra[0]), last_nonextrapolated=short(nonextra[-1]),
                last_upper_before=short(before[-1]) if before else None,
                first_lower_after=short(after[0]) if after else None))
    result = dict(audit_sha256=digest(args.audit), examined=results, absent_local=absent,
                  heldout_payloads_opened=False, scope='timing boundary diagnosis only')
    with args.output.open('x') as f:
        json.dump(result, f, indent=2)
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
