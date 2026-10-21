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
  overlay data fix is added: Skeletons keep SummonRadius 700 against RoyaleSim's 16.402 value of 400.
- **Before → after, RL configuration** (engine + 16.402 overlay + runtime crown pins):

| corpus | metric | before (live16402b-r3) | after (this branch) | reference |
|---|---|---|---|---|
| T1, 577 native fixtures (15.535) | non-tower ≤¼ tile | 50.76 | **70.15** | calibrated main 72.48, RoyaleSim 15.535 78.8 |
| | non-tower HP exact | 65.14 | **73.81** | 80.56 / 81.8 |
| | winner agrees | 423 | **449** | 448 / 477 |
| LIVE, 256 Hog 2.6 games, 636 segments | ≤¼ tile at 5 / 10 / 20 s | 72.1 / 62.0 / 53.4 | **81.1 / 72.3 / 61.6** | |
| | HP within 2% at 5 / 10 / 20 s | 92.0 / 86.2 / 78.4 | **92.8 / 87.8 / 81.1** | |
| | tower HP error at 20 s, per tower | 57 | **53** | |
| | tower damage error at 20 s, per side | 156 | **145** | |

- **T1 with 15.535 data has no regression.** The ported engine reproduces calibrated `src/clasher` on all 577
  fixtures, per fixture (72.48 / 80.56 / 448; PORT.md). Python↔Rust digest parity is 574/577, the same 3 pre-existing
  mismatches as BATCH2. The overlay hold is data only. It passes the BATCH2 gate on train (ACCEPT) and on all 577
  under leave-one-fixture-out (one Angry Barbarians cascade). Parity under the new overlay is still 574/577.
- **Stats at our real levels were already right.** Hog Rider L10 hits a tower for 288, Fireball L8 crown damage is
  120, Zap L9 is 40, and crown towers L9/10/11 hit for 90/99/109. All equal the live client exactly. The divergence is
  mechanics: formations, spawns, swarms and combat cascades.
- **Replay rebuild:** see §5 and REBUILD.md.

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
  numbers and unit level badges). The level is the one whose max HP makes every observed fraction an integer HP. The
  same method returns our own levels exactly. These levels configure the simulation; no policy sees them.

**Segments.** A segment starts at a quiet public record (towers only, no troops or buildings) just before a play.
Towers get the recorded HP, and dead towers and an active king are reproduced. Every play then goes through the
engine's own deploy path (hand, placement, formations, levels) for 20 s. Interventions are counted, not hidden
(hand_forced, elixir_topped, retried/dropped deploys). No hidden attack clock or target is invented.

**Seat.** We are natively seat 1 in 234 of 251 games. Records are in our frame, so the engine simulates us in our
native seat, rotating the frame 180° for seat 1. The rotation matters: the calibrated side-1 back-row bound shows up
in live data as our seat-1 back-row bodies being born at y ≥ 1.0 (Ice Spirit +0.5 tile in 50 of 58 cases). Seat-0
bodies are not bounded. RL already alternates seats (`seat = g % 2`), so both rules are exercised there.

**Tick convention.** Offsets −3 … +2 were tried on a 1-in-8 discovery subset. −1 is best at 5 and 10 s (tied at
20 s), the same as T1's convention, and it is frozen. A route audit of undisturbed Hog walks shows a constant
+0.12 tile (one tick) lead in the native walk, exactly what −1 absorbs.

**Scoring.** On every truth record, units group by (owner, creating card, main body or child) and pair optimally by
distance. A unit-tick is one pair or one unmatched unit.
- *Position:* within ¼ tile and within 1 tile.
- *HP:* within 2% of max, scored only where the truth logs HP.
- *Towers:* absolute HP error, damage dealt per side, death agreement.
- *Intervals:* bootstrap over games.

Breakdowns: per card (owner|card) and per interaction (own card × opponent card both played in a segment).

**Truth quality, found and handled (each counted; the *clean* tier excludes the flagged segments):**
- **Opponent evolution/hero forms:** in 74 of 251 games (Tombstone hero, Archers/Mortar/Witch/Skeleton Army evos,
  Wizard hero, …). The record collapses forms and drops several form children (`TombstoneHeroSkeleton`,
  `SkeletonArmy_EV1_Soldier`, `Witch_EV1_*`). Segments with an opponent form card are flagged.
- **Landed Goblin Barrel goblins:** absent from records before the Oct 20 A3 projection fix. Their bodies are excluded
  from scoring in those games.
- **The reworked Goblin Hut's Spear Goblins:** walk and throw spears natively, but the projection classes them
  `SpearGoblin_Dummy` (not a body). They are restored to the truth from the projectile log, with HP unknown. Without
  this, the port's *better* hut timing looked like a −10 pp regression.
