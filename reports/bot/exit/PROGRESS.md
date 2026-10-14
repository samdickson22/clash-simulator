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

- **The D recipe replicates:** the seeds score 0.827–0.843 vs v1 and 0.580–0.627 vs R3a. D-rep − R3a vs v1 =
  +0.097 [+0.037, +0.157].
- **Every refit or variant since D sits inside D's seed band.** The ExIt student has plateaued at about 0.84 vs
  v1 and 0.60 vs R3a; head-to-head vs D is 0.50–0.55.

**Lead (11:05Z):** K4S-st@student:D is null against K4S-st, paired in both engines. D in RoyaleSim: P1 0.820, vs v1
0.807, vs R3a 0.587, vs K4S-st 0.313. **The student is the fast deployable tier; it does not improve the search.**
Students are judged paired against D.

**K4S-st@student:D** (search with D as proposer and default; `eval-stD` on 04): **0.907 [0.873, 0.937] vs v1, 0.730
[0.680, 0.777] vs R3a**. The lead is running the full P1 rows on 03.

## Running (11:30Z)

| host | what | PID / receipt | content |
|---|---|---|---|
| 08 GPU | queue `$J8/gpuq/QUEUE` (runner 2503549) | lead's keep-alive `$J8/gpuq/keepalive.receipt.json` | it4a ✓ → Drep2 ✓ → **Kall** (grown D, all labels incl. it4, 2,500 steps) → Kseed3 (lead's template) → keep-alive fillers |
| 04 GPU | queue `$J4/gpuq/QUEUE` (runner 2970964) | keep-alive `$J4/gpuq/keepalive.receipt.json` | it4mix ✓ → Drep3 ✓ → **Kseed2** (K recipe, seed 2026101405) |
| 08 CPU | cal+eval queue `$J8/cpuq/QUEUE` (runner 2525950, 30 workers) | | K ✓ → **D-rep** → soup4 (weight average of D, D-rep, Drep2, Drep3) |
| 08 CPU | gen-it4x: D behavior, K4S-st@student:D, [4001500, 4003000), 34 workers | 2581978 | |
| 04 CPU | cal+eval queue `$J4/cpuq/QUEUE` (runner 3045524, 40 workers) | | it4a ✓ → **it4mix** → Drep3 |
| 04 CPU | cal+eval queue `$J4/cpuq2/QUEUE` (runner 3192422, 30 workers) | | **Drep2** → Krsim (student K, RoyaleSim rsim15535, vs v1, R3a, scripted ×2, K4S-st, D; 300 cases) |
| 04 CPU | gen-it4y: same teacher, [4103000, 4104500), 25 workers | 3192462 | |
| 03 CPU | gen-it4s: D behavior, K4S-st, [5000000, 5001500), 12 workers | 3753047 | |
| both | mirrors 08 ↔ 04 | 1178335 / 1801987 | |

Finished: gen-it4 on 08 (569,600 labels) and on 04 (1,500 games).

Queues: `bot/exit/gpu_queue.sh QUEUE` runs `<name> <command>` lines one by one; append lines to queue more work;
done names go to `QUEUE.done`.

04 cap: other users' processes vary; a `bot.fidelity.run` job with 34 processes appeared at 10:29Z. K's
calibration on 04 was killed at once (123 → 96) and moved to 08's CPU queue.

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
