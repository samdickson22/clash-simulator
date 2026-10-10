# K2 two-thread anytime W

Completed 2026-10-10T06:59:43Z. **K2 misses the 80% target at the point estimate; the paired 95% interval leaves the target uncertain.**

**Retention: 70.86 [58.10, 83.33]%.** Numerator (K0−K2) 20.67 pp; paired reference denominator (K0−K4) 29.17 pp. Historical K4/K0 losses 19.3%/46.5% provide context only; this study uses its own paired K4 anchor.

Exploration only: 1,800 terminal games, 600 fresh paired seeds across K2-200/K0-200/K4-200, sealed v1 opponent, symmetric d=27/capacity1, five decks/25 matchups/alternating seat. No Mac, live or heldout access.

| Arm | W/L/D | Loss %, 95% CI | Loss change vs K0, pp, 95% CI | Cutoff %, 95% CI | Latency p50/p95/p99/max, ms |
|---|---:|---:|---:|---:|---:|
| K2-200 | 450/150/0 | 25.00 [21.50, 28.50] | -20.67 [-25.83, -15.83] | 22.89 [21.20, 24.51] | 155.5/192.8/193.0/217.6 |
| K0-200 | 326/274/0 | 45.67 [41.67, 49.67] | 0.00 [0.00, 0.00] | 23.58 [22.96, 24.20] | 13.1/192.5/192.6/212.2 |
| K4-200 | 501/99/0 | 16.50 [13.67, 19.50] | -29.17 [-33.67, -24.83] | 3.67 [3.19, 4.19] | 114.3/181.1/192.8/217.2 |

K2−K4 loss difference: 8.50 [4.67, 12.33] pp. Paired 80%-target contrast: -2.67 [-6.33, 0.97] pp; positive favors retaining ≥80%.

| Arm | Decisions | >200 ms count / % | Positive overrun p50/p95/p99/max, ms | Extra-delay tick counts | Cut returns >208 ms | CPU hours |
|---|---:|---:|---:|---|---:|---:|
| K2-200 | 73406 | 94 / 0.128% | 5.145/14.093/15.686/17.607 | {"1": 94} | 27 | 8.19 |
| K0-200 | 171717 | 22 / 0.013% | 2.939/8.056/11.327/12.193 | {"1": 22} | 2 | 6.29 |
| K4-200 | 70508 | 87 / 0.123% | 4.471/12.887/14.248/17.191 | {"1": 87} | 20 | 8.20 |

All positive wall overruns are retained and charged as ceil(overrun×20) extra ticks to command due time, own availability and timed waits. Timer includes public observation, v1 fallback, belief, candidates, public root, scoring and submission; scoring cutoff192 ms reserves8 ms. Partial/late roots never count; the frozen collector returns without draining. Latencies cover own decision calls; intermediate policy/maintenance polls are excluded.

| Arm | GC count (generation counts) | GC p50/p95/p99/max, ms | GC >50/250/500 ms counts | GC ms per game minute | During decision |
|---|---:|---:|---:|---:|---:|
| K2-200 | 17167 ({"0": 15617, "1": 1427, "2": 123}) | 0.385/3.453/8.594/150.555 | 123/0/0 | 14.77 | 0 |
| K0-200 | 17015 ({"0": 15515, "1": 1406, "2": 94}) | 0.256/3.089/7.160/144.213 | 94/0/0 | 11.69 | 0 |
| K4-200 | 16074 ({"0": 14632, "1": 1332, "2": 110}) | 0.288/3.184/7.620/154.623 | 110/0/0 | 12.73 | 0 |

