# Batch A ("live priority") fidelity fixes — results

Exploration tier. Ours = engine-cards Python engine (+ native mirror); reference = RoyaleSim (MIT) through the
fidelity harness's `rsim16402` adapter (client 16.402 calibration, `cards-15535.1` + CLIENT16402_VALUES).
Harness = `reports/cards/fidelity/scenarios.py` + `summarize.py:compare` (unchanged; my copy in
`tools/scenarios.py` only parameterises the source pin). Runs on 127x08, gate on 127x04. Nothing committed.

Per the coordinator ruling, **pure stat-value corrections are not in the engine**: they are listed in §2 for the
`live16402` stat overlay. Fidelity "with stats" runs apply them through a scratch gamedata on 08
(`batchA/stats/gamedata.json`, built by `tools/apply_stats.py` from a spec kept only on 08; never in git).

## Verdicts (fidelity harness, 3 scenarios per card; full table §3)

Status legend: **PASS (mechanics)** = passes with the engine changes alone; **PASS (mechanics) + stats via overlay** =
passes once the §2 stat values are applied (scratch overlay on 08); **residual** = scenario still DIFF, cause in §4.

| Card | Status | Scenarios PASS (before → mechanics → mechanics+stats) |
|---|---|---|
| GoblinCage | PASS (mechanics) + stats via overlay on alone/hog; **giant residual** (1-tick first hit, §4) | 0 → 0 → 2/3 |
| SpearGoblins | PASS — stats via overlay only (no mechanic gap) | 0 → 0 → 3/3 |
| Bomber | PASS — stats via overlay only | 0 → 0 → 3/3 |
| Tombstone | PASS (mechanics) on alone/giant; **hog residual** (death-spawn first step toward an in-reach killer, §4) | 0 → 2/3 → 2/3 |
| Barbarians | PASS (mechanics) + stats via overlay on alone/knight; **minions residual** (C56 Minions/tower cascade, §4) | 0 → 0 → 2/3 |
| BattleRam | PASS (mechanics) + stats via overlay on alone/knight; **minions residual** (same cascade, 2 ticks) | 0 → 0 → 2/3 |
| MegaMinion | PASS (unchanged) | 3/3 → 3/3 → 3/3 |
| BarbarianHut | **PASS (mechanics) + stats via overlay** | 0 → 0 → 3/3 |
| Mortar | **PASS (mechanics)** (the hit/load stat rows are not observable in these scenarios) | 1/3 → 3/3 → 3/3 |
| DartBarrell (Flying Machine) | **PASS (mechanics)** | 0 → 3/3 → 3/3 |
| Witch | PASS (mechanics) on knight/minions; alone = harness ordinal artefact (§4: identical units as a multiset) | 0 → 2/3 → 2/3 |
| Pekka | PASS (unchanged) | 3/3 → 3/3 → 3/3 |
| SkeletonWarriors (Guards) | **PASS (mechanics)** | 0 → 3/3 → 3/3 |
| SkeletonDragons | **PASS (mechanics)** | 1/3 → 3/3 → 3/3 |

Totals: Batch A scenarios PASS 8/42 before → 23/42 mechanics only → **37/42 with stats**. Cards fully PASS:
2 → 6 → **9** of 14 (+ Witch, whose remaining DIFF is an ordering artefact). Rest of the 66-card pool, same runs:
no verdict regression; only DarkWitch (improved: knight now PASS; alone 13→2, minions 8→1 differences) and
GoblinDrill (alone 3→2; giant, already far off, 51→52) changed. Runs: 08 `batchA/fid/final-{base,mech,stats}.jsonl`
(baseline = `baseroot`, the unpatched engine; reproduces `reports/cards/fidelity/results.jsonl` for Batch A exactly, 84/84 engine records).


## 1. Causes and fixes (engine changes; all in `engine-cards/`)

