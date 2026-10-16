"""Summarise a bot/fullpool/smoke.sh OUT dir: games, errors, scores, non-C56 cards played, C56 hash parity."""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

from bot.fullpool.cards import C56


def rows(d):
    out = []
    for p in sorted(Path(d).glob('games-*.jsonl')):
        out += [json.loads(line) for line in p.read_text().splitlines() if line.strip()]
    return out


def main(out):
    out = Path(out)
    report = {}
    for arm in ('stu', 'k4l'):
        r = rows(out / arm)
        if not r:
            continue
        ok = [x for x in r if 'error' not in x]
        new = Counter(c for x in ok for d in x.get('deck_lists', []) for c in d if c not in C56)
        report[arm] = dict(games=len(r), errors=len(r) - len(ok), error_samples=[x['error'][:200] for x in r if 'error' in x][:3],
                           score=round(sum(x['score'] for x in ok) / len(ok), 4) if ok else None,
                           terminal=sum(bool(x.get('terminal')) for x in ok),
                           decks_with_new=sum(any(c not in C56 for d in x.get('deck_lists', []) for c in d) for x in ok),
                           distinct_new_cards=len(new), candidates=sorted({x['candidate'] for x in r}))
    for arm in ('c56s', 'c56k'):
        r = rows(out / arm)
        if not r:
            continue
        by = {}
        for x in r:
            by.setdefault(x['index'], {})[x['candidate']] = x.get('command_sha256', 'ERROR:' + x.get('error', '')[:80])
        cands = sorted({x['candidate'] for x in r})
        complete = {i: v for i, v in by.items() if len(v) == len(cands)}
        same = sum(len(set(v.values())) == 1 and not any(str(h).startswith('ERROR') for h in v.values()) for v in complete.values())
        report[arm] = dict(cases=len(complete), identical_command_hashes=same, candidates=cands,
                           errors=sum('error' in x for x in r))
    g = rows(out / 'gen')
    if g:
        report['gen'] = dict(games=len(g), errors=sum('error' in x for x in g),
                             shards=len(list((out / 'gen' / 'games').glob('game-*'))),
                             labelled=sum(s.get('labelled', 0) for x in g for s in x.get('shards', {}).values()),
                             error_samples=[x['error'][:200] for x in g if 'error' in x][:2])
    print(json.dumps(report, indent=1))


if __name__ == '__main__':
    main(sys.argv[1])
