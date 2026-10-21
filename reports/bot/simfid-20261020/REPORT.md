# Engine fidelity on live recordings, the full-pool calibration port, and a replay-rebuild prototype

2026-10-20, 127x05. Exploration tier: one harness per corpus, no preregistration. Nothing was deployed, and no running
job or runtime root was changed. Companion reports: [PORT.md](PORT.md) (calibration port) and [REBUILD.md](REBUILD.md)
(replay rebuild).

## Answer

- **The RL environment's engine was the uncalibrated one.** HP1's "ours" env plays the true game in the full-pool
  Python engine of runtime root `live16402b-r3`. That root is engine-cards r1-cards2 plus the 16.402 stat overlay. The
  Oct 14 native calibration (batches 1+2) had only gone into `src/clasher` and `engine-rs`. On T1 the RL engine scored
  50.8% within ¼ tile; calibrated main scored 72.5%.
- **Fixed.** The calibration is ported rule by rule into `engine-cards` (Python, Rust and data; PORT.md). One
  overlay data fix is added: Skeletons keep SummonRadius 700 against RoyaleSim's 16.402 value of 400 (§3, #3).
- **Before → after, RL configuration** (engine + 16.402 overlay + runtime crown pins):

| corpus | metric | before (live16402b-r3) | after (this branch) | reference |
|---|---|---|---|---|
| T1, 577 native fixtures (15.535) | non-tower ≤¼ tile | 50.76 | **70.15** | calibrated main 72.48, RoyaleSim 15.535 78.8 |
| | non-tower HP exact | 65.14 | **73.81** | 80.56 / 81.8 |
| | winner agrees | 423 | **449** | 448 / 477 |
| LIVE, 256 Hog 2.6 games, 575 segments | ≤¼ tile at 5 / 10 / 20 s | 72.5 / 62.3 / 53.6 | **82.6 / 73.4 / 62.5** | |
| | HP within 2% at 5 / 10 / 20 s | 92.6 / 86.8 / 79.5 | **93.5 / 88.5 / 82.3** | |
| | tower HP error at 20 s, per tower | 55 | **50** | |
| | tower damage error at 20 s, per side | 150 | **138** | |

- **T1 with 15.535 data has no regression.** The ported engine reproduces calibrated `src/clasher` on all 577
  fixtures, per fixture (72.48 / 80.56 / 448; PORT.md). Python↔Rust digest parity is 574/577, the same 3 pre-existing
  mismatches as BATCH2. The overlay hold is data only. It passes the BATCH2 gate on train (ACCEPT) and on all 577
  under leave-one-fixture-out (one Angry Barbarians cascade). Parity under the new overlay is still 574/577.
- **Stats at our real levels were already right.** Hog Rider L10 hits a tower for 288, Fireball L8 crown damage is
  120, Zap L9 is 40, and crown towers L9/10/11 hit for 90/99/109. All equal the live client exactly. The divergence is
  mechanics: formations, spawns, swarms and combat cascades.
- **Replay rebuild:** opening-hand inference works (every side of 999 random replays has a consistent ordinary-cycle
  assignment). But the rebuilt games are not faithful human states. On the final engine, winners agree 61.0% on 1,000
  random replays, below the 62.1% always-team baseline. 0 of 1,000 matches are fully supported (evolutions/heroes are
  in every deck). Our engine ends 53% of them early (§5).

Branch `simfid-20261020`. Work dir `/mpac/sdicks02/jobs/clasher/simfid-20261020/` on 127x05.

## 1. The live-recording harness (`bot/simfid/live_*.py`)

**Data.** The data is the retained live-memory games at `/mpac/sdicks02/scratch/live-mem/mirror/mem-c*/m*`, current
Zap Hog 2.6 deck only, where our card levels are exactly known (account-levels.json: Skeletons 8, Musketeer 7, Ice
Golem 7, Cannon 9, Fireball 8, Zap 9, Ice Spirit 8, Hog Rider 10; King/Princess 9). The cohort is frozen in
`live-manifest.json`: 256 completed games, with the sha256 of each `records.jsonl`. Older-deck games are excluded
because their levels changed mid-day. Read-only.