| Card | Cause (vs RoyaleSim) | Kind | Fix (file:function) |
|---|---|---|---|
| GoblinCage | Brawler HP base 422 vs 438. | stat | §2 overlay |
| GoblinCage, BattleRam | A set DeathSpawnDeployTime started counting on the death tick itself: Brawler deployed 9 ticks (RS 10), Ram Barbarians 19 (RS 20). RS creates death spawns in Reap, after the tick's phases (`state.rs phase_reap`). The export also omits the Cage's DeathSpawnDeployTime 500. | mechanic + omitted field | `death_effects.py:DeathSpawn.on_death` (start at deploy time + 50 ms, so the birth-tick object phase leaves exactly the deploy time; native reads it from the exported template, no native change); `balance.py` CHARACTER_FIELD_OVERRIDES GoblinCage `deathSpawnDeployTime` 500 |
| SpearGoblins | hitSpeed 1700/1600, loadTime 1200/1100 (base). Body shared with C56 GoblinGang/GoblinHut. | stat | §2 overlay (no longer blocked under live16402) |
| Bomber | BombSkeletonProjectile damage base 88 vs 83 (225 vs 212 at L11). | stat | §2 overlay |
| Tombstone, BarbarianHut | (1) A building with blank SpawnStartTime waited one SpawnPauseTime before its first wave; RS (measured, 44 Tombstone + 2 Hut deploys) emits on the deploy-end tick (`spawner.FIRST_WAVE`). (2) Emitted units, and the death units of these buildings, stood on the emission point on their birth tick; RS gives them a same-tick target pass + move step (`spawner.SPAWNED_FIRST_STEP`, `state.rs first_update`). A death spawn's members step together (one point). | mechanic | `factory/mechanic_detector.py` (first-wave default 0 for buildings; `_steps_first`); `mechanics/shared/spawner.py:PeriodicSpawner._spawn_units`, `death_effects.py:DeathSpawn.on_death` → `battle.py:BattleState._first_update_spawned`; native `lib.rs:drain_fresh` + `movement_one`, `spawn.rs:production_child` |
| Barbarians, BattleRam, BarbarianHut | Barbarian HP base 270 vs 280 (691 vs 716). C56-shared (BarbLog). | stat | §2 overlay (BOT LEAD/overlay decides; not in engine) |
| Mortar | (1) MinimumRange 3500 not modelled: the Mortar shot a Hog standing at its feet. RS: never take, and drop, a target whose edge gap < MinimumRange (`target.rs inside_minimum_range`). (2) hitSpeed 5000/4700, loadTime 4000/3700. (3) projectileStartRadius 600 omitted. | mechanic + stat + omitted field | `entities.py:Entity._inside_minimum_range` (in `_is_valid_target`), `card_types.py` `minimum_range`; native `lib.rs:inside_min_range` in `target_candidate` (keep + acquire), `Stats.min_range`; `balance.py` Mortar `minimumRange`, `projectileStartRadius`; hit/load → §2 |
| DartBarrell (Flying Machine) | Treated as a ground unit: `AIR_UNIT_NAMES` lists "FlyingMachine" but the body is "DartBarrell", and the export has no flyingHeight, so the Knight killed it. projectileStartRadius 1500 omitted (hits 2 ticks late). | omitted traits | `balance.py` CHARACTER_RUNTIME_TRAITS DartBarrell `flyingHeight` 4000, `mass` 3; CHARACTER_FIELD_OVERRIDES `projectileStartRadius` 1500 |
| Witch | A blank SpawnInterval emitted one Skeleton per tick (39–42); RS emits the whole wave on one tick (measured: 13 groups of 4). Plus the first step above. | mechanic | `mechanic_detector.py` intra interval = SpawnInterval (0 when blank); first update as above |
| SkeletonWarriors (Guards) | Formation radius omitted (ours default 500 → members ±0.5 tile; RS 800 → ±0.8). Observed-speed/hit-tick differences followed from the formation. | omitted field | `balance.py` ENTRY_PATH_OVERRIDES SkeletonWarriors `summonRadius` 800 |
| SkeletonDragons | projectileStartRadius 450 omitted: every hit 1 tick late, 2 after a retarget. | omitted field | `balance.py` CHARACTER_FIELD_OVERRIDES SkeletonDragon |
| MegaMinion, Pekka | — (already PASS) | | |

