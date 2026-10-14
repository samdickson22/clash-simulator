# X4S-4 results: do on-policy cutoff-state labels make a better student? (exploration, NEVER ADOPTABLE)

Reduced 2026-10-14T13:00:45Z from 1200 paired seeds ([PLAN](PLAN.md)). Paired-seed bootstrap, 5,000 reps, seed 2026101301, percentile 95% CIs, unadjusted (about 6 contrasts; only the primary selects the decision row). Loss = the student-tier agent loses to the exact v1 policy (draws are non-losses). **NEVER ADOPTABLE**; never cited in K4S/TIERS/T1 reporting.

## Primary (pre-declared; selects the decision row)

**Δ = mean(R5, R5-rep) minus mean(R3a, R3a-rep), pooled, equal arm weight: -1.9 pp [-3.4, -0.5] on 1200 seeds. Outcome: HELPS.**
Fit-inflated interval (σ_fit fixed at 0.65 pp, E3): [-3.9, -0.0]. Harmful (lower CI > 0, E9): no. MDE 2.1 (game sampling) to 2.8 (sigma_fit 0.65) pp; rule: helps: upper95CI < 0 AND (R5 minus R3a)[pooled] < 0 AND (R5-rep minus R3a)[pooled] < 0; no material effect: lower95CI > -2.0 pp; else inconclusive. The bootstrap CIs cover game sampling only (E2).

| Primary Δ by arm (descriptive; no outcome rule) | Point pp | 95% CI | Seeds |
|---|---:|---:|---:|
| K4S-120 | -2.7 | [-4.6, -0.9] | 1200 |
| S-200 | -1.2 | [-3.2, +0.9] | 1200 |

Seeds (E8): primary 1200 of 1200 non-retired (complete); R5W secondaries 1200 seeds.
Contention sensitivity (pre-declared C5/E7; 543 seeds excluded, receipt 025a3bba388e…, commit 056c64aec7ef): Δ -1.8 pp [-3.7, +0.1] on 657 seeds → inconclusive.
Attribution (E4, descriptive): mean(R5, R5-rep) − R5W = -2.7 pp [-4.5, -0.9] on 1200 seeds → **on-policy beyond matched data**.

## What the result changes (PLAN r3 §1 decision table; the primary outcome alone selects the row)

Helps; attribution sub-label (E4): **on-policy beyond matched data**. Iterate DAgger (collect with R5, label, refit, with replicates) and scale O; a separate SD2 PREREG for the slow-Mac/1-core tiers only after the K4S/TIERS release. In every case, check for overfitting to v1/X decks before any live use.

## Single-fit and secondary contrasts (descriptive)

| Contrast (loss pp; negative = fewer losses) | Pooled | K4S-120 | S-200 | Seeds |
|---|---:|---:|---:|---:|
| R5 minus R3a | -1.6 [-3.7, +0.4] | -3.8 [-6.5, -0.9] | +0.5 [-2.4, +3.5] | 1200 |
| R5-rep minus R3a | -3.0 [-5.0, -1.0] | -4.3 [-7.0, -1.6] | -1.7 [-4.6, +1.2] | 1200 |
| R5 minus R3a-rep | -0.9 [-2.9, +1.2] | -1.1 [-3.8, +1.7] | -0.7 [-3.5, +2.2] | 1200 |
| R3a-rep minus R3a | -0.8 [-2.8, +1.3] | -2.7 [-5.4, +0.2] | +1.2 [-1.7, +4.0] | 1200 |
| R5 minus R5-rep | +1.4 [-0.5, +3.3] | +0.6 [-2.1, +3.3] | +2.2 [-0.7, +4.9] | 1200 |
| R5 minus R5W | -2.0 [-4.1, +0.1] | -3.4 [-6.3, -0.6] | -0.7 [-3.6, +2.4] | 1200 |
| R5-rep minus R5W | -3.4 [-5.4, -1.3] | -4.0 [-6.8, -1.2] | -2.8 [-5.7, +0.0] | 1200 |

σ_fit ≈ 0.33 pp (2-df, descriptive).
|R3a-rep − R3a| ≥ 4 pp: K4S-120 no, S-200 no, pooled no.

## Timing parity (pre-declared C4; non-outcome)

