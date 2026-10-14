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
| [1000000, 1001500) / [1100000, 1101000) | gen-it2 (08 / 04) | 08/04 |
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

## Running (06:14Z; PID = process-group leader from the detach receipt)

| host | job | PID | receipt |
|---|---|---|---|
| 08 | gen-it2: behavior B, teacher K4SP4-b64, pool v1,R3a,self, games [1000000, 1001500), 80 workers | 1626915 | `$J8/gen-it2.receipt.json` |
| 04 | gen-it2: same, games [1100000, 1101000), 56 workers | 2055172 | `$J4/gen-it2.receipt.json` |
| 08 | mirror → 04 | 1178335 | `$J8/mirror.receipt.json` |
| 04 | mirror → 08 | 1801987 | `$J4/mirror.receipt.json` |

Note: `detach.sh` echoes a stale receipt if the receipt file already exists. Always use a fresh receipt name.

## Next

1. Pack gen-it2 on each host. Then train two variants:
   - **C** (08): init R3a, it2 + r1 at 50/50;
   - **D** (04): init B, it2 only.
2. Rate-calibrate both to 37.8 plays/game, then run HEADLINE vs v1 and R3a, paired against R3a.

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
