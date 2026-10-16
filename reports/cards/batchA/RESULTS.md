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
| Tombstone, BarbarianHut | (1) A building with blank SpawnStartTime waited one SpawnPauseTime before its first wave; RS (measured, 44 Tombstone + 2 Hut deploys) emits on the deploy-end tick (`spawner.FIRST_WAVE`). (2) Emitted units, and the death units of these buildings, stood on the emission point on their birth tick; RS gives them a same-tick target pass + move step (`spawner.SPAWNED_FIRST_STEP`, `state.rs first_update`). A death spawn's members step together (one point). | mechanic | `factory/mechanic_detector.py` (first-wave default 0 for buildings; `_steps_first`); `mechanics/shared/spawner.py:PeriodicSpawner._spawn_units`, `death_effects.py:DeathSpawn.on_death` → `battle.py:BattleState._first_update_spawned`; native `lib.rs:first_update_now` + `movement_one` (synchronous at the spawn point, §5 review r2), `spawn.rs:production_first_update` |
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
  movement-phase body moved verbatim into `movement_one` (one `collide` flag; `continue`→`return`); the tick's
  avoidance grid, its indexed count and the route inputs are tick-scoped `BattleState` fields (`grid`, `grid_indexed`,
  `route_ctx`, `in_tick`; never serialized) instead of `tick_once` locals, so `first_update_now` (combat_one +
  movement_one) runs **synchronously at the spawn point**: per death child in `spawn_death_templates` right after its
  Freeze inheritance (`Stats.death_first_update`).
- `spawn.rs`: `Spec.first_update`; `production_tick` runs `production_first_update` right after each spawn call
  (a wave: every member with its siblings hidden).
- Glue: `differential.py` exports `min_range`, `death_first_update`; `spawn_snapshot.py` exports `first_update`.
- All new fields are `serde(default)` and inert (0/false) for every C56 card, and `skip_serializing_if` at that
  default, so a C56 `snapshot()` is byte-identical. (The first gate attempt, build `112c0649…`, serialized them:
  every `rust_only` chain differed only through the snapshot text, while every Python↔Rust `rs` record already
  agreed. Run stopped at 506/577 fixtures, kept on 04 as `batchA/gate-killed-r1/`.)
- Data-only fixes need no native code (the native reads them from the export): death-spawn deploy start,
  omitted fields, first-wave/blank-interval timing (exported spawner spec).
- Build: `bash build.sh tree out` on 127x08 → `clasher_core.abi3.so` sha256
  `de11f12401da396b309cd2e5d3ea422cfa1c94f462a4e3250fd51d89a62887b1` (review round 2; copied to 04 for the gate).
  Earlier builds: `112c0649…` (serialized the new fields), `1923619e…` (gate PASS, commit 9eed63029),
  `5f07238c…` (review r1, commit b7c6976e4; its gate was stopped as superseded).

### Review round 2 (Sol, 2026-10-16): first update at the same boundary on every path

BLOCKER: when a spell killed a Tombstone, Python first-updated the death Skeletons at the death-spawn point and the
spell then resumed (its stun/freeze/slow pass met units that had already stepped), while native queued them and
drained after the whole spell, so the children were stunned before they could move. The class: any effect with
work left after the kill. **Fix, structural:** native now runs the first update synchronously at the spawn
point, exactly where Python does (`death_effects.py:DeathSpawn.on_death` / `spawner.py:PeriodicSpawner._spawn_units`
↔ `lib.rs:spawn_death_templates` / `spawn.rs:production_tick`); the deferred queue and its drains are gone.
Since a first-update unit is only ever created in those two functions in each engine, every caller below gets the
same boundary by construction. The table checks each path anyway. Python also restores, rather than clears, the
hidden-sibling set after a nested first update (native saves/restores it the same way).

Audit (`tools/probe_first_update_paths.py`; each case on both seats, the red one mirrored; digest compared every
tick; HP/positions set in a Python-only setup before the shared snapshot; "killer" = victim dies before its
decay-only control and the killing blow exceeds decay, which is under 1 HP/tick for a Tombstone):

