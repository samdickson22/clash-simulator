# Non-C56 card handling inventory under TODAY's C56 scope (r1-total) — read-only research, 2026-10-16, 127x05

What changes under r1-cards1: SCOPE.md §2. Paths: `R` = the clasher-cards worktree, `RO` = a read-only copy of the r1 runtime sources.

Sources: bot repo `R=/mpac/sdicks02/repos/clasher-cards` (cards/lead), frozen runtime `RO=.../cards/runtime/r1-ro`,
native `R/engine-cards` (= r1-total source). `imitation/` is not in r1-ro; it is identical in `R/imitation` and
`e4v3-20261010-r1/imitation` (diff -rq clean), so it is cited from R. Two facts were checked by running the frozen
builder (light probe, <1 s): see §0.

## 0. Key facts that frame everything

- **Observation vocab is already S122.** `RO/src/clasher/rl/contract_v5.py:7-11,70-73,157-178`: pinned 360-token list from
  the 122 corpus cards (`contract_v5_tokens.json`: `cards`=122, 360 tokens, `<pad>`=0, `<unknown>`=1).
  `ContractV5ObservationBuilder.__init__` passes `card_vocab=tokens.cards` (`contract_v5.py:406-407`).
  `StructuredObservationBuilder.token_id` (`structured_obs.py:309-332`) returns `<unknown>`(1) for unknown names and never raises.
  So all 122 ladder cards get real tokens. Only a card *outside the 122* would become token 1.
- **The true non-C56 set has 66 cards, not 69.** Three C56 cards have different names in the vocab: `BarbLog`↔`BarbarianBarrel`
  (tokens 20/24), `BlowdartGoblin`↔`DartGoblin` (38/77) and `Ghost`↔`RoyalGhost` (114/289). `bot.cards` maps both tokens
  of each pair to the C56 name (59 token keys → 56 names). Any full-pool name table must apply this aliasing, or these
  three will be double-counted or mis-keyed.
- **Native `meta.bodies` already covers every 122-card body.** `metadata()` (`RO/engine-rs/c56_controller.py:89-105`)
  iterates `bot.bodies`, and `c56_scripted.init` (`RO/src/clasher/rl/c56_scripted.py:89-131`) fills that from *all*
  `builder.card_vocab` payloads. Probe: `meta.cards`=56, `meta.bodies`=142, `bot.bodies`=151 tokens, and every
  non-C56 troop/building `stats.name` is in `meta.bodies`. **`meta.cards` is strictly C56** (`assert set(cards)==set(action_cards)`, `c56_controller.py:85`).
- **`Resources.costs` is the root of most C56 coupling.** `fair_player.py:41-42`: `config=config(CARDS)`, `costs={name: cost}` for
  the 56 only. It is passed to D1, the belief, the command channel, the translators and the planner.

## (a) Policy nets and feature builders

