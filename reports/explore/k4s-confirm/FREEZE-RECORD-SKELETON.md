# PREREG-K4S freeze record: SKELETON (draft for coordinator 0523ae6f; NOT a freeze)

- Generated 2026-10-11T14:02:11Z by `make_freeze_skeleton.py` at worktree HEAD `38c195b8` (SHAs are of the working tree when generated).
- The coordinator re-verifies every SHA at the freeze commit, fills the blanks, signs, secret-scans, commits and pushes.
- Items marked **COORDINATOR** are decisions the prep worker must not make.

## A. Documents

| Item | Path | sha256 | Note |
|---|---|---|---|
| PREREG r3 | `reports/strategy_council_20260928/live-loop/v4/PREREG-K4S-DRAFT-r3.md` | `9650972d362299d87f8b1084d450f9a2dbbad516a494e97da6ba33d60fb68b3a` | must equal 9650972d… plus any coordinator errata (R2/R5); record errata separately |
| Conformance r2 | `reports/strategy_council_20260928/live-loop/v4/PREREG-K4S-CONFORMANCE-r2.md` | `ad681329c3c072e68e5486fff47db9812a1f35fd375eddb1ec0c815a1fd092b4` |  |
| Re-check r3 | `reports/strategy_council_20260928/live-loop/v4/PREREG-K4S-RECHECK-r3.md` | `eca937da3d0db042eb2fc3c7c3ef83b280a4bbab0148cc73e795e16fa0aa8fc9` |  |
| K4S spec (implementation contract) | `reports/explore/k4s-confirm/K4S-SPEC.md` | `d1bfb11c73f744ace219008632db54d38e0a5ddb4a80a3257af51c3e91f3e2ec` | interpretation choices I-1..I-5 in §9 need coordinator acceptance |

## B. Fills prepared by the prep worker (checklist F-2..F-8)

| Fill | Path | sha256 | Status |
|---|---|---|---|
| F-2 SD1 manifest (the SD1 hash is this sha at the freeze commit) | `reports/explore/k4s-confirm/SD1-MANIFEST.json` | `b8ce7b4c088e275894b9654a85923aacf428656e71433f60ec32bed1ae63ef76` | built on 03; `sd1_manifest.py check` passes |
| F-3 SD1 supersession text + exit-r3 pointer (DRAFT) | `reports/explore/k4s-confirm/SD1-SUPERSESSION-DRAFT.md` | `494622cdc5cfdeff7aed31c9a8ee03cff8c700253c5f3642ef8e9f53395a3f04` | coordinator issues; pointer added only by coordinator |
| F-4 seed audit | `reports/explore/k4s-confirm/seed-audit.json` | `6a11556f94b34cecc43e5f7ae0b3760c2af88285e30186094f08f2c7ab835c67` | PASS; **re-run at the freeze commit** (SEED-AUDIT-RECEIPT.md has the command) |
| F-4 seed audit receipt | `reports/explore/k4s-confirm/SEED-AUDIT-RECEIPT.md` | `e39ea169f9a0b2a2acac7074bb7e259ff7aa3824114033ce3f7b56cb52308a6e` |  |
| F-4 seed audit tool | `reports/explore/k4s-confirm/audit_seeds.py` | `70cfc4e6cd25717356998891a6ea31bc58b6a09970e503ff1ae79c14f394b871` |  |
| F-5 delta manifest (eight deltas vs T1 ef4c073a) | `reports/explore/k4s-confirm/DELTA-MANIFEST.json` | `7165b33cd3a50763072038700023a2e34db5af40b96ef6045bc8283819b66c7b` | identical 61, rebound 14, delta 15, new 36; `rebind.py verify` 0 failures |
| F-5 plan | `reports/explore/k4s-confirm/plan.json` | `38064dcdeff96fb006f6e261c246a458f423d97cc53278c3921888241c8d22cf` |  |
| F-5 runner | `reports/explore/k4s-confirm/run.py` | `eb7a323f1d8fadaeccf5c0870187ee0333426dffff4eaaca0518ed364e8d7684` |  |
| F-5 reducer (author: K4S prep worker, Opus) | `reports/explore/k4s-confirm/reduce.py` | `a0ac06b98ba37533d23983207a5125e30c1025e71867a5f60bf21ec4bf92a686` |  |
| F-5 independent verifier (author: Claude Haiku 5.5, did not read reduce.py) | `reports/explore/k4s-confirm/verifier/verify_k4s.py` | `62d292423df5fedf3976f8de017c0ba9aab6dfbd4bfe70d43180ca52af70ffaf` |  |
| F-5 release barrier | `reports/explore/k4s-confirm/barrier.py` | `01a58c66573ad6f7bf116fdf03bd075f4f81991f67a8aa5d8ddf47343ad0b063` |  |
| F-5 END reference driver (delta 8) | `reports/explore/k4s-confirm/end_reference.py` | `b6731acc5fa210bd669423cbcf01adfd13099b90b8795ef0420d138e385e8b6c` | logic-tested only; T1 K4 corpus copy needs coordinator authorisation |
| F-5 END pooling (delta 8) | `reports/explore/k4s-confirm/end_pool.py` | `c103022f3ca9a7fc8033aa688e0eda2de6f67fde6db819d1a42eac647afd33c1` |  |
| F-6 qualification receipt, 127x03 | `reports/explore/k4s-confirm/receipts/qualification-127x03.json` | `MISSING` | pending |
| F-6 qualification receipt, 127x04 | `reports/explore/k4s-confirm/receipts/qualification-127x04.json` | `MISSING` | pending |
| F-8 K4S Mac manifest (N2) | `reports/explore/k4s-confirm/mac/K4S-MAC-MANIFEST.json` | `215dfbf577209e11df2a5637e6419039ce7ec4299191134612a75d179a901152` | freeze with `mac/build_manifest.py --kernel … --freeze` |
| F-8 K4S Mac procedure | `reports/explore/k4s-confirm/mac/K4S-MAC-PROCEDURE.md` | `71cd257063814c3cc6b0761b68a79bf09ac0fbd6cff790fb51b4d2cbf7b1408b` |  |
| F-8 K4S Mac script | `reports/explore/k4s-confirm/mac/measure_k4s.py` | `58e16dea8947cd35ec83f4ac0a1b50fe28fac4d22320ecef8c1eeda2f3859ad3` |  |

