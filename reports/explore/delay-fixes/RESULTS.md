# Delay fixes: exploration results

Completed **1,250 paired seeds per original arm**, plus matched-cadence controls, 12,500 terminal games. Non-confirmatory, dev-only simulation; no preregistration or frozen-registration edits.

The cadence-matched controls preserve the **+1.84 pp** win-rate point gain from delaying the opponent at our d=27, with 95% CI **[0.00, 3.68] pp**. This interval touches zero, so the exploration does not establish a strictly positive effect. At our d=0, the original +0.56 pp becomes +0.40 pp after cadence matching; both intervals span zero. The original d=27 point effect survives the cadence control; the small d=0 effect remains unresolved.

Our d=27 latency costs **5.76 pp** against the legacy immediate opponent, **5.92 pp [4.24, 7.68]** against the cadence-matched immediate opponent, and **4.48 pp [2.96, 6.08]** against the lagged opponent. Estimated latency-cost inflation is +1.28 pp [-1.12, 3.60] for the original contrast and **+1.44 pp [-0.88, 3.76]** after cadence matching. Both inflation intervals span zero. Delay still costs wins against the lagged opponent; these results do not establish that the historical +7.3 pp or +2.7 pp estimates were inflated.

Two outstanding commands change win rate by **−0.32 pp [-2.00, 1.36]** versus one; capacity four changes it by **−0.80 pp [-2.48, 0.96]**. Neither has a detected win benefit. They reduce 27-tick execution silence by 3.88/3.85 pp, but increase under-4 arrivals by **1.33 pp [0.84, 1.81]** / **1.47 pp [0.97, 1.96]**. Capacity four versus two adds no detected win benefit: −0.48 pp [-1.68, 0.72]. Its observed peak is three pending commands, so this cadence/delay does not exercise four simultaneous commands.

Forward versus current-state imitation has **0.00 pp [-1.36, 1.36]** win change (both 1,154/1,250 wins), with under-4 arrivals **+0.72 pp [0.25, 1.20]**. This is a null win result with a worse reserve metric. Its pooled median decision CPU time rises from 48.69 to 100.19 ms; active-wall p95 rises from 394.90 to 473.32 ms. Current-state imitation versus search alone shows an exploratory +2.08 pp [0.48, 3.68] win difference; this does not support the additional forward projection.

At d=27 and ten-tick physical decision polls, a single pending command mechanically forces at least 30 ticks between submissions/executions. The 100% 27-tick submission/execution silence in those arms is therefore a channel constraint, not independent evidence of strategic hesitation. Capacity two/four reduce blocked polls from 24.79% to 0.26%/0%, while no-new-submission after execution increases by 2.08/2.48 pp and mean inter-play gaps remain about 4.06/4.04 seconds (paired intervals for the gap change span zero). Commands committed before execution and elixir availability explain why these silence definitions differ; they should not be collapsed into one score.

Under-4 arrivals use physical HUD elixir, including funds reserved for commands that have not executed. Timing changes can therefore move this metric mechanically. Capacity comparisons hold d=27 fixed, but the metric remains a reserve diagnostic rather than a causal measure of defensive failure. All arms have high scripted-opponent win rates (88.4–94.7%) and under-4 rates (90.0–99.4%); this ceiling and saturation limit generalization.

Control completion: complete; R0/R27 terminal games {'R0': 1250, 'R27': 1250}; common paired controls 1,250. The target was 1,250 per control arm.

## Outcomes

