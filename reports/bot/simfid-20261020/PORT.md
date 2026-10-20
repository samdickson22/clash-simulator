# Calibration port to the full-pool engine (engine-cards)

## Result (2026-10-20)

Every accepted rule of calibration batches 1+2 (c7be66486, BATCH1.md, BATCH2.md) is now in the full-pool engine:
`engine-cards/py/src/clasher`, `engine-cards/py/gamedata.json`, `engine-cards/src` (Rust), and the glue
`engine-cards/differential.py` / `spawn_snapshot.py`. The MERGE-TESTFIX test change is in too.

| T1, 577 native fixtures (15.535) | no-tower ≤¼ tile | no-tower HP exact | winner agrees |
|---|---|---|---|
| engine-cards/py + r1 data, base 3326d2d2b | 51.39 | 65.15 | 426 |
| **engine-cards/py + data, this branch** | **72.48** | **80.56** | **448** |
| src/clasher calibrated (t1-main), for reference | 72.48 | 80.56 | 448 |
| RL config before: live16402b (a7de3e93) + base py, crown pins Fireball,Poison dropped | 50.76 | 65.14 | 423 |
| **RL config after: live16402 overlay of the ported data + ported py** | **67.61** | **72.63** | **441** |

- **The port is exact.** On all 577 fixtures, every per-fixture result file from the ported engine equals the one from
  calibrated `src/clasher` (`simfid-20261020/t1-main`). The only field that differs is the wall-clock `sim_seconds`.
  There is no residual difference to explain. The B1/B2/C1 card work changes no C56 fixture: the base engine-cards
  run also reproduces BATCH1's `baseL` exactly (train 50.72 / 64.97 / 381).
- **Python↔Rust digest parity**, engine-cards py vs engine-cards native: **429 → 574/577**. No fixture is lost. The 3
  remaining are `…0795`, `…1157` and `…1226`, the same three that BATCH2 §1 and MERGE-TESTFIX list as dating from
  before the calibration.
- **Tests:** the 71 calibration and engine-scope tests pass against engine-cards/py (50 of them fail on the base).
  engine-cards' own suite has the same failure list on base and port (19 failed + 9 errors, all pre-existing). bot/cards
  and bot/fullpool pass: 360 on both.
- **RL config (16.402 overlay):** +16.85 pp ≤¼ and +7.49 pp HP exact over the current RL runtime's engine. It scores
  below the 15.535 number because the overlay moves card stats to 16.402 (Ice Golem and Ghost max HP, among others), and
  those no longer match 15.535 recordings. That loss is intended (§5).
- **C56 behaviour changes on purpose.** The engine-cards README said "C56 behaviour must stay bit-identical", meaning to
  r1. The calibration's purpose is to change C56 behaviour to the native-measured one, so the pinned expectations moved
  with it, as in MERGE-TESTFIX. The README now names the calibrated `src/clasher` as the reference.

Work dir: 127x05 `/mpac/sdicks02/jobs/clasher/simfid-20261020/port/` (`snap/`, `runs/`, `par/`, `l16/`, `troot/`, and
scripts `snap.sh`, `t1.sh`, `parity.sh`, `parsum.py`, `build_native.sh`, `testroot.sh`, `run_ectests.sh`, `jdiff.py`).
Each run used a frozen copy of the tree (`snap/<name>`), never the live worktree.

## 1. How the port was done

- For every Python file the calibration touched, the pre-calibration `src/clasher` (c7be66486^) is byte-identical to
  r1 (5ae7d16e8), and r1 is engine-cards/py's documented base. engine-cards' `gamedata.json` is byte-identical to
  c7be66486^'s root `gamedata.json` (sha1 a990618f).
- So each file was merged three-way: base = c7be66486^, ours = engine-cards, theirs = c7be66486 (`git merge-file`).
  Each merged hunk was then read against the engine-cards code around it. Rust used the same three-way merge (base =
  `engine-rs` at c7be66486^).
