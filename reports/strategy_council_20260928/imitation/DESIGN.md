# All-card human imitation model: design

Status: design only, 2026-10-08 (UTC). Nothing was trained, extracted or launched. To write it I read the repo on
127x05 and ran small read-only `nice` inspections on 127x01 (a few NPZ shards, the index and role files) and one
read-only Hugging Face API call from 127x03. Author: Opus design sub-agent for the 127x05 coordinator.

Role of the model: (1) **proposal network** for the fair search player (srp-pub-mix style, Rust, 200 ms deadline);
(2) **fallback policy** where the engine/search cannot act. It never replaces search as the actor
(`amendments/2026-10-01-search-and-human-prior.md`; `HANDOFF_F35_20261005.md` §5.4).

## 0. Recommendation

1. **Train on C56 now, and extract S122 at the same time.** The S122 extraction is CPU-only and the C56 model is
   GPU-only, so the two tracks don't compete. The C56 model (v1) is the pipeline shakedown, the offline baseline and
   the first proposer for the C56 search player. The S122 generalist (v2), trained on C56 ∪ S122, is the deliverable
   for live play: a fresh account plays early-arena cards, and Stage 6 ported the remaining 66 S122 cards for exactly
   that reason (`engine-speed/STAGE6.md` "Scope and order"). About 4–5 working days to v1 gates, then about 3 more
   to v2 (§8).
2. **Add the derived opponent state by a sidecar replay pass, not a re-extraction.** Re-run the frozen extractor
   unchanged with an observer hook. It writes new per-row arrays (opponent elixir, known hand, next card, queue,
   refill; own deck and queue; recent play positions; intent targets) and proves alignment by checking that every
   existing array comes out byte-identical. Cost: about 180 CPU-h, about 3 h wall on two hosts. A pure post-pass from
   the stored rows recovers the opponent's card plays exactly, but not champion abilities or Collector grants. Those
   affect elixir for about 23% and 6% of opponent decks respectively (§2.2).
3. **The derivation is exact and uses no deck prior.** It uses the same integer-frame ledger as the Stage 5 C56
   tracker. "Known" means guaranteed by the public play stream alone. It is verified three ways: against the Stage 5
   and srp-public trackers on their recorded games, against simulator truth on every extracted row, and as a
   train/serve equality test (§2.4).
4. **Placement head: the tile lattice (576 per card), not half-tiles.** In 24 random shards, 36,710/36,710
   supervised human placements sit exactly on tile centres (±2 millitiles), except Tesla, whose 542 plays all sit on
   tile corners: a footprint convention, not information. A half-tile head would have nothing to learn from this
   corpus (§2.6).
5. **Model: a feed-forward set transformer of about 2.5M parameters**, built from scratch. It has a factorized
   policy (3-way gate {wait, play, ability} → card among the hand → tile given the card) and an auxiliary intent head
   ("next card I will play, and when": the "wait for card X" signal). There is no recurrence. Memory comes from
   explicit history and derived-state tokens, which keeps training iid, avoids the TBPTT failure, and lets search
   call the model on any reconstructed public state. Single-core proposer latency budget: ≤15 ms p99.
6. **Gates, all pre-registered on fresh seeds:**
   - **(a) Offline**, on the frozen held-out spec (`c56/data/eval/heldout_eval_spec_v1.json`, frozen 2026-10-02):
     beat the frequency baseline everywhere, and don't lose to the P16 BC on its own slice.
   - **(b) Search proposer:** 640 head-to-head games, imitation proposer vs the current C56 candidates (scripts plus
     16 random placements; the C56 player has no policy today). Pass: score LB > 0.50 and no drop > 0.03 vs C56
     scripts (256 paired games per arm).
   - **(c) Standalone:** P16 protocol 384 games paired with s2902 1M and the P16 BC, plus 256 head-to-head vs s2902,
     plus 384 games vs C56 scripts.
7. **Main risk:** proposal quality barely moved search strength at P16 (ExIt confirmation 0.4805
   [0.426, 0.531]). Gate (b) may well show no gain. The decision rule is fixed in advance (§5.2), and the model still
   earns its place as the S122/live fallback and as the base for a later anchored PPO run.

## 1. Evidence: what the C56 corpus is today

Sources: `c56/data/qa/fleet-v3b/production-20261008/{completion-summary,final-qa}.json`, `recon/engine-v3/completion.json`,
`roles/c56_roles_v1.json`, `index/perspectives.jsonl.gz` and NPZ shards on 127x01 (inspected 2026-10-08 ~02:20Z).

| Fact | Value |
|---|---|
| Units / perspectives / rows | 1,767 / 82,231 / 64,140,802 (64,030,423 supervised); 0 errors, 0 illegal labels |
| Phases | s117 62,766 perspectives (retention 84.6%); s122 19,465 (78.8%), where the opponent needed the S122 engine fixes |
| Retention / placement acceptance | 83.33% of decisions to the recorded end / 99.72% |
| Size | 5.93 GB compressed NPZ + JSON sidecars; ~92 B/row; copies on 127x01 and 127x04 |
| Engine | Frozen runtime `runtime-engine-v3b` (sha `1ec2c60c…`), extractor `8e95786c…`, gamedata `3d99987c` (base, not canonical `892fbfa0`; IceSpirit HP 90 vs 84, Goblin stab 47 vs 49: a known, accepted difference) |
| Contract | public contract v5, 360-token pinned vocabulary (`contract_v5_tokens.json`), 4 opponent-history slots, 8 seen-card slots, decision every 5 ticks (250 ms) |
| Row mix (24 random shards, 796,987 supervised rows) | waits 95.3%, plays 4.6% (36,710), ability 0.06% (484). Whole corpus: ≈2.9M supervised plays |
| Entities per row (12 shards, 457k rows) | mean 11.2, p50 10, p99 25, max 62 (cap 128) |
| Split (frozen before fitting) | `c56_roles_v1.json` sha `7e357f64…`: train 69,380 / dev 3,546 / eval 3,765 / eval_ood 3,771 (8 whole archetype families) / excluded_leak 1,769 |
| Deck diversity | 3,325 distinct own base decks in 1,567 families; Hog 2.6 alone is 13,239 perspectives (16.1%); top five decks are 40% |
| Modes | pathOfLegend 67,564 (82%), trail 5,616, friendly 4,167, clanMate 2,810, tournament 1,301, other 773 |

