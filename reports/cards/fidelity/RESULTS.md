# Card fidelity results

Completed 66/66 cards: {"PASS":4,"DIFF":62,"NOT-IN-ROYALESIM":0,"HARNESS-GAP":0}.

Measured on 127x08 using level-11 cards, the read-only r1 Python runtime, and the installed RoyaleSim (MIT) binding. All pairs below are **ours / RoyaleSim**. Event ticks are relative to command tick 100; one tick = 50 ms. Both seats share x/y coordinates: blue defends low y, left princess (3.5,25.5) belongs to red. Positions from RoyaleSim are divided by SUBTILE_PER_MILLITILE and 1000.

Primary baseline explicitly selects the full client-16.402 table, `cards-160402017-20261006.1`, through the existing RoyaleSim adapter and its shipped 16.402 calibration. A complete secondary run uses the adapter’s default (`cards-15535.1` plus measured CLIENT16402_VALUES corrections). The default has not switched tables upstream; retaining both avoids silently treating the older table as current card data. Build provenance: `ffe0d27de00cd2cc1121e573eba8796bfb8f5f6a`, clean.

Each normal troop has a 30-second bridge run and 30-second Knight/Minions fights. Buildings have 75-second idle/lifetime/spawn runs plus 30-second Hog Rider and Giant defenses (Collector has a longer lifetime/production run). Spells have a tower cast, a fixed Knight/Skeleton Army/Minions cluster, and a friendly Giant support cast. No champion abilities, evolutions, or hero forms are pressed. Scripts, fixed tiles, exact events, hashes and deployment interventions are in `scenarios.py` and `results.jsonl`.

PASS means the measured scenarios agree: HP/damage within 1, impact/birth/ready/death times within 1 tick, observed early movement speed within 2%. It is not exhaustive validation of unexercised abilities or special mechanics. Lethal damage is capped at remaining HP; enemy damage events can include our tower fire. DIFF attribution below distinguishes a directly measured stat mismatch from a likely mechanic source. Building decay is excluded from enemy-hit comparison. Spell boundary and status-duration probes are detailed below. All source paths in the cause column refer to r1 on 127x08, not an edited implementation.

