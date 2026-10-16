# Batch B1 (arenas 7–10 troops) fidelity fixes — results

Exploration tier. Ours = `engine-cards` Python engine + native mirror (branch `cards/b1`); reference = RoyaleSim (MIT)
through the fidelity harness's adapter table (`cards-15535.1` + CLIENT16402_VALUES), as in Batch A. Fidelity runs on
127x08 (`/mpac/sdicks02/jobs/clasher/cards/b1/fid`), C56 gate on 127x04 (`/mpac/sdicks02/jobs/clasher/cards/b1`).
Pure stat corrections are not in the engine: they are listed in §2 for the `live16402` overlay and applied for the
"with stats" runs through a scratch gamedata on 08 (`b1/stats/gamedata.json`, from `fid/stats-spec.json`, 08 only).
Start point = commit 7720915a8 (Batch A WIP) + Batch A's later serialization diff.

## Verdicts (3 scenarios per card; full table §3)

| Card | Status | Scenarios PASS (before → mechanics → mechanics+stats) |
|---|---|---|
| RoyalGiant | **PASS (mechanics)** | 0 → 3 → 3 |
| ThreeMusketeers | **PASS (mechanics)** (base HP 345 = reference table; 16.402 HP 354 via overlay) | 0 → 3 → 3 |
| GiantBuffer | **PASS — stats via overlay only** (HP); the Rune Giant buff is not exercised by these scenarios | 0 → 0 → 3 |
| BattleHealer | **PASS (mechanics) + stats via overlay**; spawn heal checked against RoyaleSim in an extra scenario (identical) | 0 → 0 → 3 |
| GoblinGiant | **PASS (mechanics) + stats via overlay** on knight/minions; alone = dismount ordinal swap + one 1-tick kill (§4) | 0 → 0 → 2 |
| RoyalRecruits | **PASS (mechanics)** on alone/minions; knight = same-tick tower-hit order only (multiset equal) | 0 → 2 → 2 |
| Hunter | **PASS (mechanics)** on knight; alone/minions equal volley totals, tick spread differs by the random pellet holds (§4) | 0 → 1 → 1 |
| MiniSparkys | PASS (stats) on alone; knight/minions residual = C56-shared stun/retarget clocks (§4) | 0 → 0 → 1 |
| GiantSkeleton | alone PASS; knight/minions residual = C56-shared plain-bomb fuse (Balloon control shows the same 2 ticks) | 1 → 1 → 1 |
| SkeletonBalloon | partial: barrel path, container timing, kamikaze drain fixed (minions 14 → 4 diffs); residual = death-slide law (§4) | 0 → 0 → 0 |

B1 scenarios PASS: before 0/30 (base engine, no stats), 6/30 (base engine + stats) → 10/30 mechanics only →
**19/30 with stats**, plus 4 scenarios whose only differences are harness ordering artefacts (RoyalRecruits knight,
GoblinGiant alone) or the random pellet stream (Hunter alone/minions). Whole 66-card pool, same stats spec:
82/196 → **95/196**. **No non-B1 scenario changed** (verdict or number of differences) between
`final-basestats` and `final-stats`.

## 1. Causes and fixes (engine changes; all in `engine-cards/`)

