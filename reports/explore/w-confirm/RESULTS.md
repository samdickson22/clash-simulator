# W confirmation and latency — 2026-10-09

**Frozen exploration lane; 600 paired fresh seeds per main arm.** Search opponents on both sides, d=27 on both sides, five train decks / 25 matchups, alternating seats. Supplementary W-vs-W uses the first 100 paired seeds. No tuning on reporting seeds; all 1,900 games are terminal.

| Focal vs opponent | Wins / losses / draws | Loss %, paired-bootstrap 95% CI | Loss change vs control, pp |
|---|---:|---:|---:|
| 0 vs 0 | 313 / 287 / 0 | 47.83 [43.83, 51.83] | — |
| W vs 0 | 480 / 120 / 0 | 20.00 [16.83, 23.33] | -27.83 [-32.17, -23.67] |
| H16 vs 0 | 305 / 295 / 0 | 49.17 [45.17, 53.17] | +1.33 [-3.00, +5.83] |
| W vs W | 49 / 51 / 0 | 51.00 [41.00, 61.00] | — |

Bootstrap: 5,000 shared seed resamples across main arms and every pooled metric; pointwise percentile 95% intervals, unadjusted. WW has a separate descriptive 100-seed bootstrap and is not a 600-seed confirmation. Draws remain separate. Paired main-arm contrasts, numerators and denominators are in [results.json](results.json).

## Tempo loss-review metrics

| Metric | 0 vs 0 | W vs 0 | H16 vs 0 | W vs W |
|---|---:|---:|---:|---:|
| arrival_under4_fraction | 93.93 [93.41, 94.42] | 61.40 [59.67, 63.07] | 94.18 [93.69, 94.66] | 64.54 [61.27, 67.97] |
| no_affordable_defender_in_hand_fraction | 65.71 [64.49, 66.94] | 28.40 [27.00, 29.81] | 64.56 [63.36, 65.78] | 30.30 [27.09, 33.65] |
| defender_not_in_hand_fraction | 0.07 [0.03, 0.13] | 1.53 [1.20, 1.89] | 0.06 [0.02, 0.12] | 1.33 [0.59, 2.31] |
| time_at_max_fraction | 0.00 [0.00, 0.00] | 0.17 [0.13, 0.21] | 0.00 [0.00, 0.00] | 0.14 [0.07, 0.24] |
| leaked_elixir_lower_bound_per_minute | 0.00 [0.00, 0.00] | 0.06 [0.04, 0.08] | 0.00 [0.00, 0.00] | 0.06 [0.02, 0.10] |
| rejected_play_fraction | 0.00 [0.00, 0.01] | 0.02 [0.00, 0.04] | 0.00 [0.00, 0.00] | 0.02 [0.00, 0.07] |

| Arm / expensive card | In-hand opportunities | Affordable %, 95% CI | Accepted plays / deck-minute, 95% CI |
|---|---:|---:|---:|
| 0 / Xbow | 40451 | 0.20 [0.16, 0.24] | 0.06 [0.04, 0.08] |
| 0 / Giant | 36485 | 0.46 [0.36, 0.59] | 0.03 [0.01, 0.05] |
| 0 / Rocket | 36783 | 0.31 [0.25, 0.38] | 0.01 [0.00, 0.02] |
| 0 / Fireball | 79376 | 1.33 [1.21, 1.46] | 0.07 [0.05, 0.09] |
| W / Xbow | 14821 | 14.01 [12.34, 15.70] | 0.61 [0.54, 0.68] |
| W / Giant | 13170 | 10.08 [9.17, 10.98] | 0.11 [0.08, 0.15] |
| W / Rocket | 15459 | 13.40 [11.60, 15.25] | 0.23 [0.19, 0.27] |
| W / Fireball | 29163 | 33.63 [31.93, 35.27] | 0.43 [0.38, 0.48] |
| H16 / Xbow | 40007 | 0.21 [0.17, 0.26] | 0.10 [0.08, 0.12] |
| H16 / Giant | 36004 | 0.36 [0.30, 0.43] | 0.09 [0.06, 0.12] |
| H16 / Rocket | 38266 | 0.24 [0.20, 0.29] | 0.02 [0.01, 0.04] |
| H16 / Fireball | 78731 | 1.07 [0.98, 1.17] | 0.08 [0.06, 0.09] |
| WW / Xbow | 2367 | 11.45 [7.70, 15.42] | 0.55 [0.40, 0.69] |
| WW / Giant | 2515 | 8.95 [6.74, 11.32] | 0.12 [0.05, 0.20] |
| WW / Rocket | 2550 | 8.90 [6.35, 11.57] | 0.14 [0.07, 0.22] |
| WW / Fireball | 5013 | 31.40 [27.65, 35.08] | 0.51 [0.38, 0.63] |

