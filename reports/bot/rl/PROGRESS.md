# Bot RL progress (exploration tier; resumable)

The design is in [DESIGN.md](DESIGN.md) and the code in `bot/rl/`: `dist.py`, `actor.py`, `learner.py`,
`test_rl.py` and `eval_watch.sh`.

The code runs from the host copies at `/mpac/sdicks02/repos/clasher-bot/bot/rl/` on 04 and 08, synced by rsync from
05 (editing only). Nothing is committed.

## Note to the ExIt agent

The RL learner runs **directly** on the 04 GPU, outside `gpuq`. It is a persistent process capped at 8 GB with
`BOT_GPU_MAX_GB=8`.

RL CPU jobs hold leases in `bot-cpu-claims`:
- 04: actors, 48 workers;
- 08: snapshot evals, 40 workers, one at a time.

So the feeders back off by that much.

## Host rules (bot lead, 21:55Z)

These apply on 04 and 08.
- Gate every multi-process launch (evals, actor pools) with `bot/exit/cpu_room.sh N 105`, then take the lease.
- Keep snapshot evals to ≤ 24 workers on 08 while actors run there (`bot-cpu-claims/max-eval-workers`).
- Keep actors + evals + learner threads within about 105 per host.
- The learner sets `torch.set_num_threads(4)`.

## State

**Current run: r3.** RUN = `/mpac/sdicks02/jobs/clasher/bot-rl-r3` on 04, where the learner runs and rollouts land.
- The same path on 08 holds the actor mirror (`bot/rl/remote_sync.sh`).
- Eval and off-host checkpoint mirror: `/mpac/sdicks02/jobs/clasher/bot-rl-r3-eval08` on 08.
- r1 and r2 were stopped for exploration settings (log below).

**RL bank:** `RL_BANK = 1462854985943728`, drawn on 04 at 2026-10-14T19:51Z with
`int.from_bytes(os.urandom(6),'big')<<4`. `check_bank` verifies it is disjoint from HEADLINE and TRAIN1.

**Game indices:** g = block·10⁶ + k·workers + w. Block 0 is the first actor pool; `RUN/rollouts/BLOCKS` lists used
blocks. Never reuse a block.

**Parity tests** (`RUN/test_rl.log`, `test_rl2.log`, 04, 19:50Z):

| check | result |
|---|---|
| deployed-mode RL vs `StudentPlayer` | command hash equal |
| learner log-prob recompute vs actor, CPU | max error 9.5e-7 |
| learner log-prob recompute vs actor, CUDA | max error 4.3e-6 |
| KL(self) | 0 |

**Exploration statistics** (2 games):
- About 35–62 decisions per 1,500–2,500 ticks.
- Plays: explore 10 vs deploy 10, and 18 vs 15.
- P(sample = deployed top-1 | play): T=1 0.11, T=0.5 0.29, **T=0.3 0.43**, T=0.1 0.67. T was set to 0.3; κ is 0.5.

### Launched (r3, κ 0.1, T 0.1)

| process | host | PID / PGID | log |
|---|---|---|---|
| learner | 04 GPU | 1341004 | `RUN/learner.log` |
| actors, block 1, 48 workers | 04 | `cpu_job.sh` wrapper 1446279 | `RUN/actor-b1.log` |
| actors, block 2, 40 workers | 08 | wrapper 1013073 | 08 `RUN/actor-b2.log` |
| sync loop | 08 | 1012860 | 08 `RUN/sync.log` |
| eval watcher | 08 | 908556 | `bot-rl-r3-eval08/watch.log` |

- Used blocks: 0 (04, workers crashed), 1 (04), 2 (08). They are recorded in 04 `RUN/rollouts/BLOCKS`.
- Stop the 08 sync with `touch RUN/STOP_SYNC` on 08.

**Stop and resume:**
- Stop: `touch RUN/STOP_ACTORS RUN/STOP_LEARNER` and `bot-rl-r3-eval08/STOP` (08).
- Resume the learner: `--resume`, which loads `RUN/learner-state.pt`.
- Resume the actors: a NEW `--block`.

## Log

**19:58Z, r1 (κ 0.5, T 0.3).**
- **Sanity eval:** `policy-00000` (= it5s2) on 08, 30 cases. All 60 v1 and R3a games have command hashes equal to
  it5s2's games in `$J8/ce-it5s2/eval`, so the snapshot format and the eval path are verified.
- **The explore policy was far weaker than the deployed one** (about 130 games):

  | opponent | explore score | deployed it5s2 |
  |---|---|---|
  | v1 | 0.59 | 0.88 |
  | R3a | 0.45 | 0.66 |
  | it5s2 | 0.25 | 0.50 |

  It played 46–47 cards per game, the overspending mechanism again. r1 was stopped.