| Card | Cause (vs RoyaleSim) | Kind | Fix (file:function) |
|---|---|---|---|
| RoyalGiant, GoblinGiant | Stomp gait columns StopMovementAfterMS 640 / WaitMS 100 (and SightClipSide 2000, Royal Giant ProjectileStartRadius 1200) omitted by the export: walked at raw 45/60 instead of the normalized 52/69 with the stomp pause. Mass/IgnorePushback omitted. | omitted fields | `py/src/clasher/balance.py` CHARACTER_FIELD_OVERRIDES / CHARACTER_RUNTIME_TRAITS (existing stomp code path, as Giant) |
| GoblinGiant | SpawnAttach riders missing: two SpearGoblinGiant riders on an arc behind the Giant, untargetable and immune while mounted, attacking on their own, carried to the mount's position each tick at its start-of-tick heading; dying with the mount and dropping a Spear Goblin each at mount position + arc offset (DeathSpawnDeployTime 700). Rider row fields omitted (FlyingHeight 4000, SpawnAngleShift -22, SpawnMaxAngle 90). | mechanic + omitted fields | new `py/src/clasher/mechanics/shared/riders.py` (AttachedRiders, RiderOnMount, rider_arc_offset_units); `factory/mechanic_detector.py` (spawnAttach); `battle.py:BattleState.step` (mount facings before combat, carry after combat), `_accumulate_troop_collision_for`, `_spawn_unit_at_position` (new `on_created` hook); `entities.py:Troop.update_movement_component`, avoidance scan; `native_spatial.py`. Native `src/riders.rs` (RiderSpec, `Entity::absent`, `carry_riders`, `dismount_riders`), `lib.rs` (Entity.mount/rider_rank, Stats.riders, every stagger victim test → `absent()`, deploy mount remap, collide neighbour skip, death trigger); `differential.py` `_rider_stats`, mount export, rider death children, mirror_x off |
| ThreeMusketeers | The export has only the card row: our engine deployed one 100-HP placeholder. The rework is three characters at SummonCharactersOffsets ((0,+1000),(+1000,-1000),(-1000,-1000) from the tap for side 0, owner-frame negated), staggered 100 ms, with an OnStartingAttackAction selector: a bayonet hit (123 base) when the target is on the ground within 1600 + both radii, chosen at swing start. | missing payload + mechanic | `balance.py` ENTRY_TRANSFORMS `_three_musketeers_entry` (character rows from RoyaleSim cards-15535.1), `card_types.py` summon_members / attack_select, `battle.py:BattleState._spawn_explicit_members`, `entities.py:Troop.update_combat_component` + `Troop._melee_selected`; native `lib.rs` Stats.attack_select, Entity.attack_choice/select_target, bayonet branch, `riders.rs` melee_selected; `differential.py` `_attack_select_stats` |
| RoyalRecruits | Legacy name-gated line spawn (2.5-tile spacing, no stagger, members clamped to the edge). RoyaleSim: SummonWidth 14000 wide formation (the Royal Hogs' one), member stagger 100 ms, the line centre moved to the nearest tile where the whole line may stand (`line_centre_client`), zigzag mirrored on the right lane. | omitted field + mechanic | `balance.py` ENTRY_PATH_OVERRIDES RoyalRecruits summonWidth; `battle.py:BattleState._native_line_centre`, `_line_territory`, legacy line kept only without SummonWidth; `formations.py:line_centre_client`, `formation_offset` (right-lane mirror for wide lines ≥ 5); native `deployment.rs:line_centre`, `lib.rs` Card.line_search + deploy; `differential.py` line_search, mirror_x |
| Hunter | One pellet per shot. RoyaleSim: MultipleProjectiles 10 straight pellets from the launch point aimed ProjectileRange from the attacker at 0, +7, -7, +14, … degrees, each held ceil(U/50 ms) ticks (U in 0..RandomDelay 200), tested at creation with ProjectileRadius + ProjectileStartExtraRadius, gone on the tick they hit (CheckCollisions). Projectile row fields omitted. | mechanic + omitted fields | `entities.py:Troop._create_projectile_fan`, `Projectile.stop_on_hit` (`resolve_start_collision`, `_update_piercing_tick`); `balance.py` HunterProjectile row, Hunter projectileStartRadius 1000; native `projectiles.rs:fire_fan`, piercing stop, `lib.rs` Stats.fan/fan_radius/fan_delay_ms/fan_stop, piercing launch hold; `differential.py:_fan_stats`, `live_snapshot.py` stop_on_hit |
| BattleHealer | (1) Hovering ran the Royal Ghost's direct (air-like) route, ~1.7 % slower and on another line; RoyaleSim's hover only prices river water in the ground route, so on these paths she walks like a Knight. (2) Neither heal existed: the SpawnAreaObject heal ignored healPerSecond, AreaEffectOnHit was not read. | mechanic | `balance.py` trait `hovering: False` (walker route); `mechanics/shared/spawn_area.py` `heal_area_pulse`, `SpawnAreaEffect.on_created` (cast at creation, not by clones), `AreaEffectOnHit`; `scope_spells.py:HealPulse.excluded_id`; native `scope.rs` Effect::Heal.exclude, `lib.rs` Config.create_areas (deploy) / hit_areas (melee hit, `riders.rs:hit_area`), `spawn.rs` exclude remap; `differential.py` create_areas / hit_areas |
| SkeletonBalloon | (1) FlyDirectPaths not read: the barrel aimed at its route cell and drifted 0.2 tiles. (2) Container released units and hit together one tick early; RoyaleSim (units_at_fuse_end): units on fuse end + 1 tick with a same-tick first update, hit one tick later. (3) KamikazeTime: RoyaleSim drains floor(maxHP × 50 / 500) per tick from the fire. | omitted field + mechanics | `card_types.py` fly_direct_paths, `entities.py:Troop._native_movement_waypoint`, native `lib.rs` Stats.fly_direct; `entities.py:TimedExplosive.update` / `_spawn_death_units(first_update)`, native `c56.rs:bomb_tick` (container branch only; plain bombs unchanged); `entities.py:Troop._kamikaze_drain`, native `lib.rs:kamikaze_drain` |
| MiniSparkys | OverrideAttackFinishTime omitted (mass too); hit/load stats. | omitted field + stat | `balance.py` MiniZapMachine overrideAttackFinishTime/attackFinishTime 0, mass 4; stats → §2 |
| GiantSkeleton | Bomb row's DeathDamageRadius 3000 / DeathPushBack 1800 omitted (our default 2000). | omitted fields | `balance.py` GiantSkeletonBomb |
| GiantBuffer | HP only. | stat | §2 |

Every new native field is `serde(default, skip_serializing_if = …)` at its inert default (Batch A's rule), and every new
code path is reached only by data no C56 card carries (riders, fan, attack selector, line search, container bombs,
kamikaze delay, heal areas, fly-direct); the stagger→`absent()` rewrite is the stagger test itself for every
entity without a mount.

## 2. Stat-value corrections for the `live16402` overlay (not applied in engine-cards)

Base (level 1) values. "Scratch" = value used in the fidelity "with stats" runs (the harness reference table); the
overlay should take the 16.402.19 column.

| Card | Body (nested object) | Field | Ours | Scratch (ref. table) | RoyaleSim 16.402.19 |
|---|---|---|---|---|---|
| BattleHealer | BattleHealer | hitpoints | 671 | 750 | 750 |
| BattleHealer | BattleHealer | damage | 58 | 105 | 105 |
| BattleHealer | BattleHealer | hitSpeed | 1500 | 2000 | 2000 |
| BattleHealer | BattleHealer | loadTime | 1200 | 1600 | 1600 |
| BattleHealer | BattleHealerSpawnHeal | radius | 2500 | (not applied) | 3000 |
| BattleHealer | BattleHealerHeal | radius | 4000 | (not applied) | 3000 |
| GiantBuffer | GiantBuffer | hitpoints | 1040 | 1100 | 1100 |
| GoblinGiant | SpearGoblinGiant | hitSpeed | 1700 | 1600 | 1600 |
| GoblinGiant | SpearGoblinGiant | loadTime | 1200 | 1100 | 1100 |
| MiniSparkys | MiniZapMachine | hitSpeed | 2100 | 2200 | 2300 |
| MiniSparkys | MiniZapMachine | loadTime | 1300 | 1400 | 1500 |
| ThreeMusketeers | ThreeMusketeer_Rework_Character_1/2/3 | hitpoints | 345 (new row) | 345 | 354 |

The scratch spec also carried Batch A's seven rows unchanged (Brawler HP, Bomber projectile, Mortar, SpearGoblin,
Barbarian), so the GoblinGiant dismount Spear Goblins use the SpearGoblin row too.

## 3. Per-scenario results (verdict (number of differences) first difference; ours/RoyaleSim)

Columns: before = base engine (Batch A tree) without stats (`batchA/fid/final-mech.jsonl`); before + stats =
base engine with the §2 scratch stats (`final-basestats.jsonl`); mechanics = B1 engine without stats
(`final-mech.jsonl`); mechanics + stats (`final-stats.jsonl`).

| Card | Scenario | Before | Before + stats | Mechanics | Mechanics + stats |
|---|---|---|---|---|---|
| RoyalGiant | alone | DIFF (13) RoyalGiant[0].configured_speed 45.0/52.0 | DIFF (13) RoyalGiant[0].configured_speed 45.0/52.0 | PASS (0) | PASS (0) |
| RoyalGiant | knight | DIFF (30) RoyalGiant[0].configured_speed 45.0/52.0 | DIFF (30) RoyalGiant[0].configured_speed 45.0/52.0 | PASS (0) | PASS (0) |
| RoyalGiant | minions | DIFF (4) RoyalGiant[0].configured_speed 45.0/52.0 | DIFF (4) RoyalGiant[0].configured_speed 45.0/52.0 | PASS (0) | PASS (0) |
| GiantBuffer | alone | DIFF (4) GiantBuffer[0].max_hp 2662/2816 | PASS (0) | DIFF (4) GiantBuffer[0].max_hp 2662/2816 | PASS (0) |
| GiantBuffer | knight | DIFF (25) GiantBuffer[0].max_hp 2662/2816 | PASS (0) | DIFF (25) GiantBuffer[0].max_hp 2662/2816 | PASS (0) |
| GiantBuffer | minions | DIFF (16) GiantBuffer[0].max_hp 2662/2816 | PASS (0) | DIFF (16) GiantBuffer[0].max_hp 2662/2816 | PASS (0) |
| BattleHealer | alone | DIFF (16) BattleHealer[0].max_hp 1717/1920 | DIFF (5) tower_hits[0].tick 163/161 | DIFF (17) BattleHealer[0].max_hp 1717/1920 | PASS (0) |
| BattleHealer | knight | DIFF (20) BattleHealer[0].max_hp 1717/1920 | PASS (0) | DIFF (20) BattleHealer[0].max_hp 1717/1920 | PASS (0) |
| BattleHealer | minions | DIFF (17) BattleHealer[0].max_hp 1717/1920 | DIFF (13) tower_hits.count 5/6 | DIFF (18) BattleHealer[0].max_hp 1717/1920 | PASS (0) |
| ThreeMusketeers | alone | DIFF (8) ThreeMusketeer_Rework_Character_1.count 0/1 | DIFF (8) ThreeMusketeer_Rework_Character_1.count 0/1 | PASS (0) | PASS (0) |
| ThreeMusketeers | knight | DIFF (46) ThreeMusketeer_Rework_Character_1.count 0/1 | DIFF (46) ThreeMusketeer_Rework_Character_1.count 0/1 | PASS (0) | PASS (0) |
| ThreeMusketeers | minions | DIFF (33) ThreeMusketeer_Rework_Character_1.count 0/1 | DIFF (33) ThreeMusketeer_Rework_Character_1.count 0/1 | PASS (0) | PASS (0) |
| RoyalRecruits | alone | DIFF (69) Recruit[0].death None/356 | DIFF (69) Recruit[0].death None/356 | PASS (0) | PASS (0) |
| RoyalRecruits | knight | DIFF (69) Recruit[1].ready 20/22 | DIFF (69) Recruit[1].ready 20/22 | DIFF (6) tower_hits[5].victim [1, 1]/[1, 2] | DIFF (6) tower_hits[5].victim [1, 1]/[1, 2] |
| RoyalRecruits | minions | DIFF (40) Recruit[1].ready 20/22 | DIFF (40) Recruit[1].ready 20/22 | PASS (0) | PASS (0) |
| Hunter | alone | DIFF (4) tower_hits.count 0/6 | DIFF (4) tower_hits.count 0/6 | DIFF (10) tower_hits.count 7/6 | DIFF (10) tower_hits.count 7/6 |
| Hunter | knight | DIFF (8) tower_hits.count 5/0 | DIFF (8) tower_hits.count 5/0 | PASS (0) | PASS (0) |
| Hunter | minions | DIFF (13) tower_hits.count 2/0 | DIFF (13) tower_hits.count 2/0 | DIFF (5) enemy_hits.count 7/6 | DIFF (5) enemy_hits.count 7/6 |
| GoblinGiant | alone | DIFF (30) GoblinGiant[0].configured_speed 60.0/69.0 | DIFF (30) GoblinGiant[0].configured_speed 60.0/69.0 | DIFF (41) GoblinGiant[0].death 553/551 | DIFF (2) SpearGoblin[0].death 585/None |
| GoblinGiant | knight | DIFF (39) GoblinGiant[0].configured_speed 60.0/69.0 | DIFF (39) GoblinGiant[0].configured_speed 60.0/69.0 | DIFF (22) enemy_hits.count 20/21 | PASS (0) |
| GoblinGiant | minions | DIFF (43) GoblinGiant[0].configured_speed 60.0/69.0 | DIFF (43) GoblinGiant[0].configured_speed 60.0/69.0 | DIFF (22) tower_hits.count 10/11 | PASS (0) |
| SkeletonBalloon | alone | DIFF (21) Skeleton[2].death 209/194 | DIFF (21) Skeleton[2].death 209/194 | DIFF (20) Skeleton[0].death 257/242 | DIFF (20) Skeleton[0].death 257/242 |
| SkeletonBalloon | knight | DIFF (42) tower_hits.count 22/26 | DIFF (42) tower_hits.count 22/26 | DIFF (31) tower_hits.count 20/26 | DIFF (31) tower_hits.count 20/26 |
| SkeletonBalloon | minions | DIFF (14) Skeleton[0].ready 77/79 | DIFF (14) Skeleton[0].ready 77/79 | DIFF (4) Skeleton[0].observed_speed 1.7763/2.1258 | DIFF (4) Skeleton[0].observed_speed 1.7763/2.1258 |
| MiniSparkys | alone | DIFF (9) tower_hits.count 10/9 | PASS (0) | DIFF (9) tower_hits.count 10/9 | PASS (0) |
| MiniSparkys | knight | DIFF (13) enemy_hits[3].tick 78/80 | DIFF (2) enemy_hits[14].tick 361/348 | DIFF (13) enemy_hits[3].tick 78/80 | DIFF (2) enemy_hits[14].tick 361/348 |
| MiniSparkys | minions | DIFF (8) tower_hits.count 2/3 | DIFF (7) tower_hits.count 2/3 | DIFF (9) tower_hits.count 2/3 | DIFF (5) tower_hits.count 2/3 |
| GiantSkeleton | alone | PASS (0) | PASS (0) | PASS (0) | PASS (0) |
| GiantSkeleton | knight | DIFF (1) tower_hits[7].tick 568/570 | DIFF (1) tower_hits[7].tick 568/570 | DIFF (1) tower_hits[7].tick 568/570 | DIFF (1) tower_hits[7].tick 568/570 |
| GiantSkeleton | minions | DIFF (1) tower_hits[2].tick 273/275 | DIFF (1) tower_hits[2].tick 273/275 | DIFF (1) tower_hits[2].tick 273/275 | DIFF (1) tower_hits[2].tick 273/275 |

## 4. Residuals (not fixed)

- **GiantSkeleton knight/minions** (1 diff each): the bomb lands at death + 59 ticks, RoyaleSim + 61. The C56 Balloon's
  bomb (same TimedExplosive path) shows the same 2 ticks against RoyaleSim (ctl run: alone/knight 372/374), so this is
  the shared plain-bomb fuse; changing it breaks C56 parity. Only container bombs (with children) were re-timed.
- **SkeletonBalloon**: after the fixes the barrel path, death tick, container release (T + 12) and hit (T + 13), the
  children's ready ticks and birth positions are exact; the remaining differences come from the children's
  death-spawn slide. Ours (native-derived `begin_death_spawn_travel`, 250 units a tick with collision and avoidance,
  shared with C56 Golem) collides with the tower and slides into the river; RoyaleSim's measured ring slide ignores
  bodies and stops at water. Native logic is authoritative on mechanics and the code is C56-shared, so not changed.
- **MiniSparkys knight** (2): the C56 Knight's attack clock under ZapFreeze stuns (ours resets loaded work, RoyaleSim
  holds it). **MiniSparkys minions** (5): a Zappy whose target dies just before its hit loses the loaded hit in ours
  (legacy retarget reset) and keeps it in RoyaleSim. Both are shared C56 clocks.
