# Scope expansion beyond the 16-card pilot, with a human-replay prior (draft)

Status: draft for decision, 2026-10-01. Nothing here is implemented or authorized. To write it I only read files and ran single-threaded analysis under `nice -n 15`. I started no emulators, training or pilot interaction.

Inputs: `../strategy.md` (especially "Levels and scope growth", "Human observations", Tier A/B and "Scheduled follow-on work"); `../m0/human-prior-scan/` (README, `summary.json`, `corpus_tiers.json`, `corpus_index.jsonl.gz`); the actor/observation contract (`model.py`, `structured_obs.py`, `public_observation.py`, `public_action_mask.py`, `public_policy_contract.py`, `card_semantics.py` v4); the Tier A/B machinery (`readiness_root_bank.py`, `training_readiness_v2.py`, `readiness_capture_ownership.py`, `../m0/tier-b/RUNBOOK.md`); `../m0/native-mechanics-20260928/`; and pilot state (`../pilot/throughput/README.md`, `../pilot/v7r1-launch/`).

New numbers in this plan come from `scope_coverage.py`, which reads the scan index and writes `scope_coverage.json`.

## Recommendation at a glance

1. **Use two scopes instead of one.**
   - The *engine/observation scope* is all 122 base cards in the corpus. That means fixing the 5 broken cards and the 2 approximations.
   - The *actor scope* (what the learner holds, what PPO trains on, what Tier A admits) is a curated **C56**: the 16 pilot cards plus 40 high-coverage cards.
   - Only the learner's own deck must be inside the actor scope. The opponent only has to be simulable. This gives C56 **67,886 labelled perspectives (3.23M plays) today and 88,680 (4.15M plays) after the engine fixes**. Requiring both decks in scope gives only 8,116 matches.
2. **Answer "does the human prior help?" first at 16 cards.** Before paying for the broad scope, run a P16 human-prior arm under the pilot recipe and compare it with the pilot's scripted and scratch arms at 1M and 5M. P16 has 11,028 perspectives today and 14,315 after the fixes.
3. **Then run C56:** engine fixes, native mechanics checks, C56 scripted controllers, contract v5, human-prior BC, Tier A in mechanic bundles, and three PPO arms (human, scripted, scratch). Tier B and the league come after.
4. **Rough timeline:**
   - About 3–3.5 weeks to a C56 5M comparison if extraction, BC and PPO run on rented compute.
   - About 4–5 weeks on this Mac alone.
   - The critical path is emulator-bound work (native checks, Tier A, Tier B), and only this Mac can do it. It cannot start until the pilot frees the CPU (pilot ends about Oct 6–7).

## 0. What this plan changes in the approved strategy

Some items need an explicit strategy amendment and a new strategy SHA. The admission receipt binds `strategy_sha256` and `supported_cards`.

- **IL_Replay use.** The strategy says "IL_Replay remains action-only until reconstruction is defensible" and forbids relabelling modern forms as base-card truth. Your guidance (a rough prior, not version-exact) plus the re-simulation evidence support an amendment. The amendment would say that re-simulated base-form observations, cut at the first contradiction, may train a *low-weight, measured* prior, with forms kept as metadata.
- **Fitting before admission.** The strategy says "No gameplay fitting precedes Tier A". Human BC on C56 observations is gameplay fitting outside the v7 admitted scope. Even P16-hand BC sees opponent units from outside the 16 cards. Section 6 proposes the rule.
- **Hard-coded 16-card scope.** These admission-bound code paths all assume 16 cards:
  - `public_scripted_opponent.SUPPORTED_CARDS`;
  - the root bank's 4 hard-coded `DECKS`, its "decks ⊆ 16" rule and its "2 focal requests per pilot card" rule;
  - the receipt's `supported_cards` default and `public_contract_version: Literal[4]`;
  - the `council_pilot` check that the receipt's cards equal the 16;
  - Tier B's `load_frozen_policy` vocabulary check.

  Changing them means a new snapshot and a new admission. The running pilot is unaffected.
- **Unchanged:** the pilot keeps its role as the learning-system viability test. Broad PPO waits for the pilot's 5M evidence. The pilot alarms seen so far are relevant here: s2901/scripted at 0.68M shows `entropy_collapse_card`, `entropy_collapse_mode` and `starved_card`.