| Card | Verdict | Key measured numbers (ours / RoyaleSim) | Likely cause; responsible r1 source function |
|---|---|---|---|
| GoblinCage | DIFF | HP [780,1080]/[780,1121]; ATK [0,337]/[0,337]; ready [20,420]/[20,430]; tower@10/20/30 [0,0,337]/[0,0,337]; hog GoblinBrawler[0].max_hp 1080/1121 | Stat + mechanic: Brawler HP 1080/1121; after cage death it acts immediately/10 ticks later. Cage HP 780 and idle death tick 420 agree. `src/clasher/factory/dynamic_factory.py::troop_from_character_data`; `src/clasher/mechanics/shared/death_effects.py::DeathSpawn.on_death`. |
| SpearGoblins | DIFF | HP [133,133,133]/[133,133,133]; ATK [81,81,81]/[81,81,81]; ready [20,22,24]/[20,22,24]; tower@10/20/30 [324,324,324]/[405,405,405]; knight enemy_hits[3].tick 71/69 | Likely attack/retarget clock: HP 133, hit 81 and deploy stagger agree; later impacts differ by 2 ticks and bridge tower damage is 324/405. `src/clasher/entities.py::Troop.update_combat_component`; `src/clasher/ordinary_combat_clock.py::advance`. |
| Bomber | DIFF | HP [304]/[304]; ATK [225]/[212]; ready [20]/[20]; tower@10/20/30 [225,225,225]/[212,212,212]; knight Bomber[0].configured_damage 225/212 | Stat: instantiated projectile damage 225/212, confirmed on both Knight and tower. `src/clasher/card_types.py::CardStatsCompat.__init__` (projectile damage import); `src/clasher/factory/dynamic_factory.py::troop_from_character_data`. |
| Tombstone | DIFF | HP [529,81,81,81,81,81]/[529,81,81,81,81,81]; ATK [0,81,81,81,81,81]/[0,81,81,81,81,81]; ready [20,89,99,169,179,249]/[20,20,29,99,109,179]; tower@10/20/30 [0,0,0]/[0,0,0]; hog Skeleton.count 5/6 | Spawner mechanic: first Skeleton tick 89/20; subsequent wave clocks and total counts differ. Buildings are assigned a full-period first delay. `src/clasher/factory/mechanic_detector.py::detect_mechanics_from_data`; `src/clasher/mechanics/shared/spawner.py::PeriodicSpawner.on_object_tick`. |
| Barbarians | DIFF | HP [691,691,691,691,691]/[716,716,716,716,716]; ATK [192,192,192,192,192]/[192,192,192,192,192]; ready [20,22,24,26,28]/[20,22,24,26,28]; tower@10/20/30 [384,3244,4972]/[384,3244,4972]; knight Barbarian[0].max_hp 691/716 | Stat: each Barbarian HP 691/716; hit damage 192 and deploy ticks agree. `src/clasher/factory/card_factory.py::_create_troop_stats`; `src/clasher/card_types.py::CardStatsCompat.__init__` (feed/balance import). |
| BattleRam | DIFF | HP [967,691,691]/[967,716,716]; ATK [286,192,192]/[286,192,192]; ready [20,139,139]/[20,140,140]; tower@10/20/30 [1341,2685,2685]/[1341,2685,2685]; knight Barbarian[0].max_hp 691/716 | Child stat: spawned Barbarians have HP 691/716. Ram HP 967 and bridge impact agree; some child combat events drift 2 ticks. `src/clasher/factory/dynamic_factory.py::troop_from_character_data`; `src/clasher/mechanics/shared/death_effects.py::DeathSpawn.on_death`. |
| MegaMinion | PASS | HP [837]/[837]; ATK [312]/[312]; ready [20]/[20]; tower@10/20/30 [312,312,312]/[312,312,312] | Measured base-card scenarios agree: HP 837, attack 312, 1.2 tiles/s, deployment ready tick 20. No evolution/hero form tested. |
| BarbarianHut | DIFF | HP [1164,691,691,691,691,691]/[1164,716,716,716,716,716]; ATK [0,192,192,192,192,192]/[0,192,192,192,192,192]; ready [20,299,309,319,599,609]/[20,20,29,39,319,329]; tower@10/20/30 [0,0,960]/[0,1728,3052]; hog Barbarian.count 1/4 | Spawner + child stat: first Barbarian 299/20; first wave [299,309,319]/[20,29,39]; child HP 691/716. `src/clasher/factory/mechanic_detector.py::detect_mechanics_from_data`; `src/clasher/mechanics/shared/spawner.py::PeriodicSpawner.on_object_tick`. |
| Mortar | DIFF | HP [1369]/[1369]; ATK [266]/[266]; ready [70]/[70]; tower@10/20/30 [0,0,0]/[0,0,0]; hog tower_hits.count 2/3 | Likely missing minimum-range acquisition/shot rule: ours hits Hog for 266 at tick 97; reference has no corresponding shot. HP 1369 and 70-tick deployment agree. `src/clasher/entities.py::Building._update_active_combat`; `Building._retain_or_acquire_target`. |
| DartBarrell | DIFF | HP [614]/[614]; ATK [171]/[171]; ready [20]/[20]; tower@10/20/30 [684,684,684]/[684,684,684]; knight tower_hits.count 3/4 | Likely projectile launch/flight clock: bridge hit ticks [80,102,124,146]/[78,100,122,144], damage 171 agrees. `src/clasher/entities.py::Troop._create_projectile`; `Projectile.update`. |
| Witch | DIFF | HP [839,81,81,81,81,81]/[839,81,81,81,81,81]; ATK [135,81,81,81,81,81]/[135,81,81,81,81,81]; ready [20,39,40,41,42,182]/[20,39,39,39,39,179]; tower@10/20/30 [918,1620,1620]/[918,1620,1620]; knight Skeleton[2].birth 41/39 | Spawner mechanic: first Skeleton wave [39,40,41,42]/[39,39,39,39], next wave starts 182/179. The detector enforces a 50 ms minimum intra-wave interval. `src/clasher/factory/mechanic_detector.py::detect_mechanics_from_data`; `src/clasher/mechanics/shared/spawner.py::PeriodicSpawner.on_object_tick`. |
| Pekka | PASS | HP [3760]/[3760]; ATK [842]/[842]; ready [20]/[20]; tower@10/20/30 [0,3052,6420]/[0,3052,6420] | Measured base-card scenarios agree: HP 3760, attack 842, nominal 0.9 tiles/s, Knight hits at [36,72,108]. No evolution tested. |
| SkeletonWarriors | DIFF | HP [81,81,81]/[81,81,81]; ATK [117,117,117]/[117,117,117]; ready [20,22,24]/[20,22,24]; tower@10/20/30 [702,936,936]/[819,1053,1053]; knight SkeletonWarrior[0].observed_speed 1.6901/1.7889 | Likely formation/contact and attack approach: HP 81 and shield 256 agree; first Knight hit 30/33; bridge damage 936/1053. `src/clasher/battle.py::_spawn_swarm_troops`; `src/clasher/entities.py::Troop._move_towards_target`. |
| SkeletonDragons | DIFF | HP [560,560]/[560,560]; ATK [151,151]/[151,151]; ready [20,22]/[20,22]; tower@10/20/30 [755,906,906]/[755,906,906]; knight tower_hits[1].tick 247/245 | Likely projectile approach/retarget timing: identical HP 560, hit 151 and deployment; after the Knight fight tower impacts drift 2 ticks. `src/clasher/entities.py::Troop._create_projectile`; `Troop.update_combat_component`. |
| RoyalGiant | DIFF | HP [3164]/[3164]; ATK [307]/[307]; ready [20]/[20]; tower@10/20/30 [614,2456,3359]/[614,2456,3359]; knight RoyalGiant[0].configured_speed 45.0/52.0 | Speed stat: configured logic speed 45/52 (nominal 0.90/1.04 tiles/s); observed early motion 0.8944/1.0270; tower first hit 141/138. `src/clasher/gamedata_normalization.py::normalized_walking_speed`; `src/clasher/card_types.py::CardStatsCompat.__init__`. |
| ThreeMusketeers | DIFF | HP [100]/[906,906,906]; ATK [0]/[204,204,204]; ready [1]/[20,22,24]; tower@10/20/30 [0,0,0]/[2040,4276,6112]; knight ThreeMusketeer_Rework_Character_1.count 0/1 | Missing explicit summon-list mechanic: ours creates one 100-HP, zero-damage placeholder; reference creates three 883-HP units with 204 damage. `src/clasher/battle.py::_spawn_troop`; `src/clasher/gamedata_normalization.py::normalize_entry` (summonCharacters list not expanded). |
| RoyalRecruits | DIFF | HP [547,547,547,547,547,547]/[547,547,547,547,547,547]; ATK [133,133,133,133,133,133]/[133,133,133,133,133,133]; ready [20,20,20,20,20,20]/[20,22,24,26,28,30]; tower@10/20/30 [665,3318,5845]/[532,4116,5180]; knight Recruit[1].ready 20/22 | Formation/stagger mechanic: ours makes all six ready at tick 20; reference [20,22,24,26,28,30]. The custom line-spawn path omits member delay. `src/clasher/battle.py::_spawn_royal_recruits_line`. |
| GiantSkeleton | DIFF | HP [3361]/[3361]; ATK [276]/[276]; ready [20]/[20]; tower@10/20/30 [552,2484,3328]/[552,2484,3328]; knight tower_hits[7].tick 568/570 | Death-bomb timer: same HP 3361, hit 276, and death tick; bomb tower impact 273/275 against Minions and 568/570 against Knight. `src/clasher/mechanics/shared/death_effects.py::DeathSpawn.on_death`; `src/clasher/entities.py::TimedExplosive.update`. |
| BattleHealer | DIFF | HP [1717]/[1920]; ATK [148]/[268]; ready [20]/[20]; tower@10/20/30 [296,888,888]/[268,1340,1340]; knight BattleHealer[0].max_hp 1717/1920 | Stats: HP 1717/1920; instantiated attack 148/268. Healing interactions are not isolated by these probes. `src/clasher/factory/card_factory.py::_create_troop_stats`; `src/clasher/card_types.py::CardStatsCompat.__init__`. |
| Freeze | DIFF | tower@10/20/30 [37,37,37]/[38,38,38]; stationary damage 148/148; effect ticks 80/70; cluster tower_hits[0].tick 222/212 | Duration + area stats/geometry: center damage 148 agrees; freeze occupies 80/70 ticks. Knight at center distance 3.5 is missed/hit. `src/clasher/dynamic_spells.py::create_spell_from_json`; `src/clasher/entities.py::Entity.intersects_native_area`. |
| Snowball | DIFF | tower@10/20/30 [45,45,45]/[45,45,45]; stationary damage 179/179; effect ticks 60/60; cluster tower_hits[1].tick 187/185 | Area geometry + zero-vector knockback: center damage 179 and slow 60 ticks agree; distance 3.0 is missed/hit. At exact center ours pushes +y, reference -x. `src/clasher/dynamic_spells.py::create_spell_from_json`; `src/clasher/entities.py::Entity.intersects_native_area`; `Projectile._apply_knockback`. |
| Vines | DIFF | tower@10/20/30 [70,70,70]/[70,70,70]; stationary damage 306/306; effect ticks 40/40; cluster tower_hits.count 26/23 | Area selection geometry: center DoT 2 x 153 and 40-tick snare agree within 1 tick; distance 3.0 is missed/hit. `src/clasher/scope_spells.py::build_scope_spell`; `_enemy_characters_in_area`; `src/clasher/entities.py::Entity.intersects_native_area`. |
| SkeletonBalloon | DIFF | HP [532,81,81,81,81,81]/[532,81,81,81,81,81]; ATK [0,81,81,81,81,81]/[0,81,81,81,81,81]; ready [20,146,146,146,146,146]/[20,147,147,147,147,147]; tower@10/20/30 [955,1360,1360]/[1117,1684,1684]; knight tower_hits.count 22/26 | Likely death-release placement/deploy timing: child HP and count agree, some child ready ticks differ by 2 and tower outcomes diverge. `src/clasher/entities.py::TimedExplosive._spawn_death_units`; `src/clasher/mechanics/shared/death_effects.py::DeathSpawn.on_death`. |
| GoblinGiant | DIFF | HP [3110]/[3110,133,133,133,133]; ATK [176]/[176,81,81,81,81]; ready [20]/[20,20,20,565,565]; tower@10/20/30 [176,1408,2112]/[662,2866,3876]; knight GoblinGiant[0].configured_speed 60.0/69.0 | Speed + missing attached troop mechanic: configured speed 60/69 (1.20/1.38 tiles/s); ours lacks both 133-HP SpearGoblinGiant riders and their death releases. `src/clasher/factory/mechanic_detector.py::detect_mechanics_from_data`; `src/clasher/battle.py::_spawn_troop`. |
| GiantBuffer | DIFF | HP [2662]/[2816]; ATK [153]/[153]; ready [20]/[20]; tower@10/20/30 [306,1224,1530]/[306,1224,1683]; knight GiantBuffer[0].max_hp 2662/2816 | Stat: Rune Giant HP 2662/2816, hit 153 agrees. Enchantment is not isolated by the original three scenarios. `src/clasher/factory/card_factory.py::_create_troop_stats`; `src/clasher/card_types.py::CardStatsCompat.__init__`. |
| Hunter | DIFF | HP [885]/[885]; ATK [84]/[84]; ready [20]/[20]; tower@10/20/30 [0,0,0]/[840,840,840]; knight tower_hits.count 5/0 | Missing pellet weapon: first Knight volley is 84/840 damage, next at tick 82/78; ours does no bridge tower damage. `src/clasher/entities.py::Troop._create_projectile`; `src/clasher/factory/mechanic_detector.py::detect_mechanics_from_data` (multi-pellet weapon not registered). |
| MiniSparkys | DIFF | HP [529,529,529]/[529,529,529]; ATK [117,117,117]/[117,117,117]; ready [20,22,24]/[20,22,24]; tower@10/20/30 [585,1170,1170]/[585,1053,1053]; knight enemy_hits[3].tick 78/82 | Likely attack/stun retarget clock: HP 529, hit 117 and deploy stagger agree; later Knight impacts drift 2 ticks. `src/clasher/entities.py::Troop.update_combat_component`; `Projectile._apply_status_to_target`. |
| IceWizard | DIFF | HP [688]/[688]; ATK [89]/[89]; ready [20]/[21]; tower@10/20/30 [267,356,356]/[267,356,356]; knight enemy_hits.count 18/17 | Spawn-effect timing/coverage: Knight first damage at tick 20/34; ordinary body stats and alone run agree. `src/clasher/mechanics/shared/spawn_area.py::SpawnAreaEffect.on_spawn`; `src/clasher/entities.py::AreaEffect.update`. |
| LavaHound | DIFF | HP [3581,215,215,215,215,215]/[3581,215,215,215,215,215]; ATK [53,81,81,81,81,81]/[71,81,81,81,81,81]; ready [20,597,597,597,597,597]/[20,597,597,597,597,597]; tower@10/20/30 [53,477,901]/[71,568,994]; knight LavaHound[0].configured_damage 53/71 | Likely death-child retarget/formation mechanics: Hound and Pups HP/damage/count agree; Minions first damage tick 245/253. `src/clasher/mechanics/shared/death_effects.py::DeathSpawn.on_death`; `src/clasher/entities.py::Troop.update_combat_component`. |
| ZapMachine | DIFF | HP [1451]/[1451]; ATK [1331]/[1331]; ready [20]/[20]; tower@10/20/30 [1331,3052,3052]/[1331,3052,3052]; knight tower_hits.count 1/0 | Attack charge/load mechanic: first Knight hit tick 42/101 despite matching HP 1451 and damage 1331. `src/clasher/cards/sparky.py::SparkyChargeUp.on_tick`; `src/clasher/entities.py::Troop.update_combat_component`. |
| Bowler | DIFF | HP [2081]/[2081]; ATK [289]/[289]; ready [20]/[20]; tower@10/20/30 [289,1445,1445]/[289,1445,1445]; knight tower_hits.count 9/2 | Likely rolling-projectile collision/pushback mechanics: bridge-only run agrees; Knight defense causes a large outcome divergence. `src/clasher/entities.py::RollingProjectile._deal_rolling_damage`; `RollingProjectile._apply_knockback`. |
| RageBarbarian | DIFF | HP [1282]/[1282]; ATK [256]/[256]; ready [20]/[20]; tower@10/20/30 [1792,2358,2358]/[1792,2350,2350]; knight tower_hits[0].damage 54/46 | Full-table stat mismatch: death Rage tower hit 54/46, while the adapter's older table gives 54 and passes. `src/clasher/cards/lumberjack.py::LumberjackRage.on_attach`; `LumberjackRage.on_death` (nested impact payload import). |
| InfernoDragon | DIFF | HP [1295]/[1295]; ATK [35]/[35]; ready [20]/[20]; tower@10/20/30 [620,3052,3052]/[620,3052,3052]; minions enemy_hits[5].tick 73/83 | Likely channel reset/retarget mechanic: alone and Knight agree; Minions damage timings diverge by 10 ticks. `src/clasher/mechanics/shared/damage_ramp.py::DamageRamp.on_target_observed`; `_reset_lock`. |
| ElectroWizard | DIFF | HP [714]/[714]; ATK [117]/[117]; ready [20]/[21]; tower@10/20/30 [936,936,936]/[936,936,936]; knight enemy_hits.count 11/10 | Spawn-zap timing/coverage: Knight receives first damage tick 20/33; body stats agree. `src/clasher/cards/electro_wizard.py::ElectroWizardSpawnZap.on_spawn`; `src/clasher/entities.py::Entity.intersects_native_area`. |
| AxeMan | DIFF | HP [1280]/[1280]; ATK [179]/[179]; ready [20]/[20]; tower@10/20/30 [895,1432,1432]/[716,1074,1074]; knight enemy_hits.count 11/12 | Returning/piercing weapon mechanic: alone tower impacts [first same, second 139/129] and total impact count 8/6 differ with the same 179 damage. `src/clasher/entities.py::Projectile._update_piercing`; `Projectile._damage_piercing_targets_at`. |
| Assassin | DIFF | HP [906]/[906]; ATK [194]/[194]; ready [20]/[20]; tower@10/20/30 [1359,1553,1553]/[1359,1359,1359]; minions tower_hits[0].tick 174/91 | Likely dash/contact timing: alone death tick 221/206 and tower hit count 7/6; Knight fight agrees. `src/clasher/cards/bandit.py::BanditDash.on_tick`; `src/clasher/entities.py::Troop.update_combat_component`. |
| DarkWitch | DIFF | HP [906,81,81,81,81,81]/[906,81,81,81,81,81]; ATK [314,81,81,81,81,81]/[314,81,81,81,81,81]; ready [20,39,40,140,141,228]/[20,39,39,139,139,227]; tower@10/20/30 [952,1752,1752]/[952,1752,1752]; knight Bat[3].birth 141/139 | Spawner wave spacing: later Bat wave members drift at least 2 ticks; base stats match. Same enforced intra-wave minimum as Witch. `src/clasher/factory/mechanic_detector.py::detect_mechanics_from_data`; `src/clasher/mechanics/shared/spawner.py::PeriodicSpawner.on_object_tick`. |
| RamRider | DIFF | HP [1766]/[1766,593]; ATK [250]/[271,104]; ready [20]/[20,20]; tower@10/20/30 [1001,2001,2001]/[1084,2168,2168]; knight Ram[0].configured_damage 250/271 | Missing attached rider weapon: ours has only Ram (1766 HP); reference also has the untargetable 593-HP rider with 104 attack, affecting defense. `src/clasher/factory/mechanic_detector.py::detect_mechanics_from_data`; `src/clasher/battle.py::_spawn_troop`. |
| MovingCannon | DIFF | HP [1809]/[1809]; ATK [212]/[212]; ready [20]/[20]; tower@10/20/30 [1272,2968,2968]/[1272,2544,2544]; knight tower_hits.count 4/0 | Likely moving-to-broken-building transition mechanic: matching initial HP 1809/hit 212, but alone death 339/307 and Knight tower damage 848/0. `src/clasher/factory/mechanic_detector.py::detect_mechanics_from_data`; `src/clasher/entities.py::Troop.update_combat_component`. |
| MegaKnight | DIFF | HP [3993]/[3993]; ATK [268]/[268]; ready [20]/[20]; tower@10/20/30 [805,2413,3857]/[805,2413,3857]; knight tower_hits[1].tick 397/395 | Likely leap landing/attack handoff clock: same HP/hit; second alone tower impact 178/176 and subsequent hits remain 2 ticks late. `src/clasher/cards/mega_knight.py::MegaKnightSlam._update_landing`; `_finish_leap`. |
| Fisherman | DIFF | HP [870]/[870]; ATK [194]/[194]; ready [20]/[20]; tower@10/20/30 [0,0,0]/[582,582,582] | Hook-to-building/self-drag mechanic: ours deals 0 bridge tower damage; reference deals 582 by 10 seconds; Knight and Minions fights agree. `src/clasher/cards/fisherman.py::FishermanHook._find_hook_target`; `_advance_drag`. |
| EliteArcher | DIFF | HP [529]/[529]; ATK [143]/[135]; ready [20]/[20]; tower@10/20/30 [572,572,572]/[540,540,540]; knight EliteArcher[0].configured_damage 143/135 | Stat: Magic Archer hit 143/135, confirmed on towers. `src/clasher/card_types.py::CardStatsCompat.__init__`; `src/clasher/cards/magic_archer.py` (projectile payload import). |
| ElectroDragon | DIFF | HP [1049]/[1049]; ATK [192]/[192]; ready [20]/[20]; tower@10/20/30 [384,576,576]/[384,576,576]; minions enemy_hits[1].tick 35/39 | Chain travel clock: first bolt agrees but subsequent Minions impacts are [35,36]/[39,43]. `src/clasher/cards/electro_dragon.py::ElectroDragonChainLightning.on_attack_hit`; `src/clasher/entities.py::ChainLightning.update`. |
| ElixirGolem | DIFF | HP [1569,762,762,360,360]/[1569,762,762,360,360]; ATK [253,128,128,64,64]/[253,128,128,64,64]; ready [20,308,308,428,428]/[20,308,308,430,430]; tower@10/20/30 [0,2036,3244]/[0,2036,3244]; knight ElixirGolem4[0].birth 277/256 | Likely death-child geometry/retarget timing: all stage HP/damage and child counts agree; a second-stage death/Blob birth drifts 2 ticks alone, farther during fights. `src/clasher/mechanics/shared/death_effects.py::DeathSpawn.on_death`; `src/clasher/battle.py::_spawn_death_units`. |
| SkeletonKing | PASS | HP [2298]/[2298]; ATK [204]/[204]; ready [20]/[20]; tower@10/20/30 [408,1632,1632]/[408,1632,1632] | Measured base-card scenarios agree: HP 2298, attack 204, nominal 1.2 tiles/s. Soul/ability behavior not exercised. |
| GoldenKnight | DIFF | HP [1799]/[1799]; ATK [161]/[168]; ready [20]/[20]; tower@10/20/30 [483,1610,1610]/[504,1680,1680]; knight GoldenKnight[0].configured_damage 161/168 | Full-table stat: damage 161/168; the adapter's older table uses 161 and passes. `src/clasher/factory/card_factory.py::_create_troop_stats`; `src/clasher/card_types.py::CardStatsCompat.__init__`. Active ability not tested. |
| Monk | DIFF | HP [2214]/[2214]; ATK [140]/[140]; ready [20]/[20]; tower@10/20/30 [280,3052,3192]/[280,3052,3052]; knight tower_hits.count 5/0 | Likely missing three-hit sequence/pushback: matching 2214 HP and ordinary 140 attack; alone tower hit count 12/14, Knight outcome differs. `src/clasher/factory/mechanic_detector.py::detect_mechanics_from_data`; `src/clasher/entities.py::Troop._get_attack_damage`. |
| WitchMother | DIFF | HP [529]/[529]; ATK [133]/[133]; ready [20]/[20]; tower@10/20/30 [399,399,399]/[399,399,399]; knight enemy_hits[0].tick 31/28 | Weapon/curse mechanic: bridge and Knight initial impacts 3 ticks late; Minions fight yields no pig/one VoodooHog. `src/clasher/factory/mechanic_detector.py::detect_mechanics_from_data`; `src/clasher/entities.py::Projectile._damage_target` (curse conversion not registered). |
| ElectroGiant | DIFF | HP [3952]/[3952]; ATK [163]/[184]; ready [20]/[20]; tower@10/20/30 [0,815,1793]/[97,1793,3052]; knight ElectroGiant[0].configured_damage 163/184 | Missing retaliation mechanic: alone tower impacts 11/24 and first impact 221/193 despite matching body HP/damage. `src/clasher/entities.py::Entity.take_damage`; `src/clasher/factory/mechanic_detector.py::detect_mechanics_from_data`. |
| Phoenix | DIFF | HP [1052]/[1052,317]; ATK [217]/[217,0]; ready [20]/[20,220]; tower@10/20/30 [434,651,651]/[434,814,814]; knight PhoenixEgg.count 0/1 | Missing death/rebirth payload: no egg/reference 317-HP PhoenixEgg at tick 220, and no corresponding death nova tower hit. `src/clasher/factory/mechanic_detector.py::detect_mechanics_from_data`; `src/clasher/gamedata_normalization.py::normalize_entry`. |
| LittlePrince | DIFF | HP [698]/[698]; ATK [104]/[104]; ready [20]/[20]; tower@10/20/30 [416,416,416]/[520,520,520]; knight tower_hits.count 5/3 | Likely missing attack-speed ramp: initial HP 698/hit 104 agree; fourth bridge impact 177/165. `src/clasher/entities.py::Troop.update_combat_component`; `src/clasher/factory/mechanic_detector.py::detect_mechanics_from_data`. |
| GoblinDemolisher | DIFF | HP [1300]/[1300]; ATK [186]/[186]; ready [20]/[20]; tower@10/20/30 [744,1302,1302]/[558,962,962]; knight enemy_hits[4].tick 124/164 | Missing low-health sprint/detonation mechanic: body HP/hit agree; alone death 256/204 and tower hit count 7/4. `src/clasher/factory/mechanic_detector.py::detect_mechanics_from_data`; `src/clasher/entities.py::Troop.update_combat_component`. |
| GoblinMachine | DIFF | HP [2150]/[2265]; ATK [212]/[232]; ready [20]/[20]; tower@10/20/30 [424,1908,1908]/[464,2320,2320]; knight GoblinMachine[0].max_hp 2150/2265 | Stats + secondary weapon coverage: HP 2150/2265, ordinary attack 212/232. Rocket interactions need separate isolation. `src/clasher/factory/card_factory.py::_create_troop_stats`; `src/clasher/card_types.py::CardStatsCompat.__init__`; `src/clasher/factory/mechanic_detector.py::detect_mechanics_from_data`. |
| SuspiciousBush | DIFF | HP [81,304]/[81,337,337]; ATK [0,256]/[0,256,256]; ready [20,83]/[20,186,187]; tower@10/20/30 [0,0,0]/[0,1536,1536]; knight BushGoblin.count 1/2 | Death/action spawn + child stat: one/two BushGoblins; child HP 304/337 and damage 256 agrees. `src/clasher/gamedata_normalization.py::_attach_action_death_spawn`; `src/clasher/factory/mechanic_detector.py::detect_mechanics_from_data`; `src/clasher/factory/dynamic_factory.py::troop_from_character_data`. |
| BossBandit | DIFF | HP [2624]/[2624]; ATK [245]/[245]; ready [20]/[20]; tower@10/20/30 [1471,3788,4523]/[1716,3788,4523]; knight tower_hits.count 9/8 | Likely dash immunity/retarget mechanics: stats agree; Minions scenario death tick 391/222 and 18/9 tower impacts. `src/clasher/cards/bandit.py::BanditDash.on_tick`; `src/clasher/entities.py::Entity.take_damage`. Active ability not tested. |
| Ronin | DIFF | HP [1779]/[1779]; ATK [371]/[371]; ready [20]/[20]; tower@10/20/30 [1113,2968,2968]/[1484,2968,2968]; knight tower_hits.count 3/6 | Attack sequence/counter mechanic: tower hit period 28/26 ticks; Knight additionally receives a reference-only 404 hit. `src/clasher/entities.py::Troop.update_combat_component`; `src/clasher/factory/mechanic_detector.py::detect_mechanics_from_data`. |
| Elixir Collector | DIFF | HP [1070]/[1070]; ATK [0]/[0]; ready [20]/[20]; tower@10/20/30 [0,0,0]/[0,0,0]; death [1898]/[2250]; production cycles [279,539,799,1059,1319,1579,1839]/[319]; hog ElixirCollector[0].configured_lifetime_ms 93000/110000 | Stat + economy: configured lifetime 93000/110000 ms; idle death tick 1898/2250. First production cycle completes at 279/319; ours continues cycles at the elixir cap while reference holds the due payout. `src/clasher/card_types.py::CardStatsCompat.__init__`; `src/clasher/cards/elixir_collector.py::ElixirProduction.on_object_tick`; `_give`; `src/clasher/entities.py::Building._update_intrinsic_lifetime`. |
| GoblinDrill | DIFF | HP [1313,202,202,202,202,202]/[2560,1313,202,202,202,202]; ATK [0,125,125,125,125,125]/[0,0,125,125,125,125]; ready [44,63,123,183,243,254]/[null,45,64,124,184,244]; tower@10/20/30 [0,125,125]/[0,125,125]; hog Goblin[0].birth 69/71 | Underground arrival/deploy clock: ours represents the eventual building from tick 1; reference digger exists until tick 25, then building is ready at 45 (ours 44). First Goblin 63/64. `src/clasher/cards/miner.py::UndergroundDeployment.on_tick`; `src/clasher/battle.py::_spawn_entity`. |
| Rage | DIFF | tower@10/20/30 [45,45,45]/[46,46,46]; stationary damage 0/0; effect ticks 98/95; support tower_hits[0].tick 194/190 | Aura start/expiry and radius: center buff occupies 98/95 ticks, first tick 16/11; center distance 3.5 is missed/hit. `src/clasher/dynamic_spells.py::create_spell_from_json`; `src/clasher/entities.py::BuffAreaEffect._apply_haste_scan`; `Entity.intersects_native_area`. |
| Mirror | PASS | HP [1938]/[1938]; ATK [221]/[221]; ready [60]/[60]; tower@10/20/30 [404,3052,4157]/[404,3052,4157] | Knight-copy scenario agrees: copied level 12, HP 1938, attack 221, ready tick 60. Other copied card types not exercised. |
| Graveyard | DIFF | HP [81,81,81,81,81,81]/[81,81,81,81,81,81]; ATK [81,81,81,81,81,81]/[81,81,81,81,81,81]; ready [53,63,75,85,97,107]/[55,65,77,87,99,109]; tower@10/20/30 [81,81,81]/[405,405,405]; cluster Skeleton[0].ready 83/85 | Spawn clock + geometry: 12 Skeletons in both; first birth 44/45, ready 53/55, but tower total diverges. Skeleton row-name aliases are normalized for comparison. `src/clasher/entities.py::Graveyard._spawn_skeleton`; `src/clasher/dynamic_spells.py::create_spell_from_json`. |
| Clone | DIFF | tower@10/20/30 [0,0,0]/[0,0,0]; support tower_hits.count 8/9 | Likely clone displacement/target acquisition: Giant copies both have 1 HP; first push tower impact 225/197 and tower impact count 8/9. Original and copied units share physical contact and can redirect one another. `src/clasher/spells.py::CloneSpell.cast`; `src/clasher/battle.py::_spawn_unit_at_position`. |
| Heal | DIFF | HP [230]/[215]; ATK [110]/[110]; ready [20]/[20]; tower@10/20/30 [110,110,110]/[0,0,0]; knight HealSpirit[0].max_hp 230/215 | Stat: Heal Spirit HP 230/215, damage 110 agrees; bridge death 94/77. `src/clasher/dynamic_spells.py::create_spell_from_json`; `src/clasher/factory/dynamic_factory.py::troop_from_character_data`. |
| DarkMagic | DIFF | tower@10/20/30 [144,144,144]/[291,291,291]; stationary damage 1020/2088; effect ticks 0/6; cluster tower_hits.count 27/6 | Void stats + cadence + geometry: isolated single-target hits 340/696; impact ticks [32,52,72]/[33,57,81], tower hit 48/97. `src/clasher/scope_spells.py::build_scope_spell`; `VoidArea.update`; `_enemy_characters_in_area`. |
| GoblinCurse | DIFF | tower@10/20/30 [60,60,60]/[60,60,60]; stationary damage 210/210; effect ticks 121/121; cluster Goblin[0].ready null/112 | Area geometry + conversion placement: center DoT 6 x 35 agrees within 1 tick; center distance 3.5 is missed/hit; converted Goblin placements/outcomes differ. `src/clasher/scope_spells.py::build_scope_spell`; `_enemy_characters_in_area`; `GoblinCurseArea.update`. |
| MergeMaiden | DIFF | HP []/[1121]; ATK []/[320]; ready []/[20]; tower@10/20/30 [0,0,0]/[1280,1600,1600]; knight MergeMaiden_Mounted.count 0/1 | Missing resource-dependent form deployment: accepted paid play produces no body in ours; reference produces Mounted form (1121 HP, full-table attack 320). `src/clasher/spells.py::MERGE_MAIDEN` (zero-damage placeholder); `src/clasher/battle.py::resolve_card_play`; `deploy_card`. |