- Clean merges: `balance.py`, `battle.py`, `entities.py`, `cards/{goblin_hut,miner,royal_ghost}.py`, `pathfinding.py`,
  `mechanics/shared/spawner.py`, `astar.rs`, `c56.rs`, `spawn_snapshot.py`, `test_stage4_spawners.py`.
- Conflicts resolved by hand: `formations.py`, `unit_traits.py`, `cards/firecracker.py`, `ordinary_combat_clock.py`,
  `lib.rs`, `projectiles.rs`, `scope.rs`, `spawn.rs` (5 hunks) and `differential.py` (2 hunks). The table below gives
  each resolution.
- The gamedata diff applied cleanly. The result is byte-identical to the calibrated root `gamedata.json` (sha256 9a70da5a…).
- The native was built with the local toolchain (`/mpac/sdicks02/scratch/real-level-planning-20261020/toolchain`,
  cargo 1.99.1, offline registry `/mpac/sdicks02/tools/cargo`), one cargo job, nice 15, features
  `extension-module,gil-release`. Outputs: `port/native-base` (sha256 b43f1241…) and `port/native-port1` (02494efa…).
  Both builds are from this compiler, so neither is byte-identical to the 1.97.1 runtime build.

## 2. Rule by rule

"Ported" means the calibrated code went in unchanged. "Adapted" means it was merged with card-batch code on the same lines; the reason is
given. Data rules reach the native through `differential.config()` and need no Rust change.