Arrays per shard (`s117/shard-000-part-00.npz`, 37,821 rows):

| Group | Arrays (dtype, per-row shape) |
|---|---|
| Observation | `global_features` f32 (18), `hand_ids` i16 (5 = 4 hand + own next card), `hand_levels` i8 (5), `opponent_history_ids` i16 (4), `opponent_history_ages` f32 (4), `opponent_seen_card_ids` i16 (8), `own_last_play_ids` i16, `own_last_play_features` f32 (2), `champion_button` bool, `board_rotated` i8, `terminal_status` i8 |
| Entities (ragged) | `entity_counts` i16; `flat_entity_ids` i16, `flat_entity_levels` i8, `flat_entity_features` f32 (17 real-play columns: position, team, kind, HP fraction, speed, range, sight, collision radius, motion, base damage…) |
| Mask | `mask_index` i32 → `mask_table` u8 (deduplicated, 289 bytes = 2,306 action bits) |
| Labels | `expert_actions` i16 (0–2303 = slot×576 + tile; 2304 wait; 2305 ability), `previous_actions`, `expert_action_supervision_valid`, `episode_starts`, `episode_ids` |
| Execution/provenance | `submitted_ticks` (row tick), `recorded_play_ticks`, `recorded_millitiles`, `recorded/submitted_world_positions`, `label_projection_distance`, `recorded_outcome`, `tower_clamped`, `overshoot_frac` |
| Header | per-perspective summary: match id, seat, own/opponent decks and forms, cut reason/tick, champions, `unreproduced_real_kill`, relaxation counters |

**What is missing for a fair-information policy:**
- opponent elixir (absent from public v4/v5 by design, per `srp-public/DESIGN.md`);
- opponent hand, next card and queue;
- own full deck and own queue order beyond the next card;
- opponent play positions (only ids and ages are kept);
- intent targets (the next own play and the time until it).

## 2. Data contract

### 2.1 Reuse and rebuild

**Reuse** (validated, and shared with search and the live loop):
- the v5 observation builder, mask builder and token list;
- the frozen role file and held-out eval spec;
- the frozen extractor/runtime, for the sidecar pass only;
- the Stage 5 C56 tracker semantics, as a test oracle;
- the Stage 5b deadline player, for gate (b);
- the P16 `run_eval.py` protocol, for gate (c).

**Not reused:**
- the `council_pilot` LSTM model, 2.6M parameters;
- the CPU trainer `human_replay_bc.py`, about 400 rows/s;
- any checkpoint.

The model starts from fresh weights (`scope-expansion/PLAN.md` §3 recommendation; handoff §5.3).

### 2.2 Derived opponent state: post-pass or re-extraction?

**What a pure post-pass can recover.** The opponent's accepted *card plays* are recoverable exactly from the stored
rows. `opponent_history_ages` stores elapsed/60 s clipped to 1 (`structured_obs.py:946-961`), so
`row_tick − round(age·1200)` gives the play tick: the sampled rows decode to integers 168, 173, 178. Each play enters
slot 0 within 5 ticks and four slots cover any 250 ms window. Card costs are public.

**Why that isn't enough:**
- **Champion abilities.** Ability activations spend opponent elixir and are public in the real game, but the rows
  don't store them. The simulator accepts only some of them: the first inspected perspective shows 0/4 opponent
  abilities accepted (`counters.opponent_abilities_accepted`). Opponent decks with a champion: golden-knight 6.3%,
  mighty-miner 4.6%, goblinstein 4.0%, skeleton-king 3.2%, monk 1.8%, archer-queen 1.3%, boss-bandit 1.1%,
  little-prince 1.0%. That sums to about 23% of perspectives.
- **Elixir Collector.** Grants depend on the building surviving in the simulation. 6.3% of opponent decks hold it.
- **Mirror** is 0.3%. Elixir Golem (2.1%) changes the learner's elixir, which is already observed, not the opponent's.

**Decision: the sidecar replay pass (task T2).**
- **Hook.** Re-run `reconstruct_perspective_v5` from the frozen runtime with its existing `row_observer` hook, plus a
  public-event recorder of the kind the Stage 5 tests use (`engine-speed/stage5/test_collector.py`). It records card
  plays, accepted ability activations and Collector grants for both seats, with ticks and positions.
- **Alignment proof.** For each perspective, every one of the 32 existing arrays and the summary must reproduce
  byte-identically (logical equality, as accepted in `COORDINATOR.md` 2026-10-08 01:15). Determinism is already
  established: 253/253 reuse checks, fresh fleet replays equal the Mac's.
- **Cost.** The C56 production run used 344,642 CPU-s for 44,097 perspectives, 7.8 CPU-s each. All 82,231 take
  ≈178 CPU-h, about 3 h wall at 64 workers on each of 127x03 and 127x04 (≤80 per host).
- **Fallback.** If the observer cannot be attached without changing bytes, fall back to the post-pass for card
  plays and mark the perspectives with an opponent champion or Collector (up to ~30%) as `elixir_exact=false`.
  Down-weighting them is a later decision, not hidden.

### 2.3 Derivation semantics (policy feature block D1)