| component | file:line | non-C56 on board | non-C56 in opp revealed cycle | non-C56 in own hand | crash/IOOB risk | notes |
|---|---|---|---|---|---|---|
| v1 SetPolicy (`imitation.model.load_policy`) | `R/imitation/model/inference.py:65-76`, `network.py:12,74` (`vocab=360`, `nn.Embedding(360,·)`) | real token, embedded | real token (types 8-10, 14, 15) | real token (type 1), `costs[hand[s]]` is a 360-row buffer | **No IOOB.** `features.py:37-41` raises only for tokens outside 0..359 | v1 was trained on `c56-store-v1` (README:38,122), so the 66 non-C56 embedding rows are **untrained** (init values). The descriptor projection (`network.py:79`) from card stats is the only signal. Silently weak, not wrong-shaped |
| R3a / it5s2 / any `student:` (`proposals.load_student`) | `RO/reports/explore/s1/proposals.py:9-16`; `RO/student-source/exit_r3/network.py:12,74` | same as v1 | same | same | No IOOB (vocab 360) | Initialized from v1 (`exit_r3/train.py:86,110`) and ExIt-trained on C56 games. Non-C56 rows are untrained |
| RL r5 v10 (`RLPolicy`/`RLPlayer`) | `R/bot/rl/actor.py:65-107,119-126,186` (`load_student`) | same | same | same | No IOOB | Same architecture and `single_features`, so the same D1 path as below |
| Live fast tier (`CLASHER_LIVE_FAST`, default it5s2) | `R/bot/live/player.py:21,43,241-247` → `bot/exit/student.py:55-63` | as student | as student | as student | via D1 (next row) | |
| **D1 sidecar (shared by every policy above)** | `R/imitation/evaluation/d1.py:13-16` `DerivedD1(costs)` with `costs=rt.R.costs` (`bot/players/policy.py:22,30`, `bot/exit/student.py:62`, `bot/rl/actor.py:125`, `bot/exit/teacher.py:57`) | n/a (events only) | **`ValueError('unknown card cost: X')`**, `RO/.../imitation/derived_d1.py:54-55` (`costs` = C56 dict) | **same `ValueError`**: both seats' trackers `accept` (`d1.py:37`) | **Hard crash on the first non-C56 play by either side.** `StandalonePlayer.decide` (`standalone.py:23`) propagates it | `D1Tracker.token` (`d1.py:21-27`) raises `unknown public card` only for names outside the 122 (token≤1). The Mirror cost uses `costs[last_card]` (`derived_d1.py:59-62`). `OwnCycle` (`own_cycle.py:24-27`) is name-agnostic |
| `ContractV5ActionMaskBuilder` | `RO/src/clasher/rl/public_action_mask.py:224-230` | – | – | **legal**: cost comes from `loader.get_card` (all cards) | none | So the policy *can* propose a non-C56 slot, and the command channel then raises (§c) |
| `make_catalog` (rt.CAT) | `RO/src/clasher/analysis/loss_review/human.py:20-41` | bodies dict over all 360 tokens | cards dict over `builder.card_vocab` (122) | 122 | none | Already full-pool. Used by `w-screen8/run.py:129` and `s1/run.py:220` (`CAT['cards'][name]['token']`) |

## (b) K4L learned rollout opponent

| component | file:line | non-C56 on board | non-C56 in opp revealed cycle | non-C56 in own hand | crash/IOOB risk | notes |
|---|---|---|---|---|---|---|
| `featurize` | `R/bot/search/lopp_feat.py:19-58` | uses `b['cost']`, `hp`, `building`, `only_buildings` from native `public_view`. Non-C56 bodies are present in `meta.bodies` (§0), so they are **featurized correctly** if they exist in the root | n/a (sees only hand/board) | `cost_of.get(t,0.)` (`:52`): cost 0, so marked **affordable** (`:54`) | none | Silently wrong: hand cost and affordability features |
| `NumpyOpponent` vocab | `lopp_feat.py:67-68`, built by `lopp_train.py:40-47,71-72` from `meta['cards']` | – | – | `m.vocab.get(t,0)` (`lopp.py:110`): index 0 (pad/empty embedding) | **No IOOB.** `pool.npz`: `meta_vocab`=57, `emb` (57,16), `tem` (57,256), `Wv` (256,57) | A non-C56 card looks like an "empty" slot with cost 0. Native view.hand already sends token 0 for non-`meta.cards` names (`scripts.rs:249`), so this case is mostly unreachable |
| `Learned.decide` mask | `R/bot/search/lopp.py:131-135` uses `native.public_mask` | – | – | the native mask is false for slots not in `meta.cards` (`scripts.rs:296`), so the card is **never played** | none | |
| `lopp_fast` `fc` cut / `ConfigCache` | `R/bot/search/lopp_fast.py:88-107,110-145,341-347` | entity names → `_card_names` (kept only if in config) | hand/cycle names: `looked_up ⊄ cards` → returns **None, so the full config is kept** (`:101-102`) | same | none in Python. The full config still lacks the card (see §c native) | Not a correctness guard for full pool. It silently falls back to full-config cost |

## (c) Candidates, scripted rollout opponents, native

