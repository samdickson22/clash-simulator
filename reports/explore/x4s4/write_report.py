"""Render X4S-4 RESULTS.md from results.json (reduce.py output) and, if present, diagnostic.json.
Pre-declared readout only (PLAN r2 C6 template). Copied in spirit from X4S-3 write_report.py."""
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
    c, ro = r['contrasts'], r.get('readout', {})
    L = ['# X4S-4 results: do on-policy cutoff-state labels make a better student? (exploration, NEVER ADOPTABLE)', '',
         f"Reduced {r['utc']} from {r['paired_seeds']} paired seeds (fixed N; [PLAN](PLAN.md), [results.json](results.json)). "
         'Paired-seed bootstrap, 5,000 reps, seed 2026101301, percentile 95% CIs, unadjusted (about 6 contrasts; only the primary '
         'selects the decision row). Loss = the student-tier agent loses to the exact v1 policy (draws are non-losses). '
         '**NEVER ADOPTABLE**; never cited in K4S/TIERS/T1 reporting.', '']
    p = ro.get('primary')
    if p:
        L += ['## Primary (pre-declared; selects the decision row)', '', f"**Δ = {p['definition']}: {f(p['point_pp'])} pp {ci(p['ci95_pp'])} "
              f"on {p['seeds']} seeds. Outcome: {p['label'].upper()}.**",
              f"Fit-inflated interval (σ_fit fixed at {p['fit_inflated_sigma_fit_pp']} pp, E3): {ci(p['fit_inflated_interval_pp'])}. "
              f"Harmful (lower CI > 0, E9): {'yes' if p['harmful'] else 'no'}. MDE {p['mde_pp']} pp; rule: {p['rule']}. "
              'The bootstrap CIs cover game sampling only (E2).']
        t = r.get('truncation', {})
        if t.get('truncated'):
            L.append(f"**Truncated (E8):** primary on the largest complete seed-index prefix, {t['primary_prefix_seeds']} of {t['non_retired']} non-retired seeds.")
        cs = ro.get('contention_sensitivity')
        if cs:
            L.append(f"Contention sensitivity (pre-declared C5/E7; {cs['excluded_paired_seeds']} seeds excluded, receipt "
                     f"{cs['exclusion_sha256'][:8]}…): Δ {f(cs['point_pp'])} pp {ci(cs['ci95_pp'])} on {cs['seeds']} seeds → {cs['label']}.")
        sw = ro.get('secondary_mean_R5_minus_R5W')
        if sw:
            L.append(f"Attribution (E4, descriptive): mean(R5, R5-rep) − R5W = {f(sw['point_pp'])} pp {ci(sw['ci95_pp'])} on {sw['seeds']} seeds → "
                     f"**{sw['attribution']}**.")
    L += ['', '## Single-fit and secondary contrasts (descriptive)', '', '| Contrast (loss pp; negative = fewer losses) | Pooled | K4S-120 | S-200 |', '|---|---:|---:|---:|']
    for l, rr in (('R5', 'R3a'), ('R5-rep', 'R3a'), ('R5', 'R3a-rep'), ('R3a-rep', 'R3a'), ('R5', 'R5-rep'), ('R5', 'R5W'), ('R5-rep', 'R5W')):
        k = f'{l} minus {rr}'
        if f'{k} [pooled]' in c:
            L.append(f'| {k} | ' + ' | '.join(f"{f(c[f'{k} [{a}]']['loss_change_pp'])} {ci(c[f'{k} [{a}]']['ci95_pp'])}" for a in ('pooled',)+ARMS) + ' |')
    if 'sigma_fit_pp' in ro:
        L += ['', f"σ_fit ≈ {ro['sigma_fit_pp']['value']:.2f} pp ({ro['sigma_fit_pp']['df']}-df, descriptive)."]
    if 'fit_seed_noise_ge_4pp' in ro:
        L.append('|R3a-rep − R3a| ≥ 4 pp: ' + ', '.join(f"{k.split('[')[1][:-1]} {'yes' if v else 'no'}" for k, v in ro['fit_seed_noise_ge_4pp'].items()) + '.')
    if extra.get('notes'): L += [''] + extra['notes']
    L += ['', '## Timing parity (pre-declared C4; non-outcome)', '', '| Arm | Student | Cutoff % | Student-default % | Wall p99 ms |', '|---|---|---:|---:|---:|']
    for arm, v in ro.get('timing_parity', {}).items():
        for s, m in v['per_student'].items():
            L.append(f"| {arm} | {s} | {m['cutoff_pct']:.1f} | {m['student_default_pct']:.1f} | {m['wall_ms_p99']:.0f} |")
        L.append(f"| {arm} | gap | {v['cutoff_gap_pp']:.1f} | {v['student_default_gap_pp']:.1f} | {'> 2 pp: disclosed (no exclusion, E10)' if v['gap_gt_2pp_disclosed'] else 'within 2 pp'} |")
    L += ['', '## Per student and arm', '', '| Student | Arm | Loss % [95% CI] | Cutoff % | Student-default % | Play % | Wall p50 / p99 ms | Overrun % |',
          '|---|---|---:|---:|---:|---:|---:|---:|']
    for key, a in r['arms'].items():
        s, arm = key.split(' ')
        L.append(f"| {s} | {arm} | {a['loss_pct']:.1f} {pc(a['loss_ci_pct'])} | {a['cutoff_pct']:.1f} | {a['student_default_pct']:.1f} | "
                 f"{a['play_pct']:.1f} | {a['wall_ms_p50']:.0f} / {a['wall_ms_p99']:.0f} | {a['overrun_pct']:.2f} |")
    diag = HERE/'diagnostic.json'
    if diag.exists():
        d = json.loads(diag.read_text())
        L += ['', '## O-holdout diagnostic (descriptive only; never a gate)', '', '| Student | Slice | Top-1 agreement | Gate accuracy | Listwise CE |', '|---|---|---:|---:|---:|']
        for s, slices in d['students'].items():
            for sl, m in slices.items():
                L.append(f"| {s} | {sl} | {m['top1_agreement']:.3f} | {m['gate_accuracy']:.3f} | {m['listwise_ce']:.3f} |")
    L += ['', '## Disclosures', ''] + [f'- {x}' for x in extra.get('disclosures', [])]
    (HERE/'RESULTS.md').write_text('\n'.join(L)+'\n')


if __name__ == '__main__':
    main()