| Arm | Win rate, 95% CI | Loss rate, 95% CI | Under-4 arrivals, 95% CI |
|---|---:|---:|---:|
| U0 | 94.16% [92.80, 95.44] | 5.84% [4.56, 7.20] | 99.36% [99.23, 99.49] |
| U27 | 88.40% [86.56, 90.16] | 11.60% [9.84, 13.44] | 89.99% [89.55, 90.42] |
| S0 | 94.72% [93.44, 95.92] | 5.28% [4.08, 6.56] | 99.35% [99.21, 99.48] |
| S27 | 90.24% [88.48, 91.84] | 9.76% [8.16, 11.52] | 93.36% [92.95, 93.76] |
| N2 | 89.92% [88.24, 91.52] | 10.08% [8.48, 11.76] | 94.68% [94.31, 95.05] |
| N4 | 89.44% [87.68, 91.12] | 10.56% [8.88, 12.32] | 94.82% [94.44, 95.19] |
| I0 | 92.32% [90.88, 93.84] | 7.68% [6.16, 9.12] | 93.23% [92.83, 93.62] |
| IF | 92.32% [90.80, 93.76] | 7.68% [6.24, 9.20] | 93.95% [93.56, 94.33] |
| R0 | 94.32% [93.04, 95.60] | 5.68% [4.40, 6.96] | 99.34% [99.20, 99.46] |
| R27 | 88.40% [86.56, 90.16] | 11.60% [9.84, 13.44] | 89.99% [89.55, 90.42] |

Draws are retained; win rate is not calculated as 1−loss rate.

| Paired contrast (treatment − control) | Win change, 95% CI | Loss change, 95% CI | Under-4 change, 95% CI |
|---|---:|---:|---:|
| opponent_delay_d0: S0 − U0 | +0.56 pp [-0.88, +2.00] | -0.56 pp [-2.00, +0.88] | -0.01 pp [-0.20, +0.17] |
| opponent_delay_d27: S27 − U27 | +1.84 pp [+0.00, +3.68] | -1.84 pp [-3.68, +0.00] | +3.37 pp [+2.82, +3.93] |
| latency_undelayed: U27 − U0 | -5.76 pp [-7.60, -4.08] | +5.76 pp [+4.08, +7.60] | -9.37 pp [-9.83, -8.92] |
| latency_delayed: S27 − S0 | -4.48 pp [-6.08, -2.96] | +4.48 pp [+2.96, +6.08] | -5.99 pp [-6.41, -5.57] |
| two_outstanding: N2 − S27 | -0.32 pp [-2.00, +1.36] | +0.32 pp [-1.36, +2.00] | +1.33 pp [+0.84, +1.81] |
| four_outstanding: N4 − S27 | -0.80 pp [-2.48, +0.96] | +0.80 pp [-0.96, +2.48] | +1.47 pp [+0.97, +1.96] |
| four_vs_two_outstanding: N4 − N2 | -0.48 pp [-1.68, +0.72] | +0.48 pp [-0.72, +1.68] | +0.14 pp [-0.16, +0.45] |
| forward_imitation: IF − I0 | +0.00 pp [-1.36, +1.36] | +0.00 pp [-1.36, +1.36] | +0.72 pp [+0.25, +1.20] |
| current_imitation_vs_search: I0 − S27 | +2.08 pp [+0.48, +3.68] | -2.08 pp [-3.68, -0.48] | -0.13 pp [-0.63, +0.38] |
| lag_only_d0: S0 − R0 | +0.40 pp [-0.96, +1.76] | -0.40 pp [-1.76, +0.96] | +0.01 pp [-0.17, +0.19] |
| lag_only_d27: S27 − R27 | +1.84 pp [+0.00, +3.68] | -1.84 pp [-3.68, +0.00] | +3.37 pp [+2.82, +3.93] |
| latency_undelayed_matched: R27 − R0 | -5.92 pp [-7.68, -4.24] | +5.92 pp [+4.24, +7.68] | -9.35 pp [-9.81, -8.90] |

| Timing effect | Original vs legacy baseline: win change | Cadence-10 comparison: win change |
|---|---:|---:|
| Opponent protocol, own d=0 | +0.56 pp [-0.88, +2.00] | +0.40 pp [-0.96, +1.76] |
| Opponent protocol, own d=27 | +1.84 pp [+0.00, +3.68] | +1.84 pp [+0.00, +3.68] |
| Own d=27 versus d=0, zero-lag opponent | -5.76 pp [-7.60, -4.08] | -5.92 pp [-7.68, -4.24] |

The left column changes opponent lag plus legacy rollout cadence/path. The right compares the same enabled native path and 10-tick opponent cadence. S0−R0 and S27−R27 isolate decision-to-execution lag. All paired comparisons use the same completed seeds; partial-control comparisons subset the corresponding lagged arm.

