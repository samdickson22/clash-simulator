# d27 tempo exploration — 2026-10-09

**Exploration lane. Non-confirmatory, no pre-registration, no eval/heldout data. Research guidance only.**

1,000 paired fresh seeds per arm; 6,000 terminal games in the primary comparison. Five decks, all 25 matchups, three scripted opponents, alternating seats, d=27. Same fixed-work fair S6 ledger/A/B harness.

**Measured outcome:** E: loss difference uncertain (interval includes zero); H12: fewer losses; H16: fewer losses; W: fewer losses; EW: fewer losses. Pointwise paired bootstrap intervals are exploratory and unadjusted for the parameter/arm search.

**The 200 ms budget is not met in this fixed-work experiment.** Latency includes public observation, belief update, candidate generation, root reconstruction, scoring and command submission. Active wall time excludes explicit guard pauses; raw wall time includes them. CPU time is reported separately and is not a wall-time guarantee.

| Arm | Wins / losses / draws | Win rate, 95% CI | Loss rate, 95% CI | Paired loss change vs baseline, pp |
|---|---:|---:|---:|---:|
| 0 | 891 / 109 / 0 | 89.10% [87.10, 91.00] | 10.90% [9.00, 12.90] | — |
| E | 876 / 124 / 0 | 87.60% [85.60, 89.50] | 12.40% [10.50, 14.40] | +1.50 [-0.30, 3.40] |
| H12 | 929 / 71 / 0 | 92.90% [91.30, 94.50] | 7.10% [5.50, 8.70] | -3.80 [-5.50, -2.10] |
| H16 | 937 / 63 / 0 | 93.70% [92.20, 95.10] | 6.30% [4.90, 7.80] | -4.60 [-6.50, -2.80] |
| W | 993 / 7 / 0 | 99.30% [98.70, 99.70] | 0.70% [0.30, 1.30] | -10.20 [-12.20, -8.20] |
| EW | 983 / 17 / 0 | 98.30% [97.40, 99.00] | 1.70% [1.00, 2.60] | -9.20 [-11.20, -7.30] |

W had fewer fresh reporting losses than the separately selected EW combination (7 versus 17). The E-only result is uncertain, and adding E to W did not improve the observed point estimate. Under-4 arrivals remained well above the 16–19% human reference even with W.

Win, loss and draw estimates and paired CIs are all in [results.json](results.json). Bootstrap: 2,000 shared seed resamples, paired across every arm and metric; event rates pool numerator and denominator counts. Zero empirical rates and [0,0] intervals do not establish population upper bounds.

## Arm definitions and separate tuning

0 is the original planner, horizon 160 ticks (8 s). E adds an own-elixir leaf option value with selected weight **0.005**. H12/H16 use 240/320 ticks (12/16 s). W adds explicit 10/20/40-tick WAIT candidates and a calibrated prior with selected weight **0.01**. The selected combination is **EW**, using the selected horizon **16 s** when it contains H.

The E option curve is nonnegative and concave: marginal value 1 below 4 elixir, 0.5 from 4 to 7, then −5.5/3 from 7 to 10. It is zero at 0 and 10 and positive in between. This rewards banked options, with diminishing marginal value and no full-cap bonus. The existing baseline elixir term remains present; terminal win/loss scores are unchanged. Only simulated own HUD elixir enters this extra term.

The W prior adds `weight × sqrt(wait_seconds) × (1 − own_elixir/10)` to WAIT root scores. It vanishes at full cap. Waiting suppresses own scripted follow-ups for the chosen duration inside rollouts and suppresses physical player decisions for the same duration; opponent behavior continues. It preserves all original immediate-play candidates and original RNG draws. The 0.5 s explicit wait has the same follow-up timing as baseline WAIT; the useful additional durations are 1 and 2 s.

Weights are selected from E={0.005,0.02} and W={0.0025,0.01}, plus H={12,16 s}, on 150 separate tuning seeds. Selection minimizes loss count, with ties preferring lower weights/shorter horizons. A second 150-seed block chooses among EH, EW, HW and EHW using the selected weights/horizon; ties use the fixed EW/EH/HW/EHW order. Reporting outcomes do not enter either selection.

| Tuning arm | Losses / 150 |
|---|---:|
| 0 | 16 |
| Elo | 19 |
| Ehi | 25 |
| H12 | 10 |
| H16 | 8 |
| Wlo | 1 |
| Whi | 0 |

| Combination selection arm | Losses / 150 |
|---|---:|
| 0 | 17 |
| EH | 9 |
| EW | 0 |
| HW | 1 |
| EHW | 0 |