## Coverage and interpretation

Both engines use their normal deploy paths. The harness seeds RNGs, constructs fixed hands, and starts at absolute tick 100 (past RoyaleSim’s opening lockout). Our elixir top-ups and hand forcing are retained in counters; a refused deployment is HARNESS-GAP rather than a fidelity verdict. No reference fixture corpus or held-out replay data was used. Only measured outputs, code, and the card-name/kind pool are saved; no upstream card data tables are included.

Spawn counts include all descendants born during the scenario, including death spawns; `alive_at` is a separate survivor count. Early movement speed is the median nonzero displacement before relative tick 120, so close combat/contact can affect it. Initial spawn locations are stored for diagnosis but are not independently gated. First-hit and hit periods can be read from the full ordered impact events; multi-unit/splash events are intentionally not mislabeled as one unit’s hit period.

The Collector idle probe runs 175 seconds. `production_ticks` records the source’s completed production clock cycles: ours advances its production counter even when the payout is wasted at 10 elixir; the reference holds the due cycle at the cap. It is not a count of elixir actually credited. The first deployment-time timer initialization is excluded. Both idle lifetimes are observed to death.

The existing adapters seed Python RNG to 0 and RoyaleSim to the start tick (100); there is no claim that unrelated PRNGs yield identical random placement. Graveyard still differs on deploy-ready ticks independently of its placement pattern. Controlled spell targets use fixed coordinates and no RNG.

