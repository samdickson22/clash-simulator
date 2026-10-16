"""Compare pinned vs patched gate outputs (fixtures-*.jsonl, roots-*-<i>.jsonl) in DIR; prints one JSON summary."""
import json
import sys
from pathlib import Path

d = Path(sys.argv[1])
out = {}
fx = {}
for tag in ('pinned', 'total'):
    fx[tag] = {r['episode']: r for r in map(json.loads, (d / f'fixtures-{tag}.jsonl').read_text().splitlines())}
eps = sorted(fx['pinned'])
same = [e for e in eps if fx['total'].get(e) == fx['pinned'][e]]
rs_ok = {t: sum(1 for e in eps if (r := fx[t][e]['rs']).get('start_match') and r.get('first_mismatch') is None
                and not r.get('action_mismatch') and 'error' not in r) for t in fx}
out['fixtures'] = dict(pinned=len(fx['pinned']), total=len(fx['total']), identical_records=len(same),
                       differing=[e for e in eps if e not in same][:10],
                       rs_full_parity=rs_ok,
                       rust_only_chains_equal=sum(1 for e in eps if fx['total'].get(e, {}).get('rust_only') == fx['pinned'][e]['rust_only']),
                       rust_only_errors={t: sum(1 for e in eps if 'error' in fx[t][e]['rust_only']) for t in fx},
                       rust_only_ticks=sum(fx['pinned'][e]['rust_only'].get('ticks', 0) for e in eps))
rt = {}
for tag in ('pinned', 'total'):
    rows, heads = [], []
    for p in sorted(d.glob(f'roots-{tag}-*.jsonl')):
        lines = p.read_text().splitlines()
        heads.append(json.loads(lines[0]))
        rows += [json.loads(x) for x in lines[1:]]
    rt[tag] = dict(heads=heads, rows={(r['k'], r['variant']): r for r in rows})
keys = sorted(rt['pinned']['rows'])
eq = [k for k in keys if rt['total']['rows'].get(k) == rt['pinned']['rows'][k]]
P = rt['pinned']['rows']
out['roots'] = dict(native=[h['native_sha256'] for h in (rt['pinned']['heads'][0], rt['total']['heads'][0])],
                    roots_total=rt['pinned']['heads'][0]['roots_total'],
                    sampled_roots=len({k[0] for k in keys}), records=dict(pinned=len(keys), total=len(rt['total']['rows'])),
                    identical_records=len(eq), differing=[k for k in keys if k not in eq][:10],
                    rollout_e1_values=sum(len(P[k]['rollout_e1']) for k in keys),
                    select_action_calls=sum(len(P[k]['select'])for k in keys),
                    apply_discrete=sum(1 for k in keys if 'apply' in P[k]),
                    step_checks=sum(len(P[k]['step']) for k in keys),
                    games=len({P[k]['index'] for k in keys}),
                    tick_range=[min(P[k]['tick'] for k in keys), max(P[k]['tick'] for k in keys)],
                    by_variant={v: sum(1 for k in eq if k[1] == v) for v in ('full', 'cut')})
print(json.dumps(out, indent=1))
