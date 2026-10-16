"""Small, engine-independent reader for per-game differential evidence."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re


def public(d):
    f = d['field']
    return (bool(re.fullmatch(r'\.entities\.\d+\.(x|y|hp|target|alive|owner|class)', f))
            or f in ('.entities.ids', '.tick', '.next_id', '.game_over', '.winner')
            or bool(re.match(r'\.players\[\d+\]\.(elixir|hand|cycle)(?:\[|$)', f))
            or bool(re.fullmatch(r'\.rng\.state\[[0-3]\]', f)))


def summary(r):
    first = r.get('first') or {}
    detail = first.get('detail') or {}
    diffs = [d for d in detail.get('field_diff', []) if public(d)]
    ids = {m.group(1) for d in diffs if (m := re.search(r'\.entities\.(\d+)\.', d['field']))}
    for d in diffs:
        if d['field'] == '.entities.ids':
            ids.update(str(eid) for eid in set(d['python']) ^ set(d['rust']))
    names = sorted({detail.get('entity_names', {}).get(eid)
                    or (detail.get('entities', {}).get(eid, {}).get('rust') or {}).get('stats', {}).get('name', '?')
                    for eid in ids})
    phases = r.get('triage', {}).get('phases', {})
    # JSON keys are sorted on disk, so use the real subsystem ordering.
    phase = next((label for label in ('start', 'combat', 'movement', 'objects', 'cleanup', 'complete')
                  if label in phases and any(public(d) for d in phases[label]['field_diff'])), None)
    return dict(game=r['game']['game'], status=r['status'], tick=first.get('tick'),
                kind=first.get('kind'), names=names, phase=phase,
                differences=diffs[:10], triage_error=r.get('triage_error'),
                error=r.get('error'))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('directory', type=Path)
    p.add_argument('--game', type=int)
    p.add_argument('--output', type=Path)
    args = p.parse_args()
    rows = [json.loads(f.read_text()) for f in sorted(args.directory.glob('game-*.json'))]
    if args.game is not None:
        row = next(r for r in rows if r['game']['game'] == args.game)
        print(json.dumps(row, indent=2))
        return
    summaries = [summary(r) for r in rows]
    output = dict(completed=len(rows), statuses=dict(Counter(r['status'] for r in rows)),
                  ticks=sum(r.get('ticks', 0) for r in rows),
                  triage_errors=sum('triage_error' in r for r in rows),
                  groups=dict(Counter('|'.join([s['phase'] or '-', ','.join(s['names']),
                     ','.join(sorted({d['field'].split('.')[-1] for d in s['differences']}))])
                     for s in summaries if s['status'] != 'match')),
                  games=summaries)
    if args.output:
        args.output.write_text(json.dumps(output, indent=1) + '\n')
        output.pop('games')
    print(json.dumps(output, indent=1))


if __name__ == '__main__':
    main()
