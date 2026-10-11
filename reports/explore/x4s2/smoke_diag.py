"""X4S2 smoke diagnostics (stdlib; exploration, NEVER ADOPTABLE). Checks metadata and the scaling
charge per decision; prints per-arm timing. Usage: smoke_diag.py PHASE_DIR PLAN OUT."""
import json, sys
from collections import defaultdict
from pathlib import Path


def main():
    phase, plan, out = Path(sys.argv[1]), json.loads(Path(sys.argv[2]).read_text()), Path(sys.argv[3])
    per = defaultdict(lambda: defaultdict(list)); bad = []
    for p in sorted((phase/'games').glob('*.json')):
        r = json.loads(p.read_text()); m = r['metadata']; s = r['search_ab']; arm = m['arm']; sp = plan['arms'][arm]
        for k in ('threads', 'coarse_horizon', 'default_source', 'inference_scale', 'scale_mode', 'kernel'):
            if m[k] != sp[k]: bad.append((p.name, k, m[k], sp[k]))
        if m['budget_ms'] != (None if sp['deadline_seconds'] is None else round(sp['deadline_seconds']*1000)):
            bad.append((p.name, 'budget_ms'))
        if not m['population'] or m['seed'] is None: bad.append((p.name, 'population/seed'))
        a = per[arm]; a['wall_s'].append(r['wall_seconds'])
        for d in s['deadline_stats']:
            extra = (sp['inference_scale']-1)*d['poll_seconds']
            a['poll_ms'].append(1000*d['poll_seconds']); a['sleep_ms'].append(1000*d['scale_sleep_seconds'])
            if d['prep_seconds'] is not None: a['prep_ms'].append(1000*d['prep_seconds'])
            a['hit'].append(d['hit']); a['student'].append(d.get('student_default', False))
            if sp['scale_mode'] == 'none' and d['scale_sleep_seconds'] != 0: bad.append((p.name, 'sleep in unscaled arm'))
            if sp['scale_mode'] == 'inference':
                # Sleep must cover the requested extra (time.sleep never returns early) with small overshoot.
                if not (extra-1e-4 <= d['scale_sleep_seconds'] <= extra+5e-3): bad.append((p.name, 'charge', extra, d['scale_sleep_seconds']))
                a['charge_ratio'].append(d['scale_sleep_seconds']/max(1e-9, d['poll_seconds']))
            if sp['scale_mode'] == 'prep' and d['prep_seconds'] is not None:
                a['prep_sleep_share'].append(d['scale_sleep_seconds']/max(1e-9, d['prep_seconds']))
        if sp['scale_mode'] != 'none' and m['scale_sleeps'] == 0: bad.append((p.name, 'no sleeps recorded'))
    mean = lambda v: sum(v)/len(v) if v else None
    q = lambda v, f: sorted(v)[int(f*(len(v)-1))] if v else None
    summary = {arm: dict(games=len(a['wall_s']), wall_s_mean=mean(a['wall_s']), decisions=len(a['poll_ms']),
                         poll_ms_mean=mean(a['poll_ms']), poll_ms_p50=q(a['poll_ms'], .5), poll_ms_p95=q(a['poll_ms'], .95),
                         sleep_ms_mean=mean(a['sleep_ms']), prep_ms_mean=mean(a['prep_ms']), prep_ms_p50=q(a['prep_ms'], .5),
                         charge_ratio_p50=q(a['charge_ratio'], .5), prep_sleep_share_p50=q(a['prep_sleep_share'], .5),
                         cutoff_pct=100*mean(a['hit']) if a['hit'] else None, student_default_pct=100*mean(a['student']) if a['student'] else None)
               for arm, a in sorted(per.items())}
    res = dict(phase=str(phase), problems=bad[:50], problem_count=len(bad), arms=summary)
    out.write_text(json.dumps(res, indent=2)+'\n')
    print(json.dumps(dict(problems=len(bad), first=bad[:5])))
    for arm, s in summary.items():
        print(arm, {k: (round(v, 2) if isinstance(v, float) else v) for k, v in s.items()})


if __name__ == '__main__':
    main()
