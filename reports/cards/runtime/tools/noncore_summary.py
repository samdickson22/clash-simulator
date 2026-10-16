"""Summarize noncore_matches.py outputs: python noncore_summary.py C56_CARDS.json FILE.jsonl... -> markdown table + JSON."""
import json
import sys
from collections import Counter, defaultdict

c56 = set(json.load(open(sys.argv[1])))
groups = defaultdict(list)
for path in sys.argv[2:]:
    for line in open(path):
        r = json.loads(line)
        groups[(r['player'], r['opponent'], r['deck'])].append(r)
rows = []
print('| player | opp | deck | games | crashes | panics | errors | native fail | search fail | root errors | roots (opp non-C56) | search / default / other | new cards played by opp | non-C56 entities in roots |')
print('|---|---|---|---|---|---|---|---|---|---|---|---|---|---|')
for (p, o, d), rs in sorted(groups.items()):
    src = Counter()
    for r in rs:
        src.update(r.get('sources') or {})
    played, ents = Counter(), Counter()
    for r in rs:
        played.update({k: v for k, v in (r.get('opp_played') or {}).items() if k not in c56})
        ents.update(r.get('noncore_entities_in_roots') or {})
    s = dict(player=p, opponent=o, deck=d, games=len(rs), crashes=sum(1 for r in rs if r.get('crash')),
             panics=sum(r.get('panics') or 0 for r in rs), errors=sum(sum((r.get('errors') or {}).values()) for r in rs),
             fast_errors=sum(r.get('fast_errors') or 0 for r in rs),
             native_failures=sum(sum((r.get('native_failures') or {}).values()) for r in rs),
             search_failures=sum(sum((r.get('search_failures') or {}).values()) for r in rs),
             root_errors=sum(sum((r.get('root_errors') or {}).values()) for r in rs),
             roots=sum(r.get('roots', 0) for r in rs), opp_noncore_roots=sum(r.get('opp_noncore_roots', 0) for r in rs),
             sources=dict(src), opp_new_played=dict(played), entities=dict(ents),
             crash_samples=[r['crash'][-300:] for r in rs if r.get('crash')][:2])
    rows.append(s)
    search = src.get('search', 0)
    default = sum(v for k, v in src.items() if k.startswith('default'))
    other = sum(v for k, v in src.items() if k not in ('search',) and not k.startswith('default'))
    short = p.replace('LIVE-K4L-R-gs-rw-fc-w200-t4-p4', 'LIVE-K4L…p4')
    ent = ', '.join(f'{k} {v}' for k, v in ents.most_common(8)) or '—'
    pl = ', '.join(f'{k} {v}' for k, v in played.most_common(8)) or '—'
    print(f"| {short} | {o} | {d} | {s['games']} | {s['crashes']} | {s['panics']} | {s['errors'] + s['fast_errors']} | "
          f"{s['native_failures']} | {s['search_failures']} | {s['root_errors']} | {s['roots']} ({s['opp_noncore_roots']}) | "
          f"{search} / {default} / {other} | {pl} | {ent} |")
json.dump(rows, open('/dev/stderr', 'w'), indent=1)
