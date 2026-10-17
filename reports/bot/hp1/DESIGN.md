# HP1 — human-init full-pool policy: design and scoping (exploration)

Owner: HP1 track (Opus), for the BOT LEAD. Written 2026-10-17, 22:29–22:55 UTC (`date -u`), from origin/main
dc5bf3dc1 → 5c88d56af. **Design only:** no training, no games. Host work was read-only: manifest/index reads, two
niced single-thread array scans of the v2 packed store on 04 (≈1 min each), and checkpoint header loads. Hosts 01, 04
and 08 only. Path prefix `/mpac/sdicks02` is written as `~` below.

## 0. Summary

1. **A native full-pool human policy already exists, and it has never played a game.** v2 = `main-2026100822`,
   best-dev step 46459, SHA256 `87794378b691db330d4d37b83f1a1c04fd9defad517492652fe79c20d0471fae`. It was trained
   on 2026-10-08 (T11) on C56 ∪ S122: 318,766 train perspectives and 8.36M supervised plays, covering 121 own cards.
   - It has the same config and the same state-dict keys and shapes as v1 / v1-fp: 2,254,949 parameters, checked on
     04 against `ext/main02-fp.pt`. So it drops into every existing loader: `student:`, `BOT_FULLPOOL_POLICIES`,
     `bot.rl.learner --init` and the PT1/PT2 prior.
   - Offline it beats v1 on their shared P16 slice: card NLL 0.886 vs 0.898, tile NLL 2.833 vs 2.882. It passes
     A1/A2/A4. Its only formal FAIL is A3 *coverage*: 4 of 56 C56 cards had too few eval plays to assess. No card was
     significantly worse than its frequency baseline.
   - v1-fp's 90 proxy rows are therefore unnecessary for an HP1 model: every human card has trained rows (§2.2).