## Loss-review metrics

| Metric | 0 | E | H12 | H16 | W | EW |
|---|---:|---:|---:|---:|---:|---:|
| arrival_under4_fraction | 89.71% | 90.19% | 90.39% | 90.34% | 61.17% | 62.90% |
| defender_not_in_hand_fraction | 0.09% | 0.12% | 0.17% | 0.19% | 2.04% | 1.61% |
| no_affordable_defender_in_hand_fraction | 63.15% | 63.37% | 64.80% | 64.39% | 29.84% | 31.65% |
| time_at_max_fraction | 0.00% | 0.00% | 0.00% | 0.00% | 0.12% | 0.15% |
| leaked_elixir_lower_bound_per_minute | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0346 | 0.0474 |
| response_latency_capped8_seconds | 4.4419 | 4.4092 | 4.4673 | 4.4490 | 5.0688 | 5.0278 |
| time_at_max_seconds_per_minute | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0733 | 0.0927 |
| card_per_deck_minute:Xbow | 0.0748 | 0.0669 | 0.1250 | 0.1661 | 0.7624 | 0.6196 |
| card_per_deck_minute:Giant | 0.0944 | 0.0782 | 0.1072 | 0.2117 | 0.2477 | 0.2340 |
| card_per_deck_minute:Rocket | 0.0066 | 0.0065 | 0.0170 | 0.0201 | 0.1473 | 0.1410 |
| card_per_deck_minute:Fireball | 0.1110 | 0.0961 | 0.1323 | 0.1196 | 0.2898 | 0.2932 |
| card_per_deck_minute:Log | 2.9777 | 3.1485 | 2.8099 | 2.7503 | 1.2920 | 1.4596 |

Defender availability uses the existing generic non-spell, non-win-condition hand proxy. Accepted card-play rates are per minute in games containing that card, including zero-use games. Cap leakage is the ledger’s conservative lower bound based on intervals already at full cap; it omits partial approaches to cap and collector overflow. All event counts, exposures and paired CIs are in the JSON.

| Arm / expensive card | Hand opportunities | Affordable, 95% CI | Accepted plays / deck-minute, 95% CI | Selected / offered |
|---|---:|---:|---:|---:|
| 0 / Xbow | 59433 | 0.25% [0.21, 0.29] | 0.0748 [0.06, 0.09] | 53 / 147 |
| 0 / Giant | 55830 | 0.64% [0.53, 0.79] | 0.0944 [0.07, 0.12] | 63 / 359 |
| 0 / Rocket | 63743 | 0.26% [0.21, 0.31] | 0.0066 [0.00, 0.01] | 5 / 164 |
| 0 / Fireball | 119917 | 2.10% [1.97, 2.23] | 0.1110 [0.09, 0.13] | 178 / 2522 |
| E / Xbow | 61124 | 0.26% [0.22, 0.30] | 0.0669 [0.05, 0.08] | 50 / 154 |
| E / Giant | 56667 | 0.68% [0.54, 0.83] | 0.0782 [0.06, 0.10] | 62 / 383 |
| E / Rocket | 64373 | 0.25% [0.21, 0.30] | 0.0065 [0.00, 0.01] | 5 / 162 |
| E / Fireball | 123796 | 2.05% [1.91, 2.20] | 0.0961 [0.08, 0.11] | 156 / 2538 |
| H12 / Xbow | 52697 | 0.32% [0.27, 0.39] | 0.1250 [0.10, 0.15] | 78 / 170 |
| H12 / Giant | 54018 | 0.45% [0.40, 0.50] | 0.1072 [0.09, 0.13] | 77 / 241 |
| H12 / Rocket | 64427 | 0.24% [0.20, 0.28] | 0.0170 [0.01, 0.03] | 14 / 154 |
| H12 / Fireball | 107983 | 1.85% [1.74, 1.96] | 0.1323 [0.11, 0.15] | 189 / 2002 |
| H16 / Xbow | 52162 | 0.39% [0.33, 0.46] | 0.1661 [0.14, 0.19] | 103 / 199 |
| H16 / Giant | 51913 | 0.56% [0.50, 0.63] | 0.2117 [0.18, 0.24] | 124 / 292 |
| H16 / Rocket | 63160 | 0.26% [0.22, 0.30] | 0.0201 [0.01, 0.03] | 17 / 164 |
| H16 / Fireball | 108109 | 1.90% [1.79, 2.00] | 0.1196 [0.10, 0.14] | 172 / 2049 |
| W / Xbow | 16353 | 9.85% [9.04, 10.68] | 0.7624 [0.71, 0.82] | 462 / 1501 |
| W / Giant | 19177 | 10.63% [9.79, 11.44] | 0.2477 [0.22, 0.28] | 157 / 2019 |
| W / Rocket | 22077 | 12.91% [11.71, 14.34] | 0.1473 [0.12, 0.18] | 100 / 2851 |
| W / Fireball | 40443 | 31.93% [30.93, 32.93] | 0.2898 [0.26, 0.32] | 364 / 12912 |
| EW / Xbow | 18255 | 10.01% [9.08, 10.89] | 0.6196 [0.57, 0.67] | 392 / 1710 |
| EW / Giant | 19753 | 10.16% [9.34, 10.99] | 0.2340 [0.20, 0.27] | 151 / 1992 |
| EW / Rocket | 22149 | 10.91% [9.77, 12.17] | 0.1410 [0.11, 0.17] | 92 / 2417 |
| EW / Fireball | 41770 | 31.64% [30.61, 32.67] | 0.2932 [0.26, 0.33] | 384 / 13214 |

