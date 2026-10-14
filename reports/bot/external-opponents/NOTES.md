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

## 2. What was trained

TODO (filled in at the end of the runs)

## 3. The Player: `rext-<model>[-greedy]` (bot/players/rext_policy.py)

TODO

## 4. Smoke (K4S-b64 vs rext-rlppo, RoyaleSim 15.535)

TODO

## Files

| File | What |
|---|---|
| `bot/players/rext_envs.py` | RoyaleGym env for training: X4S decks, level 11, 15.535.29 arms, engine delay 27/27, RoyaleGym defaults otherwise. Torch- and clasher-free. |
| `bot/players/rext_train.py` | RoyaleLearn `Learner` launcher (opponent="self"), switched to RoyaleLearn's process rollout farm. |
| `bot/players/rext_eval.py` | `royalegym.evaluate` of a checkpoint vs one rung of RoyaleGym's scripted ladder (learnvenv). |
| `bot/players/rext_policy.py` | `RextPolicyPlayer` plus `SlotRemapBattle`. |
| `bot/players/rext_check.py` | Equivalence check: the player's view of our battle == RoyaleGym's own engine state. |
| `bot/eval/headline.py` | make_player: `rext-` prefix. |
