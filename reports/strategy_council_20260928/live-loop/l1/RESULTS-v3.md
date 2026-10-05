# L1 v3 results

L2 verdict: NOT READY.
The following scores use frozen predictions from continuous native-renderer video. Stepped data and oracle events do not enter these gates.

## Timing

Pooled heldout native timing residual p95 is 26.96 ms, or 0.539 ticks. Pooled visible-clock midpoint residual p95 is 64.48 ms.
Heldout native offset/drift-fit p95 residuals range from 26.00 to 30.24 ms across matches. At 20 ticks/s, these are 0.520 to 0.605 ticks.
Visible-clock midpoint p95 residuals range from 17.73 to 90.42 ms. Each episode retains fitted offset, drift, interval-censored clock edges and native request brackets.
Started/completed native step counters prove that admitted ordinary observations did not straddle a logic step. Screenshot PTS is the emulator estimate made before copying the image. Frame tick labels retain empirical uncertainty intervals. Their coverage is not a certified compositor-to-tick guarantee, so the frame-timing gate remains failed.

## Dataset

88 completed matches, 3070 accepted deployments, 72019 captured frames. Per-match capture rates range from 9.55 to 9.86 FPS. Sanitized H.264 media uses actual arrival/production timestamps in sidecars; nominal container FPS is not used as a native tick label.
New v3 artifacts: 1.127 GiB. Live-loop total, counting hardlinks once: 4.604 GiB. No v2 evidence was deleted.
Allocated storage is 1.229 GiB for v3 and 4.820 GiB for live-loop, also within both caps. 3064 deployments have complete cue windows; the six incomplete windows belong to censored protocol-1 training tails.
Seeds and deck multisets are disjoint. The roster contains P16 plus the 40 C56 additions. Deployment labels require native scheduling success, hand disappearance and cost evidence. Negative windows are explicit. The added plan covers normal, double and triple-elixir phases and waits for expensive cards.
Primary heldout scoring uses 10 protocol-2 matches with command logging and a terminal capture target of at least 700 ms. Every scored event's full 500 ms cue window passed audit. This capture eligibility rule was declared before model fitting. Earlier protocol-1 terminal windows are excluded from training, and protocol-1 validation/heldout captures remain diagnostic. Uncollected adaptive-plan episodes are not represented as completed.

## Heldout gates

| Gate | Target | Measured | Verdict |
|---|---:|---:|---|
| Correct card/side within 0.5 s, recall | >=90% | 64.29% | FAIL |
| Event precision | >=90% | 66.67% | FAIL |
| Placement within one tile, all plays | >=90% | 57.86% | FAIL |
| Opponent elixir mean MAE | <=0.75 | 2.1141 | FAIL |
| Nominal 90% elixir interval coverage | 85-95% diagnostic band | 86.05% | IN BAND |
| Hand accuracy when concentrated | >=90% | unmeasured | FAIL |
| Frame tick certification | Required | Empirical bounds only | FAIL |

There are 180/280 timely matches and 90 false positives. Timing matches are one-to-one, after the event bracket upper bound and within 500 ms of its lower bound. Availability includes measured processing time and cumulative FIFO backlog. This is an offline scheduling estimate, not a concurrent capture/perception/search measurement. Misses and unknown placement count against the placement denominator.
Derived state is scored at 631 native query times spaced at least one second apart, using only already-completed pixel predictions and elapsed host time. Nominal 90% interval mean width is 8.2828 elixir. Hand concentration coverage is 0.00%, over 0 concentrated samples. Empty concentration coverage cannot pass.

Being inside the predeclared coverage band is a limited diagnostic. The wide spread is not useful precision or proof of calibration.
The whole-episode bootstrap 95% interval for coverage is 82.91% to 89.42%; the nominal 90% level remains above that interval. Elixir MAE bootstrap interval: 1.9184 to 2.3669.

## Per-card events

