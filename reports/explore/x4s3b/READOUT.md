# X4S-3b (U2): fit-seed noise σ_fit in deployment loss: pre-declared readout (exploration, NEVER ADOPTABLE)

Pre-declared before any X4S-3b fit or game exists. Plan: coordinator adoption U2 (COORDINATOR 2026-10-13 01:15Z) of
`/mpac/sdicks02/jobs/clasher/coordinator-notes/fleet-utilization-plan-r1.md` Item 2.

**Status: exploration only, NEVER ADOPTABLE.** No student here enters any frozen manifest (SD1 stays R3a). Nothing
here is cited in K4S, TIERS or T1 reporting. No T1, K4S or TIERS outcome is read. No held-out deck or split is used.

## Design
- **Harness:** the reviewed X4S-3 harness on 127x01, changed only by the constants in [driver.py](driver.py),
  [run_fit.sh](run_fit.sh) and [reduce.py](reduce.py) (diff against `reports/explore/x4s3/` in the review packet).
  supervise.py, run.py, runtime.sh, calibrate.py, the trainer and the game code are the J copies, byte-identical.
- **Job prefix:** J2 = `/mpac/sdicks02/jobs/clasher/x4s3b-fitseed-20261013/`, built from plain `cp -a` copies of
  J = `/mpac/sdicks02/jobs/clasher/x4s3-student-scale-20261012/{base,fit,inputs}`. J is only read, never written.
- **New students:** two r1-only fits with the R3a recipe and the frozen R3 trainer, 2,500 steps each, differing from
  R3a-rep (train seed 2026101202) only in the train seed:
  - **R3a-rep2**, train seed 2026101204;
  - **R3a-rep3**, train seed 2026101205.

  Each is calibrated by the unchanged label-free R3 rule (play rate pinned to 34.6%).
- **Games:** paired reuse of the X4S-3 reporting bank: the same 1,200 indices, with retired 0–32 still retired
  (1,167 paired seeds), both arms K4S-120 and S-200, same host, harness, cores and opponent. The existing R3a and
  R3a-rep game directories are copied into J2 so that the reducer pairs on identical seeds. This is paired reuse, as
  in X4S2; the X4S-3 seeds are not fresh.
- **Scheduling:** one fit at a time on the GPU; a fit never runs beside an S-200 phase (the X4S-3 union rule, here
  applied to the replicate fits); a fit may run beside a K4S-120 phase. Dispatch is withheld while MemAvailable
  < 24 GiB or memory PSI some avg10 > 10%.
- **Stop:** fixed N per student; **STOP_AT 2026-10-13T09:35:00Z** (set at launch per Sol r1 finding 6; the driver
  refuses to start before 01:35:00Z, i.e. STOP_AT ≤ launch + 8 h), or the coordinator's "STOP U2" at the X4S-4 GO,
  whichever is first.
- **Counting rule after a STOP (pre-declared, outcome-independent; Sol r1 finding 5).** The inherited reducer does not
  check completion times, so the owner enforces this by the `--students` list, recorded in RESULTS: a student is
  reduced only if both of its reporting phases ended with supervisor-exit reason `null` and rc 0 before any STOP U2
  or STOP_AT. A student whose phase was cut by STOP or STOP_AT is **not reduced** in this run, even if seed
  retirement would make it formally complete over the remaining indices. Phases interrupted by the inherited
  memory/console guards follow X4S-3's declared rule (started seeds retired for every later phase, phase resumed).
- **Reducer invocation:** `--job J2 --out J2/analysis/<name>.json` only; never an output under J. A copy goes to the
  05 mirror under the J2 prefix.

## Readout (reducer: x4s3b/reduce.py on J2 or its 05 mirror)
Inputs are only students for which every non-retired index is terminal in both arms (the X4S-3 fixed-N assertion).
The shared paired-seed bootstrap is unchanged: 5,000 reps, seed 2026101201, resampling seeds.