| # | rule (source) | where | status |
|---|---|---|---|
| B1 §1 | Spirit HP 90 → 84, 5 paths | gamedata | ported (data) |
| B1 §2 | lane-2 mirror for 5-, 6- and 15-slot rings | `formations.py` `lane_flip_x`; `differential.py` `mirror_x` | **adapted.** `{4,5,6,15}` on path 2 is ORed with B1's wide-line rule (`summon_width` and ≥5, ≠7). `mirror_x` keeps B1's rider-mount and explicit-member exclusions and its `line_search`. In the full pool this also mirrors Barbarians (5) on path 2, which agrees with RoyaleSim (`formation.rs`: ring counts 5, 6 and 8+ mirror on the right lane). The 8-slot event cards (RoyalRecruits_Chess, SkeletonWarriors_SpookyChess) keep world order, as in the calibration (unmeasured) |
| B1 §3 | Goblinstein 1+1 formation | `formations.py` | ported. Rust gets it from the lane-1 template plus `mirror_x` |
| B1 §4a | FirespiritHut `spawnStartTime` 3050 → 1000 | `balance.py` `_furnace_entry` | ported |
| B1 §4b | GoblinHut first delay 100 ms, idle clock runs capped, wake range + hut radius | `goblin_hut.py`; `spawn.rs` | Python ported. **Rust adapted:** the wake scan keeps engine-cards' own target filter (`!absent()`, `lock_after()`, which replaced the stagger/stealth terms) and adds the hut-radius term, the nearest-target scan and the idle clock |
| B1 §5a | Miner skips the symmetric deploy snap | `battle.py`; `differential.py` `skip_deploy_snap` | ported. Miner is still the only troop with `can_deploy_on_enemy_side` in the full pool |
| B1 §5b/5d | Miner underground grid route and tunnel-end rule | `pathfinding.py`, `miner.py`; `astar.rs` (negative cost = blocked), `c56.rs` `spawn_path_*`, `lib.rs` `tunnel_path`; `differential.py` export | ported. In the full pool only Miner carries `UndergroundDeployment`; MightyMiner's ability tunnel stays straight, as in the calibration |
| B1 §5c | Miner targetable on arrival | `miner.py`; `c56.rs` `tunnel_move`, `lib.rs` deploy-end snap | ported |
| B2 §1 | Rust: discarded-hit cooldown (`discard_keeps_load`), building retarget reset, building preload on `acquired_from_idle`, Tesla hide clock at movement scale, IceGolemite config alias | `lib.rs`; `differential.py` | ported. `discard_keeps_load` is exported next to engine-cards' `ordinary=supported(carrier)` (the C1 Spirit-carrier change is kept) |
| B2 §2 | Barbarian HP 270 → 280, 6 non-evolved paths | gamedata | ported (data) |
| B2 §3 | Royal Ghost: grid route at water cost 7; ground collision body; push-back land-recovery exemption; re-hide 2000 ms after walking resumes | `pathfinding.py`, `unit_traits.py`, `entities.py`, `royal_ghost.py`; `lib.rs` `prepare_route`, deploy water clip, push clamp; `scope.rs` `collision_air`; `c56.rs` `ghost_tick`; `differential.py` `ghost_open` | **adapted.** `uses_air_collision_plane` and `collision_air` drop hover but keep B2's Vines-grounded flier on the air plane. In the full pool BattleHealer also hovers and inherits the route and ground-body rules. RoyaleSim agrees: Battle Healer and Royal Ghost are ground walkers that only price water at the JumpEnabled cost, measured on 15.535 (`HoveringWaterRule::PricedWaterNoHop`, `card.rs` `hovering`) |
| B2 §4 | side-1 back-row bound y ≤ 31.0 while side 0's princess on that half stands | `battle.py`; `lib.rs` `apply_action` | Python ported; every formation path (including B1's `_spawn_explicit_members` and the Royal Recruits line) goes through `_spawn_unit_at_position`, where the bound applies. **Rust adapted:** the bound is computed before B1's `line_centre` block, from the same anchor Python uses (`position` before the line centre) |
| B2 §5a | GoblinHut spear-goblin aim (nearest enemy, ±20°, facing state) | `goblin_hut.py`, `spawner.py` `_radial_spawn_basis`; `spawn.rs` State `facing`/`target`, `hut_aim`; `spawn_snapshot.py` | **adapted.** `production_child` keeps C1's `Option<usize>` return and `production_first_update` plumbing, with the aim as an extra argument |
| B2 §5b | FirespiritHut 1500 straight ahead | – | not applicable: rejected and reverted in the calibration |
| B2 §5c | Goblinstein doctor damage 36 → 53 | gamedata | ported (data) |
| B2 §7A | Rascals `summonDeployDelay` 100 | gamedata | ported (data) |
| B2 §7B | Firecracker recoil on the ordinary clock; recoil resets the hit on movement | `ordinary_combat_clock.supported`, `firecracker.py`; `projectiles.rs` `recoil` | **adapted.** C1 had already moved Sparky (LoadFirstHit plus AttackRecoil) onto the ordinary clock, with an immediate `stop_hit` on an armed recoil. `supported` now admits every AttackRecoil holder. `reset_hit_on_movement` (Rust `push_reset`) is set only when the holder is not LoadFirstHit (Rust: `clock.refund == 0`). Firecracker gets the calibrated behaviour and Sparky keeps C1's. The calibration measured Firecracker only |
| B2 §9a | Wall Breakers damage 137 → 110 | gamedata | ported (data) |
| B2 §9b | Miner emergence starts on the arrival tick | `miner.py`; `lib.rs` −0.05 s | ported |
| B2 §9c | Poison crown pulse 21 → 22 | `balance.py` `TOURNAMENT_SPELL_OVERRIDES` | ported. The RL runtime drops this pin (see §5) |
| B2 §9d | projectile-spawned troops keep their full deploy on the spawn tick | `entities.py` `_defer_projectile_spawn_deploy` in `SpawnProjectile` and `RollingProjectile` | ported. Rust gets it through the exported templates. In engine-cards these two classes are still the only projectile paths that spawn troops; riders, death spawns and spell spawns are not projectile impacts |
| held | MightyMiner stage-1 damage 16 → 17 | – | not applicable: not applied in the calibration |
| tests | `tests/test_calibration_batch*.py`, `test_scope_engine_cards.py` (calibrated version) | `engine-cards/py/tests/` | new: a conftest that puts `engine-cards/py/src` first and points CLASHER_ROOT at engine-cards' gamedata, plus one re-export module per test file |
| tests | MERGE-TESTFIX `test_stage4_b2.py` (two modes), calibrated `test_stage4_spawners.py` | `engine-cards/` | ported. The engine-cards copies were the pre-calibration files and are now byte-identical to main's |

