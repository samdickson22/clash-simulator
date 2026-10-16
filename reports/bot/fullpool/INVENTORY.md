# Full-pool inventory: where the bot's learned components are wired to C56 (exploration)

Scope: the student/RL policy, R3a/v1, the K4L rollout opponent, the opponent model and belief, and the
generation/eval paths. For each site: what a non-C56 card does **today** (r1/r1-total), what it does under
**r1-cards1** (CARD LEAD pin, `reports/cards/runtime/SCOPE.md`), and the fix. The engine/runtime sites
(config, meta, costs, templates, native gating) are the CARD LEAD's: their `SCOPE.md` §2 and `INVENTORY.md` cover them,
and they are cited here only where a learned component depends on them.

Name spaces differ, so every full-pool table must alias them (`bot/fullpool/cards.py`): engine names (R.costs,
deck lists: `Archers`, `IceGolem`, `BarbLog`, `BlowdartGoblin`, `Ghost`, new `Assassin`, `SkeletonWarriors`, ...),
card_vocab names (`Bandit`, `Guards`, `BarbarianBarrel`, `DartGoblin`, `RoyalGhost`, `MergeMaiden_Normal`, ...),
display/Battle Log names. Pool = 56 C56 + 65 new = 121 playable; MergeMaiden (Spirit Empress) is excluded by the
scope (no card_action token).

## (a) Student / RL policy (RL r5 v10, it5s2, any `student:`), and (b) R3a / v1 policies

All are the same set transformer (`exit_r3/network.py`, `imitation/model/network.py`), vocab 360.

| site | today (r1/r1-total) | r1-cards1 | fix |
|---|---|---|---|
| `card_embed` (360 x width) | the vocab is the contract-v5 token walk over all 122 cards, so every card has a real token, **no OOV/IOOB**. Rows of the 223 tokens that only non-C56 cards produce are **untrained**: R3a and RL r5 v10 moved every one of them by exactly the weight-decay factor (rel. change 0.0109 v1→R3a, 0.0212 R3a→RL); only 63 rows ever got a gradient (all C56-owned + towers) | same | **`bot/fullpool/extend.py policy`**: 90 rows rewritten from proxy rows (card token ← proxy card's, body tokens ← proxy body's; 21 shared tokens such as `Freeze`, `Skeleton`, `Barbarian` are produced by a C56 card too and are left alone). Shapes unchanged; C56 parity PASS (below) |
| `descriptors` / `costs` buffers (360 rows, from gamedata) | filled for all 360 tokens (card stats; bodies/projectiles 0) | same | none |
| D1 sidecar `DerivedD1(costs)` (every policy: `policy.py`, `student.py`, `rl/actor.py`, `teacher.py`) | first non-C56 play by either seat → **`ValueError('unknown card cost')` crash** | costs cover the pool → works | runtime (CARD LEAD) |
| v5 action mask | a non-C56 own slot is legal (cost from gamedata) | same | none |
| `rt.POLICY` / `rt.STUDENT` loaders | sha-pinned `main02.pt` / `R3a.pt` | same | **`bot/fullpool/models.py`**: `BOT_FULLPOOL_POLICIES='v1=…,R3a=…'` swaps in an extended file only if its receipt says it came from the pinned sha |
| RL learner/critic (`bot/rl/learner.py`, `critic_pretrain.py`) | trunk-shaped, no card tables beyond `card_embed` | same | start RL from the extended checkpoint (`policies/LATEST` → `rl5-v10-fp.pt`) |
| R3a as search proposer (`bot/search/candidates.py` `ranked()`) | student net ranks legal actions: safe | same | extended R3a via `BOT_FULLPOOL_POLICIES` |
| `C56RolloutPlanner.candidates` (K4S/K4C/K4L own candidates, via `R.bots`) | our non-C56 hand → **`ValueError('own hand outside C56 action scope')`** | **unchanged** (R.bots stays C56) | CARD LEAD's next step (widen R.bots). Until then every search seat (teacher, K4L) needs a **C56 own deck**: deck option `own=c56`; RL league games vs `K4C-r16` get a C56 opponent deck automatically |

## (c) K4L learned rollout opponent (`bot/search/lopp*.py`, `.npz` in bot-lopp-models)