Affordability is measured at decision opportunities; timed WAIT reduces those opportunities. Accepted plays include zero-use deck games. Arrival is the ledger’s lane-incursion onset, and defender availability is its generic non-spell/non-win-condition hand proxy. Leaked elixir is a conservative cap-interval lower bound, omitting partial approaches to cap and collector overflow. Humans’ historical 16–19% under-4 reference is descriptive, not an objective.

## Decision latency in confirmation games

| Arm | Wall p50 / p95 / p99, ms | CPU p50 / p95, ms | Wall >200 ms |
|---|---:|---:|---:|
| 0 | 5.3 / 344.5 / 482.4 | 5.3 / 344.3 | 19.42% |
| W | 258.4 / 491.9 / 698.5 | 258.2 / 491.7 | 68.82% |
| H16 | 5.3 / 602.8 / 795.7 | 5.3 / 602.4 | 24.16% |
| WW | 262.9 / 508.4 / 722.9 | 262.8 / 508.1 | 68.87% |

These full-decision timings include observation, belief update, candidate generation, public reconstruction, all three styles and submission. They come from a loaded, idle-scheduled 50-worker simulation, not a live latency guarantee. Confirmation uses the private native WAIT extension with full work; it does not use reduced styles, gating or deduplication.

## Fixed-state agreement versus latency

Separate frozen corpus: **125 public decision states**, all 25 matchups, both seats, ticks 90/300/600/1200/2400 on disjoint scripted-driver seeds. These synthetic trajectories are not states selected by W during the confirmation games. Three repeats/state; all candidate lists and public roots regenerate exactly. Inputs and sampled public beliefs are fixed before timing. Warmup/profile samples are excluded, execution order alternates. Scores/actions below compare to the full W reference in the same opponent-delay model; no reduced variant has a win-rate claim.

Primary budget: one physical 3990X core on 03, Torch/BLAS/Rayon=1. Four threads get four physical cores and **exceed this budget**. Timing includes candidate generation, public root reconstruction and scoring from a prepared public input; image/sensor parsing, belief inference and actuator/network are excluded. The p95 target below is empirical for this fixed-state scope, not end-to-end live admission.

### Original tempo W: immediate hypothetical opponent

| Variant | Exact action agreement | Play/WAIT agreement | Wall p50 / p95, ms | CPU p95, ms | Core budget |
|---|---:|---:|---:|---:|---|
| full | 125/125 (100.00%) | 100.00% | 65.6 / 358.7 | 358.5 | one core |
| dedup | 125/125 (100.00%) | 100.00% | 54.4 / 345.8 | 345.6 | one core |
| wait1 | 116/125 (92.80%) | 94.40% | 43.4 / 335.0 | 334.8 | one core |
| wait2 | 123/125 (98.40%) | 98.40% | 54.6 / 346.9 | 346.7 | one core |
| gate4 | 124/125 (99.20%) | 99.20% | 65.6 / 324.8 | 324.6 | one core |
| gate6 | 124/125 (99.20%) | 99.20% | 65.5 / 324.0 | 323.6 | one core |
| gate8 | 125/125 (100.00%) | 100.00% | 66.0 / 361.1 | 360.8 | one core |
| threads4 | 125/125 (100.00%) | 100.00% | 37.8 / 140.0 | 375.7 | four cores |
| native-full | 125/125 (100.00%) | 100.00% | 65.6 / 349.5 | 349.3 | one core |
| native-dedup | 125/125 (100.00%) | 100.00% | 54.1 / 336.7 | 336.5 | one core |
| native-wait1 | 116/125 (92.80%) | 94.40% | 43.1 / 325.3 | 325.1 | one core |
| native-wait2 | 123/125 (98.40%) | 98.40% | 54.3 / 337.8 | 337.6 | one core |
| native-gate4 | 124/125 (99.20%) | 99.20% | 64.8 / 314.2 | 314.0 | one core |
| native-gate6 | 124/125 (99.20%) | 99.20% | 64.8 / 316.0 | 315.7 | one core |
| native-gate8 | 125/125 (100.00%) | 100.00% | 66.2 / 350.9 | 350.7 | one core |
| native-threads4 | 125/125 (100.00%) | 100.00% | 37.3 / 124.2 | 354.0 | four cores |

