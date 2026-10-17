# LVG2: level value per card for Sam's new live deck. Pre-registration (cycle-model owner, for the BOT LEAD; written before any LVG2 game)

Purpose: rank the next card upgrades for Sam's live deck. The answer drives real gold and wild-card spending.
Exploration tier; simulation (RoyaleSim 16.402); one bank.

**BASE = 124637565273176.** Drawn with os.urandom(6) at 2026-10-17T22:30:33Z, before any LVG2 game; logged in job
dir bot-cycle/lvg2/lvg2-base.txt on 04 and 08.

## Deck and levels

The deck is the BOT LEAD's second correction (Sol-confirmed screenshot) and the LIVE LEAD's levels:
- Skeletons 7, Archers 8, Bats 8, Cannon 9, Fireball 7, Zap 9, Electro Spirit 8, Hog Rider 8; King 7.
- Bats, Fireball and Zap were upgraded after the 22:25Z collection read, so these levels override that file.
- Electro Spirit L8 is boosted; its base level is unverified. The simulation plays it at 8.
- Collection: clasher-live/reports/live/account/collection-20261017b.json, sha256 0078ecde…, read 22:25Z. It is used
  only for copies and gold in the cost readout.

## Design

**Arms** (paired on every case; only our card levels differ):
- `base`, at the levels above;
- 8 singletons, each one card +1: `sk8` Skeletons 7→8, `ar9` Archers 8→9, `ba9` Bats 8→9, `ca10` Cannon 9→10, `fb8`
  Fireball 7→8, `zp10` Zap 9→10, `es9` Electro Spirit 8→9, `hr9` Hog Rider 8→9.

**Player:** the live `res-lb-wintp` = LIVE-K4L-R-gs-rw-fc-w200-t4-p4-mk1a1-res-lb-wint, through lopp_fast.make_live_lopp.
It is a serial twin with deadlines cleared, as in WINT-ACC1 and PT1, on source tree main 68816487f (pt off). The
planner stays all-L11, as deployed.

**Opponents:**
- **LIVE-K4CW-r16-fp: 100 cases** (seeds BASE + i).
- **R3a: 50 cases** (seeds BASE + 5000 + i).
- The two seed sets are disjoint.

**Opponent decks and levels** (the "row A" setup):
- Pool v3.2 (battlelog-pool-v3.2.jsonl, sha256 01732d23…), drawn uniformly by row index, so duplicates keep their
  observed frequency.
- Eligible rows: complete logged card levels; logged opp_king_level 9; no Goblin Hut.
- That gives **53 rows (34 distinct decks)**: 92, 108-114, 116, 118, 119, 122-131, 133-141, 143, 144, 146, 148, 149,
  151, 152, 154-168, 170.
- Each opponent plays at its row's logged card levels and King 9. We play at our levels and King 7.

**Code:**
- Driver cadence-lvg2: a copy of live-diag's cadence-pk1 (174b70bb…) that adds `--own-deck` (strata path only; the
  default is unchanged) and its own path. l16_cadence.py 00e67fb4…, run-l16-cadence.sh 42ae3683….
- Vocab: vocabv3/vocab-full.json.
- One driver run per (arm, opponent): 18 runs, 1,350 games.

**Hosts:** 08 (+ 04 ≤ 70 load), below deckopt3 / WINT-ACC1 / LV2 / NS2 and above PT1. PT1's lanes are paused if the
room is needed.

## Readout (pre-registered)

**Primary:** for each singleton, Δ = score(arm) − score(base), score = win 1 / draw .5, paired by (opponent, case):
- vs K4CW-fp (100 pairs);
- vs R3a (50);
- pooled over all 150 pairs, which is the ranking statistic.
- Each with a normal 95 % CI.

**Ranked upgrade order:** by pooled Δ, with:
- (a) Δ per 1,000 gold, from the official rarity-aware table (bot-deckopt3/inputs/official-upgrade-table.json,
  sha256 08a1040a…; commons +1 from L costs index L−1, rares index L−3);
- (b) Δ per missing copy, from the collection's copies after the post-read upgrades;
- (c) whether it is affordable now. Gold is 94,645 at the read. Wild cards are not shown in the screenshots, so they
  are unknown.

**Caveats, stated in advance:**
- One bank; the CIs are pointwise.
- Simulated opponents use the live opponents' logged decks and levels with our strong policies (K4CW-fp, R3a).
- The planner is all-L11.
- The Electro Spirit base level is unverified.

No early stopping. All runs are read together once complete.

**Amendment 1 (2026-10-17 ~23:20Z, before any top-up game; the 18 registered runs are unchanged).**

Live swaps Bats → Valkyrie 7 at the next battle end, so a small top-up is added. It runs after the 18 registered runs
and before PT1 resumes.
- **Arms:**
  - `vbase`: the new deck Skeletons 7, Archers 8, **Valkyrie 7**, Cannon 9, Fireball 7, Zap 9, Electro Spirit 8,
    Hog Rider 8; King 7;
  - `va8`: the same deck with Valkyrie 7 → 8.
- **Bank and setup:** vs LIVE-K4CW-r16-fp, 100 cases on the same bank design as the main runs (seeds BASE + i, the
  same 53 pool v3.2 rows, the same player and driver).
- **Pairing:** case i has the same opponent row, seat and seed as the main runs.
- **Readout:**
  - Valkyrie +1 Δ = va8 − vbase, paired, normal 95 % CI. It is added to the ranked list with gold and copy costs
    (Valkyrie is rare; 7 → 8 costs index 4 of the Rare table).
  - The deck swap itself is also reported, as vbase − base vs K4CW-fp, paired on the same cases.
  - The other seven singleton deltas were measured on the Bats deck. They are applied to the Valkyrie deck as an
    approximation, stated in the readout.
