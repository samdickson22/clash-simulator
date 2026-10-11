"""Write FREEZE-RECORD-SKELETON.md: every PREREG-K4S freeze fill with its current SHA, plus blanks for
coordinator-only items. A draft for the coordinator; it freezes nothing. Re-run after any fill changes."""
import hashlib, json, subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
V4 = 'reports/strategy_council_20260928/live-loop/v4'


def sha(rel):
    p = ROOT/rel
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else 'MISSING'


def row(label, rel, note=''):
    return f'| {label} | `{rel}` | `{sha(rel)}` | {note} |'


def main():
    head = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', '--short=8', 'HEAD'], text=True).strip()
    utc = subprocess.check_output(['date', '-u', '+%FT%TZ'], text=True).strip()
    K = 'reports/explore/k4s-confirm'
    delta = json.loads((HERE/'DELTA-MANIFEST.json').read_text())
    q = HERE/'receipts/qualification-127x03.json'
    qual = json.loads(q.read_text()) if q.exists() else {}
    q4 = HERE/'receipts/qualification-127x04.json'
    qual4 = json.loads(q4.read_text()) if q4.exists() else {}
    reviews = sorted(p.name for p in (HERE/'reviews').glob('*.md')) if (HERE/'reviews').exists() else []
    lines = [
        '# PREREG-K4S freeze record: SKELETON (draft for coordinator 0523ae6f; NOT a freeze)',
        '',
        f'- Generated {utc} by `make_freeze_skeleton.py` at worktree HEAD `{head}` (SHAs are of the working tree when generated).',
        '- The coordinator re-verifies every SHA at the freeze commit, fills the blanks, signs, secret-scans, commits and pushes.',
        '- Items marked **COORDINATOR** are decisions the prep worker must not make.',
        '',
        '## A. Documents',
        '',
        '| Item | Path | sha256 | Note |',
        '|---|---|---|---|',
        row('PREREG r3', f'{V4}/PREREG-K4S-DRAFT-r3.md', 'must equal 9650972d… plus any coordinator errata (R2/R5); record errata separately'),
        row('Conformance r2', f'{V4}/PREREG-K4S-CONFORMANCE-r2.md'),
        row('Re-check r3', f'{V4}/PREREG-K4S-RECHECK-r3.md'),
        row('K4S spec (implementation contract)', f'{K}/K4S-SPEC.md', 'interpretation choices I-1..I-5 in §9 need coordinator acceptance'),
        '',
        '## B. Fills prepared by the prep worker (checklist F-2..F-8)',
        '',
        '| Fill | Path | sha256 | Status |',
        '|---|---|---|---|',
        row('F-2 SD1 manifest (the SD1 hash is this sha at the freeze commit)', f'{K}/SD1-MANIFEST.json', 'built on 03; `sd1_manifest.py check` passes'),
        row('F-3 SD1 supersession text + exit-r3 pointer (DRAFT)', f'{K}/SD1-SUPERSESSION-DRAFT.md', 'coordinator issues; pointer added only by coordinator'),
        row('F-4 seed audit', f'{K}/seed-audit.json', 'PASS; **re-run at the freeze commit** (SEED-AUDIT-RECEIPT.md has the command)'),
        row('F-4 seed audit receipt', f'{K}/SEED-AUDIT-RECEIPT.md'),
        row('F-4 seed audit tool', f'{K}/audit_seeds.py'),
        row('F-5 delta manifest (eight deltas vs T1 ef4c073a)', f'{K}/DELTA-MANIFEST.json',
            f"identical {delta['counts']['identical']}, rebound {delta['counts']['rebound']}, delta {delta['counts']['delta']}, new {delta['counts']['new']}; `rebind.py verify` 0 failures"),
        row('F-5 plan', f'{K}/plan.json'),
        row('F-5 runner', f'{K}/run.py'),
        row('F-5 reducer (author: K4S prep worker, Opus)', f'{K}/reduce.py'),
        row('F-5 independent verifier (author: Claude Haiku 5.5, did not read reduce.py)', f'{K}/verifier/verify_k4s.py'),
        row('F-5 release barrier', f'{K}/barrier.py'),
        row('F-5 END reference driver (delta 8)', f'{K}/end_reference.py', 'logic-tested only; T1 K4 corpus copy needs coordinator authorisation'),
        row('F-5 END pooling (delta 8)', f'{K}/end_pool.py'),
        row('F-6 qualification receipt, 127x03', f'{K}/receipts/qualification-127x03.json', qual.get('verdict', 'pending')),
        row('F-6 qualification receipt, 127x04', f'{K}/receipts/qualification-127x04.json', qual4.get('verdict', 'pending')),
        row('F-8 K4S Mac manifest (N2)', f'{K}/mac/K4S-MAC-MANIFEST.json', 'freeze with `mac/build_manifest.py --kernel … --freeze`'),
        row('F-8 K4S Mac procedure', f'{K}/mac/K4S-MAC-PROCEDURE.md'),
        row('F-8 K4S Mac script', f'{K}/mac/measure_k4s.py'),
        '',
        'Pins carried from T1 / r3 (verify at the freeze):',
        '- T1 runtime `ef4c073a4c69e85aea0b6f9af9c1118ca8888a59` (branch `origin/worker/t1-op7-apt-20261010`); inherited S1 runtime pin `f81f3655…`.',
        '- Native `44874fd6047aa53f8f5c46fd3a77e4e2c8672f98dbcf6d758fbf90ee043a5be2`; opponent v1 `d77005d59d6ed40ce7f9bfcfde569b54958bebf056e00653b10dcee3957272ed`.',
        '- SD1 checkpoint `37509a43…`, calibration `e3003533…`, threshold 0.5005528330802917; guard decks `6d51628b…`.',
        '- 125-state qualification corpus `8b188918…` / `86ecbb60…`; T1 K4 speed corpus `a97b1fbf…` (END only).',
        '',
        '## C. Reviews',
        '',
        '| Review | File | Verdict |',
        '|---|---|---|',
    ] + [f'| {n} | `{K}/reviews/{n}` | see file |' for n in reviews] + [
        '',
        '## D. Coordinator-only items (blank until the freeze)',
        '',
        '| Item | Value |',
        '|---|---|',
        '| F-1 c\\* record | **c\\* = 0.9** (pre-filled from commit `6ef5e2ff`, COORDINATOR.md 11:46Z): phase E reduced 11:38:26Z, committed `b577a255` 11:40:02Z; receipt `reports/explore/x4s2/receipts/results-phaseACE.json` sha256 `d2b32b9a2e3ee86fc857b68b74ea0fdf62b63b3975c8b57ae4ad8f000ec7ef89`; d180 = −2.2 pp [−5.2, +0.8], lower bound not > 0 → c\\* = 0.9, sequence H1–H7 with H4; rule text locked at `daba6859` (09:30:42Z) before phase E reduction. Coordinator confirms: ________ |',
        '| F-7 host set (≥ 2 of 01/03/04/08) | ________ (**proposal: {127x03, 127x04}**, per coordinator 2026-10-11 ~13:58Z; both qualified in prep, receipts below; 04 released early by perception, receipt 5f59f7f8) |',
        '| F-7 transport-retirement declaration per host | ________ (A2 complete; 03/08 transports retired per c2cef696; 04 allocation released per 5f59f7f8) |',
        '| F-9 Q1–Q13 decision record | ________ (defaults as written in r3 §8; restate Q13 order and Q12 "TIERS stands") |',
        '| K4S-SPEC §9 interpretation choices I-1..I-5 accepted | ________ |',
        '| Errata applied at freeze (RECHECK-r3 R2/R5: Q13 r1-order .705/.366) | ________ |',
        '| F-10 attestation: T1/TIERS outcomes open at freeze time? | ________ |',
        '| F-10 attestation: no PREREG-K4S text change since RECHECK-r3 except N1–N3, M1–M6 and F-1..F-9 fills | ________ |',
        '| SD1 supersession issued (text, UTC) | ________ |',
        '| Freeze commit / UTC / signer | ________ |',
        '',
        '## E. T1 END host check (read-only, committed docs; coordinator request 13:58Z)',
        '',
        '**Finding: the T1 END pooled fleet reference needs neither 127x03 nor 127x04 for compute.**',
        '- **Rule.** TIERS Amendment 1 (`PREREG-SEARCH-TIERS-AMENDMENT-1-20261010.md` l.15): "the pool\'s host list equals the reporting host set, with a fixed reference slot per host". l.7: excluding a counted host makes the pool fail closed.',
        '- **T1 FREEZE-T1.md** (Amendment 1 section): "The reference host set must equal all hosts with counted reporting/replacement blocks."',
        '- **Counted hosts are 127x01 and 127x08 only.**',
        '  - `reports/explore/t1/receipts/host-set-0108-20261010.json`: `reporting_hosts` ["127x01","127x08"], host totals 1535 / 1537; `prior_hosts` included 03, dropped at 17:30Z ("03 perception transport parent alone exceeds frozen OP4").',
        '  - `FROZEN-T1.json` `reporting_hosts` ["127x01","127x08"].',
        '  - 04 was a forbidden T1 host (T1 `plan.json` `forbidden_hosts`).',
        '- **Storage caveat.** 03 holds T1\'s SHA-validated, read-only corpus durability copy (FREEZE-T1.md l.55, `corpus-reviewed-03-r1`; the other copy is on 05). T1 END waits for corpus approval (T1 `plan.json` `fleet_reference_schedule`). K4S on 03 must leave those files untouched, and K4S never reads them without coordinator authorisation (K4S END needs `K4-states.pkl`).',
        '- **Residual ambiguity** (for the coordinator). T1 `plan.json` `fleet_reference_schedule` says "all qualified remaining named hosts", which predates the 17:30Z 01+08 narrowing. Amendment 1\'s counted-host rule is the specific, signed rule.',
        '- **Consequence.** A K4S {03, 04} host set does not overlap T1 reporting or T1 END compute (r3 §4.2), regardless of T1\'s END timing. If T1 lost 08, substituting 03/04 into T1 END would need a T1 reference amendment; that is T1\'s decision, not K4S\'s.',
        '',
        '## F. Known blockers and open items at generation time',
        '',
        '- **TIERS blocker (outside K4S):** frozen `measure_tiers.py` (sha `5d7de8e3…`) uses `math.isfinite` at l.70 without `import math`; every authorised Mac session with `amendment_1` true would raise NameError. Needs a TIERS-side amendment before any Mac session (and so before the K4S Mac cell, which runs after TIERS §7).',
        '- END cells cannot be executed before END: the T1 K4 corpus lives only under T1 job dirs; the coordinator must authorise a read-only SHA-verified copy.',
        '- Qualification receipts exist for 127x03 and 127x04 (see B). Any other host needs its own qualification (`QUALIFICATION.md`).',
        '- Re-run qualification on both hosts if any runtime byte changes after the receipts (source binding).',
        '- Excluded smoke (r3 §4.1) after the freeze on all named hosts at nice 10 under the T1 supervisor; it also exercises the supervisor STOP path.',
    ]
    (HERE/'FREEZE-RECORD-SKELETON.md').write_text('\n'.join(lines)+'\n')
    print('written')


if __name__ == '__main__':
    main()