GC rates use terminal simulated game minutes (terminal ticks / 1,200), not wall-clock minutes. The recorded scope covers game setup through the post-extraction snapshot; file writing and inter-game gaps are excluded. GC maintenance is in whole-game wall/CPU, but does not advance simulated ticks or incur decision lateness. Frozen instrumentation lacks pause timestamps and opportunity/channel traces: **live poll overlap and the resulting loss penalty are unknown**. Zero collections inside a decision does not establish zero delayed live polls. A deployment still needs loaded Mac full-pipeline timing, timestamped maintenance/poll gaps, warmup GC freeze/threshold experiments with retained-memory/equality checks, and three available cores for K2 (two search workers plus main). No Mac-core sufficiency or distillation retirement follows automatically.

Statistics: 5,000 shared paired-seed percentile bootstrap resamples, RNG2026101003; unadjusted pointwise95% CIs. Loss means opponent wins; draws remain separate. Retention=(K0−K2)/(K0−K4); 5,000 valid replicas, 0 nonpositive-denominator replicas omitted from ratio CI. Cutoff/overrun-rate intervals resample per-game numerator/denominator totals. Each matchup/seat has12 paired seeds.

Qualification: 1/2/4 threads each exact screen8 actions/candidates/scores125/125; one/two/four equality125/125; zero-budget root immutability125/125. 125 public histories match frozen belief arrays/ledger/samples/RNG with deadline ON/OFF. Injected-clock, two/four-thread no-drain/reuse/late-score, lateness and GC tests pass; see [test receipt](receipts/tests.txt). Excluded24-game smoke is terminal/audited.

Source: K-v2 freezes e546e181/75e2513d/dd692ef9; K2 freeze 3cf8919e. Scorer only widens accepted thread counts. Native SHA44874fd6, immutable sealed checkpoint/v1 adapter and combat source retained. Reporting seeds4503602307370496+[0,600), excluded smoke4503602317370496+[0,8); [seed audit](seed-audit.json) proves disjointness from K/K-v2/X/G/R3 and noise-ceiling reservations including helper offsets. [Plan](plan.json), [qualification](receipts/qualification.json), [raw-result hashes/statistics](results.json), [GC supplement](gc-maintenance.json), [source/process exit audit](receipts/execution.json), [runtime pin](receipts/runtime-pin.json), [progress/release](PROGRESS-K2.md).

Fleet:03 only,nice10/SCHED_OTHER,11 nonoverlapping five-core slots0–54 (8 if console user), narrowed per game to K2=3,K0=1,K4=5 physical cores; supervisor59. Qualification alone on60. No timing on60–63/SMT, no cache/controller changes, G STOP-03 retained. Minimum observed available memory 117.93 GiB; all owned reporting PGIDs[2300919, 2300943] fully exited, no pauses/source mismatches. Raw games/logs remain03:/mpac/sdicks02/jobs/clasher/k2-20261010-r1/reporting. Final CPU release is recorded separately after all qualification, smoke, reporting and auxiliary processes exit.

**Strict return bound is not qualified:** K2/K4/K0 have 27/20/2 cutoff returns above 208 ms (deadline plus 8 ms reserve). All 203 positive overruns are retained and charged; no outcomes were rerun or used to tune the study.

Operational disclosure: former external cache PID1655741 was already absent at K-v2’s final census, before K2 timing admission. Exit time and reason are unknown; K2 sent no cache signals and changed no cache affinity. The external host census preserves topology, ownership and scheduler checks but explicitly leaves cache persistence unqualified. The initial nice19 smoke prelaunch failed before any pool or game; its identity and logs remain preserved. The corrected external driver leaves all scorer, game, plan and pinned runtime bytes unchanged. See [operational correction](OPERATIONAL-NOTE.md), [final host census](receipts/host-audit-final.json) and [R3 frozen-seed provenance supplement](receipts/R3-freeze-provenance.json).

03 CPU reservation released at 2026-10-10T07:00:38Z; every recorded owned PGID and both operational helpers exited. [Atomic CPU release](receipts/K2-CPU-RELEASE.json), [independent final vacancy check](receipts/final-vacate.json), [report validation](receipts/report-validation.json). G STOP-03 retained; continuation disabled. R3 performs its own admission audit before replay/Stage2.
