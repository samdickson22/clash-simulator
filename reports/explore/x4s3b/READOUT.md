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
- **Stop:** fixed N per student; STOP_AT 2026-10-13T11:00:00Z (the driver refuses to start more than 8 h before it),
  or the coordinator's "STOP U2" at the X4S-4 GO, whichever is first. Under H-1-style counting, nothing completed
  after a STOP or STOP_AT is counted (the supervisor's phase that is cut is incomplete and that student is not
  reduced).

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
- The driver rewrites each new student runtime's `policy.checkpoint` to the J2 copy of main02.pt (same SHA pin
  d77005d5, asserted by run.py), so the reporting games read nothing from J.
