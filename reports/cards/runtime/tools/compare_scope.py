"""Compare the gate outputs in DIR (gate.sh). Prints one JSON summary.

roots-<arm>-<i>.jsonl (parity_scope_roots.py): records keyed (k, variant); equal iff every field except config_sha
matches. hl-<set>-<arm>/games-*.jsonl (bot.eval.headline): rows keyed (candidate, opponent, index); equal iff
command_sha256, winner, ticks and towers match and neither row is an error.
"""
import json
import sys
from pathlib import Path

d = Path(sys.argv[1])
out = {}


def roots(arm):
    heads, rows = [], {}
    for p in sorted(d.glob(f'roots-{arm}-*.jsonl')):
        lines = p.read_text().splitlines()
        if not lines:
            continue
        heads.append(json.loads(lines[0]))
        for x in lines[1:]:
            r = json.loads(x)
            rows[(r['k'], r['variant'])] = r
    return heads, rows


arms = {a: roots(a) for a in ('live', 'c56', 'full') if list(d.glob(f'roots-{a}-*.jsonl'))}
if arms:
    strip = lambda r: {k: v for k, v in r.items() if k != 'config_sha'}
    ref = arms.get('live', arms.get('c56'))[1]
    keys = sorted(ref)
    res = dict(heads={a: dict(scope=h[0]['scope'], cards=h[0]['cards'], native=h[0]['native_sha256'][:16],
                              config_sha=h[0]['config_sha'][:16], recorded_config=[c[:16] for c in h[0]['recorded_config']],
                              records=len(r)) for a, (h, r) in arms.items()},
               records=len(keys), sampled_roots=len({k[0] for k in keys}),
               rollout_e1_values=sum(len(ref[k]['rollout_e1']) for k in keys),
               select_action_calls=sum(len(ref[k]['select']) for k in keys),
               apply_discrete=sum(1 for k in keys if 'apply' in ref[k]),
               step_checks=sum(len(ref[k]['step']) for k in keys),
               games=len({ref[k]['index'] for k in keys}))
    for a, (_, rows) in arms.items():
        same = [k for k in keys if k in rows and strip(rows[k]) == strip(ref[k])]
        res[f'identical_{a}'] = len(same)
        res[f'differing_{a}'] = [list(k) for k in keys if k not in same][:10]
        res[f'config_sha_{a}'] = sorted({rows[k]['config_sha'][:16] for k in rows})[:4]
    out['roots'] = res


def games(path):
    rows = {}
    for p in sorted(path.glob('games-*.jsonl')):
        for x in p.read_text().splitlines():
            r = json.loads(x)
            rows[(r['candidate'], r['opponent'], r['index'])] = r
    return rows


for s in ('pol', 'k4l'):
    a, b = d / f'hl-{s}-c56', d / f'hl-{s}-full'
    if not a.exists() or not b.exists():
        continue
    A, B = games(a), games(b)
    keys = sorted(set(A) & set(B))
    eq = lambda x, y: 'error' not in x and 'error' not in y and all(x[k] == y[k] for k in ('command_sha256', 'winner', 'ticks', 'towers'))
    same = [k for k in keys if eq(A[k], B[k])]
    pairs = sorted({k[:2] for k in keys})
    out[f'headline_{s}'] = dict(
        games=dict(c56=len(A), full=len(B), both=len(keys)), identical=len(same),
        differing=[list(k) for k in keys if k not in same][:10],
        errors=dict(c56=sum('error' in r for r in A.values()), full=sum('error' in r for r in B.values())),
        error_samples=[r['error'][:200] for r in list(A.values()) + list(B.values()) if 'error' in r][:3],
        by_pair={f'{c.split("/")[-1]} vs {o}': f'{sum(1 for k in same if k[:2] == (c, o))}/{sum(1 for k in keys if k[:2] == (c, o))}'
                 for c, o in pairs},
        plays=sum(sum(A[k]['plays'].values()) for k in keys if 'plays' in A[k]))
print(json.dumps(out, indent=1))