**Public information only.**
- *Our plays:* our own landed commands. The card and exact tap tile come from the decision action; the tick comes
  from `tap_landed`.
- *Opponent plays:* derived from public births. Tracks are matched frame to frame per (owner, card, body class). New
  bodies cluster into one deployment, and a deployment is a play when it contains a main body and no body of that card
  is alive nearby. Spells come from public carriers (Fireball/Arrows/Rocket/Goblin Barrel/Snowball first sighting and
  destination).
- *Validation of the derivation:* applied to our own side, births recover 5,513 of 5,561 own troop commands (99.1%).
  The placement equals the tap tile to 0.001 tile.
- *Levels:* the opponent's tower level and card levels come from the public HP fractions (the client shows tower HP
  numbers and unit level badges). A level is accepted only when it is the unique one whose max HP makes ≥ 90% of the
  observed fractions integer HP; ties are unresolved. Checked on our own side: 1,155 card-level reads, 0 wrong, 893
  unresolved (spells, never-damaged cards, ties). These levels configure the simulation; no policy sees them.

**Segments.** A segment starts at a quiet public record just before a play. "Quiet" means three things: no troop or
building on the board, no public spell carrier in flight (±3 ticks), and no play of either side in the preceding 80
ticks. Towers get the recorded HP, and dead towers are reproduced. An already-awake king gets the activation time
elapsed since its public wake (first damage or a princess down), and its first-hit phase is spent if its
KingProjectile was seen. Every play then goes through the engine's own deploy path (hand, placement, formations,
levels) for 20 s. Interventions are counted, not hidden (hand_forced, elixir_topped, retried/dropped deploys). No
hidden attack clock or target is invented.

**Seat.** We are natively seat 1 in 234 of 251 games. Records are in our frame, so the engine simulates us in our
native seat, rotating the frame 180° for seat 1. The rotation matters: the calibrated side-1 back-row bound shows up
in live data as our seat-1 back-row bodies being born at y ≥ 1.0 (Ice Spirit +0.5 tile in 50 of 58 cases). Seat-0
bodies are not bounded. RL already alternates seats (`seat = g % 2`), so both rules are exercised there.

**Tick convention.** Offsets −2 … 0 (first pass −3 … +2) were tried on a 1-in-8 discovery subset. −1 is best at every
horizon (74.0 / 62.9 / 53.4 against 72.9 / 62.7 / 52.8 at 0), the same as T1's convention, and it is frozen. A route
audit of undisturbed Hog walks shows a constant +0.12 tile (one tick) lead in the native walk, exactly what −1 absorbs.

**Scoring.** On every truth record, units group by (owner, creating card, main body or child) and pair with an exact
minimum-distance assignment (`hungarian`, checked against brute force). A unit-tick is one pair or one unmatched unit.
- *Position:* within ¼ tile and within 1 tile.
- *HP:* within 2% of max. Truth bodies with no logged HP, matched or not, are left out of the HP denominator.
- *Towers:* absolute HP error, damage dealt per side, death agreement.
- *Intervals:* bootstrap over games.

Breakdowns: per card (owner|card) and per interaction (own card × opponent card both played in a segment).

**Truth quality, found and handled (each counted; the *clean* tier excludes the flagged segments):**
- **Opponent evolution/hero forms:** in 74 of 251 games (Tombstone hero, Archers/Mortar/Witch/Skeleton Army evos,
  Wizard hero, …). The record collapses forms and drops several form children (`TombstoneHeroSkeleton`,
  `SkeletonArmy_EV1_Soldier`, `Witch_EV1_*`). Segments with an opponent form card are flagged.
- **Landed Goblin Barrel goblins:** absent from records before the Oct 20 A3 projection fix. Their bodies are excluded
  from scoring in those games.
- **Carried bodies with no carrier play:** for example, Barbarian Barrel barbarians, which have no public carrier the
  harness can inject. Flagged.
- **The reworked Goblin Hut's Spear Goblins:** walk and throw spears natively, but the projection classes them
  `SpearGoblin_Dummy` (not a body). They are restored to the truth from the projectile log, with HP unknown. Without
  this, the port's *better* hut timing looked like a −10 pp regression.
