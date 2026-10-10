# K-v2 honest-latency deadline sweep

Completed 2026-10-10T05:05:12Z. **2,400 terminal reporting games;600 fresh paired seeds per arm**, sealed v1 opponent, symmetric d=27/capacity1. Five decks/25 matchups/both seats;12 seeds per cell. Draws are separate; loss means v1 wins. No Mac/live/heldout access.

V200 improves loss by 29.50pp versus K0-200; V160 still clears the−10pp paired confidence gate. V120 loses 82.33% with 81.77% cutoffs, showing a steep cliff between160 and120ms. Minimum tested speed for the performance gate is0.80×; point interpolation0.760× is descriptive.

**The strict return bound is not qualified.** The final smoke passed, but reporting recorded16/15/7 W cut returns beyond deadline+8ms for V200/V160/V120, plus3 for K0-200. The cancellation drain fix therefore does not establish the requested bound on every full-pipeline decision. All late actions are charged; no source changes or reruns followed these outcomes. Mac deployment also remains gated on unmeasured maintenance/poll delays.

| Arm | W/L/D | Loss %,95% CI | Paired loss change vs K0-200,pp,95% CI | Cutoff %,95% CI |
|---|---:|---:|---:|---:|
| V200 | 491/109/0 | 18.17 [15.17, 21.17] | -29.50 [-33.83, -25.00] | 3.52 [3.09, 4.01] |
| V160 | 441/159/0 | 26.50 [23.00, 30.17] | -21.17 [-26.00, -16.17] | 16.94 [15.40, 18.59] |
| V120 | 106/494/0 | 82.33 [79.33, 85.17] | 34.67 [30.00, 39.17] | 81.77 [80.50, 83.02] |
| K0-200 | 314/286/0 | 47.67 [43.67, 51.67] | 0.00 [0.00, 0.00] | 23.22 [22.58, 23.87] |

| Arm | Wall p50/p95/p99/max,ms | Overruns / decisions | Overrun %,95% CI | Positive overrun p50/p95/p99/max,ms | Cut returns > deadline+8ms |
|---|---:|---:|---:|---:|---:|
| V200 | 111.9/178.9/192.8/218.1 | 98/70489 | 0.14 [0.11, 0.17] | 3.3/13.5/17.9/18.1 | 16 |
| V160 | 115.1/152.8/152.9/175.2 | 102/73531 | 0.14 [0.11, 0.16] | 3.7/10.2/13.6/15.2 | 15 |
| V120 | 112.6/112.9/113.0/133.6 | 79/89787 | 0.09 [0.07, 0.11] | 4.6/8.9/11.0/13.6 | 7 |
| K0-200 | 12.9/192.5/192.6/209.7 | 41/173685 | 0.02 [0.02, 0.03] | 2.4/8.5/9.4/9.7 | 3 |

| Arm | Cut decisions | Cut wall p50/p95/p99/max,ms | Cut returns > deadline | Cut returns > deadline+8ms |
|---|---:|---:|---:|---:|
| V200 | 2481 | 192.7/197.9/206.8/218.1 | 98 | 16 |
| V160 | 12459 | 152.7/153.0/158.4/175.2 | 102 | 15 |
| V120 | 73423 | 112.7/112.9/113.0/133.6 | 79 | 7 |
| K0-200 | 40338 | 192.5/192.6/192.8/209.7 | 41 | 3 |

Positive-overrun quantiles condition on wall exceeding that arm’s deadline; zero means none observed. Every positive overrun is recorded in raw decision stats and charged as ceil(overrun×20) ticks. A selected play remains reserved immediately and executes at observation tick+27+late ticks; timed waits and own availability also shift. Opponent cadence stays unchanged. No late action is applied for free.

| Deadline reduction | Loss increase,pp per40ms,95% CI | pp/ms |
|---|---:|---:|
| V200->V160 | 8.33 [4.67, 12.17] | 0.2083 |
| V160->V120 | 55.83 [51.67, 59.83] | 1.3958 |