| component | file:line | non-C56 on board | non-C56 in opp revealed cycle | non-C56 in own hand | crash/IOOB risk | notes |
|---|---|---|---|---|---|---|
| `CandidateSearchPlayer.candidates` | `R/bot/search/candidates.py:70-86` wraps `C56RolloutPlanner.candidates` | – | – | goes through the planner (next row) | via planner | `ranked()` (`:45-53`) is the student net: safe |
| `C56RolloutPlanner.candidates` | `RO/src/clasher/rl/c56_rollout_planner.py:73-89` | `_bodies` OK (`bot.bodies` has all 122 bodies) | – | **`ValueError('own hand outside C56 action scope')`**: `bot._ranked_actions` (`:76`) → `c56_scripted.py:192-197` | **Hard crash whenever we hold a non-C56 card** (every search decision) | `import_root` (`:94-96`) also raises on non-C56 deck cards (python-root path only) |
| `PublicScriptedOpponent` (c56) Python | `RO/src/clasher/rl/public_scripted_opponent.py:160-167` | `bodies.get(token)`: present, so OK | – | as above | – | `bot.cards` = C56 only (`c56_scripted.py:94-104`) |
| Native `NativeScripts.view` | `R/engine-cards/src/scripts.rs:168-180` | `meta.bodies.get(name)` else **skip (body invisible)**. All 122 bodies are present today, so they are visible. Champion and other bodies also need `stats.name` to match | – | `view.hand` token = `meta.cards.get(s).map_or(0,…)` (`:249`), so **token 0** | none | |
| Native `mask` | `scripts.rs:284-296` | – | – | `meta.cards.get(name)` else `continue`: **slot never legal** | none | Mirror: needs `config.cards["level12:<prev>"]` and `meta.cards[prev]` (`:285-293`) |
| Native `c56_ranked` (balanced/pressure/defense) | `R/engine-cards/src/c56_scripts.rs:50-54` | targets every `v.bodies` entry (cost/hp from meta) | – | `meta.cards.get(name)` else **skip**: **the scripted opponent never plays it** | none | Effectively 'hold forever': the card clogs a slot, the cycle stalls, and elixir is never spent on it |
| Native `command_simulation` (own action / pending) | `R/engine-cards/src/delay_commands.rs:38-43,58-62` (same in `e1_commands.rs:48,67`, `wait_screen8.rs:45,64`) | – | – | own candidate on a non-C56 slot → **`PyValueError('submitted card absent from metadata')`**. A pending reservation → `'invalid own pending reservation'` | **Python exception** (no panic) | Unreachable today because the planner raises first. It becomes the next wall once candidates allow such slots |
| Native `apply_action` | `R/engine-cards/src/lib.rs:3589-3593` | – | – | card ∉ `config.cards` → `PyValueError('unsupported card absent from imported pilot configuration')` | Python exception | `config` = `config(CARDS)` (`fair_player.py:41`; `differential.py:385` is generic in `cards`) |
| Native step-time config lookups | `c56.rs:265,286,468,588,633`, `lib.rs:1043,1109,2859,2948`, `scope.rs:263,407` | a non-C56 spell area / chain / delivery: r1-total **skips the effect** (`reports/bot/learned-opponent/NATIVE-TOTAL.md` §2). Pinned `44874fd6` **panics** | – | – | r1 pin = panic; r1-total = silent no-op | Silent wrong physics, never a crash on r1-total |
| `Resources.root` (search root) | `RO/reports/.../engine-speed/stage5/fair_player.py:113-118`; live `R/bot/live/levels.py:81-82` | **`ValueError('no C56 public model template: …')`**: templates come only from C56 config walks and C56 demos (`:67-69,92-107`) | – | own hand/cycle names are written into `players` as is. Natives accept them, then skip/raise as above | **Hard crash on any non-C56 body on board** | The live translator pre-filters (§e), so this does not fire live. Sim/eval would crash |
| Command channel | `RO/src/clasher/analysis/loss_review/delay_fixes.py:64-75` (`card not in costs` → raise) | – | – | **`ValueError('empty/reserved slot or unaffordable command')`** | crash in `ours.py:94`, `translate.py:736`, `royalesim_match.py:163` | |

## (d) Opponent belief and human deck prior

