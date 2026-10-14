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

(Filled at the end; see PROGRESS-2.md.)

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

(Table filled at the end.)