| Path (enclosing work left after the kill) | Case | Python boundary | Native boundary | Killer confirmed (death / control, blow) | de11f124 (now) | 5f07238c (r1, queued drain) |
|---|---|---|---|---|---|---|
| Zap: damage, then stun pass | `zap` | `DeathSpawn.on_death`, per child after Freeze inheritance | `spawn_death_templates` → `first_update_now`, same point | 1 / 113, 99 | equal ×2 | **mismatch tick 1 ×2** |
| Freeze: damage, then freeze pass | `freeze` | same | same | 1 / 22, 19 | equal ×2 | **mismatch tick 1 ×2** |
| Snowball: damage, knockback, slow | `snowball` | same | same | 24 / 113, 79 | equal ×2 | **mismatch 24 ×2** |
| Earthquake area tick: damage, slow | `earthquake` | same | same | 20 / 67, 42 | equal ×2 | **mismatch 20 ×2** |
| Fireball projectile spell (+ knockback) | `fireball`, `fireball_hut` (BarbarianHut) | same | same | 32 / –, 272; 32 / 154, 238 | equal ×4 | equal |
| Arrows volleys | `arrows` | same | same | 16 / 67, 46 | equal ×2 | equal |
| Rocket | `rocket` | same | same | 55 / –, 452 | equal ×2 | equal |
| Lightning strike | `lightning` | same | same | 19 / –, 483 | equal ×2 | equal |
| Log (rolling) | `log` | same | same | 41–42 / 67, 23–24 | equal ×2 | equal |
| Poison area tick (slow) | `poison` | same | same | 25 / 44, 18 | equal ×2 | equal |
| Tornado (pull + damage) | `tornado` | same | same | 12 / 33, 20 | equal ×2 | equal |
| GoblinCurse (damage, curse spawn) | `goblin_curse` | same | same | 21 / 33, 12 | equal ×2 | equal |
| Projectile impact (Musketeer) | `musketeer_projectile` | same | same | 53 / 226, 153 | equal ×2 | equal |
| Splash projectile (Bomber) | `bomber_splash` | same | same | 5 / 44, 36 | equal ×2 | **mismatch 5 ×2** |
| Melee (Knight) | `knight_melee` | same | same | 55 / 226, 152 | equal ×2 | equal |
| Tower shot (princess tower → GoblinDrill) | `tower_shot_drill` | same | same | blow 26/13 (drill decay ≈6.5/tick) | equal ×2 | equal |
| Death bomb (Balloon shot down; TimedExplosive) | `balloon_death_bomb` | same | same | 3 / 44, 37 | equal ×2 | equal |
| Death damage chain (Golem dies, its death damage kills) | `golem_death_damage` | same | same | 9 / 44, 32 | equal ×2 | **mismatch 9 ×2** |
| Champion ability (Mighty Miner lane-switch bomb) | `mighty_miner_ability` | same | same | 33 / 169 (no-ability 79), 121 | equal ×2 | equal |
| Frozen building dies (review r1) | `frozen_tombstone_death` | same | same | Rocket during Freeze | equal ×2 | equal |
| Periodic wave (object phase) + apart | `witch_corner` (`probe_native_scen.py --cases`) | `PeriodicSpawner._spawn_units`, after the call | `production_tick` → `production_first_update`, after the call | – | equal ×2 | equal |

Not covered: Ice Golem's death nova (it does not damage buildings in this engine, so no kill: probe dropped);
BarbLog's barrel cannot reach a building from the caster's half (Log covers rolling); of the champion abilities
only Mighty Miner's is probed (Archer Queen's and Goblinstein's are not). These paths still go through the same
two creation functions.

Mutation checks (Python mutants, `tools/mutants.py`, against native de11f124):

