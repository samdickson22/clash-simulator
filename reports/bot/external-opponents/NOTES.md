# External opponents (rext-*) for the headline pool

Exploration tier, 2026-10-14, by the bot-lead implementation sub-agent. Nothing is committed. Only RoyaleGym-org
packages (MIT) were used: royalegym 0.1.24, royalelearn 0.5.18, royalesim 0.1.34 and royaleimitate 0.2.13. No
ClashAI code, data or checkpoints were looked at or used.

## 1. What the RoyaleGym ecosystem ships (survey)

| Looked at | Found |
|---|---|
| Wheels: royalegym, royalelearn, royaleimitate, royaleviser (file lists) | No weights, checkpoints or policy files. Only code and json tables (cards, replay card map). |
| GitHub org `RoyaleGym` (API): RoyaleSim (license NOASSERTION in the API; PyPI says MIT), RoyaleGym, RoyaleLearn, RoyaleViser, RoyaleImitate, RoyaleBot (MIT), .github | Release assets are wheels only (RoyaleGym v0.1.15–0.1.24, RoyaleSim). RoyaleLearn, RoyaleImitate and RoyaleViser have no releases. RoyaleBot v0.1.0/0.1.1 ship `rb-build.exe`, a Nulls Royale client that plays *your* bot; it holds no policy. |
| HuggingFace (`author=RoyaleGym`, search royalegym/royalelearn) | No models. The only related artifact is the dataset `VanguardX101/IL_Replay` (human replays used by RoyaleImitate's cloning guide). It is not RoyaleGym-org, its license is unchecked, and it was not used. |
| Docs (royalegym.github.io, the docs/ tree in the clone) | No pretrained or baseline bot is downloadable. The FAQ: "We show our own bots' ladder results as a benchmark … ask in the Discord for a 1v1". |
| Documented baselines | RoyaleGym's scripted ladder `royalegym.ladder()`: noop, random (RandomLegalOpponent 0.7), first-affordable, defend, push, patient(ready=3). These are already in the pool as `rgym-*` (bot/players/royalesim_opponents.py). |

So the only new external opponent is one we train with their trainer: **rext-rlppo** (section 2).

## 2. What was trained (RoyaleLearn's own trainer)

**Environment** (`rext_envs.build_env`): RoyaleGym's quickstart env with our match conditions.
- Decks: the five X4S human decks, both seats drawn independently each battle (all 25 pairings), engine-shuffled.
- Card and tower level 11 (King 4824, Princess 3052, checked).
- Rules: `client_arms('15.535.29')`.
- **Command delay: RoyaleSim's own symmetric 27/27 ticks.**
- RoyaleGym defaults otherwise:
  - observation: `SpatialObsBuilder`, the fair default with no Reveal;
  - actions: `TileActionParser`, 2305 actions;
  - one decision every 500 ms;
  - reward: win/loss 1.0 + crowns 0.2 + tower HP 0.1.

**Trainer** (`rext_train.py`): `royalelearn.Learner(opponent="self")`, PPO with the ladder. The league mixes mirror
battles (0.50), past-self snapshots from its pool (0.35) and scripted bots (0.15). Rollouts use RoyaleLearn's process
farm instead of the Learner's inline single process. The venv is
`/mpac/sdicks02/repos/clasher-bot-rsim/learnvenv` on 08 and 04: py3.12, torch 2.7.1+cu118 (driver 470), A6000.

| run | host | net | Adam steps / update (batch x epochs) | lr | entropy | league | outcome |
|---|---|---|---|---|---|---|---|
| r1 | 08 | 64ch x 4 | 2 (batch = steps_per_update, the quickstart's advice) | 2e-4 | 0.01 | default | stopped at 0.87M steps: kl about 1e-6, policy uniform (RoyaleLearn `kl_dead` alarm) |
| r2 | 08 | 64ch x 4 | 16 (4096 x 2), 32768 steps/update | 2e-4 | 0.01 | default (scripted share = noop + random only; 1000-game gate every 1M env steps on 2 eval workers) | stopped at 2.99M steps: over 50% of wall time inside gates |
| r3 | 04 | 32ch x 2 | 96 (2048 x 3), 65536 steps/update | 5e-4 | default schedule | default | **crashed** at about 4.5M steps: upstream bug (below) |
| **r4** | 04 | 32ch x 2 | 96 (2048 x 3), 65536 steps/update | 5e-4 | default schedule (0.01 -> 0.003) | **all six RoyaleGym scripted rungs**; gate every 4M env steps, 200 games, 10 eval workers | **48.6M decisions (32.4M env steps), 3h11 wall (05:42–08:53Z), 4300/s mean -> rext-rlppo** |
| r5 | 08 | 64ch x 4 | 48 (4096 x 3), 65536 steps/update | 3e-4 | default schedule | as r4, 12 eval workers | 20.3M decisions (13.6M env steps), 3h08 wall, 1800/s mean (update 28–55 s/iteration, GPU shared with ExIt) -> rext-rlppo-r5 |

**Two RoyaleLearn 0.5.18 issues found:**
- **Bug:** evaluation workers read `snapshots/index.json` once, at start. A gate against a snapshot admitted later then
  raises `KeyError("no snapshot 'snap:vN'")` and kills the run (r3). Workaround in `rext_envs._patch_snapshot_index`:
  on a miss, re-read the index and retry. Every worker imports the env module. It held through r4's eight gates.
- **Learner defaults:**
  - `opponent="self"` gates every 1M env steps, where the ladder default is 4M.
  - The gate is 1000 games on 2 eval workers, about 22 min per gate on these hosts.
  - The scripted share is noop + random only.

**Training curves.** Per-iteration metrics are in `<run>/metrics.jsonl`; gate records are in `<run>/ladder/gates/`.
- **r4:**
  - normalised entropy 1.0 -> 0.82;
  - hold (no-op) rate 0.4% -> 12% (it learns to wait);
  - ladder Elo readout 1169 -> 1380 at the end, peak about 1470.
  - Champion `snap:v3` (at 16M env steps) beat v0 at 0.59 (n=200). The later candidates v4–v7 did not beat v3 (0.47–0.51):
    against its own champion it plateaued after about 16M env steps.
- **r5:**
  - entropy 0.86, hold rate 12%, Elo 1367;
  - no promotion beyond v0 (0.55 and 0.545).

**Eval vs RoyaleGym's scripted ladder** (`royalegym.evaluate`, the training env, half the games per seat, same seeds both
ways, sampled policy; 40 games per rung, the final rows 100). "mean5" is the mean score over the five non-noop rungs.

| model | env steps | noop | random | first-aff. | defend | push | patient | mean5 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| r2 snap:v1 | ~1M | 1.00 | 0.43 | 0.53 | 0.33 | 0.50 | 0.40 | 0.435 |
| r3 snap:v2 | ~3M | 1.00 | 0.38 | 0.55 | 0.50 | 0.50 | 0.43 | 0.470 |
| r4 ckpt | 10.2M | 1.00 | 0.55 | 0.55 | 0.45 | 0.65 | 0.43 | 0.525 |
| r4 ckpt | 18.3M | 1.00 | 0.68 | 0.63 | 0.48 | 0.63 | 0.60 | 0.600 |
| r4 ckpt | 24.4M | 1.00 | 0.60 | 0.60 | 0.55 | 0.63 | 0.63 | 0.600 |
| r4 ckpt | 30.5M | 1.00 | 0.63 | 0.63 | 0.48 | 0.65 | 0.68 | 0.610 |
| **r4 final (n=100/rung)** | 32.4M | 1.00 | 0.61 | 0.56 | 0.50 | 0.59 | 0.62 | **0.576** |
| r5 ckpt | 4.1M | 1.00 | 0.48 | 0.48 | 0.25 | 0.43 | 0.45 | 0.415 |
| r5 ckpt | 8.1M | 1.00 | 0.50 | 0.49 | 0.45 | 0.65 | 0.53 | 0.522 |
| r5 ckpt | 12.2M | 1.00 | 0.60 | 0.58 | 0.40 | 0.58 | 0.65 | 0.560 |
| r5 final (n=100/rung) | 13.6M | 1.00 | 0.59 | 0.53 | 0.52 | 0.55 | 0.52 | 0.542 |

**Head to head:** r4 beat r5 110–90 (200 games, 0.55), so r4 is `rext-rlppo` and r5 is kept as `rext-rlppo-r5`.

**Honest read.** From scratch, in about 3 h, RoyaleLearn's PPO reaches roughly 0.55–0.6 against RoyaleGym's scripted
bots. That is a weak opponent: its own docs say "from nothing it seldom gets much further", and that a strong bot starts
from a clone of human replays (RoyaleImitate + the IL_Replay dataset, not used: see section 1). Expect K4S-b64 to beat it
about as easily as it beats the scripted pool. Its value is diversity: a learned, non-Clasher policy and observation.

**Models:**
- Installed in `/mpac/sdicks02/repos/clasher-bot-rsim/rext-models/{rlppo,rlppo-r5}/` on 03 and 04 (Learner.save folders:
  `policy.json` + `actor.safetensors`).
  - rlppo = r4, actor sha256 `9cca3773ba84ca9f0e21180b8600dd36afe1350dd89b6219c6d2b7e46b9c2488`;
  - rlppo-r5 = r5, `df48912d86d5a744938ad1696633190e544fe0a08f5cf57b03b6d2fc128d6cdd`.
- Run dirs (checkpoints, snapshots, metrics) are at `/mpac/sdicks02/jobs/clasher/bot-ext-train/rlppo-r*` on their hosts.
  Off-host copies are in `bot-ext-train/mirror-127x04/` on 08, `mirror-127x08/` on 04, and
  `/mpac/sdicks02/jobs/clasher/bot-ext-eval/runs/` on 03, made by `mirror.sh` in this directory.
- Eval results are in `03:/mpac/sdicks02/jobs/clasher/bot-ext-eval/results/`.

## 3. The Player: `rext-<model>[-greedy]` (bot/players/rext_policy.py)

**Registration.** `make_player('rext-rlppo')` returns `RextPolicyPlayer(MODELS/rlppo)`. A `-greedy` suffix gives argmax;
the default samples, as it trained. It is RoyaleSim 15.535 only (`--engine rsim15535`), like `rgym-*`.

**How it acts.**
- RoyaleLearn's own loader builds the actor: `build_actor` + weights, `EvalActors.policy` for the decode, CPU, 1 thread.
- RoyaleGym's own code builds the observation and mask from **our** match battle: a `RustEngine` whose battle is the
  match's `royalesim.Battle` (same compiled class), `SpatialObsBuilder`, and the `TileActionParser` mask.
- `SlotRemapBattle` rewrites one thing, the red tower order in `state_json`. Our battle uses slot_of_k
  `[[0,1,2],[0,1,2]]`; RoyaleGym derives `[[0,1,2],[0,2,1]]`. Nothing else in the core depends on it.
- It decides every 10 ticks when its channel is free. Its tile action becomes our action id (an exact round trip is
  asserted) and goes through our `CommandQueue(27, 1)`.
- Its RNG seed is the match seed + 271828 + seat, so games are deterministic.

**Verified.** `rext_check.py` played 5 full games with random legal plays, both engines. At all 1846 checks (every 10
ticks) both seats saw an identical BattleState, mask and observation, and the final `state_hash` values were equal.
In-match: 0 illegal actions, 0 frame mismatches, and every deploy was accepted by RoyaleSim.

**Information audit.** The default observation is fair by RoyaleGym's design: board, own hand and cycle, clock, and a
counted enemy elixir. Specifics:
- **Enemy underground or invisible units:** RoyaleGym's default builder would show them (a tunnelling Miner is in our
  chip deck). The player **removes** them before building, per our fair-information rule. This differs from training,
  where they were visible.