All quantities are computed from the opponent's public event stream only, with no deck prior. Why no prior:
- Opponent decks span all 122 cards.
- The Stage 5 prior holds 2,925 C56 train decks and fails closed on anything else
  (`stage5/derived_public_state.py:77`).
- A prior turns "consistent with my prior" into "known", which isn't exact.

The network can learn meta priors itself from the seen-card tokens.

- **Elixir.** Start at 6.0. Use the integer-frame regeneration in 1e-4 units:
  `rate = 2.8 s` before tick 2400, 1.4 s to 4800, 0.93 s after, then clamp to [0, 10]. Subtract card costs and
  ability costs, and add Collector grants. This is exactly the arithmetic of `srp-public/derived_public_state.py`
  and `stage5/derived_public_state.py`; the implementation must match both bit for bit.
- **Cycle.**
  - Initial state: 4 unknown hand cards and 4 unknown queued cards. A played card goes to the back of the queue; the
    queue front refills the empty hand slot after the refill delay (1000/500/350 ms by phase, same rule as the
    trackers).
  - After k ≥ 4 plays, the queue is exactly the last 4 played cards in order, so the next card is known.
  - Known hand = revealed distinct cards not currently queued, as a multiset; the rest are `unknown`. UI slot order
    is never claimed.
  - Before 4 plays, the known queue suffix is set and the rest is `unknown`.
- **Outputs per row:**
  - `opp_elixir` (f32, plus exact int units);
  - `opp_hand_known` (4 tokens, 0 = unknown);
  - `opp_next_card` (token or unknown);
  - `opp_queue` (4 tokens with known flags);
  - `opp_refill_remaining`;
  - `opp_cards_revealed` (0–8);
  - `elixir_exact` flag (false only in the fallback above).
- **Own side** (fair, since a player knows their own deck and cycle): `own_deck` (8 tokens), `own_queue` (4 tokens,
  ordered), `own_refill_remaining`.
- **Recent events:**
  - last 8 opponent plays and last 8 own plays as (token, age, x, y);
  - opponent ability activations as (champion, age).

### 2.4 Verification of the derivation (all must pass before any fitting)

1. **Oracle equality** (unit tests, fast).
   - **Recorded games.** Run the new module on the event streams of the Stage 5 recorded C56 games (8 full games /
     74,424 checks, plus 209,575 confirmation truth checks) and srp-public's 24 recorded P16 games (23,058 elixir
     checks). Elixir must equal both trackers exactly.
   - **Known facts.** Every hand, next-card or queue fact the deck-free module calls known must equal the prior-based
     tracker's determined value. The prior trackers may know more; never less-and-different.
   - **Collector/champion game.** The Collector/Heal/champion game (12,002 checks) must also pass.
2. **Truth audit in the sidecar pass.**
   - The observer also records hidden simulator truth: opponent elixir, hand multiset and queue. It goes to a
     *separate* `audit/` file that the trainer never reads.
   - Required: `|derived − true elixir| ≤ cumulative opponent top-up so far` (top-ups are ≤0.05 each and counted
     per perspective), and every known hand, next-card and queue entry equals truth.
   - Zero violations over all 64.1M rows. Report the coverage curve: fraction of rows with next card known and with
     k/4 hand cards known, by match time.
3. **Train/serve skew test.** The search player (T6) and the live loop compute D1 from their own event streams. On 8
   recorded C56 games, the D1 tensor built inside the deadline player must equal the sidecar's D1 for the same event
   stream, byte for byte.

### 2.5 Observation tensor (policy contract v6 = v5 packet + D1)

One row is a set of typed tokens, all with d=192:

| Token type | Count | Content |
|---|---|---|
| Entity | ≤64 (p99 25) | token embedding (360 vocab) + v5 card descriptors + 17 numeric features + level + team |
| Own hand | 4 (+1 next) | card token, descriptors, cost − own elixir, legal flag (from the mask), champion button |
| Own deck / queue | 8 / 4 | card tokens with role embeddings |
| Opponent derived | 4 hand + 1 next + 4 queue | card token or `unknown`, known flags; plus scalars `opp_elixir`, refill, revealed count |
| Opponent seen cards | 8 | as stored |
| History | 8 opp + 8 own | (card, age, x, y) |
| Global | 1 | the 13 real-play globals (time, phase, own elixir, tower HP…) + champion globals + `opp_elixir` |

That is about 50–70 tokens per row. Everything here is public or own-side knowledge. The v5 invariance tests
(hidden-state poisoning leaves the packet unchanged) are extended to D1.

### 2.6 Actions and targets

- **Gate:** {wait, play, ability}. Ability only where the mask allows it.
  - Rows with no legal play are forced waits and are excluded from the gate loss; the eval spec's "when" metric
    uses playable rows too.
- **Card:** chosen among the ≤4 hand cards with any legal tile. Cards are scored from their tokens, so the head is
  permutation-equivariant; the opening slot shuffle carries no label.
- **Tile:** chosen among the 576 tiles (18×32 canonical, learner at the bottom), masked per card.
  - Even-footprint cards such as Tesla use the existing action-space snapping, so the corner is implied by the card.
  - **Why not half-tiles:**
    - In 24 random shards (1,038 perspectives), every supervised placement is a tile centre (36,168) or a Tesla
      corner (542). There are zero other positions.
    - IL_Replay positions are tile-quantized, so a 36×64 head would have no supervision for its extra cells.
    - Projected labels (nearest legal tile) are 0.9% of plays in the shard inspected.
    - ClashAI's half-tile lattice (handoff §5.3) therefore buys nothing on this data.
    - Whether the *official client* accepts finer positions is an L3 question (OPEN-QUESTIONS 2).