### Confirmation W: symmetric d=27 hypothetical opponent

| Variant | Exact action agreement | Play/WAIT agreement | Wall p50 / p95, ms | CPU p95, ms | Core budget |
|---|---:|---:|---:|---:|---|
| full | 125/125 (100.00%) | 100.00% | 63.8 / 320.8 | 320.6 | one core |
| dedup | 125/125 (100.00%) | 100.00% | 53.1 / 311.3 | 310.9 | one core |
| wait1 | 121/125 (96.80%) | 98.40% | 43.1 / 299.1 | 298.9 | one core |
| wait2 | 123/125 (98.40%) | 99.20% | 53.7 / 310.8 | 310.7 | one core |
| gate4 | 121/125 (96.80%) | 98.40% | 64.0 / 295.8 | 295.7 | one core |
| gate6 | 121/125 (96.80%) | 98.40% | 63.9 / 296.2 | 296.1 | one core |
| gate8 | 125/125 (100.00%) | 100.00% | 65.6 / 321.5 | 321.3 | one core |
| threads4 | 125/125 (100.00%) | 100.00% | 36.7 / 118.6 | 326.2 | four cores |

### Adaptive check of the one-core tail budget

Added after the frozen WAIT-only comparison missed 200 ms, using the same fixed states and complete reference scores. Every variant below is an approximation and retains all candidate actions. `plays1/2` reduces only immediate-play styles; `all1/2` reduces styles for every candidate; `plays2wait1` retains three styles for original WAIT, two for plays and one for timed waits. `horizon80/100/120` retains all three styles but shortens the horizon for every candidate. Original-model variants use the native loop. See [AMENDMENTS.md](AMENDMENTS.md) and [latency-extra.json](latency-extra.json). No reporting-seed or win-rate tuning.

| Model / variant | Exact action agreement | Play/WAIT agreement | One-core wall p50 / p95, ms | Mean / maximum full-score regret |
|---|---:|---:|---:|---:|
| original / plays1 | 112/125 (89.60%) | 99.20% | 63.8 / 178.8 | 0.0004 / 0.0123 |
| original / plays2 | 117/125 (93.60%) | 100.00% | 63.9 / 259.9 | 0.0001 / 0.0054 |
| original / all1 | 108/125 (86.40%) | 96.00% | 35.7 / 145.2 | 0.0007 / 0.0123 |
| original / all2 | 116/125 (92.80%) | 97.60% | 50.0 / 243.7 | 0.0003 / 0.0120 |
| original / plays2wait1 | 111/125 (88.80%) | 95.20% | 42.6 / 236.6 | 0.0005 / 0.0146 |
| original / horizon80 | 89/125 (71.20%) | 90.40% | 44.4 / 185.4 | 0.0039 / 0.0396 |
| original / horizon100 | 94/125 (75.20%) | 90.40% | 49.7 / 225.2 | 0.0025 / 0.0364 |
| original / horizon120 | 97/125 (77.60%) | 95.20% | 54.9 / 262.6 | 0.0019 / 0.0396 |
| symmetric / plays1 | 117/125 (93.60%) | 99.20% | 63.3 / 165.4 | 0.0004 / 0.0157 |
| symmetric / plays2 | 121/125 (96.80%) | 99.20% | 63.3 / 243.2 | 0.0000 / 0.0012 |
| symmetric / all1 | 116/125 (92.80%) | 98.40% | 35.6 / 137.6 | 0.0004 / 0.0140 |
| symmetric / all2 | 122/125 (97.60%) | 100.00% | 49.5 / 227.3 | 0.0000 / 0.0010 |
| symmetric / plays2wait1 | 119/125 (95.20%) | 97.60% | 42.5 / 222.6 | 0.0002 / 0.0140 |
| symmetric / horizon80 | 92/125 (73.60%) | 89.60% | 43.4 / 158.9 | 0.0038 / 0.0429 |
| symmetric / horizon100 | 93/125 (74.40%) | 91.20% | 48.7 / 203.7 | 0.0035 / 0.0419 |
| symmetric / horizon120 | 99/125 (79.20%) | 93.60% | 54.3 / 238.4 | 0.0021 / 0.0267 |