Least-squares loss-versus-deadline slope across120/160/200ms: **-0.80 [-0.85, -0.75]pp/ms**. Adjacent slopes above expose nonlinearity; a linear fit is descriptive.

**Minimum supported Mac admission requirement from this sweep: 0.80× fleet per-core speed**, using the smallest tested deadline whose upper paired95% loss-change CI≤−10pp. Minimum tested point-estimate ratio: 0.80×. Piecewise point interpolation crosses−10pp at **0.760×**; this is an estimate, not a qualified speed.

The labels0.8× and0.6× are budget equivalence:160/200 and120/200. Keeping the8ms reserve fixed means scoring-budget ratios are152/192=0.792 and112/192=0.583. The sweep changes compute headroom, while preparation/return timing and overrun-to-tick conversion run at actual fleet speed. It is not an underclock experiment. It measures one hypothetical public belief root. Actual Mac/four-root performance remains unknown and must pass loaded E4 qualification; the supported requirement is a lower-bound deployment condition, not a measured Mac guarantee.

**Return-path implementation:** the collector uses a remaining-time-bounded wait, admits only complete pre-cutoff scores, signals cancellation and cancels queued work, and returns without drains. Frozen native44874fd6 checks before each simulation tick. Private roots and immutable worker inputs prevent late mutation of returned scores. No scorer phase/order/horizon/tie/default-policy or combat/native change occurred. The8ms reserve starts from full observation/policy/belief/candidates/root/scoring/submission timing. Residuals beyond deadline+8ms remain visible; the reporting trace does not identify their precise stage or prove an OS cause.

Automatic cyclic GC is deferred during decisions, then restored between decisions/physics steps. Every maintenance pause is metered; whole-game CPU/wall includes its cost. This prevents a non-cancellable Python pause without attributing the unreproduced smoke-r2 residuals to GC. Loaded Mac qualification must measure maintenance and packet gaps as well as decision calls. [GC guard](GC-GUARD.md).

An additional upstream tail appeared in the first excluded smoke:165ms belief preparation inside a191ms decision. The owned exact preparation fix operates in4096-row blocks, suspends private partial histories at cutoff, and commits only complete updates. It resumes before newer events; no preparation work leaves the timer. All arms receive the same fix. No-deadline posterior implementation remains frozen. See [amendment](PREPARATION-AMENDMENT.md).

Qualification: exact screen8 actions/candidates/retained scores125/125 for each1/4 threads; one/four equality125/125; native zero-budget root immutability125/125. Exact posterior/weights/cumulative order/resource ledger/sampling/RNG on125 histories for deadlineON andOFF,125/125 each.25 injected-clock/lateness/preparation/GC tests pass. Final excluded smoke-r3:32 terminal games, timing/metadata/seed audits and the cut-return reserve gate passed. Earlier excluded smoke64 plus ten diagnostic games and a zero-terminal aborted reporting admission are retained and excluded. No outcome-based tuning occurred.

Fleet:127x03 only, nice10/SCHED_OTHER; who checked before launch, with nine independent5-core masks on physical0–44 and supervisor45. No SMT; caches/controller48–63/112–127 untouched. K0-200 preserves frozen single-thread scoring while reserving five physical cores, the other arms use four scorer workers. BLAS/Torch/Rayon1; CUDA disabled; caches under/mpac. G STOP-03 was created, its exit receipt and absent PGID were verified before timing; G was never restarted. Owned setsid-f wrapper records PIDs/PGIDs. Final vacate/release receipt is linked in progress.

Reporting seeds4503601807370496+[0,600); excluded smoke4503601817370496+[0,8). [Original frozen seed audit](receipts/seed-audit-freeze-e546e181.json) and [supplement](seed-audit.json) prove disjoint K/X/G and helper intervals against coordinator plan and freeze records. Plan freezee546e181; initial cancellation implementatione01dffe5; exact preparation amendment75e2513d; GC guard83a7faea; nice10 correction is in [operational note](OPERATIONAL-NOTE.md). Original frozen plan bytes are preserved.