## 1. Card scope

### Coverage by scope

- Columns 4–5 count "perspectives": (match, side) pairs whose own deck is inside the actor scope and whose opponent deck the engine can simulate.
- S117 is today's engine. S122 is the engine after the 5 broken cards are fixed.
- "Both decks" is the scan's tier (a).
- C40, C48 and C56 are greedy own-deck-completion picks seeded with P16. C56 is C48 plus 8 diversity cards.

| Scope | Cards (new vs P16) | Both decks in scope: matches / plays | Perspectives, S117 engine (plays) | Perspectives, S122 engine (plays) | Matches to re-simulate (S122) |
|---|---|---|---|---|---|
| P16 | 16 (0) | 262 / 31k | 11,028 (0.59M) | 14,315 (0.75M) | 14,053 |
| C40 | 40 (24) | 4,846 / 0.54M | 52,124 (2.55M) | 67,997 (3.27M) | 63,151 |
| C48 | 48 (32) | 7,433 / 0.80M | 65,030 (3.11M) | 84,948 (4.00M) | 77,515 |
| **C56** | **56 (40)** | **8,116 / 0.87M** | **67,886 (3.23M)** | **88,680 (4.15M)** | **80,564** |
| G66 | 66 (50; lacks Goblins) | 6,386 / 0.54M | 59,177 (2.39M) | 77,289 (3.07M) | 70,903 |
| S117 | 117 (101) | 146,290 / 10.3M | 292,580 (10.3M) | 383,616 (13.3M) | 237,326 |
| S122 | 122 (106) | 251,665 / 17.0M | – | 503,330 (17.0M) | 251,665 |

About 93% of C56 perspectives have Princess Towers on both sides (82,231 of 88,680). The rest use tower-troop substitutes.

**C56 list.**
- P16: Archers, Cannon, DarkPrince, Fireball, Giant, Goblins, HogRider, IceGolem, IceSpirit, Knight, Log, Musketeer, Prince, Skeletons, Tesla, Zap.
- Added, in order of corpus deck frequency: barbarian-barrel 158.5k, elite-barbarians 113.5k, berserker 113.0k, arrows 88.6k, tornado 87.4k, electro-spirit 82.2k, royal-ghost 51.5k, lightning 51.4k, balloon 49.4k, baby-dragon 47.9k, wizard 45.9k, minions 45.6k, valkyrie 45.3k, golem 42.7k, skeleton-army 40.4k, miner 38.6k, mini-pekka 36.5k, furnace 35.0k, royal-hogs 33.6k, princess 31.0k, dart-goblin 30.8k, poison 29.8k, goblin-gang 29.4k, goblin-barrel 29.2k, bats 28.3k, rocket 28.2k, wall-breakers 24.4k, bomb-tower 23.7k, firecracker 23.4k, minion-horde 22.2k, goblin-hut 22.2k, goblinstein 22.0k, rascals 21.9k, mighty-miner 21.4k, earthquake 21.2k, fire-spirit 16.2k, inferno-tower 12.6k, x-bow 10.7k, royal-delivery 10.3k, archer-queen 8.2k.

### Why C56

- **Against G66:** C56 has more data with 10 fewer cards (67.9k vs 59.2k perspectives) and covers the current meta. G66 lacks berserker, elite barbarians, mighty miner, skeleton army, lightning, furnace, goblin hut, wizard and even Goblins. The G66 tensor-support artifacts are, per the strategy, "candidates for scope, not proof of admission", so they save little native work.
- **Against S117 now:** S117 adds 101 cards to admit natively, roughly 8+ Tier A bundles. It includes heroes, more champions, Mirror/Clone/Rage and spawner variety. The 32-family Tier A design cannot cover it per card. Use S117/S122 as the engine and prior scope now. Widen the actor scope later in steps (C56, then about 80, then S122) as bundles are admitted.
- **C56 meets the strategy's diversity requirement.** It adds air (Baby Dragon, Minions, Bats, Minion Horde, Balloon), splash (Wizard, Valkyrie, Firecracker, Princess, Bomb Tower), swarm (Skeleton Army, Goblin Gang, Rascals), buildings and spawners (Furnace, Goblin Hut, Inferno Tower, X-Bow, Bomb Tower), spells (Arrows, Tornado, Lightning, Poison, Rocket, Earthquake, Barbarian Barrel, Royal Delivery), death spawn (Golem) and deploy-anywhere cards (Miner, Goblin Barrel). Recognizable decks survive: Hog 2.6, X-Bow 3.0, Log Bait, Golem beatdown, LavaLoon-lite, Miner Poison and Royal Hogs.