- **Hunter alone/minions**: same pellets and damage per volley; per-pellet hit ticks follow each engine's own random
  stream (RoyaleSim draws the holds from its client stream), so tick-exact equality is not expected. Hold law and
  creation/first-step timing checked equal.
- **GoblinGiant alone**: all units, ticks and positions equal except the two dismount Spear Goblins are listed in the
  other order by RoyaleSim (slot reuse) and the one the King Tower kills dies on 585 vs 586.
- **RoyalRecruits knight**: the 6 differences are two tower hits on the same tick listed in the other order.
  Not handled: a tap on a princess-tower tile is refused by ours (RoyaleSim relocates the line).
- **BattleHealer**: her self-heal when not attacking (BuffWhenNotAttackingTime 5000) has no buff row in either data set
  and is not simulated by either engine; the on-hit heal is from our data only (RoyaleSim does not read
  AreaEffectOnHit).
- **GiantBuffer**: the Rune Giant's enchantment is not exercised by the harness scenarios and was not audited.

## 5. Native == Python (127x08, native built from this tree)

| Check | Result |
|---|---|
| `tools/probe_native_scen.py` (via `run_scen.sh`), 10 B1 + 14 Batch A cards × 3 scenarios, no overlay | 72/72 bit-identical every tick |
| same, with the stats overlay | 72/72 bit-identical |
| `reports/cards/tools/probe_native.py` (ladder probe, 900 ticks vs Knight), 10 B1 cards | 10/10 config ok, deploys agree, no mismatch |
| `tools/probe_taps.py`: RoyalRecruits 15 taps (both seats); GoblinGiant 5 taps × Knight/Minions/Fireball/Zap/Arrows/Log/BabyDragon/MinionHorde; ThreeMusketeers 5 taps × Knight/Minions/Giant/HogRider/Fireball; Hunter 5 taps; BattleHealer 3 heal scenarios | all bit-identical |
| negative control (pinned-era native b1/out-base) on SkeletonBalloon | diverges at tick 20 (flight path) as expected |
| RoyaleSim placement (`tools/tapcmp.py`): RoyalRecruits 13 taps, ThreeMusketeers 6 taps | all identical to RoyaleSim |