Reproduce with the job instructions in REPRODUCE.md. Full raw event traces remain on 127x08 under `/mpac/sdicks02/jobs/clasher/cards/fidelity/20261015/`; the consolidated JSONL omits unused own-side damage/decay events. Source hashes and supervised job PIDs are in provenance.json.

## Controlled spell probes

One level-11 Knight is made stationary (speed 0) and given 10000 HP in both engines, outside enemy tower range. Offensive spells are normally cast at (9,19.5), Rage at (9,12.5); target x is 9 + offset. The normal spell deploy path is unchanged. RoyaleSim reset spawns and deliberately edited entity snapshots set the target state; the engine computes and verifies the new snapshot checksum. A center-distance boundary includes the Knight’s 0.5-tile hitbox. Effects below measure target-local status occupancy, not an area object’s visual lifetime.

| Spell | Center damage | Center impact ticks | Effect occupancy ticks | Farthest sampled affected center offset |
|---|---|---|---|---|
| Freeze | 148 / 148 | [[1,148]] / [[1,148]] | 80 / 70 | 3.49 / 4 |
| Snowball | 179 / 179 | [[21,179]] / [[21,179]] | 60 / 60 | 2.99 / 3.5 |
| Vines | 306 / 306 | [[38,153],[58,153]] / [[39,153],[59,153]] | 40 / 40 | 2.99 / 3.5 |
| Rage | 0 / 0 | [] / [] | 98 / 95 | 3.49 / 4 |
| DarkMagic | 1020 / 2088 | [[32,340],[52,340],[72,340]] / [[33,696],[53,696],[73,696]] | 0 / 6 | 2.99 / 3.5 |
| GoblinCurse | 210 / 210 | [[21,35],[41,35],[61,35],[81,35],[101,35],[121,35]] / [[22,35],[42,35],[62,35],[82,35],[102,35],[122,35]] | 121 / 121 | 3.49 / 4 |

