# X4S-3b (U2) results: fit-seed noise σ_fit in deployment loss: INTERIM (exploration, NEVER ADOPTABLE)

Reduced 2026-10-13T04:42:38Z on the 05 mirror (`05:/mpac/sdicks02/jobs/clasher/x4s3b-fitseed-20261013/mirror/final`,
aggregate SHA match with 01), with the reviewed reducer `x4s3b/reduce.py` (a670d2af):
`--students R3a R3a-rep R3a-rep2`. Output: [results-interim.json](results-interim.json) (00926d0d). Pre-declared
readout: [READOUT.md](READOUT.md). Paired-seed bootstrap, 5,000 reps, seed 2026101201, percentile 95% CIs,
unadjusted. 1,167 paired seeds, 7,002 games, 1,063,777 decisions; all reducer checks pass.

**NEVER ADOPTABLE:** nothing here enters a frozen manifest (SD1 stays R3a), and it is never cited in K4S, TIERS or
T1 reporting.

## Pre-declared readout: INTERIM (1 pair, 1 df)
The run was stopped at the X4S-4 GO (STOP U2, amended timing, COORDINATOR 4b33d68d) after R3a-rep2's games. R3a-rep3
was fitted and calibrated but played no games, so only the pair R3a-rep2 − R3a-rep is available.

| Pair (r1-only fits) | D_ij pooled, pp [95% CI] | V_ij, pp² | (D² − V)/2, pp² |
|---|---:|---:|---:|
| R3a-rep2 − R3a-rep | +0.26 [−1.80, +2.31] | 1.108 | −0.52 |

**σ̂_fit² = max(0, −0.52) = 0 → σ̂_fit = 0.0 pp (interim, df = 1, `final=false`).** σ̂_fit ≥ 1.0 pp: **NO**.

Per the pre-declared rule, X4S-4's assumed σ_fit = 0.65 pp is **not contradicted**. With 1 df this is very weak
evidence: the observed pair difference is smaller than its own game-sampling SD (√1.108 ≈ 1.05 pp), so the data
cannot separate σ_fit = 0 from values around 1 pp. (Not pre-declared, context only: a one-sided 95% chi-square bound
on Var(D) = 2σ² + V from this single pair would allow σ_fit up to about 2.8 pp.)

## Per arm, and descriptive contrasts
| Contrast (loss pp; negative = fewer losses) | Pooled | K4S-120 | S-200 |
|---|---:|---:|---:|
| R3a-rep2 − R3a-rep (replicate pair) | +0.26 [−1.80, +2.31] | +1.20 [−1.71, +4.03] | −0.69 [−3.60, +2.31] |
| R3a-rep2 − R3a (descriptive) | +1.67 [−0.39, +3.68] | +1.71 [−1.11, +4.54] | +1.63 [−1.29, +4.63] |
| R3a-rep − R3a (X4S-3, unchanged) | +1.41 [−0.69, +3.51] | +0.51 [−2.40, +3.34] | +2.31 [−0.77, +5.31] |

R3a is reported only descriptively: it also differs by the 212,542 G-04 rows, and its S-200 phase ran in X4S-3's
13:10–13:34Z thrash window. Both r1-only replicates lose about 1.4–1.7 pp more than R3a pooled; that is consistent
with a small G-04 data effect or with noise, and it is not tested here.

| Student | Arm | Loss % [95% CI] | Cutoff % | Student-default % | Play % | Wall p50 / p99 ms | Overrun % |
|---|---|---:|---:|---:|---:|---:|---:|
| R3a | K4S-120 | 22.1 [19.7, 24.6] | 64.2 | 22.3 | 31.7 | 113 / 113 | 0.16 |
| R3a | S-200 | 26.6 [24.2, 29.1] | 75.3 | 0.0 | 22.7 | 193 / 193 | 0.14 |
| R3a-rep | K4S-120 | 22.6 [20.2, 25.1] | 63.5 | 22.2 | 31.8 | 113 / 113 | 0.17 |
| R3a-rep | S-200 | 29.0 [26.4, 31.5] | 73.8 | 0.0 | 23.5 | 193 / 193 | 0.09 |
| **R3a-rep2** | K4S-120 | 23.8 [21.3, 26.3] | 63.1 | 21.9 | 32.0 | 113 / 113 | 0.15 |
| **R3a-rep2** | S-200 | 28.3 [25.7, 30.8] | 75.5 | 0.0 | 22.7 | 193 / 193 | 0.06 |

## Disclosures
- **Interim, not final.** The pre-declared final readout (3 pairs, 2 df) needs R3a-rep3's 2 × 1,167 games. The
  rep3 checkpoint (43621ce4, calibrated threshold 0.49953630566596985) is preserved in J2 and on the 05 mirror;
  resuming its games after X4S-4 would need a new STOP_AT and a coordinator OK. Pairing requires host 01.
- **Counting rule (READOUT, pre-declared):** R3a-rep2's K4S-120 a1 (exit 04:16:08Z) and S-200 a1 (exit 04:40:54Z)
  both ended rc 0, reason null, 1,167/1,167 blocks, before STOP (04:41:03.854Z). No phase was cut; no seed was
  retired beyond X4S-3's 0–32.
- **Paired reuse:** the same 1,167 X4S-3 reporting seeds, five X decks, one opponent (v1), same host and harness.
  New games carry run.py's unchanged study label "X4S-3 exploration, NEVER ADOPTABLE"; the job prefix and student
  IDs identify them.
- **Fits:** R3a recipe, frozen R3 trainer copied into J2, r1 only (6,009,681 roots), 2,500 steps.
  R3a-rep2 seed 2026101204 (01:35:07–02:51:57Z), checkpoint 72d73375. R3a-rep3 seed 2026101205
  (02:51:58–04:09:40Z), checkpoint 43621ce4. Both stopped=false. Calibration is the label-free R3 rule; every
  student's play count is pinned to the same rate (0.345944609297725). Thresholds: R3a-rep2 0.49848902225494385,
  R3a-rep3 0.49953630566596985.
- **Ops incident (staging, no code change):** R3a-rep2's first calibration failed (rc 1) because my J2 staging
  omitted the `calibration/` directory. I created it and cleared the anomaly, and the driver retried. That cost
  about 11 min of idle game cores ([receipts/fits/R3a-rep2/](receipts/fits/R3a-rep2/)).
- **Scheduling:** the rep3 fit ran beside rep2's K4S-120 phase (allowed). No fit ran beside S-200: the rep3 fit
  returned before rep2's S-200 dispatched. Peak memory PSI some avg10 was 0.00 in every check, with no console
  users.
- **Stop sequence:** owner holds `ANOMALY-phase-R3a-rep3-{K4S-120,S-200}` were placed at 03:36:52Z, so nothing
  dispatched after rep2's S-200. STOP + FIT.STOP were touched at 04:41:03.854Z (supervisor already exited) and the
  driver was SIGTERMed at 04:41:18Z; it exited at 04:41:19Z. The census by PID/PGID found 0 members in all 14 owned
  PGIDs, no process with cwd under J2, and the GPU at 107 MiB with no compute apps.
- **Review conditions (Sol diff r1, 840c9733):** run_fit.sh mode 100644, invoked via bash; all writes under J2 (J
  only read; reduction written under the J2 mirror prefix on 05); STOP_AT 2026-10-13T09:35:00Z with the 8 h
  assertion (a first launch 28 s early was refused by it). Inherited residual (Sol finding 5): the reducer does not
  check completion times; the counting rule above was applied by the `--students` list.
- **Validity limits:** 1 df; one opponent and five decks; budget equivalence, not a real slow Mac; descriptive
  exploration.
