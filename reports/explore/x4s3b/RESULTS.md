# X4S-3b (U2 + U2b) results: fit-seed noise σ_fit in deployment loss: FINAL (exploration, NEVER ADOPTABLE)

Interim (U2) reduced 2026-10-13T04:42:38Z on the 05 mirror (`05:/mpac/sdicks02/jobs/clasher/x4s3b-fitseed-20261013/mirror/final`,
aggregate SHA match with 01), with the reviewed reducer `x4s3b/reduce.py` (a670d2af):
`--students R3a R3a-rep R3a-rep2`. Output: [results-interim.json](results-interim.json) (00926d0d). Pre-declared
readout: [READOUT.md](READOUT.md). Paired-seed bootstrap, 5,000 reps, seed 2026101201, percentile 95% CIs,
unadjusted. 1,167 paired seeds, 7,002 games, 1,063,777 decisions; all reducer checks pass.

**NEVER ADOPTABLE:** nothing here enters a frozen manifest (SD1 stays R3a), and it is never cited in K4S, TIERS or
T1 reporting.

## FINAL pre-declared readout (U2b, 3 fits, 2 df)
Reduced 2026-10-13T13:28:56Z on 05 (`J2/mirror/reduce-u2b-final/`) with the reducer at 127dce775 (6aba2079):
`--students R3a R3a-rep R3a-rep2 R3a-rep3`. Output: [results-final.json](results-final.json) (e7e14a4b).
1,167 paired seeds, 9,336 games, 1,402,723 decisions; all checks pass. R3a-rep3's games were played on 127x03
(indices 33–615) and 127x04 (616–1199), per the U2b amendment in [READOUT](READOUT.md). All four rep3 phases ended
rc 0, reason null, with every index, before STOP, so rep3 is reduced under the counting rule.

| Pair (r1-only fits) | Hosts | D_ij pooled, pp [95% CI] | V_ij, pp² | (D² − V)/2, pp² |
|---|---|---:|---:|---:|
| R3a-rep2 − R3a-rep | 01 / 01 | +0.26 [−1.80, +2.31] | 1.108 | −0.52 |
| R3a-rep3 − R3a-rep | 03·04 / 01 | −1.50 [−3.60, +0.60] | 1.183 | +0.53 |
| R3a-rep3 − R3a-rep2 | 03·04 / 01 | −1.76 [−3.81, +0.34] | 1.100 | +0.99 |

**σ̂_fit² = 0.335 pp² → σ̂_fit = 0.58 pp (final, df = 2). σ̂_fit ≥ 1.0 pp: NO.** Per the pre-declared rule, X4S-4's
assumed σ_fit = 0.65 pp is **not contradicted**; the X4S-4 interpretation note for σ̂ ≥ 1.0 pp does not apply.
The two rep3 pairs cross hosts, so this estimate is biased upward by any host effect (see below).

**Secondary, within-host (pre-declared; the rep2′ control completed on both hosts in both arms):** R3a-rep2 was
re-played as rep2′ on the same split and hosts ([results-within.json](results-within.json), 0db5c2b6).

| Term | D, pp [95% CI] | V, pp² | (D² − V)/2, pp² |
|---|---:|---:|---:|
| R3a-rep2 − R3a-rep (01) | +0.26 [−1.80, +2.31] | 1.108 | −0.52 |
| R3a-rep3 − R3a-rep2′ (same host per seed, 03·04) | −2.14 [−4.20, −0.17] | 1.094 | +1.75 |

**σ̂_w² = 0.613 pp² → σ̂_w = 0.78 pp (df 2). ≥ 1.0 pp: NO.**

