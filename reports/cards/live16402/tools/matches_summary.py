"""Gate (a) summary of noncore_matches.py logs: per file, games / crashes / panics / decision errors / fast errors /
native failures / search failures / root errors, roots whose opponent holds a non-C56 card, decision sources, the
non-C56 cards the opponents actually played, and the changed (live16402) cards played by either side.

    python -I matches_summary.py RECEIPT.json C56_CARDS.json FILE.jsonl [...]
"""
import json
import sys
from collections import Counter

receipt, c56 = json.load(open(sys.argv[1])), set(json.load(open(sys.argv[2])))
changed = set(receipt['changes_by_card'])
for path in sys.argv[3:]:
    rows = [json.loads(line) for line in open(path)]
    s = Counter()
    played_new, played_changed, sources = Counter(), Counter(), Counter()
    for r in rows:
        s['games'] += 1
        s['crashes'] += bool(r.get('crash'))
        s['panics'] += r.get('panics') or 0
        s['decision_errors'] += sum((r.get('errors') or {}).values())
        s['fast_errors'] += r.get('fast_errors') or 0
        s['native_failures'] += sum((r.get('native_failures') or {}).values())
        s['search_failures'] += sum((r.get('search_failures') or {}).values())
        s['root_errors'] += sum((r.get('root_errors') or {}).values())
        s['roots'] += r.get('roots') or 0
        s['opp_noncore_roots'] += r.get('opp_noncore_roots') or 0
        s['terminal'] += bool(r.get('terminal'))
        s['our_wins'] += r.get('winner') == r.get('seat')
        sources.update(r.get('sources') or {})
        for side in ('opp_played', 'own_played'):
            for c, n in (r.get(side) or {}).items():
                if c not in c56:
                    played_new[c] += n
                if c in changed:
                    played_changed[c] += n
    print(json.dumps(dict(file=path, **s, sources=dict(sources), noncore_cards_played=len(played_new),
                          noncore_plays=sum(played_new.values()), changed_cards_played=sorted(played_changed),
                          changed_plays=sum(played_changed.values()),
                          crash_samples=[r['crash'][-300:] for r in rows if r.get('crash')][:3],
                          error_samples=[e for r in rows for e in (r.get('errors') or {})][:5])))
