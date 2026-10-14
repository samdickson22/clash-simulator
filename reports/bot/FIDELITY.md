# Engine fidelity against recorded native matches (exploration)

Run 2026-10-14 ~03:10Z, BOT LEAD. Exploration-tier result: one harness, one corpus, no preregistration.

## Answer

On 577 recorded native matches, RoyaleSim (its 15.535.29 rule set) reproduces the game far more closely than our
engine.
- **Non-tower units within a quarter tile:** RoyaleSim **78.8%** [76.7, 80.7], ours **51.4%** [49.5, 53.1].
- **Paired per match:** RoyaleSim is +26.1 pp [+24.5, +27.7] better, and better in 530 of 577 matches.
- **Exact HP:** RoyaleSim 81.8%, ours 65.1%; paired +16.1 pp [+14.9, +17.4].
- **Who wins the match:** RoyaleSim agrees with the recording in 477/577 matches, ours in 424/577.
- **By card:** ours is worse on every card except Tesla.

Walking is not the problem. Both engines reproduce isolated walks bit-exactly: 0 native units of error over hundreds
of ticks for Minions, Royal Hogs and Goblin Gang in `v4-phase-a-1975100700`. Our divergence starts in **combat and
spawning**: missed or shifted tower and unit hits, spawner and formation output, and some cards' formations.

## Fixtures

- **Corpus:** T1 Phase A native recordings on hub 127x01 (`/mpac/sdicks02/repos/clasher-v4-data/matches`), copied
  read-only to 03.
  - The fixture set is **train 513 + validation 64 = 577**. The heldout (64 present) and smoke matches were never
    opened.
  - The loader refuses any episode whose registered split, from `split.json` (SHA-256 of all six copies:
    `3edbd25b…5258`), is not train or validation.
