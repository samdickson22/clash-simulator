"""Render X4S-3 RESULTS.md from results.json (reduce.py output). Pre-declared readout only."""
import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ARMS = ('K4S-120', 'S-200')


def f(x, d=1): return f'{x:+.{d}f}' if x is not None else 'n/a'
def ci(c): return f'[{c[0]:+.1f}, {c[1]:+.1f}]'
def pc(c): return f'[{c[0]:.1f}, {c[1]:.1f}]'


def main():
    r = json.loads((HERE/'results.json').read_text())
    extra = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    c = r['contrasts']; L = []
    L += ['# X4S-3 results: does more teacher data make a better student, judged in deployment? (exploration, NEVER ADOPTABLE)', '',
          f"Reduced {r['utc']} from {r['paired_seeds']} paired seeds (fixed N; [PLAN](PLAN.md), [results.json](results.json)). "
          'Paired-seed bootstrap, 5,000 reps, seed 2026101201, percentile 95% CIs, unadjusted (about 4 contrasts). '
          'Loss is the rate at which the student-tier agent loses to the exact v1 policy (draws count as non-losses). '
          '**NEVER ADOPTABLE:** nothing here enters a frozen manifest (SD1 stays R3a), and it is never cited in K4S/TIERS reporting.', '']
    L += ['## Pre-declared readout', '', '| Contrast (loss pp; negative = fewer losses) | Pooled | K4S-120 | S-200 |', '|---|---:|---:|---:|']
    for l, rr in (('R4-D', 'R3a'), ('R3a-rep', 'R3a'), ('R4-D', 'R3a-rep'), ('R4-DC', 'R4-D'), ('R4-DC', 'R3a')):
        k = f'{l} minus {rr}'
        if f'{k} [pooled]' not in c: continue
        cells = [f"{f(c[f'{k} [{a}]']['loss_change_pp'])} {ci(c[f'{k} [{a}]']['ci95_pp'])}" for a in ('pooled',)+ARMS]
        L.append(f'| **{k}**{" (primary)" if k == "R4-D minus R3a" else ""} | ' + ' | '.join(cells) + ' |')
    ro = r.get('readout', {})
    L += ['']
    if 'data_helps' in ro:
        L.append(f"**\"Data helps\" (upper 95% CI of pooled R4-D − R3a < 0 AND pooled R4-D − R3a-rep point < 0): "
                 f"{'YES' if ro['data_helps'] else 'NO'}.**")
    if 'fit_seed_noise_ge_4pp' in ro:
        L.append(f"Fit-seed noise |R3a-rep − R3a| ≥ 4 pp: " + ', '.join(f"{k.split('[')[1][:-1]} {'yes' if v else 'no'}" for k, v in ro['fit_seed_noise_ge_4pp'].items()) + '.')
    if 'compute_scales_point' in ro:
        L.append(f"R4-DC − R4-D pooled point < 0 (compute also scales): {'yes' if ro['compute_scales_point'] else 'no'}.")
    if extra.get('r4dc_note'): L.append(extra['r4dc_note'])
    L += ['', '## Per student and arm', '',
          '| Student | Arm | Loss % [95% CI] | Cutoff % | Student-default % | Play % | Wall p50 / p99 ms | Overrun % |',
          '|---|---|---:|---:|---:|---:|---:|---:|']
    for key, a in r['arms'].items():
        s, arm = key.split(' ')
        L.append(f"| {s} | {arm} | {a['loss_pct']:.1f} {pc(a['loss_ci_pct'])} | {a['cutoff_pct']:.1f} | {a['student_default_pct']:.1f} | "
                 f"{a['play_pct']:.1f} | {a['wall_ms_p50']:.0f} / {a['wall_ms_p99']:.0f} | {a['overrun_pct']:.2f} |")
    sens = r.get('s200_thrash_sensitivity')
    if sens:
        L += ['', '## Pre-declared S-200 sensitivity (thrash window excluded)', '',
              f"Window {sens['window_utc'][0]} to {sens['window_utc'][1]}; exclusion receipt SHA-256 {sens['exclusion_sha256'][:8]}…; "
              f"{sens['kept_paired_seeds']} kept paired seeds (the same set for every student).", '',
              '| S-200 | Loss % [95% CI], kept seeds |', '|---|---:|']
        for k, v in sens['arms'].items(): L.append(f"| {k} | {v['loss_pct']:.1f} {pc(v['loss_ci_pct'])} |")
        L += ['', '| S-200 contrast, kept seeds | pp [95% CI] |', '|---|---:|']
        for k, v in sens['contrasts'].items(): L.append(f"| {k} | {f(v['loss_change_pp'])} {ci(v['ci95_pp'])} |")
    L += ['', '## Disclosures', '']
    L += [f'- {x}' for x in extra.get('disclosures', [])]
    (HERE/'RESULTS.md').write_text('\n'.join(L)+'\n')


if __name__ == '__main__':
    main()
