# d27 search A/B exploration — 2026-10-08

**Exploration lane. Research guidance only; no pre-registration or eval/heldout access.**

2,000 paired seeds per arm (8,000 terminal games). Exact S6 ledger harness, five decks, 25 matchups, three scripted opponents, alternating seats and d=27. Reporting seeds `2**48 + 10_000 + i`, i=0..1999. Single reserve weight selected: **1** on 150 separate tuning seeds.

**The exact-harness arms fail the 200 ms decision requirement, including Arm 0.** Results below are fixed-budget simulator research, not approval to deploy. The supplementary anytime check is reported separately.

| Arm | Wins / losses / draws | Loss rate, 95% CI | Paired loss change vs 0 |
|---|---:|---:|---:|
| 0 | 1773 / 227 / 0 | 11.35% [10.00%, 12.75%] | — |
| C | 1773 / 227 / 0 | 11.35% [9.95%, 12.75%] | +0.00 pp [-0.20, +0.20] |
| R | 1733 / 267 / 0 | 13.35% [11.85%, 14.85%] | +2.00 pp [+0.85, +3.15] |
| CR | 1735 / 265 / 0 | 13.25% [11.75%, 14.80%] | +1.90 pp [+0.75, +3.05] |

Measured interpretation: C — loss difference uncertain; pointwise CI includes zero; R — more losses in this simulator sample, with pointwise CI above zero; CR — more losses in this simulator sample, with pointwise CI above zero. These are exploratory, pointwise intervals. The tuning advantage is not assumed to generalize to reporting seeds.

Arm definitions: 0 = original planner; C = candidate coverage; R = public reserve leaf term; CR = both. One selected reserve weight is held fixed across reporting arms.

Paired percentile bootstrap: 2,000 seed resamples, shared draws across all arms and metrics. Rates pool event/exposure numerators and denominators rather than averaging per-game ratios. All estimates, denominators, paired CIs and the CR−C−R+0 interaction are in `results.json`.

| Metric | 0 | C | R | CR |
|---|---:|---:|---:|---:|
| arrival_under4_fraction | 90.03% | 90.05% | 90.44% | 90.44% |
| no_affordable_defender_in_hand_fraction | 63.54% | 63.54% | 63.59% | 63.46% |
| card_per_deck_minute:Xbow | 0.0880 | 0.0888 | 0.0871 | 0.0880 |
| card_per_deck_minute:Giant | 0.0791 | 0.0790 | 0.0790 | 0.0797 |
| card_per_deck_minute:Fireball | 0.1191 | 0.1174 | 0.1155 | 0.1146 |
| card_per_deck_minute:Rocket | 0.0013 | 0.0007 | 0.0020 | 0.0013 |
| card_per_deck_minute:Log | 2.9706 | 2.9688 | 3.0842 | 3.0800 |
| spell_mix:Arrows | 7.78% | 7.82% | 7.79% | 7.82% |
| spell_mix:Fireball | 1.62% | 1.60% | 1.52% | 1.52% |
| spell_mix:GoblinBarrel | 10.01% | 9.99% | 9.59% | 9.57% |
| spell_mix:Log | 61.32% | 61.35% | 61.80% | 61.82% |
| spell_mix:Rocket | 0.01% | 0.00% | 0.01% | 0.01% |
| spell_mix:RoyalDelivery | 19.26% | 19.23% | 19.28% | 19.26% |

Card rates are accepted plays per minute in games containing that card, including zero-use games. Spell mix is each spell’s share of all accepted spell casts. Defender availability is the existing loss-review generic non-spell, non-win-condition hand proxy. A zero empirical rate and [0,0] bootstrap interval are not population upper bounds or proof of no missed opportunity.

## Where expensive cards die