- **Intent ("wait for card X"):** an auxiliary head on every supervised row.
  - Target: the card of the next labelled own play (over the 8 own-deck cards, because X may still be in the
    queue) and the time until it, in 12 log-spaced bins up to 10 s plus ">10 s". It uses a discrete-time hazard
    loss, right-censored at the perspective cut.
  - Targets come from future rows of the same perspective; they are never inputs.
  - This is the time-to-next-action target the P16 study asked for (`human-prior-p16/README.md` §6.5: p(wait) is
    0.89 even where the human played).
- **Ability rows** are labelled only for decks with exactly one champion and no hero form (extractor rule).

### 2.7 Row weights (frozen; no new tuning)

Use `heldout_eval_spec_v1.json` "bc_weighting_natural_arm" exactly:

| Factor | Weight |
|---|---|
| Unreproduced real kill | 0.5 |
| Evo/hero play rows | 0.5 |
| Rows after the first tower clamp | 0.5 (`tower_clamp_weights`) |
| Friendly and clanMate modes | 0.5 |
| Player proxy and archetype balance | √-capped |
| Waits | sampled at 25%, inverse-probability weight 4 |

Waits keep their natural share in expectation. The P16 study showed down-weighting waits makes the clone spend early
and lose: wait02 scored 21/192 vs 40/192 for natural (`human-prior-p16/README.md` §5).

### 2.8 Training store (task T3)

- **Format.** A memory-mappable packed store per role: fixed-width row table, ragged entities with offsets, the
  deduplicated mask table, D1 arrays, intent targets, and weights. Built on 127x01 and copied over the LAN to
  127x04 and 127x08, into a fresh directory; never with `rsync -a` over an existing tree
  (`memory: no-writes-to-trees-owned-by-another-thread`).
- **Size.** ≈1.05 KB/row uncompressed, so ≈67 GB for all C56 rows. Each GPU host has 125 GB RAM and 1.6–1.7 TB
  free on `/mpac`.
  - For S122, the train role stores all plays plus a fixed hash-selected 50% of waits (weight ×2; each epoch then
    samples half of those). Dev and eval keep all rows. That is ≈180 GB per GPU host.
- **Checks.** A 1% random-perspective round trip equals the NPZ+sidecar. Per-role counts equal the role file.
  excluded_leak rows are dropped. Manifest of sha256 values.
- **Baselines** are computed in the same task from train rows only (eval spec "frequency" baseline), plus the P16
  BC upgraded with `contract_v5.upgrade_policy_payload_to_v5`, scored on the P16 slice.

## 3. Scope and sequence

| Option | Data | For | Against |
|---|---|---|---|
| Train on C56 only | 82,231 perspectives; 3.89M recorded own plays; ≈2.9M supervised | Data, split and eval spec are ready now; matches the current Rust fair player (Stage 5/5b) | Own decks limited to 56 cards; misses the early-arena cards a new account holds |
| S122 actor scope first | +355,585 Princess-tower perspectives, 11.27M recorded own plays, all 66 new own cards (scan index, recomputed 2026-10-08; my C56 count reproduces 82,231 exactly) | Covers every corpus card; about 3.9× the plays | About 1 day of fetch/QA/extraction before any training signal; no pipeline shakedown first |
| **Both in parallel (recommended)** | C56 v1 trains while S122 extracts on CPU | No idle resource; v1 debugs the trainer and evaluator before the larger run; v1 is the C56 proposer and the v2 baseline | Two QA streams for the coordinator to review |

**S122 extraction, revised from the handoff:**
- **Drop the ≤6 GiB cap and extraction-time wait subsampling.**
  - The cap was set by the Mac's ~27 GiB free disk.
  - At ~72 KB/perspective (C56 measured), all 355,585 perspectives take ≈26 GB; fleet hosts have 1.6–1.7 TB free.
  - Subsampling at extraction would break the frozen natural-row evaluation protocol.
  - Archetype caps would save CPU we have spare; weights already balance archetypes.
- **CPU:** 355,585 × 7.8 CPU-s ≈ 770 CPU-h, so ≈5 h wall at 160 workers (127x03 + 127x01, ≤80 each), plus QA.
- **Source:**
  - The original `hf_manifest.json` and shard 0 lived in `artifacts/worktree-data`, whose only copy is on dead f35
    (`artifacts/OFFLOADED_TO_F35.md`).
  - The pinned revision `059d43a0…` is reachable from 127x03: 104 parquet files, 1.89 GB, each with its LFS sha256.
  - Regenerate the manifest from the API, and verify the re-fetch by re-filtering C56: the output must equal
    `c56/data/payloads/` byte for byte.
- **Engine:** the same frozen `runtime-engine-v3b` and gamedata `3d99987c` as C56, so the corpus is one engine
  version and the existing QA tooling applies unchanged.
  - The Python engine has not changed since; Stage 6 treats it as a read-only oracle.
  - The canonical-gamedata difference stays documented.
- **Exclusions and flags** (known Python oracle limitations, `engine-speed/STAGE6.md` "Current resume point"):
  - Exclude any perspective with Three Musketeers on either side: the engine deploys one 100 HP placeholder.
  - Flag Battle Healer (healing ignored) and Mirror (predecessor rejections) perspectives in metadata.
  - Tower-troop perspectives (65,514) stay excluded, as in v1.
  - New champions (golden-knight, skeleton-king, monk, little-prince, boss-bandit) get ability labels only where the
    attribution rule and mask allow. Golden Knight has no active ability in the oracle, so its ability events are
    unlabelled and that is reported.
- **Roles v2:** new perspectives get roles by the same salted hash and the same family and proxy rules, extended to
  S122 decks. The v1 role assignments of all 82,231 C56 perspectives stay unchanged.
  - New eval_ood families are drawn only from S122-only decks.
  - A cross-version leak check is required (a match with one C56 and one S122 perspective).