**Swap rules (open).** The greedy step kept some low-frequency cards because they complete decks: archer-queen 8.2k, royal-delivery 10.3k, x-bow 10.7k and inferno-tower 12.6k. It skipped some popular cards that only appear in decks with other out-of-scope cards: battle-ram 55.5k, zappies 52.1k, mother-witch 48.1k, inferno-dragon 46.5k, giant-snowball 45.7k, bowler 43.4k, bomber 41.2k and freeze 40.5k. Swaps are allowed but reduce complete-deck coverage, so re-run `scope_coverage.py` after any change.

**Champions (decision).** C56 contains three: mighty-miner, goblinstein and archer-queen. Including them needs the ability action (section 3). Dropping them leaves a C53 with somewhat less coverage (not computed).

### Native evidence by option

These counts are order-of-magnitude planning numbers:

| Option | New cards to admit | Targeted native scenarios (est.) | Tier A bundle attempts (first pass) |
|---|---|---|---|
| C56 | 40 | ~24 | 4 × 32 families |
| G66 | 50 | ~30 | 5 |
| S117 | 101 | ~60 | 8+ |

## 2. Engine work

### 2a. Broken and approximated cards (engine scope; needed for the prior, not the actor)

The order follows S117 marginal unlocks from the scan. The native decoded-logic catalog (`~/.cache/clasher-native-reference/decoded-logic-1e505767/*.csv`) has entries for all of these, so native traces should be possible. Whether the native harness can deploy each one still needs a check.

| Priority | Card | Deck freq. | S117 marginal matches | Current defect | Work |
|---|---|---|---|---|---|
| 1 | vines | 45.8k | 34,742 | No effect | Root/DoT on up to N targets, air pull-down |
| 2 | heal-spirit | 36.6k | (in S117, wrong) | Legacy Heal spell substituted | Kamikaze troop with heal pulse |
| 3 | elixir-collector | 30.6k | 22,760 | Body only, no elixir | Elixir generation over lifetime and on death; affects own elixir channel |
| 4 | goblin-drill | 19.8k | 14,510 | Own side only, no spawns | Dig to any tile, periodic goblin spawns, death spawn |
| 5 | void | 18.9k | 12,821 | No effect | Damage pulses scaled by target count |
| 6 | goblin-curse | 9.6k | 6,103 | No effect | DoT, damage amplification, goblin conversion on death |
| 7 | spirit-empress | 5.7k | (approx.) | Ground form only | Two-mode card; low priority |
| – | tower troops | 19.6k S117 matches | – | Princess substituted | Filter these matches out in v1; revisit later |

The acceptance bar here is lower than for actor cards: a scalar smoke test plus one native trace per card in the `nm_lib` scenario format. Errors limit themselves somewhat, because opponent-unit errors cause earlier contradictions and therefore earlier cuts. Track per-card contradiction attribution (2c) to confirm this.

### 2b. Native mechanics checks for the 40 C56 cards

Reuse the `native-mechanics-20260928` method:
- identical commands on both engines, first seed by fixed rule, one-tick stepping, rich native frames;
- verdict scale match / small / consequential;
- repairs go into tests with native fixtures, as was done for the King wake-up stun.

The bundles below, ordered by summed deck frequency, also define the Tier A bundles in section 6:

| Bundle | Cards | Scenarios to write (examples) |
|---|---|---|
| B1 Spells/control | barbarian-barrel, arrows, tornado, electro-spirit, lightning, poison, rocket, earthquake, royal-delivery | Tornado pull and King activation; Lightning target choice and stun; E-Spirit chain and reset; Poison slow and DoT ticks; Earthquake building multiplier; Barrel roll plus spawn; Rocket/Arrows edge radius |
| B2 Air + splash | baby-dragon, minions, bats, minion-horde, balloon, wizard, valkyrie, princess, firecracker, dart-goblin | Air targeting and retarget; Balloon death damage; Firecracker recoil; Princess range and splash vs swarms |
| B3 Ground melee / swarm / kamikaze | elite-barbarians, berserker, mini-pekka, skeleton-army, goblin-gang, rascals, golem, royal-hogs, wall-breakers, fire-spirit, royal-ghost | Golem death spawn and damage; Wall Breakers building hit; Royal Ghost invisibility and reveal; Royal Hogs split lanes |
| B4 Buildings / deploy-anywhere / champions | furnace, goblin-hut, inferno-tower, x-bow, bomb-tower, miner, goblin-barrel, mighty-miner, goblinstein, archer-queen | Spawner intervals and pulls; Inferno ramp reset; X-Bow lock range; Miner tunnel time and tower damage; Goblin Barrel flight; champion abilities |

Two cheaper screens should run before native time is spent:
- **Per-card contradiction attribution from re-simulation.** Regress time-to-first-contradiction on card presence. Cards whose presence pulls the first contradiction earlier go to the front of the native queue.
- **The tower-outcome undershoot.** In 195 of 262 P16 matches, a real tower kill never happens in simulation. Most likely cause: evo/hero forms (about a third of deck slots) and L16 stats played at L11 base. The native build includes evo tables (`buildings_evo.toml`, `card_forms.toml`), so modelling evo forms for the top cards later is possible. It is not part of this plan.

### 2c. Scripted controllers for C56

`PublicScriptedOpponent` is mostly generic stat-driven scoring. It has one card-specific branch (Log), and its constructor refuses any vocabulary outside the 16 cards.

Extending it to C56 is required for four things: Tier A candidate generation and continuations, the scripted warm-start arm, the fixed evaluation pool and league filler.

The work covers:
- deploy-anywhere placement (Miner, Goblin Barrel);
- building, spawner and siege placement;
- spell targeting for pull, DoT and multi-target spells;
- air awareness;
- a declared champion-ability rule (or abilities stay masked for the scripts).

Before freezing, check non-wait coverage on scalar development roots, as Tier A requires.

## 3. Model contract v5

**Vocabulary.**
- Today the token list is built from the deck pool: the pilot has 36 tokens. Building from all 122 cards gives 360 tokens.
- The pilot's 36 tokens are a strict subset of the 360.
- `card_stat_features` has shape (360, 36). Every card gets a nonzero semantic vector except Mirror, and no two cards have identical vectors.
- v5 should pin the token list as a versioned file built from S122, including payloads added by the engine fixes, instead of deriving it from decks. The observation vocabulary then stays fixed while the actor scope grows.

**Semantic descriptors (v5 additions).** The v4 features miss mechanics that C56 and S122 introduce. Proposed additions:
- deploy_anywhere;
- spawn interval, plus spawned elixir value per minute;
- building lifetime/decay;
- elixir generation;
- champion flag, ability cost and cooldown;
- invisibility and underground travel;
- ramp damage;
- chain target count;
- kamikaze;
- buff and pull flags;
- clone and mirror flags;
- knockback strength;
- death-damage magnitude;
- spawn/deploy damage;
- multi-projectile count;
- a non-zero Mirror descriptor.

Add them as new columns with zero-initialized input weights, so the extension does not change existing outputs.

**Actions.**
- Keep the 2,306-way action space: 4 slots × 576 tiles, plus wait and ability.
- Unmask the ability action only when a champion is on the board, elixir covers the cost and the cooldown is visible. Today it is always masked. The champion decision in section 1 depends on this.
- Audit masks for footprints (X-Bow, spawners), deploy-anywhere cards and Mirror/Clone.
- Audit the placement-sensitive cases the strategy flags (pulls and spell edges), now including Tornado and building pulls.

**Visible status.** The strategy's "visible-status contract extension during the pilot" becomes a hard prerequisite for C56. The builder already computes `stealth_active`, `hidden_building`, `stun_remaining` and `slow_remaining`, but the actor uses the real-play-v2 subset. For each channel, v5 must decide whether it is public, and enemy invisible or underground units must be hidden (Royal Ghost, Miner, Archer Queen cloak). The hidden-state invariance test needs cases for these.

**Levels.** The human data is mostly L16 vs L16; 562k deck slots are at L11 in capped modes. Simulate and observe at nominal L11 for both sides, store the original levels, and keep the 10–12 mixed-level plan unchanged.