- **Record dropouts and unexplained tower damage:** dropouts are 58 in 161,502 sample steps, where every healthy
  opponent body vanishes at once. Unexplained damage is our tower losing HP with no visible attacker or carrier,
  e.g. an unplaced body or an invisible Zap/Log/Earthquake. Both are flagged.

Result tables use all 575 segments. The clean tier has 423 segments. It tracks all segments within 1.2 pp on
position and 1.6 pp on HP:
- **Before:** 73.6 / 63.5 / 54.5 ≤¼, HP 92.8 / 87.6 / 81.1.
- **After:** 83.0 / 74.4 / 63.6 ≤¼, HP 93.3 / 88.8 / 83.5.

## 2. Engines on the live harness

| engine | ≤¼ 5 / 10 / 20 s | HP≤2% 5 / 10 / 20 s | unmatched 20 s |
|---|---|---|---|
| A. deployed RL root live16402b-r3 (before) | 72.5 / 62.3 / 53.6 | 92.6 / 86.8 / 79.5 | 10.9 |
| B. engine-cards main before the port, 15.535 data | 73.4 / 65.2 / 55.7 | 93.2 / 87.8 / 80.8 | 9.3 |
| C. calibrated src/clasher (C56 engine), 15.535 data | 81.3 / 71.0 / 59.2 | 92.2 / 86.7 / 79.5 | 10.2 |
| D. ported engine-cards, 15.535 data | 82.5 / 73.4 / 62.1 | 93.3 / 87.9 / 81.2 | 8.8 |
| D2. ported engine-cards + 16.402 overlay | 81.1 / 70.7 / 61.0 | 93.5 / 87.9 / 81.4 | 9.3 |
| **F. D2 + Skeletons radius hold (after, this branch)** | **82.6 / 73.4 / 62.5** | **93.5 / 88.5 / 82.3** | **8.8** |

The calibration measured on 15.535 T1 transfers to real 16.x games: C − A is +8.8 pp at 5 s. engine-cards' card work
(Royal Recruits line, Goblin Giant riders, Guards, Tombstone) adds what C lacks: D − C is +2.9 pp at 20 s. On each game
half (128 + 128) F beats D2 at every horizon: +2.1 / +3.0 / +1.8 and +0.7 / +2.5 / +1.3 pp.

**Hog 2.6 cards and their common opponents** (all segments; before = A, after = F):