The radius samples bracket the hit boundary; they are not exact inferred card radii. At the center Snowball’s zero-vector push is also different: ours moves +y, RoyaleSim −x. Positions are retained in the probe rows.

## Adapter default cross-check

The same scripts also ran through the unchanged rsim16402 adapter default. Both table arms are retained separately in results.jsonl. Golden Knight and Lumberjack pass with that older table but differ with the full 16.402 table.

| Card | Full 16.402 table | Adapter default |
|---|---|---|
| GoblinCage | DIFF | DIFF |
| SpearGoblins | DIFF | DIFF |
| Bomber | DIFF | DIFF |
| Tombstone | DIFF | DIFF |
| Barbarians | DIFF | DIFF |
| BattleRam | DIFF | DIFF |
| MegaMinion | PASS | PASS |
| BarbarianHut | DIFF | DIFF |
| Mortar | DIFF | DIFF |
| DartBarrell | DIFF | DIFF |
| Witch | DIFF | DIFF |
| Pekka | PASS | PASS |
| SkeletonWarriors | DIFF | DIFF |
| SkeletonDragons | DIFF | DIFF |
| RoyalGiant | DIFF | DIFF |
| ThreeMusketeers | DIFF | DIFF |
| RoyalRecruits | DIFF | DIFF |
| GiantSkeleton | DIFF | DIFF |
| BattleHealer | DIFF | DIFF |
| Freeze | DIFF | DIFF |
| Snowball | DIFF | DIFF |
| Vines | DIFF | DIFF |
| SkeletonBalloon | DIFF | DIFF |
| GoblinGiant | DIFF | DIFF |
| GiantBuffer | DIFF | DIFF |
| Hunter | DIFF | DIFF |
| MiniSparkys | DIFF | DIFF |
| IceWizard | DIFF | DIFF |
| LavaHound | DIFF | DIFF |
| ZapMachine | DIFF | DIFF |
| Bowler | DIFF | DIFF |
| RageBarbarian | DIFF | PASS |
| InfernoDragon | DIFF | DIFF |
| ElectroWizard | DIFF | DIFF |
| AxeMan | DIFF | DIFF |
| Assassin | DIFF | DIFF |
| DarkWitch | DIFF | DIFF |
| RamRider | DIFF | DIFF |
| MovingCannon | DIFF | DIFF |
| MegaKnight | DIFF | DIFF |
| Fisherman | DIFF | DIFF |
| EliteArcher | DIFF | DIFF |
| ElectroDragon | DIFF | DIFF |
| ElixirGolem | DIFF | DIFF |
| SkeletonKing | PASS | PASS |
| GoldenKnight | DIFF | PASS |
| Monk | DIFF | DIFF |
| WitchMother | DIFF | DIFF |
| ElectroGiant | DIFF | DIFF |
| Phoenix | DIFF | DIFF |
| LittlePrince | DIFF | DIFF |
| GoblinDemolisher | DIFF | DIFF |
| GoblinMachine | DIFF | DIFF |
| SuspiciousBush | DIFF | DIFF |
| BossBandit | DIFF | DIFF |
| Ronin | DIFF | DIFF |
| Elixir Collector | DIFF | DIFF |
| GoblinDrill | DIFF | DIFF |
| Rage | DIFF | DIFF |
| Mirror | PASS | PASS |
| Graveyard | DIFF | DIFF |
| Clone | DIFF | DIFF |
| Heal | DIFF | DIFF |
| DarkMagic | DIFF | DIFF |
| GoblinCurse | DIFF | DIFF |
| MergeMaiden | DIFF | DIFF |