**Transferring the 16-card pilot's weights: feasible and cheap.**
- Copy the 36 token-embedding rows by name in both the actor and critic encoders. `placement_prior` is disabled in the pilot, so it needs no remap.
- Keep every other tensor as it is: entity/global projections, transformer, LSTM and heads. Their shapes do not depend on the vocabulary.
- Zero-initialize the identity rows for new tokens. With `card_input_mode="hybrid"`, the stat and semantic projections give new cards a meaningful starting embedding.
- Zero-initialize the input columns for new semantic features.
- Acceptance test: the upgraded v5 model gives logits bit-identical to the pilot checkpoint on P16 observations. `checkpoint_upgrade.py` (semantics v1→v3) is the precedent.
- Recommendation: start the primary human arm from fresh weights. Treat "pilot-5M → v5 → human BC fine-tune" as a secondary arm, only if the pilot learns by 5M. Pilot skills were learned against 16-card scripts and may anchor the policy too much.

## 4. Human-prior dataset pipeline

1. **Selection.** Keep perspectives whose own deck is in the actor scope (P16 or C56) and whose opponent deck is in the engine scope. Keep both towers as Princess in v1. Keep game mode as metadata: ranked/Path of Legends is 207k of 252k matches.
2. **Re-simulation.** Extend `resim_pilot.py` into a deterministic replayer:
   - base forms, nominal L11, both sides' plays at the exact recorded 20 Hz ticks (equal to native ticks);
   - hand cycle reconstructed from play order, logging forced-hand events (0.15–0.6%) and elixir top-ups (<0.15%);
   - champion `activate_ability` is attributed only when the side has exactly one champion and no hero forms; otherwise the ability label is missing.

   Running the same replay twice must produce identical bytes.
3. **Cut at the first contradiction.**
   - Hard contradictions: the simulation destroys a tower that is standing in the real game; a pocket placement is made while the simulated tower is alive; a recorded placement is still rejected after nudging; a forced hand; an elixir shortfall.
   - Supervision ends at the last 5-tick boundary before the first hard contradiction, and `expert_action_supervision_valid` is set false after it.
   - A real kill that never happens in simulation has no timestamp, so the whole match is flagged and down-weighted instead of cut.
   - Expected retention is roughly 85–90% of decisions, since the median first contradiction is at 0.89–0.97 of the match. Measure it.
4. **Observations and actions under the public contract.**
   - At every 5-tick boundary (250 ms) for the perspective side, run the v5 `StructuredObservationBuilder` and `PublicActionMaskBuilder`, the same "every-five-tick-opportunity" sampling as the scripted adapter.
   - A play is labelled at boundary floor(tick/5)·5 with the slot of the card in the reconstructed hand and the nearest legal tile.
   - Store the original millitile coordinates, the projection distance and the label's tick offset.
   - Record whether the label is legal under the mask; the illegal-label rate is a QA gate.
   - A second play in the same window moves to the next boundary and is flagged.
   - Previous own action is recorded; previous reward is zero.
   - Output uses the existing per-game npz schema (`scripted-demonstrations/game-*.npz`, validated by `PublicPolicySequence`), so `imitation.py` loads it unchanged. Human provenance goes in `metadata_json`: tag, shard, mode, forms per slot, original levels, contradiction time and label offsets.
5. **Deck/match split.**
   - The corpus has no player identity. Use a *player proxy*: the exact team deck including forms, levels and tower troop. Consecutive matches in a shard share it.
   - Group by proxy, then by base-deck archetype cluster (for example 8-card Jaccard ≥ 0.75), keeping parents and derivatives together as the strategy requires.
   - Roles by group: 90% train, 5% development, 5% human evaluation. Hold out whole archetype families as an out-of-distribution slice.
   - Freeze the role file, with its hash, before any fitting.
6. **Weighting** (frozen per arm; ablations in brackets):

   | Factor | Rule |
   |---|---|
   | After first contradiction | 0 [tail at 0.25] |
   | Match with an unreproduced real kill | 0.5 [1.0] |
   | Plays of cards recorded as evo/hero | 0.5 [1.0] |
   | Waits | Subsample to 25% with inverse-probability weight 4, so the timing prior is unchanged (strategy: "Correct timing-prior changes") |
   | Deck/proxy balance | Square-root cap per player proxy and per archetype, so Hog 2.6 mirrors and meta decks do not dominate |
   | Mode | Ranked/challenge 1.0, friendly 0.5 |
   | Human vs other supervision | A single coefficient frozen in the run config; low weight per the strategy |