| Card | Truth | Predictions | Recall | Precision | Placement, all truth |
|---|---:|---:|---:|---:|---:|
| AngryBarbarians | 6 | 9 | 100.00% | 66.67% | 100.00% |
| ArcherQueen | 5 | 5 | 100.00% | 100.00% | 80.00% |
| Archers | 5 | 6 | 100.00% | 83.33% | 100.00% |
| Arrows | 4 | 0 | 0.00% | unmeasured | 0.00% |
| BabyDragon | 8 | 7 | 87.50% | 100.00% | 75.00% |
| Balloon | 3 | 3 | 100.00% | 100.00% | 100.00% |
| BarbLog | 6 | 3 | 50.00% | 100.00% | 16.67% |
| Bats | 5 | 6 | 80.00% | 66.67% | 80.00% |
| Berserker | 5 | 4 | 60.00% | 75.00% | 60.00% |
| BlowdartGoblin | 3 | 3 | 100.00% | 100.00% | 100.00% |
| BombTower | 9 | 9 | 88.89% | 88.89% | 77.78% |
| Cannon | 4 | 5 | 100.00% | 80.00% | 100.00% |
| DarkPrince | 5 | 3 | 60.00% | 100.00% | 60.00% |
| Earthquake | 5 | 10 | 40.00% | 20.00% | 20.00% |
| ElectroSpirit | 3 | 2 | 33.33% | 50.00% | 33.33% |
| FireSpirits | 10 | 10 | 80.00% | 80.00% | 80.00% |
| Fireball | 6 | 2 | 33.33% | 100.00% | 0.00% |
| Firecracker | 3 | 3 | 33.33% | 33.33% | 33.33% |
| FirespiritHut | 4 | 3 | 50.00% | 66.67% | 50.00% |
| Ghost | 6 | 4 | 66.67% | 100.00% | 50.00% |
| Giant | 3 | 4 | 100.00% | 75.00% | 100.00% |
| GoblinBarrel | 5 | 0 | 0.00% | unmeasured | 0.00% |
| GoblinGang | 4 | 3 | 75.00% | 100.00% | 75.00% |
| GoblinHut | 5 | 8 | 60.00% | 37.50% | 40.00% |
| Goblins | 6 | 5 | 66.67% | 80.00% | 66.67% |
| Goblinstein | 2 | 1 | 50.00% | 100.00% | 50.00% |
| Golem | 6 | 6 | 83.33% | 83.33% | 83.33% |
| HogRider | 6 | 6 | 83.33% | 83.33% | 83.33% |
| IceGolem | 3 | 6 | 100.00% | 50.00% | 100.00% |
| IceSpirit | 7 | 9 | 85.71% | 66.67% | 85.71% |
| InfernoTower | 6 | 13 | 83.33% | 38.46% | 83.33% |
| Knight | 4 | 0 | 0.00% | unmeasured | 0.00% |
| Lightning | 5 | 6 | 80.00% | 66.67% | 60.00% |
| Log | 6 | 22 | 66.67% | 18.18% | 33.33% |
| MightyMiner | 3 | 1 | 33.33% | 100.00% | 33.33% |
| Miner | 5 | 0 | 0.00% | unmeasured | 0.00% |
| MiniPekka | 5 | 5 | 40.00% | 40.00% | 40.00% |
| MinionHorde | 4 | 2 | 50.00% | 100.00% | 50.00% |
| Minions | 4 | 4 | 100.00% | 100.00% | 100.00% |
| Musketeer | 7 | 11 | 100.00% | 63.64% | 100.00% |
| Poison | 2 | 1 | 50.00% | 100.00% | 0.00% |
| Prince | 2 | 2 | 50.00% | 50.00% | 50.00% |
| Princess | 6 | 4 | 66.67% | 100.00% | 50.00% |
| Rascals | 4 | 6 | 100.00% | 66.67% | 100.00% |
| Rocket | 5 | 0 | 0.00% | unmeasured | 0.00% |
| RoyalDelivery | 9 | 0 | 0.00% | unmeasured | 0.00% |
| RoyalHogs | 3 | 3 | 66.67% | 66.67% | 66.67% |
| SkeletonArmy | 3 | 4 | 100.00% | 75.00% | 66.67% |
| Skeletons | 5 | 4 | 80.00% | 100.00% | 80.00% |
| Tesla | 5 | 6 | 100.00% | 83.33% | 100.00% |
| Tornado | 6 | 8 | 16.67% | 12.50% | 0.00% |
| Valkyrie | 5 | 6 | 80.00% | 66.67% | 80.00% |
| Wallbreakers | 9 | 9 | 77.78% | 77.78% | 77.78% |
| Wizard | 5 | 3 | 60.00% | 100.00% | 40.00% |
| Xbow | 5 | 2 | 40.00% | 100.00% | 40.00% |
| Zap | 5 | 3 | 60.00% | 100.00% | 60.00% |