| component | file:line | non-C56 on board | non-C56 in opp revealed cycle | non-C56 in own hand | crash/IOOB risk | notes |
|---|---|---|---|---|---|---|
| `DerivedPublicState` (frozen) | `RO/reports/.../engine-speed/stage5/derived_public_state.py:22-27,34-37,72-77,83` | n/a | `self.ids[event.name]` → **`KeyError`** (`:73`). Even with ids extended, no prior deck holds it → `ValueError('no train deck/order…')` (`:77`) | n/a | **Crash** | `ids` come from `costs` (C56). The uint8 state allows ≤255 cards (`:26-27`), so 122 fits. Constructor raises `KeyError` if any prior deck holds an unknown name (`:35`) |
| `s1/belief.Belief` (deadline wrapper, used by K4/K4S/K4L) | `RO/reports/explore/s1/belief.py:43,55,58` | – | same `KeyError`, then `ValueError` | – | crash | |
| `LiveBelief` / `completed_prior` | `R/bot/live/player.py:200-235` | – | catches only 'no train deck' and rebuilds the prior as human decks completed with revealed cards (open world). A non-C56 name still hits `KeyError` in `self.ids` | – | crash on non-C56; fine on off-prior C56 decks | Fill rule: revealed + the remaining cards of each catalog deck in catalog order, top 400 by summed weight (`:225-235`). So unknown slots are always C56 |
| Human deck catalog | `RO/reports/strategy_council_20260928/c56/engine/root-v3/human_deck_catalog.json` (identical copy in `search-noise-s6/runtime/support/`) | – | – | – | – | schema `c56-human-deck-catalog-v1`, source_role train, **2925 decks, exactly the 56 C56 cards**, weights in `frequency`. Sampling (`derived_public_state.py:108-113`) draws only whole catalog decks × 1680 orders, so it is **closed world: hidden slots are always C56** |
| `x4s_decks` / `x4s_setup` | `R/bot/players/runtime.py:120-125`, `ours.py:19-31` | – | – | – | – | Eval decks are drawn from that catalog, so eval is C56-only by construction |

## (e) Live translator, RoyaleSim vocab, fair_player

| component | file:line | non-C56 on board | non-C56 in opp revealed cycle | non-C56 in own hand | crash/IOOB risk | notes |
|---|---|---|---|---|---|---|
| `bot/live/translate.py` body map | `:330-341,360-365` | `body()` needs `(token,kind)` in `R.templates` (C56 only), otherwise **dropped and counted** (`unmapped_unit:`/`no_template:`) | – | – | none (guards the root) | Search is blind to non-C56 units: no defense against them |
| card-level `assign` | `:501-523` | not `cards.is_card`: proxy if `unknown_card='proxy'`, else dropped (`unmapped_card_unit:`) | – | – | none | |
| `card_name` / `accept_events` | `:475-482,547-586`, `PROXY` `:60-70` | – | `'drop'` (default): the play is **removed**, so opponent elixir is over-estimated by its cost and the cycle is short. `'proxy'`: a same-cost C56 stand-in (31 entries) keeps the elixir ledger, with the wrong identity. Cards not in PROXY are dropped either way | own non-C56 play: `own_tracker.play` runs, but no D1/public event is emitted (`:573-576`), so our D1 own cycle diverges silently | none | 9th distinct enemy card dropped (`:579-582`) |
| `board_card_ok` | `:525-545` | an own unit off our deck, or an enemy 9th card, is dropped | – | – | none | Its docstring records the pinned-native panic it guards against (Electro Spirit `electro_land`) |
| `hud` / `OwnTracker` | `:588-599`, `:160-266` | – | – | **only counted** (`own_non_c56:`). The docstring at `:35` says these become empty slots, but `OwnTracker.own` returns deck names unchanged, so a non-C56 own deck card reaches `info.own.hand`, then `R.root`/D1/channel (§a/§c) | latent crash (planner `ValueError`, channel `ValueError`) | Live decks are C56 today, so it is not hit |
| `royalesim_translate.Translator` | `R/bot/players/royalesim_translate.py:97,236-256` | rows map via `royalesim_vocab.json` (47 C56 units), else dropped | history/seen use `token_id` (OK) | `own_last_play=… int(self.costs[last])` (`:256`) → **`KeyError`** for a non-C56 own play | crash (RoyaleSim matches) | |
| `royalesim_vocab.py` | `:163,174,250-259` | built by looping `c56_controller.CARDS` demos, so non-C56 units are `unresolved` (dropped) | – | – | none | Rebuild over S122 needed |
| `fair_player` (`bot/players/fair_player*` does not exist; the runtime one is `RO/.../engine-speed/stage5/fair_player.py`) | `:41-42,92,113-118,165-179` | `root` raises (see §c) | `PublicPlanner` belief = `DerivedPublicState(prior, costs)` (`:167`) | `costs`/`config` C56 | see above | `royalesim_opponents.py:151` and `variants.py:108` also build `PublicScriptedOpponent(card_scope='c56')` |

