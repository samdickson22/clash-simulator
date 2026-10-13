"""PE-1 descriptive per-seed breakdown (05 only, read-only copies). Uses the reviewed qualify4.proved_game/game_meta projection
(d09bdef9): timing metadata only, never outcomes. Pairs each smoke index's collection game with its evaluation game."""
import json, sys
code, job = sys.argv[1], sys.argv[2]
sys.path.insert(0, code)
import x4s4io as io
io.JOB = job; io.REPORT_ROOT = code
import qualify4 as Q
out = {}
for arm in ('K4S-120', 'S-200'):
    rows = []
    for i in range(8):
        r = dict(index=i)
        for kind in ('collect', 'eval'):
            g, _ = Q.proved_game(f'{job}/smoke/{kind}-{arm}', i, arm, Q.SMOKE_BASE)
            ds = Q.game_meta(g)['search_ab']['deadline_stats']
            n = len(ds); c = sum(bool(d.get('hit')) for d in ds)
            r[kind] = dict(decisions=n, cutoff_pct=round(100*c/max(1, n), 2))
        r['delta_pp'] = round(r['collect']['cutoff_pct'] - r['eval']['cutoff_pct'], 2)
        rows.append(r)
    ds_ = [r['delta_pp'] for r in rows]
    out[arm] = dict(rows=rows, mean_delta_pp=round(sum(ds_)/8, 2), positive=sum(d > 0 for d in ds_))
print(json.dumps(out, indent=1))