For each pair (i, j) of the r1-only fits {R3a-rep, R3a-rep2, R3a-rep3}:
- **D_ij** = the pooled paired loss difference, in pp: per seed, the mean over K4S-120 and S-200 of
  loss_i − loss_j, averaged over the paired seeds (the reducer's existing `[pooled]` contrast);
- **V_ij** = the bootstrap variance of D_ij over the 5,000 resamples, in pp² (`boot_var_pp2`).

Then

    σ̂_fit² = max(0, mean_ij (D_ij² − V_ij) / 2),    σ̂_fit = √σ̂_fit²

over the available pairs:
- **final:** all 3 pairs (rep2−rep, rep3−rep, rep3−rep2), 3 fits, **2 df**;
- **interim:** if only R3a-rep2 is complete when the run stops, the single pair rep2−rep (1 df), labelled interim.

Reasoning: under equal expected loss per seed, E[D_ij²] = 2σ_fit² + V_ij, so each term is an unbiased estimate of
σ_fit². The three pairs share fits, so they are not independent; the df count is fits − 1.

**Reported alongside, descriptively:** R3a-rep2 − R3a and R3a-rep3 − R3a (pooled and per arm). R3a is not in the
σ̂_fit estimate, because it also differs by the 212,542 G-04 rows and its S-200 phase ran in the 13:10–13:34Z thrash
window. Per-arm D_ij, the per-student/arm table and the existing X4S-3 contrasts are also emitted by the reducer.
No S-200 thrash sensitivity is computed for X4S-3b (the window touched only R3a).

**Interpretation rule (pre-declared, from the plan):** if σ̂_fit ≥ 1.0 pp, the coordinator records in the X4S-4
interpretation that its true false-positive rate for "helps" is about 10–12% (X4S-4 PLAN [E2]), that the "no
material effect" band is optimistic, and that X4S-5 or SD2 should spend compute on more fits rather than more games.
If σ̂_fit < 1.0 pp, X4S-4's assumed σ_fit = 0.65 pp stands as not contradicted. With 2 df the estimate is very
imprecise either way; that is disclosed with the number.

## Disclosures fixed in advance
- The new games carry the run.py study label `X4S-3 exploration, NEVER ADOPTABLE` (game code unchanged); the job
  prefix and student IDs identify them as X4S-3b.
- Paired reuse of the X4S-3 seeds; the same five X decks and the one opponent (v1).
- External read-only inputs, as in X4S-3: the R1 human store and corpus
  (`exit-r1-student-screen-20261009-r1`), the R2 held-out calibration slice (`exit-r2-20261010-r1/heldout-corpus`),
  the clasher-gpu env, and the 01 repo venv used by runtime.sh.
- `run_fit.sh` keeps the baseline git mode 100644 (Sol r1 finding 1: the r1 candidate had 100755, restored);
  the driver invokes it through `bash`.
- The driver rewrites each new student runtime's `policy.checkpoint` to the J2 copy of main02.pt (same SHA pin
  d77005d5, asserted by run.py), so the reporting games read nothing from J.

## Amendment U2b (pre-declared before any U2b game; COORDINATOR d28ce370)
R3a-rep3's games (fit and calibration done on 01: checkpoint 43621ce4, threshold 0.49953630566596985) run on
127x03 and 127x04, CPU only, under `/mpac/sdicks02/jobs-x4s3b/rep3-20261013/`, with the X4S-3 runtime copy
`rt-R3a-rep3`. Only changes: host tuples in run.py:300, supervise.py:72 (→ 127x03/127x04) and reduce.py:53
(→ 01/03/04), the two checkpoint paths in the runtime plan, and index files.
- **Split:** 03 plays indices 33–615 ([idx-rep3-03.json](idx-rep3-03.json), 583), 04 plays 616–1199
  ([idx-rep3-04.json](idx-rep3-04.json), 584); each host runs K4S-120 then S-200, so both arms of a seed share a host.
  Seeds, decks, opponent, cores 0–49, nice 10 are unchanged.
- **Identity gate per host:** K4S-none(R3a) on X4S qualification indices [0, 1] must reproduce `command_sha256`
  af630cf0… and d530982b…; a host with any mismatch is not used.
- **Stop:** `--stop-at 2026-10-13T13:30:00Z` in every supervisor; STOP before 13:30Z; throughput guard: STOP if
  K4S-120 runs below about 13 games/min on a host.
- **Counting rule:** rep3 is reduced only if all four rep3 phases (2 hosts × 2 arms) end rc 0, reason null, with all
  their indices, before STOP; otherwise the interim readout (1 pair) stands.
- **Primary final readout:** the 3-pair σ̂_fit formula above, with rep3's games from 03/04. The pairs rep3−rep and
  rep3−rep2 cross hosts: a host effect δ adds about δ² to each of those two terms, so σ̂_fit is biased **upward**
  (conservative for the ≥ 1.0 pp question). Disclosed with the number.
- **Secondary (only if complete):** a host control, R3a-rep2 re-played as rep2′ on the same split and hosts
  (S-200 first, then K4S-120), best effort. If rep2′ completes in both arms on both hosts (same counting rule),
  report the within-host estimate σ̂_w² = max(0, mean of (D²−V)/2 over {rep2−rep on 01, rep3−rep2′ on 03/04}), 3 fits,
  df 2, and rep2′−rep2 (same fit, host 03/04 vs 01) descriptively as the host effect. If only rep2′ S-200 completes,
  report rep2′−rep2 [S-200] descriptively only.
