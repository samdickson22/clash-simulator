"""Generate the offline Markdown report from saved reports, curves and compute."""
import argparse
import json
from pathlib import Path
from .guards import sha


def number(x):
    return 'N/A' if x is None else f'{x:.6f}'


def interval(x):
    return 'N/A' if x is None else '['+', '.join(number(v) for v in x)+']'


def verdict(x):
    return 'PASS' if x is True else 'FAIL' if x is False else 'N/A'


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--selection', required=True); p.add_argument('--manifest', required=True)
    p.add_argument('--prereg', required=True); p.add_argument('--reports', required=True)
    p.add_argument('--curves-compute', required=True); p.add_argument('--output', required=True)
    a = p.parse_args()
    selection = json.loads(Path(a.selection).read_text()); manifest = json.loads(Path(a.manifest).read_text())
    compute = json.loads(Path(a.curves_compute).read_text()); root = Path(a.reports)
    reports = {(run, role): json.loads((root/f'{run}-{role}.json').read_text())
               for run in selection['runs'] for role in ('eval', 'eval_ood')}
    primary = selection['primary']; chosen = reports[primary, 'eval']
    out = ['# C56 v1 offline results', '', f"Gate (a): **{verdict(chosen['gate_pass'])}**. Primary entrant: `{primary}`, selected by uncalibrated EMA dev joint NLL only.",
           '', f'Frozen PREREG SHA256: `{sha(a.prereg)}`.', f'Executable manifest SHA256: `{sha(a.manifest)}`.',
           f"Qualified T4 code: `{manifest['qualified_code_sha256']}`. Microbatch7168, effective8192, workers4, eager bf16. One run per GPU.",
           '', '## Selected checkpoints', '', '| Run | Dev joint NLL | Step | Checkpoint SHA256 |', '|---|---:|---:|---|']
    for run, s in selection['runs'].items():
        out.append(f"| {run} | {number(s['dev_joint_nll'])} | {s['step']} | `{s['checkpoint_sha256']}` |")
    for role in ('eval', 'eval_ood'):
        r = reports[primary, role]; g = r['gates']
        out += ['', f'## Primary {role} gate bars', '', '| Bar / metric | Model − baseline | 95% paired CI | Verdict |', '|---|---:|---|---|']
        for key, v in g['A1']['details'].items():
            out.append(f"| A1 {key} | {number(v['value'])} | {interval(v['ci95'])} | {verdict(v['ci95'] is not None and v['ci95'][1]<0)} |")
        for key, v in g['A2']['details'].items():
            out.append(f"| A2 {key} | {number(v['delta'])} (model {number(v['model'])}; P16 {number(v['baseline'])}; margin .05) | point bar | {verdict(v['pass'])} |")
        if not g['A2']['details']:
            out.append('| A2 | No P16 perspectives | N/A | N/A |')
        out.append(f"| A3 | {g['A3']['passing_cards']}/{g['A3']['scoped_cards']} cards | per-card table below | {verdict(g['A3']['pass'])} |")
        out.append(f"| A4 | ECE {number(g['A4']['ece'])}, bar .01 | {interval(g['A4']['ci95'])} | {verdict(g['A4']['pass'])} |")
        out += ['', '| A3 card | Plays | Tile NLL delta | 95% CI | Significantly worse |', '|---|---:|---:|---|---|']
        for card, v in g['A3']['cards'].items():
            out.append(f"| {manifest['card_names'][card]} | {v['n']} | {number(v['value'])} | {interval(v['ci95'])} | {v['significantly_worse']} |")
    out += ['', '## All seeds and ablations', '', '| Run / role | Joint NLL | Play/wait NLL | Card NLL | Tile NLL | Top8 exact | Top8 within1 | A1/A2/A3/A4 |', '|---|---:|---:|---:|---:|---:|---:|---|']
    for (run, role), r in reports.items():
        m = r['after']['metrics']
        vals = [number(m[k]['value']) for k in ('joint_nll','play_wait_nll','card_nll','tile_nll','top8_recall','top8_within1')]
        out.append('| '+run+' / '+role+' | '+' | '.join(vals)+' | '+' / '.join(verdict(r['gates'][k]['pass']) for k in ('A1','A2','A3','A4'))+' |')
    out += ['', '| Contrast | Joint NLL | Card NLL | Tile NLL | Top8 exact |', '|---|---:|---:|---:|---:|']
    contrasts = [(run+' OOD − eval', reports[run, 'eval_ood'], reports[run, 'eval']) for run in selection['runs']]
    contrasts += [(run+' − main2026100801 / '+role, reports[run, role], reports['main-2026100801', role])
                  for run in ('noD1-2026100801','gru-2026100801') for role in ('eval','eval_ood')]
    for name, first, second in contrasts:
        vals = [number(first['after']['metrics'][k]['value']-second['after']['metrics'][k]['value']) for k in ('joint_nll','card_nll','tile_nll','top8_recall')]
        out.append('| '+name+' | '+' | '.join(vals)+' |')
    out += ['', 'Per-card/per-arena metrics, uncalibrated scores, calibration bins, hazards and intervals are in the accompanying per-run JSON reports. All supervised rows have natural weight1. Ten thousand whole-perspective PCG64 resamples use seed2026100805, paired across comparisons.',
            '', '## Training curves and compute', '', '```json', json.dumps(compute, indent=2), '```',
            '', 'Training/selection/calibration used train/dev only. Each selected run was scored once per held-out role; analysis uses committed sufficient statistics. T3 baseline summaries were visible before training and were not tuning inputs. No extra fitted trials, data deletion or commits.']
    Path(a.output).write_text('\n'.join(out)+'\n')


if __name__ == '__main__':
    main()