- **Enemy plays:** `MatchMemory` notices a play when the enemy's hand slot changes between observations. RoyaleSim's
  delay is 0 in our loop, so that is the execution tick, when the card appears: a public event.
- **Enemy elixir bar:** read once at the start (6, public). After that it only sets the `exact` flag, which is always
  True with eight distinct cards and no ability presses.

**Lag difference.** It trained with the engine's 27-tick delay, which can hold several commands. Our loop has the same
27 ticks but one outstanding command, so it is blocked while one is pending. The memory is built with delay (0, 0),
the delay of the battle it reads.

**Imports.** It imports royalegym/royalelearn/pettingzoo from a no-deps vendor dir
(`/mpac/sdicks02/repos/clasher-bot-rsim/rext-vendor` on 03 and 04, appended to sys.path). Our venv is untouched: its
gymnasium 1.2.3 works.

**Cost:** about 2–5 s of CPU per game for the rext side (policy-vs-scripted games).

## 4. Smoke (K4S-b64 vs rext-*, RoyaleSim 15.535, HEADLINE cases 0–3)

Run on 04:

```
python -m bot.eval.headline --engine rsim15535 --candidate K4S-b64 --opponents rext-rlppo,rext-rlppo-r5 --games 4 \
    --out /mpac/sdicks02/jobs/clasher/bot-ext-smoke/final-{a,b}
```