"Omitted field" = a column the compact export drops entirely (not a value correction), kept in `balance.py` beside
the existing rows of the same kind (projectileStartRadius, mass/flyingHeight, summon geometry). Values from
RoyaleSim's `cards-15535.1` row for that card; no tables copied.

## 2. Stat-value corrections for the `live16402` overlay (not applied in engine-cards)

| Card | Body (nested object) | Field | Ours (gamedata, base L1) | RoyaleSim 16.402 | Effect at L11 |
|---|---|---|---|---|---|
| GoblinCage | GoblinBrawler | hitpoints | 422 | 438 | 1080 → 1121 |
| Bomber | BombSkeletonProjectile | damage | 88 | 83 | 225 → 212 |
| Mortar | Mortar | hitSpeed | 5000 | 4700 | |
| Mortar | Mortar | loadTime | 4000 | 3700 | |
| SpearGoblins (+ C56 GoblinGang, GoblinHut) | SpearGoblin | hitSpeed | 1700 | 1600 | |
| SpearGoblins (+ C56 GoblinGang, GoblinHut) | SpearGoblin | loadTime | 1200 | 1100 | |
| Barbarians, BattleRam, BarbarianHut (+ C56 BarbLog) | Barbarian | hitpoints | 270 | 280 | 691 → 716 |
| BattleRam | BattleRam | sightRange | 5500 | 6500 (16.402 table) | not applied in the scratch overlay: the harness reference table (cards-15535.1) has 5500, so this one cannot be shown by this harness |

The scratch overlay applies the first seven rows (SpearGoblin and Barbarian in every card that carries them, as the
overlay would).

## 3. Per-scenario results (verdict (number of differences) first difference; ours/RoyaleSim)