## 3. T1 before/after (r1 data → ported data)

Base = `runs/base` (engine-cards/py and data at 3326d2d2b). Port = `runs/port1` (this branch). The harness is
`bot/simfid/t1.sh` with 30 workers and engine `clasher`, `--issue-offset -1`, seeded RNG. Comparisons use
`bot.fidelity.compare_runs`. As in BATCH2, decisions use train; validation is reported once.

| split | view | no-tower ≤¼ tile | no-tower HP exact | paired ≤¼ (better/worse) | crown-tower HP exact | winner agrees | gate (≥8k cards) |
|---|---|---|---|---|---|---|---|
| train (513) | standard | 50.72 → **72.26** | 64.97 → **80.51** | +20.11 pp [+18.77, +21.44] (481/24) | 67.77 → 81.97 | 381 → 400 | ACCEPT; worst card Wizard +1.01 |
| | live | 55.31 → **75.52** | 70.53 → **83.84** | +19.46 pp [+18.27, +20.63] (489/17) | | | ACCEPT; worst Xbow +0.47 |
| validation (64) | standard | 57.64 → **74.48** | 66.79 → **81.08** | +16.51 pp [+12.54, +20.42] (56/6) | 68.46 → 83.00 | 45 → 48 | strict REJECT on BombTower −10.0; LOO ACCEPT |
| | live | 60.19 → **77.93** | 69.62 → **84.54** | +17.32 pp [+14.00, +20.48] (60/2) | | | ACCEPT; worst Tesla +2.92 |
| all (577) | standard | 51.39 → **72.48** | 65.15 → **80.56** | +19.71 pp [+18.54, +20.97] (537/30) | 67.84 → 82.08 | 426 → 448 | ACCEPT; worst InfernoTower +1.03 |
| | live | 55.80 → **75.76** | 70.44 → **83.91** | +19.22 pp [+18.17, +20.38] (549/19) | | | ACCEPT; worst Xbow +0.45 |

- Every number equals BATCH2's base → batch 2 numbers (`baseL` → `c12-spawn`) to two decimals. The reason is the
  per-fixture identity above: engine-cards' base equals `baseL`, and the port equals calibrated `src/clasher`.
- No card with ≥8k unit-ticks loses ground against the engine-cards baseline, train or all, in either view. Validation
  BombTower −10.0 pp (standard only) is the small-sample case BATCH1 reported (−8.4 there). It passes LOO, and in the
  live view no card goes below −1 pp. `src/clasher` gives the identical per-fixture result.

### Per card, all 577 fixtures (≥8k unit-ticks, standard view)

