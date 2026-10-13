"""Render X4S-4 RESULTS.md (exploration, NEVER ADOPTABLE; PLAN r3 frozen at 87809ae0). Stdlib only.
r3 after Sol script review r2 (R2-F1, R2-F9). Every read and write goes through x4s4io.

Inputs are FIXED job paths, not caller choices, and their identities must chain (R2-F9): <job>/analysis/results.json
(reduce.py; its contention view names the frozen receipt SHA and commit), <job>/data/label-plan.json (the O gate must
carry this plan's SHA, and the plan's kept O count must cover the gate's rows within the 0.1% drop limit),
<job>/data/O-VERIFIED.json, <job>/data/OW-VERIFIED.json (must carry the O gate's SHA) and, if present,
<job>/analysis/diagnostic.json (must carry the HOLDOUT-VERIFIED SHA and all five students). A missing diagnostic is
rendered as an explicit "unavailable" entry per student (it stays descriptive; it never changes the outcome rule).
The output is confined to <repo>/reports/explore/x4s4/RESULTS.md.
r5 (Sol r4 R4-F4, R4-F6): --contention-sha and --freeze-commit are required; the reducer's full C5 freeze gate
(reduce.verify_freeze) runs on them BEFORE results.json is opened; the model identity set must equal the reduced
student list exactly and the diagnostic must carry staged identities for all five students.
Always rendered (Sol F14): the primary pooled and separately by arm; prefix seed counts for the primary and for R5W;
the contention view (an explicit no-estimate line when it is empty); the composition table; the fixed control-data
disclosures; and the decision-table row selected by the primary outcome, with its harmful/attribution follow-up.
"""
import argparse, hashlib, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import x4s4io as io, studytree                   # noqa: E402

STUDENTS = ('R3a', 'R3a-rep', 'R5', 'R5-rep', 'R5W')

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
def sha(p): return io.sha256_file(str(p))


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
    L += ['', '## O-holdout diagnostic (descriptive only; never a gate)', '', '| Student | Slice | Top-1 agreement | Gate accuracy | Listwise CE | Frozen objective |', '|---|---|---:|---:|---:|---:|']
    for s in STUDENTS:
        slices = (diag or {}).get('students', {}).get(s)
        if not slices:
            L.append(f"| {s} | — | unavailable | unavailable | unavailable | unavailable |"); continue
        for sl, m in slices.items():
            L.append(f"| {s} | {sl} | {m['top1_agreement']:.3f} | {m['gate_accuracy']:.3f} | {m['listwise_ce']:.3f} | {m['frozen_objective']:.3f} |")
    if not diag:
        L.append('**The O-holdout diagnostic is unavailable (not completed before the hard stop, or its guarded run did not pass); disclosed, descriptive only.**')
    L += ['', '## Disclosures', ''] + [f'- {x}' for x in FIXED_DISCLOSURES + list(notes)]
    L += ['', '## Inputs', ''] + [f'- `{k}` sha256 {v}' for k, v in inputs.items()]
    return '\n'.join(L)+'\n'


HELDOUT64_SHA = '0ecce0f0f410ff7f1093994cdb62b44c4c141c3a4bddb237cf1427b0a512818f'


def staged_students(J, plan_path):
    """The five staged students' current checkpoint/threshold (R3a from the reduction plan, the rest from READY)."""
    out = {}
    for sid in STUDENTS:
        s = io.read_json(plan_path, 16 << 20)['student'] if sid == 'R3a' else io.read_json(f'{J}/rt-{sid}/READY.json', 4 << 20)['student']
        out[sid] = dict(checkpoint_sha256=s['checkpoint_sha256'], threshold=s.get('threshold'))
    return out