Native builds: `bash tools/build.sh tree out` on 127x08 (-j8); final `clasher_core.abi3.so` sha256
`6215ee543ba28f2d8756d0a6cc6d8681d7bc36f1b4d2348891ce10a1d8e3cd00` (copied to 04 for the gate).

## 6. C56 parity

Batch A's gate script (`tools/gate.sh` = `batchA/tools/gate.sh` with B1 paths; BOT LEAD native-total-tools
parity_fixtures 577 + parity_roots 300 × full/cut), pinned arm = r1 Python + native 681b5f2c, total arm = b1 `rt/`
(r1 mirror with src/engine-rs/gamedata → b1 tree) + b1 native.

| Gate | Tree / native | Fixtures (identical / rust_only chains equal / rs_full_parity) | Roots (identical, full + cut) |
|---|---|---|---|
| intermediate (02:42–03:11Z) | 05f84d347 / a25c1848 (riders, absent() rewrite, fan, line search, container, drain, fly-direct) | 577/577 / 577 / 429 = 429 | 600/600 |
| **final** (03:26–03:58Z) | c8e11955d / 6215ee54 (all B1 changes) | **577/577 / 577 / 429 = 429**, 0 rust_only errors | **600/600** |

**C56 gate: PASS** on both trees: every fixture record and every sampled root record (300 roots × full/cut, 12 games,
1,800 select_action calls) identical between the pinned arm and B1. compare.json files:
`gate-intermediate-compare.json`, `gate-final-compare.json` (host dirs `b1/gate-r1/`, `b1/gate/` on 127x04).
