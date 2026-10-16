# Bot ExIt progress (exploration)

Design: [DESIGN.md](DESIGN.md). Code: `bot/exit/` in the `bot/lead` worktree on 05. It is synced to both hosts
with:

```
rsync -a --exclude __pycache__ bot/ 127x0{4,8}:/mpac/sdicks02/repos/clasher-bot/bot/
```

## Hosts, envs, dirs

- **127x08** (owned): job dir `J8=/mpac/sdicks02/jobs/clasher/bot-exit-r1`.
  - CPU env: `/mpac/sdicks02/repos/clasher-bot/.venv`.
  - GPU env: `/mpac/sdicks02/repos/clasher-bot-gpu/venv` (torch 2.7.1+cu118 on driver 470).
  - Runtime: `/mpac/sdicks02/repos/clasher-bot-runtime/r1`, with pins checked.
  - R3a's r1 corpus is read-only at `/mpac/sdicks02/jobs/clasher/exit-r2-20261010-r1/corpus`.
- **127x04** (shared): job dir `J4=/mpac/sdicks02/jobs/clasher/bot-exit-r1-04`.
  - Limits: ≤60 CPU workers, and leave ≥20 GB of GPU free (`BOT_GPU_MAX_GB=20`).
  - Same env layout as 08; its own GPU venv lives at the same path.
  - The r1 corpus was copied to `$J4/r1-corpus` (53 GB).