2. **v1 barely saw much of the live-relevant pool.** v1's C56 filter (own deck ⊆ C56) dropped almost every deck
   containing the common spells and win conditions:

   | card | C56 train-store plays (v1's data) | v2 train-store plays |
   |---|---:|---:|
   | Zap | 1,359 | 138,135 |
   | Giant | 121 | 54,013 |
   | Arrows | 469 | 86,676 |
   | Tornado | 322 | 117,288 |
   | Bats | 7,986 | 65,960 |

   Sam's current Hog deck is all C56, but two of its eight cards (Zap, Bats) were nearly absent from v1's data. This
   bears directly on the "few spells / undervalued small spells and swarm air" symptoms.
3. **Recommendation.** The human policy is the **init and anchor** for (b), not (a) by itself:
   - v1-style IL alone loses to our bots: rl5-v10 alone beats v1 0.88, and search beats it 0.93 (NS1).
   - Order of work:
     - **S0 (CPU, now):** v2 as a policy-only player, on-policy calibrated threshold, 100-case screen. ~20 CPU-h.
     - **P1 (GPU, ~5 h on one A6000):** the IL pilot (§7).
     - **(b):** terminal-reward PPO from the better human init, with a KL anchor to it, in a league with K4CW-fp, R3a,
       f1a2 and rl5.
     - **(c):** v2 as the PT2 prior. Cheap; a side use only.
     - **(a):** policy-only live, only if an RL'd HP1 policy clears the §4 gate against the live search.
4. **New design constraint found: command lag.** Human labels carry no command lag, but our sim and live loop have
   27 ticks (1.35 s).
   - 93.9% of C56 train plays are still legal (same card, same tile) 25 ticks earlier, and 90.5% 30 ticks earlier.
   - So lag-aligned labels are viable, losing ≈6–10% of plays. This is the second P1 arm (§2.5).

## 1. Data

### 1.1 Where it lives (verified 2026-10-17 22:31–22:42Z)

| item | host : path | format / size | id |
|---|---|---|---|
| Raw IL_Replay | 04 `~/jobs/clasher/bot-ext2-data/il_replay/replays/` | 52 Parquet, 825,394,311 B, 252,238 games (NS1 footer read) | HF `VanguardX101/IL_Replay` @ `059d43a0…` |
| C56 perspective index | 04 `~/repos/clasher/reports/strategy_council_20260928/c56/data/index/perspectives.jsonl.gz` | 4,889,809 B, 82,231 rows | — |
| S122-new index | 04 `…/imitation/data/index/perspectives.jsonl.gz` (+ `c56-v2-metadata.json`) | 31,251,796 B, 333,934 rows | T9 index `473463da…` |
| Reconstructions | 04 `…/c56/data/recon/engine-v3/`, `…/imitation/data/recon/engine-v3-s122/` | NPZ shards + D1 sidecars (frozen runtime-engine-v3b, gamedata 3d99987c) | T10-production.json |
| **v2 packed store** (all IL training reads this) | **04 and 08** `~/repos/clasher-t11-home-v1/data/v2-store-v1/{train,dev,eval,eval_ood}` | `clasher.imitation.packed.v1`; 228 GB per host; 64 mmap `.npy` arrays per role + `mask_table.npy` (381,887 × 289 B, big-endian bits); manifest `passed: true`, `roundtrip_exact: true` (3,664 perspectives) | role file `1f45f1d1…`, mask table `0287247…` |
| v1 (C56 human) | runtime pin `main02.pt`; extended `04 ~/jobs/clasher/bot-fullpool/ext/main02-fp.pt` | 36,464,206 B | `69313468…` |
| **v2 (full-pool human)** | 04 `~/repos/clasher-checkpoints/v2/main-2026100822/87794378…/best-dev-step-00046459.pt`; 01 `~/repos/clasher-t11-home-v1/runs/main-2026100822-hostloss-20261008-v1/best-dev-step-00046459.pt` | 36,477,979 B (with optimizer state) | `87794378…` (both copies hashed today) |
| v2 seed 21 | 04 `…/main-2026100821/88c5862c…/best-dev-step-00046460.pt` | — | `88c5862c…` |
| rl5-v10 / f1a2 | 04 `ext/policy-00010.pt`; f1a2 `step-001200.pt` (fullpool_eval FAST) | 19,826,631 B / — | `e188e2ae…` / `0c03f79f…` |

Not in git and never to be committed: raw data, stores, checkpoints.

### 1.2 Filtering: how v1 became C56 (`imitation/s122/build_payloads.py`; T9-payloads.json)

- **Match filters, both sides:**
  - 1v1 with valid 8-card decks over the 122 base cards (evo/hero forms map to base);
  - **Princess tower on both sides**, which drops 32,789 tower-troop matches;
  - plays logged on both sides.
- **Three Musketeers:** any game with it on either side is excluded from the S122 track (12,006 matches). v2 also
  drops 2,361 old C56 perspectives that faced it.
- **C56 vs S122-new:** a perspective is **C56** if its *own* 8 cards ⊆ the 56-card list (`bot/fullpool/cards.py C56`)
  and **S122-new** otherwise. The opponent deck is unrestricted:
  - 66,241 of the 82,231 C56 perspectives (80.6%) face at least one non-C56 card;
  - 270,054 of the 333,934 S122-new perspectives do.
- **Reconstruction:** an open-loop re-simulation at L11, base forms, with recorded ticks and positions. Supervision
  stops at the first hard contradiction; retention is 83.3% for C56. There are row weights for tower clamp, evo,
  friendly mode and the proxy cap.
- **v1-main:** trained on the C56 store (69,380 train perspectives / 53.99M rows).
- **v2:** trained on the mixed store. Train has 318,766 perspectives:
  - 67,378 C56 and 251,388 S122;
  - 143,740,698 stored rows, after hash-thinning 50% of S122 train WAITs (stored weight 2);
  - 228,863,669 source rows.

### 1.3 Card scope

Filtered corpus: 209,263 games, 416,165 perspectives, 297,342,989 supervision-valid decisions (NS1).

- **Games with any non-C56 card on either side:** 201,268 of 209,263 (**96.2%**). Index read, unique tags.
- **Decisions from perspectives whose own deck has a non-C56 card:** 233.31M of 297.34M (**78.5%**).
- **Supervised plays of non-C56 cards** in the v2 train store: 2,438,684 of 8,361,062 (**29.2%**). That is 65 card
  tokens; 121 own-card tokens have plays in total.
- The human scope is 121 cards: C56, plus 65 new cards including Spirit Empress (`MergeMaiden_Normal`, 9,583 plays),
  minus Three Musketeers.
- The bot's pool is also 121, but swaps those two: it has Three Musketeers and excludes MergeMaiden. **Three
  Musketeers is the one bot-pool card with zero human data.**

**Sam's live Hog deck** (all eight cards are C56). Columns:
- *perspectives:* own deck contains the card;
- *plays:* supervised plays in the v2 **train** store, split into the C56 part (v1's data) and the S122 part.

| card | perspectives C56 + S122 = union | train plays (C56 / S122) | v1 had |
|---|---|---|---|
| Hog Rider | 34,787 + 19,940 = 54,727 | 189,827 (145,299 / 44,528) | 77% |
| Archers | 9,430 + 5,470 = 14,900 | 62,780 (44,567 / 18,213) | 71% |
| Cannon | 41,228 + 20,422 = 61,650 | 182,106 (130,091 / 52,015) | 71% |
| Skeletons | 55,641 + 57,688 = 113,329 | 479,782 (270,677 / 209,105) | 56% |
| Fireball | 30,905 + 73,025 = 103,930 | 162,971 (60,726 / 102,245) | 37% |
| **Zap** | **608** + 78,275 = 78,883 | 138,135 (**1,359** / 136,776) | **1%** |
| Electro Spirit | 46,167 + 28,552 = 74,719 | 308,093 (217,815 / 90,278) | 71% |
| **Bats** | **1,706** + 21,666 = 23,372 | 65,960 (**7,986** / 57,974) | **12%** |

- **Exact deck in the corpus:** 0 perspectives.
- **≥5 of the 8 cards:** 2,358 C56 + 55 S122.
- **≥4 of the 8:** 31,678 + 1,212, mostly Hog 2.6, which shares Hog, Cannon, Skeletons and Fireball.

The full 121-card table is in Appendix A. The thinnest cards are Barbarian Hut (438 plays), Mirror (1,203), Goblin
Machine (1,595) and Clone (2,485).

### 1.4 Trophies and quality

- **No numeric trophy, player id, date or patch** exists in the source or the indexes (NS1 audit). A
  "high-trophy subset" can only use proxies, all read from the indexes:

  | proxy | C56 | S122-new |
  |---|---:|---:|
  | Path of Legends (ranked) | 82.2% | 81.5% |
  | Trophy Road | 6.8% | 7.9% |
  | Card slots at L16 | 84.3% | 84.0% |
  | Card slots at L11 (capped modes) | 14.7% | 14.7% |
  | All 8 cards at L16 | 80.7% | 78.9% |
  | King tower 16 | 84.8% | 84.4% |

- The corpus is dominated by maxed-out ranked players. A Path-of-Legends ∧ all-L16 subset keeps roughly 70–80%, so
  filtering buys little.
- Winners-only filtering failed before (P16 §6: outcome confounded by evo/L16 effects the sim lacks).
- **Recommendation:** no subset for the main run. A PoL∧L16 ×2 weight is at most a later ablation.

### 1.5 WAIT share

- v2 train source rows: 220,428,447 WAITs of 228,863,669, i.e. **96.3% WAIT**, 3.7% play or ability.
- The unthinned C56 part of the store: 95.25% WAIT, 4.68% play, 0.07% ability (37,035).
- Ability labels in total: 65,649 in train (single-champion decks only).
- Cadence is one decision per 5 ticks (250 ms).

## 2. Model and tokenisation

### 2.1 Architectures already in the lineage (configs read from the checkpoints on 04)

| net | config | params | role |
|---|---|---:|---|
| v1 `main02` / v1-fp / **v2** | SetPolicy, vocab 360, width 192, 4 layers, 6 heads, FFN 768, tile width 64, 57 descriptors | 2,254,949 | human IL |
| rl5-v10 / f1a2 | same, but 6 layers, FFN 1536 | 4,918,757 | RL / search-distilled fast tier |

- Heads: a 3-way gate {wait, play, ability}; a permutation-equivariant card pointer over the 4 hand slots; a
  card-conditioned 576-tile head; and the intent head (next card + 13-bin hazard).
- No recurrence. Memory comes from D1 tokens: derived opponent elixir/hand/queue, own deck/queue, 8+8 play histories.
- ClashAI uses the same factorization (gate → card pointer → card-conditioned cell + "wait for X"; ~1.34M parameters).

### 2.2 Full-pool tokens

- The contract-v5 vocabulary (360 tokens, `contract_v5_tokens.json` sha `35db1a76…`) is the token walk over **all
  122 cards**. A full-pool HP1 net needs no vocabulary change.
- v1-fp patched 90 rows that v1 never trained (card ← proxy card, body ← proxy body; 21 shared tokens left alone).
  That was the right fix for a C56-trained net. **v2 already trained those rows on real data** for every human card.
- An HP1 net trained on the v2 store therefore needs no extension. The only bot-pool card without data is Three
  Musketeers: apply `extend.py`'s proxy-row rule to that single card if it ever appears.
- **Opponent-side encoding** is where v1-fp was weakest:
  - in PT2's King-9 rows, 29.4% of opponent deck slots are non-C56 (PT2-DESIGN);
  - v2 has seen 270k perspectives with such opponents.
- Feature builders (`imitation/model/features.py`), the D1 sidecar contract and the v5 mask are unchanged.
  `DerivedD1(costs)` on live16402b-r3 covers the pool. Run a parity check: v2 decisions on recorded roots through
  `student:` vs `imitation.model.inference`, as in the `bot/fullpool/parity.py` pattern.

### 2.3 Action space for full-pool decks

- The action space is unchanged: 2,306 actions = 4 slots × 576 tiles + WAIT (2304) + ability (2305).
- The card is chosen by hand slot, so any 8-card deck is the same action space. The mask carries legality: cost,
  placement, 3×3 Princess footprint, even-footprint snapping.
- Abilities are labelled only for single-champion, non-hero decks (65,649 labels).
- Not in the head: hero/evo forms (played as base) and Golden Knight's ability (no oracle). Both are documented
  limits, not HP1 work.

### 2.4 WAIT imbalance: what the evidence says

| decoding | evidence | verdict |
|---|---|---|
| Greedy argmax gate | v1-greedy: 23 accepted plays in 300 games, 0/300 wins (NS1). P(play) ≥ 0.5 on 0.01% of v1 polls (STRENGTH.md) | never |
| Sampled gate, T = 1 | R3a-sampled − R3a: −0.24 [−0.31, −0.18] vs v1. Overspends: 44.7–51.2 plays/game vs 37–38 | never deploy |
| Threshold calibrated **off-policy** | v1-τ (τ = 0.1387 from sampled-v1 states): plays only 6.9–13.9/game; −0.45 vs sampled v1 | never |
| Threshold calibrated **on-policy** | R3a, it5s2, rl5 (τ0 0.5375), f1a2 (τ 0.6444): 37–38 plays/game; `bot.exit.calibrate --mode rate` (secant on plays/game over CRN cases) | **use this** |
| Re-weighting waits in IL | P16 wait02: 21/192 vs natural 40/192; ClashAI wait-label tweaks null | no |
| Advantage/outcome-weighted IL | P16 winners-only failed (confounded outcomes) | only through RL (b) |

- **Training:** keep T11's natural gate with unbiased wait thinning: the gate loss is on playable rows, and the card
  and tile losses are on plays only, so the 96% WAIT share never touches them.
- **Decoding:** play iff P(play) ≥ τ, with top-1 legal card and tile. τ is fitted by `calibrate --mode rate` on the
  policy's own games.
  - Target plays/game = f1a2's on the same opponents and training bank, ±1.5.
  - Re-check after every weight change, because thresholds don't transfer (v1-τ).
  - Rate calibration is also the play/wait gate the brief asks for. Its "calibrated threshold" means a play-rate
    match, not probability calibration: gate ECE is already 0.001–0.003 after temperature scaling.
- **RL:** the existing r5 scheme.
  - Gate q = σ((logit p − logit τ0)/κ) with κ = 0.1; card and tile at T = 0.1.
  - The mode of q is exactly the deployed gate. Train/serve parity is tested in `bot.rl.test_rl`.

### 2.5 Command-lag alignment (new; measured)

- **The mismatch.**
  - Human labels are the human's own play ticks, re-simulated with no command delay.
  - HEADLINE/RoyaleSim evals, RL and the live loop all execute our command 27 ticks (1.35 s) after the decision
    (`CommandQueue(delay)` in `bot/players/ours.py`). Live tap→deploy is ≈1.4 s; ClashAI measured 28 ticks.
  - So a human-IL policy decides on a state 1.35 s staler than the one its labels assumed.
  - ClashAI's main measured live loss mechanism was exactly this kind of train/serve latency skew (deep dive L3).
- **Measured on the unthinned C56 train rows** (2,462,229 plays; bit order validated: 100% legal at shift 0):

  | shift | card still in hand | same card and tile legal |
  |---|---:|---:|
  | 25 ticks | 99.8% | 93.9% |
  | 30 ticks | 97.0% | 90.5% |

- **Option L1, lag-shifted labels:** attach each play to the row ≥ 27 ticks earlier (row r−6). If that is illegal
  there, use the latest legal row in [r−6, r−1]; drop it only if none is legal (≤ 2.2% have no hand match at r−6).
  This teaches anticipation and keeps train = serve.
- **Option L2:** feed a lag-extrapolated board (ClashAI's 26-tick projection). It needs a forward model in the
  feature path: more code, and a new skew surface.
- **Recommendation:** L1 as a P1 arm (§7). RL in the lagged sim corrects any residual.

## 3. Training plan

### 3.1 Measured IL cost (v2, T11 recipe, one A6000 48 GB per seed)

| | v2 seed 22 | v2 seed 21 |
|---|---|---|
| sampled rows / epochs / steps | 380,566,524 / 6 / 46,459 | 380,571,633 / 6 / 46,460 |
| trainer wall | 12.9 h | 20.5 h |
| CPU | 61.4 CPU-h | 64.3 CPU-h |
| loader-inclusive rate | 7,320 rows/s | 6,718 rows/s |
| dev EMA joint NLL per epoch | 0.2824, 0.2735, 0.2695, 0.2672, 0.2662, **0.2659** | 0.2832 … 0.2663 |

- **Per epoch:** 63.4M sampled rows: every train play, 1/2 of the stored S122 WAITs, 1/4 of the C56 WAITs.
- **Resources:**
  - GPU: micro-batch 7,168, effective 8,192; peak allocated ~28 GB.
  - RAM: ~5–7 GB PSS per loader process, plus page cache over a 228 GB random-mmap store. The hosts have 125 GB.
  - Disk: the store already sits on 04 and 08.
  - Optimizer steps alone ran at ~12.3k rows/s, so the run was loader-bound.

### 3.2 IL options for HP1 (estimates scale v2's measured numbers by forward FLOPs, §5)

| run | model | data | GPU wall | why |
|---|---|---|---:|---|
| **use v2 as is** | 2.25M | done | 0 | the free baseline human init |
| **P1-cap** (pilot) | rl5 arch 6L/FFN 1536, 4.92M, from scratch | 1 epoch (63.4M rows) | ≈3.5 h + ≈0.5 h dev | does capacity help human IL? Matched-rows comparison with v2's epoch-1 dev NLL 0.2824 |
| **P1-lag** (pilot) | v2, fine-tuned | 0.5 epoch, lag-shifted labels (§2.5) | ≈1.2 h | train/serve lag parity |
| HP1-IL-M full | 4.92M | 6 epochs | ≈20–24 h | only if P1-cap wins by ≥ 0.005 nats at 1 epoch |

- **P1-cap's expected rate:** ≈5.5k rows/s. That is 2.1–2.2× v2's FLOPs/row and GPU-bound, at micro-batch 4,096 × 2.
- **Why the rl5 shape:** the RL/ExIt students already use it. Its per-poll cost (f1a2) is known on the Mac path, and
  `bot.rl.learner` handles it (16 GB GPU).
- **Bigger models:** wait for P1-cap's answer and the §5 latency.

### 3.3 After IL: options

**(a) Policy-only bot / fast tier.**
- Steps: `student:<HP1.pt>@τ_rate`, then the §4 gate against f1a2-alone, rl5-alone and the live search.
- Cost: S0 calibration ≈3 CPU-h, plus the gate (§4).
- Expectation: on its own the human net is v1-class. Its value is the init, so (a) is a **post-(b)** decision.
- As a fast tier under search, a full-pool human net would also change the search default.

**(b) RL init for terminal-reward PPO, reusing `bot.rl`.** Recommended main path.
- Init and KL reference: the best human init (v2, P1-lag or HP1-IL-M); r5 used β_KL 0.05.
  - The anchor is the human policy, not it5s2. This keeps human holding and spell timing as the prior that RL
    sharpens. It is the ClashAI recipe, and their KL-free run degenerated.
- **Reward:** terminal ±1 only; shaping drifted ClashAI's gate.
- **Critic:** a separate trunk copy with a 3-update warm-up; λ = 1.
  - Option: pretrain the critic on the store's `recorded_outcome` (416k perspectives). It is confounded, so only as a
    warm start; compare its explained variance with `critic_pretrain`'s ≈0.5.
- **League (fresh RL bank, checked disjoint):**

  | opponent | share |
  |---|---:|
  | LIVE-K4CW-r16-fp (strong) | 20% |
  | R3a-fp | 20% |
  | f1a2 (frozen) | 20% |
  | rl5-v10-fp | 10% |
  | v1-fp | 10% |
  | own snapshots | 20% |

- **Decks:** our deck rotates the full-pool sampler, Sam's Hog deck (25%) and ~5 Battle Log decks (standing
  deck-diverse rule). Opponents use full-pool sampler and Battle Log decks. L16.
- **Throughput:**
  - Policy-vs-policy games cost ≈50–55 CPU-s; K4CW games cost ≈3–4× that.
  - Budget ≈80 CPU-s/game: at 48 workers that is ≈2,100 games/h and ≈120k learner transitions/h.
  - 24 h ≈ 50k games and ≈2.8M transitions, against ClashAI's 24M.
  - GPU: the learner holds ≤16 GB.
  - Eval every 10 updates on a dev bank. r5's collapse rules apply (KL > 0.5 nats/transition; train win-rate up
    while the paired eval drops below −0.05 twice).
- **Why this is the lever:**
  - search − rl5-alone ≈ +0.02/+0.05/+0.03 (NS1, CIs span 0);
  - rl5 and f1a2 descend from v1, which saw ~1,400 Zap and 121 Giant plays;
  - Sam's binding direction is per-tick decisions with *learned* holding, which a policy at 5-tick cadence is by
    construction.
- **Known risk:** r5 PPO moved it5s2 only +0.013/+0.027 by v20. A better init may move the ceiling or may not. That
  is what (b) measures.

**(c) Search prior (PT2).**
- Replace v1-fp with v2 (later HP1) as π in `bot/search/priortb.py` (token `hp<N>`). This removes PT2's proxy-row
  caveat and is natively full-pool on both sides.
- Optionally use v2 top-N as K4C proposer rows next to R3a top-16.
- Cost: one 2.25M forward per search decision ≈ 7–11 ms on a 127x core, i.e. ≤ 2% of the ~500 ms decision.
- The value is bounded: search adds ≈0.03 over policy alone, so (c) runs as PT2's own track.

## 4. Eval gates (pre-registerable; fresh banks drawn by `int.from_bytes(os.urandom(6),'big')<<4` at registration, `check_bank`-disjoint from HEADLINE, TRAIN1, NS1, NS2 and RL banks)

**G-A, offline:**
- Data: the v2 store; select on **dev** only; score eval and eval_ood once.
- Metrics: T11's A1–A4 metrics plus per-card slices for Sam's 8 cards and Giant.
- Spell proposals: top-8 recall of Zap/Fireball/Arrows at human spell moments (ClashAI L6: Rocket was 24% calibrated
  but rarely argmax).
- The ECE bar is unchanged. P1-cap pass: dev EMA joint NLL at 1 epoch ≤ 0.2774 (v2's 0.2824 − 0.005).

**G-B, policy-only sim, primary:**
- Protocol: `bot.eval.headline`, RoyaleSim 0.1.34 / 16.402, `--levels max` (all cards and towers L16 both sides),
  `--decks fullpool:<seed>`, 27-tick lag, PYTHONHASHSEED=0, the live16402b-r3 env and FullPoolBelief prior as NS1/NS2.
- Arms, all on identical cases and seats:

  | arm | player |
  |---|---|
  | H | HP1 candidate `student:<ckpt>@τ_rate` |
  | F | f1a2 alone, `@0.6444` (its shipped calibration) |
  | R | rl5-v10-fp alone, `@0.5375` |
  | S | live search `LIVE-K4L-R-gs-rw-fc-w200-t4-p4-mk1a1-res-wint`, deadlines cleared, serial twin |

- Opponents: **LIVE-K4CW-r16-fp** (strong, never pooled), R3a-fp, v1-fp.
- Size: 300 cases × 3 opponents × 4 arms = 3,600 games, plus a 24-game smoke (0 errors required).
- **Primary:** H − F vs K4CW-fp; claim if the lower bound of the 95% paired bootstrap CI > 0 (4,000 draws, Random(0),
  sorted[100]/[3899]).
- **Secondary:**
  - H − S per opponent, non-inferiority margin −0.03 (a policy-only live candidate);
  - H − R;
  - equal-weight R3a+v1 pooled contrasts.
- Power: the NS2 note gives half-width ≈7 pp at n=300 against the strong opponent, so ≈10 pp is detectable at 80%.
- **Sam-deck row:** our deck fixed to the Hog deck vs Battle Log pool v3 opponents, L16, 200 cases, arms H/F/S, via
  `bot/livediag/l16_cadence.py`. That driver currently hard-codes its fast-tier specs, so a `student:` arm needs a
  small player pass-through; check before registering.

**G-C, account row (secondary):**
- `l16_cadence` / deckopt3 `--levels account`: our verified account levels vs each row's logged levels and King, as
  in PEKKA-1. Sam's deck, 200 cases, H vs S.
- HEADLINE itself exposes only `--levels none|max` (NS2), so this row can't run there.

**G-D, behaviour (descriptive, definitions fixed in `bot/livediag/behaviour_diag.py`):**
- per arm and opponent:
  - plays/game and elixir leaked;
  - (a) spell/swarm/tower-only casts;
  - (b) spell windows taken / missed / short;
  - (c) `push_elixir` when an enemy push reaches our bridge;
  - (d) Giant plays by zone and elixir;
  - (e) swarm response within 6 s;
  - reaction cadence (enemy accepted play → our next accepted play, `l16_report.reaction`) and undefended Giant
    pushes.
- **Hog timing:** (d) is Giant-only. Register a Hog analogue before any game: Hog plays by elixir at play and
  whether each is within 5 s of an enemy commit (a counter-push). This is a small addition to `behaviour_diag`.
- Human reference: `behaviour_diag human` on the Parquet for (d), (e) and Hog timing.

**G-E, RL snapshots (b):** r5's curve, then a confirm on fresh cases 300–599. Only the best snapshot goes to G-B. Per
the RL snapshot-bias memory, claims come only from fresh banks.

**Ship rule** (BOT LEAD decides):
- an HP1 policy replaces f1a2 as fast tier if G-B H − F > 0 (LB) and no behaviour regression;
- it replaces the live search only if H − S ≥ −0.03 (LB) on K4CW-fp **and** the Sam-deck row, then the live A/B.

## 5. Live feasibility (Mac mini M4 Pro, 8P+4E, 24 GB; owned by the loop owner, not touched; estimates)

| net | params | fwd GFLOP at 62 / 77 / 128 tokens | measured on fleet (one 127x core) |
|---|---:|---|---|
| v1/v2 (4L/768) | 2.25M | 0.31 / 0.37 / 0.60 | feature build + top-8: p50/p99 7.1/7.4 ms (10 entities), 11.3/11.6 ms (78) (`imitation/PROGRESS-model.md`) |
| rl5/f1a2 (6L/1536) | 4.92M | 0.65 / 0.79 / 1.30 | fast tier 17.4–17.6 ms per poll, mean, incl. D1/observe (fullpool PROGRESS 2026-10-16) |
| 8L d256 (hypothetical) | ≈7M | 0.89 / 1.10 / 1.84 | — |

Tokens ≈ 52 fixed (hand, deck, queues, opponent derived, seen, 16 history, global, CLS) plus entities (p50 10, p99 25).

- **Budget:** the Mac gate is poll-step p95 ≤ 60 ms. Live s74 searched runs gave per-battle poll-step p95 44–64 ms.
  f1a2 already runs on every poll on the Mac today.
- **Policy-only:** removes the search; the policy itself is ≈10–20 ms.
  - Estimate for the Mac: ≈5–12 ms for v2-size and ≈10–18 ms for rl5-size on one P-core under live load. An M4 P-core
    is at least as fast per thread as a Zen 2 3990X core, but the bench-is-a-lower-bound memory applies.
  - That leaves ≥30 ms of headroom. About 2× rl5's FLOPs (≲1.6 GFLOP at p99 tokens) still fits on CPU.
- **CoreML is not needed up to ≈5M parameters.** Consider it only for ≥10M models:
  - the ANE/GPU is shared with the YOLO perception models;
  - display-capture and SCK contention are known latency sources.
- Any Mac bench runs in a planned pause with the loop owner's explicit go (ladder-gap memory).

## 6. Risks and unknowns

1. **Human IL alone is weak in our sim.** v1 at T = 1 loses 0.88 to rl5-alone and 0.93 to search. v2 may be only
   modestly better. Mitigation: (b) is the plan, and S0 measures v2's standalone level first.
2. **Re-sim fidelity.**
   - Labels were reconstructed in the old Python engine: L11, base forms, gamedata 3d99987c.
   - We evaluate in RoyaleSim 16.402 at L16. Balance drift and evo/hero substitution are distribution shift.
   - RL in the eval engine is the correction. Report per-card behaviour, not just score.
3. **Lag skew** (§2.5). Unproven whether L1 helps in play. The P1-lag vs v2 S0-style screen decides.
4. **The RL ceiling** may be unchanged: r5's +0.01–0.03 and ClashAI's +3–4 pp. RL throughput (≈2k games/h) is small.
   Kill rule: no G-E gain after ≈30 updates → stop and report.
5. **Gate calibration drift.** Every new checkpoint needs on-policy rate calibration; off-policy thresholds collapsed
   (−0.45).
6. **Data quality has no trophy signal.** PoL + L16 proxies only. Meta skew: Hog 2.6 alone is 16% of C56. The
   generalist matched specialists before (A2; ClashAI).
7. **Leakage.** Keep roles v2 frozen and select on dev only. The S122 eval_ood families have never been fitted.
8. **Champion abilities and Collector** make D1 inexact in ≈23% / 6% of opponent decks (the `elixir_exact` flag).
   Golden Knight's ability is unlabelled; Three Musketeers has no data.
9. **Licence:** IL_Replay's licence is unstated, so internal use only, as now.
10. **Compute contention.** At 22:4xZ all three A6000s were busy: 01 98% (29 GB), 04 78% (15 GB), 08 99% (29 GB, lent
    to YOLO).
    - P1 fits beside one job on 04 (33 GB free), but slower; a dedicated window is better.
    - CPU work must yield to NS2, deckopt3, LV2 and WINT-ACC1 under `cpu_job.sh` / nice 15.
    - 04 has a console user: load ≤ 70.

## 7. First concrete step

**S0 + P1, about one day, at most ≈5 GPU-h and ≈30 CPU-h:**

1. **S0 (CPU only, can queue now on 04/01 under `cpu_job.sh`, nice 15):**
   - `student:<v2 best-dev>`: write a `.calibration.json` via `bot.exit.calibrate --mode rate`. Target = f1a2's
     plays/game vs R3a-fp and v1-fp on TRAIN1 indices; 3–5 rounds × 64 games.
   - A 100-case **screen** on a fresh dev bank: arms v2@τ, f1a2@0.6444 and v1-fp (stock T = 1) vs R3a-fp, v1-fp and
     K4CW-fp; L16 full-pool decks. Smoke first.
   - Cost ≈20 CPU-h (policy games ≈55 CPU-s; K4CW games ≈3–4×), i.e. ≈1.5 h wall at 16 workers.
   - Read: v2's standalone level vs v1-fp and f1a2, plus behaviour G-D. Screen only; no claim.
2. **P1 IL pilot (GPU, one A6000 on 04 or 08, store already local):**
   - **P1-cap:** rl5-shape SetPolicy (6L, FFN 1536, 4.92M), from scratch.
     - Data: one epoch of the frozen T11 sampler on `v2-store-v1/train`: 63.4M rows, including all 8.36M plays.
     - Recipe: T11 (AdamW 3e-4, cosine, warmup 2k, EMA 0.999, effective batch 8,192 = 2 × 4,096).
     - Cost ≈3.5 h train + ≈0.5 h dev scoring.
     - Pass: dev EMA joint NLL ≤ 0.2774.
   - **P1-lag:** v2 fine-tuned for 0.5 epoch (≈32M rows) with lag-shifted play labels (L1, §2.5); lr 1e-4. ≈1.2 h.
   - Both get rate-calibrated and join the S0 screen (≈6 CPU-h more).
   - The trainer is a copy of `imitation/t11/train.py` with config arguments and the label shift in the sampler.
     T11's files stay frozen. New code is reviewed before any host run (review-before-host-scripts).
   - RAM ≤ 20 GB PSS; disk: +≈80 MB per checkpoint.
3. **Decision after S0 + P1:**
   - Pick the RL init: v2, P1-lag, or (if P1-cap passes) a full HP1-IL-M run (≈20–24 GPU-h).
   - Register G-B and G-E.
   - Start (b) in a GPU window, ≤16 GB, plus 48 CPU workers.
   - Hand v2 to the PT2 owner as π for (c) now; it needs no HP1 work.

## 8. Handoff notes (for any HP1 owner, helper or babysitter brief)

- **STANDING RULE (Sam, via BOT LEAD, 2026-10-17): always steer, never queue.**
  - Every `t3_thread_send` to any thread or agent uses `mode: "steer"`.
  - If it returns `thread_not_sendable` (the target is idle), resend the same text with `mode: "auto"`.
  - Never use `queue`.
  - Copy this rule verbatim into every helper brief.
- Report to the BOT LEAD. Hosts 01/04/08 only. Never 02, 03, 05, 06, 07 or 09–18. Never `pkill -f`; kill only
  verified own PIDs/PGIDs. Times from `date -u`, hashes from commands. Commit via a temp index on origin/main with
  `clasher-secret-scan`; no data or checkpoints in git.
- The Mac belongs to the loop owner: no Mac jobs without their explicit go in a planned pause.

## Appendix A — supervised plays per card in the v2 train store (union; second number = the C56 part = what v1 trained on)

Counted on 04 at 22:34Z: `expert_actions` < 2304 and `supervision_valid`, card = `hand_ids[row, action // 576]`.
Totals: 8,361,062 plays (C56 2,462,229 / S122 5,898,833) and 65,649 abilities. The stored S122 WAITs are thinned to
50%; plays are never thinned.

| card (* = non-C56) | plays | of which C56 store | card | plays | C56 | card | plays | C56 |
|---|---:|---:|---|---:|---:|---|---:|---:|
| 1. Skeletons | 479,782 | 270,677 | 42. Bomber* | 69,972 | 0 | 83. Rocket | 30,868 | 15,253 |
| 2. BarbarianBarrel | 356,566 | 70,334 | 43. Tombstone* | 69,132 | 0 | 84. NightWitch* | 30,729 | 0 |
| 3. Berserker | 324,974 | 88,738 | 44. Wallbreakers | 68,897 | 27,966 | 85. SuspiciousBush* | 30,407 | 0 |
| 4. ElectroSpirit | 308,093 | 217,815 | 45. Bats | 65,960 | 7,986 | 86. MagicArcher* | 30,052 | 0 |
| 5. Log | 273,514 | 194,771 | 46. DarkPrince | 65,775 | 4,821 | 87. SkeletonKing* | 29,674 | 0 |
| 6. IceSpirit | 212,526 | 150,510 | 47. Archers | 62,780 | 44,567 | 88. Hunter* | 29,081 | 0 |
| 7. HogRider | 189,827 | 145,299 | 48. GoblinGang | 61,524 | 17,202 | 89. Pekka* | 28,887 | 0 |
| 8. Cannon | 182,106 | 130,091 | 49. SkeletonDragons* | 61,260 | 0 | 90. MinionHorde | 25,936 | 691 |
| 9. Fireball | 162,971 | 60,726 | 50. Vines* | 58,847 | 0 | 91. Rage* | 25,625 | 0 |
| 10. AngryBarbarians | 154,920 | 7,035 | 51. FireSpirits | 57,694 | 6,652 | 92. LavaHound* | 24,612 | 0 |
| 11. Zap | 138,135 | 1,359 | 52. Heal* | 57,409 | 0 | 93. RoyalDelivery | 24,592 | 13,357 |
| 12. IceGolem | 136,354 | 91,401 | 53. Bandit* | 54,910 | 0 | 94. Xbow | 24,334 | 15,458 |
| 13. Knight | 135,392 | 53,438 | 54. MovingCannon* | 54,494 | 0 | 95. ElectroGiant* | 22,883 | 0 |
| 14. RoyalGhost | 134,570 | 33,131 | 55. Giant | 54,013 | 121 | 96. RoyalRecruits* | 22,247 | 0 |
| 15. Musketeer | 124,241 | 70,494 | 56. GoblinDrill* | 53,964 | 0 | 97. GiantBuffer* | 22,172 | 0 |
| 16. Tornado | 117,288 | 322 | 57. GoldenKnight* | 53,851 | 0 | 98. MegaKnight* | 21,873 | 0 |
| 17. Valkyrie | 107,048 | 27,314 | 58. MiniPekka | 52,466 | 3,790 | 99. SpearGoblins* | 21,538 | 0 |
| 18. GiantSnowball* | 106,459 | 0 | 59. ElectroWizard* | 51,396 | 0 | 100. Barbarians* | 20,732 | 0 |
| 19. BattleRam* | 106,372 | 0 | 60. IceWizard* | 50,463 | 0 | 101. Elixir Collector* | 20,649 | 0 |
| 20. BabyDragon | 105,604 | 3,867 | 61. Poison | 48,814 | 1,134 | 102. InfernoTower | 18,433 | 11,258 |
| 21. Princess | 102,024 | 80,407 | 62. GoblinHut | 47,853 | 29,212 | 103. Phoenix* | 17,581 | 0 |
| 22. MiniSparkys* | 100,732 | 0 | 63. Rascals | 47,824 | 1,647 | 104. ArcherQueen | 17,493 | 10,842 |
| 23. FirespiritHut | 98,335 | 45,127 | 64. BombTower | 47,789 | 13,046 | 105. DarkMagic* | 16,009 | 0 |
| 24. GoblinBarrel | 94,730 | 76,354 | 65. Lightning | 47,787 | 14,085 | 106. RamRider* | 15,181 | 0 |
| 25. DartGoblin | 92,787 | 41,668 | 66. Goblinstein | 47,104 | 13,838 | 107. DartBarrell* | 14,908 | 0 |
| 26. Miner | 91,890 | 5,695 | 67. Freeze* | 45,964 | 0 | 108. Prince | 13,368 | 1,350 |
| 27. Minions | 88,871 | 2,000 | 68. MegaMinion* | 44,813 | 0 | 109. Monk* | 12,311 | 0 |
| 28. SkeletonBarrel* | 87,155 | 0 | 69. Goblins | 41,742 | 14,023 | 110. MergeMaiden_Normal* | 9,583 | 0 |
| 29. Arrows | 86,676 | 469 | 70. Lumberjack* | 41,668 | 0 | 111. GoblinCurse* | 9,566 | 0 |
| 30. Bowler* | 86,661 | 0 | 71. Earthquake | 41,077 | 36,851 | 112. LittlePrince* | 9,291 | 0 |
| 31. Tesla | 86,189 | 50,873 | 72. AxeMan* | 39,832 | 0 | 113. Ronin* | 8,976 | 0 |
| 32. Firecracker | 85,698 | 68,938 | 73. GoblinCage* | 38,884 | 0 | 114. ElixirGolem* | 8,127 | 0 |
| 33. RoyalHogs | 85,623 | 65,308 | 74. Golem | 37,805 | 145 | 115. GoblinGiant* | 7,179 | 0 |
| 34. SkeletonArmy | 85,153 | 31,635 | 75. ZapMachine* | 37,724 | 0 | 116. BossBandit* | 6,841 | 0 |
| 35. InfernoDragon* | 83,701 | 0 | 76. Fisherman* | 37,119 | 0 | 117. BattleHealer* | 3,921 | 0 |
| 36. Balloon | 81,177 | 296 | 77. Graveyard* | 35,733 | 0 | 118. Clone* | 2,485 | 0 |
| 37. MightyMiner | 75,697 | 64,669 | 78. Guards* | 33,508 | 0 | 119. GoblinMachine* | 1,595 | 0 |
| 38. WitchMother* | 75,406 | 0 | 79. Witch* | 33,434 | 0 | 120. Mirror* | 1,203 | 0 |
| 39. Mortar* | 74,639 | 0 | 80. ElectroDragon* | 32,247 | 0 | 121. BarbarianHut* | 438 | 0 |
| 40. Wizard | 71,689 | 6,173 | 81. RoyalGiant* | 32,145 | 0 |  | |  |
| 41. GiantSkeleton* | 71,309 | 0 | 82. GoblinDemolisher* | 31,125 | 0 |  | |  |

Own-deck perspectives per card (C56 index + S122 index, union of 416,165):

barbarian-barrel 136,305; skeletons 113,329; fireball 103,930; berserker 97,241; the-log 86,014; elite-barbarians 81,317; zap 78,883; tornado 75,602; electro-spirit 74,719; arrows 67,365; cannon 61,650; hog-rider 54,727; zappies 46,782; battle-ram 45,664; lightning 44,651; ice-spirit 44,359; balloon 43,479; mother-witch 41,550; giant-snowball 41,219; royal-ghost 41,171; baby-dragon 40,738; inferno-dragon 40,600; wizard 39,614; bowler 39,020; vines 38,997; valkyrie 38,759; knight 37,998; minions 37,464; musketeer 36,699; skeleton-army 35,810; freeze 34,700; miner 34,287; giant-skeleton 33,739; ice-golem 32,057; royal-hogs 30,450; golem 29,120; giant 28,477; furnace 28,435; electro-wizard 28,083; tombstone 27,756; mini-pekka 27,722; princess 27,688; skeleton-dragons 27,557; tesla 27,476; dark-prince 27,366; skeleton-barrel 27,095; poison 26,918; dart-goblin 26,693; goblin-barrel 26,045; rocket 25,247; graveyard 25,172; mortar 24,570; bomber 24,287; bats 23,372; sparky 23,082; goblin-gang 22,749; cannon-cart 22,746; golden-knight 22,498; heal-spirit 22,371; bandit 21,998; bomb-tower 21,502; firecracker 21,364; night-witch 20,475; executioner 20,352; wall-breakers 20,204; goblin-hut 20,160; earthquake 19,723; rascals 19,543; mighty-miner 19,399; mega-minion 19,270; electro-dragon 18,663; goblin-drill 17,736; pekka 17,598; lumberjack 17,421; goblin-cage 17,367; rage 17,225; guards 17,216; goblinstein 17,108; ice-wizard 16,744; minion-horde 16,736; elixir-collector 16,703; lava-hound 16,401; royal-giant 16,262; witch 15,788; archers 14,900; fisherman 14,778; void 14,598; fire-spirit 14,438; skeleton-king 14,328; mega-knight 13,655; hunter 13,000; barbarians 12,940; electro-giant 12,699; goblins 12,366; magic-archer 12,327; inferno-tower 11,344; royal-recruits 10,577; goblin-demolisher 9,696; rune-giant 9,693; elixir-golem 9,614; x-bow 9,347; royal-delivery 9,099; suspicious-bush 8,897; ram-rider 8,434; phoenix 8,109; goblin-curse 7,623; spear-goblins 6,513; flying-machine 6,436; prince 6,403; archer-queen 5,735; monk 5,333; spirit-empress 4,880; ronin 4,869; boss-bandit 4,762; goblin-giant 4,209; little-prince 4,095; battle-healer 2,282; clone 2,088; goblin-machine 1,473; mirror 1,113; barbarian-hut 295

## Appendix B — evidence

- **Repo:**
  - `reports/bot/NOSEARCH-20261017.md`, `NOSEARCH-NS2-20261017.md`;
  - `imitation/RESULTS-v2-offline.md`, `PROGRESS-T11.md`, `PROGRESS-model.md`;
  - `reports/strategy_council_20260928/imitation/{DESIGN.md,PROGRESS-s122.md,S122-CARD-COUNTS.tsv,s122/build_payloads.py}`;
  - `reports/bot/fullpool/{INVENTORY,BUNDLE,PROGRESS}.md`;
  - `reports/bot/rl/DESIGN.md`, `reports/bot/STRENGTH.md`;
  - `reports/bot/prior-tb/PT2-DESIGN.md`;
  - `reports/bot/live-diag/RESULTS.md` §12–14;
  - `reports/clashai_deepdive_20261008.md` (method only; no ClashAI code read or used);
  - `bot/{exit/student.py,exit/calibrate.py,rl/learner.py,players/ours.py,livediag/behaviour_diag.py,livediag/k4cw_fp.py,fullpool/extend.py,fullpool/cards.py}`.
- **Host reads (all read-only; scripts kept off-host in a scratch dir and fed over ssh stdin; outputs in this
  report):**
  - 04: the two perspective indexes (`own_base`, `own_levels`, `battle_type`, `tag`);
  - 04: v2 store `train/{expert_actions,expert_action_supervision_valid,corpus_s122,hand_ids,episode_ids,submitted_ticks,mask_index}` and `mask_table`;
  - 04/01: checkpoint headers and SHA256 of v2, v1-fp and rl5;
  - 01/04/08: `nvidia-smi` and `free`.