| card | unit-ticks (port) | ≤¼ base | **≤¼ port** | Δ | HP exact base | **HP exact port** | Δ |
|---|---:|---:|---:|---:|---:|---:|---:|
| Tower | 3375170 | 98.1 | **99.0** | +0.9 | 67.8 | **82.1** | +14.2 |
| SkeletonArmy | 621671 | 31.3 | **65.0** | +33.8 | 76.5 | **85.4** | +8.9 |
| GoblinGang | 375574 | 37.4 | **67.7** | +30.2 | 69.3 | **81.9** | +12.7 |
| Bats | 294560 | 35.5 | **73.2** | +37.7 | 75.3 | **87.2** | +11.9 |
| Goblins | 255831 | 58.9 | **73.4** | +14.5 | 73.4 | **83.6** | +10.2 |
| Minions | 236748 | 58.5 | **73.5** | +15.0 | 76.4 | **85.1** | +8.7 |
| GoblinHut | 193459 | 30.3 | **50.5** | +20.1 | 37.2 | **61.6** | +24.4 |
| Archers | 178296 | 58.6 | **73.7** | +15.1 | 73.3 | **83.9** | +10.6 |
| Skeletons | 178619 | 64.1 | **76.9** | +12.8 | 78.7 | **86.4** | +7.7 |
| Princess | 143908 | 54.0 | **69.2** | +15.2 | 74.5 | **82.9** | +8.4 |
| FirespiritHut | 124529 | 23.0 | **49.7** | +26.7 | 30.0 | **66.1** | +36.1 |
| Wallbreakers | 127929 | 68.2 | **81.3** | +13.1 | 72.8 | **83.3** | +10.5 |
| Ghost | 123082 | 21.2 | **64.9** | +43.7 | 53.0 | **71.5** | +18.5 |
| Cannon | 123670 | 84.7 | **91.5** | +6.8 | 71.6 | **84.6** | +13.0 |
| Knight | 112106 | 59.2 | **74.3** | +15.1 | 60.1 | **74.4** | +14.2 |
| Firecracker | 109624 | 36.6 | **59.7** | +23.1 | 66.7 | **78.5** | +11.8 |
| BarbLog | 107095 | 62.2 | **76.1** | +13.9 | 0.0 | **79.5** | +79.5 |
| IceGolem | 105103 | 65.8 | **83.0** | +17.2 | 62.0 | **79.3** | +17.3 |
| Berserker | 105386 | 59.6 | **73.8** | +14.1 | 64.2 | **77.1** | +12.9 |
| BombTower | 102374 | 84.0 | **89.4** | +5.4 | 67.1 | **78.5** | +11.4 |
| RoyalDelivery | 93437 | 71.0 | **80.3** | +9.3 | 81.3 | **86.6** | +5.3 |
| MinionHorde | 87601 | 43.5 | **70.6** | +27.1 | 73.8 | **86.4** | +12.5 |
| Tesla | 88640 | 89.8 | **93.8** | +3.9 | 75.4 | **83.6** | +8.2 |
| BlowdartGoblin | 81015 | 60.6 | **74.1** | +13.5 | 74.2 | **82.0** | +7.8 |
| Miner | 59402 | 47.6 | **85.4** | +37.8 | 33.7 | **85.8** | +52.1 |
| RoyalHogs | 71438 | 75.9 | **81.7** | +5.8 | 76.0 | **81.5** | +5.5 |
| GoblinBarrel | 67748 | 71.4 | **80.4** | +9.0 | 79.2 | **86.2** | +7.0 |
| Goblinstein | 66652 | 9.8 | **79.6** | +69.7 | 50.4 | **78.9** | +28.5 |
| BabyDragon | 68866 | 56.2 | **68.7** | +12.6 | 63.3 | **74.2** | +11.0 |
| Valkyrie | 65455 | 61.0 | **70.2** | +9.2 | 59.2 | **67.4** | +8.2 |
| Musketeer | 62199 | 56.8 | **74.3** | +17.5 | 66.1 | **78.2** | +12.1 |
| Rascals | 60951 | 42.0 | **64.0** | +22.0 | 64.1 | **73.6** | +9.5 |
| DarkPrince | 54168 | 54.7 | **72.0** | +17.3 | 62.1 | **75.1** | +13.0 |
| MightyMiner | 46740 | 54.3 | **63.8** | +9.5 | 47.0 | **57.9** | +10.9 |
| ElectroSpirit | 46573 | 71.9 | **81.1** | +9.3 | 0.0 | **85.9** | +85.9 |
| HogRider | 43615 | 70.4 | **83.4** | +13.0 | 64.2 | **77.0** | +12.7 |
| FireSpirits | 43090 | 69.3 | **77.8** | +8.5 | 0.0 | **82.4** | +82.4 |
| IceSpirit | 41805 | 71.5 | **82.3** | +10.8 | 76.8 | **85.6** | +8.8 |
| InfernoTower | 42638 | 91.2 | **92.2** | +1.0 | 70.6 | **78.3** | +7.7 |
| MiniPekka | 39091 | 58.8 | **75.7** | +16.9 | 57.6 | **75.3** | +17.7 |
| Giant | 32772 | 83.9 | **89.1** | +5.2 | 69.5 | **77.3** | +7.7 |
| Balloon | 28869 | 85.1 | **92.9** | +7.7 | 78.0 | **88.7** | +10.7 |
| Wizard | 25275 | 59.5 | **62.9** | +3.4 | 69.4 | **70.0** | +0.6 |
| Golem | 21049 | 73.7 | **85.9** | +12.2 | 61.8 | **76.9** | +15.2 |
| Prince | 19605 | 53.2 | **68.6** | +15.4 | 48.6 | **65.1** | +16.5 |
| Xbow | 17461 | 91.5 | **92.8** | +1.3 | 76.6 | **80.9** | +4.3 |
| ArcherQueen | 16467 | 54.8 | **68.8** | +14.1 | 62.8 | **73.8** | +11.0 |
| AngryBarbarians | 9569 | 58.4 | **66.2** | +7.8 | 51.0 | **60.2** | +9.2 |