7. **Held-out human evaluation set.** This is the 5% group split above.
   - Metrics:
     - play/wait log-likelihood per 250 ms decision;
     - top-1/top-3 card accuracy given a play, against frequency and uniform-legal baselines;
     - tile negative log-likelihood and median tile error;
     - timing hazard calibration.
   - Report by phase, archetype, mode, a P16 slice and an out-of-distribution archetype slice.
   - Freeze it before any human fitting. The pilot checkpoints can be scored on the P16 slice at no extra cost.
   - The camera-derived KataCR `katacr_hog26_human_v1` is one-sided; use it only as a cross-domain check on the Hog 2.6 slice.
   - QA gates before fitting: placement acceptance ≥99%, illegal-label rate, forced-hand rate, retention, byte determinism and the contract validators.

**Size.**
- The scripted corpus takes about 190 B per decision compressed (227 KB for 1,201 decisions).
- C56 under the S122 engine is about 88.7k perspectives × about 900 boundaries × 0.85 retention ≈ 68M decisions, or about 13 GB with every wait.
- Subsampling waits to 25% gives about 20M rows, around 4 GB.
- P16 is about 1/6 of that.

**Extraction CPU.**
- Re-simulation measured about 3 s per match (100 matches in 290 s, single thread).
- With observations and masks at about 1,800 boundaries for both sides, I estimate 8–12 s per match; measure this on 100 matches first.
- P16: 30–50 CPU-h. C56: 130–270 CPU-h. The full S122 corpus: 560–840 CPU-h.

## 5. Training recipe

**Stage 0: P16 human-prior pre-test (recommended first).**
- Contract v5 vocabulary, P16 hand scope. Everything else matches the pilot: actor, opponents, PPO recipe, 64 envs and the evaluation protocol.
- Arm H16: BC on P16 perspectives, then PPO, 3 seeds, a diagnostic at 1M and a comparison at 5M against the pilot's scripted and scratch arms.
- Cost: 15M decisions, about 2 days on the Mac after the pilot, or 3M decisions (about 10 h) for a 1M-only read.
- This isolates the value of the human prior from the cost of scope expansion. It also tests whether a human prior relieves the pilot's card-starvation and entropy-collapse alarms.

**Stage 1: C56 prior.**
- Primary is H-C56: BC on C56 perspectives.
- An optional ablation, H-broad, pre-trains on all S122 perspectives and then fine-tunes on C56. It adds more data on shared timing, placement and defence, at about 4× extraction and BC cost.
- Use truncated-BPTT chunks with burn-in for BC. For scale: the pilot's full-prefix fit ran about 285 samples/s on CPU (410k samples in 24 min). At that speed, C56 at 20M rows × 2 epochs would take about 39 CPU-h per seed. That is the main reason to rent a GPU for BC.

**Stage 2: C56 PPO arms.** Same recipe and budget for each, 3 seeds × 5M:
- **H:** human-prior initialization;
- **S:** scripted warm start with the C56 controllers (2c);
- **Z:** scratch;
- optional: H with a decaying KL anchor to the prior, as an ablation only. The pilot's `ppo_update` is admission-bound.

For the first 1M decisions, the opponent mixture is scripts plus initial policies, and it includes the frozen human-prior policy as a fixed opponent. After that, the strategy's 25/50/25 league schedule applies, with PFSP and exploiters later as written.

**How to tell whether the human prior helps.** All measures are frozen before outcomes:
1. Primary: mean match score against the fixed reacting pool at 1M and 5M, with paired seats, 512 games per finalist and clustered CIs. H must beat S and Z by ≥0.05 with the 95% interval above zero, in at least 2 of 3 seeds.
2. Sample efficiency: decisions H needs to reach S's 5M score.
3. Human-likeness drift: held-out human negative log-likelihood and accuracy across PPO checkpoints.
4. Card-usage health: monitor alarms and card shares.
5. Tier B: material failures and exploit-probe triggers per arm.
6. Held-out deck families and mixed levels, as separate slices.
7. Results against the frozen human-prior opponent, reported separately because the comparison is circular.

