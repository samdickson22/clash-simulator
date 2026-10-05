# P16 human-imitation starting policy from IL_Replay

Status: research artifact under the 2026-10-01 amendment (`../amendments/2026-10-01-search-and-human-prior.md`). This is not a Tier A admitted pilot arm. Every checkpoint here carries `"provenance": "human-prior research artifact; not a Tier A admitted pilot arm"`.

Work ran 2026-10-01 to 2026-10-02 on CPU, with at most 4 processes under `nice -n 10`. The frozen runtime `m0/runtime-snapshots/pilot-runtime-v4` supplied the engine, observation builder, mask builder, model and evaluator. Nothing under `runtime-snapshots/` or `pilot/` was modified, and no existing source module changed. New code:

- `src/clasher/rl/human_replay_demonstrations.py`: replays recordings into decision rows.
- `src/clasher/rl/human_replay_bc.py`: streaming BC fit and per-head metrics.
- `tests/test_human_replay_demonstrations.py` and `tests/test_human_replay_bc.py`: 18 tests, all passing.
- `scripts/`: drivers. `PROGRESS.md` holds the exact commands.

## Short answer

The natural-weight human clone (`human-bc-natural`) beats the scripted warm start on the same 192 games: **40/192 vs 23/192**. That is +8.9 points (95% CI +1.4 to +16.2). Paired McNemar on identical matchup seeds gives p = 0.019, though this is one of three pre-declared variants and the p-value is not corrected for that.

- **hog26 deck:** 18/96 vs 9/96. This is the best hog26 result of any checkpoint so far, including the 1M PPO checkpoint (5/96 on these seeds).
- **Holdout decks:** 22/96 vs 14/96. The intervals overlap, and it is clearly below the 1M checkpoint's 38/96.
- **Behaviour:** the clone reproduces human tempo almost exactly: about 10 plays/min, median elixir at play about 7, and the human play-when-held profile by cost.
- **Limits:**
  - The gain is small in absolute terms.
  - The corpus is 99.7% Hog 2.6, so the clone is a Hog 2.6 specialist and plays holdout decks only somewhat better than the scripted clone.
  - It comes from one seed.
  - The two variants that change the natural prior did not help: down-weighting waits, and winners-only fine-tuning.

## 1. Pipeline

1. **Data.** `scripts/fetch_payloads.py` re-streamed all 52 replay shards of `VanguardX101/IL_Replay` at revision `059d43a0…`. Shard 0 came from the local copy. Every shard matched its manifest SHA-256.
   - It kept only matches with a P16 perspective: own 8 base cards inside the 16 pilot cards, both decks inside the S117 engine scope, and plays from both sides. That is 10,766 matches stored as `data/payloads/` (63 MB).
2. **Replay.** `human_replay_demonstrations.reconstruct_perspective` runs one perspective at a time:
   - **Setup.** Scalar engine with base forms, level 11 and Princess towers. Each side's hand is reconstructed from first-play order, with the four opening slots shuffled by a fixed per-match seed so slot position carries no label.
   - **Opponent.** Opponent plays are replayed at their exact tick, with the scan's relaxations: hand forcing, tiny top-ups, nudges and champion abilities. Each relaxation is counted.
   - **Learner rows.** Every 5-tick decision step (250 ms) records the pilot builder's public-v4 actor observation (`project_council_public_observation`), the public action mask and the label. The layout is the `scripted_demonstrations.collect_public_script_game` row format: pre-decision observation, mask and label on one row; `previous_actions` = labels shifted by one; zero previous rewards; a terminal context row that is never supervised.
   - **Play labels.** A recorded own play is labelled on the step at or just before its tick, as slot of the card in hand × tile. The tile is the world coordinate rounded to the 500-unit lattice and then floored, mirrored for seat 1, so the learner is always the canonical bottom seat.
   - **Late plays.** If the card is not yet affordable on that step but the tick falls inside the interval, the play moves to the next step, at most 4 ticks late. This happened to 1,991 plays (0.6%).
   - **Execution.** Own plays execute through the pilot action space exactly as in the pilot environment.