Pins carried from T1 / r3 (verify at the freeze):
- T1 runtime `ef4c073a4c69e85aea0b6f9af9c1118ca8888a59` (branch `origin/worker/t1-op7-apt-20261010`); inherited S1 runtime pin `f81f3655…`.
- Native `44874fd6047aa53f8f5c46fd3a77e4e2c8672f98dbcf6d758fbf90ee043a5be2`; opponent v1 `d77005d59d6ed40ce7f9bfcfde569b54958bebf056e00653b10dcee3957272ed`.
- SD1 checkpoint `37509a43…`, calibration `e3003533…`, threshold 0.5005528330802917; guard decks `6d51628b…`.
- 125-state qualification corpus `8b188918…` / `86ecbb60…`; T1 K4 speed corpus `a97b1fbf…` (END only).

## C. Reviews

| Review | File | Verdict |
|---|---|---|
| RESPONSE-CORE-r1.md | `reports/explore/k4s-confirm/reviews/RESPONSE-CORE-r1.md` | see file |
| SOL-REVIEW-CORE-r1.md | `reports/explore/k4s-confirm/reviews/SOL-REVIEW-CORE-r1.md` | see file |
| SOL-REVIEW-MAC-END-r1.md | `reports/explore/k4s-confirm/reviews/SOL-REVIEW-MAC-END-r1.md` | see file |

## D. Coordinator-only items (blank until the freeze)