## 4. Python↔Rust parity (engine-cards py vs engine-cards native)

`bot.fidelity.rs_parity` over train and validation runs with `PYTHONPATH=<engine-cards glue + .so>:<engine-cards/py/src>:<repo>`
and CLASHER_ROOT set to the snapshot's gamedata (`port/parity.sh`, `parsum.py`).

| engine pair | full-length digest parity (577) | first-mismatch classes |
|---|---|---|
| base py + base native (b43f1241) | 429 (train 379, val 50) | IceGolemite 139 (+2 Firecracker/IceGolemite, +1 DeliveryRecruit/IceGolemite), Princess, Projectile, Tesla, Firecracker/Projectile, RoyalHogs, SpearGoblin |
| **ported py + ported native (02494efa)** | **574** (train 510, val 64) | Projectile `…0795`, Ghost `…1157`, RoyalHogs `…1226` |

- 145 fixtures go from mismatch to parity. None goes the other way.
- The base's IceGolemite class is the harness naming artifact BATCH2 §1 fixed in `differential.py`. It is fixed here too.
- The pre-port Rust gaps behind Princess/Tesla/Firecracker (discarded-hit cooldown, Inferno retarget, Tesla hide clock)
  are fixed by the ported §1 Rust changes.
- The 3 remaining fixtures are the ones BATCH2 and MERGE-TESTFIX trace to before the calibration.

## 5. RL config: live16402 overlay

**Reproducing the live16402b gamedata.** The RL runtime root `live16402b-r3` has gamedata sha256 `a7de3e93…`. Its
`LIVE16402-RECEIPT.json` names the inputs:
- base `r1-cards2-dev/gamedata.json` = 892fbfa0…, which is this branch's base engine-cards/py/gamedata.json;
- RoyaleSim `cards-160402017-20261006.json` (babaa3d1…) and `cards-15.535.json` (c68d6c01…), found with the same sha256
  in `/mpac/sdicks02/tmp/bot-upstream/RoyaleSim/data/derived/`;
- `--calibration` = 9a70da5a…, the calibrated root `gamedata.json`.

The overlay at HEAD (`bot/cards/balance_overlay.py`, version 2) gives df93121d…. The only differences are 6 DarkMagic
(Void) laser-tier values and `meta.version` 1 → 2. They come from release-d's Void pass (abea8cb75), which postdates
live16402b. The overlay as of **0874da215** (version 1; `git archive` of `bot/` and `reports/cards/{stats,tools}`)
reproduces **a7de3e93 byte for byte**. The before/after comparison therefore uses version 1. The ported data was also
run through version 2 (476f17cf…), and the result is identical on all 577 T1 fixtures; Void is not in the corpus.