**Decision rule.**
- Adopt H as the main-lineage initialization if it meets measure 1 against S, or matches S with no subgroup collapse and better sample efficiency.
- If H does no better than Z, drop the human prior from the training path and keep the dataset as an evaluation set only.

## 6. Admission

**Rule proposal for the open question in section 0.**
- Offline human BC may run before the broadened Tier A, because it only produces a candidate initialization.
- No PPO, league play or evaluation claim on C56 cards until the relevant bundle is admitted.
- Stage 0 (P16 hand scope) needs an explicit coordinator decision. Its observations include units from outside the 16 cards, but its training games are fully inside the v7-admitted scope.

**Broadened Tier A.**
- **Root generator v3.**
  - Takes a card-scope parameter.
  - Draws deck families from the most frequent *human* C56 decks, which gives the strategy's "recognizable professional-style decks", grouped by archetype instead of the 4 hard-coded decks.
  - Stratifies focal cards by bundle and adds mechanic contexts such as air threat, building pull, spell value and enemy-side deployment.
  - Keeps all existing rules: one root per independent episode, seat balance, no replacement and retained failures.
- **Option A (recommended): one 32-family attempt per bundle B1–B4.** Each new card in the bundle is focal 2–4 times, and P16 cards fill opponent decks.
  - Native time per attempt: 32 × 4 candidates × 4 conditions = 512 branches; at 260 s each over 8 emulators that is 4.6 h. v7's real end-to-end wall time, including prefixes and technical reruns, was about 8 h.
  - Four bundles take about 18.5 h of branch time, or about 32 h of wall time if every attempt passes first time.
  - The 16-card scope needed 7 attempts, two blocked by single material failures. Budget 2 attempts per bundle: about 64 h of emulator wall time.
  - Add a new identical-repetition study per new runtime and about 24 native scenario checks (about 1 emulator-day).
  - Expect 4–7 calendar days with repairs in between.
  - Each bundle is admitted separately; that is the strategy's "admit new mechanic bundles before training on them". Training on C56 needs all four, or PPO is restricted to the admitted bundles.
- **Option B: a single 64-family C56 attempt.** Each card is focal at least once, with extra focal requests for high-coverage cards.
  - 1,024 branches: 9.2 h of branch time, about 14 h of wall time.
  - Zero failures give an upper bound of about 4.6%.
  - However, one material failure blocks all 40 cards, and per-card coverage is thin.
- **Not recommended:** one 32-family attempt across all 56 cards. Most new cards would never be focal.
- **Mixed levels (10–12):** the level-extension probes and adaptation study must be redone for the new cards before mixed-level training on them.

**Tier B implications.**
- It needs the C56 scripted controllers as continuations, and `load_frozen_policy` must accept the v5 vocabulary.
- *Representative block.* At 56 cards, 30 roots stratified by deck × phase × seat are too few for bundle coverage. Propose 60 roots: at least 30 with non-wait coverage, upper bound about 4.9%, 960 branches, about 8.7 h on 8 emulators. Alternatively, 30 roots per bundle.
- *Targeted probes.* Add tornado pull, spawner building pull, Royal Ghost invisibility, Miner/Goblin Barrel enemy-side deployment, Golem/Balloon death effects, E-Spirit/Lightning chain stun, Firecracker recoil, inferno ramp and champion abilities. About 10 kinds × 4 roots gives 640 branches, about 5.8 h.
- Each arm's frozen checkpoint needs its own Tier B before promotion, so budget about 15 h of emulator time per promoted candidate.

## 7. Timeline, compute and order relative to the pilot

**Pilot state** (read at 01:47Z Oct 1):

| Seed | State |
|---|---|
| s2901 scripted | 0.68M decisions |
| s2902 scripted | 0.09M (critic warm-up) |
| s2903 | Warm start |

Three concurrent CPU seeds run about 29.5 decisions/s each. Each seed runs scripted then scratch, 10M decisions in total, followed by evaluation.

My estimates:

| Milestone | Estimate |
|---|---|
| First 1M diagnostic (s2901/scripted) | About Oct 1 |
| s2901/scripted 5M | About Oct 2–3 |
| Last scratch arm 5M | About Oct 5–6 |
| Pilot evaluation complete | About Oct 6–7 |