| Mutant | Rows run | Detected |
|---|---|---|
| `no_death_first_update` (death spawns skip the first update) | zap, freeze, fireball, knight_melee, golem_death_damage (×2 seats) | 10/10 mismatch (ticks 1, 1, 32, 55, 9) |
| `first_update_before_freeze` (review r1's bug: step before the Freeze inheritance) | frozen_tombstone_death, freeze, zap (×2) | frozen_tombstone_death 2/2 (tick 95); freeze and zap do not expose it (the parent is not frozen when it dies) |
| the r1 native itself (queued drain after the enclosing effect) | all 21 cases ×2 | 6 cases ×2 seats mismatch (table column) |

### Review round 1 (Sol, 2026-10-16): fixes

1. **BLOCKER, native ≠ Python on a frozen death:** Python ran a death child's first update before the Freeze
   inheritance; native froze at creation and stepped later. A frozen Tombstone's Skeletons moved in Python and
   stood still in native. Fix: `death_effects.py:DeathSpawn.on_death` runs `_first_update_spawned` after the child is fully
   initialised (Freeze inherited), the native order. Probe `frozen_tombstone_death` (+ red seat): before, first digest
   mismatch at tick 95 on both seats (native 1923619e); after, none.
2. **SHOULD-FIX, wave siblings visible in the first update:** members emitted together saw each other in the
   first update's collision and avoidance scans; RoyaleSim's `first_update(..., apart=true)` hides them. Fix: Python
   `_first_update_spawned(hidden=…)` (the wave's other ids, from `PeriodicSpawner._spawn_units`), skipped in
   `battle.py:_accumulate_troop_collision_for` and `entities.py:_update_native_avoidance`; native `BattleState.hidden`
   (wave = same parent in the drained batch), skipped in `lib.rs:collide` and `update_avoidance`. Probe `witch_corner`
   (+ red): the Witch is moved into the corner just before her first wave so the clamped ring overlaps. Native == Python
   with the rule; with the rule disabled in Python only, the engines diverge at tick 1 (the wave tick), so the
   rule is live and both engines apply it identically.

### Native == Python (127x08)

| Check | Result |
|---|---|
| `reports/cards/tools/probe_native.py`, 14 Batch A cards (900 ticks, Knight answer) | 14/14 config ok, deploy agree, no digest mismatch |
| `tools/probe_native_scen.py`: the 42 fidelity scenarios lockstep, digest every tick, no overlay | 42/42 bit-identical |
| same, with the stats overlay | 42/42 bit-identical |
| review cases (`probe_native_scen.py --cases`): frozen Tombstone death ×2 seats, Witch in a corner ×2 seats | 4/4 bit-identical on 5f07238c (frozen cases mismatched at tick 95 on 1923619e) |
| 42 scenarios rerun on 5f07238c, with and without overlay | 42/42 and 42/42; `probe_native.py` 14/14; fidelity verdicts for Witch/Tombstone/BarbarianHut/GoblinCage unchanged |
| review r2 on de11f124: path audit (21 cases ×2 seats), review-r1 cases, 42 scenarios ×2 roots, `probe_native.py` | 42/42, 4/4, 42/42 + 42/42, 14/14 |
| negative control: patched Python + pinned native 681b5f2c | mismatches exactly where native code changed: Tombstone/BarbarianHut ×3 at tick 19, Witch ×3 at 38 (first update), Mortar hog/giant at 70 (min range); 31/42 equal |

## 6. C56 parity

BOT LEAD gate tools (`reports/bot/learned-opponent/native-total-tools/` parity_fixtures.py, parity_roots.py,
compare.py; unmodified, wrapped by `tools/gate.sh`), run on 127x04 2026-10-16 01:44:11Z–02:18:04Z, ≤8 processes,
nice, under `cpu_job.sh 8`. **pinned** = runtime r1 Python (`src`, engine-rs glue) + `native-total-r1` (681b5f2c);
**patched** = r1 mirror with `src` → engine-cards/py/src and `engine-rs` → engine-cards (this patch, no stat overlay) +
native `1923619e…`. Outputs: 04 `batchA/gate/`.

| Gate | Inputs | Pinned | Patched | Equal |
|---|---|---|---|---|
| (a) 577 fixtures, `rs_parity.run_one` (Python ↔ Rust lockstep) | 577 train+val | 429/577 full parity | 429/577 | per-fixture records **577/577 identical** |
| (a') Rust-only full trajectories (digest every tick, snapshots every 100 ticks + end) | 1,010,680 ticks | 0 errors | 0 errors | chains **577/577 equal**; files byte-identical, sha256 `f5a2665b2e7a14e4bf5cb2691a63ddc5cb7df150efd7f3b4ca7fd42fb5b5c670` both (the value NATIVE-TOTAL.md §4 recorded) |
| (b) 300 sampled real roots × full/cut | 1,043 roots, 12 games, ticks 140–5,570 | 600 records | 600 | **600/600 identical**; files byte-identical apart from the header, sha256 `a710536268e111f1c200dea5c916302a258199dc3859e817e35236fb6094ea92` both |
| ↳ `full` | Same 300 sampled root IDs | 300 records | 300 | **300/300 identical**, no differing root IDs |
| ↳ `cut` | Same 300 sampled root IDs | 300 records | 300 | **300/300 identical**, no differing root IDs |
| ↳ contents | 9,336 rollout_e1 values, 1,800 select_action, 478 apply_discrete, 1,800 step checks | | | all equal |
| C56 config export (`differential.config`, all 56 cards) | | | | equal apart from the new keys, which are inert (0/false) for C56 (`tools/cfg_dump.py`, `cfg_diff.py`) |

**PASS: C56 behaviour is bit-identical on this gate (native 1923619e).** The review-round-2 build de11f124 is
re-gated on 127x04 with the same `tools/gate.sh` (the 5f07238c run was stopped as superseded, partial outputs in
`batchA/gate-5f07238c-stopped/`); earlier outputs are kept as 04 `batchA/gate-1923619e/`, the new ones land in
`batchA/gate/compare.json`. The native source did change (§5); the gate covers that, plus the config-export change.

Test-shepherd audit: the original PGID/PID 2388512 exited normally; no restart or additional simulation job
was needed. Fixtures ended at 02:17:30Z and roots at 02:18:04Z. Verified native SHA256s:
`681b5f2c866ba3df1aa9903d1bf40d565e21feb6f541319bef84ee493c72066b` (pinned) and
`1923619e996684122571cae05688e085163328b3cf6334dd3bad1a2d8e53aae8` (patched).
The three gate scripts match the documented native-total-tools copies byte-for-byte. Independently
read all 577 fixture pairs and all 600 root pairs, checked exact body bytes in all four root shards
(native-path/hash headers excluded), and checked matching `full`/`cut` root ID sets.
**Differing fixture IDs: none. Differing root IDs: none.** Both arms retain the existing 429/577
Python↔Rust full-length parity outcomes; this gate establishes regression parity rather than resolving
those existing mismatches. No first-tick/subsystem triage or fix spec is needed. Evidence:
`127x04:/mpac/sdicks02/jobs/clasher/cards/batchA/gate/compare.json`, the fixture/root JSONLs,
and `batchA/gate.log`. Measurement only; the test shepherd changed reports only and committed nothing.
