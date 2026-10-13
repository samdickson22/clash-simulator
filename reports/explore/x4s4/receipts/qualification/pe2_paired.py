"""PE-2 test B paired control (05 only, read-only copies; COORDINATOR b98fda79). Same reviewed code as PE-1:
qualify4.parity_once (pooled C7b metric) and qualify4.proved_game/game_meta (timing metadata only, never outcomes),
at d09bdef9, with io.JOB pointed at the copy. argv: code job collect_phase eval_phase arm."""
import json, sys
code, job, cph, eph, arm = sys.argv[1:6]
sys.path.insert(0, code)
import x4s4io as io
io.JOB = job; io.REPORT_ROOT = code
import qualify4 as Q
pooled = {k: Q.parity_once([f'{job}/smoke/{ph}'], 8, require_both=False, bank='smoke')['arms'][arm] for k, ph in (('collect', cph), ('eval', eph))}
rows = []
for i in range(8):
    r = dict(index=i)
    for kind, ph in (('collect', cph), ('eval', eph)):
        g, _ = Q.proved_game(f'{job}/smoke/{ph}', i, arm, Q.SMOKE_BASE)
        ds = Q.game_meta(g)['search_ab']['deadline_stats']
        n = len(ds); c = sum(bool(d.get('hit')) for d in ds)
        r[kind] = dict(decisions=n, cutoff_pct=round(100*c/max(1, n), 2))
    r['delta_pp'] = round(r['collect']['cutoff_pct'] - r['eval']['cutoff_pct'], 2)
    rows.append(r)
d = [r['delta_pp'] for r in rows]
print(json.dumps(dict(check='pe2-paired', arm=arm, collect_phase=cph, eval_phase=eph, pooled=pooled, rows=rows,
                      mean_delta_pp=round(sum(d)/8, 4), positive=sum(x > 0 for x in d),
                      code_commit='d09bdef9aecc416cb83b002fcff002ff57579fde',
                      label='X4S-4 PE-2 test B, exploration, NEVER ADOPTABLE'), indent=1))