## Implementation and limits

Fusion uses a causal three-frame network, persistent body births, multi-unit grouping, secondary-spawn suppression, learned deploy-clock offsets and own HUD transitions. Spell identity combines both visual ownership heads; a short causal buffer resolves ownership from own HUD evidence. Spawner sources can be retained from perceived deployments because the frozen entity model covers P16 bodies. Suppression removes weak birth/clock boosts, not independent temporal evidence.
The opponent filter tracks unrevealed deck tokens, hand/queue/refill hypotheses, affordability, uncertain event acceptance and latent missed plays. It exposes a joint sampler and learns an elixir residual distribution on validation only. That correction affects both spread and search samples. The observed heldout coverage above, not the existence of this correction, determines whether spread is calibrated.
The v3 HUD reader separates white digits from the red overtime background and exposes that visible phase cue. Late-entry state starts with unknown deck tokens and a bounded elixir prior, without inventing plays through unobserved warmup time. State-event reliability uses a separate two-second validation identity window; the primary event gate remains 500 ms.
A calibration tie bug was corrected using validation only. Equal-F1 thresholds now prefer more matches, fewer predictions and then the higher threshold. Original validation and uninspected heldout measurements were retained under *-initial-tie-bug. Weights, candidates and inference timestamps did not change.
C56 champion cycle/status behavior is not separately certified. The frozen body model does not become a full C56 entity detector merely because event heads were added. These limits must not be converted into an L2 readiness claim.

## Evidence and changed files

Evidence: v3/dataset-merged, v3/audit, v3/model, v3/inference-validation, v3/inference-heldout, v3/evaluation-validation, v3/evaluation-heldout, v3/boundary-runtime.json and emulator ownership/stop receipts. Superseded capture attempts remain named and excluded.
Vision: src/clasher/vision/l1_timing_v3.py, l1_events_v3.py, l1_derived_v3.py, l1_hud_v3.py. Scripts: certify_l1_timing_v3.py, analyze_l1_timing_v3.py, l1_native_capture_v3.py, collect_l1_stream_v3.py, audit_l1_stream_v3.py, finish_l1_collection_v3.py, stop_l1_reference_v3.py, train_l1_stream_v3.py, infer_l1_stream_v3.py, evaluate_l1_stream_v3.py, verify_l1_v3_boundary.py, run_l1_v3_pipeline.py, report_l1_v3.py. Tests: tests/test_l1_v3.py. Reports: this file, PROGRESS.md and v3/.
Only owned offline emulators were used. Game-app IPv4/IPv6 egress was rejected. No official client, account, probe/APK modification, engine edit, protected-directory write, Git mutation or foreign-process signal was performed.
Final verification passed all 24 integrity/resource checks and all 51 focused L1 tests. Model/prediction hashes, native observation fences, cost parity, split isolation, full roster coverage, protected-reference identity and owned emulator shutdown passed. Acceptance remains false because the stream quality and timing-certification gates failed.