- **Record dropouts and unexplained tower damage:** dropouts are 58 in 161,502 sample steps, where every healthy
  opponent body vanishes at once. Unexplained damage is our tower losing HP with no visible attacker or carrier,
  e.g. an unplaced body or an invisible Zap/Log/Earthquake. Both are flagged.

Result tables use all 636 segments. The clean tier has 471 segments and tracks them within 1.5 pp:
- **Before:** 73.3 / 63.5 / 54.4 ≤¼, HP 92.3 / 86.9 / 80.0.
- **After:** 81.7 / 73.5 / 62.8 ≤¼, HP 92.8 / 88.2 / 82.5.

## 2. Engines on the live harness

| engine | ≤¼ 5 / 10 / 20 s | HP≤2% 5 / 10 / 20 s | unmatched 20 s |
|---|---|---|---|
| A. deployed RL root live16402b-r3 (before) | 72.1 / 62.0 / 53.4 | 92.0 / 86.2 / 78.4 | 11.3 |
| B. engine-cards main, 15.535 data | 72.8 / 64.5 / 55.3 | 92.5 / 87.0 / 79.5 | 9.8 |
| C. calibrated src/clasher (C56 engine), 15.535 data | 80.1 / 70.0 / 58.7 | 91.7 / 86.2 / 78.7 | 10.5 |
| D. ported engine-cards, 15.535 data | 81.1 / 72.3 / 61.2 | 92.6 / 87.3 / 80.2 | 9.3 |
| D2. ported engine-cards + 16.402 overlay | 79.9 / 69.9 / 60.3 | 92.8 / 87.2 / 80.3 | 9.8 |
| **F. D2 + Skeletons radius hold (after, this branch)** | **81.1 / 72.3 / 61.6** | **92.8 / 87.8 / 81.1** | **9.3** |

The calibration measured on 15.535 T1 transfers to real 16.x games: C − A is +8.0 pp at 5 s. engine-cards' card work
(Royal Recruits line, Goblin Giant riders, Guards, Tombstone) adds what C lacks: D − C is +2.5 pp at 20 s. On both
game halves (128 + 128) F beats D2 at every horizon, by +0.7 … +2.5 pp.

**Hog 2.6 cards and their common opponents** (all segments; before = A, after = F):

| card (owner) | unit-ticks 20 s | 5 s ≤¼ | 20 s ≤¼ | 20 s HP≤2% | 20 s unmatched |
|---|---:|---|---|---|---|
| ours HogRider | 21683 | 91.1 → 91.6 | 71.0 → **72.8** | 76.7 → 79.0 | 4.8 → 4.2 |
| ours Musketeer | 17802 | 98.1 → 98.1 | 83.7 → **85.4** | 83.6 → 85.7 | 5.7 → 5.1 |
| ours IceGolem | 7544 | 87.4 → 87.9 | 68.9 → **70.1** | 60.0 → 62.6 | 15.4 → 15.1 |
| ours Cannon | 7523 | 99.0 → 99.4 | 89.4 → **91.8** | 78.1 → 80.9 | 10.4 → 8.0 |
| ours Skeletons | 26747 | 56.2 → 75.7 | 39.0 → **56.3** | 84.1 → 88.8 | 15.8 → 11.1 |
| ours IceSpirit | 4430 | 49.7 → 91.6 | 57.0 → **84.0** | 86.7 → 87.8 | 11.8 → 10.8 |
| opp SkeletonArmy | 21678 | 45.8 → 75.4 | 21.2 → **38.0** | 83.8 → 85.1 | 12.6 → 11.8 |
| opp Witch | 11501 | 63.1 → 63.1 | 44.7 → **43.9** | 79.1 → 79.0 | 15.5 → 15.2 |
| opp Barbarians | 10378 | 51.9 → 65.8 | 43.3 → **47.1** | 78.1 → 79.1 | 3.9 → 4.0 |
| opp GoblinGang | 8229 | 55.2 → 65.4 | 41.4 → **50.7** | 82.3 → 83.4 | 9.3 → 8.1 |
| opp Tombstone | 6538 | 54.8 → 54.8 | 37.0 → **38.7** | 57.4 → 60.2 | 38.8 → 37.0 |
| opp Bats | 5087 | – | 22.4 → **63.4** | 84.9 → 86.9 | 12.2 → 10.9 |
| opp RoyalHogs | 4879 | 61.3 → 61.3 | 47.3 → **49.8** | 65.5 → 66.9 | 9.6 → 8.4 |
| opp RoyalRecruits | 3774 | 15.6 → 97.2 | 20.6 → **79.2** | 87.7 → 96.9 | 1.5 → 0.6 |
| opp SpearGoblins | 3223 | 80.5 → 80.5 | 53.7 → **56.6** | 84.9 → 85.8 | 9.2 → 8.2 |
| opp SkeletonDragons | 2939 | 69.8 → 69.8 | 67.6 → **69.9** | 83.0 → 85.0 | 4.6 → 3.4 |
| opp Valkyrie | 2930 | – | 59.8 → **61.3** | 79.4 → 80.9 | 2.2 → 2.0 |
| opp GoblinHut | 2672 | – | 43.3 → **72.1** | 57.5 → 78.0 | 28.0 → 10.2 |
| opp SkeletonBalloon | 2597 | 44.5 → 45.6 | 28.4 → **35.8** | 73.8 → 78.6 | 22.8 → 17.1 |
| opp GoblinBarrel | 2552 | 52.4 → 52.4 | 75.6 → **75.5** | 68.9 → 68.2 | 19.2 → 19.8 |
| opp Knight | 2304 | – | 63.3 → **66.4** | 69.4 → 72.2 | 1.2 → 1.3 |
| opp HogRider | 1737 | 75.9 → 75.9 | 64.0 → **64.8** | 68.7 → 72.7 | 5.4 → 3.7 |
| opp GoblinGiant | 1730 | 4.8 → 5.6 | 4.3 → **14.6** | 9.9 → 60.8 | 71.8 → 9.3 |