### Coarse scan, full refinement

Final latency-only check: every play gets a balanced-style scan, the top 3/5/8 plays get the other two styles, and every WAIT receives full three-style scoring with exact original-WAIT/10-tick reuse. Final selection considers those refined plays and all WAITs in original tie order. Every retained final score matches full W exactly; omitted contenders can still change the decision. Three repeats on the same fixed states, one physical core. `paired-full` is a fresh full-W baseline interleaved in this final comparison, so fleet load changing as reporting finished cannot be mistaken for a reduction benefit. [latency-screen.json](latency-screen.json).

| Model / refinement count | Exact action agreement | Play/WAIT agreement | One-core wall p50 / p95, ms | Mean / maximum full-score regret |
|---|---:|---:|---:|---:|
| original / paired-full | 125/125 (100.00%) | 100.00% | 52.5 / 281.6 | 0.0000 / 0.0000 |
| original / screen3 | 122/125 (97.60%) | 100.00% | 43.8 / 158.9 | 0.0000 / 0.0017 |
| original / screen5 | 122/125 (97.60%) | 100.00% | 43.7 / 172.2 | 0.0000 / 0.0017 |
| original / screen8 | 124/125 (99.20%) | 100.00% | 43.8 / 192.9 | 0.0000 / 0.0001 |
| symmetric / paired-full | 125/125 (100.00%) | 100.00% | 51.6 / 258.6 | 0.0000 / 0.0000 |
| symmetric / screen3 | 123/125 (98.40%) | 99.20% | 43.4 / 143.7 | 0.0001 / 0.0054 |
| symmetric / screen5 | 124/125 (99.20%) | 100.00% | 43.3 / 157.0 | 0.0000 / 0.0009 |
| symmetric / screen8 | 125/125 (100.00%) | 100.00% | 43.5 / 176.6 | 0.0000 / 0.0000 |

`dedup` reuses original WAIT’s rollout for the identical 10-tick WAIT, preserving score addition and tie order. This is exact shared work; general branching prefixes were not implemented because continuation must retain both queues, phase and RNG. `wait1/2` uses one/two styles only for the three timed waits; immediate plays and original WAIT retain all three styles. `gateX` omits timed waits at elixir ≥X. `native-*` moves original W’s unchanged cadence/command schedule into the existing Rust command path with opponent_delay=0. Symmetric W already uses that native path. `threads4` uses GIL release with independent private mutable roots. Exact agreement retains action IDs/durations. Reference-score regret and exact score-vector counts are in [latency-results.json](latency-results.json).

### Why W increased the historical median

Appending timed WAIT candidates turns formerly single-WAIT decisions into full root reconstruction and nine extra style/candidate rollouts, even when no card is affordable. The original W adapter also runs each delayed rollout through Python/native calls at every cadence/execution boundary. Deduplicating original WAIT and 10-tick WAIT removes three redundant rollouts. The profile below shows native combat stepping and opponent selection dominate the measured work; moving the command loop into Rust alone gives little tail improvement. Dense immediate-play candidate evaluation remains after WAIT-only reductions. These mechanisms explain the historical median jump; current fixed-state numbers use a different state distribution, so they do not claim to reproduce the old 330 ms median.

