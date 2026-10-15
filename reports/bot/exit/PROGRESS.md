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