- **Mirrors** (every 30 min): 08→04 `bot-exit-r1-mirror/`, 04→08 `bot-exit-r1-04-mirror/`.
- **Assets:** `inputs/assets.npz` is 3954af44 (R3a's).

## Seed bank TRAIN1 = 874184153281168

Drawn with os.urandom at 2026-10-14T04:05:19Z. It is disjoint from HEADLINE 1455777415631152, which
`check_bank` enforces.

| index range | use | host |
|---|---|---|
| [0, 1500) | gen-it1: R3a behavior. 1,407 played; 93 unplayed after the STOP | 08 |
| [0, 8) | determinism replay of gen-it1 (`$J4/verify-repro`) | 04 |
| [100000, 100400) | gen-it1x: R3a behavior, extra labels | 04 |
| [200000, 200192) | on-policy recalibration of R3a (cal-r3a) | 08 |
| [300000, 300192) | per-state calibration of A (stopped after 2 rounds; A-state labels kept) | 08 |
| [400000, 402064) | first rate calibrations (case noise; superseded) | 08/04 |
| [410000, 410128) / [411000, …) / [412000, …) | rate calibration of A / B / W (common cases) | 08/04 |
| [500000, 500224) | teacher plays/game and K4SP4 vs K4S paired test | 04/08 |
| [1000000, 1001500) / [1100000, 1101000) | gen-it2, K4SP4-b64 teacher (08 / 04) | 08/04 |
| [2000000, 2001500) / [2100000, 2101500) | gen-it3st, K4S-st teacher (08 / 04) | 08/04 |
| [420000, 420128) / [421000, 421128) | rate calibration of C / D (128 common cases) | 08/04 |
| [422000, …) / [423000, …) / [424000, …) / [425000, …) / [426000, …) | rate calibration of E / F / G / H / I | 08/04 |
| [3000000, 3001500) / [3100000, 3101500) | gen-it3D: behavior D, K4S-st teacher (08 / 04) | 08/04 |
| [3101500, 3103000) | gen-it3D2: behavior D, K4S-st teacher | 04 |
| [4000000, 4001500) / [4100000, 4101500) | gen-it4: behavior D, teacher K4S-st@student:D (08 / 04) | 08/04 |
| [427000, …) J, [428000, …) K, [429000, …) D-rep, [430000, …) it4a, [431000, …) it4mix, [432000, …) Drep2, [433000, …) Drep3; next free [434000, …) | rate calibrations | 04/08 |
| [4001500, 4003000) | gen-it4x: D behavior, K4S-st@student:D teacher, 34 workers | 08 |
| [6000000, 6001500) / [6100000, 6101500) / [6200000, 6201500) | gen-it5: Kall behavior, K4S-st teacher (01 / 08 / 04) | 01/08/04 |
| [4003000, 4004500) / [4103000, 4104500) | gen-it4z (08) / gen-it4y (04), stopped at 13:10Z | 08/04 |
| [5000000, 5001500) | gen-it4s: D behavior, K4S-st teacher, 12 workers (`$J3=/mpac/sdicks02/jobs/clasher/bot-exit-r1-03`, PID 3753047) | 03 |
| [600000, 600002) | K4S-st@student equivalence smoke | 04 |
| [1000000, …) | iteration-2 generation | |

## Done

- **Self-test:** 4/4 passed.
- **gen-it1** (08): 1,407 games, **558,286 root labels**, 0% budget cuts. Packed to `$J8/packed-it1`; a copy is in
  `$J4/packed-it1`.
- **gen-it1x** (04): 400 games, 156,724 labels. Packed to `$J4/packed-it1x`.
- **Determinism:** 8/8 replayed games on 04 have identical command hashes, and the label arrays are byte-identical
  in 10/10 shards. The R3a baseline matches bot-gate-r1 in 300/300 hashes. The unseeded `BattleState.rng` default
  is never used, because `stage2_matches.battle` passes `Random(seed)`.
- **Baseline:** R3a vs v1 = **0.743 [0.693, 0.793]** (`$J8/eval-base`). student10:R3a = 0.750 (ns).
- **Training it1, from R3a:**

  | variant | data | steps / lr | GPU | held-out loss | decision agreement |
  |---|---|---|---|---|---|
  | A | ExIt only | 800 / 1e-4 | 08 | 5.77 → 5.59 | 0.58 → 0.61 |
  | B | ExIt + r1 at 50/50 | 1,200 / 1e-4 | 08 | 5.77 → 5.58 | 0.58 → 0.61 |
  | W | grown to 6 layers / ffn 1536 (4.9 M params, exact function-preserving warm start); ExIt + r1 at 50/50 | 1,500 / 2e-4 | 04 | 5.77 → 5.54 | 0.58 → 0.62 |

- **Calibration lesson:**
  - The per-state fixed point (match the teacher's play rate on the student's own states) chases itself: the
    teacher's rate falls 31.9% → 17% → 11.5% as the student plays more.
  - R3a recalibrated that way (τ 0.346, 44.8 plays/game) scores **0.627 vs v1**, i.e. −11.6 pp.
  - **Adopted:** an on-policy plays/game controller (`calibrate --mode rate`). It uses the same 128 training-bank
    cases every round and targets the teacher K4S-b64's 37.8 plays/game vs v1 (112 training-bank games).
  - Thresholds: A 0.5117 (38.7 plays/game), B 0.5407 (37.8), W 0.5109 (38.5).
- **A at its threshold (04, `eval-it1A-off`):** vs v1 0.743 (= R3a), vs R3a **0.443 [0.390, 0.500]**.
- **Teacher candidate K4SP4-b64** (K4S plus R3a's top-4 plays as extra candidates; `bot/exit/teacher.py`): 0.830
  [0.781, 0.879] vs v1 on 224 training-bank cases. A paired K4S-b64 run on the same cases is in progress.

## Iteration-1 HEADLINE results

These are the 300 HEADLINE cases. Paired Δ = student vs v1 − R3a vs v1 on the same case, bootstrapped.

| student | threshold (on-policy) | vs v1 | paired Δ vs R3a | vs R3a (h2h) | plays/game vs v1 |
|---|---|---|---|---|---|
| R3a (reference) | 0.5006 | 0.743 [0.693, 0.793] | — | — | 37.9 |
| A (ExIt only) | 0.5117 | 0.743 [0.697, 0.793] | +0.000 [−0.053, +0.057] | 0.443 [0.387, 0.503] | 39.2 |
| B (ExIt + r1 at 50/50) | 0.5407 | 0.743 [0.693, 0.790] | +0.000 [−0.053, +0.053] | 0.470 [0.417, 0.527] | 38.8 |
| W (grown 2.2×, ExIt + r1) | 0.5109 | 0.703 [0.650, 0.753] | −0.040 [−0.100, +0.017] | 0.473 [0.417, 0.530] | 39.7 |
| R3a-OP (per-state recalibration, τ 0.346) | 0.3456 | 0.627 [0.570, 0.680] | −0.116 | 0.42 (n = 131) | 44.8 |

**Reading:** no it1 student beats R3a. Offline agreement gains (+3 pp) do not transfer.

**Diagnosis:**
- The K4S teacher's candidates never include the student's own proposals: there are 16 random tiles, and student
  proposals only reorder the scan.
- Its tile labels are therefore mostly "a random tile happened to roll out best". Top-1 agreement on teacher plays is
  11%.

**Teacher candidate:** K4SP4-b64 (`bot/exit/teacher.py`) − K4S-b64 = +0.031 [−0.031, +0.094] paired vs v1 over 224
training-bank cases. So it is at least as strong.

## Iteration 2 (teacher K4SP4-b64, behavior B)

- gen-it2: **962,854 labels** (08: 577,277 from 1,500 games; 04: 385,577 from 1,000 games).
  - The teacher plays at 24.7% of the student's states and the student at 7.7%; they agree on 73%, against 66%
    under K4S.
  - Packed: `packed-it2-08` and `packed-it2-04` on both hosts.
- **K4SP4-b64 on HEADLINE (04):** vs v1 0.857 [0.817, 0.897], vs R3a 0.720 [0.670, 0.770]. This equals the lead's
  K4S-st.

### Iteration-2 HEADLINE results (300 cases; paired Δ against R3a vs v1 = 0.743)

| student | init / data | threshold (rate) | vs v1 | paired Δ vs R3a | vs R3a h2h | plays/game vs v1 |
|---|---|---|---|---|---|---|
| **D** | B + it2 (K4SP4 labels) only, 1,200 steps | 0.5375 | **0.827 [0.783, 0.867]** | **+0.083 [+0.033, +0.133]** | **0.627 [0.573, 0.680]** | 37.6 |
| C | R3a + it2 + r1 at 50/50, 1,500 steps | 0.5142 | 0.777 [0.730, 0.823] | +0.033 [−0.023, +0.093] | 0.520 [0.463, 0.577] | 38.6 |
| E | B + it3st-a (557 k K4S-st labels on B states), 1,200 steps | 0.5373 | 0.783 [0.737, 0.830] | +0.040 [−0.020, +0.103] | 0.627 [0.570, 0.680] | 36.9 |
| F | B + it2 + it3st-a, 1,500 steps | 0.5088 | 0.800 [0.753, 0.843] | +0.057 [−0.003, +0.117] | 0.537 [0.480, 0.590] | 38.4 |
| H | D + it3D-a + it3st-a + it2 (all teachers), 1,500 steps | 0.5104 | 0.817 [0.770, 0.860] | +0.073 [+0.020, +0.130] | 0.577 [0.520, 0.633]; vs D 0.528 [0.472, 0.585] | 38.1 |
| J | D + it3D (04 full + 08a), 1,000 steps | 0.5123 | 0.830 [0.787, 0.870] | +0.087 [+0.030, +0.147] | 0.557 [0.500, 0.613]; vs D 0.520 [0.460, 0.577] | 36.7 |
| **K** | D grown to 6 layers / ffn 1536 (4.9 M params, function-preserving), it3D + it2, 2,000 steps, lr 2e-4 | 0.5075 | **0.863 [0.823, 0.900]** | **+0.120 [+0.067, +0.173]** | 0.600 [0.543, 0.657]; vs D 0.527 [0.470, 0.583] | 38.9 |
| I | D + it3D-a only, 800 steps | 0.5143 | 0.827 [0.783, 0.867] | +0.083 [+0.023, +0.147] | 0.553 [0.497, 0.607]; vs D 0.477 [0.420, 0.533] | 38.0 |
| G | **D** + it3D-a (462 k, D states, K4S-st) + it3st-a, 1,200 steps | 0.5289 | 0.823 [0.777, 0.867] | +0.080 [+0.023, +0.137] | 0.577 [0.520, 0.633]; **vs D 0.537 [0.480, 0.593]** | 38.1 |

For reference, the K4S-b64 search itself scores 0.830 vs v1 and 0.633 vs R3a. **D, a single network forward per
decision, is about as strong as the 64-rollout search.** D: `$J4/train-it2D/step-001200.pt` (sha 1888a3f8…),
copied to `$J8/ckpt-it2D/`.

Held-out curves (it2 rows): D's decision agreement went 0.659 → 0.672 and top-1 on teacher plays 0.120 → 0.165. C
went 0.656 → 0.667. So small offline gains became a large strength gain once the labels scored the student's own
proposals.

## Iteration 3 (teacher K4S-st, the lead's best bot = K4S plus R3a's top-8 proposals as candidates)

- **gen-it3st** (behavior B), paused after 854 games (08) + 586 (04): **556,747 labels**, packed as
  `packed-it3st-08a` and `packed-it3st-04a`, on both hosts. The pause made room for calibration and eval within the
  110-process cap. The run is resumable.
- **gen-it3D** (behavior **D**, teacher K4S-st), 04 games [3100000, 3101500); 08 will take [3000000, 3001500).

**Iteration 3 has plateaued.** G, H and I (refits from D) are all within noise of D (vs D 0.48–0.54). D stays
the reference student.

**Paired against D** (`python -m bot.exit.paired`, same 300 HEADLINE cases; D = 0.827 vs v1, 0.627 vs R3a):

| student | what | vs v1 | Δ vs D (v1) | vs R3a | Δ vs D (R3a) | h2h vs D |
|---|---|---|---|---|---|---|
| K | grown D (4.9 M), it3D + it2 | 0.863 | +0.037 [−0.013, +0.087] | 0.600 | −0.027 [−0.090, +0.037] | 0.527 [0.470, 0.583] |
| it4a | D + it4-a (564 k labels, K4S-st@student:D teacher) | 0.840 | +0.013 [−0.037, +0.067] | 0.603 | −0.023 [−0.080, +0.033] | 0.553 [0.497, 0.610] |
| it4mix | D + it4-a + it3D (all) | 0.837 | +0.010 [−0.040, +0.063] | 0.590 | −0.037 [−0.093, +0.020] | 0.500 [0.443, 0.557] |
| D-rep (seed 2) | D recipe | 0.840 | +0.013 [−0.037, +0.063] | 0.597 | −0.030 [−0.087, +0.027] | 0.523 [0.467, 0.580] |
| Drep2 (seed 3) | D recipe | 0.843 | +0.017 [−0.033, +0.067] | 0.580 | −0.047 [−0.107, +0.013] | 0.500 [0.443, 0.557] |
| Drep3 (seed 4) | D recipe | 0.790 | −0.037 [−0.090, +0.013] | 0.573 | −0.053 [−0.113, +0.007] | 0.497 [0.443, 0.553] |
| soup4 | weight average of D, D-rep, Drep2, Drep3 (τ 0.5375) | 0.827 | +0.000 [−0.050, +0.050] | 0.590 | −0.037 [−0.093, +0.020] | 0.513 [0.457, 0.570] |
| **Kall** | D grown 6 layers / ffn 1536, ALL labels (it2 + it3st + it3D + it4), 2,500 steps, lr 2e-4 (τ 0.5375) | 0.827 | +0.000 [−0.053, +0.053] | **0.640** | +0.013 [−0.043, +0.070] | **0.573 [0.517, 0.630]** |
| it5s1 | Kall + it5a (703 k labels on Kall's states, K4S-st), 1,200 steps (τ 0.5375) | 0.863 | +0.037 [−0.010, +0.083] (vs Kall: +0.037 [−0.010, +0.083]) | 0.610 | −0.017 (vs Kall: −0.030 [−0.090, +0.027]) | **0.583 [0.530, 0.640]**; vs Kall 0.513 [0.457, 0.570] |
| **it5s2** | Kall + it5a, seed 2026101452 (τ 0.5375) | **0.883 [0.847, 0.917]** | vs Kall **+0.057 [+0.007, +0.107]** | 0.660 | vs Kall +0.020 [−0.043, +0.083] | vs D 0.560 [0.503, 0.617]; vs Kall 0.517 [0.460, 0.573] |
| **Kseed2** | K recipe, seed 2026101405 | 0.850 | +0.023 [−0.030, +0.077] | **0.647** | +0.020 [−0.037, +0.077] | 0.537 [0.480, 0.593] |

- **D recipe over 4 seeds:** mean 0.825 vs v1 (0.790–0.843) and 0.594 vs R3a (0.573–0.627). D itself is the
  luckiest seed against R3a.
- **Grown K recipe over 2 seeds:** mean 0.857 vs v1, 0.623 vs R3a and 0.532 vs D. That is a consistent +3 pp
  over the D recipe, but not significant in either seed alone.
- **The D recipe replicates:** the seeds score 0.790–0.843 vs v1 and 0.573–0.627 vs R3a. D-rep − R3a vs v1 =
  +0.097 [+0.037, +0.157].
- **Every refit or variant since D sits inside D's seed band.** The ExIt student has plateaued at about 0.84 vs
  v1 and 0.60 vs R3a; head-to-head vs D is 0.50–0.55.

**Lead (11:05Z):** K4S-st@student:D is null against K4S-st, paired in both engines. D in RoyaleSim: P1 0.820, vs v1
0.807, vs R3a 0.587, vs K4S-st 0.313. **The student is the fast deployable tier; it does not improve the search.**
Students are judged paired against D.

**K4S-st@student:D** (search with D as proposer and default; `eval-stD` on 04): **0.907 [0.873, 0.937] vs v1, 0.730
[0.680, 0.777] vs R3a**. The lead is running the full P1 rows on 03.

**Student K in RoyaleSim** (rsim15535, HEADLINE 300 cases; `$J4/rsim-K`, τ 0.5075), paired against the lead's
D-alone rows (`03:bot-headline-D-rsim15535`):

| opponent | K | D | K − D [95% CI] |
|---|---|---|---|
| v1 | 0.853 | 0.807 | +0.047 [−0.003, +0.093] |
| R3a | 0.610 | 0.587 | +0.023 [−0.043, +0.087] |
| scripted-balanced | 0.970 | 0.937 | +0.033 [+0.010, +0.060] |
| scripted-pressure | 0.960 | 0.950 | +0.010 [−0.020, +0.040] |
| **P1 mean** | **0.848** | 0.820 | +0.028 |
| K4S-st | 0.363 | 0.313 | +0.050 [−0.010, +0.113] |
| D (h2h) | 0.520 [0.463, 0.577] | – | – |

**Students vs rext-bc (RoyaleSim rsim15535, 300 cases; `$J4/rsim-rext`; K4S-st scores 0.833 vs rext-bc):**

| student | vs rext-bc | vs v1 | vs R3a |
|---|---|---|---|
| Kall | 0.853 [0.813, 0.893] | 0.843 | 0.687 [0.633, 0.737] |
| K | 0.873 [0.833, 0.910] | 0.853 | 0.610 |
| D | 0.837 [0.793, 0.877] | 0.807 | 0.587 |

Kall − D paired in RoyaleSim: vs R3a **+0.100 [+0.033, +0.167]**, vs v1 +0.037 [−0.017, +0.087], vs rext-bc +0.017
[−0.030, +0.067].

**Current best student: it5s2 (vs v1), with Kall as the established reference.** it5s2 is
`$J1/train-it5s2/step-001200.pt` (copy at `$J8/ckpt-it5s2/`), τ 0.5375. `$J8/train-it4Kall/step-002500.pt`, sha ffc4299d…, τ 0.5375. It is the
first variant whose head-to-head CI vs D excludes parity. Copies: `$J4/ckpt-Kall/` and `$J1/ckpt-Kall/`.

## Iteration 5: behavior Kall, teacher K4S-st, on-policy (13:13Z)

The X4S-4 study (coordinator b8dfb77c) independently found that on-policy labels help: −1.9 pp loss [−3.4, −0.5].

| host | what | PID | |
|---|---|---|---|
| 01 | gen-it5, [6000000, 6001500), 96 workers | 1259444 | `J1=/mpac/sdicks02/jobs/clasher/bot-exit-r1-01` |
| 08 | gen-it5, [6100000, 6101500), 72 workers | 3254487 | |
| 04 | gen-it5, [6200000, 6201500), 74 workers | 3664741 | |
| 01 GPU | `$J1/gpuq/QUEUE` (lead's runner and keep-alive): Kseed21 (lead) → **Kallseed2** (Kall recipe, seed 2026101431) | | |
| 08 GPU | `$J8/gpuq/QUEUE`: Kseed3 plus keep-alive fillers (K seeds) | 2503549 | |
| 04 GPU | `$J4/gpuq/QUEUE`: keep-alive fillers (K seeds) | 2970964 | |
| 04 CPU | cpuq2: Krsim (student K in RoyaleSim vs v1, R3a, scripted ×2, K4S-st, D) | 3192422 | |
| 01 | mirror → 04 `bot-exit-r1-01-mirror/` | 1259458 | |
| 08/04 | mirrors 08 ↔ 04 | 1178335 / 1801987 | |

D-behavior label runs were stopped at 13:10Z with STOP files: gen-it4x and gen-it4z on 08, gen-it4y on 04. Their
shards are kept.

**it5 snapshot (13:40Z):** packed-it5a-x01/x04/x08 hold 263,549 + 200,257 + 238,835 = **702,641 labels**
(Kall states, K4S-st teacher). They are on all three hosts.

**it5 fits (init Kall, grown architecture):**
- it5s1: 08, seed 2026101451, it5a, 1,200 steps;
- it5s2: 01, seed 2026101452, ahead of Kallseed2;
- it5mix: 04, it5a + it4 + it3D, 1,500 steps.

Their cal+eval jobs are queued in `$J8/cpuq/QUEUE`, against v1, R3a, D and **Kall**, cases 437000 / 438000 /
439000.

**it5 full (14:35Z):** packed-it5full-x01/x04/x08 hold 563,781 + 563,554 + 560,714 = **1,688,049 labels**
(4,498 games). On Kall's states the teacher plays 17.6% and agrees with Kall on 80%. They are on all three hosts.

Fits it5f1 (08), it5f2 (04) and it5f3 (01, after Kallseed2) each start from Kall, use it5full, 1,500 steps, seeds
2026101461/62/63. Their cal+eval jobs are queued in `$J8/cpuq/QUEUE` (cases 440000 / 441000 / 442000; opponents v1,
R3a, D, Kall).

**CPU label generation (lead):** `bot/exit/cpu_feeder.sh` since 14:58Z; it replaces the 14:27Z cpuqka
keep-alive.
- It writes 200-game Kall/K4S-st batches into `<J>/gen-ka-s<start>`. State is in `<J>/cpu-feed/`, the log in
  `<J>/cpu-feed.log`, the PID in `<J>/cpu-feed.receipt.json`.
- It caps itself at about 105 python processes per host, counting my jobs too.
- Ranges: 01 [7000000, 7100000), 04 [7100600, 7200000), 08 [7200600, 7300000). 04 [7100000, 7100600) and 08
  [7200000, 7200600) were never run.
- **Pack all `gen-ka-s*` dirs into the next iteration.** They are on-policy for Kall, labelled by K4S-st.

**How to read pending results.** On 08, from `/mpac/sdicks02/repos/clasher-bot`:

```
.venv/bin/python -B -m bot.eval.summarize $J8/ce-<name>/eval
.venv/bin/python -B -m bot.exit.paired --a $J8/ce-it4Kall/eval:it4Kall --b $J8/ce-<name>/eval:<name> --opponent v1   # also R3a
```

`<name>` is one of it5s2, it5mix, it5f1, it5f2, it5f3. The 04 `rsim-rext` dir holds K, Kall and D vs rext-bc, v1
and R3a in RoyaleSim.

**rext-bc** (lead, HEADLINE-v3): `$J4/cpuq2` job `rextS` runs K, Kall and D vs rext-bc, v1 and R3a in RoyaleSim. It
starts when 04's gen-it5 ends, with 50 workers.

**Zombie fix (13:50Z):** `generate.py` and `headline.py` joined workers in list order, so finished workers stayed
zombies behind one slow worker (about 70 seen on 08). Both now use `reap()`
(`multiprocessing.connection.wait` on sentinels, joining each worker as it exits). A test shows 3 → 0 zombies while
a slow worker is still running. The fix is synced to 08, 04 and 01 (not 03's tree, which is the lead's). Running
parents pick it up at their next launch.

Next:
1. Pack gen-it5 (about 45 min).
2. Fit from Kall on the it5 labels (plus earlier ones), with seed replicates, on the 01/08/04 queues.
3. Rate-calibrate, then run HEADLINE paired against Kall and D.

Queues: `bot/exit/gpu_queue.sh QUEUE` runs `<name> <command>` lines one by one; append lines to queue more work;
done names go to `QUEUE.done`.

04 cap: other users' processes vary; a `bot.fidelity.run` job with 34 processes appeared at 10:29Z. K's
calibration on 04 was killed at once (123 → 96) and moved to 08's CPU queue.


## Iteration 6+ (owner: ExIt sub-agent, from 2026-10-14T15:45Z)

Behaviour/teacher: teacher stays **K4S-st**. Best student entering it6: **it5s2** (sha 08bdaf32…, τ 0.5375).
Its copies are in `clasher-bot-runtime/students/it5s2-step001200.pt` (+ `.calibration.json`, sha 5abb8a51…,
`SHA256SUMS`) on 01/03/04/08, and in `<J>/ckpt-it5s2/` on 01/04/08 with the ON-POLICY calibration json. Do not use
`$J1/train-it5s2/*.calibration.json`, which is the trainer's off-policy one.

**Feeder behaviour switch, 15:48Z: Kall → it5s2.** `<J>/cpu-feed.tmpl` was replaced atomically; the old template
is `cpu-feed.tmpl.Kall.bak`, and the log is `<J>/cpu-feed/BEHAVIOUR.log`.

| host | gen-ka-s < this start: Kall | from this start: it5s2 |
|---|---|---|
| 01 | 7002000 | 7002000 |
| 04 | 7101400 | 7101400 |
| 08 | 7201400 | 7201400 |

**Labels for it6.**
- `packed-ka6a-x01/x04/x08` hold 528,708 + 373,938 + 373,226 = **1,275,872 labels**, from Kall behaviour and the
  K4S-st teacher.
  - 01: gen-ka-s7000000, s7000600, s7001200.
  - 04: s7100000, s7100600, s7100800.
  - 08: s7200000, s7200600, s7200800.
- They are on all three hosts. `bot/exit/pack_sync.sh` copies each pack and writes a `.synced` marker.
- The next pack (ka6b) starts at 01 gen-ka-s7001400, 04 s7101000 and 08 s7201000. Those are still Kall
  behaviour up to the switch starts above.

**it6 fits.** Each starts from it5s2 and trains on it5full + ka6a (about 2.96 M labels, all on Kall states).

| name | host | recipe | seed |
|---|---|---|---|
| it6s1 | 08 | 1500 steps, lr 1e-4 | 2026101471 |
| it6s2 | 04 | 1500 steps, lr 1e-4 | 2026101472 |
| it6s3 | 01 | 1500 steps, lr 1e-4 | 2026101473 |
| **it6g8** | 08 | grown to **8 layers / ffn 2048**, 2500 steps, lr 2e-4 | 2026101481 |
| it6g8b | 01 | grown to 8 layers / ffn 2048, 2500 steps, lr 2e-4 | 2026101482 |
| Kseed6s5 / Kseed6s6 / Kseed6s4 | 08 / 01 / 04 | it6s recipe | 2026101500 / 2026101600 / 2026101700 |

The `Kseed6s*` lines are also the new keep-alive templates, so later fillers are it6-recipe replicates on each host.

**Evals pending.** Each candidate is evaluated against v1, R3a, D, Kall and it5s2. it5mix was queued before this
change, so its it5s2 game is a separate `it5mixH` job.

| candidate | where | cases | PID / queue |
|---|---|---|---|
| it5mix | 08 cpuq | 439000 | it5mix, then it5mixH (h2h vs it5s2, same dir) |
| it5f1 | 08 cpuq | 440000 | it5f1b |
| Kallseed2 | 08 cpuq | 443000 | Kallseed2b |
| it5f2 | 04 | 441000 | `$J4/ce-it5f2`, PID 117233 |
| it5f3 | 01 | 442000 | `$J1/ce-it5f3`, PID 1856660 |
| **RoyaleSim it5s2** vs rext-bc, v1, R3a | 04 | — | `$J4/rsim-it5s2`, PID 127096, 20 workers |

Paired against Kall in `$J4/rsim-rext`.


### it5 results collected (our engine, HEADLINE 300 cases; Δ = paired on the same cases)

| student | vs v1 | Δ vs it5s2 (v1) | vs R3a | Δ vs it5s2 (R3a) | h2h vs Kall | h2h vs it5s2 |
|---|---|---|---|---|---|---|
| it5s2 (best) | 0.883 [0.847, 0.917] | — | 0.660 [0.607, 0.713] | — | 0.517 [0.460, 0.573] | — |
| it5s1 | 0.863 [0.823, 0.900] | — | 0.610 | — | 0.513 [0.457, 0.570] | — |
| it5mix (it5a + it4 + it3D) | 0.840 [0.797, 0.880] | −0.043 [−0.090, +0.003] | 0.650 [0.597, 0.703] | −0.010 [−0.070, +0.053] | 0.490 [0.433, 0.547] | 0.527 [0.470, 0.580] |
| it5f2 (Kall + it5full, τ 0.5075) | 0.863 [0.823, 0.900] | −0.020 [−0.067, +0.023] | 0.617 [0.560, 0.670] | −0.043 [−0.100, +0.017] | 0.513 [0.457, 0.570] | 0.483 [0.427, 0.540] |
| it5f3 (Kall + it5full, τ 0.5075) | 0.853 [0.810, 0.893] | −0.030 [−0.080, +0.020] | 0.633 [0.580, 0.690] | −0.027 [−0.087, +0.033] | 0.490 [0.433, 0.547] | 0.447 [0.390, 0.503] |

**RoyaleSim rsim15535: it5s2** (`$J4/rsim-it5s2`, τ 0.5375), paired against Kall (`$J4/rsim-rext`):

| opponent | it5s2 | Δ vs Kall [95% CI] |
|---|---|---|
| v1 | 0.887 [0.850, 0.920] | +0.043 [−0.007, +0.097] |
| R3a | 0.647 [0.593, 0.700] | −0.040 [−0.100, +0.017] |
| rext-bc | **0.883 [0.847, 0.917]** | +0.030 [−0.010, +0.073] |

For comparison, K4S-st scores 0.833 vs rext-bc.

Row helper: `python -m bot.exit.report --ref REFDIR:SUBSTR CANDDIR:SUBSTR ... [--opps v1,R3a,ckpt-it2D,Kall,it5s2]`
prints scores with 95% CIs and paired Δ vs the reference.


**Teacher switch, 17:25Z: K4S-st → K4C-r16** (lead 17:18Z, after the K4C-r16 confirmation passed).

| host | first K4C-r16 batch (gen-ka-s start) | earlier batches |
|---|---|---|
| 01 | 7004000 | K4S-st |
| 04 | 7102600 | K4S-st |
| 08 | 7203000 | K4S-st |

- The old template is `cpu-feed.tmpl.it5s2-K4Sst.bak`, and the switch is logged in `cpu-feed/BEHAVIOUR.log`.
- Each shard's `receipt.json` records `"teacher"`, so packs can tag rows by teacher.
- **Resolution check:** `generate --teacher K4C-r16` resolves through `bot.eval.headline.make_player`, then
  `bot/search/candidates.py`.
  - `candidates.py` and `cand_run.py` had never been synced to 01/04/08; they are synced now. `players/runtime.py`
    was also synced, and only its r2 pin differs; we run r1.
- **Smoke** (`$J8/smoke-teacher-*`, 2 games, bank [600010, 600012), it5s2 vs v1):
  - K4C-r8 labels are byte-identical to K4S-st, in `teacher_search_action`, `root_actions` and `root_scores`.
  - K4C-r16 labels differ; root action agreement with K4S-st is 94.5–95.0%.
  - The command hashes are identical across all three, as expected with β = 0.

**CPU cap fix, 17:05Z.**
- The feeder only checked the 105 cap when it launched a batch, so evals started afterwards pushed 01 to 125 python
  processes.
- **New `bot/exit/cpu_room.sh N`:** it blocks until live + N ≤ 110. While it waits, it holds a claim in
  `/mpac/sdicks02/jobs/clasher/bot-cpu-claims/claim-<pid>`, and `cpu_feeder.sh` now subtracts claims from its room.
- `cal_eval.sh` calls `cpu_room.sh` before calibration and before the eval.
- All three feeders were restarted with the same args and state; the PIDs are in `<J>/cpu-feed.receipt.json`.
  The new log is `<J>/cpu-feed.log2`, because detach truncates its log.
- 01 batch 7003200 was killed at launch (0 games), so the range [7003200, 7003400) is skipped.


**ka6b (18:03Z):** `packed-ka6b-x01/x04/x08` hold 758,650 + 604,077 + 527,830 = **1,890,557 labels**, all with the
K4S-st teacher. They are on all three hosts (`.synced`).

| host | Kall behaviour | it5s2 behaviour |
|---|---|---|
| 01 | s7001400–7001800 | s7002000–7003000 and s7003800 |
| 04 | s7101000–7101200 | s7101400–7102400 |
| 08 | s7201000–7201200 | s7201400–7202200 |

**Left for ka6c:**
- K4S-st teacher, it5s2 behaviour: 01 s7003400 and s7003600; 08 s7202400–7202800.
- Everything from the K4C-r16 switch starts on is K4C-r16; keep those packs separate (`packed-kc7*`).

**it7 fits.** Each starts from it5s2 and trains on it5full + ka6a + ka6b (about 4.86 M labels).

| name | host | recipe | seed | calibration cases |
|---|---|---|---|---|
| it7s1 | 04 | 1500 steps, lr 1e-4 | 2026101801 | 452000 |
| it7s2 | 08 | 1500 steps, lr 1e-4 | 2026101802 | 453000 |
| it7s3 | 01 | 1500 steps, lr 1e-4 | 2026101803 | 454000 |
| **it7g8** | 08 | 8 layers / ffn 2048, 3000 steps, lr 2e-4 | 2026101881 | 455000 |

- The pending Kseed6s6 on 01 was dropped in favour of it7s3.
- The new keep-alive templates are Kseed7s4/5/6 (04/08/01).
- Evals are queued in `<J>/cpuq6/QUEUE`; the runners are in `<J>/cpuq6/runner.receipt.json`.

**Iteration 6 results** (our engine, HEADLINE cases 0–299; Δ = paired vs it5s2 on the same cases; τ = on-policy rate
threshold):

| student | τ | vs v1 | Δ vs it5s2 (v1) | vs R3a | Δ vs it5s2 (R3a) | vs D | h2h vs it5s2 |
|---|---|---|---|---|---|---|---|
| it6s1 | 0.5075 | 0.853 [0.813, 0.890] | −0.030 [−0.080, +0.017] | 0.600 | −0.060 [−0.120, 0.000] | 0.523 | 0.470 [0.413, 0.527] |
| it6s2 | 0.5375 | 0.860 [0.820, 0.897] | −0.023 [−0.067, +0.020] | 0.643 | −0.017 [−0.077, +0.040] | 0.607 | 0.503 [0.447, 0.560] |
| it6s3 | 0.5075 | 0.880 [0.843, 0.917] | −0.003 [−0.047, +0.037] | 0.613 | −0.047 [−0.103, +0.013] | 0.553 | 0.490 [0.433, 0.547] |
| it6g8 (8 layers / ffn 2048) | 0.5375 | 0.877 [0.837, 0.913] | −0.007 [−0.050, +0.037] | 0.663 | +0.003 [−0.053, +0.060] | 0.580 | 0.474 [0.416, 0.532] (n = 293) |
| it6g8b (8 layers / ffn 2048) | 0.4775 | 0.877 [0.837, 0.913] | −0.007 [−0.053, +0.040] | 0.623 | −0.037 [−0.097, +0.023] | 0.500 | 0.430 [0.373, 0.487] |
| it5f1 (Kall + it5full) | 0.5075 | 0.827 [0.783, 0.867] | −0.057 [−0.107, −0.010] | 0.653 | −0.007 [−0.067, +0.057] | 0.513 | 0.473 [0.416, 0.530] |

**No new best in it6.** Every refit from it5s2 lies inside the seed band, at h2h 0.47–0.50 vs it5s2.

**Fresh-case confirmation of it5s2 vs Kall** (`$J8/conf-300`, HEADLINE cases 300–599):

| opponent | it5s2 | Kall | paired Δ |
|---|---|---|---|
| v1 | 0.883 | 0.880 | **+0.003 [−0.043, +0.050]** |
| R3a | 0.673 [0.620, 0.727] | 0.623 [0.570, 0.677] | **+0.050 [−0.013, +0.110]** (complete, 19:42Z; it5s2 − Kall) |

**Honest negative:** it5s2's +0.057 vs v1 on cases 0–299 does **not** replicate on fresh cases; on 0–299 it was
the best of 6 it5 fits. it5s2 remains the reference (its R3a edge is still open), but the loop has plateaued at
about 0.88 vs v1 and about 0.64 vs R3a since Kall.
- it6g8's held-out loss was 4.615 at 2500 steps, against 4.636 for it6s1 and 4.660 at init. Offline only.


**CPU leases (19:00Z, after the lead found 08 at 124 at 18:54Z).**
- **Cause:** `cal_eval.sh` only waited for room before its first phase. Between calibration rounds its workers drop
  to 0, so the feeder filled the gap, and then the next round added 30 more on top.
- **Fix:** jobs now hold a lease, `bot-cpu-claims/lease-<pid>` containing "N pgid", for their whole run.
  - `cpu_feeder.sh` subtracts max(0, N − the lease's live python processes) from its room, in addition to the
    waiting claims.
  - `cal_eval.sh` takes the lease itself.
  - `bot/exit/cpu_job.sh N CMD…` wraps any other CPU job, such as raw headline runs.
- Leases were added by hand for the two running cal_evals (01 pid 2520148, 08 pid 332005).
- All three feeders were restarted with their current args: 08 keeps the lead's cap 92; 01 and 04 keep cap 105.
  The logs are `<J>/cpu-feed.log4`.
- **Feeder targets:** 01 96, 04 80 (raised from 50 at 18:38Z, when load was ~66/128), 08 80 (cap 92).
- **Rule:** launch every CPU job through `cal_eval.sh` or `cpu_job.sh`. Never launch a bare multi-worker job.

### Running (19:45Z) and next

**Verified PIDs:**

| host | GPU runner | keep-alive | cpuq6 runner | cpuq runner | feeder | mirror |
|---|---|---|---|---|---|---|
| 01 | 1255120 | 1406036 | 2084764 | — | 2680243 | 1259458 |
| 04 | 2970964 | 3845222 | 363971 | 3045524 (idle) | 976480 | 1801987 |
| 08 | 2503549 | 3420881 | 4115451 | 2525950 (conf5, then Kallseed2b) | 535314 (cap 92) | 1178335 |

**Running now:**
- **GPU:** it7g8 (08), then it7s2 (08). Kseed7s6 (01) and Kseed7s4 (04) are it7-recipe seed replicates. it7s1
  (04) and it7s3 (01) are done or in train.
- **CPU:** cpuq6 evals for it6g8b, it7s3 (01), it7s1 (04), and Kseed6s5, it7g8 and it7s2 (08). The feeders
  generate it5s2-behaviour, **K4C-r16**-labelled batches.

**Next:**
1. Collect the it7 evals.
2. Pack the K4C-r16 batches as `packed-kc7*`.
3. Refit from it5s2 or the best it7 with K4C labels weighted in; confirm any candidate on cases 300–599 before
   calling a new best.
4. Run RoyaleSim evals for any new best.

Next calibration case blocks: 456000, 457000, … (444000–455000 are assigned above)

## Iteration 7+ (owner: ExIt sub-agent #2, from 2026-10-14T19:43Z)

Reference stays **it5s2**. A "new best" must (a) beat it5s2 paired on HEADLINE cases 0–299 vs v1 and R3a, (b) replicate
on fresh cases 300–599 (vs v1 and R3a, paired with `$J8/conf-300`), and (c) pass RoyaleSim rsim15535 vs v1, R3a and
rext-bc (paired with `$J4/rsim-it5s2`).

**K4C-r16 labels packed (19:47Z).** `bot.exit.pack` gained `--teacher/--student/--exclude/--max-rows/--select-seed`
(filters on each shard's receipt.json; `--exclude PACKED` skips shards already in a pack's sources.json).
All are it5s2 behaviour, pool v1,R3a,self; the K4S-st era differs from the K4C era only in `--teacher`.

| pack | 01 | 04 | 08 | total | content |
|---|---|---|---|---|---|
| `packed-kc7a-x*` | 615,497 | 728,921 | 201,399 | **1,545,817** | every sealed K4C-r16 shard at 19:46Z |
| `packed-ks7m-x*` | 615,492 | 454,462 | 201,385 | 1,271,339 | K4S-st shards, row-matched per host (04 had only 454k) |
| `packed-kc7m-x04` | — | 454,462 (target) | — | — | K4C-r16 subset matched to ks7m-x04 (`--select-seed 7`) |

Next K4C pack (kc7b) must use `--exclude packed-kc7a-x<host>`.

**Label-quality test (task 3):** kcM = kc7a-x01 + kc7m-x04 + kc7a-x08 vs ksM = ks7m-x*, 1.271 M rows each, same
behaviour, same init it5s2, same recipe (1500 steps, lr 1e-4), shared seed per pair. Paired over 3 seeds.

**it7 fits from it5s2 (GPU queue lines appended 19:48Z):**

| name | host | data | seed | cal cases |
|---|---|---|---|---|
| kcM1 / kcM2 / kcM3 | 04 / 01 / 08 | kcM (K4C only) | 2026102101 / 02 / 03 | 456000 / 457000 / 458000 |
| ksM1 / ksM2 / ksM3 | 04 / 01 / 08 | ksM (K4S-st only, matched) | 2026102101 / 02 / 03 | 459000 / 460000 / 464000 |
| kmix1 / kmix2 / kmix3 | 08 / 01 / 04 | `--new` kc7a ×3, `--old` it5full+ka6a+ka6b, `--new-ratio 0.5` | 2026102281 / 11 / 41 | 461000 / 462000 / 463000 |

- Evals: new runner `<J>/cpuq7` per host, `cal_eval.sh` with 36 workers and `BOT_EXIT_OPPS=v1,R3a,student:it5s2`
  (new override; D dropped to save 25% CPU). Next calibration case block: 465000.
- **Dropped as redundant** (4 it7-recipe fits already exist: it7s1, it7s3, Kseed7s4, Kseed7s6): it7s2 (GPU and its
  cpuq6 eval), Kseed7s5 filler, Kseed6s5 eval (it6-recipe replicate) — names added to the QUEUE.done files.
- **Keep-alive switched (19:49Z):** old `Kseed` keep-alives killed (01 1406036, 04 3845222, 08 3420881) along with the
  two seed fillers that had just started (01 2916864, 04 1191600); new keep-alives replicate the last **kmix** line
  per host (`gpuq/keepalive-kmix.log`, max 6). Other agents may append to `gpuq/QUEUE`; lines are never removed.

**Queue fix (20:25Z, after the lead's utilization flags).**
- **kmix1 crashed at step 2:** `OSError [Errno 24] Too many open files`. With 12 packs the DataLoader's shared-memory
  fd passing exceeds the soft nofile limit of 1024. The runner still logged rc=0.
- **Rule: no waiting items in any queue.** A wait item holds the slot, so the GPU idles and the keep-alive can't
  fill. New `bot/exit/fit_eval.sh CPUQ CAL_START W OPPS -- TRAIN_ARGS`:
  - runs `ulimit -n 65536`, then trains;
  - only if training completed, appends `ev-<tag>` (cal_eval) to `<J>/cpuq7/QUEUE`.
- For fits already training, the detached `bot/exit/when_done.sh FILE QUEUE LINE` appends the eval when
  complete.json appears: ksM1 (04), ksM2 (01), kcM3 (08).
- Pending wait-style lines (01 ksM2/kmix2, 04 kmix3, 08 ksM3 and the cpuq7 waits) were marked done and re-queued as
  fit_eval lines: kmix2f / kmix3f / kmix1f (out `train-kmix1r`) / ksM3f.
  - 01 had already started the old ksM2 line (race), so ksM2f was skipped.
  - kmix keep-alive fillers now copy the fit_eval lines, so fillers also queue their own evals.
- Dead-PID lease files were removed (01 lease-2520148, 08 lease-332005). The lead patched `cpu_feeder.sh` to count
  each process group once.
- **State at 20:27Z:** GPUs 80–97%, live python processes 96–100 on 01/04/08.

**Second GPU slot (21:05Z).**
- **Why:** kmix fits run at ~31–36 steps/min against kcM's 48. They are bound by batch assembly in the main process
  (the loader worker sits idle with a full queue), so a lone kmix fit holds the GPU at 55–65%.
- **What:** each host now runs a second runner, `<J>/gpuq2/QUEUE` (fit_eval items):

| item | host | recipe | seed | cal cases |
|---|---|---|---|---|
| kmixg8a | 08 | kmix data, grown to 8 layers / ffn 2048, 2500 steps, lr 2e-4 | 2026102381 | 465000 |
| kmixg8b | 01 | same as kmixg8a | 2026102311 | 466000 |
| kcA4 | 04 | all 1.55 M K4C labels (kc7a ×3), 1500 steps, lr 1e-4 | 2026102441 | 467000 |

- **Effect (21:10Z):** GPUs 96–100% on all three hosts; 04 uses 24.8 GB of 48 GB, so ≥20 GB stays free.
- Next calibration case block: 468000.

**Quoting bug (fixed 21:25Z).** The three `when_done.sh` eval lines kept a literal `$J`, so `bash -c` expanded it
to empty.
- ev-ksM1 and ev-ksM2 failed at mkdir `/ce-…` (rc 1).
- ev-kcM3 sat in `cpu_room` holding a 36-process claim; killed it by verified PIDs.
- Re-queued as ev-kcM3b (08), ev-ksM1b (04) and ev-ksM2b (01) with absolute paths. The fit_eval-generated lines were
  never affected.

**08 oversubscription (lead 21:55Z: load 136, 139 live python).**
- **Cause:** ev-kcM3b (37) passed `cpu_room` while the it7g8 eval was in a gap, then stacked with the RL eval (42),
  the RL actors (25), the feeder (28) and two trainers.
- **`cpu_room.sh N [CAP]`:** the default CAP is now 105 (`BOT_CPU_CAP`). It also counts leased-but-idle room
  (lease N minus the live python processes in its process group, each group once).
- **`cal_eval.sh`:** gates at 105, and caps workers at `bot-cpu-claims/max-eval-workers` if that file exists.
  - 08: the file says **24** while RL actors run there. Delete or edit it to change the cap.
- **`fit_eval.sh`:** sets `OMP_NUM_THREADS=8 MKL_NUM_THREADS=8`. Running trainers keep their old settings.
- **Lease and eval fixes on 08:**
  - The it7g8 eval lease (pgid 4115451) was cut to 4, since only 5 games were left.
  - ev-kcM3b (36 workers, 30/900 games done) was killed and re-queued as ev-kcM3c: a plain headline resume via
    `cpu_job.sh 24`. Calibration was already done; τ 0.5375 is on the ckpt.
- **Rule:** every multi-process launch goes through `cpu_room.sh N 105` (cal_eval and cpu_job both do).

**Eval routing (21:59Z):** to get two evals per host (still gated by cpu_room at 105), the kmix evals moved from
cpuq7 to the idle cpuq6 runners.
- Moved: ev-kmix2 (01) and ev-kmix1r (08).
- ev-kmix3 (04) is appended by `when_done` when its fit completes.
- In each case the cpuq7 name was marked done; no line was removed.

**127x01 GPU lent to the LIVE LEAD (lead, 23:05Z, ~10 h).**
- The lead stopped 01's gpuq runner (pgid 1255120) and the kmix keep-alive (2925019). The filler kmix2-ka2026102213
  died at step 32.
- kmixg8b (gpuq2) is allowed to finish. A detached watcher then stops the gpuq2 runner (3269819).
- **Do not queue or launch anything on 01's GPU until the lead returns it.** 01's CPU stays ours; its feeder cap is
  now 89.
- 01 evals (cpuq6/cpuq7) continue on CPU.

**cal_eval regression (21:57Z–22:55Z, fixed).** `maxw=$(cat max-eval-workers)` failed under `set -e` on hosts
without the file, so every cal_eval started on 01 or 04 in that window exited at once with rc 1.
- Lost: ev-kmix2 (01), ev-kmix2-ka2026102212 (01 filler), ev-kmix3 (04). 08 has the file and was unaffected.
- Fixed with `|| true`; tested on 04 with no file. Re-queued at 22:55Z as ev-kmix2r and ev-kmix3r (cpuq6) and
  ev-kmix2-ka2026102212r (01 cpuq7).
- 04's ev-ksM1b is slow because calibration took 4 rounds (τ 0.5375 → 0.4775 → 0.4965).

**Iteration 7 results** (our engine, HEADLINE cases 0–299; Δ paired vs it5s2 from `$J8/ce-it5s2`; rows via
`bot.exit.report`):

| student | τ | vs v1 | Δ vs it5s2 (v1) | vs R3a | Δ vs it5s2 (R3a) | vs D | h2h vs it5s2 |
|---|---|---|---|---|---|---|---|
| it7s1 (it5full+ka6a+ka6b, 4.86 M) | 0.4775 | 0.843 [0.803, 0.883] | −0.040 [−0.090, +0.010] | 0.610 | −0.050 [−0.107, +0.007] | 0.497 | 0.457 [0.400, 0.513] |
| it7s3 (same data, seed 2026101803) | 0.5375 | 0.853 [0.813, 0.890] | −0.030 [−0.080, +0.020] | 0.678 | +0.018 [−0.038, +0.073] | 0.587 | 0.540 [0.483, 0.597] |
| it7g8 (8 layers / ffn 2048, 3000 steps) | 0.5375 | 0.867 [0.830, 0.903] | −0.017 [−0.063, +0.027] | 0.653 | −0.007 [−0.070, +0.053] | 0.600 | 0.543 [0.487, 0.597] |
| kcM1 (K4C-r16 only, 1.27 M) | 0.5375 | 0.830 [0.787, 0.870] | −0.053 [−0.103, −0.003] | 0.640 | −0.020 [−0.087, +0.047] | — | 0.460 [0.403, 0.517] |
| kcM2 (K4C-r16 only, 1.27 M) | 0.5075 | 0.840 [0.797, 0.880] | −0.043 [−0.090, 0.000] | 0.620 | −0.040 [−0.107, +0.027] | — | 0.457 [0.400, 0.510] |
| ksM2 (K4S-st only, 1.27 M, pairs kcM2) | 0.5375 | 0.853 [0.813, 0.893] | −0.030 [−0.080, +0.020] | 0.660 | 0.000 [−0.063, +0.063] | — | 0.493 [0.437, 0.550] |
| kcM3 (K4C-r16 only, 1.27 M) | 0.5375 | 0.837 [0.793, 0.877] | −0.047 [−0.100, +0.003] | 0.637 | −0.023 [−0.083, +0.037] | — | 0.480 [0.423, 0.537] |
| ksM1 (K4S-st only, pairs kcM1) | 0.4965 | 0.833 [0.790, 0.873] | −0.050 [−0.097, −0.003] | 0.620 | −0.040 [−0.097, +0.017] | — | 0.420 [0.363, 0.477] |
| kmix1r (kc7a 50% + it5full/ka6a/ka6b) | 0.5075 | 0.853 [0.813, 0.893] | −0.030 [−0.077, +0.017] | 0.630 | −0.030 [−0.090, +0.030] | — | 0.420 [0.363, 0.477] |

**Label quality vs quantity (task 3), 2 of 3 seed pairs:** ksM − kcM, same behaviour, size, init and seed, pooled
per case over seeds 1–2.
- vs v1: **+0.008 [−0.030, +0.047]**
- vs R3a: **+0.010 [−0.037, +0.055]**

So K4C-r16 labels are **not** measurably better than K4S-st labels for the student, even though K4C-r16 is the
stronger bot (+0.021 fresh-bank). Both 1.27 M-row arms fall 0.03–0.05 below it5s2 vs v1. Refitting it5s2 on 1.27 M
fresh labels for 1500 steps loses strength whatever the teacher. The ksM3 pair is pending (08 cpuq7).

**Verdict at 23:50Z:** no new best; **it5s2 remains the reference**.
- None of the 9 it7-era fits beats it5s2 on HEADLINE 0–299, so none advanced to the fresh-case or RoyaleSim stages.
- The 9 fits: it7s1, it7s3, it7g8, kcM1–3, ksM1–2, kmix1r.
- Most are −0.02 to −0.05 vs v1, and head-to-head vs it5s2 is 0.42–0.54.
- The ExIt refit loop from it5s2 has plateaued. More or better labels at this step size do not move it.

**Pending (queues keep running):**
- Evals: kmix2r and the kmix2 filler eval, then kmixg8b (01 CPU); kmix3r, kcA4 and the kmix3 fillers (04);
  ksM3, kmixg8a and the kmix1r filler (08).
- GPU: kmix keep-alive fillers on 04 and 08 (max 6 each). **01's GPU is lent to the LIVE LEAD; nothing of ours
  runs on it.**
- Feeders: it5s2 behaviour, K4C-r16 teacher, on all three hosts. Unpacked K4C shards start after kc7a; the next
  pack uses `--exclude packed-kc7a-x<host>`.

**Next ideas** (the loop needs a change of kind, not more refits):
1. Lower lr or fewer steps from it5s2, so a refit stops degrading it.
2. Train from the Kall/R3a lineage on all labels, it5full + ka6* + kc7a (~6.4 M).
3. Stop ExIt here and hand it5s2 to the RL fine-tuning agent as its init.

## Iteration 8: arms A/B (owner: ExIt sub-agent #3, from 2026-10-14T23:51Z; time box ~10 h, to ~10:00Z 10-15)

Lead decision: stop 1500-step refits. Reference stays **it5s2** (sha 08bdaf32…, τ 0.5375). Promotion rule
unchanged: beat it5s2 paired on HEADLINE 0–299 vs v1 and R3a → fresh cases 300–599 (`$J8/conf-300` pairs) →
RoyaleSim rsim15535 vs v1, R3a, rext-bc (`$J4/rsim-it5s2` pairs).

**Data for both arms ("all labels", 6.4 M rows):** the 12 packs it5full, ka6a, ka6b, kc7a × x01/x04/x08, all as
`--new` (uniform over rows, K4C-r16 ≈ 24 %; budget-cut rows dropped; 5 % held out by game hash).

**Arm A: gentle refits from it5s2** (`<J>/gpuq/QUEUE`, warmup 100, one checkpoint at the end). Seed s1 (08,
2026102501) and s2 (04, 2026102502) are shared across the four configs, so lr/steps comparisons see the same batches.

| name | lr | steps | cal cases (s1 08 / s2 04) |
|---|---|---|---|
| A3x300s1 / s2 | 3e-5 (×0.3) | 300 | 468000 / 472000 |
| A3x800s1 / s2 | 3e-5 | 800 | 469000 / 473000 |
| A1x300s1 / s2 | 1e-5 (×0.1) | 300 | 470000 / 474000 |
| A1x800s1 / s2 | 1e-5 | 800 | 471000 / 475000 |

**Arm B: Kall lineage on all labels.** Init it2D step 1200 (Kall's init, as it4Kall), grown function-preserving,
lr 2e-4, warmup 150, **6000 steps** (≈3.8 epochs of 6.4 M; Kall had 2500 steps on 3.06 M), ckpts every 1500.

| name | host / queue | arch | seed | cal cases |
|---|---|---|---|---|
| B6s1 | 08 gpuq2 | 6 layers / ffn 1536 (Kall arch) | 2026102661 | 476000 |
| B6s2 | 08 gpuq (after arm A) | same | 2026102662 | 477000 |
| B8s1 | 04 gpuq2 | 8 layers / ffn 2048 | 2026102681 | 478000 |
| B8s2 | 04 gpuq (after arm A) | same | 2026102682 | 479000 |

Next calibration case block: 480000.
- Evals: `fit_eval.sh` appends `ev-<name>` (on-policy cal + HEADLINE 300 cases vs v1, R3a, it5s2 h2h) to
  `<J>/cpuq6/QUEUE` (arm A) or `<J>/cpuq7/QUEUE` (arm B) on the fit's host. If 04's CPU is full (RL lead's evals),
  copy the ckpt + `.calibration.json` to 01 and run the eval there.
- Read rows: `.venv/bin/python -B -m bot.exit.report --ref $J8/ce-it5s2:it5s2 <J>/ce-<name>:<name> --opps v1,R3a,it5s2`.

**Queue/CPU changes (23:55Z):**
- kmix keep-alives killed (04 1222234, 08 792318) and the two running kmix fillers killed (04 kmixka234550,
  08 kmixka233346; partial dirs `train-kmix*-ka*` left, no eval). No keep-alive now; arm B's long fits keep both
  GPUs busy until ~05–07Z. **Append new GPU work to `<J>/gpuq*/QUEUE`; nothing on 01's GPU (LIVE LEAD until ~09Z).**
- Skipped (marked done, not run) the kmix replicate evals: 01 ev-kmix2-ka2026102212r (killed at 3 min), 04
  ev-kmix3-ka2026102242/43, 08 ev-kmix1r-ka2026102282.
- Feeders: 01 target 96 → 24 (PID 4082246, log `cpu-feed.log5`), 08 80 → 24 (PID 2100782, `cpu-feed.log5`),
  **04 stopped** (next_start 7106000; restart with the old args from `cpu-feed/BEHAVIOUR.log`). The labels can't
  reach this time box's fits; the CPU goes to evals. In-flight batches drain on their own.

**00:12Z: RL fine-tune finished (lead), so its CPU/GPU share is free.**
- 08 `bot-cpu-claims/max-eval-workers` 24 → 36. 04 feeder restarted at target 24 (PID 2783863, `cpu-feed.log5`).
- Learning-curve probes: detached `when_done.sh` append `ev-B6s1-3000` (08 cpuq7, cases 480000; PID 2179426) and
  `ev-B8s1-3000` (04 cpuq7, 481000; PID 2788210) when the step-3000 ckpts appear. Next cal block: **482000**.
- **K4C vs K4S, all 3 seed pairs** (ksM − kcM, per case pooled): vs v1 **+0.004 [−0.028, +0.037]**, vs R3a
  **+0.020 [−0.018, +0.059]**: null. ksM3 (τ 0.5075): v1 0.833, Δ vs it5s2 −0.050 [−0.097, −0.007]; R3a 0.677,
  Δ +0.017 [−0.040, +0.073]; h2h vs it5s2 0.443.
- Reporting on 05: `bot/exit/it8_pull.sh` (EV=dir) copies `ce-*/eval/games-*.jsonl` to `/tmp/sdicks02-exit8/ev/<host>/`;
  `python3 bot/exit/pooled_delta.py OPPS A,B [A,B ...]` gives seed-pooled paired deltas.

**Iteration 8 results** (our engine, HEADLINE 0–299; Δ paired vs it5s2 `$J8/ce-it5s2`; h2h = score vs it5s2):

| student | τ | vs v1 | Δ vs it5s2 (v1) | vs R3a | Δ vs it5s2 (R3a) | h2h vs it5s2 |
|---|---|---|---|---|---|---|
| kmix2 (it7 leftover) | 0.5375 | 0.890 [0.853, 0.923] | +0.007 [−0.037, +0.050] | 0.633 | −0.027 [−0.083, +0.027] | 0.470 |
| kmix3 (it7 leftover) | 0.5375 | 0.883 [0.847, 0.920] | 0.000 [−0.040, +0.043] | 0.610 | −0.050 [−0.107, +0.007] | 0.503 |
| kcA4 (it7 leftover, 1.55 M K4C) | 0.5075 | 0.863 [0.823, 0.900] | −0.020 [−0.063, +0.023] | 0.550 | **−0.110 [−0.167, −0.053]** | 0.417 |
| kmixg8b (it7 leftover, 8 layers) | 0.5375 | 0.863 [0.823, 0.900] | −0.020 [−0.070, +0.027] | 0.630 | −0.030 [−0.083, +0.027] | 0.470 |
| kmixg8a (it7 leftover, 8 layers) | 0.5075 | 0.850 [0.810, 0.890] | −0.033 [−0.083, +0.013] | 0.610 | −0.050 [−0.110, +0.013] | 0.470 |
| A3x800s2 (lr 3e-5, 800 steps) | 0.5075 | 0.870 [0.830, 0.907] | −0.013 [−0.057, +0.033] | 0.630 | −0.030 [−0.087, +0.027] | 0.422 |
| A3x300s1 (lr 3e-5, 300 steps) | 0.5375 | 0.847 [0.807, 0.887] | −0.037 [−0.087, +0.013] | 0.673 | +0.013 [−0.047, +0.073] | 0.477 |
| A3x300s2 | 0.5375 | 0.870 [0.830, 0.907] | −0.013 [−0.060, +0.033] | 0.650 | −0.010 [−0.070, +0.050] | 0.480 |
| A3x800s1 (lr 3e-5, 800 steps) | 0.5375 | 0.893 [0.857, 0.927] | +0.010 [−0.033, +0.053] | 0.640 | −0.020 [−0.083, +0.040] | 0.470 |
| A1x300s1 (lr 1e-5, 300 steps) | 0.5375 | 0.873 [0.833, 0.910] | −0.010 [−0.057, +0.037] | 0.660 | 0.000 [−0.063, +0.060] | 0.473 |
| A1x300s2 | 0.5075 | 0.843 [0.800, 0.883] | −0.040 [−0.087, +0.003] | 0.650 | −0.010 [−0.073, +0.057] | 0.473 |
| A1x800s1 (lr 1e-5, 800 steps) | 0.5375 | 0.857 [0.817, 0.897] | −0.027 [−0.073, +0.020] | 0.637 | −0.023 [−0.087, +0.037] | 0.487 |
| A1x800s2 | 0.5375 | 0.870 [0.830, 0.907] | −0.013 [−0.060, +0.033] | 0.683 | +0.023 [−0.030, +0.077] | 0.447 |
| **B6s1 (Kall lineage, 6L, 6000 steps, all 6.4 M)** | 0.5375 | 0.880 [0.843, 0.917] | −0.003 [−0.053, +0.043] | 0.650 | −0.010 [−0.067, +0.047] | 0.513 |
| B6s2 (Kall lineage, 6L, seed 2) | 0.5375 | 0.867 [0.827, 0.903] | −0.017 [−0.063, +0.030] | 0.667 | +0.007 [−0.053, +0.067] | 0.497 |
| soupB6s12 (weight average of B6s1 + B6s2) | 0.4775 | 0.857 [0.817, 0.897] | −0.027 [−0.070, +0.017] | 0.597 | **−0.063 [−0.123, −0.003]** | 0.477 |
| B6s3 (6L, seed 3) | 0.5075 | 0.873 [0.833, 0.910] | −0.010 [−0.057, +0.037] | 0.627 | −0.033 [−0.093, +0.027] | 0.493 |
| B8s2 (8L, seed 2) | 0.5075 | 0.833 [0.790, 0.877] | −0.050 [−0.100, −0.003] | 0.620 | −0.040 [−0.103, +0.027] | 0.507 |
| **B8s3 (8L, seed 3)** | 0.5375 | 0.887 [0.850, 0.920] | **+0.003 [−0.040, +0.047]** | 0.662 | **+0.002 [−0.058, +0.062]** | 0.503 |
| B8s1 (Kall lineage, 8L/2048, 6000 steps) | 0.5075 | 0.863 [0.823, 0.900] | −0.020 [−0.063, +0.023] | 0.623 | −0.037 [−0.100, +0.023] | 0.483 |
| B8s1 @ step 3000 (probe) | 0.5375 | 0.853 [0.813, 0.893] | −0.030 [−0.080, +0.023] | 0.683 | +0.023 [−0.033, +0.080] | 0.537 |
| B6s1 @ step 3000 (probe) | 0.5075 | 0.837 [0.793, 0.877] | −0.047 [−0.100, +0.003] | 0.600 | −0.060 [−0.120, 0.000] | 0.433 (n 263) |

Note (01:10Z): even a 300-step lr-3e-5 nudge lands −0.037 vs v1. it5s2's 0–299 score was the max of 6 it5 fits and
its +0.057 vs Kall did not replicate on 300–599, so "beat it5s2 on 0–299" carries a selection (winner's-curse) bias.
The lr-1e-5 arm-A fits are near-copies of it5s2 and serve as the null control for that bias.
- Eval routing: `bot/exit/moveto01.sh NAME [04|08]` moves a pending 04 cpuq6 eval to 01 (sha-checked copy).
  Done for A3x300s2 (01 cpuq6); `moveto01.sh A1x300s1 08` did A1x300s1 (08 → 01 cpuq6).
- **All it7 leftovers are in (01:35Z): none beats it5s2.**
- **02:00Z:** feeders raised 24 → 48 on 01/04/08 (CPU idle at ~60/128; leases keep evals first). PIDs 01 465191,
  04 3327187, 08 2717927; logs `cpu-feed.log6`. B6s1 at step 3313, B8s1 at 2577 (8L ≈ 15 steps/min → done ≈ 06:40Z).
- **Arm A interim (02:30Z, 6 of 8):** pooled per case over the 6 fits, gentle refit − it5s2 = **−0.017 [−0.053,
  +0.019]** vs v1 and **−0.009 [−0.057, +0.039]** vs R3a. No single fit beats it5s2 on both. Small steps neither help
  nor hurt measurably, so it5s2 looks like a local optimum for this data (plus the 0–299 selection bias).
- 02:27Z: 08 feeder 48 → 16 (PID 2853243) and 04 48 → 24 (PID 3472083), logs `cpu-feed.log7`. Target 48 starved
  ev-A1x800s1 and the lead's `bot-lfast` job (both waited in cpu_room for 25 min). 01 stays at 48 (cap 89).
- 02:53Z: 01 feeder target 72, cap 89 kept (PID 716842, `cpu-feed.log7`). Queued extra 6L seeds in gpuq2 to
  follow B*s1: **B6s3** (08, seed 2026102663, cal 482000) and **B6s4** (04, seed 2026102664, cal 483000). Next cal
  block: **484000**. Kill them (verified trainer PID) if B6s1/B6s2 finals are clearly below it5s2.
  ETAs: B6s1 ≈ 03:50Z, B8s1 ≈ 04:40Z, B6s2 ≈ 05:30Z, B8s2 ≈ 06:45Z, B6s3/s4 ≈ 08:30–09:30Z (+45 min eval each).
- **Arm A final (03:25Z, 8 of 8): no new best.** Pooled per case over all 8 fits, gentle refit − it5s2 = **−0.018
  [−0.052, +0.018]** vs v1 and **−0.007 [−0.054, +0.040]** vs R3a.
  - lr 1e-5 (4 fits): −0.022 [−0.058, +0.013] / −0.003 [−0.052, +0.046].
  - lr 3e-5 (4 fits): −0.013 [−0.050, +0.024] / −0.012 [−0.061, +0.037].
  - The near-copies (lr 1e-5) lose as much as lr 3e-5, so the ~−0.02 vs v1 is mostly the 0–299 selection
    inflation of it5s2, not harm from the step. Small steps neither help nor hurt: **it5s2 is a local optimum** of
    this data/objective.
- 03:26Z: 04 feeder 24 → 40 (`cpu-feed.log8`). 08 stays at 16: the lead's `bot-lfast` wall job holds 40 there.
- **B6s1 final (04:10Z):** ties it5s2 (Δ −0.003 / −0.010, h2h 0.513). It is the best non-reference fit so far, but
  not a win, so it was not promoted. Trained from it2D (not from it5s2), so data quantity at full training reaches
  it5s2's level. Waiting on the other seeds and the 8L arm.
- **Utilization flag (lead 03:54Z):** feeders 04 → target 80, 08 → target 70, 100-game batches, cap 105.
  - From 03:56Z to 04:09Z the caps were 141/136 (to look past the old K4L wall lease's idle room). When the K4L
    `bot-lfast/fresh2-resume` jobs (40-proc leases) started, live py overshot to 126 (04) and 115 (08).
  - Fixed: caps back to 105 (PIDs 04 4025244, 08 3385733, `cpu-feed.log10`). Killed the newest batches by PGID:
    04 s7108800 and 08 s7207900, so those 100-seed ranges are skipped.
  - 04:12Z: live py 04 = 98, 08 = 105.
  - The 08 feeder block is NOT exhausted: it runs to 7300000 (next_start ~7208000).
  - **Rule:** never raise a feeder cap above 105 to work around another job's lease.
- **04:25Z: 01's GPU is back from the LIVE LEAD** (lead). The LIVE LEAD's PID 1117790 (eval_val.py, ~2 GB) still
  coexists; leave it alone.
  - New 01 gpuq runner: PID 1161458, log `gpuq/runner.log2`.
  - Keep-alive `gpu_keepalive.sh gpuq/QUEUE B8s 2`: PID 1161470, log `gpuq/keepalive-B8s.log`. It replicates the
    last B8s line with seed+1, at most 2 fillers.
  - Queued **B8s3** (8L, seed 2026102683, cal 484000); its eval goes to 01 cpuq7. Next cal block: **485000**.
  - The lead restarted the 01 feeder at cap 105 (PID 1157187, `cpu-feed.log8`).
- 04:45Z (lead): 01 feeder restarted at target 92, cap 105 (PID 1237616, `cpu-feed.log9`, same block). Evals on 01
  take room through cpu_room leases, and the feeder yields.
- **06:06Z:** B8s1 final is below its own step-3000 probe vs R3a (0.683 → 0.623). Not a win.
  - 08 gpuq was empty after B6s2, so **B6x** is queued: 6L, seed 2026102671, cal 485000, on all ~9.5 M labels
    (the 12 packs plus Kall's 8 older packs it2-08/04, it3st-08a/04a, it3D-04full/08full, it4-08a/04a).
  - **soupB6s12** = `bot.exit.soup` of B6s1 + B6s2 at step 6000. Both grow it2D identically, so they share an
    init. File `$J8/soup-B6s12/soup.pt`; eval `ev-soupB6s12` in 08 cpuq6, cal 486000.
  - Next cal block: **487000**.
- **06:40Z, B6 pooled over s1 and s2:** − it5s2 = **−0.010 [−0.050, +0.032]** vs v1 and **−0.002 [−0.053, +0.050]**
  vs R3a. That is level with it5s2, the closest of any arm (arm A −0.018/−0.007, it7 −0.03…−0.05), but no win.
- **07:10Z:** B8s2 (04), B6s3 (08) and B8s3 (01) finished training; their evals are in the cpuq7s.
  - 01's keep-alive started filler `B8ska070748` (seed 2026102684, out `train-B8s3-ka2026102684`).
  - Queued more 6L seeds: **B6s5** (04 gpuq, seed 2026102665, cal 487000) and **B6s6** (08 gpuq2, seed 2026102666,
    cal 488000). Both finish after the time box (~11–12Z), so a successor must collect them.
  - Next cal block: **489000**.
- **07:40Z: the soup is negative.** Averaging two same-init 6000-step seeds needs τ 0.4775 (the gate gets less
  confident) and loses −0.063 vs R3a. Don't soup Kall-lineage seeds.
- **08:20Z: pooled arm B** (− it5s2, per case over seeds):
  - B6 s1–3: **−0.010 [−0.048, +0.029]** vs v1, **−0.012 [−0.062, +0.038]** vs R3a.
  - B8 s1–3: **−0.022 [−0.058, +0.014]** vs v1, **−0.025 [−0.077, +0.027]** vs R3a.
- **B8s3 is above it5s2 on both (+0.003 / +0.002), so per the rule it goes to confirmation.** It is best of 3 seeds
  with a noise-sized margin, so we expect regression. Both checks started 08:20Z and run in parallel to fit the box:
  - fresh cases 300–599 vs v1 and R3a: `$J1/conf-B8s3` (01, cpu_job 36, PID 2321351). Pair with `$J8/conf-300`
    (it5s2: `student:…ckpt-it5s2`).
  - RoyaleSim rsim15535 vs rext-bc, v1, R3a: `$J4/rsim-B8s3` (04, cpu_job 36, PID 1129524). Ckpt copied to
    `$J4/ckpt-B8s3/` (sha a13bb62f…). Pair with `$J4/rsim-it5s2`.
  - Both use τ 0.5375 pinned (`@0.5375`).
- **09:08Z: B8s3 fresh-case check FAILED.** Cases 300–599, paired with it5s2 in `$J8/conf-300`:

  | opponent | B8s3 | it5s2 | Δ (B8s3 − it5s2) |
  |---|---|---|---|
  | v1 | 0.867 | 0.883 | −0.017 [−0.063, +0.033] |
  | R3a | 0.610 | 0.673 | **−0.063 [−0.123, −0.003]** |

  Its HEADLINE +0.003/+0.002 was best-of-3 seed noise. **Not a new best.** RoyaleSim (`$J4/rsim-B8s3`) is
  recorded below for information only.
- RoyaleSim rsim15535, B8s3 vs it5s2 (paired with `$J4/rsim-it5s2`):
  - rext-bc: 0.867, Δ −0.017 [−0.060, +0.027]
  - v1: 0.873, Δ −0.013 [−0.063, +0.033]
  - R3a: 0.647, Δ 0.000 [−0.063, +0.063]

### Iteration 8 verdict (09:10Z): no new best, it5s2 remains the reference

- **Arm A, gentle refits from it5s2** (8 fits: lr 3e-5/1e-5 × 300/800 steps × 2 seeds). Pooled − it5s2:
  −0.018 [−0.052, +0.018] vs v1, −0.007 [−0.054, +0.040] vs R3a. Near-copies (lr 1e-5) score the same as lr 3e-5.
  it5s2 is a local optimum, and its 0–299 score carries about +0.02 of selection inflation.
- **Arm B, Kall lineage on all 6.4 M labels** (from it2D, 6000 steps):
  - B6 (3 seeds): −0.010 [−0.048, +0.029] / −0.012 [−0.062, +0.038].
  - B8 (3 seeds): −0.022 [−0.058, +0.014] / −0.025 [−0.077, +0.027].
  - Retraining from it2D on 2× the data reaches it5s2's level but does not pass it. 8 layers did not help.
  - The only fit above it5s2 on HEADLINE (B8s3) failed the fresh bank.
- **Side results:**
  - K4C vs K4S labels are null over 3 seed pairs.
  - Soup of B6s1+B6s2 is −0.063 vs R3a.
  - All it7 leftovers are below it5s2.
- **Conclusion:** the supervised ExIt student has plateaued at about 0.87–0.88 vs v1 and 0.63–0.67 vs R3a on this
  teacher and label set. Neither step size (A) nor data quantity at full training (B) moves it. The remaining
  lever is the teacher/targets (stronger or different supervision), or RL from it5s2.

**Still running at hand-off (09:10Z).** Each fit's eval is queued automatically by fit_eval in its host's cpuq7.

| fit | host | step at 09:10Z | ETA | note |
|---|---|---|---|---|
| B6x | 08 gpuq | 4500 | ≈10:10Z | 6L on all ~9.5 M labels (adds Kall's older data); cal 485000 |
| B6s5 | 04 gpuq | 3218 | ≈11:15Z | 6L seed 5 |
| B6s6 | 08 gpuq2 | 3073 | ≈11:20Z | 6L seed 6 |
| B6s7 | 04 gpuq2 | 317 | ≈13:30Z | 6L seed 7 |
| B8s3-ka2026102684 | 01 gpuq | 4500 | ≈09:45Z | B8 keep-alive filler |

- After B8s3-ka2026102684, 01's keep-alive adds 1 more B8 filler (max 2), then stops.
- Pending eval: ev-B6s4 (04 cpuq7).
- Feeders (K4C-r16 teacher, it5s2 behaviour) keep running: 01 lead's PID 1237616; 04 PID 4025244 (target 80);
  08 PID 3385733 (target 70). All cap 105, 100-game batches.
- To pool B6 seeds when they land:
  `python3 bot/exit/pooled_delta.py v1,R3a <ce-B6sN/eval>:B6sN/,$REF …` (REF = `$J8/ce-it5s2/eval:it5s2`).
  A B6 that passes HEADLINE still needs the fresh bank 300–599 (`conf-*`) and RoyaleSim. Expect regression.

## Iteration 9: change the supervision (owner: ExIt sub-agent #4, from 2026-10-15T09:20Z; time box ~12 h, to ~21:20Z)

Lead decision: no more refits on the same supervision, no more K4C-r16 labels after the in-flight batches. Reference
stays **it5s2** (sha 08bdaf32…, τ 0.5375). Promotion rule: pooled seeds beat it5s2 on HEADLINE 0–299 vs v1 and R3a →
fresh cases (never HEADLINE for the final claim) → RoyaleSim rsim15535; report the play-count band vs v1 (37.8 ± 3).

**Arm (a), soft/value targets, is already the recipe (measured 09:24Z).** `bot.exit.label` records the teacher's
complete candidate list and per-candidate root scores (`root_actions/root_scores/root_valid`, WAIT and timed waits
included), and `bot.exit.train` trains on `exit_r3.student.teacher_loss` = cross-entropy against
softmax(scores / T) with T = 0.003, not the argmax. On 20 k K4C-r16 roots (`packed-kc7a-x08`):

| statistic | p10 | p25 | p50 | p75 | p90 |
|---|---|---|---|---|---|
| candidates per root | 4 | 4 | 12 | 12 | 12 |
| top-1 − top-2 score gap | 0.000 | 0.0017 | 0.0032 | 0.0037 | 0.0069 |
| score range | 0.0053 | 0.0059 | 0.0086 | 0.0173 | 0.0288 |

At T = 0.003 the target puts a mean 0.53 (median 0.59) on the best candidate, entropy 1.30 nats; T = 0.01 gives
0.28, T ≥ 0.03 is near uniform. The temperature axis was already swept in ExIt r2
(`reports/strategy_council_20260928/PLAN-NEXT-20261010.md`: X1 T=0.003 ≈ median gap, X2 ≈ argmax, X3 z-scored), and
T = 0.003 is that sweep's recipe. So (a) is not a new lever; it9 runs (b) and (c) instead.

**Arm (b): K4L-R-gs teacher, on-policy it5s2 behaviour.** The strongest bot (+0.055 [+0.041, +0.068] over K4C-r16 on
fresh banks) as the labeller, everything else as the K4C-r16 feeders (pool v1,R3a,self, budget 64; its soft scores
cover the work set: WAIT, timed waits and the top-8 plays).
- Smoke (08, `$J8/k4l-smoke`, TRAIN1 [8990000, 8990003)): 90 CPU s per game, 233 labels, 0 budget cuts, sealed.
- 01 had no K4L code or opponent nets: `bot/` rsynced from 05 and `bot-lopp-models/` copied from 04 (sha256 equal;
  `pool.npz` 1e4bb6a0…).
- 09:28Z: the K4C-r16 feeders were stopped (01 1237616, 04 4025244, 08 3385733; in-flight batches drain) and K4L-R-gs
  feeders started: state `<J>/cpu-feed-k4l`, template `<J>/cpu-feed-k4l.tmpl`, log `<J>/cpu-feed-k4l.log`, cap 105,
  100-game batches.

| host | feeder PID | target | TRAIN1 block |
|---|---|---|---|
| 01 | 2646090 | 92 | [8000000, 8100000) |
| 04 | 1490179 | 80 | [8100000, 8200000) |
| 08 | 809475 | 70 | [8200000, 8300000) |

- Plan: when ~1.3 M K4L rows exist, (1) **kLM1–3** = kcM1–3's exact recipe (from it5s2, 1500 steps, lr 1e-4, seeds
  2026102101/02/03) on 1.27 M K4L rows, so kLM − kcM pooled over seeds is the teacher effect at matched size;
  (2) **BL6** = arm B's B6 recipe (it2D, grown 6L, 6000 steps) with K4L rows as `--new` at ratio 0.5 and the 12
  it8 packs as `--old`, the promotion candidate if K4L labels help.

**Arm (c): RL retry, critic first.** RL r3's critic explained 0–36 % of outcome variance. The packs hold millions of
it5s2-behaviour states with the labelled seat's game outcome (`recorded_outcome`), so `bot/rl/critic_pretrain.py`
trains the RL critic (`bot.rl.learner.make_critic`) on them before any PPO, and reports explained variance on
held-out games and on RL r3's 127 leftover rollouts (copied to `$J1/critic-inputs-r3`, with r3's
`learner-state.pt` sha 4e66f255… as the reference critic). Opponent ids follow generate's pool rule
(`('v1','R3a','self')[g % 3]`, checked against local receipts). If the pretrained critic is clearly better, RL r4 =
PPO from it5s2 with `--critic-init`, a lower KL coefficient and higher lr, and more actors vs R3a/it5s2
(`BOT_RL_LEAGUE`, new in `bot/rl/actor.py`; names and ids unchanged).
- 09:30Z: `packed-kc7b-x01` = all 01 K4C-r16 shards after kc7a (it5s2 behaviour): 15,856 shards, 4,477,958 rows.
- 09:34Z: 01's B8 keep-alive (1161470) killed; its running filler B8s3-ka2026102684 finishes, no more B8 fillers.
- **Critic c1** (01 GPU, `$J1/critic-c1`, PID 2712348): it5s2 init, all 7 it5s2-behaviour packs (kc7a ×3, ks7m ×3,
  kc7b-x01) = 6,950,319 train rows, 344,795 held-out rows (by game); 20,190 shard receipts matched the pool rule.
  4000 steps × 4096, lr 1e-4. Explained variance of the game outcome:

  | critic | held-out games | RL r3 rollouts (127 games, 35 k decisions) | by opponent (rollouts): v1 / R3a / it5s2 |
  |---|---|---|---|
  | RL r3's own critic after 23 updates (reference) | — | 0.233 | 0.03 / 0.39 / 0.09 |
  | c1, step 0 (untrained head) | −0.06 | −0.02 | — |
  | c1, step 250 | 0.493 | 0.499 | 0.48 / 0.60 / 0.46 |
  | c1, step 500 | 0.504 | 0.512 | 0.49 / 0.59 / 0.50 |
  | c1, step 750 | 0.507 | 0.532 | 0.51 / 0.63 / 0.50 |

  So 100× more games (from the ExIt corpus) more than double the critic's explained variance; this was the RL
  owner's first recommendation.
- **RL r4** (01; RUN = `/mpac/sdicks02/jobs/clasher/bot-rl-r4`, launched 10:00Z). Changes vs r3, as the RL owner
  recommended:
  - critic init = c1 step 750 (`RUN/critic-init-c1-step750.pt`, sha e849d8e0…), 1 critic-only warm-up update;
  - policy lr 3e-5 (r3 1e-5), KL coefficient 0.01 (r3 0.05);
  - league (`BOT_RL_LEAGUE`): v1 .15, R3a .35, it5s2 .30, self .15, K4C-r16 .05 (r3: .30/.25/.20/.15/.10), so actors
    play where the headroom is;
  - unchanged: λ 1 (MC advantage, now outcome − a 0.5-EV critic), κ 0.1, T 0.1, 2 epochs, ≤400 games per update,
    max lag 2, snapshots every 10 versions, deployed decode at τ0 0.5375; RL_BANK unchanged with **new blocks ≥ 10**
    (r3 used 0–4).
  - Learner PID 2809878 (01 GPU, `BOT_GPU_MAX_GB=16`); actors block 10, 48 workers via `cpu_job.sh` (wrapper 2811714);
    01's K4L feeder lowered 92 → 44 at 09:54Z (PID 2777620, `cpu-feed-k4l.log2`) to make room.
  - Evals: `bot/rl/eval_watch.sh` on 08 (PID 972426, DST `/mpac/sdicks02/jobs/clasher/bot-rl-r4-eval08`, 24 workers):
    each snapshot vs v1, R3a and it5s2 on HEADLINE 0–299, paired vs `$J8/ce-it5s2`.
  - Stop: `touch RUN/STOP_ACTORS RUN/STOP_LEARNER` (01) and `bot-rl-r4-eval08/STOP` (08).
- 10:14Z: the 48-worker actor pool was still waiting for room (01 live py 73, K4C batches draining), so it was
  replaced by a **32-worker** pool on the same block 10 (block 10 had not started): wrapper PID 2886058,
  `RUN/actor-b10.log`. Add a second pool on a new block (≥ 11) when 01 has room.
- 10:24Z, update 1 (critic-only warm-up, 162 games, 45 k decisions): explained variance of the fresh batch
  **before** training 0.348 (r3 at the same point: −0.002); explore score 0.568 (v1 0.84, R3a 0.62, it5s2 0.46);
  deployed would-play 38.6 per game.
- **10:36Z, allocation change (coordinator): 01's GPU goes to the LIVE LEAD's perception round 2 for ~6–10 h.**
  - SIGTERM to critic c1 (2712348; stopped at step ~3300; `critic-best.pt` = step 3250, held-out EV 0.516), the RL r4
    learner (2809878; state after update 2) and 01's gpuq runner (1161458). 01 `nvidia-smi`: no processes of ours
    at 10:36:42Z. **Do not queue anything on 01's GPU until the LIVE LEAD returns it.**
  - 01 K4L feeder cap 105 → **89** (target 44; PID 3011456, `cpu-feed-k4l.log3`), so the LIVE LEAD keeps ≤16 loader
    cores. Other 01 CPU work continues; keep 01 ≤89 live python.
  - **RL r4 moved to 08's GPU:** RUN copied to the same path on 08 (rollouts moved, not copied, so none is consumed
    twice); learner resumed there with `--resume` and the same args (PID 1155932, `RUN/learner.log`; the 01 log is
    `learner.log.01`). The actors stay on 01's CPU; `bot/rl/remote_sync.sh 127x08 RUN` on 01 (PID 3014735) pushes
    rollouts to 08 and pulls policies back. Verified: 08 published version 2 and 01's LATEST followed.
  - `bot/rl/eval_watch.sh` gained SRC_HOST `local` (08 cannot ssh to itself); the 08 watcher was restarted as
    `eval_watch.sh local RUN …` (PID 1161529).
  - Stop RL now: `touch RUN/STOP_LEARNER RUN/STOP_ACTORS` on 08 (01's sync propagates STOP_ACTORS), `RUN/STOP_SYNC`
    on 01, `bot-rl-r4-eval08/STOP` on 08.
- **10:57Z, critic reset.** After 4 PPO updates the critic's out-of-sample EV per batch had fallen from 0.35 (warm-up)
  to 0.14–0.26 under online training at critic lr 1e-4 on ~160 games per update. `bot.rl.learner` now applies the
  command-line lrs on `--resume`, and `--resume --critic-init` resets the critic and its optimizer. The learner was
  restarted with the critic reset to c1's best (step 2500, held-out EV 0.5163, `RUN/critic-init-c1-step2500.pt` sha
  09462971…) and `--critic-lr 1e-5`. Update 6 (the first after the reset): EV 0.40 before training on that batch.
  Policy KL to it5s2 rises fast at lr 3e-5 / KL coefficient 0.01: 0.046, 0.060, 0.089, 0.115, 0.129 (updates 2–6;
  r3 reached 0.034 after 20). Collapse rule: stop at KL > 0.5 or eval Δ < −0.05 twice.
- **11:01Z, `NUMPY_MADVISE_HUGEPAGE=0`** (coordinator; THP madvise forces direct compaction: few-MB allocations took
  2–47 s on 01). Exported in `bot/exit/run.sh` (feeders, actors, evals, calibration), `fit_eval.sh`, `gpu_queue.sh`,
  `cpu_feeder.sh` and `bot/detach.sh` (every detached launch); the K4L feeder templates also carry it. Host copies on
  01/04/08 updated. Restarted for it: the RL learner on 08 (PID 1321862, plain `--resume --critic-lr 1e-5`, the state
  already holds the reset critic) and the 01 actors (block 10 stopped via STOP_ACTORS at 11:03Z; **block 11**, 32
  workers, wrapper 3160647). Running fits and evals were left alone.
- **01 ≤ 89 live python.** The new actor pool passed `cpu_room` under the default cap 105 while K4C batches were still
  draining (py 96). Those three batches were stopped by verified PGID (s7017400/7800/8000; sealed shards kept), and
  `cpu_room.sh` now honours a per-host ceiling file `bot-cpu-claims/max-live` (written as **89 on 01**; delete it when
  the LIVE LEAD returns 01's GPU). 01 then had 75 live python.
- **11:26Z, arm (b) fits launched** (lead: 08's GPU idle beside the bursty RL learner). Packs `packed-kl9a-x01/x04/x08`
  = every sealed K4L-R-gs shard (it5s2 behaviour) at 11:26Z: 287,033 + 531,104 + 348,912 = **1,167,049 rows**
  (kcM had 1,271,358), synced to 04 and 08 by `pack_sync.sh`. A detached appender (`<J>/append_kl.sh`) queued
  kcM's exact recipe once all three packs had `.synced` (seeds paired with kcM1–3):

  | name | host / queue | seed | cal cases | eval queue |
  |---|---|---|---|---|
  | kLM1 | 04 gpuq (`BOT_GPU_MAX_GB=20`) | 2026102101 | 490000 | 04 cpuq7 |
  | kLM2 | 08 gpuq2 | 2026102102 | 491000 | 08 cpuq6 |
  | kLM3 | 08 gpuq | 2026102103 | 492000 | 08 cpuq7 |

  - 08 keep-alive `gpu_keepalive.sh gpuq/QUEUE kLM 2` (PID 1491243): up to 2 more kLM seeds when gpuq runs dry.
  - 11:29Z: 08 GPU 98 %, 22 GB (learner 16 GB + kLM3 + kLM2). Next cal block: **493000**.
  - Read: `pooled_delta.py v1,R3a <ce-kLMi>:kLMi,<ce-kcMi>:kcMi …` (teacher effect) and vs `$J8/ce-it5s2` (promotion).
- **12:22Z, BL6 queued** (arm (b) promotion candidate). `packed-kl9b-x01/x04/x08` = K4L shards sealed after kl9a
  (`--exclude packed-kl9a-*`): 119,019 + 253,417 + 198,364 = 570,800 rows, so **1,737,849 K4L rows** in all. BL6 = B6's
  recipe (it2D grown to 6L/1536, lr 2e-4, warmup 150, 6000 steps, ckpts every 1500) with the six K4L packs as `--new`
  at `--new-ratio 0.5` and the 12 it8 packs (it5full, ka6a, ka6b, kc7a × 3 hosts) as `--old`; appended by
  `<J>/append_bl6.sh` once all packs were synced.

  | name | host / queue | seed (= B6 seed) | cal cases | eval |
  |---|---|---|---|---|
  | BL6s1 | 04 gpuq (`BOT_GPU_MAX_GB=20`) | 2026102661 (B6s1) | 493000 | 04 cpuq7 |
  | BL6s2 | 08 gpuq2, after kLM2 | 2026102662 (B6s2) | 494000 | 08 cpuq7 |
  | BL6s3 | 04 gpuq2 (free after B6s7 ended 12:16Z) | 2026102663 (B6s3) | 495000 | 04 cpuq6 |

  Next cal block: **496000**. ETA ≈ 4 h per fit + 45 min eval (≈ 17:00–17:30Z).
- **RL r4 snapshot evals** (our engine, HEADLINE 0–299, deployed τ0 0.5375, Δ paired vs `$J8/ce-it5s2`):

  | snapshot | KL at that version | vs v1 | Δ (v1) | vs R3a | Δ (R3a) | h2h vs it5s2 | plays/game vs v1 |
  |---|---|---|---|---|---|---|---|
  | v10 | 0.27 | 0.880 | −0.003 [−0.047, +0.040] | 0.677 | +0.017 [−0.040, +0.077] | 0.513 | — |
  | v20 | 0.36 | 0.900 | +0.017 [−0.030, +0.060] | 0.690 | +0.030 [−0.030, +0.090] | 0.537 | 36.5 (band 37.8 ± 3: no recal) |
  | v29 (final, KL 0.516) | 0.52 | 0.887 | +0.003 [−0.043, +0.050] | 0.707 | +0.047 [−0.017, +0.110] | 0.556 (n 117, partial) | — |

  - v20 passes the F9 screen. 13:51Z: `f9-rl4v20` (04 cpuq; snapshot copied to `$J4/ckpt-rl4v20/`, sha256
    ae369f23…) and, for the RoyaleSim gate, `rsim-rl4v20` (04 cpuq2; same args as `$J4/rsim-it5s2`).
  - **13:57Z: RL r4 stopped by the collapse rule** (KL 0.516 at v29; 30 updates, ~4.9 k games). v29 queued for eval.
    14:31Z: 01 sync stopped (`STOP_SYNC`), 01 K4L feeder target 44 → 80 (cap 89; PID 4171198, `cpu-feed-k4l.log4`).
  - 13:17Z: `RUN/kl_stop.sh` (08, PID 2247006) applies the collapse rule: at KL > 0.5 it touches STOP_LEARNER and
    STOP_ACTORS and queues the final version for eval. KL was 0.494 at v28 (13:50Z).
- **RL r4 v20 on fresh bank F9 = NEW BEST STUDENT (14:52Z, pre-registered rule).** Our engine, F9 cases 0–599, τ0 0.5375,
  paired per case vs `$J4/f9-it5s2` (it5s2 @0.5375 on the same cases):

  | opponent | v20 | it5s2 | Δ (v20 − it5s2) | plays/game v20 / it5s2 |
  |---|---|---|---|---|
  | v1 | 0.892 | 0.857 | **+0.035 [+0.002, +0.068]** | 35.5 / 37.0 (band 37.8 ± 3: in) |
  | R3a | 0.680 | 0.657 | +0.023 [−0.018, +0.063] | 42.2 / 43.4 |
  | mean of v1 and R3a | | | **+0.029 [+0.003, +0.055]** | |

  RoyaleSim rsim15535 gate (HEADLINE 0–299, paired vs `$J4/rsim-it5s2`): v1 0.860, −0.027 [−0.077, +0.020]; R3a 0.670,
  +0.023 [−0.040, +0.087]; rext-bc 0.910, +0.027 [−0.017, +0.070]; mean of the three **+0.008 [−0.022, +0.038]**, not
  negative. Claim rule met: mean CI above 0, neither opponent below −0.02, RoyaleSim not negative, play count in band.
  - Checkpoint: `/mpac/sdicks02/jobs/clasher/bot-rl-r4/snapshots/policy-00020.pt` (08; copy `$J4/ckpt-rl4v20/`),
    sha256 **ae369f2358bb98fe54726591b1f17149770ad6ad85c4bf7fcb1b0a4ead27aef2**, threshold 0.5375 (RL gate centre; no
    recalibration needed). Serve as `student:<ckpt>@0.5375`.
  - Selection note: v20 was picked from 2 snapshots (v10, v20) on HEADLINE; F9 was never used for selection.
  - Caveat: one RL run; the R3a half alone is not significant, and RoyaleSim vs v1 is −0.027 (CI includes 0).
- **RL r5 (14:54Z, 01): continue from v29** (anchor = v29, so the KL budget restarts; v29's HEADLINE is ≥ v20's and h2h vs
  it5s2 rose 0.513 → 0.537 → 0.556 over v10/v20/v29). RUN `/mpac/sdicks02/jobs/clasher/bot-rl-r5` (01); init
  `bot-rl-r5-init/snapshots/policy-00029.pt` (sha 1f5d651a…), critic `critic-r4-final.pt` (r4's final critic, sha
  22e8a030…), critic lr 1e-5, policy lr 3e-5, KL 0.01, same league; **blocks ≥ 20** on RL_BANK. Learner PID 89766 (01 GPU,
  beside BL6s4); actors block 20, 32 workers (wrapper 91763); `kl_stop.sh` (PID 92732, limit 0.5 vs v29); eval watcher on 08
  `eval_watch.sh 127x01 RUN /mpac/sdicks02/jobs/clasher/bot-rl-r5-eval08 24` (PID 2815807). 01 K4L feeder target 80 → 50
  (PID 89723, `cpu-feed-k4l.log6`). Every r5 snapshot must pass F9 on its own (vs it5s2, and vs v20 for "better than v20").
- **B6 on F9 (16:00Z):** vs it5s2 (paired): B6s1 v1 +0.020 [−0.015, +0.053] / R3a −0.003 [−0.047, +0.040]; B6s2 +0.025
  [−0.010, +0.058] / +0.012 [−0.030, +0.055]; B6s3 0.000 [−0.037, +0.037] / −0.032 [−0.077, +0.013]. **Pooled: v1 +0.015
  [−0.015, +0.045], R3a −0.008 [−0.043, +0.028]**, i.e. level with it5s2 off HEADLINE (on HEADLINE it read −0.016/−0.009,
  consistent with ~0.03 of it5s2 HEADLINE luck). Pooled vs v20 on F9: v1 −0.020 [−0.049, +0.008], R3a −0.031
  [−0.068, +0.006].
- **16:01–16:04Z, GPUs refilled** (BL6s1–3 trained; kLM fillers done; 04/08 GPUs had gone idle):
  - 08: **BL6s5** (gpuq, seed 2026102665, cal 497000, eval cpuq7) and **BL6s6** (gpuq2, 2026102666, cal 498000, eval cpuq6);
    keep-alive `gpu_keepalive.sh gpuq/QUEUE BL6s 1` (PID 3154008). 08 GPU 99 %.
  - 04: **BL6s7** (gpuq, 2026102667, cal 499000, eval cpuq7), keep-alive BL6s 1 (PID 3438336). Next cal block **500000**.
  - **RL r6** (04): an independent second line from **v20** (anchor v20), r4's final critic, same settings, seed 2026101593,
    **blocks ≥ 30**. RUN `/mpac/sdicks02/jobs/clasher/bot-rl-r6` (init copies in `bot-rl-r6-init/`); learner PID 3427060 (04
    GPU), actors block 30, 32 workers (wrapper 3428924), `kl_stop.sh` PID 3431580; eval watcher on 08 `eval_watch.sh 127x04
    RUN /mpac/sdicks02/jobs/clasher/bot-rl-r6-eval08 24` (PID 3160215). 04 K4L feeder target 80 → 45 (PID 3427027,
    `cpu-feed-k4l.log2`).
  - RL r5 (01) at v6 by 16:00Z, KL 0.094 vs v29.
- **17:36Z reads.**
  - RL r5 v10 (= v29 + 10 updates; HEADLINE, 192/300 h2h games): v1 0.887, Δ +0.003 [−0.043, +0.047]; R3a 0.700, Δ +0.040
    [−0.027, +0.105]; **h2h vs it5s2 0.630 [0.562, 0.698]** (v20: 0.537). Passes the screen → `f9-rl5v10` queued in 01
    cpuq6 (snapshot `bot-rl-r5/snapshots/policy-00010.pt`, sha e188e2ae…).
  - RL r5 at v18 (KL 0.25), r6 at v10 (KL 0.15, EV 0.52).
  - BL6s3 (τ 0.5075): v1 0.890, Δ vs it5s2 +0.007 [−0.040, +0.053]; R3a 0.667, +0.007 [−0.057, +0.070]; h2h 0.463.
    BL6s3 − B6s3 (same seed): v1 +0.017 [−0.030, +0.063], R3a +0.040 [−0.020, +0.097]. BL6s2 partial (253 R3a games):
    −0.027 / −0.059.
  - 16:52Z: ev-BL6s2 moved from 08 cpuq7 to 08 cpuq6; ev-kLM3-ka2026102105 stopped (kLM settled).
- **BL6 verdict (18:20Z): null.** HEADLINE 0–299, Δ paired vs `$J8/ce-it5s2` (BL6s1 at 746/900 games):

  | fit | τ | vs v1 | Δ (v1) | vs R3a | Δ (R3a) | h2h |
  |---|---|---|---|---|---|---|
  | BL6s1 | 0.5075 | 0.877 | −0.007 [−0.053, +0.040] | 0.667 | +0.007 [−0.050, +0.067] | 0.500 (n 146) |
  | BL6s2 | — | 0.857 | −0.027 [−0.077, +0.020] | 0.613 | −0.047 [−0.103, +0.010] | 0.450 |
  | BL6s3 | 0.5075 | 0.890 | +0.007 [−0.040, +0.053] | 0.667 | +0.007 [−0.057, +0.070] | 0.463 |
  | BL6s4 | 0.4775 | 0.887 | +0.003 [−0.040, +0.047] | 0.620 | −0.040 [−0.100, +0.020] | 0.473 |

  Pooled s1–s4 vs it5s2: v1 −0.006 [−0.043, +0.033], R3a −0.018 [−0.067, +0.031]. **BL6 − B6 (same seeds, 4 pairs): v1
  +0.007 [−0.019, +0.033], R3a −0.003 [−0.035, +0.030].** K4L labels at ratio 0.5 add nothing to the B6 recipe, so arm (b)
  closes without a candidate (the kcM-recipe gain vs v1 does not carry over). BL6 is on F9-screen level but below v20 and
  adds nothing over B6, so it gets no F9 games.
  - BL6s5/s6 (08), BL6s7 (04) and 01's filler BL6s4-ka2026102665 keep training as GPU fillers; their evals were pre-marked
    done (ev-BL6s5/6/7, ev-BL6s4-ka2026102665) so the CPU goes to RL F9 runs; BL6 keep-alives stopped. A successor can
    re-queue those evals under new names.
  - 18:16Z: 01 K4L feeder target 50 → 20 (PID 1023539, `cpu-feed-k4l.log7`) so F9 runs get room.
- **18:57Z, keep-alives on every GPU queue** (lead: 04's gpuq ran dry after BL6s7 ended 18:21Z; the lead had started a BL6s
  keep-alive there, PID 99089, which appended filler BL6ska185604). Since BL6 is null, the fillers are **BL6f\*** lines
  whose fit_eval writes evals to `<J>/cpuq-parked/QUEUE`, a queue **with no runner**: the GPU stays busy and the
  checkpoints are kept, but no CPU is spent evaluating them (a successor can run those lines by hand). Appended BL6f1 (01
  gpuq), BL6f2/BL6f3 (04 gpuq/gpuq2), BL6f4/BL6f5 (08 gpuq/gpuq2); seeds 2026102691–95. Keep-alives
  `gpu_keepalive.sh <q>/QUEUE BL6f 3` on all five: 01 gpuq 1196124, 04 gpuq 109055, 04 gpuq2 109143, 08 gpuq 4093222,
  08 gpuq2 4093287. The lead's 04 keep-alive (99089) was replaced; its filler's eval (ev-BL6s7-ka2026102668) was pre-skipped.
  18:59Z: 04 GPU 100 % (BL6f3 + BL6ska185604 + RL r6 learner).
- **19:01Z, RL r5 is the strongest line.** HEADLINE 0–299 (Δ paired vs `$J8/ce-it5s2`), τ0 0.5375:

  | snapshot | vs v1 | Δ (v1) | vs R3a | Δ (R3a) | h2h vs it5s2 |
  |---|---|---|---|---|---|
  | r5 v10 | 0.887 | +0.003 [−0.043, +0.047] | 0.700 | +0.040 [−0.027, +0.105] | 0.603 |
  | r5 v20 | 0.910 | +0.027 [−0.017, +0.070] | 0.763 | **+0.103 [+0.040, +0.167]** | 0.563 |
  | r6 v10 (from v20) | 0.890 | +0.007 [−0.037, +0.050] | 0.660 | 0.000 [−0.067, +0.067] | 0.553 |

  - F9 r5 v10 (partial, 929/1200): v1 0.908, Δ vs it5s2 **+0.052 [+0.017, +0.085]** (600); R3a 0.711, +0.049 [−0.009, +0.106]
    (329); vs v20 on F9: +0.017 [−0.015, +0.048] / +0.018 [−0.036, +0.076].
  - Queued 19:01Z: `f9-rl5v20` (04 cpuq) and RoyaleSim gates `rsim-rl5v20` (04 cpuq2) and `rsim-rl5v10` (08 cpuq), with snapshot
    copies `<J>/ckpt-rl5/` (v10 sha e188e2ae…, v20 sha e6f3c4ec…). Feeders lowered for room: 04 45 → 20 (PID 129493,
    `cpu-feed-k4l.log3`), 08 90 → 40 (PID 4115670, `cpu-feed-k4l.log3`).
  - RL r5 at v26 (KL 0.28 vs v29), r6 at v21 (KL 0.28 vs v20).
- **19:27Z, coordinator HOLD on 01** (a lab admin, mpacadmin, logged in ~19:16Z): don't raise 01's load, start nothing new
  there, restart nothing; the lead set `bot-cpu-claims/max-live` on 01 to the current count (54). Done: 01 K4L feeder loop
  stopped (1023539; in-flight batches finish; it does not use cpu_room), 01 BL6f keep-alive stopped (1196124), BL6f1 marked
  done in 01 gpuq (never started). Left running: 01's current GPU filler (BL6s4-ka2026102665), RL r5 learner and actors.
  No pending items in 01's CPU queues. **While the hold lasts, queue new CPU work on 04/08 only.** When it ends: delete
  01 `max-live` (the lead's), restart the 01 feeder/keep-alive if wanted (same args as `cpu-feed-k4l.log7`, keep-alive BL6f 3).
- **RL r5 v10 on F9 = NEW BEST STUDENT, superseding r4 v20 (19:50Z, same pre-registered rule).** Our engine, F9 cases
  0–599, τ0 0.5375, paired per case:

  | comparison | v1 | R3a | mean of v1 and R3a |
  |---|---|---|---|
  | r5 v10 score | 0.908 | 0.723 | |
  | r5 v10 − it5s2 | **+0.052 [+0.017, +0.085]** | **+0.067 [+0.023, +0.110]** | **+0.059 [+0.031, +0.087]** |
  | r5 v10 − r4 v20 | +0.017 [−0.015, +0.048] | +0.043 [−0.002, +0.087] | **+0.030 [+0.002, +0.058]** |

  - Plays per game vs v1 on F9: **34.9** (band 37.8 ± 3 = 34.8–40.8: just inside; it5s2 37.0, v20 35.5). RL lowers the
    play count a little each round; a successor continuing RL should check it and recalibrate on-policy if it leaves the
    band.
  - RoyaleSim rsim15535 gate (HEADLINE 0–299, paired vs `$J4/rsim-it5s2`; R3a at 242/300 at 19:50Z): v1 0.903, +0.017
    [−0.030, +0.060]; R3a 0.711, +0.029 [−0.041, +0.103]; rext-bc 0.897, +0.013 [−0.030, +0.057]; mean of the three
    **+0.025 [−0.008, +0.058]**: not negative.
  - Checkpoint: `/mpac/sdicks02/jobs/clasher/bot-rl-r5/snapshots/policy-00010.pt` (01; copies `<J>/ckpt-rl5/` on 04 and 08),
    sha256 **e188e2aeb9a6828ffbef237aa327e495eb39ca5f8322ae18aa70c63cb81bba19**, threshold 0.5375. Lineage: it5s2 →
    RL r4 (30 updates, stopped at KL 0.516) → v29 → RL r5 (10 updates, anchor v29).
  - Selection: r5 v10 was the only r5 snapshot screened when its F9 run was queued; F9 was not used to choose it.
  - RoyaleSim of r5 v20 (complete): v1 0.887, 0.000 [−0.043, +0.043]; R3a 0.683, +0.037 [−0.023, +0.100]; rext-bc 0.893,
    +0.010 [−0.037, +0.057]; mean +0.016 [−0.013, +0.044]. F9 of r5 v20 still running (04).
- **kLM results (arm (b), K4L vs K4C labels at ~matched size, kcM recipe):**

  | fit | τ | vs v1 | Δ vs it5s2 (v1) | vs R3a | Δ vs it5s2 (R3a) | h2h | Δ vs its kcM twin (v1 / R3a) |
  |---|---|---|---|---|---|---|---|
  | kLM1 | 0.4775 | 0.890 | +0.007 [−0.040, +0.050] | 0.610 | −0.050 [−0.110, +0.013] | 0.437 | |
  | kLM2 | 0.4475 | 0.883 | 0.000 [−0.040, +0.043] | 0.607 | −0.053 [−0.117, +0.013] | 0.454 (n 271) | |
  | kLM3 | 0.4775 | 0.887 | +0.003 [−0.040, +0.047] | 0.620 | −0.040 [−0.103, +0.023] | 0.437 | +0.050 [+0.003, +0.100] / −0.017 [−0.073, +0.037] |

  - **K4L − K4C labels, pooled over the 3 seed pairs: v1 +0.051 [+0.022, +0.081], R3a −0.020 [−0.058, +0.018].** The
    stronger teacher's labels make the student clearly better vs v1, not vs R3a (K4L's rollout opponent net imitates
    v1 and R3a; K4C vs K4S labels were null on both). kLM − it5s2 pooled: v1 +0.003 [−0.031, +0.039], R3a −0.048
    [−0.100, +0.004]; h2h 0.44–0.45; the on-policy calibration lowers τ to 0.45–0.48. So no kLM is a candidate: the
    kcM-recipe refit from it5s2 loses ~0.05 whatever the labels, and K4L labels recover it vs v1 only. BL6 (K4L labels in
    the B6 recipe) is the arm (b) candidate.
- **14:42Z: 01's GPU is back** (lead; the `max-live` ceiling was removed by the lead). 14:43Z: 01 K4L feeder cap 89 → 105
  (target 80; PID 33848, `cpu-feed-k4l.log5`). kl9a/kl9b x04/x08 packs copied to 01 (row counts equal). New 01 gpuq
  runner (PID 38762, `gpuq/runner.log3`) with **BL6s4** (seed 2026102664 = B6s4's, cal 496000, eval 01 cpuq7) and keep-alive
  `gpu_keepalive.sh gpuq/QUEUE BL6s 1` (PID 38836). 14:45:57Z: 01 GPU 99 %. Next cal block: **497000**.
- **ExIt fresh bank F9, pre-registered (12:47:41Z, before any game on it).** BASE **465456850770064** =
  `int.from_bytes(os.urandom(6),'big')<<4`, drawn on 05; checked ≥1e9 away from HEADLINE, TRAIN1, RL_BANK, the FIT
  bank and fresh banks 1–3. Why: K4L round 2 found that reseeded copies of a bot score −0.027/−0.038 vs its own
  HEADLINE 0–299 games, i.e. HEADLINE is lucky by ~0.03 for anything selected on it (it5s2 included).
  - **Reference:** it5s2 @0.5375, our engine, cases 0–599 vs v1 and R3a (1,200 games), `$J4/f9-it5s2`.
  - **Screen** (which candidates get F9 games): pooled-seed HEADLINE Δ vs it5s2 ≥ −0.03 on both v1 and R3a (= level
    with it5s2 after the reseed correction). RL snapshots: the best of v10/v20/… by HEADLINE mean Δ.
  - **Claim (new best student):** on F9 cases 0–599, our engine, τ from the candidate's on-policy calibration,
    paired per case vs `f9-it5s2` and pooled over the candidate's seeds, the mean Δ over v1 and R3a has a 95 %
    bootstrap CI above 0, and neither opponent's Δ is below −0.02. Then RoyaleSim rsim15535 (vs v1, R3a, rext-bc;
    paired vs `$J4/rsim-it5s2`) must not be negative (CI upper bound > 0).
  - Report the play count vs v1 on F9 against the 37.8 ± 3 band.
- **RL r4 v10** (our engine, HEADLINE 0–299, τ0 0.5375, paired vs it5s2; partial h2h): v1 0.880, Δ −0.003
  [−0.047, +0.040]; R3a 0.677, Δ +0.017 [−0.040, +0.077]; h2h vs it5s2 0.520 (198 games). Flat. KL 0.30 at v15.
- 10:02Z: skipped ev-B8s3-ka2026102684 (01 cpuq7; it sat in cpu_room with a 36-process claim ahead of the RL actors;
  a 4th seed of the closed B8 arm).

**it8 leftovers (read as they land; HEADLINE 0–299, Δ paired vs `$J8/ce-it5s2`):**

| student | τ | vs v1 | Δ (v1) | vs R3a | Δ (R3a) | h2h vs it5s2 |
|---|---|---|---|---|---|---|
| B6s4 (6L seed 4) | 0.5075 | 0.863 | −0.020 [−0.067, +0.027] | 0.633 | −0.027 [−0.090, +0.037] | 0.490 |
| B6s5 (6L seed 5) | 0.5075 | 0.857 | −0.027 [−0.073, +0.020] | 0.630 | −0.030 [−0.090, +0.030] | 0.477 |
| B6s6 (6L seed 6) | 0.5375 | 0.880 | −0.003 [−0.053, +0.047] | 0.677 | +0.017 [−0.043, +0.077] | 0.513 |
| B6s7 (6L seed 7) | 0.5375 | 0.853 | −0.030 [−0.077, +0.017] | 0.673 | +0.013 [−0.043, +0.070] | 0.523 |
| B6x (6L, all ~9.5 M labels incl. Kall's older packs) | 0.5375 | 0.883 | 0.000 [−0.047, +0.043] | 0.657 | −0.003 [−0.063, +0.057] | 0.477 |

- B6 pooled over s1–s4: **−0.013 [−0.050, +0.025]** vs v1, **−0.016 [−0.064, +0.033]** vs R3a; over s1–s5:
  **−0.015 [−0.051, +0.021]** / **−0.019 [−0.066, +0.029]** (the BL6 control).
- **B6 pooled over all 7 seeds: −0.016 [−0.051, +0.020] vs v1, −0.009 [−0.055, +0.038] vs R3a**, h2h 0.48–0.52.
  it5s2's HEADLINE games carry ~+0.03 of selection luck (K4L round 2 reseed controls), so the B6 recipe may be level
  with or slightly above it5s2 off HEADLINE. B6 passes the F9 screen and is BL6's control, so B6s1–s3 (the original
  seeds, chosen without looking at results) get F9 games (13:20Z): 08 `cpuq` f9-B6s1 then f9-B6s3, 08 `cpuq2` f9-B6s2,
  out `$J8/f9-<name>`, 36 workers each, τ from each on-policy calibration.
- B6x ties it5s2 (not above on either), so no fresh-bank run: 3 M more (older) labels do not move the B6 recipe.

## Iteration 10: RL continuation (owner: ExIt/RL sub-agent #5, from 2026-10-15T20:32Z; time box ~12 h, to ~08:30Z 10-16)

Takeover after a T3 restart cut off sub-agent #4. **Reference = RL r5 v10** (`bot-rl-r5/snapshots/policy-00010.pt` on 01;
copies `<J>/ckpt-rl5/` on 04/08; sha256 e188e2ae…, τ0 0.5375). Paired reads: `bot/exit/mean_delta.py A_DIR:SUBSTR
B_DIR:SUBSTR [--opps v1,R3a] [--alpha]` (per opponent and the per-case mean over opponents, plus plays/game per side);
it reproduces the 19:50Z F9 numbers for r5 v10 exactly.

<!-- it10-state-begin -->
### Iteration 10: current state (resume here; updated 2026-10-16T01:36:24Z)

Read this block first; the dated log below it has the evidence. Hosts: **01, 03, 04, 08** (never 02/06/07/09–18; 05 light
only). Our work is only under `/mpac/sdicks02/jobs/clasher/bot-*` and `/mpac/sdicks02/repos/clasher-bot*`. Code is `bot/`
in `/mpac/sdicks02/repos/clasher-bot` (identical on 01/04/08; 03 uses `/mpac/sdicks02/repos/clasher-bot-rl03`). `<J>` =
`bot-exit-r1-01` (01), `bot-exit-r1-04` (04), `bot-exit-r1` (08), under `/mpac/sdicks02/jobs/clasher/`. Signal only
verified PIDs/PGIDs (never `pkill -f`); launch via `bot/detach.sh LOG RECEIPT cmd…`; CPU jobs via `bot/exit/cpu_job.sh N
cmd…` (lease; waits under 105 live python, or the host's `bot-cpu-claims/max-live`). Other leads' processes run as our
user too (cards tools, `bot-mb-ab`, `bot.noise`, LIVE `finetune_r3`/compositing): never touch them.

**ALLOCATION (01:34Z 10-16, coordinator; Sam's priority is vision): ALL our GPUs are lent to the LIVE LEAD** — 01 since
22:49Z 10-15, 04 and 08 since **01:34:46Z 10-16** (~12–24 h). **Do not start anything on any GPU.** CPU: ours ≤ **30**
live python on **03, 04, 08** (the LIVE LEAD composites synthetic frames there); 01's CPU is ours up to `max-live` 89
(the LIVE LEAD's ~13 loaders on 01 are counted in it). When GPUs come back: see "Resume" below.

**Best student = RL r5 v10** (LIVE fast tier and cutoff default): `/mpac/sdicks02/jobs/clasher/bot-rl-r5/snapshots/policy-00010.pt`
(01; copies `<J>/ckpt-rl5/policy-00010.pt` on 01/04/08, `bot-rl03/ckpt/` on 03), sha256
`e188e2aeb9a6828ffbef237aa327e495eb39ca5f8322ae18aa70c63cb81bba19`, threshold **0.5375** (`student:<ckpt>@0.5375`).

**Fresh banks and claim rule.**
- F9 BASE `465456850770064`, cases 0–599 vs v1/R3a; refs `$J4/f9-it5s2`, `$J1/f9-rl5v10`. Now only a screen.
- **F10 BASE `1212998755579280`** (pre-registered 847340f2), cases 0–999 vs v1/R3a, reference `$J1/f10-rl5v10` (complete).
  Claim (replaces r5 v10): F10 mean Δ over v1/R3a vs r5 v10 with bootstrap CI above 0 at level 1 − 0.05/k, neither
  opponent below −0.02, RoyaleSim rsim15535 (HEADLINE 0–299 vs v1/R3a/rext-bc, paired vs `$J4/rsim-it5s2`) mean CI upper
  > 0; play count reported only. **k = 2 now:** r5 v30 (not confirmed, −0.004 [−0.024, +0.016]) and the soup below.
- Reads: `.venv/bin/python -B -m bot.exit.mean_delta A_DIR:SUBSTR B_DIR:SUBSTR [--opps v1,R3a] [--alpha .025]` (`=NAME`
  exact). Local copies for reads on 05: `/mpac/sdicks02/jobs/clasher/bot-reads/`.
- A confirmed successor also needs LIVE perfect-sight + sr1u50 numbers: copy 04 cpuq2's `live-rl5v30` line with the new
  checkpoint (harness `/mpac/sdicks02/repos/clasher-bot-liveeval` on 04), pair vs `live-rl5-perc-ours/{rl5,it5s2}`.

**Running now (CPU only):**
- **Soup candidate** `soup-r5-v10-40.pt` = uniform average of r5 v10/v20/v30/v40 (`bot.exit.soup`), sha256 ba809435…,
  @0.5375; HEADLINE mean +0.050 (v1 +0.033, R3a +0.067).
  - `f9-soup-r5`: 08 cpuq (PGID 2525950), 24 workers, out `/mpac/sdicks02/jobs/clasher/bot-rl-soup/f9-soup-r5-v10-40`.
  - `f10-soup-r5`: 01 cpuq6 (runner PGID 2084764), 64 workers, out `$J1/f10-soup-r5` (ckpt `$J1/ckpt-soup/`).
  - `rsim-soup-r5`: 01 cpuq7 (runner PGID 2925089), 12 workers, out `$J1/rsim-soup-r5`.
  - Claim check when done: `mean_delta <f10-soup-r5>:soup <f10-rl5v10>:policy-00010 --alpha 0.025`, plus RoyaleSim vs
    `$J4/rsim-it5s2` (mean CI upper > 0), and report F9 vs r5 v10.
- CPU queue runners still alive (idle unless lines are appended): 01 cpuq6/cpuq7/cpuqka; 04 cpuq 3045524, cpuq2 3192422,
  cpuq6 363971, cpuq7 1222266, cpuqka 3964180; 08 cpuq 2525950, cpuq2 2581995, cpuq6 4115451, cpuq7 792386, cpuqka
  3544192. Keep any new 03/04/08 CPU job ≤ 30 workers in total per host.
- **Stopped (01:34Z):** all GPU queue runners + BL6f keep-alives on 04/08, filler fits, RL r9/r10 learners (SIGTERM;
  state saved after r9 update 5 = v4, r10 update 4 = v3), all r9/r10 actor pools (04, 01, 03) and syncs, kl_stops, all
  K4L feeders (01, 04, 08), eval watchers r4/r5/r9/r10 on 08 (STOP files). No RL run is active.

**Resume when GPUs return** (ask/confirm the allocation first):
1. RL r9 (04 GPU; RUN `/mpac/sdicks02/jobs/clasher/bot-rl-r9`): `rm RUN/STOP_LEARNER RUN/STOP_ACTORS`; `cd
   /mpac/sdicks02/repos/clasher-bot; env BOT_GPU_MAX_GB=16 bot/detach.sh RUN/learner.log2 RUN/learner.receipt2.json nice
   -n 5 /mpac/sdicks02/repos/clasher-bot-gpu/venv/bin/python -B -m bot.rl.learner --run RUN --init /mpac/sdicks02/jobs/clasher/bot-rl-r9-init/policy-00010.pt --resume
   --critic-lr 1e-5 --critic-warmup 1 --lam 1.0 --lr 3e-5 --kl-coef 0.01 --epochs 2 --microbatch 512 --games-per-update
   480 --max-games-per-update 800 --max-lag 2 --kappa 0.1 --temp 0.1 --snapshot-every 5 --seed 2026101599`; `bot/detach.sh
   RUN/kl_stop.log2 RUN/kl_stop.receipt2.json bash RUN/kl_stop.sh RUN 0.5`; actors `env
   BOT_RL_LEAGUE=v1:.15,R3a:.35,it5s2:.30,self:.15,K4C-r16:.05 bot/detach.sh RUN/actor-b63.log RUN/actor-b63.receipt.json
   bash bot/exit/cpu_job.sh 64 bot/exit/run.sh -m bot.rl.actor --run RUN --workers 64 --block 63` (new block each
   launch; r9 used 60–62); 03 pools via `clasher-bot-rl03` + `bot/rl/remote_sync.sh 127x04 RUN`; watcher on 08
   `eval_watch.sh 127x04 RUN /mpac/sdicks02/jobs/clasher/bot-rl-r9-eval08 24` (rm its STOP first).
2. RL r10 (08 GPU, actors on 01; RUN `/mpac/sdicks02/jobs/clasher/bot-rl-r10` on both): same learner command with
   `--init /mpac/sdicks02/jobs/clasher/bot-rl-r10-init/policy-00010.pt --lr 1e-5 --seed 2026101600`; on 01 rm
   `STOP_SYNC`/`STOP_ACTORS`, `remote_sync.sh 127x08 RUN`, actors block ≥ 73 (r10 used 70–72); watcher `eval_watch.sh local
   RUN /mpac/sdicks02/jobs/clasher/bot-rl-r10-eval08 24` on 08.
3. GPU queues: `bot/detach.sh <J>/<q>/runner.logN <J>/<q>/runner.receiptN.json bash bot/exit/gpu_queue.sh <J>/<q>/QUEUE`
   for gpuq/gpuq2 on 04/08 (+01 gpuq) and keep-alives `bash bot/exit/gpu_keepalive.sh <J>/<q>/QUEUE BL6f 3`. Pending
   (killed mid-fit, rerun from scratch): 04 gpuq BL6f2, 04 gpuq2 BL6fka231307, 08 gpuq BL6fka232138, 08 gpuq2
   BL6fka202652r. They are fillers only (BL6 is null; evals go to the runner-less `cpuq-parked`).
4. Feeders (filler K4L labels): `bot/detach.sh <J>/cpu-feed-k4l.logN <J>/cpu-feed-k4l.receiptN.json bash
   bot/exit/cpu_feeder.sh <J>/cpu-feed-k4l <J>/cpu-feed-k4l.tmpl TARGET 100 <block> <block+100000> CAP 400` with blocks
   01 8000000, 04 8100000, 08 8200000 (`next_start` persists). If a feeder exits with "batch S produced no games" after a
   batch was stopped by hand, `touch <J>/cpu-feed-k4l/checked-S` first (01: S = 8004700; 04/08: check the log).
5. 01: when the LIVE LEAD returns its GPU, delete `bot-cpu-claims/max-live` on 01.

**Next steps (CPU-only while GPUs are lent):** read the soup's F9/F10/RoyaleSim as they land and claim per the rule
(k = 2 → `--alpha 0.025`); if it is confirmed, run the LIVE recipe for it and report path/sha/τ. RL resumes only with a GPU
(r9: lr 3e-5, r10: lr 1e-5, both 480–800 games per update from r5 v10; next RL_BANK block 80, next TRAIN1 cal block
511000).
<!-- it10-state-end -->

**State at takeover (20:32Z, read on the hosts):**
- RL r5 (01) stopped by `kl_stop.sh` at 20:29:34Z: KL 0.713 > 0.5 vs v29 at version 42 (0.448 at v41; one-update
  spike). Snapshots v10/v20/v30/v40 and final v42. 01's GPU then held only filler BL6s4-ka2026102665 (PID 1236307).
- RL r6 (04) at v33, KL rising; its in-training deployed plays/game 32.0 (mixed league), i.e. the play count keeps
  falling.
- 01: the lead restored the K4L feeder (target 55, PID 1618247) and the BL6f keep-alive (PID 1618265) ~20:27Z; mpacadmin
  idle 1 h 15 m (login 19:16Z). 04 live python 62, 08 91.
- **r5 v20 on F9 (complete; 599/600 R3a cases):** vs it5s2 v1 +0.058 [+0.025, +0.092], R3a +0.048 [+0.005, +0.091], mean
  **+0.053 [+0.025, +0.081]**; plays/game vs v1 **34.3** (below the 34.8–40.8 band). **v20 − v10 on F9: v1 +0.007
  [−0.022, +0.035], R3a −0.019 [−0.062, +0.022], mean −0.006 [−0.033, +0.020]**: no gain from 10 more updates.
  RoyaleSim v20 mean +0.016 [−0.013, +0.044]; RoyaleSim v10 (complete) v1 +0.017, R3a +0.053, rext-bc +0.013, mean
  +0.028 [−0.001, +0.058].
- HEADLINE (0–299, Δ vs it5s2): r5 v30 v1 0.937 **+0.053 [+0.013, +0.093]**, R3a 0.773 **+0.113 [+0.053, +0.173]**, h2h
  0.580; r6 v20 v1 +0.017 [−0.027, +0.060], R3a +0.060 [−0.003, +0.123], h2h 0.640. HEADLINE's R3a half overstates RL
  snapshots (r5 v20: +0.103 on HEADLINE, +0.048 on F9).

**Fresh bank F10, pre-registered (2026-10-15T20:37:17Z, before any game on it).** BASE **1212998755579280** =
`int.from_bytes(os.urandom(6),'big')<<4`, drawn on 05 (redraw if within 1e10 of any 13–17-digit integer in
`reports/`, `bot/`, `imitation/` on origin/main; min distance 2.8e10). Why: F9 has now been used to compare r4 v20, r5
v10 and r5 v20, so picking "the best of several" on F9 is selection; F10 is for claims of **beating r5 v10**.
- **Reference:** r5 v10 @0.5375, our engine, F10 cases 0–999 vs v1 and R3a (2,000 games), `<J>/f10-rl5v10`.
- **Who gets F10 games** (at most 4 candidates this iteration): an RL snapshot (or seed-pooled student) whose HEADLINE
  0–299 mean Δ vs it5s2 over v1/R3a is ≥ r5 v10's (+0.022), and whose F9 mean Δ vs r5 v10 is ≥ 0 (point estimate).
- **Claim (new best student, replacing r5 v10):** on F10 cases 0–999, paired per case vs `f10-rl5v10`, the mean Δ over
  v1 and R3a has a bootstrap CI above 0 at level 1 − 0.05/k (k = number of candidates given F10 games this iteration,
  counted when the claim is made), neither opponent's Δ is below −0.02, RoyaleSim rsim15535 (HEADLINE 0–299 vs v1, R3a,
  rext-bc) mean Δ vs `rsim-it5s2` has CI upper bound > 0, and plays/game vs v1 on F10 is in 34.8–40.8, or else the
  candidate is also run at an on-policy recalibrated threshold and the claim uses whichever τ was fixed **before** its
  F10 games.

- **20:38–20:40Z launches** (bot-first; the K4L feeders only make filler labels now that arm (b) is closed, so CPU
  moves to RL actors and evals):
  - 01 K4L feeder target 55 → **10**, cap 100 (stopped 1618247; new PID 1675752, `cpu-feed-k4l.log9`).
  - **RL r7** (01) = r5 continued with a fresh KL budget: init/anchor **r5 v40** (`bot-rl-r7-init/policy-00040.pt`, sha
    13f02881…; KL 0.42 vs v29, before v42's 0.71 spike), critic = r5's final critic (`critic-r5-final.pt` from r5
    `learner-state.pt` update 43, sha f023967c…), r5's exact args, seed 2026101597, **blocks ≥ 40**. RUN
    `/mpac/sdicks02/jobs/clasher/bot-rl-r7`; learner PID 1675774 (01 GPU, `BOT_GPU_MAX_GB=16`), actors block 40, **48
    workers** (wrapper 1678162, same `BOT_RL_LEAGUE`), `kl_stop.sh` PID 1678216 (0.5 vs v40). Eval watcher on 08:
    `eval_watch.sh 127x01 RUN /mpac/sdicks02/jobs/clasher/bot-rl-r7-eval08 24` (PID 450255, log `bot-rl-r7-eval08.log`).
  - **F10 reference** `f10-rl5v10` appended to 01 cpuq6 (36 workers; `$J1/ckpt-rl5/policy-00010.pt`, sha e188e2ae…).
  - 08 K4L feeder target 40 → **8**, cap 100 (stopped 4115670; new PID 450237, `cpu-feed-k4l.log4`); `f9-rl5v30`
    appended to 08 cpuq (24 workers; `$J8/ckpt-rl5/policy-00030.pt`, sha 2772e8f9…).
  - Plan for 04: when r6 hits its KL stop, start **RL r8** there from **r5 v10** (independent seed, blocks ≥ 50) on the
    freed actors and GPU.
- **21:17Z reads.** HEADLINE 0–299 (Δ vs it5s2): **r5 v40** v1 0.872 −0.012 [−0.057, +0.035], R3a 0.753 +0.093
  [+0.037, +0.150], h2h 0.557 (mean +0.040, below v30's +0.083); **r6 v30** v1 0.917 +0.033 [−0.007, +0.073], R3a 0.733
  +0.073 [+0.010, +0.137], h2h 0.613. Both pass the F10 HEADLINE screen (≥ +0.022).
  - r7 updates 1–3: KL 0.022/0.037/0.049 vs v40, EV 0.22–0.54, in-training deploy plays 34–37. ~7 min per update while
    01's old K4L batches drain (01 live python 98; `f10-rl5v10` waits in `cpu_room` for 36).
  - r6 at v39: KL 0.377 vs v20, in-training deploy plays **32.0** (falling; check vs v1 on F9).
  - Queued: `rsim-rl5v30` (04 cpuq2, 30 workers, snapshot `$J4/ckpt-rl5/policy-00030.pt` sha 2772e8f9…); `f9-rl6v30` (08
    cpuq2, 24 workers, `$J8/ckpt-rl6/policy-00030.pt` sha 2083facd…). 08 had dropped to 41 live python: K4L feeder
    target 8 → **25** (PID 663854, `cpu-feed-k4l.log5`). `f9-rl5v30` (08) at 641/1200 games.

- **22:02Z: r5 v30 on F9 (complete)** — vs it5s2: v1 0.923, +0.067 [+0.032, +0.100]; R3a 0.759, +0.102 [+0.058, +0.147];
  mean **+0.085 [+0.056, +0.113]**. **vs r5 v10: v1 +0.015 [−0.013, +0.043], R3a +0.036 [−0.008, +0.078], mean +0.025
  [−0.001, +0.052]** → passes the F10 screen (candidate 1). Plays/game vs v1 **33.9** (R3a 37.9): **below the band**, so
  per the F10 rule it also gets an on-policy recalibrated threshold, fixed before its F10 games (counted as a 2nd
  candidate for the Bonferroni k).
  - `f10-rl5v30` (τ0 0.5375) appended to 08 cpuq (24 workers). `cal-rl5v30` appended to 04 cpuq: `bot.exit.calibrate
    --mode rate --target-plays 37.8 --opponents v1` (cal_eval.sh's recipe), TRAIN1 [510000, 510640), on a separate copy
    `$J4/ckpt-rl5v30cal/policy-00030.pt` (sha 2772e8f9…) so the other copies keep τ0. Then `f10-rl5v30cal` at the
    calibrated τ.
  - Partial F9 r6 v30 vs r5 v10 (671/1200): v1 −0.018 [−0.048, +0.012] (600), R3a +0.085 (71). If it ends below v10, r6
    (r4 v20 lineage, KL 0.36–0.43, deploy plays ~31–33) is stopped and 04 gets RL r8 from the best r5 snapshot.
  - r7 at v10 (KL 0.125 vs v40; 21:57Z); 01 live python 95, admin logged out (no mpacadmin processes from ~21:48Z).
    `f10-rl5v10` running (234/2000 at 22:02Z).

- **LIVE handover recipe (22:20Z).** The LIVE LEAD adopted r5 v10 as the live fast tier and cutoff default (their
  sr1u50 check: vs it5s2 R3a +0.032 [−0.032, +0.097], v1 +0.040 [−0.013, +0.093]). A confirmed successor must also come
  with perfect-sight and sr1u50 numbers. Own copy of their harness: `/mpac/sdicks02/repos/clasher-bot-liveeval` on 04
  (`bot/` from origin 0d4a6bd9; `bot/live` identical to `clasher-live-eval5`); run as their `run.sh` does
  (`CLASHER_LIVE_FAST=student:<ckpt>@τ bot.live.headline_wall --candidate LIVE-fast-it5s2,PERC-emp-sr1u50:LIVE-fast-it5s2
  --opponents v1,R3a --games 300`, env pins r1-total). Check: 4/4 games (r5 v10, v1 cases 0–1, both candidates) have
  the same command_sha256 as their `live-rl5-perc-ours/rl5`. Pair vs their `it5s2`/`rl5` dirs (read only).
  `live-rl5v30` appended to 04 cpuq2 (36 workers, out `/mpac/sdicks02/jobs/clasher/bot-liveeval-rl5v30`).

- **22:46Z: r6 v30 on F9 (complete)** — vs it5s2 v1 +0.033 [+0.002, +0.065], R3a +0.098 [+0.055, +0.140], mean +0.066
  [+0.039, +0.092]; **vs r5 v10 mean +0.007 [−0.022, +0.034]** (v1 −0.018, R3a +0.032); vs r5 v30 −0.019 [−0.044,
  +0.007]; 33.6 plays/game vs v1. The r4-v20 lineage is not better than r5's: **RL r6 stopped** at v49 (22:47Z,
  STOP_LEARNER/STOP_ACTORS; kl_stop 3431580 killed; the 08 watcher got STOP).
- **v30 recalibration (cal-rl5v30, rounds 0–2 on the same 128 TRAIN1 cases vs v1):** τ 0.5375 → 34.9 plays, score
  0.898; τ 0.5075 → 36.3, 0.867; τ 0.4775 → 38.9, 0.836. Pushing an RL snapshot into the play band costs win rate on
  common cases. **F10 rule amendment (22:47Z, before any candidate F10 game exists):** for RL snapshots the play band is
  reported, not a gate (RL learns its play rate against the win signal; the band came from ExIt teacher rates); the
  τcal F10 run is dropped, so r5 v30 counts once in k.
- **22:48–22:51Z: 01's GPU to the LIVE LEAD's perception round 3 (coordinator, ~6–8 h).** 01 gpuq keep-alive 1618265
  and runner 38762 stopped; filler BL6fka202652 (trainer 1863670) SIGTERMed and requeued as **BL6fka202652r** in 08
  gpuq2 (paths rewritten, all present on 08). RL r7 learner SIGTERMed (state after update 18). **01 GPU free at
  22:49:16Z** (nvidia-smi: Xorg/gnome-shell only). 01 feeder cap → 89 (PID 2244168, `cpu-feed-k4l.log10`) and
  `bot-cpu-claims/max-live` = **89** on 01 (delete it when the LIVE LEAD returns the GPU); a fresh K4L batch (PGID
  2242643) stopped → 86 live python. **Do not queue anything on 01's GPU.**
  - **RL r7 moved to 08's GPU:** RUN copied to the same path on 08 (rollouts excluded; 01's logs kept as `*.01`),
    learner `--resume` PID 1154334 (same args); actors stay on 01 (48, block 40) with `remote_sync.sh 127x08 RUN` on 01
    (PID 2248018). kl_stop on 08 PID 1155378 (01's 1678216 killed). r7 eval watcher restarted as `local` on 08 (PID
    1155410, log `bot-rl-r7-eval08.log2`); the old watcher's orphaned v10 eval (PGID 450255) was stopped and v10 is
    re-evaluated. Stop r7: `touch RUN/STOP_LEARNER RUN/STOP_ACTORS` on 08 (sync propagates), `RUN/STOP_SYNC` on 01.
  - **RL r8 (04)** = r5 continued from **v30** (the F9-best snapshot), r5's final critic, r5's args, seed 2026101598,
    **blocks ≥ 50**. RUN `/mpac/sdicks02/jobs/clasher/bot-rl-r8`, init `bot-rl-r8-init/` (v30 sha 2772e8f9…, critic
    f023967c…); learner PID 1313254 (04 GPU), actors block 50, 32 workers (wrapper 1314674), kl_stop PID 1314718; eval
    watcher on 08 `eval_watch.sh 127x04 RUN /mpac/sdicks02/jobs/clasher/bot-rl-r8-eval08 24` (PID 1163670).
  - Keep-alives remain on 04 gpuq/gpuq2 (109055/109143) and 08 gpuq/gpuq2 (4093222/4093287).

- **23:03Z: RoyaleSim r5 v30 (complete, HEADLINE 0–299, paired vs `$J4/rsim-it5s2`):** v1 0.887, 0.000 [−0.047, +0.047];
  R3a 0.755, +0.108 [+0.047, +0.170]; rext-bc 0.897, +0.013 [−0.027, +0.053]; **mean +0.041 [+0.009, +0.070]** (gate
  met). vs r5 v10's RoyaleSim: mean +0.013 [−0.014, +0.038]. F10 at 23:03Z: `f10-rl5v10` 1497/2000, `f10-rl5v30`
  842/2000. RL r7 (08 learner) at v19; RL r8's actors wait in 04's `cpu_room` until `live-rl5v30` (36) ends.
  01: ours 86 (49 actors + 37 F10) + the LIVE LEAD's 13 `finetune_r3` loaders.

- **LIVE recipe for r5 v30 (`live-rl5v30`, 04, HEADLINE 0–299; paired vs the LIVE LEAD's `live-rl5-perc-ours/{rl5,it5s2}`,
  read only; `mean_delta.py` now takes `=NAME` for exact candidate names):**

  | comparison | v1 | R3a | mean |
  |---|---|---|---|
  | perfect sight (LIVE-fast), v30 − v10 | +0.050 [+0.007, +0.093] | +0.073 [+0.010, +0.137] | +0.062 [+0.022, +0.101] |
  | sr1u50, v30 − v10 | +0.013 [−0.033, +0.063] | +0.058 [−0.005, +0.122] | +0.036 [−0.005, +0.075] |
  | sr1u50, v30 − it5s2 | +0.053 [0.000, +0.107] | +0.090 [+0.023, +0.153] | +0.072 [+0.030, +0.112] |
  | v30 noise penalty (sr1u50 − perfect) | −0.073 | −0.103 | −0.088 [−0.125, −0.052] |

  v30 scores: perfect v1 0.937 / R3a 0.773 (= its eval_watch HEADLINE numbers exactly), sr1u50 0.863 / 0.670; plays/game
  vs v1 33.8 perfect, 34.4 sr1u50.

- **F10 VERDICT (23:57Z): r5 v30 NOT CONFIRMED; r5 v10 stays the best student.** F10 cases 0–999, our engine, τ0
  0.5375, paired per case vs `f10-rl5v10` (2,000 + 2,000 games, 0 error rows), k = 1:

  | | v1 | R3a | mean |
  |---|---|---|---|
  | r5 v10 score | 0.910 | 0.760 | |
  | r5 v30 score | 0.922 | 0.741 | |
  | v30 − v10 | +0.012 [−0.010, +0.035] | −0.019 [−0.052, +0.013] | **−0.004 [−0.024, +0.016]** |

  Plays/game vs v1: v30 34.4, v10 34.8. So r5 past v10 is level with v10 off the selection banks: HEADLINE said +0.061,
  F9 +0.025 [−0.001, +0.052], F10 −0.004. Pooled F9+F10 (1,600 cases) ≈ +0.007. RL r6 v30 (F9 +0.007) and RL r7
  v10/v20 (= r5 v50/v60; HEADLINE mean +0.026/+0.015 vs r5 v10's +0.022) agree. **Reading:** at 160 games per update,
  lr 3e-5, KL 0.01, the policy random-walks (≈0.04 KL per update) once past r5 v10, with no further gain vs v1/R3a.
- **00:00–00:03Z, new arms (bigger batches against the update noise), both from r5 v10, r5's final critic, KL-stop 0.5
  vs v10, snapshots every 5 updates:**
  - RL r7 and r8 stopped (STOP files; kl_stops 1155378/1314718 killed; 01 `STOP_SYNC`); their 08 watchers got STOP.
  - **RL r9** (04): `--games-per-update 480 --max-games-per-update 800`, **lr 3e-5**, seed 2026101599, **blocks ≥ 60**.
    RUN `/mpac/sdicks02/jobs/clasher/bot-rl-r9`, init `bot-rl-r9-init/` (v10 sha e188e2ae…, critic f023967c…); learner
    PID 1698595 (04 GPU), actors block 60, **64 workers** (wrapper 1700492), kl_stop 1700514; 04 K4L feeder target 8,
    cap 98 (PID 1698573, `cpu-feed-k4l.log5`). Watcher on 08: `eval_watch.sh 127x04 RUN …/bot-rl-r9-eval08 24` (PID
    1677034).
  - **RL r10** (learner 08 GPU, actors 01 CPU): same but **lr 1e-5**, seed 2026101600, **blocks ≥ 70**. RUN
    `/mpac/sdicks02/jobs/clasher/bot-rl-r10` on both hosts; learner PID 1670964 (08), kl_stop 1672991 (08); on 01
    `remote_sync.sh 127x08 RUN` PID 2569158 and actors block 70, **64 workers** (wrapper 2571003). Watcher on 08
    `eval_watch.sh local RUN …/bot-rl-r10-eval08 24` (PID 1677062).
  - **Soup screen:** `/mpac/sdicks02/jobs/clasher/bot-rl-soup/soup-r5-v10-40.pt` = uniform average of r5 v10/v20/v30/v40
    (`bot.exit.soup`; sha256 ba809435…), HEADLINE vs v1/R3a/it5s2 @0.5375 queued as `hl-soup-r5` in 08 cpuq.
  - 08 K4L feeder target 30, cap 96 (PID 1678054, `cpu-feed-k4l.log7`): 08 had dropped to 43 live python.
  - Candidates for F10 from now on are counted in k (r5 v30 was k = 1).

- 00:12Z: r5 v42 (final) HEADLINE: v1 0.897 +0.013 [−0.033, +0.057], R3a 0.703 +0.043 [−0.023, +0.113], h2h 0.587
  (mean +0.028). 01 gpuq's stale `BL6fka202652` marked done there (its copy is 08 gpuq2 `BL6fka202652r`). Resume block
  added at the top of Iteration 10.

- **00:13–00:19Z, 03 added** (bot lead: free after the noise worker). New tree `clasher-bot-rl03` (03's own
  `clasher-bot` is old and was left alone); repro checks bit-identical; extra actor pools for r9 (block 62, 32) and r10
  (block 72, 28) pushing rollouts to their learners via `remote_sync.sh` (see the state block).

- **00:34Z: soup screen (HEADLINE 0–299, @0.5375):** soup(r5 v10/20/30/40) v1 0.917 +0.033 [−0.010, +0.077], R3a 0.727
  +0.067 [+0.007, +0.130], h2h vs it5s2 0.593; mean +0.050 ≥ +0.022 → **`f9-soup-r5`** queued in 08 cpuq (24 workers, out
  `/mpac/sdicks02/jobs/clasher/bot-rl-soup/f9-soup-r5-v10-40`). F10 if F9 mean Δ vs r5 v10 ≥ 0 (would be k = 2).
  - r9/r10 learners take ~800 games per update (856/886 rollouts waiting at 00:23Z), so the first updates take ~20+ min.

- **01:34Z, coordinator: 04's and 08's GPUs to the LIVE LEAD (YOLO perception, ~12–24 h); our CPU ≤ 30 on 03/04/08.**
  Stopped by verified PID/PGID: 04 keep-alives 109055/109143 and gpuq runners 2970964/1662202, filler trainers 1419133/
  1434119 (SIGTERM); 08 keep-alives 4093222/4093287, runners 2503549/1189926, filler trainers 1371794/1379714; RL r9
  learner 1698595 (state after update 5, v4; r9 update 1–5 KL 0.034…) and r10 learner 1670964 (after update 4, v3);
  kl_stops 1700514/1672991; feeders 1698573 (04), 1678054 (08); actor pools 04 PGID 1700492, 01 2571003, 03 2495573/2495594;
  syncs 01 2569158, 03 2483080/2483096; 08 in-flight K4L batches PGIDs 2448613/2506651. **04/08 GPUs free at
  01:34:46Z** (nvidia-smi: no compute processes on either). Ours afterwards: 03 0, 04 0, 08 25 (`f9-soup-r5`).
  - 01's CPU (ours ≤ 89) now runs the soup's claim runs: `f10-soup-r5` (64 workers, started before its F9 read, so
    k = 2) and `rsim-soup-r5` (12 workers). Resume commands for everything are in the state block above.

## Next

1. Results of eval-stD (search plus student D), and H/I calibration followed by evals.
2. J/K: calibrate, then HEADLINE including head-to-head vs D.
3. Take the best student as next-round behavior and proposer (K4S-st@student:best as the teacher).

## Commands

```
cd /mpac/sdicks02/repos/clasher-bot; PY=/mpac/sdicks02/repos/clasher-bot-gpu/venv/bin/python
# generation (CPU)
bot/detach.sh LOG RECEIPT bot/exit/run.sh -m bot.exit.generate --out $J8/gen-it1 \
  --student "student:/mpac/sdicks02/repos/clasher-bot-runtime/r1/R3a.pt@0.5005528330802917" \
  --pool v1,v1,self --games 1500 --start 0 --workers 80 --budget 64 --base 874184153281168
$PY -B -m bot.exit.pack --games $J8/gen-it1/games --out $J8/packed-it1
# training (GPU)
bot/detach.sh LOG RECEIPT nice -n 5 $PY -B -m bot.exit.train --init R/R3a.pt --assets $J8/inputs/assets.npz \
  --new $J8/packed-it1 [--old R1CORPUS --new-ratio 0.5] [--grow-layers 6 --grow-ffn 1536] --steps 800 --out DIR
# on-policy calibration (CPU)
bot/exit/run.sh -m bot.exit.calibrate --ckpt CKPT --out DIR --base 874184153281168 --start S --games 64 --rounds 3 --workers 64
# eval
bot/exit/run.sh -m bot.eval.headline --out DIR --candidate student:CKPT --opponents v1,R3a --games 300 --workers 64
.venv/bin/python -B -m bot.eval.summarize DIR $J8/eval-base --paired R3a,student:CKPT
```