**The calibration's data rules were already partly in the RL runtime.** The overlay takes the calibrated gamedata as
an input and writes a calibration value wherever RoyaleSim 15.535 == 16.402. Building the overlay from the ported data
(1303eb29…, version 1) instead of the base data changes only these fields from a7de3e93:

| field | live16402b (a7de3e93) | from ported data |
|---|---|---|
| Rascals `summonDeployDelay` (spells[53]) | absent | **100** |
| FirespiritHut evolution's FireSpirits HP (2 paths, spells[111] `evolvedSpellsData`) | 90 | **84** |
| BarbarianLauncher Barbarian HP (spells[112]) | 270 | **280** |
| meta: canonicalization note, overlay `input_sha256` | | |

Which calibration data rules survive the overlay, and whether that is right for 16.x (RoyaleSim 16.402 is the
reference there; T1 is 15.535):

| rule | in live16402b | after the port | RoyaleSim 15.535 / 16.402 | correct for 16.x? |
|---|---|---|---|---|
| Spirit HP 84 (Fire, Electro, hut spawns) | 84 on the RS-covered paths ("16.402 wins") | 84 everywhere, including the evo hut | 85 / 84 | yes. 16.402 says 84. The evo hut spawns the same FireSpirits character |
| Barbarian HP 280 | 280 on 5 paths, 270 on BarbarianLauncher | 280 on all 6 | 280 / 280 | yes. The launcher spawns the same Barbarian (data global id 34000009), which the overlay missed |
| Goblinstein doctor 53 | 53 | 53 | 53 / 53 | yes |
| Rascals deploy stagger 100 ms | **dropped** ("keep-calibration-unconfirmed": RoyaleSim has no `summon_deploy_delay_ms`) | kept | `summon_deploy_delay_second_ms` = 100 in both | yes. RoyaleSim carries the stagger as SummonDeployDelaySecond (girl j waits (j+1) × 100 ms), which is the native 20/22/24 measured in BATCH2 §7A. The overlay looked only at the primary field |
| Wall Breakers 110 | 118 | 118 (overlay overrides 110) | 110 / 118 | yes. 16.402 changed it; 110 is the 15.535 value |
| Poison crown pulse 22 (code, `balance.py`) | the pin is dropped | dropped | – | yes. The runtime pin `tournament_crown_from_gamedata=('Fireball','Poison')` computes crown damage from the 16.402 crown percent; 22 is the 15.535 level-11 value |

All code rules (formations, huts, Miner, Ghost, back edge, Firecracker, projectile spawns, Rust parity fixes) are
behaviour, not stats. The overlay does not touch them, so they carry into the RL config as they are.

**T1 in the RL config** (`SIMFID_CROWN_FROM_GAMEDATA=Fireball,Poison`). Before = base py + a7de3e93. It is identical
per fixture to the parent's run of the read-only RL runtime copy (`simfid-20261020/t1-fprt`: 0/577 differ). After =
ported py + the version-1 overlay of the ported data.

| split | no-tower ≤¼ tile | no-tower HP exact | paired ≤¼ (better/worse) | crown-tower HP exact | winner agrees | worst ≥8k card |
|---|---|---|---|---|---|---|
| train | 50.30 → **67.29** | 65.03 → **72.39** | +16.77 pp [+15.44, +18.01] (463/35) | 67.34 → 73.73 | 380 → 393 | Xbow −0.21 (gate ACCEPT) |
| validation | 55.06 → **70.54** | 66.20 → **74.86** | +14.85 pp [+10.86, +18.85] (54/8) | 67.11 → 74.02 | 43 → 48 | Cannon +0.16 |
| all | 50.76 → **67.61** | 65.14 → **72.63** | +16.55 pp [+15.37, +17.81] (517/43) | 67.31 → 73.76 | 423 → 441 | InfernoTower +0.38 |