| Arm / card | Hand opportunities | Unaffordable | Affordable | Fully masked | Generator absent | Reduction absent | Final absent | Selected / offered |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 / Xbow | 119587 | 119292 | 295 | 0 | 0 | 5 | 5 | 127 / 290 |
| 0 / Giant | 112012 | 111398 | 614 | 0 | 0 | 1 | 1 | 110 / 613 |
| 0 / Fireball | 240156 | 235135 | 5021 | 0 | 0 | 1 | 1 | 378 / 5020 |
| 0 / Rocket | 127449 | 127152 | 297 | 0 | 0 | 0 | 0 | 2 / 297 |
| C / Xbow | 119441 | 119146 | 295 | 0 | 0 | 5 | 0 | 128 / 295 |
| C / Giant | 112151 | 111526 | 625 | 0 | 0 | 1 | 0 | 111 / 625 |
| C / Fireball | 240120 | 235122 | 4998 | 0 | 0 | 0 | 0 | 373 / 4998 |
| C / Rocket | 127268 | 126973 | 295 | 0 | 0 | 0 | 0 | 1 / 295 |
| R / Xbow | 121082 | 120772 | 310 | 0 | 0 | 6 | 6 | 129 / 304 |
| R / Giant | 112341 | 111719 | 622 | 0 | 0 | 1 | 1 | 107 / 621 |
| R / Fireball | 243084 | 238412 | 4672 | 0 | 0 | 0 | 0 | 368 / 4672 |
| R / Rocket | 128927 | 128630 | 297 | 0 | 0 | 0 | 0 | 3 / 297 |
| CR / Xbow | 120810 | 120502 | 308 | 0 | 0 | 6 | 0 | 130 / 308 |
| CR / Giant | 112439 | 111805 | 634 | 0 | 0 | 1 | 0 | 108 / 634 |
| CR / Fireball | 242819 | 238159 | 4660 | 0 | 0 | 0 | 0 | 365 / 4660 |
| CR / Rocket | 128832 | 128537 | 295 | 0 | 0 | 0 | 0 | 2 / 295 |

Instrumentation is per decision with no outstanding command. Fully masked is conditional on affordability; generator absence is conditional on legal tiles; reduction absence means present in exhaustive script ranking but absent in the original fixed pool. Coverage repairs only missing legal hand slots by replacing the lowest-prior unprotected extra; WAIT and one existing best-prior representative per covered slot are protected. Original candidate count is preserved. Expensive-card opportunities after the affordability gate are small; zero attrition is not evidence of healthy resource planning.

## Reserve value and tuning

Leaf value adds `−weight * 0.005 * max(0, defender_target − own_leaf_elixir)` only when a visible living enemy troop is at canonical y≤18. The defender target is the cheapest generic defender affordable in the root public own hand; if none is affordable, use the cheapest defender in that hand as a savings target. This fixed reference avoids the tautology of requiring a leaf-affordable card and then testing a deficit. It uses native `public_view`: visible bodies and own elixir only. No opponent hand, deck order, live RNG, snapshots or privileged hidden clocks enter this term. Terminal ±2 values are preserved. One weight is shared by R and CR. The inherited loss-review card catalog lacks the internal BlowdartGoblin alias in this schedule; it is excluded from the generic defender/card diagnostic proxy. Candidate coverage itself operates on every legal hand slot, independently of catalog identity. The public/native alias smoke shows BlowdartGoblin remains affordable, has 222 legal tiles and is represented under C; the catalog limitation affects reserve/diagnostic classification, not candidate coverage.

Tuning seeds: `2**48 + 30_000 + i`, i=0..149. Grid: 0, 1, 4, 16, 64. Select minimum tuning losses, breaking ties toward lower weight. No reporting games were read before selection.

| Weight | Tuning losses / 150 |
|---:|---:|
| 0 | 23 |
| 1 | 18 |
| 4 | 26 |
| 16 | 29 |
| 64 | 26 |

## Decision latency

| Arm | Wall median / p95 / p99 / max (ms) | >200 ms | CPU p95 (ms) |
|---|---:|---:|---:|
| 0 | 3.8 / 411.1 / 674.3 / 83328.6 | 133179 / 598173 (22.26%) | 404.9 |
| C | 3.8 / 407.4 / 669.8 / 83712.0 | 133059 / 597800 (22.26%) | 401.6 |
| R | 3.8 / 416.0 / 680.3 / 84973.7 | 133957 / 602272 (22.24%) | 409.5 |
| CR | 3.8 / 414.8 / 679.6 / 83853.6 | 133866 / 601828 (22.24%) | 408.5 |

All arms include the same candidate attrition instrumentation, which adds an exhaustive prior ranking pass; absolute times include this diagnostic cost. Primary latency starts at candidate generation/instrumentation and includes public root reconstruction, scoring and submission; public observation and belief update precede this boundary, so it is a lower bound on full decision latency. CPU timing distinguishes compute cost from scheduling. Command execution delay remains 27 ticks. The ledger uses fixed work rather than a deadline and reproduces its behavior; these results cannot satisfy a hard 200 ms wall budget.

## Supplementary budget check

Separate 100 paired fresh seeds per arm at `2**48 + 50_000 + i`. Same selected weight, decks and matchup schedule; an opt-in 180 ms search cutoff starts before public observation, belief update, candidate generation and root construction, with another 8 ms return cushion. Cancellation occurs between native calls and 10-tick rollout chunks. Only completed three-style candidate scores count; no completed score means WAIT. This changes the baseline planner and is not the exact ledger Arm 0.