## C56 scope baked-in sites

1. `RO/engine-rs/c56_controller.py:16` `CARDS = sorted(SUPPORTED_CARDS | C56_ADDED_CARDS)`; `:24` `card_scope="c56"`; `:85` `assert set(cards)==set(action_cards)`; `:136-141` `resources()` (meta, NativeScripts, 3 bots).
2. `RO/src/clasher/rl/public_scripted_opponent.py:24` `SUPPORTED_CARDS`; `:76` scope ∈ {p16,c56}; `RO/src/clasher/rl/c56_scripted.py:18` `C56_ADDED_CARDS`, `:78-104` (`bot.cards` restricted to the scope), `:195-196` raise.
3. `fair_player.py:41-42` `config(CARDS)`, `costs` (feeds D1, belief, channel, translators, planner `core.costs` at `bot/players/search.py:123`, `bot/search/players.py:153`, `bot/live/player.py:127`); `:92-107` template demos `for name in CARDS`; `:118` the error string says "C56".
4. `derived_public_state.py:23-24` names/ids from `costs`; the catalog file `c56/engine/root-v3/human_deck_catalog.json` (`runtime.py:82`), 56 cards; `live/player.py:225-235` completes the prior from it.
5. `imitation/evaluation/d1.py:16` / `derived_d1.py:23` `DerivedD1(costs)`.
6. `delay_fixes.py:73` `card not in costs`.
7. K4L: `lopp_train.py:40-47` vocab = `meta['cards']` tokens (57 with pad) baked into every `.npz` (`meta_vocab`, `emb`, `tem`, `Wv`). **Retraining is needed for full pool** (shapes change).
8. Native: `meta.cards` gating in `scripts.rs:249,291,296,394,533,808`, `c56_scripts.rs:54`, `delay_commands.rs:42,61`, `e1_commands.rs:48,67`, `wait_screen8.rs:45,64`. `meta.c56` flag branches (`scripts.rs:55,174,181,305-353,655,732,743,888-909`). Card-name special cases in the C56 scorer (`c56_scripts.rs:60,74,100,105,109,116,171,174`: Miner, GoblinBarrel, Lightning, Log/BarbLog, Tornado, Poison/Earthquake, Xbow, GoblinHut). `c56_controller.py:79` hits_air exceptions {Log, BarbLog, Earthquake}.
9. `c56_rollout_planner.py:94-96` import_root "level 11 supported cards"; `C56RolloutPlanner`/`C56SearchConfig` naming throughout `bot/players/search.py:83-99`.
10. Live: `translate.py:60-70` `PROXY` (non-C56 → C56 map); `:33-35` drop/proxy policy; `:597` `own_non_c56`; `royalesim_vocab.py:163,174` and `royalesim_vocab.json` (`meta.cards` = CARDS); `bot/fidelity/c56_native_ids.json` (used by `rs_parity.py:22`, `speed/bench.py:23`, `rsim_fork/clone_test.py:27`, `rext_imitate_replays.py:36`); `bot/live/replay.py:88,289,309`, `real_replay.py:217`, `perc.py:85` (`rt.R.costs` as the card universe).
11. Training data: v1 `main02.pt` and all students (R3a, it5s2, RL r5) are trained on C56-only stores (`imitation/model/README.md:38,122-131`), so the non-C56 embedding rows are untrained.
12. Aliases: C56 internal names `BarbLog`/`BlowdartGoblin`/`Ghost` vs vocab card names `BarbarianBarrel`/`DartGoblin`/`RoyalGhost` (§0).