The RL config scores below the 15.535 run (72.48 / 80.56) because of the overlay, not the port. Ported py with the
overlay against ported py with r1 data, all 577: ≤¼ −4.87 and HP exact −7.93. The losses are on cards whose 16.402
stats differ from 15.535: HP exact IceGolem 79.3 → 0.0, Ghost 71.5 → 0.0, Goblinstein −32.9, Giant −13.6, Golem −12.8,
MiniPekka −12.2, and so on. T1 scores against 15.535 recordings, so a 16.x stat costs HP exact by construction.

## 6. Tests

New: `engine-cards/py/tests/` (run as its own session: `python -m pytest -q engine-cards/py/tests`).

| suite | base 3326d2d2b | this branch |
|---|---|---|
| `engine-cards/py/tests` (calibration batches 1+2: 7 files, plus `test_scope_engine_cards.py`) against engine-cards/py | 21 passed, **50 failed** (every calibration assertion) | **71 passed** |
| engine-cards suite: `pytest engine-rs/` in a root whose `engine-rs` is engine-cards with its native (`troot/`, `run_ectests.sh`) | 116 passed, 19 failed, 9 errors, 143 subtests | same 19 failed + 9 errors (identical list), **155 subtests** (the two-mode B2 tests) |
| `bot/cards/test_{balance_overlay,build_runtime,proxy_table}.py`, `bot/fullpool/test_fullpool.py` | 360 passed | 360 passed |

**Pre-existing failures in the engine-cards suite** (identical on base and port; not owned here):
- errors, missing data files: `test_canonical_data`, `test_stage3`, `test_stage3_backend`, `_backend_edges`,
  `_corpus_views`, `_finalize`, `_qualified_backend`, `_record_roots`, `_rollouts`;
- failures: `test_stage2` (10), `test_stage3_regressions` (2), `test_stage5_search` (1), `test_stage5b_deadline` (4),
  and `test_stage4_b2::{test_air_knockback_does_not_recover_ground_at_river,
  test_stun_resets_special_clock_but_preserves_frozen_target_observation}`. MERGE-TESTFIX lists these 2 as needing
  `engine-speed/stage4` artifacts that are not in the tree.
- The counts (19 failed, 9 errors) match MERGE-TESTFIX's `engine-rs/` baseline.

**Ad hoc, not committed:** the other `tests/` files the calibration or MERGE-TESTFIX edited (`test_enabled_troop_interactions`,
`_spell_interactions`, `_reachable_children`, `test_torch_simple_spawn_{blueprints,runtime}`, `test_stat_scaling`,
`test_spell_levels`, `test_torch_simple_periodic_areas`) were run through the same re-export wrapper against engine-cards/py.
- Base: 123 failed. Port: 103 failed, **0 new**, 20 fixed.
- The 103 fail on both because engine-cards has drifted from main's tests (B-batch death-spawn and dash changes, for
  example).
- 4 of them are tests the calibration edited, but each fails on an assertion the calibration did not touch:
  - `test_battle_ram_connect…` fails at the barbarian deploy delay, before the edited HP line;
  - `test_graveyard_first_skeleton…`;
  - `test_reachable_children…` (a damage value);
  - `test_compiler_materializes_internal_rows…`.

## 7. Open

- No Mac or live check: the RL-config number is T1 against 15.535 recordings only. No runtime root was built or
  changed; the RL jobs still run live16402b-r3. Building a runtime from this branch is the parent's call
  (`bot/cards/build_runtime.py` + `build_live16402.py`).
- The overlay generator at HEAD (version 2) and at 0874da215 (version 1) give the same T1 result from the ported data.
- The full-pool rule extensions are checked against RoyaleSim's rules, not against native recordings:
  - BattleHealer inherits the Ghost route and ground body;
  - Barbarians get the lane-2 5-ring mirror;
  - the side-1 back edge applies to new ground cards;
  - projectile spawns keep their full deploy.

  Sparky deliberately keeps C1's recoil behaviour.
- The 3 parity mismatches from before the calibration remain.
