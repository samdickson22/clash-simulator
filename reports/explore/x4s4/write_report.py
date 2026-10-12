"""Render X4S-4 RESULTS.md (exploration, NEVER ADOPTABLE; PLAN r3 frozen at 87809ae0). Stdlib only.
r2 after Sol script review r1 (F10, F14).

Inputs (read-only, SHA-recorded in the report): results.json from reduce.py (<job>/analysis/), the frozen label plan
(O composition, dedup, 600-tick feature-only duplicates), the O and O_W gates (|O|, O_W single-candidate root share)
and, if present, the O-holdout diagnostic. The output is confined to <repo>/reports/explore/x4s4/RESULTS.md.
Always rendered (Sol F14): the primary pooled and separately by arm; prefix seed counts for the primary and for R5W;
the contention view (an explicit no-estimate line when it is empty); the composition table; the fixed control-data
disclosures; and the decision-table row selected by the primary outcome, with its harmful/attribution follow-up.
"""
import argparse, hashlib, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import confine                                   # noqa: E402

ARMS = ('K4S-120', 'S-200')
FIXED_DISCLOSURES = [
    'R3a-rep differs from R3a in its G-04 rows as well as its fit seed, so the control mean averages two closely related, '
    'but not seed-only, replicates (C1).',
    'O samples hidden states from the deployed Belief (the S1 exact resumable prior); r1, G and O_W used the emitter\'s '
    'ExactFastPrior. Both are exact-prior beliefs (C8).',
    'O is labelled through the anchor kernel and O_W through the emitter: different wrappers of the screen8 scorer whose '
    'equivalence rests on the 125-state frozen equality.',
    'O_W differs from O in behavior policy (W\'s own decisions, including single-candidate roots, vs the student-tier '
    'agent\'s cutoff-heavy selection of > 1-candidate decisions); R5 - R5W measures that intended contrast.',
    'Bootstrap CIs cover game sampling only; fit-seed variance is not in them (E2). One DAgger round, one behavior policy, '
    'one opponent, five decks; x4 up-weighting is a single pre-declared choice.',
    'Exploration only, NEVER ADOPTABLE; never cited in K4S/TIERS/T1 reporting.',
]


def f(x, d=1): return f'{x:+.{d}f}' if x is not None else 'n/a'
def ci(c): return f'[{c[0]:+.1f}, {c[1]:+.1f}]'
def pc(c): return f'[{c[0]:.1f}, {c[1]:.1f}]'
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def next_step(p, sw):
    """The PLAN r3 §1 decision-table row selected by the primary outcome (descriptive)."""
    o = p['outcome']
    if o == 'helps':
        att = sw.get('attribution') if sw else None
        if att == 'on-policy beyond matched data':
            row = 'Iterate DAgger (collect with R5, label, refit, with replicates) and scale O; a separate SD2 PREREG for the slow-Mac/1-core tiers only after the K4S/TIERS release.'
        elif att == 'matched data does at least as well':
            row = 'Matched W generation (W vs v1 on deployment decks).'
        else:
            att = 'on-policy or deployment-matched data helps; attribution unresolved'
            row = 'Default: matched W generation first (cheaper: no capture or labeling pipeline), then disambiguate before DAgger iteration 2.'
        return f'Helps; attribution sub-label (E4): **{att}**. {row} In every case, check for overfitting to v1/X decks before any live use.'
    if o == 'no material effect':
        s = ('No material effect: one round of on-policy cutoff labels at this scale does not move deployment by >= 2 pp. Next lever: '
             'capacity/value targets (a separate X4S-5 with a latency-charged arm). Mac tiers stay on SD1.')
        if p.get('harmful'):
            s += (' **Also harmful (E9):** first audit the O labels (anchor kernel vs frozen references at cutoff states) and use the '
                  'O-holdout diagnostic for x4 memorization, before any rerun.')
        return s
    s = 'Inconclusive: the lever is untested at this power, not exhausted; only a larger, replicated design (N and fits) can settle it. No program decision.'
    if p.get('harmful'): s += ' Harmful sub-label (E9) set: audit the O labels before any rerun.'
    return s


