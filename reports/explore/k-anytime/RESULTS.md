# K anytime W search

Completed 2026-10-10T01:30:45Z. Frozen exploration; **3,000 terminal games, 600 fresh paired seeds per arm**, v1 policy opponent, symmetric d=27/capacity1, five decks/25 matchups, alternating seats. Draws remain separate; loss means opponent wins. No heldout, live or Mac access.

| Arm | W/L/D | Loss %, 95% CI | Loss change vs K0, pp, 95% CI | Retention %, 95% CI | v1 fallback %, 95% CI | Wall p50/p95/p99, ms |
|---|---:|---:|---:|---:|---:|---:|
| K0 | 321/279/0 | 46.50 [42.50, 50.33] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.16 [0.14, 0.19] | 16.9/192.7/192.8 |
| K1 | 21/579/0 | 96.50 [95.00, 97.83] | 50.00 [46.00, 54.00] | -184.05 [-234.78, -149.17] | 0.85 [0.82, 0.88] | 192.4/192.7/193.2 |
| K4 | 484/116/0 | 19.33 [16.17, 22.67] | -27.17 [-31.67, -22.50] | 100.00 [86.45, 115.00] | 0.75 [0.73, 0.78] | 114.6/187.9/193.3 |
| K4h | 484/116/0 | 19.33 [16.33, 22.50] | -27.17 [-31.67, -22.83] | 100.00 [85.35, 117.29] | 0.72 [0.69, 0.75] | 115.7/183.3/193.1 |
| KU | 484/116/0 | 19.33 [16.17, 22.50] | -27.17 [-31.50, -22.67] | 100.00 [100.00, 100.00] | 0.00 [0.00, 0.00] | 241.5/444.8/591.8 |

**K1 fails under the one-core budget:** cutoffs hit 96.49% of decisions. In 85.80% (83,698/97,547), legal plays existed but no complete play score was eligible at cutoff; only complete waits remained. The comparable fractions are 1.78% for K4 and 1.00% for K4h. This is an admission diagnostic, not a causal comparison across identical states. [Post-study counts](receipts/choice-diagnostics.json). Completing waits first alone does not make the one-core scan fast enough.

**Decision rules:** advance **K4, K4h** (upper 95% CI of arm−K0 loss change≤ −10 pp). **Kill anytime W: NO**, because K4’s loss-change CI excludes 0. Rules are exactly the frozen plan; neither statistical significance alone nor retention substitutes for the −10 pp threshold.

K4/K4h/KU have equal aggregate W/L/D totals, with different paired outcomes; the retention intervals reflect that uncertainty.

Retention=(K0 loss−arm loss)/(K0 loss−KU loss); its CI uses the same paired seed resamples. KU is the unlimited screen8 ceiling. K0 is one-core deadline baseline. K1 completes WAIT/WAIT10 (one rollout set), then timed waits, then scans every play and refines top 8. K4 uses the identical scorer with four GIL-release threads/private clones; each game pins five physical cores. K4h ranks with an 80-tick coarse scan, then recomputes all three styles at 160 for retained plays. K1/K4 reuse the 160-tick balanced score in refinement. Final reduction retains original candidate order and the frozen 1e-9 tie threshold.

**Complete-score admission:** every eligible candidate has all three 160-tick style scores finished before the 192 ms scoring cutoff. Partial/late roots never count. The 200 ms timer starts before public observation, v1 fallback sampling, belief, candidates and reconstruction; 8 ms is reserved for reduction/submission. KU has no deadline. The table includes full own decision calls, including first calls; opponent and intermediate five-tick maintenance are excluded. Native cancellation checks each tick; observed wall overruns expose OS/return residuals.

| Arm | Cutoff %, 95% CI | Wall >200ms % | Own decisions | Game CPU hours |
|---|---:|---:|---:|---:|
| K0 | 25.85 [25.22, 26.50] | 0.29 | 172860 | 7.55 |
| K1 | 96.49 [96.03, 96.91] | 0.77 | 97547 | 8.56 |
| K4 | 4.54 [3.99, 5.15] | 0.48 | 70224 | 8.51 |
| K4h | 3.95 [3.52, 4.40] | 0.45 | 73146 | 8.81 |
| KU | 0.00 [0.00, 0.00] | 64.17 | 69081 | 9.20 |

Qualification before games: K1/K4 exact frozen screen8 actions and retained scores 125/125 each; one/four-thread vectors identical 125/125; native zero-budget roots immutable 125/125; 12 injected-clock tests passed. K4h agreement **114/125 (91.2%)** is descriptive, not a gate. Source and v1 adapter pins match E1; only generic GIL-release build feature was enabled. No v3 or combat transition.

Seeds: 4503601407370496+[0,600); excluded smoke 4503601417370496+[0,8), 40 terminal games. Freeze **0f2a9ec8**; implementation **8237f993**. [Plan](plan.json), [seed audit](seed-audit.json), [qualification](receipts/qualification.json), [runtime03](receipts/runtime-pin-03.json), [runtime01](receipts/runtime-pin-01.json), [counts/CIs/audits](results.json), [progress](PROGRESS-K.md), [X interface](INTERFACE.md).

Bootstrap: 5,000 shared resamples of paired seed, pointwise 95% percentile intervals, unadjusted. Pairing covers shuffled decks and seat; every seed runs all five arms on the same host. Each matchup/seat has 12 seeds. 600 reporting games per arm are retained. Fallback/cutoff CIs resample per-game numerator/denominator totals; KU’s zero fallback denominator is its own decision calls.

Fleet: 03 physical CPUs 0–59 and 01 physical CPUs 0–39, no SMT siblings, nice 10/SCHED_IDLE, BLAS/Torch/Rayon 1, CUDA disabled, caches under /mpac. 03 perception cache services stayed up; X4 parent/loader CPUs and siblings were excluded. Minimum observed MemAvailable **103.05 GiB**. Jobs use owned setsid-f detach wrapper with closed stdin and durable PID/PGID records. Raw games/logs remain under /mpac on 03/01. No simulations ran on 04, 08, leased hosts or 05.

These are exploration results under fleet load, not Mac or live deadline qualification.

The advancing-arm [Mac E4 v2 note](MAC-E4-V2.md) and [L2-v4 amendment draft](L2-V4-AMENDMENT-DRAFT.md) are prepared. Mac execution remains outside this worker’s scope.

Final execution audit: both hosts completed without restarts or paused census samples; all owned supervisors/pools exited. [03 execution](receipts/execution-03.json), [01 execution](receipts/execution-01.json), and [final 03 cache/process audit](receipts/host-audit-final-03.json). The 03 runtime pin predates a supervisor host-limit syntax fix; the correct prelaunch bytes are independently pinned on 01 and committed in `8237f993` before smoke/reporting. [Explicit correction receipt](receipts/runtime-pin-correction-03.json) retains the original pin and verifies the prelaunch fix. Scorer, game runner, plan, native binary and native source remained unchanged.