**Host effect (descriptive, same fit R3a-rep2, 03·04 minus 01, same seeds):** pooled +0.39 pp [−1.67, +2.49];
K4S-120 +0.60 [−2.40, +3.60]; S-200 +0.17 [−2.83, +3.17] (452 of 1,167 seeds disagree pooled). Computed inline on
the mirrors with the same bootstrap; this is not a reducer output. The hosts differ in speed: cutoff rates are clearly
lower on 03/04 (K4S-120 54.7–56.6% vs 63.1–64.2% on 01; S-200 70.2–70.6% vs 73.8–75.5%), with identical
p50/p99 wall (113/113, 193/193 ms) and overrun ≤ 0.13%. The loss effect of that speed difference is small and
not resolved. It is consistent with K4S's anytime design, in which faster search mostly changes which search
completes, not the default.

| Student (host) | Arm | Loss % [95% CI] | Cutoff % | Student-default % | Play % | Overrun % |
|---|---|---:|---:|---:|---:|---:|
| R3a-rep3 (03·04) | K4S-120 | 21.7 [19.4, 24.0] | 54.7 | 18.7 | 32.5 | 0.12 |
| R3a-rep3 (03·04) | S-200 | 26.9 [24.4, 29.5] | 70.2 | 0.0 | 25.2 | 0.12 |
| R3a-rep2′ (03·04) | K4S-120 | 24.4 | 56.6 | | | 0.13 |
| R3a-rep2′ (03·04) | S-200 | 28.4 | 70.6 | | | 0.11 |

Descriptive (not in σ̂): R3a-rep3 − R3a pooled −0.09 [−2.14, +1.97]. The three r1-only replicates span pooled
loss within about 1.8 pp, and R3a sits inside that range.

**What this means:** fit-to-fit noise in deployment loss is about 0.6–0.8 pp. The interval is wide (2 df), but it
gives no sign that σ_fit ≥ 1 pp, so X4S-4's design assumption (0.65 pp) looks about right. One fit-seed draw is
worth roughly the same as the paired-game sampling SD at 1,167 seeds (~1.05 pp per contrast), so more fits and more
games are similarly valuable for future student comparisons.

### U2b disclosures
- **Hosts:** 03/04 were used only after the coordinator verified the FSC stop; K4S was not on them before 14:30Z.
  The prefix was `/mpac/sdicks02/jobs-x4s3b/rep3-20261013/` (no `jobs/clasher` on 04, no `jobs-fsc`). Preflight:
  0 console users, about 122 GiB free memory, PSI 0, idle. Venv python 3.12.13, numpy 2.3.5, torch 2.10.0. The
  identity gate (K4S-none(R3a), X4S qual indices 0,1) reproduced `command_sha256` af630cf0/d530982b on both hosts.
- **Code:** only host tuples (run.py:300, supervise.py:72, reduce.py:53; commit 127dce775); the runtime plan's two
  checkpoint paths and index files are config.
- **Phases:** 03: rep3 K4S-120 11:52:28–12:27:18Z, S-200 –12:39:03Z; rep2′ S-200 –12:50:49Z, K4S-120 –13:25:39Z.
  04: rep3 K4S-120 –12:27:42Z, S-200 –12:39:36Z; rep2′ S-200 –12:51:28Z, K4S-120 –13:26:46Z. All rc 0, reason
  null, full index sets. K4S-120 throughput was about 16.4 games/min per host (guard 13). PSI 0, no console users.
- **STOP / census:** STOP touched 13:27:02.914Z (03) and 13:27:27.971Z (04), before STOP_AT. Every supervisor PID
  (gate, 2 rep3, 2 rep2′ per host) was gone and every supervisor PGID and child PGID had 0 members; no process had cwd
  under the prefix. Mirrors on 05 (`J2/mirror/u2b-03`, `u2b-04`) match the host trees by aggregate SHA.
- **Seeds:** the same paired reuse of the X4S-3 bank as before. Host differs by seed half for rep3/rep2′, and both
  arms of a seed share a host.

## INTERIM readout (U2, kept for the record)

### Pre-declared readout: INTERIM (1 pair, 1 df)
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