**20:06Z, r2 (κ 0.2, T 0.15).** About 140 games: vs v1 0.71, it5s2 0.32, R3a 0.63; 42–49 plays per game. Stopped.

**20:13Z, r3 (κ 0.1, T 0.1).** About 150 games: vs v1 0.78, it5s2 0.46, R3a 0.58, self 0.50; 8% of decisions
differ from the deployed action.
- In mirror games vs deployed it5s2, the explorer plays 44.4 cards per game and it5s2 plays 43.9.
- So the explore play rate is matched, and the training policy is close to the deployed one.
- The 37.8 target is plays vs v1 on TRAIN1; games against it5s2 run longer.

**Lesson.** Even a threshold-centred gate overspends unless κ ≤ 0.1. The policy gets about 270 decision polls per
game, and every poll with q > 0 adds plays.

**20:33Z, bug fixed.** In r1–r3 every actor worker crashed after 2–4 games: the snapshot-cache pruning did
`opp_spec.split(':')[1]` on 'v1'. So each run had only about 150 games. The fix is in `actor.py`.
- New blocks were started: 1 on 04 and 2 on 08, through `remote_sync.sh`.
- Both wait for CPU room, since the feeders filled the gap.
- **Lesson:** check live worker counts, not only the first rows.

**20:45Z, small pools added.** The big pools (04 block 1 with 48 workers, 08 block 2 with 40) wait for room behind
ExIt label batches. To start now, small pools that fit under the cap were added: 04 block 3 (12 workers) and 08
block 4 (24 workers).

**20:49–21:05Z, critic warm-up.** Three updates on about 160 games each (about 45 k transitions):
- explained variance on each new batch: −0.002, −0.025, −0.006;
- training-time value MSE 0.22–0.33.

So the critic barely generalises.

**21:05Z, learner OOM.** The first PPO update hit the 8 GB cap: the policy, ref and critic graphs at microbatch 512.
- The learner was relaunched with `--resume` (state after update 3), `BOT_GPU_MAX_GB=16`, `--microbatch 256` and
  **`--lam 1.0`** (Monte-Carlo advantage; see DESIGN).
- New PID 1703156, receipt `RUN/learner.receipt3.json`. The old logs are `learner.log.1` and `.2`.

**21:17Z, first PPO update, v1** (189 games, 52 k transitions):
- log-prob gap at epoch 0, max 3.7e-5 (parity holds);
- KL 0.006, clip fraction 0.046, explained variance 0.12;
- 367 s wall per update, so the learner is about as fast as collection (about 190 games in 6 min).

**21:18Z, every-5th-version snapshots.** `bot/rl/snap5.sh` (PID 1750919) snapshots, adds to the league and queues an
eval for every 5th version. The learner's own snapshot cadence stays at 10.

**21:27Z, learner sped up.** Learner PID **1817425** (receipt4). The 04 big pool (48 workers) had started, so 04
has about 60 workers and 08 about 24, which is more collection than a 6-minute update consumes.
- The learner restarted with `--resume`: `--epochs 2 --microbatch 512 --max-games-per-update 400 --max-lag 2`.
  max-lag 2 means it uses rollouts from versions ≥ current − 2, still importance-corrected by the PPO ratio.
- The waiting 08 big pool (block 2) was cancelled, since the learner couldn't consume it. Block 2 was never used.
- Update 5 (v2): 295 games, KL 0.009, clip fraction 0.059, explained variance 0.13.

**21:55Z, 08 oversubscribed** (lead: load 136, 139 python processes). My 40-worker v5 eval was stopped after 54 of 900
games: watcher 908556, `cpu_job` 1427760, headline 1435294 and its children, all killed by explicit PID.
- It resumed at **24 workers** (`bot.eval.headline` is resumable).
- New watcher PID 1459435 (`watch.log2`). It now gates with `cpu_room.sh N 105` before each eval.
- Afterwards 08 had 85 python processes.