- **QA before production:**
  - a 400-perspective stratified sample covering all 66 new own cards (≥3 perspectives each; the rarest,
    barbarian-hut, has 311 in the corpus);
  - placement acceptance ≥0.99 overall and reported per card;
  - 0 illegal labels;
  - byte determinism on 6 perspectives;
  - retention reported per card.
  - Any new own card with placement acceptance <0.95 is excluded from the actor scope and reported, not patched.
- The sidecar observer (T2) runs **inside** the S122 extraction, so S122 needs no second pass.

## 4. Model and training

### 4.1 Architecture (implemented from scratch in plain PyTorch, eager, bf16 autocast)

- **Token encoder.** Per type: a linear projection of numeric features, plus the card/token embedding (360×192),
  plus a projection of the v5 card descriptors, plus a type embedding.
  - Entity positions also go through a 2-D Fourier feature map (8 frequencies).
- **Trunk.** A 4-layer pre-LN transformer encoder, d=192, 6 heads, FFN 768, dropout 0.1, with a [CLS] token and
  attention masks for padding. Rows are bucketed by token count (≤48/64/96).
- **Gate head.** MLP([CLS]) → 3 logits, with illegal classes masked.
- **Card head.** For each hand card, MLP([CLS], card token output) → 1 logit, masked by "has a legal tile".
- **Tile head.**
  - Computed once per row: 576 tile queries (a learned embedding plus the 12 static features of
    `build_canonical_tile_features`, d=128) with one cross-attention layer over trunk tokens and FFN 256 → F
    (576×128).
  - Per card: logits = MLP(F ⊙ (W · card output)) → 576, masked by that card's slice of the action mask.
  - Training uses teacher forcing on the labelled card.
- **Intent head.** MLP([CLS]) → 8 own-deck card logits and 13 hazard logits.
- **Joint policy for proposals.** p(card) · p(tile | card) over legal pairs; top-8 by joint probability.
  - The gate doesn't enter the proposal list, because search always includes no-op.
  - Standalone play samples gate → card → tile.
- **Size:** ≈2.4M parameters: trunk 1.8M, tile head 0.3M, embeddings and heads 0.3M. For comparison, the P16 BC
  had 2.6M and ClashAI about 1.3M (`COORDINATOR.md` 2026-10-04 ClashAI note).
- **Latency budget:** propose(top-8) including feature building ≤15 ms p99, single thread, measured on a 127x core
  and on the Mac mini (P3 runs there).
  - Rough count: ≈0.35 GFLOP forward, so ≈7–12 ms at the 30–50 GFLOPS one fp32 core sustains.
  - The 200 ms Stage 5b deadline currently uses p99 111 ms (`engine-speed/STAGE5B.md`).
  - If the budget is missed, first shrink the tile dimension to 64; nothing else changes.
- **Why no recurrence:**
  - Stored-state TBPTT hurt PPO (v7r5 47/43 vs v7r4h 60/88 at 1M, `amendments/…` 2026-10-04).
  - srp-pub needed per-game recurrent warm-up and reset (`search-tuning/RESULTS.md`).
  - Search must score policies at *reconstructed* public roots where no consistent hidden state exists.
  - Everything an LSTM remembered here is now an explicit token: derived elixir, hand, queue, histories.
  - A GRU over the last 32 [CLS] states is one pre-declared offline ablation (§4.4).

### 4.2 Losses

L = L_gate + L_card + L_tile + 0.25·L_intent, all weighted by the §2.7 row weights.
- L_gate is cross-entropy on playable supervised rows.
- L_card and L_tile are cross-entropy on play rows only, so the 95% wait share never touches them. This is the
  class-balance answer: the gate sees natural rates with unbiased wait subsampling, and the card and tile heads see
  only plays.
- No label smoothing; tile within-1 accuracy is reported instead.
- No value head in v1: the recorded outcome is confounded by evo/L16 units the simulator lacks, which is why the P16
  winners-only filter failed (`human-prior-p16/README.md` §6).
- After training, fit separate temperatures for gate, card and tile on dev.

### 4.3 Optimization, throughput, checkpoints

- **Sampling.** Every epoch takes all train play rows and a fresh 25% of train waits (hash of row id and epoch),
  shuffled iid.
  - That is ≈2.5M play rows + 12.9M wait rows ≈ 15.4M rows per epoch: 84.4% of perspectives are train, waits
    subsampled.
  - S122 (v2): ≈13M plays + 68M waits ≈ 81M rows per epoch.
- **Optimizer.** AdamW, lr 3e-4, cosine schedule, 2k warmup steps, weight decay 0.05, grad clip 1.0. Batch 8,192
  rows. EMA of weights (0.999) is used for evaluation.
- **Throughput:**
  - Estimate: ≈6·params·tokens ≈ 0.9 GFLOP per row for forward and backward, so at a realistic 10–20 TFLOPS
    achieved in eager bf16 (105 TFLOPS peak, `fleet/GPU-CHECK.md`), about 10–20k rows/s.
  - T4 must measure it in its first 10 minutes. Plan on 8k rows/s, assuming the loader keeps up from mmap.
- **Wall-clock at 8k rows/s:**
  - C56: 32 min per epoch; ≤12 epochs with early stopping on dev joint NLL, so ≤6.5 h per run.
  - S122+C56: 2.8 h per epoch; ≤6 epochs, so ≤17 h per run.
- **Checkpoints.** Every 1,000 steps and every epoch; keep the last 3 plus best-dev. Each is resumable (optimizer,
  scheduler, RNG, sampler epoch).
  - Each records the config, contract hashes (token list `5e20ce08…`, role file, eval spec, sidecar manifest,
    store manifest) and the provenance string "human-prior research artifact; not a Tier A admitted pilot arm".
  - Launch through `fleet/fleet_run.sh` (detached, niced, lock and exit receipts).