| Item | Value |
|---|---|
| F-1 c\* record | **c\* = 0.9** (pre-filled from commit `6ef5e2ff`, COORDINATOR.md 11:46Z): phase E reduced 11:38:26Z, committed `b577a255` 11:40:02Z; receipt `reports/explore/x4s2/receipts/results-phaseACE.json` sha256 `d2b32b9a2e3ee86fc857b68b74ea0fdf62b63b3975c8b57ae4ad8f000ec7ef89`; d180 = −2.2 pp [−5.2, +0.8], lower bound not > 0 → c\* = 0.9, sequence H1–H7 with H4; rule text locked at `daba6859` (09:30:42Z) before phase E reduction. Coordinator confirms: ________ |
| F-7 host set (≥ 2 of 01/03/04/08) | ________ (**proposal: {127x03, 127x04}**, per coordinator 2026-10-11 ~13:58Z; both qualified in prep, receipts below; 04 released early by perception, receipt 5f59f7f8) |
| F-7 transport-retirement declaration per host | ________ (A2 complete; 03/08 transports retired per c2cef696; 04 allocation released per 5f59f7f8) |
| F-9 Q1–Q13 decision record | ________ (defaults as written in r3 §8; restate Q13 order and Q12 "TIERS stands") |
| K4S-SPEC §9 interpretation choices I-1..I-5 accepted | ________ |
| Errata applied at freeze (RECHECK-r3 R2/R5: Q13 r1-order .705/.366) | ________ |
| F-10 attestation: T1/TIERS outcomes open at freeze time? | ________ |
| F-10 attestation: no PREREG-K4S text change since RECHECK-r3 except N1–N3, M1–M6 and F-1..F-9 fills | ________ |
| SD1 supersession issued (text, UTC) | ________ |
| Freeze commit / UTC / signer | ________ |

## E. T1 END host check (read-only, committed docs; coordinator request 13:58Z)

**Finding: the T1 END pooled fleet reference needs neither 127x03 nor 127x04 for compute.**
- **Rule.** TIERS Amendment 1 (`PREREG-SEARCH-TIERS-AMENDMENT-1-20261010.md` l.15): "the pool's host list equals the reporting host set, with a fixed reference slot per host". l.7: excluding a counted host makes the pool fail closed.
- **T1 FREEZE-T1.md** (Amendment 1 section): "The reference host set must equal all hosts with counted reporting/replacement blocks."
- **Counted hosts are 127x01 and 127x08 only.**
  - `reports/explore/t1/receipts/host-set-0108-20261010.json`: `reporting_hosts` ["127x01","127x08"], host totals 1535 / 1537; `prior_hosts` included 03, dropped at 17:30Z ("03 perception transport parent alone exceeds frozen OP4").
  - `FROZEN-T1.json` `reporting_hosts` ["127x01","127x08"].
  - 04 was a forbidden T1 host (T1 `plan.json` `forbidden_hosts`).
- **Storage caveat.** 03 holds T1's SHA-validated, read-only corpus durability copy (FREEZE-T1.md l.55, `corpus-reviewed-03-r1`; the other copy is on 05). T1 END waits for corpus approval (T1 `plan.json` `fleet_reference_schedule`). K4S on 03 must leave those files untouched, and K4S never reads them without coordinator authorisation (K4S END needs `K4-states.pkl`).
- **Residual ambiguity** (for the coordinator). T1 `plan.json` `fleet_reference_schedule` says "all qualified remaining named hosts", which predates the 17:30Z 01+08 narrowing. Amendment 1's counted-host rule is the specific, signed rule.
- **Consequence.** A K4S {03, 04} host set does not overlap T1 reporting or T1 END compute (r3 §4.2), regardless of T1's END timing. If T1 lost 08, substituting 03/04 into T1 END would need a T1 reference amendment; that is T1's decision, not K4S's.

## F. Known blockers and open items at generation time

- **TIERS blocker (outside K4S):** frozen `measure_tiers.py` (sha `5d7de8e3…`) uses `math.isfinite` at l.70 without `import math`; every authorised Mac session with `amendment_1` true would raise NameError. Needs a TIERS-side amendment before any Mac session (and so before the K4S Mac cell, which runs after TIERS §7).
- END cells cannot be executed before END: the T1 K4 corpus lives only under T1 job dirs; the coordinator must authorise a read-only SHA-verified copy.
- Qualification receipts exist for 127x03 and 127x04 (see B). Any other host needs its own qualification (`QUALIFICATION.md`).
- Re-run qualification on both hosts if any runtime byte changes after the receipts (source binding).
- Excluded smoke (r3 §4.1) after the freeze on all named hosts at nice 10 under the T1 supervisor; it also exercises the supervisor STOP path.