def authenticate(J, contention_sha, freeze_commit, repo=None):
    """R2-F9, R3-F4, R4-F4, R4-F6. Order matters: the FULL C5 freeze gate of the reducer (reduce.verify_freeze: readonly
    single-link receipt, SHA, committed bytes by the verified git walk on origin/main, schema, phase set, every phase's
    census/launch/exit/SETTLED/block/game SHA/size/st_mtime_ns inventory, retired.json) runs on the declared freeze
    BEFORE results.json or any other outcome-bearing input is opened. Then every input identity must chain to the
    current evidence: results name exactly that receipt/commit; the reduced student list equals the identity set
    exactly (no omission, extra or duplicate) and equals the staged students; gates match and are re-authenticated;
    the diagnostic covers exactly the five students with the staged checkpoints/thresholds, the fixed held-out64 and
    the authenticated holdout gate. Returns (docs, input SHAs)."""
    import reduce
    def need(cond, msg):
        if not cond: raise SystemExit('write_report.py: input binding failed: '+msg)
    reduce.verify_freeze(J, contention_sha, freeze_commit, repo or io.REPO)        # raises SystemExit on any failure
    paths = dict(results=f'{J}/analysis/results.json', label_plan=f'{J}/data/label-plan.json', o_gate=f'{J}/data/O-VERIFIED.json',
                 ow_gate=f'{J}/data/OW-VERIFIED.json')
    need(studytree.guarded_output(J, paths['results']) is not None, 'results.json has no passed guard receipt (R7: guarded reduce.py)')
    need(studytree.guarded_output(J, paths['label_plan']) is not None, 'the label plan has no passed guard receipt (R8-F4)')
    # R7: a diagnostic counts only if its guarded run passed; otherwise it is rendered as unavailable (disclosed)
    if io.lexists(f'{J}/analysis/diagnostic.json') and studytree.guarded_output(J, f'{J}/analysis/diagnostic.json') is not None:
        paths.update(diagnostic=f'{J}/analysis/diagnostic.json', holdout_gate=f'{J}/data/HOLDOUT-VERIFIED.json')
    docs = {k: io.read_json(v, 1 << 30) for k, v in paths.items()}
    shas = {k: sha(v) for k, v in paths.items()}
    need(docs['o_gate'].get('label_plan_sha256') == shas['label_plan'], 'O gate was not verified against this label plan')
    need(docs['ow_gate'].get('o_gate_sha256') == shas['o_gate'], 'O_W gate was not verified against this O gate')
    kept, rows = docs['label_plan']['stats']['O']['kept'], docs['o_gate']['rows']
    need(rows <= kept and kept-rows <= 0.001*kept+1, f'label plan kept O ({kept}) does not cover the gate rows ({rows})')
    r = docs['results']; ids = r.get('identities')
    need(isinstance(ids, dict), 'results carry no study identities (not produced by the r4 reducer)')
    reduced = r.get('students')
    need(isinstance(reduced, list) and len(set(reduced)) == len(reduced) and set(STUDENTS[:4]) <= set(reduced) <= set(STUDENTS),
         'reduced student list must hold the four primary students, only declared students, no duplicates')
    need(isinstance(ids.get('students'), dict) and sorted(ids['students']) == sorted(reduced), 'model identities must cover exactly the reduced students')
    cs = r['readout']['contention_sensitivity']
    need(ids.get('contention_receipt_sha256') == contention_sha == cs.get('exclusion_sha256') and ids.get('freeze_commit') == freeze_commit
         == cs.get('freeze_commit'), 'results were not reduced under the authenticated C5 freeze')
    retired = f'{J}/driver/retired.json'
    need((sha(retired) if io.lexists(retired) else None) == ids['retired_sha256'], 'retired.json changed since the reduction')
    need(sha(ids['plan_path']) == ids['plan_sha256'], 'the reduction plan changed')
    need(ids['gates'].get('O') == shas['o_gate'] and ids['gates'].get('OW') == shas['ow_gate'], 'results were reduced under other data gates')
    for mode in ('O', 'OW'):
        try: studytree.authenticate_gate(J, mode)
        except io.Refusal as e: need(False, f'{mode} corpus no longer matches its gate: {e}')
    staged = staged_students(J, ids['plan_path'])
    need(all(ids['students'][k] == staged[k] for k in reduced), 'reduced student checkpoints/thresholds differ from the staged students')
    if 'diagnostic' in docs:
        d = docs['diagnostic']
        try: _, hsha, _ = studytree.authenticate_gate(J, 'holdout')
        except io.Refusal as e: need(False, f'holdout corpus no longer matches its gate: {e}')
        need(d.get('holdout_gate_sha256') == shas['holdout_gate'] == hsha, 'diagnostic was not run on the verified O-holdout')
        need(d.get('heldout64_sha256') == HELDOUT64_SHA, 'diagnostic did not use the fixed R1 held-out64 slice')
        need(sorted(d.get('students', {})) == sorted(STUDENTS), 'diagnostic must cover exactly the five students')
        dc = d.get('student_checkpoints')
        need(isinstance(dc, dict) and sorted(dc) == sorted(STUDENTS)
             and all(dict(checkpoint_sha256=dc[k].get('checkpoint_sha256'), threshold=dc[k].get('threshold')) == staged[k] for k in STUDENTS),
             'diagnostic student checkpoints/thresholds differ from the staged students')
    return docs, shas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--contention-sha', required=True, help='SHA-256 of the frozen C5 receipt (as given to reduce.py)')
    ap.add_argument('--freeze-commit', required=True, help='commit on origin/main that contains the C5 receipt')
    ap.add_argument('--notes', default='[]', help='JSON list of extra disclosure lines (in addition to the fixed ones)')
    ap.add_argument('--out', default=io.REPORT_ROOT+'/RESULTS.md')
    a = ap.parse_args()
    studytree.require_guard('write_report')                        # R7: runs only under guard.py --readout
    io.check_writable(a.out, report=True)
    docs, shas = authenticate(io.JOB, a.contention_sha, a.freeze_commit)
    notes = json.loads(a.notes)
    if not (isinstance(notes, list) and all(isinstance(x, str) for x in notes)): raise SystemExit('--notes must be a JSON list of strings')
    text = render(docs['results'], docs['label_plan'], docs['o_gate'], docs['ow_gate'], docs.get('diagnostic'), shas, notes)
    io.replace_bytes(a.out, text.encode(), report=True)


if __name__ == '__main__':
    main()