def render(r, plan, o_gate, ow_gate, diag, inputs, notes):
    c, ro = r['contrasts'], r['readout']
    L = ['# X4S-4 results: do on-policy cutoff-state labels make a better student? (exploration, NEVER ADOPTABLE)', '',
         f"Reduced {r['utc']} from {r['paired_seeds']} paired seeds ([PLAN](PLAN.md)). Paired-seed bootstrap, 5,000 reps, seed "
         '2026101301, percentile 95% CIs, unadjusted (about 6 contrasts; only the primary selects the decision row). Loss = the '
         'student-tier agent loses to the exact v1 policy (draws are non-losses). **NEVER ADOPTABLE**; never cited in K4S/TIERS/T1 '
         'reporting.', '']
    p = ro['primary']
    L += ['## Primary (pre-declared; selects the decision row)', '',
          f"**Δ = {p['definition']}: {f(p['point_pp'])} pp {ci(p['ci95_pp'])} on {p['seeds']} seeds. Outcome: {p['label'].upper()}.**",
          f"Fit-inflated interval (σ_fit fixed at {p['fit_inflated_sigma_fit_pp']} pp, E3): {ci(p['fit_inflated_interval_pp'])}. "
          f"Harmful (lower CI > 0, E9): {'yes' if p['harmful'] else 'no'}. MDE {p['mde_pp']} pp; rule: {p['rule']}. "
          'The bootstrap CIs cover game sampling only (E2).', '',
          '| Primary Δ by arm (descriptive; no outcome rule) | Point pp | 95% CI | Seeds |', '|---|---:|---:|---:|']
    for arm in ARMS:
        b = ro['primary_by_arm'][arm]
        L.append(f"| {arm} | {f(b['point_pp'])} | {ci(b['ci95_pp'])} | {b['seeds']} |")
    t = r['truncation']
    L += ['', f"Seeds (E8): primary {t['primary_prefix_seeds']} of {t['non_retired']} non-retired"
              f"{' — **truncated to the largest complete seed-index prefix**' if t['truncated'] else ' (complete)'}; "
              f"R5W secondaries {t['r5w_prefix_seeds']} seeds"
              f"{' — **R5W prefix shorter than the primary** (its own prefix; never cuts the primary)' if t['r5w_truncated'] else ''}"
              f"{'' if t['r5w_reduced'] else ' (R5W not reduced)'}."]
    cs = ro['contention_sensitivity']
    if cs.get('estimate') is None:
        L.append(f"Contention sensitivity (pre-declared C5/E7; receipt {cs['exclusion_sha256'][:12]}…, commit {cs['freeze_commit'][:12]}): "
                 f"**no estimate** — all {cs['excluded_paired_seeds']} paired seeds are contention-excluded.")
    else:
        L.append(f"Contention sensitivity (pre-declared C5/E7; {cs['excluded_paired_seeds']} seeds excluded, receipt "
                 f"{cs['exclusion_sha256'][:12]}…, commit {cs['freeze_commit'][:12]}): Δ {f(cs['point_pp'])} pp {ci(cs['ci95_pp'])} "
                 f"on {cs['seeds']} seeds → {cs['label']}.")
    sw = ro['secondary_mean_R5_minus_R5W']
    if sw.get('estimate', True) is None:
        L.append(f"Attribution (E4, descriptive): no R5W estimate → **{sw['attribution']}** (default).")
    else:
        L.append(f"Attribution (E4, descriptive): mean(R5, R5-rep) − R5W = {f(sw['point_pp'])} pp {ci(sw['ci95_pp'])} on {sw['seeds']} seeds → "
                 f"**{sw['attribution']}**.")
    L += ['', '## What the result changes (PLAN r3 §1 decision table; the primary outcome alone selects the row)', '', next_step(p, sw)]
    L += ['', '## Single-fit and secondary contrasts (descriptive)', '', '| Contrast (loss pp; negative = fewer losses) | Pooled | K4S-120 | S-200 | Seeds |', '|---|---:|---:|---:|---:|']
    for l, rr in (('R5', 'R3a'), ('R5-rep', 'R3a'), ('R5', 'R3a-rep'), ('R3a-rep', 'R3a'), ('R5', 'R5-rep'), ('R5', 'R5W'), ('R5-rep', 'R5W')):
        k = f'{l} minus {rr}'
        if f'{k} [pooled]' in c:
            L.append(f'| {k} | ' + ' | '.join(f"{f(c[f'{k} [{a}]']['loss_change_pp'])} {ci(c[f'{k} [{a}]']['ci95_pp'])}" for a in ('pooled',)+ARMS)
                     + f" | {c[f'{k} [pooled]'].get('seeds', r['paired_seeds'])} |")
    L += ['', f"σ_fit ≈ {ro['sigma_fit_pp']['value']:.2f} pp ({ro['sigma_fit_pp']['df']}-df, descriptive).",
          '|R3a-rep − R3a| ≥ 4 pp: ' + ', '.join(f"{k.split('[')[1][:-1]} {'yes' if v else 'no'}" for k, v in ro['fit_seed_noise_ge_4pp'].items()) + '.']
    L += ['', '## Timing parity (pre-declared C4; non-outcome)', '', '| Arm | Student | Cutoff % | Student-default % | Wall p99 ms |', '|---|---|---:|---:|---:|']
    for arm, v in ro['timing_parity'].items():
        for s, m in v['per_student'].items():
            L.append(f"| {arm} | {s} | {m['cutoff_pct']:.1f} | {m['student_default_pct']:.1f} | {m['wall_ms_p99']:.0f} |")
        L.append(f"| {arm} | gap | {v['cutoff_gap_pp']:.1f} | {v['student_default_gap_pp']:.1f} | {'> 2 pp: disclosed (no exclusion, E10)' if v['gap_gt_2pp_disclosed'] else 'within 2 pp'} |")
    L += ['', '## Per student and arm', '', '| Student | Arm | Loss % [95% CI] | Cutoff % | Student-default % | Play % | Wall p50 / p99 ms | Overrun % |',
          '|---|---|---:|---:|---:|---:|---:|---:|']
    for key, a in r['arms'].items():
        s, arm = key.split(' ')
        L.append(f"| {s} | {arm} | {a['loss_pct']:.1f} {pc(a['loss_ci_pct'])} | {a['cutoff_pct']:.1f} | {a['student_default_pct']:.1f} | "
                 f"{a['play_pct']:.1f} | {a['wall_ms_p50']:.0f} / {a['wall_ms_p99']:.0f} | {a['overrun_pct']:.2f} |")
    L += ['', '## O composition and duplicates (§2; from the frozen label plan)', '',
          '| Set | Games | Dropped (no block) | Captured | Duplicates | Over cap | Kept | Kept K4S-120 | Kept S-200 | Plays | Student-default | Fallback |',
          '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for s, st in plan['stats'].items():
        L.append(f"| {s} | {st['games']} | {st['dropped_no_block']} | {st['captured']} | {st['duplicate']} | {st['over_cap']} | {st['kept']} | "
                 f"{st['kept_per_arm']['K4S-120']} | {st['kept_per_arm']['S-200']} | {st['plays']} | {st['student_default']} | {st['fallback']} |")
    for s, st in plan['stats'].items():
        tot = max(1, st['kept'])
        L.append(f"- {s} strata shares: " + (', '.join(f'{k} {100*v/tot:.1f}%' for k, v in sorted(st['strata'].items())) or 'none'))
    L += ['', '| 600-tick bucket | O states | Feature-only duplicates | Rate |', '|---:|---:|---:|---:|']
    for b, v in plan['feature_only_duplicates_by_600_tick_bucket'].items():
        L.append(f"| {b} | {v['states']} | {v['feature_duplicates']} | {100*v['rate']:.1f}% |")
    L += ['', f"|O| (scored roots) = {o_gate['rows']}; O_W roots = {ow_gate['roots']} (rows {ow_gate['rows']}); "
              f"O_W single-candidate root share = {100*ow_gate['single_candidate_root_share']:.1f}% (no dedup in O_W, E11)."]
    if diag:
        L += ['', '## O-holdout diagnostic (descriptive only; never a gate)', '', '| Student | Slice | Top-1 agreement | Gate accuracy | Listwise CE | Frozen objective |', '|---|---|---:|---:|---:|---:|']
        for s, slices in diag['students'].items():
            for sl, m in slices.items():
                L.append(f"| {s} | {sl} | {m['top1_agreement']:.3f} | {m['gate_accuracy']:.3f} | {m['listwise_ce']:.3f} | {m.get('frozen_objective', float('nan')):.3f} |")
    L += ['', '## Disclosures', ''] + [f'- {x}' for x in FIXED_DISCLOSURES + list(notes)]
    L += ['', '## Inputs', ''] + [f'- `{k}` sha256 {v}' for k, v in inputs.items()]
    return '\n'.join(L)+'\n'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--results', type=Path, default=confine.JOB/'analysis'/'results.json')
    ap.add_argument('--label-plan', type=Path, default=confine.JOB/'data'/'label-plan.json')
    ap.add_argument('--o-gate', type=Path, default=confine.JOB/'data'/'O-VERIFIED.json')
    ap.add_argument('--ow-gate', type=Path, default=confine.JOB/'data'/'OW-VERIFIED.json')
    ap.add_argument('--diagnostic', type=Path)
    ap.add_argument('--notes', default='[]', help='JSON list of extra disclosure lines (in addition to the fixed ones)')
    ap.add_argument('--out', type=Path, default=confine.REPORT_ROOT/'RESULTS.md')
    a = ap.parse_args()
    out = confine.writable(str(a.out), roles=('RESULTS.md',), roots=[confine.REPORT_ROOT])
    paths = dict(results=a.results, label_plan=a.label_plan, o_gate=a.o_gate, ow_gate=a.ow_gate)
    if a.diagnostic: paths['diagnostic'] = a.diagnostic
    docs = {k: json.loads(Path(v).read_text()) for k, v in paths.items()}
    notes = json.loads(a.notes)
    if not (isinstance(notes, list) and all(isinstance(x, str) for x in notes)): raise SystemExit('--notes must be a JSON list of strings')
    text = render(docs['results'], docs['label_plan'], docs['o_gate'], docs['ow_gate'], docs.get('diagnostic'),
                  {k: sha(v) for k, v in paths.items()}, notes)
    tmp = confine.writable(str(out)+'.tmp', roles=('RESULTS.md.tmp',), roots=[confine.REPORT_ROOT])
    tmp.write_text(text); tmp.replace(out)


if __name__ == '__main__':
    main()