The legacy-protocol loss-cost difference-in-differences `(U27−U0)−(S27−S0)` is **+1.28 pp**, 95% CI [-1.12, +3.60]. A positive value means the zero-lag opponent inflated the measured latency cost in this sample.

The matched-cadence loss-cost difference-in-differences `(R27−R0)−(S27−S0)` is **+1.44 pp**, 95% CI [-0.88, +3.76], n=1,250 paired seeds.

The historical ledger +7.3 pp and S6 +2.7 pp use different samples/settings. This factorial contrast remeasures the asymmetry; it does not retroactively correct those estimates.

[Exported paired-effects figure](paired-effects.svg) ([PNG](paired-effects.png)).

## Behavior

| Arm | Submission silence | Execution silence | No submission after execution | Pending-blocked polls |
|---|---:|---:|---:|---:|
| U0 | 87.24% [86.85, 87.63] | 87.24% [86.85, 87.63] | 87.24% [86.85, 87.63] | 0.00% [0.00, 0.00] |
| U27 | 100.00% [100.00, 100.00] | 100.00% [100.00, 100.00] | 58.78% [57.88, 59.71] | 25.11% [24.79, 25.43] |
| S0 | 87.89% [87.53, 88.25] | 87.89% [87.53, 88.25] | 87.89% [87.53, 88.25] | 0.00% [0.00, 0.00] |
| S27 | 100.00% [100.00, 100.00] | 100.00% [100.00, 100.00] | 59.63% [58.74, 60.55] | 24.79% [24.47, 25.11] |
| N2 | 96.14% [96.04, 96.25] | 96.12% [96.02, 96.23] | 61.71% [60.80, 62.66] | 0.26% [0.25, 0.27] |
| N4 | 96.17% [96.06, 96.28] | 96.15% [96.04, 96.25] | 62.12% [61.18, 63.04] | 0.00% [0.00, 0.00] |
| I0 | 100.00% [100.00, 100.00] | 100.00% [100.00, 100.00] | 60.94% [60.07, 61.81] | 24.38% [24.08, 24.70] |
| IF | 100.00% [100.00, 100.00] | 100.00% [100.00, 100.00] | 61.40% [60.55, 62.24] | 24.24% [23.95, 24.54] |
| R0 | 87.26% [86.88, 87.63] | 87.26% [86.88, 87.63] | 87.26% [86.88, 87.63] | 0.00% [0.00, 0.00] |
| R27 | 100.00% [100.00, 100.00] | 100.00% [100.00, 100.00] | 58.78% [57.88, 59.71] | 25.11% [24.79, 25.43] |

Silence uses complete 27-tick windows. Submission silence measures the next commitment; execution silence measures the next accepted server-visible play. The third column asks whether a new command was submitted after execution. Under-4 arrivals use the existing loss-review lane-incursion-onset definition and physical HUD elixir; pending-spend reservations are not subtracted from that behavior metric. All behavior ratios pool event numerators/denominators and retain paired-seed uncertainty.

Additional loss-review metrics and paired differences are in [results.json](results.json), including capped response latency, affordability, low-reserve win-condition plays, active-threat plays, inter-play gaps, rejections and time at max elixir.

## Arms and implementation

- U0/U27: our delay 0/27; opponent delay 0, capacity 1.
- S0/S27: our delay 0/27; opponent decision-to-execution lag 22, cadence 10, capacity 4.
- N2/N4: S27 with our outstanding-command capacity 2/4.
- I0/IF: S27 with released-v1 current-state/forward-state imitation proposals.
- R0/R27: enabled S0/S27 native path, opponent lag 0, cadence 10, capacity 4 (nonbinding at zero lag), our delay 0/27.

Original U arms retain legacy opponent rollout cadence 3; physical opponent cadence is 10 in every arm. Enabled S/N/I/R rollouts use opponent cadence 10 and own continuation cadence 3. Own physical decision polls are every 10 ticks. The two R controls were added on a code-audit finding before outcomes were inspected, with coordinator approval. [Config](lag-controls-config.json), [timestamp and SHA receipt](receipts/lag-controls-addition.json), [progress](PROGRESS.md).