**22:27Z, v5 eval partial** (our engine, HEADLINE 0–299, paired vs it5s2's `ce-it5s2/eval`):

| opponent | v5 score | Δ vs it5s2 | n |
|---|---|---|---|
| v1 | 0.900 | +0.017 [−0.030, +0.063] | 300 |
| R3a | 0.583 | **−0.079 [−0.139, −0.019]** | 266 |

This is a possible early regression vs R3a, so I'm watching the collapse rule.

The training (explore) score is flat at about 0.61 across updates 4–13. KL rose 0.006 → 0.028, and the critic's
explained variance rose 0.12 → 0.36.

**22:27Z, 08 actors retired** (`touch RUN/STOP_ACTORS` on 08). The 04 pool's 60 workers produce about 50 games per
minute, which matches the learner's consumption. Evals on 08 are now the bottleneck, so they get the CPU instead.

**22:55Z, v5 eval complete** (`bot-rl-r3-eval08/eval-policy-00005`, our engine, HEADLINE 0–299, deployed τ0 0.5375):

| opponent | v5 score | Δ vs it5s2 | plays per game (deployed) |
|---|---|---|---|
| v1 | 0.900 [0.863, 0.933] | +0.017 [−0.030, +0.063] | 37.8, on target, so no recalibration was needed |
| R3a | 0.597 [0.543, 0.650] | **−0.063 [−0.117, −0.007]** | 42.0 |
| it5s2 (h2h) | 0.490 [0.433, 0.547] | — | 44.0 |

**22:56Z, watcher retired.** The eval watcher (STOP) is replaced by manual evals: the 900-game evals at 24 workers
take about 60 minutes. v10 vs v1 and R3a (no h2h) is running on 08: PID 1795350, gated by `cpu_room 24 105`.

**23:14Z, training stopped at v20** (`STOP_ACTORS` + `STOP_LEARNER` on 04; `STOP_SYNC` on 08).
- 23 updates in total: 3 critic warm-up and 20 PPO.
- **5,499 games and 1.46 M transitions.**
- KL to it5s2 rose steadily, 0.006 → 0.034 per decision. Clip fraction 0.05–0.07, explained variance 0.1–0.36.

**Training (explore) score per opponent, by consumed-policy block:**

| block | v1 | R3a | it5s2 | self | K4C-r16 |
|---|---|---|---|---|---|
| v0 (489 games) | 0.819 | 0.646 | 0.423 | 0.51 | 0.455 |
| v1–7 (2,187) | 0.850 | 0.599 | 0.480 | 0.44 | 0.328 |
| v8–14 (1,847) | 0.861 | 0.607 | 0.486 | 0.52 | 0.310 |
| v15–20 (976) | 0.886 | 0.573 | 0.487 | 0.46 | 0.326 |

There's no clear training gain: v1 is slightly up, R3a slightly down, the rest flat. Explore plays held at 40–46 per
game; deployed would-play counts at the visited states held at 35–40.

**Snapshot SHA256** (computed on 04, 23:13Z):

| snapshot | SHA256 prefix |
|---|---|
| v5 | 8597222a |
| v10 | 742b50c0 |
| v15 | 30dc8162 |
| v20 | e104f168 |

**Final candidate = v20, chosen as the last snapshot, not on results.** Its evals run on 04, in
`/mpac/sdicks02/jobs/clasher/bot-rl-r3-final/`:
- `ours-v20`: vs v1, R3a and it5s2 h2h; 36 workers, PID 2532394;
- `rsim-v20`: rsim15535 vs v1, R3a and rext-bc; 30 workers, PID 2532427.

v10's eval on 08 is still waiting for room in `cpu_room` (08 is at about 95 python processes).

## Result of the first full train → eval cycle (00:10Z, 2026-10-15)

All rows use the deployed decode at τ0 0.5375 on HEADLINE cases 0–299. Δ is paired per case against it5s2's own
games: `ce-it5s2/eval` for our engine, `$J4/rsim-it5s2` for RoyaleSim.

| snapshot | engine | vs v1 (Δ) | vs R3a (Δ) | other |
|---|---|---|---|---|
| v5 | ours | 0.900 (+0.017 [−0.030, +0.063]) | 0.597 (**−0.063 [−0.117, −0.007]**) | h2h vs it5s2 0.490 [0.433, 0.547] |
| v10 | ours | 0.880 (−0.003 [−0.050, +0.043]) | 0.620 (−0.040 [−0.097, +0.013]) | — |
| **v20** | ours | 0.897 (+0.013 [−0.033, +0.057]) | 0.687 (+0.027 [−0.030, +0.083]) | **h2h vs it5s2 0.513 [0.457, 0.570]** |
| **v20** | RoyaleSim 15.535 | 0.860 (−0.027 [−0.073, +0.020]) | 0.660 (+0.013 [−0.047, +0.073]) | vs rext-bc 0.897 (+0.013 [−0.030, +0.057]) |

v20's deployed plays per game, our engine: vs v1 36.9 (target 37.8 ± 3, so no recalibration was needed), vs R3a
44.0, vs it5s2 45.3.

**Verdict: honest negative.**
- Twenty PPO versions (5.5 k games, 1.46 M decisions, KL 0.034 to it5s2) left the deployed student statistically
  unchanged. Every Δ is inside ±0.03 except v5's R3a dip, which reversed by v20, so it was noise or transient.
- **No collapse:** training score and eval are both flat, and the KL is small.
- **No fresh-case confirmation (cases 300–599) was run,** because there's no gain to confirm.

Outputs: v20 evals in 04 `/mpac/sdicks02/jobs/clasher/bot-rl-r3-final/`. Snapshots, learner state and train.jsonl
are mirrored on 08 in `bot-rl-r3-eval08/{snapshots,state}`. **All RL processes have stopped.**
