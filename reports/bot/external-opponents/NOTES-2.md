# External opponents, round 2: rext-bc and rext-bcppo (human clone, then PPO)

Exploration tier, 2026-10-14, by the BOT LEAD's implementation sub-agent. Nothing is committed. Tools used: RoyaleGym-org
packages only (MIT): royalegym 0.1.24, royalelearn 0.5.18, royaleimitate 0.2.13, royalesim 0.1.34. No ClashAI code,
data or checkpoints were used. Run log: PROGRESS-2.md.

## 1. Data and license: IL_Replay, internal evaluation only

- **Source:** Hugging Face `VanguardX101/IL_Replay`, revision `059d43a0…`: 252,238 anonymised ladder replays.
  - It is the corpus RoyaleImitate's own cloning guide uses, and the one our v1 human prior was trained from.
  - Local copy: `03:/mpac/sdicks02/repos/clasher-local-data/il_replay`.
- **License:** none stated, no restrictions stated, no source stated (IL_REPLAY-LICENSE.md).
- **Coordinator ruling (binding): internal evaluation only.**
  - The data, the shards derived from it, and the rext-bc/rext-bcppo weights are never committed or published.
  - They live only under `/mpac/sdicks02/jobs/clasher/bot-ext2-*/` on the fleet:
    - `bot-ext2-data`: the replay copy on 04, the shards and the logs;
    - `bot-ext2-models`: the clone, plus the PPO bot once installed;
    - `bot-ext2-train`: the PPO runs.
  - The Players load weights from `/mpac/sdicks02/jobs/clasher/bot-ext2-models/<name>`, never from the repo.
  - **Any score below for rext-bc/rext-bcppo comes from opponents derived from IL_Replay (license unstated) and is
    for internal evaluation only.**

## 2. Conversion: none of the format; a replay in our environment

**Format.** RoyaleImitate reads IL_Replay's own `replays/*.parquet` (`payload_json`), which is what the local copy holds,
so no format conversion was needed. Its replay rules are used unchanged (`royaleimitate.replays.match_plan`), in
`bot/players/rext_imitate_replays.py`:
- deck card keys lose form suffixes and map through `replay_cards.json`;
- each deck is dealt unshuffled, in an order that explains every play;
- a play at tick t is made at the first decision at or after t;
- both seats get a decision every 500 ms;
- the label is the human's card and tile, or the no-op.

**Environment.** The replay runs in **our training environment** (`rext_envs.build_env`), so the shards carry the PPO
run's engine key (`090cad9bbbea1acc`): level 11, 15.535.29 arms, RoyaleSim engine delay 27/27, and the default
`SpatialObsBuilder`/`TileActionParser`.

**Three additions:**
1. **Refused plays wait.** Under a 27-tick engine delay, a human's quick second play is often refused at its decision:
   its card is not yet back in hand, or its slot or elixir is still held by the waiting command. Stock RoyaleImitate
   then skips the whole match, and it kept only about 18% of attempted matches (test, 50 matches). Here a refused
   play waits at the head of its seat's queue for up to 6 decisions (3 s), labelled no-op meanwhile. That keeps 86%,
   and in the full run 6.3% of plays waited. Shifting plays 27 ticks earlier was worse and was not used.