The opponent lag is applied in physical games and native search rollouts. True pending opponent commands live outside BattleState and never enter observation, the accepted-event stream, or the planner root. Rollouts begin without that queue and generate their own hypothetical future commands. This models response lag; it does not shift the observation of a command after execution.

Within the fixed-cost C56 card scope, own reservations retain action, card, cost and execution tick individually. Available elixir subtracts all pending costs; occupied slots remain masked. Roots retain the physical unspent own HUD and execute every known pending command at its due tick through the engine exactly once. Completion releases only its reservation. No premature refill, duplicate slot spend or physical refund is introduced.

Forward proposals project the planner’s own fair hypothetical root at t+27, including known own pending executions and newly simulated opponent commands. D1 advances using only hypothetical public accepted events. A proposal must also pass the current mask with the same card in the same slot. Both imitation arms use the gate-(b) matched-count replacement pattern: top-8 proposals replace random extras while WAIT, script candidates and the exact baseline candidate count remain available.

Flags default off: `symmetric_opponent=False`, `max_outstanding=1`, `forward_prior=False`. Enabled opponent lag/cadence are parameterized as `opponent_delay` / `opponent_interval`. The native method is additive; legacy S6 scoring delegates unchanged when flags are off. The implementation supplies the simulation planner/runtime adapter; the live pixel-verification actuator is not replaced.

## Validation and provenance

- [24 pytest checks passed](receipts/final-tests-r2.log), including equality of every public observation and confidence field with/without pending opponent commands through tick 22, on both seats. The command becomes visible only when it executes.
- [Native preflight passed on both seats](receipts/pending-preflight.json): flags-off score parity, native single-channel parity, two simultaneous pending commands, four commands at ticks 10/20/27/35, exact elixir/card conservation, root immutability, t+27 endpoint execution, matched legal proposal counts and unchanged current D1.
- Eight-arm smoke completed terminal games; full study checks reject duplicate games, forbidden roles, nonterminal games, seed-exclusion collisions and incomplete original pairing. Two reducer checks verify distinct legacy/matched-cadence effects and correct seed-subsetting for partial controls.

Seed namespace: `2**48 + 50000 + i`; 1,250 paired indices. Five train-catalog deck archetypes form 25 matchup cells, seats alternate, and three opponent styles rotate every 25 seeds. Opening decks/shuffle, seat, style and helper seeds match across arms. Own sampled opponent state and rollout RNG remain independent of the physical opponent’s hidden state. Abilities are disabled on both physical sides. The same fixed 160-tick search horizon and candidate budget are used; this is not a general d-sweep and does not duplicate the parallel candidate-coverage/reserve-leaf exploration.

Checkpoint: released main02 v1 EMA, SHA256 `d77005d59d6ed40ce7f9bfcfde569b54958bebf056e00653b10dcee3957272ed`; task copy read-only, CPU fp32, in-memory temperature 1. Frozen gate-(b)/(c) artifacts, seeds and driver files are untouched. No training or raw eval/heldout data enter the sims.

Provenance limitation: while locating checkpoint provenance, the implementation agent inadvertently opened the first 65 lines of the existing `imitation/RESULTS-v1-offline.md`, which includes summarized gate-(a) heldout outcomes. No raw heldout data were opened or loaded, and those summarized outcomes did not inform arm definitions, checkpoint choice or comparisons. This exploration is not outcome-blinded.

Bootstrap: 5,000 shared paired-seed resamples; pooled numerator/denominator ratios; percentile 95% CIs, pointwise and uncorrected. Bootstrap RNG is `2**48 + 59001`. Null estimates and intervals spanning zero are reported as such. Results apply to these train-deck scripted-opponent sims, not human matches or frozen imitation gates.

## Compute and practical limits

| Host | Games | Maximum pool workers | Worker CPU hours | Mean active cores | Pool utilization incl. pauses/startup/tails | GPU p10/p50/p90 |
|---|---:|---:|---:|---:|---:|---|
| 127x08 | 2,310 | 26 | 20.49 | 7.36 | 50.5% | 23%/35%/100% |
| 127x09 | 2,830 | 22 | 28.06 | 9.35 | 58.6% | 75%/88%/91% |
| 127x11 | 0 | 26 | 0.06 | 0.13 | 0.5% | unrecorded |
| 127x13 | 2,410 | 22 | 23.34 | 7.51 | 65.0% | 85%/93%/99% |
| 127x14 | 1,260 | 22 | 36.90 | 10.77 | 68.0% | 77%/94%/98% |
| 127x15 | 2,490 | 22 | 23.98 | 8.53 | 71.9% | 97%/99%/99% |
| 127x16 | 1,200 | 26 | 11.93 | 7.73 | 33.9% | 0%/63%/100% |