CIs use one shared5000-resample paired-seed bootstrap, seed2026101002, pointwise95% percentile intervals without adjustment. Loss contrasts preserve all four seed pairings; cutoff/overrun CIs resample per-game numerator/denominator totals. Every game passes arm/seed/deck/seat/terminal/outcome/deadline/thread/affinity/priority/lateness checks. Full wall distributions include first calls, and exclude blocked polls, five-tick maintenance and opponent calls.

[Full counts/CIs/tails/file hashes](results.json), [plan](plan.json), [qualification](receipts/qualification-r2.json), [posterior qualification](receipts/belief-qualification.json), [runtime pin](receipts/runtime-pin-r3.json), [progress and release](PROGRESS.md), [Mac E4 requirements](MAC-E4-V2.md), [interface](INTERFACE.md). Raw games/logs remain03:/mpac/sdicks02/jobs/clasher/k-v2-20261010-r1/reporting-r2.

**Live-deployment caveat: deferred GC maintenance.** The sim meters these pauses in whole-game wall/CPU, but does not advance game ticks or charge them as decision lateness. In live play they can delay the next poll; the loss estimates therefore retain an unquantified deployment penalty. The final excluded smoke already observed maintenance pauses up to152ms.

| Arm | Pauses | Pause p50/p95/p99/max,ms | Pauses/game minute | Pause ms/game minute | Inside decision windows | Live opportunity overlap |
|---|---:|---:|---:|---:|---:|---|
| V200 | 15287 | 0.3/3.3/7.9/151.8 | 8.10 | 11.66 | 0 | Unknown |
| V160 | 16410 | 0.4/3.5/8.4/149.1 | 8.59 | 13.75 | 0 | Unknown |
| V120 | 23722 | 1.0/2.4/4.7/150.0 | 13.79 | 21.28 | 0 | Unknown |
| K0-200 | 16886 | 0.3/3.2/8.2/142.3 | 8.63 | 12.47 | 0 | Unknown |

Rates use summed terminal game ticks/1200 as game minutes, rather than simulator wall minutes. Counts cover recorded collections from game setup through the post-extraction snapshot; file writing and inter-game gaps are excluded, and the frozen trace has no finer phase labels. Distributions condition on recorded collections, including short generation0 pauses. No collection occurred inside an own/opponent decision window. **Whether any maintenance pause overlapped a live decision opportunity is unknown**: the trace lacks pause start/end timestamps, scheduled poll deadlines and opportunity/channel state. Zero inside-window collections cannot establish zero delayed polls. [GC counts, generations, distributions, rates and limitations](gc-maintenance.json). Loaded Mac tests must record this overlap explicitly.

A prose bound in the frozen seed audit overstated the conservative DAgger block; numerical checks used10,000,000 seeds and also verified the actual32,768-seed freeze. [Clarification](receipts/seed-audit-prose-clarification.md). Arbitrarily extended future DAgger allocation needs a new audit against these reporting/smoke/helper intervals.

Final execution audit verified1,536 pinned runtime files and77 native-source files with zero mismatches; all2,400 terminal files and407,492 decisions passed metadata/lateness checks. Supervisor exited0 at05:04:16Z; no pauses across973 census samples, minimum117.84GiB available. Reporting supervisor/pool PGIDs1718083/1718091 and G PGID1575208 are absent. [Execution/source/vacate receipt](receipts/execution-final.json), [final host census](receipts/host-audit-final.json). The original final host audit failed its persistent-cache-PID assertion because former cache PID1655741 was absent; start/warm audits passed. K-v2 issued no cache/controller signals or affinity changes; that external exit’s time/reason is unknown. The replacement read-only final census records this absence explicitly and establishes owned process vacancy.
