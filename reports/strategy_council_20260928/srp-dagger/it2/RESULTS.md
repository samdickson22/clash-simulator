# Iteration 2 results

Iteration 2 won 87/192 games versus 88/192 for the initial student. It avoided the observed pilot collapse to 16 wins, but this trial does not demonstrate improvement or statistical noninferiority. Keep the initial student.

The pilot diagnosis is in ../DIAGNOSIS.md. No action-index, tick-alignment or recurrence pipeline bug was found. Pilot files are preserved. The optional collection hook in kit.py is the only changed pilot Python file.

Collected 72 complete native srp_xm games with canonical gamedata 892fbfa0, beta 0.5, stochastic initial student and seed base 980031. Every labelled row includes the sampled student action, scored with the same root/rollout/leaf as the other candidates. Duplicate actions reuse their score.

Target temperature tau = 0.00969796919; margin = 0.05. Kept 267/14249 queried decisions (1.87%). Training-kept median candidate entropy is 1.000000 nat; all-kept median 1.013471; all-queried median 2.761114. Tau uses training games only. Leaf score quantiles [min, p1, median, p99, max] are [-2.0, -2.0, 0.04873479666453504, 2.0, 2.0]; advantage quantiles [min, p25, median, p75, p90, p99, max] are [0.0, 0.0, 0.00022422677817778708, 0.01058507750329736, 0.023098550919806175, 0.06715132497547972, 1.9499711525743741]. The 0.05 margin is unchanged from the requested leaf-score threshold.

Fit: one epoch, LR 5e-6, 206 optimizer updates, candidate-renormalized soft CE plus 1.0 KL(student || initial) on the full legal distribution. CE uses kept rows; KL uses every queried training row. Both losses use their own row-count normalization. Complete histories retain filtered and forced-wait context. BC stored-state TBPTT uses 64-step chunks and 16-step burn-in. Initial stored/full-prefix max logit difference 3.81e-06. Direct candidate-CE gradients outside the candidate set are zero. The final checkpoint reloads.

| Split | Candidate CE before | Candidate CE after | Full KL after | Kept rows |
|---|---:|---:|---:|---:|
| train | 9.251459 | 8.414268 | 0.005678 | 231 |
| heldout | 9.825357 | 9.037090 | 0.006413 | 36 |

## Paired evaluation

Six cells, same decks/seeds/seats/opponents and stochastic action sampling, seed base 770031. Differences use match score 1/0.5/0 for win/draw/loss. The bootstrap and exact two-sided sign-flip test cluster by deck/seat pair. The predeclared quick gate requires nonnegative paired mean score and win difference; it is not a statistical noninferiority claim.

| Evaluation | Initial wins | Iteration 2 wins | Score difference | Paired 95% interval | Exact p |
|---|---:|---:|---:|---|---:|
| Quick 48 | 23/48 | 24/48 | +2.08% | [-14.58%, +18.75%] | 1 |
| Full 192 | 88/192 | 87/192 | -0.52% | [-8.85%, +7.81%] | 1 |

Quick gate passed. Full evaluation completed. All 48 freshly rerun initial game records exactly match the existing canonical 192-game baseline, which was reused. See baseline-reuse.json. Its first eight games per cell overlap the gate, so it is not independent confirmation.

| Cell | Initial wins | Iteration 2 wins | Games |
|---|---:|---:|---:|
| holdout-nominal-balanced | 17 | 16 | 32 |
| holdout-nominal-pressure | 10 | 15 | 32 |
| holdout-nominal-defense | 15 | 13 | 32 |
| hog26-nominal-balanced | 18 | 14 | 32 |
| hog26-nominal-pressure | 14 | 16 | 32 |
| hog26-nominal-defense | 14 | 13 | 32 |

## Recommendation

Retain the initial student as the deployment baseline. Only 231 training targets and 36 held-out targets survived the margin. Calibrate the advantage threshold on repeatable leaf-score gains before expanding collection; do not lower it merely to inflate the label count. Before increasing collection, use an iteration-3 ablation that separates wait/play timing from placement targets, adds more student-distribution states, and restricts teaching to reproducible advantages. Compare an anchor-only control and a script-candidate-only target at matched update budgets. The current trial changes several factors together and cannot attribute any gain or loss to one of them.

Total srp-dagger footprint including the pilot/archive and evaluation artifacts is 132.7 MiB. At most two owned heavy processes ran, all launched with nice -n 10 under the required detached wrapper; inherited priority made some workers nice 20. Source/canonical/native guards and all 72 game invariants passed. Final audit passed 204 finite checkpoint tensors, all game hashes, canonical/native/source pins and preserved initial/pilot checkpoint, corpus and configuration identities. No owned jobs remain. Receipts: audit.json, diagnostics.json, behavior.json, targets.json, split.json, fit.json, fit-batches.jsonl, verification.json, quick.json, optional full.json, results.json and completion.json. Commands and owned PIDs are in ../PROGRESS.md.

Files changed: ../kit.py adds an optional planner hook and sampled-action assignment; ../PROGRESS.md records progress; ../DIAGNOSIS.md is new; it2/ contains the config, local adapters, diagnostics, collection, fit, evaluation and reports. No shared engine, native engine, gamedata, runtime snapshot, pilot, C56 or oracle files were edited.

Collection cost: 368.995 planner CPU-seconds and 1125.416 total CPU-seconds across 72 games. Retained decisions span 61 games; 25 of 267 have a terminal-win best leaf. The student was tied best on 48.27% of queried rows.

Checkpoint metadata note: the reused export helper left generic imitation_objective=exact and validation_accuracy=0 fields. Those fields were not used for training, gating, or this report; accuracy was not measured for iteration 2. The implemented objective is candidate-conditioned soft CE plus full KL, and fit.json contains the measured candidate CE/KL. The evaluated checkpoint is preserved unchanged.