| Arm | Student | Cutoff % | Student-default % | Wall p99 ms |
|---|---|---:|---:|---:|
| K4S-120 | R3a | 65.2 | 22.7 | 113 |
| K4S-120 | R5 | 66.6 | 23.2 | 113 |
| K4S-120 | R5-rep | 66.5 | 23.3 | 113 |
| K4S-120 | R3a-rep | 65.6 | 22.8 | 113 |
| K4S-120 | R5W | 65.0 | 21.9 | 113 |
| K4S-120 | gap | 1.6 | 1.4 | within 2 pp |
| S-200 | R3a | 78.6 | 0.0 | 193 |
| S-200 | R5 | 79.9 | 0.0 | 193 |
| S-200 | R5-rep | 80.0 | 0.0 | 193 |
| S-200 | R3a-rep | 78.9 | 0.0 | 193 |
| S-200 | R5W | 77.9 | 0.0 | 193 |
| S-200 | gap | 2.1 | 0.0 | > 2 pp: disclosed (no exclusion, E10) |

## Per student and arm

| Student | Arm | Loss % [95% CI] | Cutoff % | Student-default % | Play % | Wall p50 / p99 ms | Overrun % |
|---|---|---:|---:|---:|---:|---:|---:|
| R3a | K4S-120 | 23.5 [21.2, 25.9] | 65.2 | 22.7 | 31.7 | 113 / 113 | 0.18 |
| R3a | S-200 | 24.9 [22.4, 27.4] | 78.6 | 0.0 | 21.0 | 193 / 193 | 0.09 |
| R3a-rep | K4S-120 | 20.8 [18.6, 23.2] | 65.6 | 22.8 | 31.5 | 113 / 113 | 0.17 |
| R3a-rep | S-200 | 26.1 [23.7, 28.7] | 78.9 | 0.0 | 20.9 | 193 / 193 | 0.11 |
| R5 | K4S-120 | 19.8 [17.4, 22.1] | 66.6 | 23.2 | 31.7 | 113 / 113 | 0.18 |
| R5 | S-200 | 25.4 [23.0, 27.9] | 79.9 | 0.0 | 20.3 | 193 / 193 | 0.10 |
| R5-rep | K4S-120 | 19.2 [16.9, 21.4] | 66.5 | 23.3 | 31.8 | 113 / 113 | 0.18 |
| R5-rep | S-200 | 23.2 [20.9, 25.7] | 80.0 | 0.0 | 20.4 | 193 / 193 | 0.09 |
| R5W | K4S-120 | 23.2 [20.8, 25.6] | 65.0 | 21.9 | 31.5 | 113 / 113 | 0.17 |
| R5W | S-200 | 26.1 [23.6, 28.5] | 77.9 | 0.0 | 21.7 | 193 / 193 | 0.10 |

## O composition and duplicates (§2; from the frozen label plan)

| Set | Games | Dropped (no block) | Captured | Duplicates | Over cap | Kept | Kept K4S-120 | Kept S-200 | Plays | Student-default | Fallback |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| O | 3500 | 0 | 339846 | 0 | 0 | 339846 | 173469 | 166377 | 131413 | 52291 | 50445 |
| holdout | 500 | 0 | 49183 | 0 | 0 | 49183 | 21652 | 27531 | 18969 | 6538 | 8165 |
- O strata shares: hit 87.0%, nonhit_sample 13.0%
- holdout strata shares: hit 87.2%, nonhit_sample 12.8%

| 600-tick bucket | O states | Feature-only duplicates | Rate |
|---:|---:|---:|---:|
| 0 | 45683 | 24 | 0.1% |
| 600 | 45037 | 0 | 0.0% |
| 1200 | 45734 | 0 | 0.0% |
| 1800 | 45316 | 0 | 0.0% |
| 2400 | 63617 | 0 | 0.0% |
| 3000 | 58760 | 0 | 0.0% |
| 3600 | 18202 | 0 | 0.0% |
| 4200 | 9709 | 0 | 0.0% |
| 4800 | 5414 | 0 | 0.0% |
| 5400 | 2362 | 0 | 0.0% |
| 6000 | 12 | 0 | 0.0% |

|O| (scored roots) = 339846; O_W roots = 339892 (rows 2201951); O_W single-candidate root share = 0.0% (no dedup in O_W, E11).

## O-holdout diagnostic (descriptive only; never a gate)

| Student | Slice | Top-1 agreement | Gate accuracy | Listwise CE | Frozen objective |
|---|---|---:|---:|---:|---:|
| R3a | O-holdout | 0.491 | 0.694 | 2.933 | 5.877 |
| R3a | R1-heldout64 | 0.553 | 0.744 | 2.523 | 5.659 |
| R3a-rep | O-holdout | 0.492 | 0.694 | 2.934 | 5.878 |
| R3a-rep | R1-heldout64 | 0.554 | 0.743 | 2.524 | 5.660 |
| R5 | O-holdout | 0.502 | 0.708 | 2.909 | 5.831 |
| R5 | R1-heldout64 | 0.554 | 0.745 | 2.524 | 5.661 |
| R5-rep | O-holdout | 0.502 | 0.707 | 2.910 | 5.833 |
| R5-rep | R1-heldout64 | 0.554 | 0.746 | 2.525 | 5.662 |
| R5W | O-holdout | 0.497 | 0.697 | 2.921 | 5.852 |
| R5W | R1-heldout64 | 0.552 | 0.740 | 2.524 | 5.661 |