| Card | Scenario | Before (r1 engine) | Mechanics (no overlay) | Mechanics + stats overlay |
|---|---|---|---|---|
| GoblinCage | alone | DIFF (8) GoblinBrawler[0].max_hp 1080/1121 | DIFF (3) GoblinBrawler[0].max_hp 1080/1121 | PASS (0) |
| GoblinCage | hog | DIFF (18) GoblinBrawler[0].max_hp 1080/1121 | DIFF (3) GoblinBrawler[0].max_hp 1080/1121 | PASS (0) |
| GoblinCage | giant | DIFF (28) GoblinBrawler[0].max_hp 1080/1121 | DIFF (22) GoblinBrawler[0].max_hp 1080/1121 | DIFF (19) enemy_hits.count 22/21 |
| SpearGoblins | alone | DIFF (5) tower_hits.count 4/5 | DIFF (5) tower_hits.count 4/5 | PASS (0) |
| SpearGoblins | knight | DIFF (2) enemy_hits[3].tick 71/69 | DIFF (2) enemy_hits[3].tick 71/69 | PASS (0) |
| SpearGoblins | minions | DIFF (2) enemy_hits[3].tick 73/71 | DIFF (2) enemy_hits[3].tick 73/71 | PASS (0) |
| Bomber | alone | DIFF (5) Bomber[0].configured_damage 225/212 | DIFF (5) Bomber[0].configured_damage 225/212 | PASS (0) |
| Bomber | knight | DIFF (4) Bomber[0].configured_damage 225/212 | DIFF (4) Bomber[0].configured_damage 225/212 | PASS (0) |
| Bomber | minions | DIFF (1) Bomber[0].configured_damage 225/212 | DIFF (1) Bomber[0].configured_damage 225/212 | PASS (0) |
| Tombstone | alone | DIFF (51) Skeleton.count 18/20 | PASS (0) | PASS (0) |
| Tombstone | hog | DIFF (42) Skeleton.count 5/6 | DIFF (14) Skeleton[2].observed_speed 2.3476/1.8535 | DIFF (14) Skeleton[2].observed_speed 2.3476/1.8535 |
| Tombstone | giant | DIFF (77) Skeleton.count 6/8 | PASS (0) | PASS (0) |
| Barbarians | alone | DIFF (5) Barbarian[0].max_hp 691/716 | DIFF (5) Barbarian[0].max_hp 691/716 | PASS (0) |
| Barbarians | knight | DIFF (7) Barbarian[0].max_hp 691/716 | DIFF (7) Barbarian[0].max_hp 691/716 | PASS (0) |
| Barbarians | minions | DIFF (25) Barbarian[0].max_hp 691/716 | DIFF (25) Barbarian[0].max_hp 691/716 | DIFF (20) tower_hits.count 8/7 |
| BattleRam | alone | DIFF (2) Barbarian[0].max_hp 691/716 | DIFF (2) Barbarian[0].max_hp 691/716 | PASS (0) |
| BattleRam | knight | DIFF (8) Barbarian[0].max_hp 691/716 | DIFF (2) Barbarian[0].max_hp 691/716 | PASS (0) |
| BattleRam | minions | DIFF (4) Barbarian[0].max_hp 691/716 | DIFF (4) Barbarian[0].max_hp 691/716 | DIFF (2) tower_hits[1].tick 313/315 |
| MegaMinion | alone | PASS (0) | PASS (0) | PASS (0) |
| MegaMinion | knight | PASS (0) | PASS (0) | PASS (0) |
| MegaMinion | minions | PASS (0) | PASS (0) | PASS (0) |
| BarbarianHut | alone | DIFF (54) Barbarian.count 7/8 | DIFF (8) Barbarian[0].max_hp 691/716 | PASS (0) |
| BarbarianHut | hog | DIFF (25) Barbarian.count 1/4 | DIFF (4) Barbarian[0].max_hp 691/716 | PASS (0) |
| BarbarianHut | giant | DIFF (58) Barbarian.count 1/4 | DIFF (4) Barbarian[0].max_hp 691/716 | PASS (0) |
| Mortar | alone | PASS (0) | PASS (0) | PASS (0) |
| Mortar | hog | DIFF (17) tower_hits.count 2/3 | PASS (0) | PASS (0) |
| Mortar | giant | DIFF (35) enemy_hits.count 34/33 | PASS (0) | PASS (0) |
| DartBarrell | alone | DIFF (4) tower_hits[0].tick 80/78 | PASS (0) | PASS (0) |
| DartBarrell | knight | DIFF (29) tower_hits.count 3/4 | PASS (0) | PASS (0) |
| DartBarrell | minions | DIFF (2) enemy_hits[0].tick 34/32 | PASS (0) | PASS (0) |
| Witch | alone | DIFF (24) Skeleton[0].death 220/218 | DIFF (2) Skeleton[4].death 298/282 | DIFF (2) Skeleton[4].death 298/282 |
| Witch | knight | DIFF (40) Skeleton[2].birth 41/39 | PASS (0) | PASS (0) |
| Witch | minions | DIFF (4) Skeleton[2].birth 41/39 | PASS (0) | PASS (0) |
| Pekka | alone | PASS (0) | PASS (0) | PASS (0) |
| Pekka | knight | PASS (0) | PASS (0) | PASS (0) |
| Pekka | minions | PASS (0) | PASS (0) | PASS (0) |
| SkeletonWarriors | alone | DIFF (15) SkeletonWarrior[0].death 106/109 | PASS (0) | PASS (0) |
| SkeletonWarriors | knight | DIFF (10) SkeletonWarrior[0].observed_speed 1.6901/1.7889 | PASS (0) | PASS (0) |
| SkeletonWarriors | minions | DIFF (2) tower_hits[0].tick 200/202 | PASS (0) | PASS (0) |
| SkeletonDragons | alone | PASS (0) | PASS (0) | PASS (0) |
| SkeletonDragons | knight | DIFF (5) tower_hits[1].tick 247/245 | PASS (0) | PASS (0) |
| SkeletonDragons | minions | DIFF (3) tower_hits[0].tick 119/117 | PASS (0) | PASS (0) |