- **GPUs:**
  - 127x04 and 127x08 have the env now.
  - 127x01 needs the T0 installer (`fleet/gpu_env.sh`, minutes).
  - 127x07 and 127x02 are offline.
  - Imitation takes 04 and 08. 127x01's GPU is left for live-loop v4 T6/T7 perception training when its data is
    ready; imitation may borrow it until then.

### 4.4 Runs (pre-declared; nothing else is tuned)

| Run | What | Purpose |
|---|---|---|
| shakedown | 1 seed, 0.2 epoch on a 2% subset, then overfit 1,000 rows | Pipeline sanity; measured throughput |
| **v1-main** ×3 seeds | recipe above | Offline gate; dev-selected seed → gates (b) and (c) |
| v1-noD1 | main recipe without the D1 block | Measures the value of the derived state offline (reported, no bar) |
| v1-gru | main + GRU over 32 steps | Recurrence check offline; adopted only if it beats main on dev joint NLL by >0.01 nats **and** meets the latency budget |
| **v2-main** ×2 seeds | C56 ∪ S122, same recipe | The generalist |

## 5. Evaluation gates (each frozen in a PREREG.md with content hashes before any games or eval-set scoring)

### 5.1 Gate (a): offline, on the frozen held-out spec

- Metrics as defined in `heldout_eval_spec_v1.json`: play/wait NLL and Brier, card top-1/top-3/NLL, tile
  NLL/median error, joint NLL, ability NLL, hazard calibration. Add:
  - **top-8 recall:** the human's (card, tile) is in the model's top-8 joint; also reported within 1 tile;
  - **per-card and per-arena slices:** arena = the card's `unlockArena` in `gamedata.json` (TrainingCamp,
    Arena1–14, legendary codes). It is a reporting slice only, because the gamedata's arena table may be dated;
  - **ECE** for gate and card, before and after temperature scaling.
- Natural row weighting; whole perspectives; 10,000 perspective-cluster bootstrap resamples.
- Checkpoints are selected on **dev** only. **eval** and **eval_ood** are scored once.
- **Pass bars** (all required, on eval, and reported on eval_ood):
  - **A1.** Joint NLL, play/wait NLL, card NLL and tile NLL are each lower than the frequency baseline, with 95%
    CIs of the paired difference below 0.
  - **A2.** On the P16 slice, card NLL and tile NLL are ≤ the upgraded P16 BC's + 0.05 nats (the generalist doesn't
    lose to the specialist on its home data).
  - **A3.** No own card with a significantly worse card-conditional tile NLL than its per-card frequency
    histogram. Count passing cards out of 56; for v2, out of all scoped cards.
  - **A4.** Gate ECE after temperature scaling ≤0.01. The base play rate is ≈0.046, so this bounds miscalibration
    at about 20% of it.
- **Descriptive** (no bar): top-8 recall overall and per card/arena; noD1 and GRU deltas; eval vs eval_ood gap. The
  gap is the honest generalization number, because 67% of perspectives belong to the 55 large proxies that are
  split per match, so in-distribution eval can share players with train.

### 5.2 Gate (b): as the search proposal network (C56, Rust fair player)

- **Arms:**
  - **A**, current Stage 5b deadline player (`engine-speed/STAGE5B.md`): script choice, no-op, script top 4,
    ability, 16 sampled public-legal placements; 200 ms deadline, 2 threads.
  - **B**, identical except the 16 sampled slots become the imitation top-8 (deduplicated against script candidates)
    plus random fill to 16. The candidate count stays the same, so compute is matched and only proposal quality
    changes. Model inference counts inside the deadline.
- **Games:**
  - **Primary, B vs A head-to-head:** 320 seeded worlds × 2 controller swaps = 640 games. Decks follow Stage 5b's
    role-held-out eval/eval_ood planning, with fresh seeds and a seed audit against every prior receipt.
  - **Secondary:** B and A each vs C56 scripts (balanced/pressure/defense), 256 games per arm on identical seeds.
- **Sample size.**
  - Pair means are in {0, ½, 1}. Stage 5b saw 124/128 identical pairs only because the controllers were identical;
    with different proposers, assume 30–50% discordant pairs.
  - The SD of a pair mean is then 0.27–0.35. At 320 pairs the SE of the score is 0.015–0.020, so a true score of
    0.55 clears a 0.50 lower bound with about 70–90% power.
  - The previous designs' 256 games (128 pairs) have an SE of 0.024–0.031 and detect only about +0.07 to +0.09 at
    80% power.
- **Pass:**
  - Primary score ≥0.53 with 95% paired-matchup bootstrap LB >0.50.
  - Secondary point drop vs scripts ≤0.03.
  - Timing: 0 decisions >250 ms, and p99 ≤ A's p99 + 15 ms.
- **Decision rule:**
  - Pass → B becomes the default C56 fair player, and live-loop v4 P3 uses it.
  - Fail → A stays. The model serves only as the fallback policy and as the base for later work. No retuning on
    these games. The single pre-declared retry is v2 on fresh seeds.

### 5.3 Gate (c): standalone policy strength

1. **P16 protocol vs scripts.** `human-prior-p16/scripts/run_eval.py` cells (3 styles × holdout/hog26), two fresh
   seed blocks = 384 games.
   - Played by v1-main (stochastic sampling at T=1, gate hazard per 250 ms as trained), s2902 1M and
     human-bc-natural, all on identical seeds.
   - Bar: v1 beats human-bc-natural, exact McNemar p<0.05.
   - Reasoning: the known gap between s2902 (88/192) and the P16 BC (40/192) is 25 pp. At 384 paired games with
     about 30% discordance, a 10 pp difference gives McNemar power of about 90%.
   - v1 vs s2902 is reported with a Newcombe CI and has no bar.