Candidate attrition counts remain available, including masked, generator absent, reduction absent and final absent. Affordability is measured at search decision opportunities, not every telemetry frame; long WAIT choices reduce the number of opportunities. Consequently this metric is treatment-dependent and must be read alongside arrival metrics and accepted play rates.

## Decision latency

| Arm | Active-wall p50 / p95 / p99, ms | Raw-wall decisions >200 ms | CPU p50 / p95, ms | Raw-wall p95, ms |
|---|---:|---:|---:|---:|
| 0 | 7.7 / 522.4 / 764.2 | 24.00% | 7.6 / 511.6 | 523.9 |
| E | 7.8 / 546.5 / 791.1 | 23.62% | 7.7 / 543.3 | 547.3 |
| H12 | 7.9 / 735.6 / 1064.5 | 25.16% | 7.8 / 717.6 | 738.8 |
| H16 | 7.8 / 918.5 / 1343.5 | 25.48% | 7.6 / 891.4 | 923.1 |
| W | 330.2 / 766.2 / 1049.9 | 70.70% | 325.3 / 758.6 | 768.6 |
| EW | 333.2 / 772.8 / 1039.5 | 69.72% | 328.4 / 764.6 | 775.7 |

| Horizon arm | Paired mean CPU latency change vs 0, ms (95% CI) | Paired mean active-wall change, ms (95% CI) | Paired mean raw-wall change, ms (95% CI) |
|---|---:|---:|---:|
| H12 | +35.95 [32.85, 38.87] | +37.87 [34.81, 40.86] | +44.03 [30.06, 57.84] |
| H16 | +70.20 [66.36, 74.13] | +73.94 [69.74, 78.13] | +84.92 [71.74, 98.50] |

These timings come from loaded, idle-scheduled compute lanes. CPU timings help separate compute from descheduling, but hardware, SMT contention and GPU co-location differ across hosts. This is fixed-work search research, not approval to deploy a live player.

## Seed exclusion and fair-information boundary

Reporting uses `2**48 + 70_000 + i`, **i=10..1009**. Offsets 0..4 were in the prior A/B pause-parity registration, and offsets 5/6 would collide through helper seeds; offsets 7..9 are conservatively skipped. Tuning is `2**48 + 80_000 + i`; combination selection is `2**48 + 85_000 + i`, i=0..149. Smoke uses `+87_000`, two seeds. All game/shuffle/player seeds with helper offsets 0,100000,100001,100002 were checked against gate seed-only audit lists, historical exclusions, the loss-review ledger and every prior search A/B set. [Seed audit](seed-audit.json) includes source hashes and zero intersections.

The player receives public observations, own HUD, accepted enemy events and independent sampled hidden-state beliefs. No live opponent hand, cycle or live RNG enters its search. Telemetry is reduced outside the player boundary. Perception coexistence instrumentation counts completion-journal records only; it does not decode predictions, labels or outcomes. No gate outcomes or evaluation payloads are used.

For exact-harness comparability, opponent scripts retain immediate execution and immediate rollout answers. The command-delay review identifies this asymmetry as a realism limitation; these results do not resolve it. No command-delay/queued-command fix is mixed into these arms.

## Compute and validation

Shard payloads, short remote helpers, rsync servers and worker subprocesses start with `nice -n 10 chrt --idle 0`; forked workers inherit the settings. This explicit exec policy was applied at ~02:25Z after the coordinator detected a transient nice-0 process. Already-compliant shards were left running. First-interpreter-instruction, nested exec, fork-worker and fleet policy checks passed, with receipts under `receipts/`. HW was also corrected to exclude E, and its separate tuning games were rerun; the zero-loss EW winner was unchanged by this correction.

