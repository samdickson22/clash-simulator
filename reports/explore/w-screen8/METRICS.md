# Paired loss-review metrics

Pooled ratios resampled by paired seed; 5,000 shared bootstrap resamples. Percentages except leakage (elixir/minute). Exact numerators/denominators, expensive-card opportunity counts and all arm contrasts are in results.json.

| Metric | Baseline | Full W | Screen8 |
|---|---:|---:|---:|
| arrival_under4_fraction | 93.69 [93.18, 94.20] | 61.29 [59.68, 62.93] | 61.31 [59.69, 62.90] |
| no_affordable_defender_in_hand_fraction | 63.78 [62.59, 65.00] | 28.61 [27.25, 29.97] | 28.59 [27.23, 29.95] |
| defender_not_in_hand_fraction | 0.09 [0.04, 0.15] | 1.68 [1.30, 2.11] | 1.66 [1.27, 2.09] |
| time_at_max_fraction | 0.00 [0.00, 0.00] | 0.18 [0.14, 0.22] | 0.18 [0.14, 0.22] |
| leaked_elixir_lower_bound_per_minute | 0.00 [0.00, 0.00] | 0.07 [0.05, 0.08] | 0.07 [0.05, 0.08] |
| rejected_play_fraction | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.01] | 0.00 [0.00, 0.01] |

| Arm / card | Affordable at in-hand opportunity %, 95% CI | Accepted plays / deck-minute, 95% CI |
|---|---:|---:|
| Baseline / Xbow | 0.19 [0.15, 0.23] | 0.05 [0.04, 0.07] |
| Baseline / Giant | 0.40 [0.31, 0.51] | 0.02 [0.01, 0.04] |
| Baseline / Rocket | 0.28 [0.22, 0.35] | 0.00 [0.00, 0.01] |
| Baseline / Fireball | 1.27 [1.16, 1.38] | 0.07 [0.05, 0.08] |
| Baseline / Log | 38.29 [37.47, 39.09] | 3.32 [3.26, 3.38] |
| Full W / Xbow | 14.66 [13.04, 16.22] | 0.64 [0.58, 0.70] |
| Full W / Giant | 9.37 [8.54, 10.18] | 0.16 [0.12, 0.20] |
| Full W / Rocket | 12.90 [11.33, 14.53] | 0.18 [0.15, 0.22] |
| Full W / Fireball | 34.35 [32.58, 36.08] | 0.44 [0.39, 0.48] |
| Full W / Log | 81.31 [80.44, 82.12] | 1.60 [1.53, 1.66] |
| Screen8 / Xbow | 14.63 [13.04, 16.20] | 0.64 [0.58, 0.70] |
| Screen8 / Giant | 9.40 [8.57, 10.20] | 0.17 [0.13, 0.21] |
| Screen8 / Rocket | 12.97 [11.39, 14.58] | 0.18 [0.14, 0.21] |
| Screen8 / Fireball | 34.55 [32.78, 36.32] | 0.43 [0.38, 0.48] |
| Screen8 / Log | 81.39 [80.55, 82.20] | 1.59 [1.53, 1.66] |

| Arm | Full-decision wall p50 / p95 / p99, ms | CPU p50 / p95 / p99, ms | Wall >200 ms, % | Decisions |
|---|---:|---:|---:|---:|
| Baseline | 5.2 / 343.7 / 482.4 | 5.2 / 343.5 / 482.1 | 19.51 | 192853 |
| Full W | 258.5 / 491.4 / 696.1 | 258.4 / 491.1 / 695.7 | 69.02 | 77474 |
| Screen8 | 176.8 / 330.2 / 460.0 | 176.7 / 330.0 / 459.7 | 37.63 | 77624 |

Affordability is measured at decision opportunities, which timed WAIT reduces. Accepted plays include zero-use deck games. Arrival is lane-incursion onset; defender availability is the generic non-spell/non-win-condition hand proxy. Leakage is a conservative cap-interval lower bound. Scored opportunities include the balanced scan for every initial candidate, including plays omitted from full refinement. The reference screen adapter does not tally wait_counts; its empty tally is not zero WAITs.

Completed reporting game CPU: 29.05 core-hours. Startup, builds and qualification are outside this subtotal.

The study uses the frozen w-confirm screen8 adapter and private WAIT native binary; the production batch implementation is separately proven exact on the frozen 125-state corpus. Games use sampled public roots and scripted rollout futures, with a physical baseline search opponent. No reporting-seed tuning or game replacement. Loaded SCHED_IDLE timing is descriptive; no image/sensor/network live admission is claimed.