2. **Head-to-head vs s2902 1M.** 128 P16 worlds × 2 seat/controller swaps = 256 games, on the P16 Python engine.
   - The v1 policy uses the v5 mask, which has the game's 3×3 tower footprint; s2902 uses its own v4 mask. Recorded
     as a known asymmetry.
   - Decision: LB >0.50 → v1 replaces s2902 as the P16 reference policy. Otherwise s2902 stays.
3. **C56 vs C56 scripts.** 384 games, 3 styles × 128, on eval-role decks. Descriptive only: it is the baseline for
   the next stage (a v7r4h-style anchored PPO from the BC model, stopped at 1M, no league) and the
   fallback-adequacy number.

All results are reported, including failures. Interrupted games follow the established technical-rerun rule:
replay from seed, with no outcome inspected.

## 6. Risks, and what failed before

| Risk / prior failure | Evidence | How this plan handles it |
|---|---|---|
| Proposal quality may not matter | ExIt confirmation 0.4805 [0.426, 0.531]; srp-pub 0.809 vs srp-pub-pol 0.797 vs scripts; the "policy16" profile fell to 0.44 | Gate (b) measures it directly with matched candidate counts and enough power for +0.05; the decision rule is fixed in advance; the model's other jobs (fallback, S122, live) don't depend on passing |
| Distilling search into the policy (DAgger/ExIt) | DAgger it1 88→16/192 (premature spending; hard tile labels from random candidates flattened the location head); it2 87 vs 88; ExIt 0.48 | Human labels only; no search labels anywhere in this milestone |
| Re-weighting timing | P16 wait02: 21 vs 40/192 | Natural gate with unbiased wait subsampling (frozen spec) |
| League self-play | v7r2c 43→20/192; v7r4h s2902 88→59 | No self-play here; any later PPO stops at 1M with a KL anchor and fresh-seed selection |
| Stored-state TBPTT | v7r5 47/43 vs 60/88 | No recurrence; GRU only as an offline ablation |
| Re-simulation fidelity (sim states, real human labels) | 83.3% retention; cuts: sim game over 32,968, recorded end 22,253, tower kill 9,667, pocket 5,910, masked tile 5,596; evo/hero forms played as base; L16→L11 | Prefix cuts, tower-clamp ×0.5, evo/hero ×0.5 (frozen). Gates (b) and (c) are judged in the simulator, where the model is deployed for search. The live gap is the L2/L3 tracks' problem, not hidden here |
| Split leakage without player identity | 55,077 of 82,231 perspectives (67%) are in large proxies split per match | Select on dev; report eval_ood (8 whole families, never fitted) next to eval |
| Train/serve skew in D1 | Two code paths (sidecar vs live tracker) | §2.4.3 byte-equality test; one shared module |
| Wrong "known" facts from a deck prior | Stage 5 prior = 2,925 C56 train decks | Deck-free exact derivation; prior trackers are test oracles only |
| Hog 2.6 and meta dominance | 16.1% of perspectives are one deck; top 5 decks 40% | √ caps (frozen); per-family and per-card reporting |
| Thin S122 cards | barbarian-hut 311, mirror 1,200, goblin-machine 1,526 perspectives | Per-card QA and reporting; card descriptors give shared structure; cards under the acceptance bar are excluded, not patched |
| Python oracle defects in S122 | Three Musketeers placeholder, Battle Healer, Mirror (STAGE6) | Exclude or flag (§3) |
| Live perception noise (opponent events 64% recall in L1 v3; fair player 86.7%→50% under full noise) | `live-loop/v4/DESIGN.md` §1 | Out of scope for v1. Live D1 comes from the ELT MAP hypothesis with its concentration flag. Noise-augmented fine-tuning with the S1 noise model is a later, separately gated step |
| Compute contention and shared-tree incidents | S1 on 04/08, Stage 6 on 01, the 01:39Z overwrite | ≤80 processes per host; GPUs on 04/08; outputs only in fresh `imitation/` directories; hash manifests; mirror to 127x04 |
| GPU path | `torch.compile` fails on driver 470 | Eager only; throughput measured in the shakedown |

## 7. Task breakdown (implementation: GPT-6-Astra high via `delegate_task`; Opus for PREREG review and independent re-verification)

Data lives under `127x01:/mpac/sdicks02/repos/clasher/reports/strategy_council_20260928/imitation/data/` (not in
git), mirrored to 127x04. Docs and analysis scripts only go to git. Every long job is detached and resumable, with
exit receipts.