- **What the recordings are:** the native client (Null's Royale 15.535.13 APK, content 15.535.86), run offline with
  an instrumented probe.
  - Both sides are our scripted bots on C56 decks. All cards and towers are level 11; there are no evolutions.
  - Object rows are sampled every 1–4 ticks (about 3,300 frames per match).
  - Matches end by the normal rules: regulation 3601, or an overtime tower.
- **RoyaleSim's own corpus is not available.** Its 73 recordings (client 16.402) are private. The repo ships one
  sample fixture. So both engines are measured on our corpus only.
- **Version note:** the recordings are from client 15.535.
  - RoyaleSim ships the 15.535.29 card table plus measured 15.535 mechanics (`client_arms("15.535.29")`). That's
    the main column.
  - The `16.402` column is RoyaleSim's default (current-client) rules on 15.535 data, so it is penalised by
    version drift. The live game today is 16.x.
  - Our engine's card data was derived from this same native client (c56 audit). If anything, the corpus favours
    ours.

## Method (`bot/fidelity/`)

**Script.** Every accepted card play and champion ability in `events.jsonl` is issued through each engine's **own
deploy path** (hand, elixir, placement rules, formations):
- at the tap tile;
- one tick before the native execution tick. The offset was chosen from {−2…+2} on 12 train fixtures and is best
  for both engines; −1 is also RoyaleSim's own harness convention.

Both engines start at the recording's first tick (340) with the recorded elixir (10). Initial hand and cycle order
come from the first evaluation-only row, which is privileged but used only to make hands match.

Interventions are counted, not hidden:

| | ours | RoyaleSim 15.535 |
|---|---:|---:|
| plays issued | 26,529 | 27,105 |
| plays dropped after 10 retry ticks | 80 | 253 (hand-cycle misses, NO_DEPLOY, WATER) |
| other interventions | 153 forced hands | none (RoyaleSim can't force) |

Dropped plays count against the engine (missing units), so RoyaleSim's number is, if anything, conservative.

**Truth.** Native objects with hp (towers, troops, buildings). Projectiles and spell areas are excluded. The root card
is the native `card_id`. Native body names are unreliable in this corpus (Rascals girls are labelled
SkeletonBalloon), so they are not used.

**Root cards in the engines.**
- RoyaleSim reports the root card itself.
- Ours has no root tag, so the harness tags each new entity at insertion from its creator. If the creator is a deploy,
  the root is that card. If it is a spell, the spell. If it is a spawning or dying unit, that unit's root.
- Per-card unit counts match the recording, e.g. 36/36 Goblin Gang units and 15/15 Minions.

**Pairing and scoring** follow RoyaleSim's `examples/replay_parity/harness.rs` (upstream 39e7d482, 2026-10-13):
- towers pair by (side, slot);
- other units form (side, root) groups by first-seen tick, paired within 100 ticks, preferring a group of the same
  size, then the nearest in time;
- members are assigned by least total first-frame distance (exact up to 7, greedy beyond), with ties broken by HP.

A unit-tick is one pair, or one unmatched unit, on one truth frame where either side has it alive:
- **Within ¼ tile:** both alive and within 250 native units.
- **HP exact:** both alive with equal HP.
- Every percentage is over all unit-ticks, so alive mismatches count as misses.
- After an engine's battle ends, its frozen final state is scored, as RoyaleSim does.

**Extra columns.**
- **First 5 s:** the first 100 ticks of each truth unit's life; less exposed to cascading divergence.
- **Winner and crown agreement:** from final tower state.

**Intervals.** 95% percentile bootstrap over fixtures (2,000 draws, seed 0). Paired differences are bootstrapped
over fixtures too.

## Overall, all 577 fixtures

| engine | units with towers ≤¼ tile | **no towers ≤¼ tile** | no towers ≤1 tile | with towers HP exact | **no towers HP exact** | no towers alive mismatch | first 5 s ≤¼ | winner agrees | crowns equal |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **Clasher (ours)** | 69.6 [68.2, 71.0] | **51.4 [49.5, 53.1]** | 66.9 [64.9, 68.9] | 66.2 [64.7, 67.7] | **65.1 [63.2, 67.0]** | 20.7 [18.7, 22.8] | 62.1 [60.6, 63.6] | 424 | 398 |
| **RoyaleSim, 15.535.29 rules** | 86.9 [85.5, 88.3] | **78.8 [76.7, 80.7]** | 85.0 [83.0, 86.9] | 82.8 [81.3, 84.3] | **81.8 [79.8, 83.6]** | 10.3 [8.6, 12.2] | 86.2 [84.7, 87.6] | 477 | 465 |
| RoyaleSim, 16.402 rules (default) | 82.8 [81.2, 84.3] | 72.1 [70.0, 74.3] | 80.5 [78.3, 82.6] | 78.4 [76.8, 79.9] | 77.3 [75.3, 79.3] | 13.4 [11.5, 15.5] | 82.3 [80.6, 83.8] | 458 | 444 |

Unit-ticks without towers: 5,274,927 for ours, 4,966,988 for RoyaleSim 15.535 and 5,054,462 for RoyaleSim 16.402.

Paired per fixture, no towers:

| comparison | ≤¼ tile | HP exact |
|---|---|---|
| RoyaleSim 15.535 − ours | +26.1 pp [+24.5, +27.7]; better in 530/577 | +16.1 pp [+14.9, +17.4]; better in 513/577 |
| RoyaleSim 16.402 − ours | +21.1 pp [+19.6, +22.5]; better in 509/577 | +12.9 pp [+11.6, +14.2]; better in 479/577 |
| RoyaleSim 15.535 − 16.402 | +5.0 pp [+4.0, +6.1] | +3.2 pp [+2.4, +4.2] |

Train (513) and validation (64) agree:
- **Train, no towers ≤¼ tile:** ours 50.7, RoyaleSim 15.535 78.8, RoyaleSim 16.402 71.9.
- **Validation, no towers ≤¼ tile:** ours 57.7 [52.4, 62.6], RoyaleSim 15.535 78.5 [72.9, 84.0], RoyaleSim 16.402
  74.6.

For scale, RoyaleSim publishes 56.5% (no towers ≤¼ tile) on its own 16.402 human-match corpus. That corpus is harder:
human play, frame gaps, and 40/73 fixtures played only as prefixes. The numbers are not comparable across corpora.

## Per card (all fixtures; unit-ticks ≥ 8k)

| card | fixtures | unit-ticks (ours) | ours ≤¼ tile | RS 15.535 ≤¼ | RS 16.402 ≤¼ | ours HP exact | RS 15.535 HP exact | RS 16.402 HP exact | ours first-5 s ≤¼ | RS 15.535 first-5 s ≤¼ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Tower | 577 | 3380588 | 98.1 | 99.0 | 98.7 | 68.0 | 84.4 | 79.9 | – | – |
| SkeletonArmy | 129 | 662959 | 31.1 | 74.5 | 59.5 | 76.0 | 87.9 | 81.1 | 40.9 | 82.4 |
| GoblinGang | 164 | 404047 | 37.4 | 77.0 | 70.5 | 69.2 | 86.4 | 84.1 | 52.6 | 85.5 |
| Bats | 140 | 318067 | 35.5 | 80.0 | 70.8 | 75.3 | 90.2 | 85.2 | 44.9 | 87.5 |
| Goblins | 149 | 274073 | 58.9 | 72.8 | 69.6 | 73.5 | 81.1 | 81.5 | 73.4 | 83.1 |
| Minions | 169 | 246057 | 58.6 | 79.1 | 72.7 | 76.5 | 87.9 | 81.7 | 76.8 | 88.5 |
| GoblinHut | 145 | 197393 | 30.3 | 66.6 | 61.5 | 37.2 | 73.6 | 69.0 | 22.7 | 68.8 |
| Archers | 152 | 185858 | 58.7 | 79.1 | 73.0 | 73.1 | 86.7 | 82.0 | 79.2 | 88.7 |
| Skeletons | 144 | 184648 | 64.1 | 81.5 | 74.7 | 78.6 | 88.7 | 85.2 | 73.9 | 85.9 |
| Princess | 163 | 151120 | 54.2 | 77.9 | 66.6 | 74.4 | 87.8 | 80.3 | 81.0 | 90.5 |
| FirespiritHut | 165 | 146252 | 23.0 | 68.2 | 64.0 | 29.9 | 51.9 | 73.9 | 24.6 | 76.8 |
| Wallbreakers | 168 | 132988 | 68.2 | 83.6 | 78.5 | 72.8 | 85.3 | 80.8 | 75.9 | 88.1 |
| Ghost | 172 | 130176 | 21.3 | 66.1 | 62.8 | 53.2 | 68.6 | 65.1 | 36.5 | 81.1 |
| Cannon | 141 | 128235 | 84.8 | 92.4 | 90.3 | 71.5 | 88.1 | 84.0 | 92.3 | 95.2 |
| Knight | 149 | 115552 | 59.4 | 81.2 | 75.1 | 60.2 | 81.7 | 72.2 | 79.3 | 89.9 |
| Firecracker | 158 | 114520 | 36.6 | 65.5 | 60.2 | 66.9 | 82.4 | 78.2 | 68.6 | 84.1 |
| BarbLog | 167 | 111710 | 62.1 | 79.6 | 75.9 | 0.0 | 82.8 | 78.3 | 81.2 | 87.5 |
| IceGolem | 144 | 109693 | 65.8 | 85.1 | 76.1 | 62.0 | 82.8 | 0.0 | 77.7 | 89.6 |
| Berserker | 153 | 109276 | 59.6 | 76.5 | 71.0 | 64.1 | 81.0 | 74.7 | 74.8 | 86.0 |
| BombTower | 148 | 103339 | 84.0 | 92.3 | 88.4 | 67.2 | 86.3 | 78.7 | 92.3 | 95.0 |
| RoyalDelivery | 146 | 93733 | 71.1 | 83.4 | 79.0 | 81.3 | 86.6 | 82.8 | 86.7 | 91.6 |
| MinionHorde | 83 | 90753 | 43.5 | 75.5 | 66.5 | 73.8 | 85.5 | 78.4 | 62.2 | 86.7 |
| Tesla | 151 | 90248 | 89.8 | 88.3 | 85.6 | 75.5 | 77.5 | 74.9 | 96.2 | 96.0 |
| BlowdartGoblin | 165 | 82882 | 60.0 | 79.2 | 74.5 | 73.7 | 88.1 | 84.9 | 76.5 | 88.3 |
| Miner | 147 | 74655 | 47.6 | 92.4 | 91.5 | 33.7 | 89.4 | 86.8 | 55.9 | 96.5 |
| RoyalHogs | 117 | 72623 | 75.7 | 81.8 | 81.3 | 76.0 | 87.0 | 83.9 | 87.3 | 87.7 |
| GoblinBarrel | 154 | 70700 | 70.9 | 84.9 | 80.2 | 78.7 | 87.8 | 83.5 | 79.7 | 87.9 |
| Goblinstein | 115 | 70074 | 9.8 | 89.3 | 85.3 | 50.4 | 91.0 | 84.3 | 1.9 | 97.1 |
| BabyDragon | 154 | 69870 | 56.2 | 75.8 | 73.1 | 63.3 | 78.2 | 75.5 | 78.7 | 89.9 |
| Valkyrie | 138 | 65358 | 61.2 | 78.9 | 73.6 | 59.4 | 79.4 | 71.5 | 80.4 | 90.9 |
| Musketeer | 129 | 63766 | 56.7 | 83.2 | 76.4 | 66.0 | 85.7 | 80.1 | 79.7 | 94.3 |
| Rascals | 94 | 61139 | 41.7 | 75.8 | 70.4 | 63.3 | 83.8 | 80.9 | 64.8 | 89.4 |
| DarkPrince | 153 | 55993 | 54.9 | 74.0 | 67.9 | 62.2 | 75.0 | 70.6 | 74.2 | 87.6 |
| MightyMiner | 121 | 48746 | 53.9 | 73.2 | 70.2 | 46.7 | 69.4 | 62.8 | 81.0 | 88.5 |
| ElectroSpirit | 169 | 47843 | 71.7 | 85.3 | 84.0 | 0.0 | 0.0 | 0.0 | 76.4 | 88.2 |
| HogRider | 151 | 46437 | 70.4 | 89.3 | 84.0 | 64.3 | 86.5 | 76.8 | 81.4 | 92.6 |
| FireSpirits | 155 | 44226 | 69.3 | 85.5 | 80.6 | 0.0 | 0.0 | 85.0 | 74.1 | 87.8 |
| IceSpirit | 155 | 43475 | 71.5 | 89.3 | 82.3 | 76.8 | 0.0 | 86.0 | 76.9 | 90.2 |
| InfernoTower | 129 | 42288 | 91.3 | 93.8 | 92.7 | 70.7 | 87.0 | 81.5 | 95.5 | 97.1 |
| MiniPekka | 127 | 41372 | 58.8 | 82.6 | 76.1 | 57.6 | 83.8 | 74.8 | 74.2 | 89.4 |
| Giant | 113 | 33444 | 83.9 | 91.2 | 85.9 | 69.5 | 87.3 | 74.8 | 92.0 | 96.2 |
| Balloon | 127 | 29394 | 85.1 | 95.3 | 94.2 | 78.0 | 91.2 | 83.0 | 92.8 | 97.0 |
| Wizard | 95 | 23883 | 59.7 | 74.3 | 68.5 | 69.6 | 79.8 | 75.0 | 82.8 | 90.2 |
| Golem | 51 | 21762 | 73.7 | 94.0 | 91.7 | 62.0 | 91.0 | 82.4 | 67.5 | 89.4 |
| Prince | 86 | 20211 | 53.2 | 76.7 | 71.7 | 48.6 | 74.4 | 67.3 | 73.1 | 87.5 |
| Xbow | 72 | 17749 | 91.5 | 98.4 | 97.2 | 76.6 | 94.0 | 89.6 | 97.2 | 98.5 |
| ArcherQueen | 75 | 17477 | 54.0 | 74.6 | 70.7 | 62.0 | 79.3 | 76.8 | 79.5 | 87.0 |
| AngryBarbarians | 29 | 8863 | 58.4 | 75.3 | 62.7 | 51.9 | 77.6 | 60.8 | 75.9 | 84.8 |

Spells (Fireball, Zap, Log, Arrows, Poison, Tornado, Rocket, Lightning, Earthquake) are scored through the units they
hit, not as rows.

A 0.0 HP-exact row means an HP *reporting or level* convention differs on every tick, not a mechanics failure. It
isn't investigated yet. The cases:
- ElectroSpirit, all three engines;
- BarbLog, ours;
- FireSpirits and IceSpirit, RoyaleSim 15.535;
- IceGolem, RoyaleSim 16.402.

## What this means for the engine decision (input to step 4)

- **For truth on this client version, RoyaleSim is the better simulator.** Its 15.535 arm wins on every aggregate and
  on 47 of 48 cards. Our engine's worst gaps (≤¼ tile, ours vs RoyaleSim) are concentrated in spawners, swarms and
  special spawns: Goblinstein 9.8 vs 89.3, Ghost 21 vs 66, Firespirit Hut 23 vs 68, Goblin Hut 30 vs 67, Skeleton Army
  31 vs 75, Bats 36 vs 80, Miner 48 vs 92.
- **Our walking is exact.** Fixing our engine means fixing combat and spawn rules card by card, a known but long job.
  RoyaleSim also publishes a rule-by-rule calibration method we could copy.
- **Speed is step 2** and is not yet measured on equal hardware.

## Caveats

- The opponents in the corpus are scripted bots, not humans, so card interactions are less varied than ladder play.
- The truth is sampled every 1–4 ticks.
- "First 5 s" approximates "moving" (no reliable deploy-state column).
- The harness re-implements RoyaleSim's pairing in Python. It is not their binary. For example, our "first-seen tick"
  is the first *observed* frame.
- Our engine got the hand forced 153 times. RoyaleSim had 253 plays dropped by hand-cycle divergence or placement
  refusals.
- One run, no repeats. All engines are deterministic given the script.

## Reproduce (127x03)

```
cd /mpac/sdicks02/repos/clasher-bot
D=/mpac/sdicks02/repos/clasher-bot-data   # t1-trainval/ (copied train+val dirs), t1-split.json
for e in clasher rsim15535 rsim16402; do
  PYTHONPATH=src:. nice -n 10 .venv/bin/python -m bot.fidelity.run --engine $e --data $D/t1-trainval \
    --split $D/t1-split.json --ids bot/fidelity/c56_native_ids.json --out OUT --workers 40 --issue-offset -1
done
PYTHONPATH=src:. .venv/bin/python -m bot.fidelity.aggregate OUT --json OUT/aggregate-all.json
.venv/bin/python -m bot.fidelity.paired OUT clasher rsim15535
.venv/bin/python -m bot.fidelity.percard_table OUT/aggregate-all.json 8000
```

The full run took 48 s on 03 (3 × 40 workers). Per-fixture results are in `/mpac/sdicks02/jobs/clasher/bot-fid-r2/`
on 03.

The engines were Clasher at origin/main dbf31faf (Python reference engine) and royalesim 0.1.34 from PyPI (MIT).