The CPU is saturated (load about 10.5), so heavy CPU work and emulators wait for the pilot.

| Phase | Window (est.) | Work | Where |
|---|---|---|---|
| A | Now → first 1M diagnostics (Oct 1–2) | Your decisions (below); strategy amendment draft; v5 spec; freeze C56 list | Desk only |
| B | Pilot 1M → 5M (Oct 2–6) | Implement in main, not in pilot snapshots: replayer and extraction (tested on 100–500 matches, `nice -n 15`, 1 core), v5 contract and upgrade tool, scalar fixes for the 5 broken cards and heal-spirit, C56 scripted controllers, root generator v3; freeze the human evaluation set. Optional: full P16 + C56 extraction on rented CPU | Mac (light); rented CPU, about 160–320 CPU-h, about 3–5 h on 64 cores |
| C | Pilot 5M read (Oct 6–7) | Go/no-go for broad PPO from the pilot's 5M results and its Tier B | – |
| D | Oct 7–10 | Stage 0 (H16 BC + PPO, 3×1M ≈ 10 h, or 3×5M ≈ 2 days); native scenario checks for C56 and the broken cards (about 1–2 emulator-days plus repairs) | Mac (emulators); BC on rented GPU or Mac MPS |
| E | Oct 10–16 | Broadened Tier A bundles (4–7 days with repairs); C56 BC prior | Mac emulators (critical path); rented GPU for BC (hours) or Mac (about 1–2 days per seed) |
| F | Oct 16–26 (rented) or to about Nov 5 (Mac) | C56 PPO: 3 arms × 3 seeds × 5M = 45M decisions, then evaluation; then broadened Tier B (about 15 h emulator per candidate); then the league | Mac at 88–115 decisions/s aggregate gives 4.5–6 days plus 1–2 days of evaluation. Rented: about 2–3 days, if the CUDA path is admitted and benchmarked |

**Compute summary for the C56 path:**

| Item | CPU-h | GPU-h | Emulator wall-h |
|---|---|---|---|
| Extraction (P16 + C56) | 160–320 | – | – |
| Extraction (optional full S122) | 560–840 | – | – |
| BC (3 seeds) | – | 5–15 rented (Mac CPU about 120) | – |
| PPO (45M) | Strategy ceiling scaled to 3 arms: about 6,900 core-h | About 108 | – |
| Native checks + Tier A (option A) | – | – | About 90 |
| Tier B per promoted candidate | – | – | About 15 |

Renting shortens extraction, BC and PPO from weeks to days. It does not shorten the emulator path: remote native emulation is unverified, so the Mac stays the bottleneck for admission. A CUDA learner also needs an admitted code change, since `CouncilPilotConfig` limits the device to cpu/mps.

## Open questions for you

1. **Scope:** approve C56 with the two-scope design (engine 122 / actor 56)? Any swaps, such as battle-ram, zappies or inferno-dragon in place of archer-queen, royal-delivery or fire-spirit?
2. **Champions:** keep mighty-miner, goblinstein and archer-queen (which needs the ability action in v5) or drop them to C53?
3. **Strategy amendment:** allow re-simulated IL_Replay labels as a low-weight prior, and allow offline BC before the broadened Tier A (section 6 rule)?
4. **Order:** run the Stage 0 P16 human-prior pre-test before C56 (recommended), or go straight to C56?
5. **Initialization:** primary human arm from fresh v5 weights (recommended), or transferred from the pilot at 5M?
6. **Forms and levels:** base substitution with evo/hero plays at 0.5 weight; treat L16 as nominal L11; exclude tower-troop matches in v1?
7. **Compute:** approve rented CPU for extraction (about 160–320 CPU-h for C56; up to about 840 more for full S122) and a rented GPU for BC/PPO, including the CUDA admission change? Or stay Mac-only and accept about 4–5 weeks?
8. **Tier A design:** per-bundle 32-family attempts (A, recommended) or one 64-family attempt (B)? What emulator-day budget?
9. **Broad prior:** also train the H-broad ablation on all S122 perspectives (about 4× extraction and BC)?
10. **Opponents and evaluation:** may the frozen human-prior policy join the opponent pool and serve as a separately reported evaluation opponent?