Observed worker CPU totals **144.76 hours**, a lower bound including verified technical stops. Home 08 throughput guards recorded zero below-95% samples across 2,584 measured samples; p10/p50/p90 throughput ratios were 0.9899/0.9974/1.0063. Host 16 recorded six below-threshold samples and paused under the new policy; the other leases lack an interval-rate baseline.

Leased work used wrapper v2 on the six allowed hosts, whole-job declarations ≤30, 25-seed shards initially, then five-seed original shards after the cap reductions and 25-seed/two-arm control shards and lease-local paths. Refusals and wrapper failures are preserved. An initial PSS refusal on 16 moved its unstarted primary block to home 08. Detached pre-hotfix supervision failed twice; supported foreground admission then worked, and new launches used the coordinator’s repaired wrapper. No cap bypass or wrapper modification. Host 05 only orchestrated and handled compact text/receipts. Coordinator priority updates then closed 13/15 completely; both drained within ten minutes and received no new launches. The later actual 00:10Z update declared 11 down and authorized its lost block to rerun elsewhere. Current caps became 13/15=10, 09/14=15, 16 ≤30 and home 08=12 after draining. 16 used 16 workers following a declared 12 GB PSS stop (13.09GB peak), then 26 workers with 18 GB declared PSS after the throughput-policy update; its 103 completed games were preserved and only verified orphan workers cleaned up. A technical guard restart and the cap reductions preserved completed games and schedules. An earlier 16 restart was refused for an existing Clasher process below the nice minimum; that refusal was accepted, and later coordinator-authorized admission succeeded.

The final 16 lane also accepted an aggregate-PSS admission refusal and retired; its unstarted seeds were requeued on the remaining hosts. Later nice-minimum admissions refused 09/15; both main lanes retired with no owner process altered. After the coordinator fixed the tempo-horizon exec-nice cause and explicitly authorized conditional re-admission, read-only checks cleared 09/15 for controls. Every leased control admission first checks for any Clasher process below nice 10; failed checks wait without attempting admission. The wrapper retains its own admission checks. The compute total is a lower bound: it includes stopped-attempt CPU, while the down 11 second attempt is unavailable and successful initialization/build/test CPU is excluded. Utilization uses the sum of workers×attempt wall time across changing caps. Early shards used the original utilization guard, which the perf audit found ineffective. Following the coordinator’s 00:46Z authorization, the shared guard samples every two seconds and can pause only for a fresh GPU-job interval throughput more than 5% below an explicitly measured baseline. Idle GPUs and missing/stale metrics are exempt; GPU utilization is receipt-only. New shards use SCHED_IDLE and refresh their affinity away from observed active GPU-job/feeder cores and SMT siblings. The A/B owner measured 30-minute coexistence on 08, while this task kept 08 drained through the qualification. Lease v4 capture logs supplied no interval fps or measured baseline, so those shards rely on idle scheduling/affinity and do not claim validated throughput protection. Continuous GPU utilization ≥80% is not claimed. [compute-audit.json](compute-audit.json) records below-threshold samples, monitor-reported paused worker-seconds, stopped attempts, utilization and completed shards. Brief verified idle-GPU drains on 13/15 can overstate monitor-reported paused time. The coordinator ordered an early lease drain at 03:00Z; all leased launch caps were set to zero at 03:00:44Z. The named 09/p1050 and 14/p0925 reservations finished naturally and were verified absent at 03:04:53Z. The final leased shard exited successfully at 03:06:04Z; registry and process checks at 03:06:50Z confirmed zero own reservations/workers on all five leased hosts ([receipt](receipts/early-leases-clear.json)). Remaining controls ran on home 08 with at most 12 pool workers; new home 03/01 allowances were unnecessary. All controls completed by 03:14:25Z; home 08 sim/reduction work was verified clear at 03:19:49Z ([completion receipt](receipts/completion.json)), before its 04:55Z handover, and the leased 04:30Z hard exit remains binding.

