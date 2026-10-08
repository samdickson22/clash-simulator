# S3 results

S3 passes the registered elixir calibration and sharpness requirements, but **both registered strength tests FAIL**. The 15.0 pp gap to R-derived misses the ≤5 pp target. This result does not justify unblocking L2-v4.

Complete: 1,792 games. Paired-matchup bootstrap (10,000 draws; both seats retained).

| Cell | Score | 95% CI |
| --- | ---: | --- |
| T2-N97 | 65.0% | [57.8, 72.1] |
| T2-N90 | 64.5% | [57.0, 71.5] |
| Full-N97 | 64.8% | [57.4, 71.9] |
| Full-N90 | 62.9% | [55.5, 69.9] |
| ELT-N97 | 70.7% | [63.7, 77.3] |
| R-derived | 80.1% | [74.2, 85.5] |
| T2-N64 | 56.6% | [48.8, 64.1] |

## Registered contrasts

- primary: +1.6 pp [-4.7, +7.8]; FAIL
- secondary: +0.2 pp [-6.4, +6.8]; FAIL
- ceiling_gap: +15.0 pp [+8.8, +21.5]

## Tracker diagnostics

| Cell | Coverage | Post-error coverage | Width | MAE | Hand mass ≥90% | Old hand flag |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| T2-N97 | 0.891 | 0.854 | 2.780 | 0.701 | 0.0132 | 0.0000 |
| T2-N90 | 0.902 | 0.895 | 2.757 | 0.741 | 0.0004 | 0.0000 |
| Full-N97 | 0.999 | 0.998 | 6.128 | 0.727 | 0.0052 | 0.0052 |
| Full-N90 | 0.993 | 0.992 | 6.675 | 0.759 | 0.0007 | 0.0007 |
| ELT-N97 | 0.711 | 0.612 | 3.417 | 1.641 | 0.0962 | 0.0000 |
| R-derived | 1.000 | 1.000 | 0.000 | 0.000 | 0.1619 | 0.1619 |
| T2-N64 | 0.933 | 0.933 | 4.230 | 0.827 | 0.0000 | 0.0000 |

Game CPU: 41.97 core-hours. Supervisor/worker, development and preflight accounting are reported separately in compute-audit.json.

Manifest: `7f2a2f72c573828433808fc1b2153eb0fc74b30c6193319dfb897e0ad4d658d9`. Receipt aggregate: `9a9b38ae9543770206b7d6c7d170d958ced5aa01d70c5912698d74d6ab26bdc3`.

Truth is scoring-only. T2 intervals use the calibration-split radius frozen before confirmation. Full/ELT anchors retain their original intervals. No outcome-based exclusions. T2-N64 is descriptive. Raw receipts stay on the fleet.

## Design and validation

`tracker_v2.py` uses a full 100,001-value integer resource lattice, exact phase/cap arithmetic, missed-spend transitions, accept/reject/confusion branches, an explicit affordability repair, persistent broad resource mass, and fixed-lag fusion of public body sightings with detected events. The separate 48-slot deck-free cycle mixture merges equivalent states and transfers pruned mass to an unknown-state component. The perfect-event path retains exact finite derivation. Resource/cycle correlation is approximate; noisy updates form a robust mixture filter, not an exact Bayesian action-policy model. See DESIGN.md.

Eight unit tests pass, covering exact phase/cap behavior, synthetic missed/spurious/confused cues, recovery, board deduplication, pruning fallback, and hidden-card/RNG invariance. All 24 original recorded P16 games pass: 23,058 observations, zero elixir/hand/cycle/next-card errors, with additional D1 comparisons. Three S2 anchor wrappers reproduce terminal action hashes/counts/ticks. All seven outcome-suppressed timing pilots finish.

Fresh development uses 56 script-v-script worlds, both seats, at three event levels. Indices 0–27 set the final interval radii; 28–55 supply validation diagnostics. Validation informed the development revisions and is not an untouched confirmation set. No confirmation result set a parameter.

| Dev validation | Coverage | Post-error coverage | Width | MAE | Legacy width | Legacy MAE |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| T2-N97 | 0.9131 | 0.8862 | 2.697 | 0.633 | 6.507 | 0.787 |
| T2-N90 | 0.9104 | 0.9017 | 2.635 | 0.739 | 6.995 | 0.865 |
| T2-N64 | 0.9079 | 0.9071 | 4.133 | 0.866 | 7.945 | 1.591 |

## Interpretation and hand-confidence limitation

N97 and N90 meet ≥88% overall coverage and ≥80% coverage in the 60 seconds following any event error, with substantially narrower intervals than legacy. Their MAE gains in confirmation are small (0.701 vs 0.727 and 0.741 vs 0.759). Neither paired score contrast resolves a positive improvement. Better elixir interval calibration alone is insufficient evidence of stronger search.

**The noisy hand posterior remains unreliable.** At N97, ≥90%-mass resolved hands occur on 1.32% of sampled decisions and are correct only 16.7% of those times. At N90, they occur on 0.045% of decisions and none are correct. Model mass is not empirically calibrated hand confidence. The factorization and board/cycle handling are limitations; this study does not causally isolate the reason for the failed strength tests. No post-confirmation retuning was performed.

The old hand flag means unanimity across retained branches for T2/ELT, exact agreement for R-derived, and the original ≥90% hand criterion for legacy. The ELT new mass diagnostic is a conservative sum over fully resolved branch hands. Unresolved hands never count as resolved concentration.

Postcompletion recovery descriptives (not new pass criteria): among N97 error games with a subsequent uncovered sample, 247/248 later regain coverage at least once; 75/248 end uncovered. N90 regains coverage in 256/256 such games; 73/256 end uncovered. These are sampled, right-censored episodes, not proof of permanent failure or event-level causation. See completion-audit.json.

## Integrity and operations

Both seed audits found no collision in retained evidence (04: 972,459 seed fields / 10,209 NPZ archives; 01: 982,778 fields / 12,497 NPZ archives). There are 726 unavailable historical paths, including six NPZ archives; disjointness claims retain that limitation. All 468 S1, 473 S2 and 518 S3 sealed files verify on each of 01/04/08 after completion. The independently recomputed receipt aggregate matches.

All 1,792 terminal receipts, 152 successful partitions and both successful supervisors existed before outcome analysis. There were no confirmation game exclusions or reruns. The collector's first startup preceded receipt-directory creation; its failed evidence is retained, and the unchanged collector finished as s3-collect-r1b. Two initial development trace captures failed during static body-map serialization; their evidence was preserved and the mapping fixed before the final freeze.

Game CPU: **41.97 core-hours**. Confirmation supervisors plus workers: **42.12**. Development/preflight/audits: **3.90**. Total metered: **46.02 core-hours**; these figures overlap as documented in compute-audit.json and must not be added together. Game wall span: 20.15 minutes. Small copy/hash/registration and postcompletion summary operations are unmetered.

Games and heavy offline work ran only on 04/08, nice 10, one native/BLAS thread. Peak per host was 76 workers plus one supervisor, with no console users observed. Raw receipts and binaries stay on the fleet. Only S3-owned code/docs/small evidence/results were mirrored to 05. No engine/gamedata or sealed S1/S2 files changed. No commits were made. Frozen generated prose is preserved in RESULTS-generated.md; result.json remains unchanged.