| Arm | Wins / losses / draws | Paired loss change vs budgeted 0 | Wall p95 / max (ms) | >200 ms |
|---|---:|---:|---:|---:|
| 0 | 91 / 9 / 0 | — | 172.7 / 279.1 | 13 / 30090 |
| C | 89 / 11 / 0 | +2.00 pp [+0.00, +5.00] | 172.7 / 289.6 | 12 / 30249 |
| R | 88 / 12 / 0 | +3.00 pp [-2.00, +9.00] | 172.7 / 283.0 | 12 / 30844 |
| CR | 89 / 11 / 0 | +2.00 pp [-3.00, +8.00] | 172.7 / 277.7 | 14 / 30776 |

The full-boundary check records 51 overruns in 121,959 decisions, mostly at early public conditioning calls. A separate train-prior-only profile conditions 4,914,000 posterior states down to 1,498,560 on one public Log event: update plus sampling took about 415 ms. The earlier BarbLog profile took about 160 ms and is also retained. This identifies a preparation cost the rollout cutoff cannot interrupt. Profile code and receipt are retained; no prior-conditioning rewrite was introduced during reporting.

Any measured >200 ms event means this cooperative cutoff does not provide a hard real-time guarantee. Truncation, completed-candidate and fallback counts are retained in JSON. Budget sensitivity is exploratory and selected without reporting-seed tuning.

## Reproduction, seeds, tests and compute

The unmodified S6 reproduction matches within float32 reduction tolerance all 36,856 common metric numerator/denominator pairs in all 150 ledger d27 games, plus every game loss. Aggregate losses 22/150; under-4 91.03%; no affordable defender 65.34%; X-Bow 0.123608, Giant 0.056545, Fireball 0.112252, Rocket 0, Log 3.000536 per deck-minute.

Seed audit checks game/shuffle and all player-helper seed offsets 0, 100000, 100001, 100002 against the ledger’s read-only 4,356 gate/helper seed inventory and 19,294 historical values. Reporting, tuning, budget-check, public/native smoke and ledger sets have zero intersections. No gate outcomes, eval data or frozen registrations were opened. `seed-audit.json` includes exclusion hashes and exact ranges.

33 A/B, guard and loss-review unit tests passed, including loss-review reduction/bootstrap tests and new coverage, public reserve, parity, cutoff and resume tests. Final tests and native parity receipts are retained under `receipts/`. Default behavior is unchanged: experiment flags are required; no live-player files were modified. No git commits.

| Run / host | Workers | Fresh / reused games | Wall seconds | Fresh games/s | Fresh worker CPU seconds | Reserved CPUs |
|---|---:|---:|---:|---:|---:|---:|
| primary / 127x08 | 16 | 0 / 500 | 177.4 | 0.000 | 0.0 | 112 |
| primary / 127x04 | 40 | 356 / 144 | 364.1 | 0.978 | 12297.6 | 88 |
| primary / 127x09 | 18 | 39 / 461 | 179.7 | 0.217 | 1605.9 | 110 |
| primary / 127x04 | 40 | 429 / 71 | 405.1 | 1.059 | 14433.2 | 88 |
| primary / 127x09 | 18 | 11 / 489 | 180.7 | 0.061 | 365.5 | 110 |
| primary / 127x04 | 40 | 450 / 50 | 463.6 | 0.971 | 16139.1 | 88 |
| primary / 127x15 | 36 | 500 / 0 | 578.7 | 0.864 | 18485.7 | 92 |
| primary / 127x13 | 36 | 500 / 0 | 628.4 | 0.796 | 19256.0 | 92 |
| primary / 127x04 | 40 | 335 / 165 | 356.3 | 0.940 | 11866.4 | 88 |
| primary / 127x15 | 36 | 500 / 0 | 509.1 | 0.982 | 16845.1 | 92 |
| primary / 127x15 | 36 | 148 / 352 | 219.3 | 0.675 | 5795.2 | 92 |
| primary / 127x13 | 36 | 500 / 0 | 615.3 | 0.813 | 19370.1 | 92 |
| primary / 127x15 | 36 | 500 / 0 | 599.3 | 0.834 | 19379.1 | 92 |
| primary / 127x04 | 40 | 500 / 0 | 494.9 | 1.010 | 17546.8 | 88 |
| primary / 127x04 | 40 | 500 / 0 | 479.8 | 1.042 | 17083.3 | 88 |
| primary / 127x04 | 40 | 500 / 0 | 483.0 | 1.035 | 17378.3 | 88 |
| budget / 127x04 | 32 | 400 / 0 | 356.2 | 1.123 | 10219.7 | 96 |