| opponent | case | K4S seat | K4S score | ticks | command hash (rep a = rep b) |
|---|---|---|---|---|---|
| rext-rlppo | 0 | 0 | 1 | 3600 | 8aee6cff71ccd976 |
| rext-rlppo | 1 | 1 | 1 | 3600 | c90a14237dc101c1 |
| rext-rlppo | 2 | 0 | 1 | 2641 | ce28599b1d1e01fb |
| rext-rlppo | 3 | 1 | 1 | 3097 | 8f96fb6b1c49133d |
| rext-rlppo-r5 | 0 | 0 | 1 | 3358 | 464fe0f2da03f7d2 |
| rext-rlppo-r5 | 1 | 1 | 1 | 3600 | 5e8f7a72390d6fe7 |
| rext-rlppo-r5 | 2 | 0 | 1 | 2232 | faa59c709600349d |
| rext-rlppo-r5 | 3 | 1 | 1 | 3195 | 7c92717b27329b0e |

- **Result:** K4S-b64 won 8/8.
- **Determinism:** reps a and b are identical in every game: hash, ticks, towers and plays.
- **Cost:** 25–53 CPU s per game, which is the K4S side.
- **Earlier plumbing smoke:** with the untrained r1 model, `plumb-r1-{a,b}` was also identical across reps.

## Files

| File | What |
|---|---|
| `bot/players/rext_envs.py` | RoyaleGym env for training: X4S decks, level 11, 15.535.29 arms, engine delay 27/27, RoyaleGym defaults otherwise. Torch- and clasher-free. |
| `bot/players/rext_train.py` | RoyaleLearn `Learner` launcher (opponent="self"), switched to RoyaleLearn's process rollout farm. |
| `bot/players/rext_eval.py` | `royalegym.evaluate` of a checkpoint vs one rung of RoyaleGym's scripted ladder (learnvenv). |
| `bot/players/rext_policy.py` | `RextPolicyPlayer` plus `SlotRemapBattle`. |
| `bot/players/rext_check.py` | Equivalence check: the player's view of our battle == RoyaleGym's own engine state. |
| `bot/eval/headline.py` | make_player: `rext-` prefix. |