| Full original-W profile function | Calls | Self profiled seconds | Cumulative seconds |
|---|---:|---:|---:|
| `/mpac/sdicks02/jobs/clasher/w-confirm-20261009-r1/repo/reports/explore/w-confirm/latency.py:60:decision` | 8 | 0.000 | 3.043 |
| `/mpac/sdicks02/jobs/clasher/w-confirm-20261009-r1/repo/reports/explore/w-confirm/planner.py:26:score_candidates` | 8 | 0.003 | 2.511 |
| `/mpac/sdicks02/jobs/clasher/w-confirm-20261009-r1/repo/reports/explore/w-confirm/planner.py:42:evaluate` | 576 | 0.001 | 2.505 |
| `/mpac/sdicks02/jobs/clasher/w-confirm-20261009-r1/repo/reports/explore/w-confirm/planner.py:85:simulate_commands` | 576 | 0.001 | 2.504 |
| `/mpac/sdicks02/jobs/clasher/w-confirm-20261009-r1/repo/src/clasher/analysis/loss_review/tempo.py:55:delayed_rollout` | 576 | 0.004 | 2.338 |
| `/mpac/sdicks02/jobs/clasher/w-confirm-20261009-r1/repo/src/clasher/analysis/loss_review/search_ab.py:98:delayed_rollout` | 504 | 0.001 | 2.044 |
| `/mpac/sdicks02/jobs/clasher/w-confirm-20261009-r1/repo/reports/strategy_council_20260928/search-noise-s6/delay.py:90:delayed_rollout` | 504 | 0.019 | 2.044 |
| `~:0:<method 'step' of 'clasher_core.BattleState' objects>` | 11227 | 1.783 | 1.783 |
| `~:0:<method 'select_action' of 'clasher_core.NativeScripts' objects>` | 13591 | 0.537 | 0.537 |
| `/mpac/sdicks02/jobs/clasher/w-confirm-20261009-r1/repo/src/clasher/analysis/loss_review/tempo.py:43:candidates` | 8 | 0.000 | 0.351 |
| `/mpac/sdicks02/jobs/clasher/w-confirm-20261009-r1/repo/src/clasher/analysis/loss_review/search_ab.py:61:candidates` | 8 | 0.001 | 0.351 |
| `/mpac/sdicks02/jobs/clasher/w-confirm-20261009-r1/repo/src/clasher/rl/contract_v5.py:581:build` | 32 | 0.000 | 0.301 |

cProfile covers eight serial decisions; cumulative rows overlap and must not be added.

## Recommendation

W retains a loss-rate advantage against the baseline search opponent under symmetric delay. Keep it as the exploration candidate for a separately qualified live test.
Exact WAIT deduplication is a modest safe saving on this corpus: native original-W agreement is 125/125, one-core p95 336.7 ms. The native loop alone is insufficient, and four-core timing must not be presented as a one-core solution. Repeat prospective live deadline and completed-candidate qualification; these games and prepared-state timings do not authorize a production change.
Among tested one-core approximations meeting the empirical target, screen8 preserves 124/125 choices at p95 192.9 ms. This is an agreement-versus-cost result only; any adoption needs a separate fresh outcome comparison.
Top-eight refinement in the confirmation model preserves 125/125 choices at one-core p95 176.6 ms. It still omits contenders and remains an approximation despite perfect agreement on this finite corpus. Prioritize it for that fresh outcome test.

## Reproducibility, validation and compute

Freeze [PLAN.md](PLAN.md), config SHA256 `414ecf5235f899c41e874e9c03465c2a944de2f5372f25747b0159bfcaea42a8`, committed/pushed before games in `e006fdba`. See [AMENDMENTS.md](AMENDMENTS.md), [seed-audit.json](seed-audit.json), [runtime pin](receipts/runtime-pin.json), [qualification](receipts/qualification.json), [ordinary parity](receipts/ordinary-parity.json), [state manifest](receipts/state-manifest.json), and [compute](receipts/compute.json).

All arms share build48 combat semantics. The private native binary adds timed waits only to the existing delay-command path and uses GIL-release/v3; ordinary actions have exact score/trace/digest parity with the supplied build48 quickwins binary. This matched comparison is not an engine-parity claim to historical tempo’s build46. Fair inputs remain public board/own HUD, accepted enemy card events, independent sampled hidden-state/RNG and the train-only prior. Physical opponent search is stronger than scripts but its rollout futures still use scripts and a public reconstruction model.

Compute: 03 only, nice 10 / SCHED_IDLE, detached via setsid; peak own processes **54**, peak combined Clasher **57**. Completed reporting game CPU: **35.07 core-hours**; startup, profiler and technical attempts are outside that subtotal. No leased/GPU-reserved host or heavy 05 work. Raw game/state/profile/build artifacts and caches stay on 03 under `/mpac/sdicks02/jobs/clasher/w-confirm-20261009-r1/`; no raw games are committed. The reducer validates full paired coverage, terminal games, identical seed/seat/shuffled decks, capacity one and queue conservation on both sides. Rare physical deployment rejections remain in the outcomes and ledger metrics; no seed/game is dropped or replaced. Aggregate counts are retained in results.json.

All lane jobs exited after reporting and latency completed; see [shutdown receipt](receipts/shutdown.json).