The simulation uses the existing A/B shard runner and improved throughput guard: SCHED_IDLE, core pinning, periodic exclusion of observed GPU/feeder cores and SMT siblings, and pauses only when the co-located GPU job’s measured interval rate falls below 95% of its separately measured baseline. GPU utilization does not control pausing. Captures use counts of the GPU job’s own completed-frame journals; 16 uses T11’s existing own interval-row throughput. Initial capture baselines were measured with this task’s simulations absent. Refreshed baselines retain verified unloaded control intervals and the originals; a failed control check never authorizes a refresh. Unknown/stale metrics and absent jobs are exempt. The whole-worker process declaration includes supervisors for lease admission.

04: ≤40 simultaneous simulation workers. 03: reservation absence checked before launch, ≤96 workers, CPUs 0–47 and 64–111. Leased 09/13/14/15: ≤20 workers each; 16: ≤40. Wrapper v2 r3 handles combined admission and refusal; no cap bypass. New leased shards stop at 04:15Z and runtime termination begins by 04:29Z for exit by 04:30Z. Already-paused leased shards with stalled progress can drain after five minutes and resume their exact uncompleted cases elsewhere; the scheduler retains completed games and retires that lane for the phase. No work on 01/02/08, no git commits, no broad process kills, no tailscale/crontab, no owner-repository access.

Completed unique simulations: **7,808**; completed-game CPU lower bound: **114.84 core-hours**. Initialization, reducers, monitors and unfinished attempts are excluded from this CPU total. The compute audit separately counts the 150 superseded HW instances and their CPU cost. Admission refusals and per-attempt wall time are retained in the compute audit.

| Host | Unique games | Completed CPU, s | Worker-time utilization lower bound | Measured GPU-rate samples / all guard samples |
|---|---:|---:|---:|---:|
| 127x03 | 4209 | 264748.6 | 74.88% | 0 / 1648 |
| 127x04 | 2106 | 81487.4 | 15.10% | 1822 / 1939 |
| 127x09 | 418 | 19319.6 | 43.05% | 1014 / 1049 |
| 127x13 | 435 | 21328.5 | 47.36% | 991 / 1041 |
| 127x14 | 13 | 2133.8 | 6.99% | 589 / 622 |
| 127x15 | 327 | 13844.3 | 43.93% | 692 / 740 |
| 127x16 | 300 | 10549.4 | 41.78% | 333 / 410 |

The utilization lower bound divides completed unique game CPU by declared workers × attempt wall time, including startup and guard pauses. It is not measured hardware occupancy. Unknown/stale GPU rates are explicitly exempt; a lane with missing rate samples does not establish validated throughput protection. The per-host guard counts deduplicate resumed histories.

All leased wrapped jobs and this task’s leased monitors were verified exited by ~02:45Z, with no remaining own leased runtime or monitor processes. The final home shard completed normally on04 at ~02:51Z. Its requested SIGINT migration did not terminate the runtime; no forced tree cleanup or migration occurred. Future runners explicitly install SIGINT/SIGTERM cleanup handlers.

The first full 600 s on 03 completed 748 games (1.247 games/s). The runner reuses warmed external bytecode, assigns horizon-aware LPT case costs, and uses 50-seed reporting shards to amortize resource initialization. Throughput interruptions and unloaded refresh controls are retained in the receipts.

[Tests](receipts/tests.txt), [default/disabled-tempo action parity](receipts/parity.json), [runtime hashes](receipts/runtime-pin.json), [compute audit](compute-audit.json), [first-ten-minute throughput](receipts/first10-throughput.json), and scheduler/wrapper receipts under `receipts/`. Full per-game reductions remain on 04 and shard copies on their original hosts. Compact results and receipts are copied to 05.

## What to try next

1. Split W into timed waits without the prior and the calibrated prior without extra durations, on new exploration seeds. The current W arm bundles both, so its result does not identify which component helps. Inspect WAIT root scores and the behavior at submission and execution.
2. If E is null or worse, test persistent banked-option value across the rollout rather than only at a leaf whose scripted follow-up policy spends immediately. Repeat the most promising intervention with delay matched on both sides, keeping that comparison separate from this exact-harness screen.
3. Establish a wall-deadline implementation that retains play/WAIT coverage before any live test. Longer horizons increase fixed-work cost; CPU budgets do not enforce the 200 ms wall requirement.

Behavioral resemblance to humans is a diagnostic, not a reward target or causal proof of improved play. Null results are reported as nulls; tuning improvements are not assumed to transport to fresh seeds.