3. **Stopping rules.** A perspective stops at the first of the following (row counts in section 2):
   - **Tower contradiction.**
     - The sim destroys a tower the recording shows standing.
     - A recorded territory-restricted placement in the enemy half lands while the sim tower on that lane stands (the "pocket" rule from `resim_pilot.py`).
     - An opponent placement the engine rejects even after nudging.
   - **Illegal own action.**
     - The card is not in the reconstructed hand.
     - Elixir is short by more than 0.05.
     - The recorded tile is outside the public mask and not within one tile of a legal tile of the same card (see deviation 2).
     - The engine rejects a placement the mask allowed.
   - **End of recording.** Rows stop at the recorded end (tail correction below), or the sim match ended.
4. **Storage.** Compact, exact shards live in `data/recon/` (608 MB for 7.2M rows). Padding and derivable confidence fields are dropped only after an assertion that they are derivable, and masks are deduplicated. `load_human_replay_shard(...).arrays()` returns exactly the arrays `imitation_arrays()` produced; a test checks the round trip.
   - Per-perspective metadata: match id, side, recorded result for this side, crowns, cut reason, tick and detail, forms of both decks, both decks, levels, tower troops, all relaxation counters, and per-card play counts.
   - Validation split: 10% of matches by `sha256(match_id)`, both perspectives together.

**Deviations from the scan and the brief**, each found in the data:

1. **The scan's tower contradiction rule was wrong.** IL_Replay's `princess_left/right` are positional (surviving towers listed first), not lanes. All 2,881 exactly-one-down sides in the first 20 shards report `princess_right == 0`.
   - `resim_pilot.py` therefore treated half of all one-tower kills as being on the wrong lane.
   - The replay now uses tower counts, plus lane evidence from pocket placements. It also applies the sudden-death rule: a match that went to overtime had level crowns at 180 s, so no unequal tower count is allowed before then.
2. **The pilot public mask is stricter than the game near towers.** It blocks a 5×5 area around each Princess tower, because a float32 radius of 1.0000000298 gives footprint 4; the game blocks 3×3.
   - 5.7% of labelled human plays (20,090) sit in that ring, mostly Musketeer and Hog Rider behind the tower.
   - Cutting there, as the brief literally asks, would keep only 57% of rows (4.12M vs 7.20M). Such plays are instead labelled as the nearest legal tile (always 1 tile away; 1.41 when diagonal) and still executed at the recorded point.
   - `label_projection_distance` and `first_projected_row` are stored, so the strict-cut corpus is recoverable. It was not fitted.
3. **Recorded timeline length.** The recorded timeline runs 91 ticks past the last playable tick: 1,584 matches last exactly 184.55 s, and no play is closer than 102 ticks to the end. Rows therefore stop at timeline − 101 ticks.
4. **Unaccepted mechanics.** Furnace is a back-row troop in the current game but a building in our engine. Its placements are rejected and cut 617 perspectives. Champion abilities succeed for only 598 of 11,732 opponent ability events. Own ability events (none in P16) are ignored, because the ability action is always masked in contract v4.

## 2. Yields

| | count |
|---|---:|
| P16 perspectives / matches | **11,028** / 10,766 (262 matches give both perspectives) |
| Hog 2.6 perspectives | **10,994** (99.7%); the rest are 34 near-Hog decks |
| Decision rows (supervised) | 7,204,187 (7,201,925) |
| Supervised play rows | **352,260**, which is 60.0% of the 586,747 recorded own plays |
| Rows per perspective, p5 / p50 / p95 | 183 / 667 / 1,148 |
| Cut point as a fraction of the match, p25 / p50 / p75 | 0.53 / 0.77 / 0.97 |
| Validation split | 1,015 perspectives, 652,424 rows |
| Recorded result of learner (win / loss / draw) | 5,705 / 5,309 / 14 |

Cut reasons:

| Reason | Perspectives | Median cut point (fraction of match) |
|---|---:|---:|
| Sim kills a tower standing in the recording (2,891 learner towers, 1,204 opponent towers) | 4,095 | 0.63 |
| Sim match ended (3 crowns, or regulation with a crown lead) | 2,131 | 0.95 |
| Recorded end | 1,601 | 1.00 |
| Own tile masked and not adjacent (1,493 are Cannon: the mask's building-footprint guard) | 1,496 | 0.61 |
| Opponent placement rejected (617 Furnace) | 752 | 0.22 |
| Pocket placement while the sim tower is alive (406 opponent, 313 own) | 719 | 0.88 |
| Own placement rejected by the engine after the mask allowed it (Log 55, Fireball 36) | 131 | 0.69 |
| Own elixir short by more than 0.05 (median 0.79) | 103 | 0.35 |

Per-card supervised plays:

| Card | Plays |
|---|---:|
| IceSpirit | 57,583 |
| Skeletons | 55,629 |
| IceGolem | 54,099 |
| HogRider | 47,145 |
| Musketeer | 42,376 |
| Log | 40,280 |
| Cannon | 35,539 |
| Fireball | 19,441 |
| Knight | 80 |
| Goblins | 36 |
| Tesla | 20 |
| Archers | 17 |
| Zap | 10 |
| Giant | 4 |
| DarkPrince | 1 |
| Prince | 0 |

Other replay statistics:

- Own elixir top-ups (all ≤ 0.05): 16 in total, summing to 0.22 elixir. Opponent top-ups: 80, summing to 1.6 elixir. Opponent hand forcing: 0.
- The elixir alignment is two-sided. The slack between sim elixir and card cost at a recorded play has a sharp edge at 0 and is never negative, so the economy and timing align.
- Fidelity gaps:
  - Deck slots: 37% of own slots and 34% of opponent slots are evo/hero forms played as base.
  - Levels: decks are mostly L16, played at L11.
  - Tower troops: 7.1% of perspectives have a non-Princess tower troop on one side.
  - Only 26 perspectives are all-base on both sides.

**Unknown cards.** The builder maps any entity whose serialized identity is not in the 36-token pilot vocabulary to token 1 `<unknown>`. That token has zero card-stat and semantic descriptors and a learned embedding. The entity row keeps its public features: position, side, kind, HP fraction, speed, range, sight, collision radius, facing and damage. About 18% of outside-vocabulary entity calls resolve to an existing token through a shared payload name, for example:

- Skeleton Army, Witch, Graveyard and Tombstone skeletons → `Skeleton`
- Electro Spirit, Electro Wizard, Zappies and Electro Giant stuns → `ZapFreeze`
- Ice Wizard slow → `IceWizardSlowDown`

Unknown fractions:

| Token set | Unknown |
|---|---:|
| All entity tokens (towers included) | 13.8% |
| Enemy entity tokens | 26.6% |
| Enemy troop bodies | 61.0% |
| Enemy projectiles | 41.5% |
| Enemy area effects | 62.1% |
| Opponent history slots | 69.0% |
| Opponent seen-card slots | 68.1% |

Source: `results/corpus_stats.json` and `results/sanity_checks.json`.

## 3. Sanity checks (before fitting)

`scripts/sanity_checks.py` ran on 200 random perspectives: 127,973 rows and 6,149 plays. Output is in `results/sanity_checks.json`.

- **(a) Legality.** 0 of 127,925 supervised labels are outside their stored mask. In 18,322 rows (every play row plus every 10th row), the stored mask was rebuilt from the stored public row alone by an uncached `PublicActionMaskBuilder`, with 0 mismatches.
- **(b) Alignment**, in the style of `test_scripted_demo_wait_rows.py`:
  - Each perspective was re-simulated. Every stored hand equals the engine hand captured just before the decision, and every array is byte-identical to the stored shard, so the replay is deterministic.
  - Each labelled slot holds the recorded card, and that card has left the hand on the next row. No supervised wait coincides with a card leaving the hand.
  - Labels sit on the step at or before the recorded tick; 39 plays sit one step late, under the deferral rule.
  - The label tile is the recorded tile or its declared adjacent projection. All 362 projections lie within one tile; the 4 listed checker "failures" were diagonal projections at distance 1.41, flagged before the threshold was corrected.
  - `previous_actions` = labels shifted by one; ticks advance in 5-tick steps; `board_rotated` matches the seat.
- **(c) Human statistics versus the pilot diagnosis** (`pilot/diagnosis-1M`), from the stored rows:
  - Human wait fraction is 0.951 overall and 0.949 when a play is legal. The scripted teachers' noop-when-playable is 0.83; the warm start is 0.85 at update 1 and the 1M policy about 0.03 in training.
  - Median elixir at play is 7.1 for humans, against 3.0 for teachers and 2.1 for the warm start.
  - The remaining human figures are in the behaviour table in section 5.

## 4. Behaviour cloning

- **Architecture.** Exactly the pilot's: `council_pilot.build_council_model_config`, 2,604,979 parameters, the 36-token vocabulary, public contract v4, semantics v4, 4 history slots, 8 seen-card slots, LSTM 256.
- **Initialization.** The same seed (2903), so the initial weights equal the pilot s2903 `scripted-random-control.pt` bit for bit (checked).
- **Loss.** The scripted warm start's loss: cross-entropy on the masked joint log-probabilities, as in `fit_imitation_corpus(imitation_objective="exact")`. AdamW at lr 1e-4, gradient clip 0.5, 128-step sequences, 1 epoch, forced rows included.
- **Recurrence.** At 7.2M rows the corpus is 14 times the scripted corpus and does not fit the in-memory full-prefix replay. Episodes are therefore unrolled in order on 8 streams, with the LSTM state carried between 128-row chunks (truncated BPTT).
- **Speed.** Wait rows skip the tile decoder; their joint loss does not depend on location logits, and a test confirms the gradients are equal. Throughput was about 400 rows/s per fit at 2 threads, or 4.4 h for 6.55M training rows.
- **Critic.** No value target exists on this fit path (`fit_imitation_corpus` has none either), so the critic is untrained. The recorded result is stored per row as `recorded_outcome` for a later value fit.

Variants (each declared before evaluation):

| Variant | Weighting | Checkpoint (sha256) |
|---|---|---|
| natural | all supervised rows weight 1 (the scripted warm start's handling) | `checkpoints/human-bc-natural-seed2903.pt` `49be1480…b482` |
| wait02 | waits more than 4 steps (1 s) before a play weigh 0.2; plays and the 4 steps before them weigh 1 | `checkpoints/human-bc-wait02-seed2903.pt` `2139ef96…1441` |
| natural-winners | natural, then fine-tuned on winners' perspectives only (filtered BC): 16 pools, 806,831 rows | `checkpoints/human-bc-natural-winners-seed2903.pt` `301fa1c4…b459` |

Validation on the first 200 held-out perspectives (124,871 rows; 6,053 plays), with recurrent state carried through each whole episode. Definitions:

- "when" = play vs wait on rows where a card is playable (120,705 rows).
- "card" = slot given that a play happened.
- "tile" = location given the recorded slot.

| Metric | random init | scripted warm start | v7r2 1M | **natural** | wait02 | natural-winners |
|---|---:|---:|---:|---:|---:|---:|
| joint loss (nats) | 1.661 | 1.381 | 2.541 | **0.376** | 0.407 | 0.377 |
| when loss | 1.389 | 0.906 | 2.184 | **0.171** | 0.190 | 0.172 |
| p(wait), human waited | 0.24 | 0.51 | 0.20 | 0.956 | 0.908 | 0.962 |
| p(wait), human played | 0.23 | 0.44 | 0.16 | 0.894 | 0.829 | 0.902 |
| card loss / accuracy | 1.30 / 0.29 | 1.74 / 0.39 | 2.57 / 0.40 | 0.98 / 0.58 | 0.97 / 0.57 | **0.96 / 0.59** |
| card accuracy, ≥2 playable | 0.26 | 0.38 | 0.38 | 0.56 | 0.56 | 0.57 |
| tile loss | 5.29 | 8.70 | 6.29 | **3.36** | 3.63 | 3.38 |
| tile top-1 / top-5 | 0.004 / 0.016 | 0.007 / 0.062 | 0.041 / 0.086 | **0.221 / 0.491** | 0.153 / 0.442 | 0.214 / 0.492 |
| tile within 1 / mean distance | 0.05 / 9.9 | 0.14 / 7.0 | 0.11 / 8.0 | **0.42 / 4.3** | 0.32 / 6.0 | 0.41 / 4.5 |

The "when" decision stays hard. Even the best model puts p(wait) at 0.89 on rows where the human played, against 0.96 where the human waited, so play timing is mostly a calibrated hazard rather than a sharp prediction. That supports the review's call for a time-to-next-action target, which this architecture has no head for.

## 5. Evaluation

Setup:

- **Cells.** The pilot diagnostic cells exactly, as in `council_pilot.evaluation_commands(final=False)`: `clasher.rl.eval --opponent public-script --public-script-style {balanced,pressure,defense} --level-mode nominal --games 32 --stochastic`.
  - Candidate decks: development holdout decks and the hog26 deployment deck.
  - Opponent decks: training decks.
  - Decision interval 5, max ticks 6001.
- **Runtime.** The frozen `pilot-runtime-v4`, with cwd = runtime root, `CLASHER_ROOT=<runtime>` and `PYTHONPATH=<runtime>/src:<runtime>/scripts`. No metadata had to be added; eval accepted the checkpoints as written.
- **Seeds.** `770031 + 1_000_003·(role·6 + style + 12)`, i.e. 12,770,067 / 13,770,070 / 14,770,073 (holdout) and 18,770,085 / 19,770,088 / 20,770,091 (hog26). The pilot uses base 9413 (diagnostic 12,009,449–20,009,473 and final cells).
- **Baselines.** Both were re-run on these same seeds, so every row below is paired game by game.
- **Commitment.** Every pre-declared checkpoint was evaluated once and all results are reported.

| Checkpoint | Holdout wins / 96 (bal / pres / def) | Wilson 95% | hog26 wins / 96 (bal / pres / def) | Wilson 95% |
|---|---|---|---|---|
| scripted warm start s2903 | 14 (6 / 2 / 6) | 8.9–23.0% | 9 (1 / 4 / 4) | 5.0–16.9% |
| v7r2 1M s2903 | 38 (12 / 16 / 10) | 30.4–49.6% | 5 (1 / 1 / 3) | 2.2–11.6% |
| **human-bc-natural** | **22** (10 / 5 / 7) | 15.6–32.3% | **18** (8 / 3 / 7) | 12.2–27.7% |
| human-bc-wait02 | 15 (6 / 5 / 4) | 9.7–24.2% | 6 (5 / 0 / 1) | 2.9–13.0% |
| human-bc-natural-winners | 13 (7 / 2 / 4) | 8.1–21.8% | 15 (7 / 3 / 5) | 9.7–24.2% |

On the pilot's own diagnostic seeds the baselines were:

- scripted warm start: 16–19/96 holdout and 5–11/96 hog26 across seeds; s2903 scored 19 and 11;
- s2903 1M: 46/96 and 8/96.

Paired comparisons (`results/paired_comparisons.json`; difference CI is Newcombe; p is exact McNemar on the discordant games):

| A vs B | Holdout | hog26 | Both (192 games) |
|---|---|---|---|
| natural vs scripted | +8.3 pts [−2.8, +19.3], p = 0.15 | +9.4 [−0.6, +19.3], p = 0.093 | **+8.9 [+1.4, +16.2], p = 0.019** |
| natural vs 1M | −16.7 [−29.0, −3.5], p = 0.007 | **+13.5 [+4.4, +23.0], p = 0.007** | −1.6 [−9.8, +6.7], p = 0.78 |
| wait02 vs scripted | +1.0, p = 1.0 | −3.1, p = 0.61 | −1.0, p = 0.86 |
| winners vs scripted | −1.0, p = 1.0 | +6.3, p = 0.24 | +2.6, p = 0.51 |
| winners vs natural | −9.4, p = 0.064 | −3.1, p = 0.70 | −6.3, p = 0.10 |

### Behaviour comparison

Policy figures come from decision traces of the first 8 games of each cell (24 games per role). Human figures come from the reconstructed corpus, which is 99.7% Hog 2.6, so it compares with the hog26 role. "Play-when-held" = plays of cards at that cost ÷ hand appearances of such cards at play decisions (the diagnosis's definition).

| | Humans (corpus) | natural, hog26 | natural, holdout | scripted WS, hog26 | scripted WS, holdout | 1M, hog26 | 1M, holdout | wait02, hog26 | winners, hog26 |
|---|---|---|---|---|---|---|---|---|---|
| plays / minute | 11.2 | 10.4 | 9.3 | 15.9 | 12.5 | 12.6 | 9.9 | 13.6 | 11.1 |
| plays / match | – | 31.2 | 33.4 | 54.3 | 50.3 | 37.6 | 32.1 | 41.2 | 33.0 |
| wait when a play is legal | 0.949 | 0.955 | 0.957 | 0.769 | 0.863 | 0.892 | 0.927 | 0.928 | 0.953 |
| elixir at play, median (p25–p75) | 7.1 (5.2–9.1) | 7.0 (5.2–9.0) | 7.3 (5.5–9.1) | 2.1 (1.2–3.1) | 3.2 (2.4–4.1) | 2.9 (1.6–4.1) | 4.0 (3.0–4.5) | 4.0 (2.7–5.5) | 7.4 (5.7–8.9) |
| play-when-held, cost 1 / 2 / 3 / 4 | .41 / .28 / .18 / .18 | .45 / .28 / .20 / .17 | .40 / .27 / .29 / .19 | .91 / .47 / .47 / .04 | .87 / .31 / .51 / .10 | .75 / .19 / .11 / .19 | .62 / .11 / .52 / .22 | .62 / .43 / .20 / .10 | .42 / .35 / .18 / .16 |
| mean play cost | 2.40 | 2.38 | 2.97 | 1.98 | 2.71 | 2.34 | 3.04 | 2.16 | 2.36 |
| share cost ≤ 2 / ≥ 4 | .59 / .31 | .59 / .30 | .33 / .35 | .73 / .11 | .38 / .20 | .60 / .33 | .24 / .35 | .68 / .21 | .61 / .29 |

hog26 card shares:

| Card | Humans | natural | scripted WS | 1M |
|---|---:|---:|---:|---:|
| IceSpirit | .163 | .163 | .200 | .203 |
| Skeletons | .158 | .166 | .202 | .184 |
| IceGolem | .154 | .140 | .199 | .197 |
| HogRider | .134 | .135 | .075 | .151 |
| Musketeer | .120 | .120 | .028 | .166 |
| Log | .114 | .120 | .127 | .016 |
| Cannon | .101 | .111 | .166 | .075 |
| Fireball | .055 | .044 | .003 | .009 |

Full per-role statistics, including per-card play-when-held and holdout card shares, are in `results/evaluation-*.json`.

## 6. Assessment

**Does the human prior beat the scripted warm start?** Yes, modestly.

- **Wins.** The natural clone wins 40/192 against 23/192 on paired games (+8.9 points; CI +1.4 to +16.2). The gain is concentrated on the hog26 deck, the deck it was trained on: 18 vs 9.
- **Behaviour.** It is far more human. It banks elixir to a median of 7 instead of spending at 2–3. It plays Hog Rider, Musketeer and Fireball at human rates where the scripted clone almost never plays the 4-cost cards. Its tile top-5 accuracy on held-out human placements is 49% (scripted 6%).
- **Starting point.** This is the profile the pilot diagnosis said was "never present to lose". As a PPO starting point it removes the spend-at-2-elixir origin of the v7r1 collapse. It would also give the KL anchor a target that is not itself the cheap-spam policy.
- **Holdout decks.** It is not a strong player. Against these scripts it still loses about 80% of games. On holdout decks it is no better than the 1M PPO checkpoint, which was trained on those deck families, and is significantly worse (22 vs 38).
- **Evidence strength.** One seed. The whole-run McNemar p of 0.019 should be read against three pre-declared variants. A Bonferroni ×3 gives about 0.056.

**What did not help.**

- **wait02 (down-weighting waits to 0.2).** It made the policy play earlier: wait-when-playable 0.93, median elixir at play 4.0. That is exactly the cheap-spending direction, and it lost the hog26 gain (6/96). The evidence favours the natural timing prior here.
- **Winners-only fine-tuning.** Not significant against natural, but in the wrong direction (28 vs 40). Recorded winners in these matches won with evo/L16 units the replay does not have, so filtering by recorded result selects on facts the observations do not contain.

**What limits it.**

1. **Deck diversity, not row count.** 352k play rows, but 99.7% are Hog 2.6. Prince has 0 plays; Giant, DarkPrince, Archers, Zap, Tesla, Goblins and Knight have under 100 each. On holdout decks the policy falls back on generic card semantics.
2. **Re-simulation fidelity.**
   - Only 60% of recorded own plays survive to a label.
   - 37% of perspectives stop at a sim tower kill the recording contradicts, at a median of 0.63 of the match. These are mostly the learner's own towers, consistent with the opponent's evo/L16 units being weaker in sim.
   - Late-game states, overtime, triple elixir and tower-down pockets are under-represented.
3. **Unknown opponent units.** 61% of enemy troop bodies and 69% of opponent-history slots are `<unknown>`. The clone sees "some enemy troop" with public stats but no identity, so card-specific responses to off-vocabulary threats cannot be learned from identity.
4. **Version and form mismatch.**
   - Recorded humans played at L16 with evo/hero forms; the sim uses L11 base forms.
   - The current Furnace is a different card and its placements are rejected.
   - Champion abilities mostly fail.
   - The pilot mask's 5×5 tower margin required projecting 5.7% of labels by one tile.
5. **Timing imbalance.** About 95% of rows are waits and the "when" head stays soft: p(wait) is 0.89 even on play rows. Stochastic play then gives human-like average tempo but weakly state-dependent timing. A time-to-next-action or hazard target, which the review recommends, needs an architecture change and was out of scope for a drop-in comparison.
6. **Critic.** Untrained. A PPO arm seeded from this checkpoint would need the critic warm-up the scripted arm already uses. Value targets from `recorded_outcome` are stored but unused.

**What the wide-scope (S117 own deck) pre-train would need.**

- **Vocabulary.** A contract-v5 vocabulary pinned from all corpus cards (360 tokens; `scope-expansion/PLAN.md` §3), so opponent units stop being `<unknown>`. Plus the token-row transfer test against these checkpoints.
- **Actor.** A larger actor scope, C56 or wider, so own decks are diverse.
- **Mask.** Unmask abilities and fix the Princess-tower margin (the float32 footprint), or carry the projection rule.
- **Engine.** The scalar fixes for the five broken cards and a modern Furnace.
- **Fidelity.** Preferably evo/hero forms for the top cards to lift the 60% play retention.
- **Compute.**
  - Reconstruction took about 3.3 s per perspective per core on the shared machine (11k perspectives in about 11 core-hours). The C56 set (about 68k perspectives) is about 65 core-hours, and the full corpus (about 500k perspectives) about 450 core-hours. Storage is about 85 bytes/row, so about 4 GB for C56's roughly 45M rows.
  - BC at about 400 rows/s per 2-thread process means C56's roughly 45M rows need about 30 h per epoch per process. That is feasible on this Mac only with several processes, or on a small rented CPU or GPU box.
- **Recipe.** Wide pre-train, then narrow P16 fine-tune with natural timing, a time-to-next-action head, a value target from recorded results, and evaluation at several seeds.

## Files

- `data/payloads/`: filtered source matches (63 MB).
- `data/recon/`: reconstructed shards (608 MB).
- `checkpoints/`: the three BC checkpoints, 10 MB each.
- `results/`:
  - `corpus_stats.json`, `sanity_checks.json`
  - `fit-*.json`: training history and validation
  - `validation-*.json`: baselines on the same 200 held-out perspectives
  - `evaluation-*.json`: cells, Wilson intervals, behaviour
  - `paired_comparisons.json`
- `evaluation/<name>/`: raw eval outputs (decision traces deleted after summarizing).
- `scripts/`:
  - `fetch_payloads.py`, `reconstruct.py`, `corpus_stats.py`, `sanity_checks.py`
  - `fit_bc.py`, `validate_bc.py`, `run_eval.py`, `behaviour_stats.py`, `compare.py`
  - `hp_bootstrap.py`: binds to the frozen runtime and loads the two new modules by path, because the snapshot must stay byte-identical.
- `PROGRESS.md`: run log and exact commands.