## 4. Residuals (not fixed)

- **Witch alone**: the wave-2 Skeletons have identical (position, birth, ready, death, HP) in both engines; the harness
  pairs units by per-name ordinal and RoyaleSim lists that wave in a different order (its state_json follows entity
  slots, which are reused). Multiset of unit records equal. Not a fidelity difference.
- **Barbarians × Minions, BattleRam × Minions**: everything agrees until C56 bodies take over: the Minions' hits on a
  Barbarian and on our princess tower, and the princess tower's shots at the Minions, drift 2–5 ticks. The pure-C56
  control `Wizard × Minions` (same harness, baseline engine) shows the same 2-tick tower-hit drift
  (tower_hits 121/119, 149/147), as does `SkeletonArmy × Knight` for swarm speed. **Blocked by C56 parity**
  (shared Minion/tower combat timing); not a Batch A data path.
- **GoblinCage × Giant**: with the Giant already in reach when the Brawler's deploy ends, RoyaleSim's first hit is
  ready + 16 ticks, ours ready + 17 (both report ready at tick 171). With a walking target (× Hog) and for the Ram's
  Barbarians the deploy fix is exact, so the gap is in the first-hit load right after a death spawn's deploy, not the
  deploy time. Unresolved; whether it is C56-shared is not established (no C56 death spawn deploys).
- **Tombstone × Hog**: the Hog kills the Tombstone in combat; RoyaleSim's four death Skeletons step 0.15 tile toward
  the Hog on their birth tick, ours acquire the in-reach Hog and hold. Unresolved detail of `first_update` for a target
  already in reach.

## 5. Native (engine-cards/src) changes

- `lib.rs`: `Stats.min_range` + `inside_min_range` in `target_candidate` (current-target keep and acquisition scan);
  movement-phase body moved verbatim into `movement_one` (one `collide` flag; `continue`→`return`); `BattleState.fresh`
  queue + `drain_fresh` (combat_one + movement_one for each queued troop), drained at every per-entity boundary of
  `tick_once`; `Stats.death_first_update` queues death children in `spawn_death_templates`.
- `spawn.rs`: `Spec.first_update`; `production_child` queues its child.
- Glue: `differential.py` exports `min_range`, `death_first_update`; `spawn_snapshot.py` exports `first_update`.
- All new fields are `serde(default)`, inert (0/false) for every C56 card.
- Data-only fixes need no native code (the native reads them from the export): death-spawn deploy start,
  omitted fields, first-wave/blank-interval timing (exported spawner spec).
- Build: `bash build.sh tree out` on 127x08 → `clasher_core.abi3.so` sha256
  `112c064969de71e8f3fba891eaa134c10c9b7865c498567d0202f161a113c90d` (copied to 04 for the gate).

### Native == Python (127x08)

| Check | Result |
|---|---|
| `reports/cards/tools/probe_native.py`, 14 Batch A cards (900 ticks, Knight answer) | 14/14 config ok, deploy agree, no digest mismatch |
| `tools/probe_native_scen.py`: the 42 fidelity scenarios lockstep, digest every tick, no overlay | 42/42 bit-identical |
| same, with the stats overlay | 42/42 bit-identical |
| negative control: patched Python + pinned native 681b5f2c | mismatches exactly where native code changed: Tombstone/BarbarianHut ×3 at tick 19, Witch ×3 at 38 (first update), Mortar hog/giant at 70 (min range); 31/42 equal |

## 6. C56 parity

@@PARITY@@