| card (owner) | unit-ticks 20 s | 5 s ≤¼ | 20 s ≤¼ | 20 s HP≤2% | 20 s unmatched |
|---|---:|---|---|---|---|
| ours HogRider | 19805 | 91.5 → 92.0 | 71.6 → **73.4** | 77.4 → 79.8 | 4.6 → 4.0 |
| ours Musketeer | 16061 | 98.7 → 98.7 | 85.5 → **87.6** | 84.9 → 86.8 | 5.0 → 4.4 |
| ours IceGolem | 6421 | 87.6 → 88.3 | 72.0 → **73.2** | 63.0 → 65.9 | 13.9 → 13.5 |
| ours Cannon | 6961 | 99.0 → 99.4 | 89.9 → **92.4** | 79.4 → 82.2 | 10.0 → 7.5 |
| ours Skeletons | 24932 | 57.3 → 78.5 | 38.9 → **58.3** | 84.0 → 89.2 | 15.8 → 10.7 |
| ours IceSpirit | 4145 | 47.3 → 94.0 | 56.0 → **85.3** | 87.4 → 88.6 | 11.2 → 10.1 |
| opp SkeletonArmy | 20214 | 43.9 → 73.4 | 19.3 → **36.8** | 84.3 → 85.5 | 12.9 → 11.8 |
| opp Barbarians | 10288 | 51.9 → 65.9 | 42.4 → **46.6** | 80.0 → 81.1 | 3.6 → 4.0 |
| opp Witch | 10058 | 69.8 → 69.8 | 47.8 → **47.1** | 83.8 → 83.5 | 11.7 → 11.7 |
| opp GoblinGang | 6439 | 54.0 → 65.5 | 41.9 → **51.9** | 82.8 → 83.4 | 9.1 → 8.1 |
| opp Tombstone | 6413 | 56.8 → 56.8 | 35.8 → **37.7** | 57.7 → 60.6 | 39.0 → 37.1 |
| opp RoyalHogs | 4457 | 65.2 → 65.2 | 47.8 → **50.1** | 65.9 → 67.3 | 9.9 → 8.6 |
| opp Bats | 4362 | – | 21.5 → **62.9** | 85.6 → 87.3 | 12.2 → 10.8 |
| opp RoyalRecruits | 3774 | 15.6 → 97.2 | 19.7 → **79.0** | 88.3 → 97.0 | 1.5 → 0.6 |
| opp SkeletonDragons | 2786 | 78.5 → 78.5 | 70.0 → **72.5** | 85.0 → 87.1 | 3.7 → 2.5 |
| opp Valkyrie | 2667 | – | 59.2 → **60.9** | 80.0 → 81.6 | 1.5 → 1.5 |
| opp GoblinHut | 2599 | – | 41.6 → **70.9** | 78.4 → 81.7 | 28.8 → 10.5 |
| opp SpearGoblins | 2408 | – | 58.5 → **61.5** | 86.3 → 87.3 | 7.8 → 7.2 |
| opp Skeletons | 2245 | – | 50.6 → **45.8** | 93.1 → 91.2 | 6.6 → 7.1 |
| opp Minions | 2163 | – | 67.8 → **65.9** | 87.7 → 88.4 | 4.6 → 3.9 |
| opp Knight | 2158 | – | 66.5 → **70.4** | 71.4 → 74.5 | 0.3 → 0.3 |
| opp GoblinBarrel | 2109 | – | 83.1 → **84.1** | 73.3 → 73.2 | 13.0 → 12.7 |
| opp SkeletonBalloon | 1983 | 34.1 → 35.2 | 25.3 → **32.5** | 66.0 → 72.5 | 31.8 → 24.9 |
| opp GoblinGiant | 1730 | 4.8 → 0.8 | 4.3 → **9.0** | 9.9 → 69.0 | 71.8 → 8.2 |
| opp Pekka | 1690 | – | 76.5 → **79.8** | 70.4 → 75.7 | 4.1 → 4.1 |

Per-card losses at 20 s: opponent Skeletons −4.8, Minions −1.9, Witch −0.7; also Goblin Giant at 5 s. These are not
diagnosed.

**Per interaction** (own card × opponent card both played in a segment; 20 s; the 16 most frequent):

| our card × opponent card | segments | ≤¼ | HP≤2% | tower-damage error per segment (HP) |
|---|---:|---|---|---|
| HogRider × GoblinBarrel | 88 | 48.7 → 56.9 | 74.6 → 78.6 | 374 → 313 |
| Musketeer × GoblinBarrel | 75 | 54.8 → 61.7 | 73.8 → 77.1 | 435 → 381 |
| HogRider × Valkyrie | 70 | 57.5 → 63.6 | 81.1 → 82.7 | 195 → 187 |
| HogRider × SkeletonArmy | 63 | 36.1 → 48.5 | 80.7 → 82.8 | 312 → 305 |
| HogRider × Cannon | 62 | 61.7 → 69.1 | 85.6 → 85.8 | 109 → 97 |
| Skeletons × GoblinBarrel | 61 | 47.1 → 55.2 | 71.8 → 77.9 | 420 → 365 |
| HogRider × Knight | 59 | 60.3 → 70.2 | 84.0 → 86.3 | 163 → 146 |
| Musketeer × Valkyrie | 56 | 58.1 → 65.1 | 81.4 → 83.5 | 187 → 178 |
| HogRider × GoblinGang | 54 | 49.9 → 56.1 | 72.6 → 74.5 | 324 → 303 |
| HogRider × HogRider | 53 | 60.9 → 66.5 | 79.5 → 81.7 | 235 → 220 |
| Musketeer × Knight | 53 | 58.2 → 68.4 | 83.4 → 85.2 | 225 → 206 |
| IceGolem × GoblinBarrel | 52 | 49.5 → 54.6 | 72.1 → 75.0 | 440 → 405 |
| HogRider × BlowdartGoblin | 49 | 58.5 → 59.8 | 75.0 → 75.6 | 297 → 292 |
| Cannon × GoblinBarrel | 48 | 50.7 → 57.4 | 71.7 → 76.0 | 255 → 202 |
| IceSpirit × GoblinBarrel | 47 | 45.9 → 54.7 | 71.5 → 77.6 | 530 → 415 |
| Skeletons × Valkyrie | 45 | 56.4 → 63.2 | 81.5 → 83.3 | 185 → 178 |