## Disclosures

- R3a-rep differs from R3a in its G-04 rows as well as its fit seed, so the control mean averages two closely related, but not seed-only, replicates (C1).
- O samples hidden states from the deployed Belief (the S1 exact resumable prior); r1, G and O_W used the emitter's ExactFastPrior. Both are exact-prior beliefs (C8).
- O is labelled through the anchor kernel and O_W through the emitter: different wrappers of the screen8 scorer whose equivalence rests on the 125-state frozen equality.
- O_W differs from O in behavior policy (W's own decisions, including single-candidate roots, vs the student-tier agent's cutoff-heavy selection of > 1-candidate decisions); R5 - R5W measures that intended contrast.
- Bootstrap CIs cover game sampling only; fit-seed variance is not in them (E2). One DAgger round, one behavior policy, one opponent, five decks; x4 up-weighting is a single pre-declared choice.
- Exploration only, NEVER ADOPTABLE; never cited in K4S/TIERS/T1 reporting.
- SA-1 (COORDINATOR 69345e4a): the X4S-3 base lacked imitation/exit_r1 and base/corpus. exit_r1 {__init__,rows,pack,emitter} came from 04c068f5, and the corpus was copied from J3. S2 was then re-run and passed 44/44.
- PE-1 (COORDINATOR f6afe586): the Q4 smoke C7b parity (8 games per arm) was out of band on the low side: cutoff 58.67 vs 64.2 (K4S-120) and 69.75 vs 75.3 (S-200); K4S-120 student-default 19.94 vs 22.3. An exact-receipt exception (parity-smoke.json 10c68b04...) was granted with decision 'disclose'.
- SA-2 (COORDINATOR 55254853): the X4S-3 base's search-noise-s6/delay.py (20cff68a) lacked 59454e1a's two-line W-screen8 hand-off, so the O_W emitter's acceptance smoke failed ('invalid action'). delay.py fa3d3296 was installed in base, rt-R3a and rt-R3a-rep. Every other runtime path uses wait_screen8=False, where the lines never execute. Q5 r2 passed.
- SA-2 follow-up sweep: of 1,344 base/repo .py files, 1,298 equal origin/main. The runtime-imported differences are the frozen X4S-3 base's imitation/evaluation/paths.py (runtime_dependencies path) and untracked loss_review / runtime_dependencies modules, byte-equal to the shared worktree. There is no other W-screen8 or delay skew, and nothing else was changed.
- PE-1 control (Q7, capture-free evaluation on the same 8 smoke seeds): cutoff 56.06 % (K4S-120) and 55.78 % (S-200), against collection 58.67 / 69.75 and X4S-3 64.2 / 75.3. Paired per seed on S-200, collection exceeded evaluation on 8/8 seeds (mean +9.7 pp).
- PE-2 test B (COORDINATOR b98fda79): at --workers 10, the S-200 paired collection - evaluation cutoff gap was -0.70 pp (4/8 seeds). This is the contention branch, so SA-3 applies: S-200 collection (P2) ran at --workers 10. Run-to-run variance on the same seeds is large (pooled S-200 evaluation cutoff was 55.78 % at 50 lanes and 66.69 % at 10).
- PE-3 (COORDINATOR f4a2bc1f): P1 a1 was paused by the in-loop C7b watch at 147 games (K4S-120 cutoff 61.30 vs 64.2, low side; receipt b63b4a99...), and 'disclose' was granted. P1 continued as phase a2 over the remaining 2,103 indices (a1's 147 games are kept).
- SA-4 (COORDINATOR f0156bef): the in-loop C7b watch was made one-sided. It pauses only if a metric is more than 2 pp above X4S-3. Low-side readings are recorded in receipts/parity-lowside.jsonl, which is disclosed. P3 stays the binding check.
- SA-5 (COORDINATOR 6d70070d): a failed P3 could not reach label.py's exact-receipt exception, because its guard always failed and the receipt completed inside the STOP that pause() created. qualify4 parity --final (P3 only) never pauses and passes its guard when the check completes; the verdict stays in 'passed'.
- PE-4 (COORDINATOR 9ecc275a): the final C7b check (P3-r2, receipt 2ec15eb4...) has K4S-120 in band (cutoff 62.46 vs 64.2) and S-200 out of band on the low side only (cutoff 63.32 vs 75.3). Decision: disclose. The S-200 O-states come from 10-lane collection (SA-3), which had fewer cutoffs than X4S-3's 50-lane reference.
- Collection phases: K4S-120 a1 (147 games, paused at PE-3) + a2 (2,103 games); S-200 a1 (1,750 games at --workers 10). P3 and the label plan name all three phases.
- Deadline windows: T1 = 2026-10-13T04:55:07Z (ended by HALT 1), T2 = 2026-10-13T12:37:13Z (GO 9a1613fc; ended by HALT 2), T3 = 2026-10-14T00:07:39Z (GO HR-2 e0c087da; hard stop 2026-10-15T00:07:39Z). The P1/P2 collection carried over and was re-verified by P3-r3 (T2) and P3-r4 (T3), each reproducing the P3-r2 inventory. Every later production step (P5 onward, fits, P11, P12) completed under T3. Nothing completing at or after a HALT, or inside a STOP period, counts (H-1).
- HALT 1 (2026-10-13T11:57:58Z, under T1): the watchdog's `du -sb` disk reading exited 1 because P5 labelling renamed files during the walk. 51 study processes were stopped by verified PID. The 523 raw-O games sealed before the HALT were set aside and never count. This was a measurement-path defect, not a resource breach.
- HR-1 (COORDINATOR 77a01d88; GO 9a1613fc): the watchdog's disk reading became an own bounded scandir/lstat walk (studytree.tree_bytes): vanishing entries are skipped and counted, and every other error raises. J continued under T2: HALT.json was archived, the HALT window was recorded as a STOP period, W0 passed, P3-r3 reproduced P3-r2, and P5 onward re-ran.
- HALT 2 (2026-10-13T14:32:50Z, under T2): 'measurement overdue (> 8 s)'. A single 8 s watchdog budget held the disk walk (2.45 s at 564k entries), nvidia-smi and the process/PSS scan; the last readings before it were healthy. 111 study processes were stopped by verified PID (P9 collect-w, the driver, the R5 fit). This was a measurement-path robustness defect, not a resource breach.
- HR-2 (r3 after two Sol fix-check rounds; GO e0c087da): the watchdog was split into two lanes. The fast lane (8 s) covers the scan, STOP, deadline, MemAvailable, PSI, process count and GPU. The slow lane covers PSS and the walk: a pass every 30 s, a 120 s budget, and the last result must be at most 180 s old. Breaches and failed readings still HALT. J restarted under T3: P3-r4 reproduced the frozen inventory; P9 re-ran in full (the 2,741 pre-HALT raw-OW games were set aside); R5 restarted from step 0 (its post-HALT step-1590 checkpoint is excluded by H-1).
- AR-1 (COORDINATOR 424113d7): the driver could not reach the coordinator's ACK for the R5 fit anomaly (Fits.tick returns early), so the reviewed driver.unresolved_anomalies() was run once, unchanged, from a one-off process. AR-2 (cfc3e7c6): the HALT-killed R5 DataLoader had left 6 pymp-* listener sockets under cache/fit/tmp, which prepare_fit_dirs refused; they were moved to fits/halted-r2-R5/cache-fit-tmp/ and the driver-exception anomaly was ACKed 'continue'. The standing AR-2b ruling was never needed again.
- Readout (RF-1 COORDINATOR ae1c0a57, RF-2 3e697fb6): the single approved fetch on 01 ran after the C5 receipt commit, so reduce.verify_freeze could authenticate it. The absent report directory on 01 (checkout from 2026-10-07) was created with one mkdir before P15.

## Inputs

- `results` sha256 cae1577aeb1b88e8f4725a0712552e56233e008565042208dd2500be7c71d1fc
- `label_plan` sha256 2cc0f62597c2c171015226f4bb2512aa723891de15f3d240dd140093f7e5d2b5
- `o_gate` sha256 e6d19a8166712b0879697fd41c62f0245f16f630e8c09c81c5db10d9405435e5
- `ow_gate` sha256 67700e08b423f86f4ab1035f77adac6e499d37205ea1525f599b157322c257d9
- `diagnostic` sha256 c66ca750d6b6d1a27c25e564e4c57631046ae3ec9851aff1ab5f1b1fe0fa2a42
- `holdout_gate` sha256 eb969538ee2d4da1f1872bed472ebacf3e9a41893b0cd25d415b83fd942d0201