Simulations ran detached through fleet_run.sh on authorized home hosts or lease wrapper v2, with nice ≥10. Initial 96/96/80-worker tuning allocations were reduced following coordinator corrections. The early 96-worker 04 batch tripped perception’s process guard; it was stopped and completed games retained. Final primary shards used 04≤40, 08≤16, and leased09/14≤18. 01 and 03 remained off after their reservations; no simulator started on03 because the handoff file existed before launch. 11 became unreachable and its incomplete shard was replayed elsewhere. 13/15 drained and were vacated. 16 admission refusals on PSS were honored. Leased staging used rsync -c from04 into isolated lease-local paths. No work on02, roader paths, tailscale or crontab; no pkill. 05 only authored code and read compact artifacts. First baseline throughput was 0.98 games/s on96 workers; first-ten-minute measurements and subsequent affinity receipts are retained.

The primary dataset was produced with the historical GPU-utilization guard. Its wall-latency arrays include external SIGSTOP time and remain labeled legacy raw wall; they are not retrospectively corrected. Successful-game CPU sums exclude abandoned partial-game compute. A later audit showed the utilization guard caused unnecessary pauses; the separate versioned throughput qualification uses fresh GPU-job interval rows/s, a measured baseline, idle scheduling, observed active GPU-job core/SMT exclusions, pause-aware wall telemetry and CPU-clock decision deadlines. The primary fixed-work behavior was preserved.

All16 primary shards completed, 8,000 terminal games. The old lease worker’s14-minute wall limit caused retries; completed games were retained. The new worker counts only active time toward its840-second shard limit and retains an absolute lease exit deadline. Fixed-work action hashes and winners matched across all4arms with3forced pauses and permuted LPT dispatch. The scheduling replay preserves all8,000 cases and their paired clusters in20balanced100-pair shards. Measured initialize startup was28.90s cold and25.79s after external bytecode warming; source hashes were unchanged. New leased starts stop at04:15Z and all our leased work exits by04:30Z. Full admissions, process/PSS peaks, pauses, retries and original commands are retained.

Primary runtime pins agree on the native binary, train prior, public reconstruction, fixed S6 planner and both treatment implementations. The sole difference among primary pins is optional full-decision timing metadata in simulate.py; its flag was off in primary games. Later pause-clock/throughput changes are staged separately for qualification and their source hashes are recorded independently.

Reproduction flags: `--arms 0 --pairs 150 --seed-base 281474976710656 --delays 27 --reserve-weight 0 --allow-ledger-seeds`. Reporting flags: `--arms 0 C R CR --pairs 125 --pair-offset OFFSET --seed-base $((281474976710656 + 10000 + OFFSET)) --delays 27 --reserve-weight 1 --resume`, with the shared exclusions JSON and an authorized worker cap. Each shard’s complete deck/opponent/seat schedule is retained in schedule.json; receipts retain exact launch commands. Omitting --arms preserves the original simulator/player behavior.

Full per-game reductions, latency arrays, schedules and receipts were collected on 04 under this report directory; leased copies remain in the isolated lease-local runtime. Compact JSON and source hashes accompany this report. Pointwise exploration intervals carry no confirmatory interpretation.

## Throughput guard qualification

On 127x08, 15 minutes without exploration sims followed by 15 minutes with 16 SCHED_IDLE sims, pinned away from observed active GPU-job cores and SMT siblings. Fresh GRU step throughput: 237.66→233.99 rows/s, change -1.55%, 95% moving-block bootstrap ratio CI [0.9794, 0.9898] (25/25 complete steps, boundary-crossing first steps excluded). The measured reduction stays within 5% and the pointwise interval excludes a 5% drop. Guard-paused samples: 0/410; completed qualification games: 350. Fixed-work action SHA256 and winners match in all 4 arms with three forced pauses and permuted LPT dispatch. Legacy primary wall timings remain raw; new full-decision telemetry excludes external pauses, while guarded optional decision deadlines use process CPU time. CPU deadlines do not guarantee a 200 ms wall bound. Short background rsync collections continued in both phases; no delay-fixes simulations or reductions ran on 08.

Details and phase samples are retained in receipts/coexistence-summary.json. This sequential exploration check is research guidance; it does not prove a population guarantee. Legacy primary wall times remain unchanged.