The A/B owner’s sequential 08 coexistence qualification measured 237.66→233.99 fresh interval rows/s with 16 idle sims, a 1.55% slowdown; 5,000 three-step moving-block bootstrap ratio CI [0.9794, 0.9898], 25 fresh steps per phase. This is a small measured loss within 5% tolerance, not zero loss. It recorded 0/410 paused samples and 350 completed qualification games; background rsync traffic occurred in both phases. Qualification receipt: [../search-ab/receipts/coexistence-summary.json](../search-ab/receipts/coexistence-summary.json). The qualification used the A/B native runtime; our isolated native binary differs, so it does not certify our exact binary. Following confirmed treatment drain, this task resumed 08 with 12 workers and a three-step median guard using the measured 237.66 rows/s baseline.

On 16, the own-sim-drained T11 control measured 12,147.40 interval rows/s from 40 fresh steps over 38 seconds; the guard compares 10-step medians against 95% of that baseline. The baseline and its source field are retained in [receipts/throughput-baseline16.json](receipts/throughput-baseline16.json). Measured throughput ratios and guard coverage are retained in compute-audit.json; missing metrics on the other leases are disclosed rather than treated as successful protection.

New-shard decision latency uses an atomic shared active-wall clock that removes completed and ongoing GPU pauses; raw wall and process CPU are retained. Legacy pause-inflated wall times are separated and cannot be retrospectively corrected exactly. Fixed-work outcomes have no wall-clock deadline. The A/B owner handles opt-in CPU-time decision-budget producer/consumer changes in its own simulator/search files. CPU quantiles cover all games, while active-wall quantiles cover only corrected-clock games in results.json. These timings do not establish compliance with a live 200ms deadline or validate multi-command pixel verification.

Full reduced per-game files, schedules and game hashes remain under `reports/explore/delay-fixes/` on home 08; shard copies and the isolated build remain lease-local. Compact results, source hashes, validation and wrapper receipts are retained here. See [README.md](README.md) for methods, [launch.json](launch.json) for initial accounting and [launch-throughput-v5.json](launch-throughput-v5.json) for the original controller and [launch-lag-controls.json](launch-lag-controls.json) for the controls. [source-hashes.json](source-hashes.json) identifies the isolated binary/source snapshot. Prior unstarted offsets are superseded by the final manifest.

## Recommended L2-v4 amendments

1. Prospectively specify symmetric opponent decision-to-execution lag, its cadence and command capacity in both physical simulation and search. Use execution-only opponent visibility, forbid true pending-queue input, and retain the two-seat observation equality test. Include matched zero-lag/cadence controls when estimating latency cost. Treat 22 ticks as the exploration setting to validate against measured opponent response timing; the win evidence here is borderline and latency-cost inflation remains unresolved.
2. Keep outstanding-command capacity one as the default. Retain the tested opt-in queue for a prospective capacity-two comparison with explicit pending-spend/hand-cycle conservation and a reserve-aware policy. Predefine win, under-4 and the separate silence metrics. This exploration does not justify promoting capacity two or four on win rate; four adds no detected benefit and its fourth slot was not exercised. Verify the live pixel-confirmation actuator separately before enabling overlapping commands in live games.
3. Keep forward imitation off. A prospective comparison should hold proposer count, legality, checkpoint, device/dtype and decision budget fixed, and specify whether t+d includes hypothetical opponent responses. Require a win benefit and acceptable reserve/latency tradeoffs before adoption; the present comparison has zero measured win gain, higher under-4 arrivals and extra CPU cost. The current-state imitation point gain is a separate hypothesis to confirm.
4. Register fresh prospective seeds and stopping rules for any confirmatory amendment. Retain paired resampling, draws and pooled behavior denominators; distinguish process CPU, pause-adjusted active wall and raw wall. Use measured job interval throughput for coexistence protection, with idle/missing/stale exemptions and core/SMT exclusions. These sims do not establish a live 200 ms deadline. No frozen L2-v4 registration was edited.