Full tables: `report-live-tables.txt` in the work dir; `python -m bot.simfid.live_run --aggregate DIR` regenerates them.

## 3. Fidelity gaps ranked by impact

Impact is measured on the live harness as position error mass at 20 s (unit-ticks not within ¼ tile). Before:
91,958. After: 73,409.

| # | gap | evidence | status |
|---|---|---|---|
| 1 | **RL engine lacks the T1 calibration.** Swarm/ring formations and lane order, spawner timing, Ghost, Miner, the side-1 back-row bound, Firecracker, projectile-spawned deploy ticks, Barbarian/Spirit/Doctor data | T1 50.8 vs 72.5; live C − A +8.8 pp at 5 s; our Ice Spirit 47 → 94 and Skeletons 57 → 79 at 5 s | **fixed**: ported to engine-cards py + Rust + data, exact on T1, parity 574/577 (PORT.md) |
| 2 | **RL runtime root predates engine-cards' card work.** Royal Recruits line (native spacing 2.8, staggered), Goblin Giant riders as bodies, Guards ring | Recruits 19.7 → 79.0 at 20 s, Goblin Giant HP 9.9 → 69.0, unmatched 72 → 8 | fixed on main already; carried by this branch; **needs a runtime rebuild (not done: deployment is out of scope)** |
| 3 | **16.402 overlay Skeletons SummonRadius 400.** A 0.46-tile ring that no live deployment shows (open field 0.58, bridge row: the 700 ring's sides at 0.82) | own Skeletons ≤¼ at 5 / 10 / 20 s 72.3 / 55.7 / 47.9 → 78.5 / 70.6 / 58.3 when 700 is held | **fixed**: `bot/cards/balance_overlay.py` HOLD + test |
| 4 | Opponent Skeleton Army swarm dynamics | 17% of remaining error mass; 37% at 20 s. Native inner layouts vary (106 distinct in 126 complete 15-body deployments): spawn randomness plus collision cascade | open |
| 5 | Our Skeletons at the edges | 13% of remaining mass. Mid-field: native 0.58 ring. Bridge row: the 700 ring's sides with the front clipped to y 14.77. Back row (seat 1): ±0.96 / +0.36 / +0.65. A ring-radius rule (max(summon, collision)) fixed mid-field but lost at the edges, **rejected by the gate** (−0.2 pp at 20 s) and reverted | open; the data is in `bot/simfid/formation_audit.py` |
| 6 | Barbarians, Witch, Tombstone combat cascades | 7.5% / 7.2% / 5.3% of remaining mass; position diverges after 5 s with near-equal counts | open, not diagnosed |
| 7 | **Opponent evolutions/hero forms** | 74/251 live games; 1,000/1,000 HF replays; the engine plays base forms; the record drops several form children | open: large modelling task, flagged and excluded from the clean tier |
| 8 | Support towers | Cannoneer in 5/251 live games; 144/1,000 HF replays; the engine models a Princess everywhere | open |
| – | Damage at real levels, max-HP tables, crown-tower curve, Hog routing, tick convention | all exact against live (above) | no gap |

## 4. T1 per card (Hog 2.6 and common cards)

RL config before → after and r1 data before → after, no-tower ≤¼ / HP exact. The RL-config HP for Ice Golem is 0.0 by
construction: its 16.402 max HP differs from the 15.535 recordings.

| card | unit-ticks | RL before | **RL after** | r1 before | r1 after |
|---|---:|---|---|---|---|
| HogRider | 42931 | 72.8 / 62.3 | **84.6 / 73.3** | 70.4 / 64.2 | 83.4 / 77.0 |
| Musketeer | 61969 | 60.0 / 67.9 | **72.8 / 75.7** | 56.8 / 66.1 | 74.3 / 78.2 |
| IceGolem | 104964 | 65.5 / 0.0 | **78.1 / 0.0** | 65.8 / 62.0 | 83.0 / 79.3 |
| Cannon | 123664 | 85.4 / 72.3 | **90.8 / 81.0** | 84.7 / 71.6 | 91.5 / 84.6 |
| Skeletons | 181420 | 46.3 / 78.0 | **75.2 / 85.1** | 64.1 / 78.7 | 76.9 / 86.4 |
| IceSpirit | 41980 | 69.3 / 75.2 | **81.1 / 84.3** | 71.5 / 76.8 | 82.3 / 85.6 |
| SkeletonArmy | 632105 | 31.3 / 76.5 | **63.3 / 83.5** | 31.3 / 76.5 | 65.0 / 85.4 |
| GoblinGang | 372294 | 39.9 / 73.2 | **68.2 / 82.4** | 37.4 / 69.3 | 67.7 / 81.9 |
| Bats | 293901 | 34.5 / 74.4 | **72.8 / 87.4** | 35.5 / 75.3 | 73.2 / 87.2 |
| Knight | 114556 | 59.0 / 57.0 | **70.6 / 65.4** | 59.2 / 60.1 | 74.3 / 74.4 |
| Valkyrie | 65312 | 60.3 / 56.5 | **67.3 / 59.7** | 61.0 / 59.2 | 70.2 / 67.4 |
| GoblinHut | 194327 | 29.8 / 35.7 | **49.6 / 60.1** | 30.3 / 37.2 | 50.5 / 61.6 |
| GoblinBarrel | 66840 | 72.9 / 80.4 | **79.9 / 86.3** | 71.4 / 79.2 | 80.4 / 86.2 |

## 5. Replay rebuild prototype (REBUILD.md)

`bot/simfid/rebuild.py` rebuilds HF IL_Replay matches in our engine.
- **Levels:** real per-match levels, both seats' cards and towers. HF `level` is the displayed level; a match with
  an incomplete level map is rejected, never defaulted to 11.
- **Opening hand:** ClashAI-style inference, implemented independently. All 70 × 24 = 1,680 opening-hand/queue
  assignments are checked against each side's whole play sequence, inconsistent ones are rejected, and candidates
  are never ranked by outcome.
- **Injection:** strict, with no forced hands or top-ups. A 40-tick slack tier is reported separately.
- **Forms:** unsupported forms are classified, never called faithful.

Same 50 native-corpus matches as Oct 4, and 1,000 random replays (seed 20261020). Main (strict) tier:

| engine | 50: winner | 50: crowns | 50: six-HP | 50: HP MAE | 1,000: winner | 1,000: crowns | 1,000: HP MAE | 1,000: pending events (matches) |
|---|---|---|---|---|---|---|---|---|
| Oct 4 native client, first-use order + real levels | 41/50 | 39/50 | 2 | 623 | – | – | – | – |
| deployed RL engine (live16402b-r3) | 31/50 | 20/50 | 1 | 1100 | 590/999 (59.1%) | 358 (35.8%) | 1255 | 17,088 (582) |
| **final engine (port + hold overlay)** | **30/50** | **21/50** | **1** | **1063** | **609/999 (61.0%)** | **390 (39.0%)** | **1166** | **15,762 (533)** |
| null baseline: team always wins | 38/50 | – | – | – | 621/999 (62.1%) | – | – | – |

- **Hand inference works and matters:** every one of the 1,998 sides has a consistent assignment (median 256
  candidates; none unique). On the 1,000, card-unavailable rejections fall from 5,599 to 635 against the source
  deck-list order. Which consistent assignment is chosen barely changes the engine trajectory (993/999 bit-identical).
  It does change which unplayed cards are in hand, so an actor label must not depend on it (FIDELITY.md).
- **Levels move HP, not winners:** HP MAE 1,676 at L11 vs 1,255 at real levels, with winners within 1%.
- **Not faithful:** 0/1,000 matches are fully supported by our engine. Every deck has an evolution, 92.8% a hero,
  14.4% a non-Princess tower, and 75.8% execute an unsupported or ambiguous ability. The median faithful prefix ends
  at tick 221. On the final engine 533/999 matches (53%) end with source events still pending: regulation crown
  leads at 3601, sudden-death crowns and King kills.
- **Throughput:** 4.5 CPU-s per match (engine only), about 340 CPU-hours for all 252,238 per configuration.

So the engine is not yet a substitute for native re-drive as the source of human training states. Its remaining
blockers are evolution/hero/support-tower mechanics and end-of-game timing, not hand inference.

## 6. Review

GPT-6.1 Sol, round 1 (NO-GO). Six harness findings, all fixed and the evidence regenerated:
1. Quiet starts ignored carriers in flight.
2. An awake king restarted its activation.
3. Pairing silently fell back to greedy matching without SciPy.
4. Tied level candidates picked the lowest level.
5. Unknown-HP truth bodies entered the HP denominator when unmatched.
6. Carried bodies with no carrier were unflagged.

The port and the overlay hold passed review: 71 tests, 577/577 per-fixture matches with calibrated main, and parity
574/577. Round 2 is recorded in the merge commit.

## 7. Limits

- Live truth is the public record sampled every ~5 ticks. It carries no hidden state, HP for some projected bodies,
  invisible opponent spells, or form children. Segments start on quiet boards only (towers alone, nothing in flight).
  That excludes states whose clocks and targets we cannot see, and it under-samples long, dense fights.
- Opponent levels come from public HP fractions. 300 of 1,726 opponent card levels (17.4%) are unresolved (spells,
  never-damaged cards, ties) and take the opponent's median resolved level. So opponent spell damage is at an
  estimated level. The opponent tower level is resolved in 251/256 games; the 5 others default to 11.
- The overlay hold and the offset were chosen on the whole 256-game cohort (a binary choice between two published
  values, and a one-parameter convention). The hold's effect is confirmed on each half separately; there is no
  untouched held-out bank.
- Fidelity is not strength. BATCH2's calibrated planner showed no strength change (R2-AB.md). This branch changes
  the true game the RL env would simulate, and that is not live until a runtime root is rebuilt from it.

## Reproduce (127x05)

```
W=/mpac/sdicks02/repos/clasher-simfid-20261020; J=/mpac/sdicks02/jobs/clasher/simfid-20261020
# overlay with the hold (sha256 ccd2a5f1...); root = that gamedata + hitboxes.json, pyproject.toml, decks.json
python3 -I bot/cards/balance_overlay.py --gamedata engine-cards/py/gamedata.json \
  --rs16 /mpac/sdicks02/tmp/bot-upstream/RoyaleSim/data/derived/cards-160402017-20261006.json \
  --rs15 /mpac/sdicks02/tmp/bot-upstream/RoyaleSim/data/derived/cards-15.535.json --calibration gamedata.json \
  --out $J/overlay/gamedata-hold.json --receipt $J/overlay/receipt-hold.json
# live harness (frozen manifest): OUT, engine src, gamedata root, runtime crown pins
bot/simfid/live.sh $J/live-g-F-hold16 $W/engine-cards/py/src $J/overlay/root-hold Fireball,Poison --workers 24 --offset=-1
python -m bot.simfid.live_run --aggregate $J/live-g-F-hold16
# T1 (577 fixtures)
bot/simfid/t1.sh $J/t1-F-hold16 $W/engine-cards/py/src $J/overlay/root-hold Fireball,Poison 40
# replay rebuild on an engine
bot/simfid/rebuild.sh $W/engine-cards/py/src $J/overlay/root-hold Fireball,Poison run --sample $J/rebuild/samples/random1000 --config main --out OUT.jsonl --workers 24
# diagnostics: formation / route audits, single-segment trace; unit tests
python -m bot.simfid.formation_audit --owner 0|1;  python -m bot.simfid.route_audit --card HogRider
python -m bot.simfid.live_debug OUT mem-c15/m27 210 --card GoblinHut
PYTHONPATH=. python -m pytest -q bot/simfid/test_live.py bot/cards/test_balance_overlay.py
```