| ID | Task | Inputs | Outputs | Done when | Host | Est. |
|---|---|---|---|---|---|---|
| T0 | GPU env on 127x01 | `fleet/gpu_env.sh`, `gpu_check.py` | env + receipt | gpu_check PASS | 127x01 | 0.5 h |
| T1 | Deck-free D1 module + own-cycle module + tests | §2.3; Stage 5 and srp-public trackers and recorded games | `imitation/derived_d1.py`, tests | §2.4.1 passes: elixir bit-equal on all oracle games, 0 known-fact conflicts, Collector/ability cases | 127x03 | 0.5 day |
| T2 | C56 sidecar replay pass | T1; frozen runtime v3b; payloads; recon/engine-v3 | per-unit `sidecar/*.npz` (D1, histories, own deck/queue, intent targets); separate `audit/`; manifest | 82,231/82,231 perspectives; all existing arrays byte-identical; §2.4.2 0 violations; coverage curves; copy on 04 | 127x03 + 127x04, ≤64 workers each | 0.5 day impl + ~3 h run |
| T3 | Packed training store + baselines | NPZ, T2 sidecars, role file, eval spec | per-role mmap store, weights, store manifest; frequency baseline; upgraded P16 BC scores on the P16 slice | 1% round trip exact; counts equal roles; baseline metrics file | 127x01 CPU → LAN copy to 04/08 | 0.5 day |
| T4 | Model, trainer, evaluator, inference API (from scratch) | §4; T3 store | `imitation/model/` code; `evaluate.py` implementing §5.1; `propose(public_packet, d1, k=8)` CPU API; TorchScript export for the Mac | unit tests (masking, equivariance, the loss on a hand-built row); shakedown run; measured rows/s; latency bench ≤15 ms p99 on 127x and Mac | code on 127x05, runs on 04 | 1–1.5 days |
| T5 | v1 training runs + gate (a) report | T3, T4 | 3 seeds + noD1 + GRU checkpoints; `imitation/RESULTS-v1-offline.md` | Gate (a) pass/fail written; dev-selected checkpoint hashed | 04, 08 (+01 if free) | ~14 h wall |
| T6 | Search integration | T4 API, Stage 5b deadline player, T1 module | arm B player; D1 tracker in the player | §2.4.3 skew test exact; 20 smoke games; timing within budget | 127x03 | 1 day |
| T7 | Gate (b) PREREG + games + report | T5 checkpoint, T6 | `imitation/gate-b/{PREREG,RESULTS}.md`, receipts | 1,152 games complete, analysis as registered | 127x03 + 127x04 (≤80 processes) | 0.5 day + ~4 h run |
| T8 | Gate (c) adapters + PREREG + games + report | T5 checkpoint; `run_eval.py`; s2902 1M; human-bc-natural | `imitation/gate-c/…` | 1,792 games complete (384 × 3 policies + 256 head-to-head + 384 C56); report | 127x03 / 127x08 | 1 day |
| T9 | IL_Replay re-fetch + manifest + S122 payloads + index + roles v2 | HF revision `059d43a0…`; scan index; C56 payloads | regenerated manifest; S122 payloads; `roles/s122_roles_v2.json` | re-filtered C56 equals existing payloads byte for byte; v1 roles unchanged; leak check | 127x03 | 0.5 day |
| T10 | S122 QA + production extraction (with T2 observer inline) | T9, T1, frozen runtime | `recon/engine-v3-s122/` NPZ + sidecars; QA receipts; copy on 04 | §3 QA bars; 0 errors or isolated per-perspective errors <0.5%; sidecar audit 0 violations | 127x03 + 127x01 (≤80 each) | 1 day incl. ~5 h run |
| T11 | v2 store + training + gate (a) on C56 and S122 eval | T10, T3/T4 code | v2 checkpoints; `RESULTS-v2-offline.md` | Gate (a) for both eval sets | 04, 08 | ~1.5 days |
| T12 | Gate (b) retry with v2 (C56, fresh seeds) | T11, T6 | `gate-b-v2/` | as T7 | CPU | 0.5 day |

**Dependencies:**
- T1 → T2 → T3 → T4 shakedown → T5 → {T7, T8}.
- T6 needs T1 and T4.
- T9 → T10 → T11 → T12.
- T9 and T10 run alongside T2–T5. T10 waits only for T1 (the inline observer) and the T9 QA.

S122 search (gate (b) at S122 scope) needs a qualified S122 fair player: Stage 6 sealing plus a Stage-5-style
controller and candidate qualification for the 66 cards. That is a separate track, not part of this design.

**Coordinator's independent checks:**
- Rerun the T2 truth audit on 200 random perspectives on a different host.
- Recompute gate (a) joint NLL for one checkpoint from raw saved predictions.
- Spot-replay 4 gate (b) games from seed.

## 8. Timeline and compute

| Day (from start) | CPU | GPU |
|---|---|---|
| 0 | T1; T9 fetch and checks | T0 |
| 1 | T2 run (~3 h); T10 QA | T4 shakedown |
| 2 | T3; T10 production (~5 h) | T5 (3 seeds + 2 ablations, ~14 h) |
| 3 | T6 | T5 finishes; gate (a) |
| 4 | T7 + T8 games (~4 h + ~3 h) | v2 store copy |
| 5–7 | T12 | T11 (~17 h per seed, 2 seeds in parallel) |

Totals: ≈180 + 770 CPU-h of replay/extraction, ≈60 CPU-h of evaluation games and ≈60 GPU-h of training. Disk:
≈26 GB compressed for the S122 extraction plus ≈67 GB (C56) and ≈180 GB (S122 train rows with waits pre-thinned to
50%, plus dev/eval) of packed stores per GPU host. Agent and review overhead dominates calendar time.

## 9. Sources

- `HANDOFF_F35_20261005.md` §3, §5; `HANDOFF_127X05_20261007.md`; `COORDINATOR.md` (2026-10-04 TODO on derived
  features; 2026-10-08 C56 completion and logical-equivalence decision); `amendments/2026-10-01-search-and-human-prior.md`.
- `human-prior-p16/README.md`; `pilot/v7r4h-launch/RESULT-1M.md`; `search-tuning/RESULTS.md`; `srp-public/DESIGN.md`,
  `srp-public/derived_public_state.py`; `engine-speed/stage5/derived_public_state.py`, `STAGE5.md`, `STAGE5B.md`,
  `STAGE6.md`, `GAMEDATA_CANONICAL.md`; `live-loop/v4/DESIGN.md` §2.5–2.6; `fleet/GPU-CHECK.md`;
  `scope-expansion/PLAN.md`.
- Code: `src/clasher/rl/human_replay_v5.py` (reconstruction loop, `row_observer`), `human_replay_demonstrations.py`
  (`_ROW_FIELDS`), `structured_obs.py:946-981`, `public_observation.py` (feature names).
- Data inspected on 127x01: `c56/data/{index,roles,eval}`, `recon/engine-v3/{completion.json, s117/shard-000-part-00.npz}`,
  24 random shards (placement lattice, row mix), 12 random shards (entity counts),
  `m0/human-prior-scan/corpus_index.jsonl.gz` (S122 counts). HF API on 127x03: revision `059d43a0…`, 104 parquet
  files, 1.89 GB.