| site | today | r1-cards1 | fix |
|---|---|---|---|
| `.npz` vocab `meta_vocab` = [pad] + 56 C56 meta tokens; `emb` (57,16), `tem` (57,H), `Wv` (H,57), `meta_cost` | native view sends token 0 for non-`meta.cards` hand slots; net sees pad | native view sends the **real token**; net maps it to index 0 (**pad embedding**), `cost_of` 0 → marked affordable; the native mask allows the slot, so the net can play the card **with the pad embedding** (silently wrong, no crash) | **`extend.py lopp`**: 65 tokens APPENDED (never renumbered), `emb`/`tem` rows and the card-logit column copied from the proxy card, true meta cost; new columns in `Wv_x`/`bv_x` with their own matmul (`lopp_feat.NumpyOpponent.heads`), so the C56 columns are the same BLAS call. Parity PASS (below) |
| `lopp_train.card_meta` (vocab = sorted meta tokens) | 57 | 122, but **sorted** (new tokens interleave: a fresh model, not a fine-tune of the extended one) | a fine-tune from the extended net must keep its vocab order (`meta_vocab` of the `…fp.npz`); open item for the retrain worker |
| `featurize` board features | cost/hp/building from native `public_view`: correct for any body in `meta.bodies` | same | none |
| `lopp_fast` fc config cut | non-C56 card names → full config kept | CARD LEAD's `fc_cut.py` | runtime |

## (d) Opponent model and belief

| site | today | r1-cards1 | fix |
|---|---|---|---|
| `bot/search/oppmodel.py` (K4O style aggregation) | weights over the 3 scripted styles, no card tables | same | none |
| native scripted rollout opponents (`c56_ranked`) | never play a non-C56 card (clogs a slot) | play revealed/sampled new cards | runtime |
| `s1/belief.Belief` / `DerivedPublicState` prior = `rt.PRIOR` (C56 human catalog, 2925 decks, closed world) | first non-C56 reveal → `KeyError` (ids) | ids cover the pool, then **`ValueError('no train deck/order…')`** (no prior deck holds the card): every K4S/K4C/K4L search seat crashes vs a full-pool opponent | **`bot/fullpool/belief.py`**: prior = 400 full-pool sampler decks (public meta, never the actual deck); on 'no train deck' the prior is rebuilt as 400 sampler decks containing every revealed card (deterministic) and history is replayed. Selected by `rt.belief_prior` / `BOT_BELIEF_PRIOR`; set automatically by `--decks fullpool:…`; default = `rt.PRIOR` + frozen class (bit-identical) |
| `LiveBelief` (`bot/live/player.py`) | completes the prior with C56 catalog decks: hidden slots always C56 | same | LIVE LEAD's file; `bot.fullpool.belief.prior_decks(Sampler, require=revealed)` is a drop-in for `completed_prior` |
| belief determinization (lopp token D, `noise/mr_fast.py`) | samples from the same belief | same | covered by the belief fix |

## Generation and eval

| site | today | fix |
|---|---|---|
| `bot.players.ours.x4s_setup` (HEADLINE, generate, RL actor, lopp_record) | 5 X-decks from the C56 catalog only | **`bot/fullpool/banks.py case()`**: same seed/seat/shuffle, decks from the sampler; `--decks fullpool:<seed>[:own=c56,opp=c56]` / `--bank NAME` in `bot.eval.headline` and `bot.exit.generate`, `BOT_RL_DECKS` in `bot.rl.actor`. Default `x4s` unchanged |
| `generate.check_bank` | HEADLINE only | also every eval bank of `banks.BANKS` |
| `bot/players/royalesim_vocab.py`, `royalesim_translate.py` | C56 units only; `costs[last]` KeyError | not used for full-pool evals (`--engine` must be `ours` with full-pool decks, checked) |
| `bot/search/lopp_record.py` (K4L training data) | x4s cases | needs the `case()` switch before a full-pool K4L retrain (small change, not done) |

## Parity results (C56 inputs, original vs extended)

- Policy nets, 600 roots sampled from 12,477 recorded `single_features` inputs of 10 C56 games (4 HEADLINE x4s
  cases + 6 human-catalog cover-deck games, all 56 cards, 86 distinct token ids), every output tensor `torch.equal`
  and the deployed decision: RL r5 v10 (`--init row` and `--init input`), R3a, v1: **0/600 differ, PASS**;
  recorded ids ∩ rewritten rows = ∅.
- K4L `pool` and `pool2L`: 1000 recorded native public views: features, card indices, trunk, gate, base logits,
  hand logits, card argmax and tile logits for all 4 slots, row-wise and batched: **0 mismatches, PASS**.