**Per interaction** (own card × opponent card both played in a segment; 20 s; the 16 most frequent):

| our card × opponent card | segments | ≤¼ | HP≤2% | tower-damage error per segment (HP) |
|---|---:|---|---|---|
| HogRider × GoblinBarrel | 102 | 47.0 → 54.5 | 73.3 → 76.8 | 424 → 374 |
| Musketeer × GoblinBarrel | 88 | 51.2 → 57.3 | 72.2 → 75.2 | 492 → 455 |
| HogRider × Valkyrie | 77 | 57.1 → 62.4 | 80.1 → 81.6 | 246 → 238 |
| Skeletons × GoblinBarrel | 69 | 47.0 → 54.1 | 72.0 → 77.4 | 412 → 353 |
| HogRider × SkeletonArmy | 68 | 36.1 → 47.8 | 78.9 → 81.0 | 359 → 361 |
| HogRider × Cannon | 67 | 62.4 → 68.6 | 85.6 → 85.2 | 108 → 96 |
| HogRider × GoblinGang | 63 | 50.1 → 55.9 | 73.4 → 75.1 | 368 → 339 |
| IceGolem × GoblinBarrel | 62 | 46.4 → 51.4 | 71.4 → 74.0 | 492 → 473 |
| HogRider × Knight | 62 | 58.9 → 67.7 | 81.9 → 84.5 | 186 → 173 |
| HogRider × HogRider | 59 | 59.9 → 64.1 | 78.4 → 80.1 | 239 → 230 |
| HogRider × BlowdartGoblin | 59 | 57.3 → 58.2 | 74.8 → 75.9 | 360 → 350 |
| IceSpirit × GoblinBarrel | 56 | 43.6 → 51.4 | 70.0 → 74.7 | 570 → 499 |
| HogRider × SpearGoblins | 56 | 55.4 → 61.3 | 77.8 → 79.2 | 249 → 239 |
| HogRider × Bats | 53 | 44.3 → 59.1 | 78.4 → 80.1 | 407 → 379 |
| HogRider × Barbarians | 45 | 48.8 → 59.1 | 79.2 → 82.5 | 278 → 234 |
| Musketeer × SkeletonArmy | 47 | 38.0 → 50.3 | 79.4 → 81.5 | 330 → 305 |

Full tables: `report-live-tables.txt` in the work dir; `python -m bot.simfid.live_run --aggregate DIR` regenerates them.

## 3. Fidelity gaps ranked by impact

Impact is measured on the live harness as position error mass at 20 s (unit-ticks not within ¼ tile). Before:
101,800. After: 82,896.