2. **Card scope (C56).** Only the rows of a seat whose whole deck lies in our C56 catalogue are kept (`--scope
   c56any`; the opponent's deck is unrestricted).
   - In the first 10k matches, 2.8% have both decks in C56 and 25.6% have one.
   - X4S decks appear exactly in 6.7% of seats: bridge, bait and siege, but not beatdown.
3. **No-op subsampling.** Each no-op row is kept with p = 0.25 and weight 4; every play row is kept with weight 1. The
   weighted cross-entropy is unbiased for the full one, with about 3x fewer rows.

**Output.** 48 workers on 04 (parquet parts split into two disjoint batches) replayed 19,200 matches in 5 min.
- Rows: 2,894,949 in all, of which 140,800 are validation (RoyaleImitate's by-battle split): 820,412 plays and
  2,074,537 kept no-ops.
- Skips: 42,502 out of scope, 8,916 card not in catalogue, 639 not an 8-card deck, 2,808 refused after waiting.

## 3. BC (rext-bc): `royaleimitate.clone`, default model and observation

**Network.** RoyaleLearn's default actor (32 channels x 2 blocks), the same as rext-rlppo r4 and the PPO run
(`rext_imitate_ppo.make_learner`). It sees the default fair `SpatialObsBuilder`.

**Training.** `clone()` itself: masked cross-entropy, row-weighted, AdamW (wd 0.01), cosine schedule, early stopping
on validation. Non-default settings:
- batch 1024 instead of 256;
- lr 5e-4;
- 12 epochs, patience 2;
- packed rows cached in memory (41.5 GB).

Run on the 04 GPU in 76 min; epoch 1 was 20 min, because it packs the rows, and later epochs took 3–5 min.

**Validation NLL curve:**

| epoch | 1 | 2 | 3 | 4 | 5 | 7 | 8 | 9 | 10 | 11 | 12 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| NLL | 0.7057 | 0.6732 | 0.6678 | 0.6728 | 0.6522 | 0.6477 | 0.6434 | 0.6398 | 0.6372 | 0.6366 | **0.6356** |

The best epoch was the last one.

**Artifact.** Folder `bot-ext2-models/bc-r1`, digest `29876dfe60518ae2…`, installed as `bot-ext2-models/bc` on 03, 04 and
08 (actor sha256 `385af5123b631c81…`).

## 4. PPO fine-tune (rext-bcppo): `bot/players/rext_imitate_ppo.py`

**Config.** RoyaleLearn `Learner(opponent="self")`, the same as rext-rlppo r4:
- 32ch x 2 network; 65,536 steps per update; batch 2048 x 3 epochs; lr 5e-4; the default entropy schedule;
- league: mirror battles, own snapshots, and all six RoyaleGym scripted rungs;
- gate every 4M env steps, 200 games;
- 22 rollout workers x 32 battles, 8 eval workers;
- the environment is the clone's: X4S decks, level 11, 15.535.29, delay 27/27.

**RoyaleImitate sections:**
- `warm_start.init` = bc-r1, digest-checked, with a probe self-test;
- `actor_lr_scale` 0 for the first 1M env steps (critic warm-up), then 1;
- `imitation`: a `reference_kl` regulariser, KL(clone ‖ policy), with RoyaleImitate's default budget of 0.1 nats per
  choice row and an adaptive coefficient starting at 1.0.

**Three precision settings,** each needed because a cloned actor is far more peaked than a seeded one:
- `net.policy_head_float32` on, and TF32 off. bcppo-r1 and r2 died at update 5 on RoyaleLearn's ratio invariant:
  deviation 0.0056 and 0.0059 against the TF32 tolerance of 0.005;
- `self_test_atol` 1e-4, because the clone's probe rows were recorded under TF32 and reproduce to 2.8e-5 (bcppo-r3).
- Both net fields are actor-neutral, so the clone still loads.

**Run.** bcppo-r4 on the 08 GPU, sharing it with ExIt: 10:53–13:18Z (2h24), 24.1M decisions (16.1M env steps),
2.8k steps/s. It was stopped by SIGINT and saved.
- **Artifact:** run dir `08:/mpac/sdicks02/jobs/clasher/bot-ext2-train/bcppo-r4`, with a mirror in
  `04:…/bot-ext2-train/mirror-127x08/`.
- **Installed as:** `bot-ext2-models/bcppo` on 03, 04 and 08 (actor sha256 `5e1bef59bc9cab87…`).
- **Curves** (`metrics.jsonl`):
  - KL(clone) went 0 -> 0.08 at unfreeze, then about 0.13–0.14, inside the coefficient's band, with λ settled at 0.088;
  - PPO KL 0.03 -> 0.007, and the lr backed off to 1e-4;
  - normalised entropy 0.16–0.21, no-op rate 0.90 (the clone's), explained variance about 0.9;
  - ladder Elo readout 1200 -> about 1500.
- **RoyaleLearn's own gates:** snap:v1 and v2 scored 0.52 and 0.525 vs the clone v0 (n=200 each); neither was
  promoted.
- **Ladder, checkpoints at 40/rung:** mean5 0.79 at 6.1M env steps and 0.82 at 10.2M (noisy at n=40).

## 5. Players

`make_player('rext-bc')` and `make_player('rext-bcppo')` (a `-greedy` suffix also works) give `RextPolicyPlayer` on
`/mpac/sdicks02/jobs/clasher/bot-ext2-models/{bc,bcppo}`; the env var `REXT_EXT2_MODELS` overrides the directory.
- **Wrapper:** the same as rext-rlppo (`bot/players/rext_policy.py`).
  - It loads the clone folder (`policy.json` + `actor.safetensors`) with RoyaleLearn's own loader.
  - The observation is RoyaleGym's default builder on our live RoyaleSim battle.
  - Enemy underground and invisible units are removed (our fair-information rule).
  - Its commands go through our `CommandQueue(27, 1)`.
- **Information audit:** as NOTES.md section 3. Nothing new is read: the clone's observation and action space are
  rext-rlppo's.
- **Train/serve difference, as rext-rlppo:**
  - the engine delay at training time is 27/27 with several commands in flight; our loop has one outstanding command;
  - the `own_hand_pending` and `own_pending_cost` fields are therefore 0 in our loop.
- **Smoke:** v1 vs rext-bc, 4 games. rext-bc played 25–31 cards a game; all were accepted, with 0 errors.

## 6. Evaluation

**Data disclosure:** rext-bc and rext-bcppo are trained from IL_Replay (license unstated); internal evaluation only.

**A. vs RoyaleGym's scripted ladder.** `royalegym.evaluate`, the training env, sampled policy, 100 games per rung, half
per seat:

| model | noop | random | first-aff. | defend | push | patient | mean5 |
|---|---:|---:|---:|---:|---:|---:|---:|
| rext-rlppo (round 1, from scratch) | 1.00 | 0.61 | 0.56 | 0.50 | 0.59 | 0.62 | 0.576 |
| **rext-bc** | 0.995 | 0.85 | 0.76 | 0.80 | 0.72 | 0.69 | **0.764** |
| **rext-bcppo** | 1.00 | 0.83 | 0.79 | 0.74 | 0.72 | 0.72 | **0.760** |

**B. Head to head in RoyaleGym's env.** The same evaluate call:

| matchup | games | wins–losses | score |
|---|---:|---|---:|
| rext-bc vs rext-rlppo | 200 | 152–48 | 0.76 |
| rext-bcppo vs rext-rlppo | 200 | 139–61 | 0.695 |
| rext-bcppo vs rext-bc | 400 | 206–194 | 0.515 (too close to call) |

**C. Our harness.** HEADLINE bank (cases 0–299, BASE 1455777415631152), `--engine rsim15535`, our match loop
(CommandQueue 27/1), 300 games each, 95% bootstrap CI, 0 errors:

| candidate | opponent | score [95% CI] | W-D-L |
|---|---|---|---|
| K4S-st | rext-rlppo | 1.000 [1.000, 1.000] | 300-0-0 |
| K4S-st | **rext-bc** | **0.833 [0.790, 0.877]** | 250-0-50 |
| K4S-st | **rext-bcppo** | 0.933 [0.903, 0.960] | 280-0-20 |
| v1 | rext-rlppo | 0.727 [0.673, 0.777] | 218-0-82 |
| v1 | rext-bc | 0.583 [0.527, 0.640] | 175-0-125 |
| v1 | rext-bcppo | 0.480 [0.423, 0.537] | 144-0-156 |

Paired on the same cases, moving from rext-bc to rext-bcppo:
- K4S-st: **+0.100 [+0.053, +0.143]**;
- v1: **−0.103 [−0.167, −0.040]**.

**Read:**
- **The clone is the real external opponent.** rext-bc is the first non-Clasher policy K4S-st does not saturate. For
  comparison, K4S-st scores 0.833 vs rext-bc, about 0.99 vs the RoyaleGym scripted bots, 0.89 vs v1 and 0.72 vs R3a.
  It sits a little below our v1 human prior (v1 scores 0.583 vs it), from the same corpus with a different
  architecture and observation.
- **PPO is non-transitive, not uniformly stronger:**
  - rext-bcppo ties v1 (0.48) and is level with the clone in RoyaleGym's env (0.515);
  - but K4S-st beats it more easily than the clone (0.933 vs 0.833).
  - So in 2.4 h it moved towards beating policy-like play and became more exploitable by search.
  - One plausible part of that is the train/serve lag difference (several engine-queued commands in training vs one
    outstanding command in our loop). It was not tested.
- **What to add to the pool:** rext-bc is the external member with signal for K4S-st. rext-bcppo is worth keeping
  too, as a diverse member that v1 cannot beat.
- **Untried:** a looser or no KL anchor, a longer PPO run, and a bigger BC network.

**Results paths:**
- headline runs: `04:/mpac/sdicks02/jobs/clasher/bot-ext2-eval/hl-*` (the bc and rlppo ones also on 03);
- ladder and head-to-head JSONs: `04:` and `08:/mpac/sdicks02/jobs/clasher/bot-ext2-eval/results/`.

## Files (code only; no data or weights in the repo)

| File | What |
|---|---|
| `bot/players/rext_imitate_replays.py` | IL_Replay -> RoyaleImitate shards in our env: stats, replay with retry and scope, merge |
| `bot/players/rext_imitate_clone.py` | `royaleimitate.clone` launcher |
| `bot/players/rext_imitate_ppo.py` | PPO from the clone (warm start, freeze, reference-KL anchor); `make_learner` is shared by both |
| `bot/players/rext_imitate_h2h.py` | head to head of two RoyaleLearn policies (`royalegym.evaluate`) |
| `bot/eval/headline.py` | make_player: `rext-bc*`/`rext-bcppo*` -> `/mpac/sdicks02/jobs/clasher/bot-ext2-models/<name>` |
