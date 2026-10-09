# E1 CPU checks — arms 1–4 complete; reserve arm pending

Exploration lane; frozen plan before games, no PREREG. **2,400 terminal games**, 600 matched seeds, five train decks / 25 matchups, alternating seats, symmetric d=27 and capacity one. Shared 5,000 paired-seed bootstrap resamples; pointwise 95% percentile CIs. Draws count half for score and separately from losses.

| Arm | W/L/D | Loss rate, 95% CI |
| --- | ---: | ---: |
| Deadline baseline vs baseline | 311/289/0 | 48.17% [44.17, 52.17] |
| Deadline W vs baseline | 161/439/0 | 73.17% [69.50, 76.67] |
| Baseline vs v1 | 351/249/0 | 41.50% [37.67, 45.34] |
| W vs v1 | 476/124/0 | 20.67% [17.50, 23.83] |

**E1a:** deadline W minus deadline baseline loss change **+25.00 [+20.17, +30.00] pp**. W loses more often under this budget. Its frozen balanced coarse scan must finish before a root can complete all three styles; the high fallback rate shows that this ordering usually supplies no complete root within the budget.
**E1b:** W minus baseline against v1 loss change **-20.83 [-25.17, -16.67] pp**. W win rate against v1 **79.33% [76.17, 82.50]**; score **79.33% [76.17, 82.50]**.

| Deadline arm | Search cutoff hits | v1 fallbacks | Actual wall >200 ms |
| --- | ---: | ---: | ---: |
| Deadline baseline vs baseline | 32.26% [31.37, 33.18] | 0.80% [0.67, 0.95] | 0.44% [0.40, 0.49] |
| Deadline baseline vs baseline, opponent | 31.84% [30.95, 32.74] | 0.80% [0.68, 0.94] | 0.41% [0.39, 0.44] |
| Deadline W vs baseline | 94.41% [93.62, 95.15] | 85.87% [83.94, 87.65] | 0.83% [0.74, 0.94] |
| Deadline W vs baseline, opponent | 33.35% [32.51, 34.20] | 1.17% [0.93, 1.44] | 0.49% [0.45, 0.53] |

| Own deadline arm / seat | Search cutoff hits | v1 fallbacks | Actual wall >200 ms |
| --- | ---: | ---: | ---: |
| a0 / 0 | 31.61% [30.35, 32.83] | 0.83% [0.63, 1.09] | 0.47% [0.40, 0.57] |
| aW / 0 | 94.47% [93.36, 95.52] | 85.95% [83.28, 88.50] | 0.83% [0.71, 0.98] |
| a0 / 1 | 32.92% [31.61, 34.19] | 0.77% [0.61, 0.94] | 0.42% [0.39, 0.45] |
| aW / 1 | 94.35% [93.23, 95.42] | 85.79% [83.03, 88.32] | 0.83% [0.70, 1.01] |

Every deadline decision includes public observation, cached v1 policy sample, belief, candidates, root reconstruction, scoring and submission. Scoring reserves 8 ms for return. Native cancellation checks each physical tick; only complete roots finished before cutoff are eligible. The actual wall-overrun column exposes OS scheduling/return residuals under SCHED_IDLE; these runs are not hard-real-time OS qualification. Partial/late roots never count. Fallback actions use the sealed v1 player at T=1; search runs on one pinned core.

| Arm | Full decision wall p50/p95/p99, ms | CPU p50/p95/p99, ms | Decisions/s/core |
| --- | ---: | ---: | ---: |
| Deadline baseline vs baseline | 27.7/193.1/193.2 | 27.6/192.7/192.9 | 12.511 |
| Deadline W vs baseline | 192.8/193.0/195.6 | 192.4/192.6/193.4 | 5.326 |
| Baseline vs v1 | 26.8/622.2/893.1 | 26.7/617.3/886.9 | 7.290 |
| W vs v1 | 330.7/626.3/857.4 | 329.5/619.1/841.5 | 3.108 |

**Teacher sizing:** unlimited W against v1 measured **3.108 decisions/sec/core**, from summed CPU time for complete own decision calls after each game's first decision. This includes public reconstruction and v1 sampling, and excludes the intermediate five-tick policy maintenance polls and other game work. Including opponent, physics, five-tick policy maintenance and loss-review telemetry, E1 emitted 1.422 own W decision calls/sec/core over total game CPU. Neither rate includes an ExIt emitter/store implementation, and neither is a guaranteed generation throughput.

| Arm | Under-4 arrivals | No affordable defender in hand | Low-minus-high arrival subsequent damage risk |
| --- | ---: | ---: | ---: |
| Deadline baseline vs baseline | 88.30% [87.59, 88.97] | 59.44% [58.11, 60.76] | +2.86 [-0.18, +5.87] pp |
| Deadline W vs baseline | 20.97% [18.56, 23.41] | 11.79% [10.32, 13.27] | -4.92 [-8.06, -1.65] pp |
| Baseline vs v1 | 95.59% [95.01, 96.16] | 69.60% [68.16, 71.06] | +8.40 [+1.92, +14.85] pp |
| W vs v1 | 70.61% [69.13, 72.10] | 35.99% [34.36, 37.64] | +7.64 [+4.56, +10.62] pp |

W-v-v1 under-4 arrivals among losses: **68.64% [65.46, 71.82]**; among nonlosses: **71.15% [69.51, 72.82]**. These loss-stratified ledger comparisons are observational.

| Arm | Candidate plays filtered | Own/opponent command rejections | Own/opponent v1 polls |
| --- | ---: | ---: | ---: |
| a0 | 0 | 1/0 | 503,406/503,406 |
| aW | 0 | 0/1 | 451,894/451,894 |
| b0 | 0 | 0/1 | 457,053/457,053 |
| bW | 0 | 0/2 | 442,193/442,193 |

The reducer verifies exactly one poll per actor at every five-tick cadence point from tick90, including blocked channels and timed waits. Filtering counts candidate occurrences across decisions, not distinct plays.

The fifth arm is frozen and runs last. No causal reserve conclusion is reported before it completes.

Fair inputs: public board, own HUD, accepted public events and independent sampled hidden-model RNG. v1 uses the unmodified sealed gate(c) adapter at five-tick cadence through blocked polls; delayed capacity-one command execution stays outside it. Physical abilities are disabled. All completed games are retained; the separate two-seed smoke is excluded.03 had one technical restart after its broad Python census counted65 against cap64; completed receipts were preserved and only pending scheduled cases retried. The extra process identity was not recorded and remains unresolved. Per-game telemetry and raw logs remain under `/mpac` on compute hosts.

Validation: frozen OFF 250/250 score/action/trace parity; E1 OFF symmetric 125/125; W 125/125 frozen choices/scores; v1 same-state byte/action 250/250; zero-budget native root immutability 125/125; 13 injected-clock/filter tests passed, including the crown-tower correction. Library and sealed adapter hashes are pinned in [runtime receipts](receipts/runtime-pin.json).

Freeze commit **`bfb9b107`**; implementation **`47e97277`**; crown-only reserve correction **`72e84a5f`** (before reporting reserve games). Config SHA256 **`633e21dbc97ad4dda2576c1cdd1bd1d24d4ed563ad5d5c1834765a61d82fd9b4`**. [Counts, CIs, rate denominators and audits](results-arms1-4.json); [execution progress](PROGRESS.md). Child game CPU: **60.39 hours**. E1 ran on03/04 at nice10/SCHED_IDLE, detached setsid, with process/memory supervision; final per-host execution receipts report measured peaks/floors.