| # | gap | evidence | status |
|---|---|---|---|
| 1 | **RL engine lacks the T1 calibration.** Swarm/ring formations and lane order, spawner timing, Ghost, Miner, the side-1 back-row bound, Firecracker, projectile-spawned deploy ticks, Barbarian/Spirit/Doctor data | T1 50.8 vs 72.5; live C − A +8.0 pp at 5 s; our Ice Spirit 50 → 92 and Skeletons 56 → 76 at 5 s | **fixed**: ported to engine-cards py + Rust + data, exact on T1, parity 574/577 (PORT.md) |
| 2 | **RL runtime root predates engine-cards' card work.** Royal Recruits line (native spacing 2.8, staggered), Goblin Giant riders as bodies, Guards ring | Recruits 20.6 → 79.2, Goblin Giant HP 9.9 → 60.8, unmatched 72 → 9 | fixed on main already; carried by this branch; **needs a runtime rebuild (not done: deployment is out of scope)** |
| 3 | **16.402 overlay Skeletons SummonRadius 400.** A 0.46-tile ring that no live deployment shows | own Skeletons ≤¼ at 5 / 10 / 20 s 70.4 / 54.7 / 47.4 → 75.7 / 68.1 / 56.3 when 700 is held | **fixed**: `bot/cards/balance_overlay.py` HOLD + test |
| 4 | Opponent Skeleton Army swarm dynamics | 16% of remaining error mass; 38% at 20 s. Native inner layouts vary (106 distinct in 126 complete 15-body deployments): spawn randomness plus collision cascade | open |
| 5 | Our Skeletons at the edges | 13% of remaining mass. Mid-field: native 0.58 ring. Bridge row: the 700 ring's sides with the front clipped to y 14.77. Back row (seat 1): ±0.96 / +0.36 / +0.65. A ring-radius rule (max(summon, collision)) fixed mid-field but lost at the edges, **rejected by the gate** (−0.2 pp at 20 s) and reverted | open; the data is in `bot/simfid/formation_audit.py` |
| 6 | Witch, Barbarians, Tombstone combat cascades | 8% / 7% / 5% of remaining mass; position diverges after 5 s with near-equal counts | open, not diagnosed |
| 7 | **Opponent evolutions/hero forms** | 74/251 games; the engine plays base forms; the record drops several form children | open: large modelling task, flagged and excluded from the clean tier |
| 8 | Support towers | Cannoneer in 5/251 games; the engine models a Princess everywhere | open, low impact here |
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

## 5. Replay rebuild prototype

REBUILD_SECTION

## 6. Limits

- Live truth is the public record sampled every ~5 ticks. It carries no hidden state, HP for some projected bodies,
  invisible opponent spells, or form children. Segments start on quiet boards only (towers alone). That excludes
  states whose clocks and targets we cannot see, and it under-samples long, dense fights.
- Opponent levels come from public HP fractions. 262 of 1,726 opponent card levels (15.2%) cannot be read that way:
  spells with no bodies, or cards never partly damaged in the game. They take the opponent's median resolved level.
  So opponent spell damage is at an estimated level. The opponent tower level is resolved in 251/256 games (the 5
  others, which include the Cannoneer games, default to 11).
- The overlay hold and the offset were chosen on the whole 256-game cohort (a binary choice between two published
  values, and a one-parameter convention). The hold's effect is confirmed on each half separately; there is no
  untouched held-out bank.
- Fidelity is not strength. BATCH2's calibrated planner showed no strength change (R2-AB.md). This branch changes
  the true game the RL env would simulate, and that is not live until a runtime root is rebuilt from it.

## Reproduce (127x05)

```
W=/mpac/sdicks02/repos/clasher-simfid-20261020; J=/mpac/sdicks02/jobs/clasher/simfid-20261020
# live harness (frozen manifest): OUT, engine src, gamedata root, runtime crown pins
bot/simfid/live.sh $J/live-f-F-hold16 $W/engine-cards/py/src $J/overlay/root-hold Fireball,Poison --workers 24 --offset=-1
python -m bot.simfid.live_run --aggregate $J/live-f-F-hold16
# T1 (577 fixtures)
bot/simfid/t1.sh $J/t1-F-hold16 $W/engine-cards/py/src $J/overlay/root-hold Fireball,Poison 40
# overlay with the hold (sha256 ccd2a5f1...)
python3 -I bot/cards/balance_overlay.py --gamedata engine-cards/py/gamedata.json \
  --rs16 /mpac/sdicks02/tmp/bot-upstream/RoyaleSim/data/derived/cards-160402017-20261006.json \
  --rs15 /mpac/sdicks02/tmp/bot-upstream/RoyaleSim/data/derived/cards-15.535.json --calibration gamedata.json \
  --out $J/overlay/gamedata-hold.json --receipt $J/overlay/receipt-hold.json
# diagnostics: formation / route audits, single-segment trace
python -m bot.simfid.formation_audit --owner 0|1;  python -m bot.simfid.route_audit --card HogRider
python -m bot.simfid.live_debug OUT mem-c15/m27 210 --card GoblinHut
```
