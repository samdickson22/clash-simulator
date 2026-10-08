# Stage 6: S122 native parity

Status: Linux build48 private core QUALIFIED and sealed. Full Stage 6/S122 admission remains BLOCKED by the unchanged ThreeMusketeers Python controller exception. All requested parity gates passed, including 48 recorded and 24 human independent games covering all 66 cards with zero mismatches. See `stage6/qualification-r48b-linux.json` and `stage6/completion-audit-r48b-linux.json`. Main-hub source and drivers are restored to build48; verification used `/mpac/sdicks02/repos/clasher-stage6-build48`. All owned gate jobs have finished.

## Scope and order

`stage6/scope.json` derives the remaining base cards from the same S117 union FIVE rule as `scope-expansion/scope_coverage.py`, normalizing aliases with `clasher.card_aliases.resolve_card_name` before subtracting C56. DarkPrince and Prince are already in P16. The six repaired opponent cards from Stage 4 remain in the S122-minus-C56 checklist and require requalification, not a second implementation claim. Evolution and hero forms are excluded; the corpus's base-card rows are authoritative.

Arena priority source, accessed 2026-10-04: https://www.pockettactics.com/clash-royale/arenas . Use arenas 1-8 first, then corpus deck frequency, with adjacent mechanics grouped. The page has a probable Skeleton Tower typo in arena 4; Skeleton Dragons needs independent verification. Requested IceWizard, ElectroWizard, Hunter and AxeMan follow the early-arena bundles. Full derived rows and frequencies are in scope.json; source counts come from the pinned human-prior scan, not current ladder popularity.

First bundles: ordinary ground/air/splash bodies (SpearGoblins, Bomber, Barbarians, MegaMinion, Pekka); production/death children (GoblinCage, Tombstone, Witch); charging death children (BattleRam); minimum-range building/projectiles (Mortar), followed by the remaining early cards. Each bundle needs focused cases, root-cause regressions and mixed interactions before admission.

## Gates

Require zero digest, action and full MT-state mismatches. Final gates: at least 64 terminal human-corpus deck games covering every new card; 1,000 live imports; 4,000 accepted public-legal placements; 30x stepping speed; clone below 20 us; C56-native controller/candidate extensions and 100 planner calls. None has run for Stage 6 yet. Python engine crashes must be recorded here and retained without changing Python behavior.

Long jobs use `pilot/detach.sh` with `stage6/run.sh`, nice 10 and at most two heavy workers. Inspect exit files and process ancestry before resuming; never duplicate a live worker. Preserve failing receipts. Outputs must remain below 500 MB. Clean only the owned Stage 6 Cargo target when idle.

## Work log

- Entry: read Stage 4/5/5b, PROGRESS, Python scope and native tooling. Captured source/data/native hashes, copied the existing native extension to a private location, and created the scope/priority inventory. No implementation changes yet.
- Scope audit: exactly 66 remaining canonical base cards. Skeleton Dragons arena4 confirmed independently at https://liquipedia.net/clashroyale/Skeleton_Dragons . Entry identity and the five-card body baseline are running, with separate exit receipts.
- First reduced spawn baseline FAIL retained in spawn-r0.log: Goblin Cage omits its death child at tick420; Tombstone/Witch native production panics because the exporter omitted child templates. Python did not crash. Added templates for these cards, BattleRam and GiantSkeleton. Zero-radius death children now recompute Python's terrain candidates at the actual death position instead of copying one demonstration offset. References: src/clasher/mechanics/shared/death_effects.py:243-295, src/clasher/battle.py:2050-2104, src/clasher/mechanics/shared/spawner.py:114-196. Regression: stage6/test_early.py production/death test, both seats and imported continuations. Private build1 pending.
- Build1 fixes pass both reduced methods, including both seats and live imports for all8 cards. Spawn focused24-case gate running. Five reused body cards passed40 existing-core cases/88,000 ticks; these are focused-only receipts and require final-build replay.
- GoblinCage/Tombstone/Witch focused24 PASS on build1. GiantSkeleton delayed-bomb regression passes. BattleRam reduced test fails both seats at75: Python commits the building hit then destroys the ram and releases its two riders; native retained the ram. First difference retained in stage6/ram75-r1.json. Added mechanic-derived break_on_building_hit after committed attack damage, matching src/clasher/cards/battle_ram.py:20-26 and entities.py:945-983. Regression: test_ram.RamAndBomb.test_ram_dies_on_building_hit_and_releases_two_riders. Build2 pending; no Python changes.
- Build2 ram reduction exposed a second error at75: copied death-child offsets retain the demonstration facing. BattleRam has nonzero SpawnAngleShift, so Python rotates the child ring using the parent's facing at death. Added runtime fixed-point rotation for nonzero-angle radial death spawns; retained the existing world-fixed/constant-priority path for other cards. References: death_effects.py:212-253, formations.py:199-234. Full phase trace in ram75-r2.json; same both-seat regression catches the missing rotation. Build3 pending.

## Early group checkpoint

Build3 reductions pass for SpearGoblins, GoblinCage, Bomber, Tombstone, Barbarians, BattleRam, MegaMinion, Witch, Pekka and GiantSkeleton. Existing physics handles five of these without new mechanics. `early-r4-interactions.json` passes12 terminal constructed games/53,659 ticks,135 live imports/10,800 continuation ticks and1,127 accepted public-legal placements. Every focal card entered play. Aggregate stepping56.583x and maximum per-root100-clone mean4.030us apply only to this constructed group. Final human-corpus gates remain pending. Final-build80 focused cases and old-scope regressions are in progress.

`stage6/controller.py` is an explicit development metadata adapter for the ten early cards, using unchanged C56 Python and native scoring functions. Its20 initial card/seat smoke comparisons pass public body/mask and all3 style actions. It is not installed into the default policy or admitted fair player. Native candidate ranking and100 planner calls remain pending.

The first interaction launch failed in the new fixture driver because it treated no-op2304 as a deployment. `early-r3.log` is retained; `early-r4` fixes the placement slice. This was a fixture error, not a Python-engine crash.
- Early group qualification complete on frozen build3:80 focused cases/158,624 ticks and88 existing Stage4 regressions pass in addition to the4 new regression methods and12 full interaction games. `stage6/early-manifest.json` binds counts, receipts, sources and the unchanged reference audit. Final S122 admission is false;56 remaining checklist cards are unqualified by Stage6. Build4 adds native all-placement C56 rankings for candidate generation; it needs separate controller/planner qualification. The NumPy sampler remains unchanged.

## Current resume point

All 66 remaining cards have incremental core certificates through sealed build41. Mirror completed 58 cumulative methods, 8 focused cases and 12 terminal mixed games, plus 88 C56 and 47 earlier controls. Historical group evidence does not establish final S122 admission.

The 2026-10-05 restart left no Stage6 build or gate workers. No final human or planner gate had begun. Old empty launches are retained and superseded by completed retries. Always check process ancestry and exit files before resuming.

Skeleton King's active summon is being added in private42. Python calls the three-Skeleton helper 15 times, producing 45 bodies; below20 souls the ready query can succeed but activation fails. Golden Knight has no active ability in the Python oracle. The new reducer checks both seats, soul thresholds, payment, timers and imported continuations. Build42 failed compilation before replacement;42b is the corrected retry.

The opt-in controller now includes Mirror, bringing its supported new-card roster to65. ThreeMusketeers remains blocked because unchanged Python scoring raises float(None) on the visible placeholder. This is an unresolved full-roster controller qualification limitation. Evolutions/heroes are excluded.

human64-plan.json and the optional32-game supplement remain frozen and prospective. Final64+ human terminal games covering all66,1000 live imports,4000 placements,30x speed,clone<20us and expanded100 searchable planner calls remain open. Final controls must pass on the same source/native pins. All long jobs use pilot/detach.sh and run.sh with at most2 owned heavy workers and niceness10.

Known unchanged oracle limitations are retained in python-issues.json: ThreeMusketeers placeholder/controller error, ignored BattleHealer healing, stale moving-building placement cache, and rejected Mirror predecessors. Never change the Python engine, scripts, data or admitted native extension.

## Early2 work log

- First40 focused cases (SkeletonDragons,Mortar,DartBarrell,SkeletonWarriors,RoyalGiant) pass on build4. ThreeMusketeers fails at action0,seat1/right lane,by one x logic unit. Python skips symmetric deploy snap when serialized card speed is absent/zero, even though body creation later uses a60-speed fallback. Exported an explicit skip_deploy_snap flag and respected it in template offset removal,native anchor adjustment and forward edge. References: src/clasher/battle.py:1382-1425,1938-1956. Regression: test_early2.Early2.test_missing_serialized_speed_skips_deployment_snap, both seats/both lanes. Failure retained in early2-r4.json. Private build5 pending.

Python oracle issue found, unchanged: canonical ThreeMusketeers raw row has no summonCharacterData/count/speed/HP/damage. Python deploys one placeholder Troop with100HP,0damage and fallback60speed, rather than three Musketeers. This is a data/engine limitation, not a crash. Native qualification for this card reproduces that placeholder and cannot imply real-game Three Musketeers fidelity. Do not repair Python or gamedata in this task.
- ThreeMusketeers tick1 additionally exposed unfiltered Crown fallback and inconsistent fresh/live movement metadata. Native Crown fallback now applies the same hit-plane filter as visible targets; fresh troop metadata uses serialized speed like the live exporter. Reference: entities.py:2520-2553 and live_snapshot.py:18. RoyalRecruits needs dynamic line construction, because a left-lane demonstration clips its first bodies before translation. Ported its2.5-tile line, live Crown avoidance, owner-ordered nearest-valid search, lane provenance, forward-edge clipping and final quantization into engine-rs/src/deployment.rs. Reference: battle.py:1792-1910,1912-2004,2131-2236 and arena.py:85-127,303-338. Existing Early2 combat/import regression plus40 seat/x/y deployment fixtures cover these branches. Build6 pending.

## Arena8 work log

- Retained baselines:Snowball case0 diverges at194 from missing projectile-spell slow; Freeze at641 from missing one-time freeze recipient snapshot; BattleHealer at20 from missing serialized spawn-area creation. Added spell slow fields and fresh post-damage status application,all3 slow axes and fractional production milliseconds (spawner.py:43-50); Freeze snapshot/import flag and target-owned expiry (entities.py:6085-6132); generic SpawnAreaEffect templates and one-time damage/buff/lifetime state (mechanics/shared/spawn_area.py:20-82). Reduced tests are in test_arena8.py and cover both seats,Tombstone production,Freeze death children/late arrivals/imports,and BattleHealer spawn-area lifetime. Private build7 pending.

- Python oracle limitation under test: BattleHealerSpawnHeal serializes healPerSecond in its buff data, but SpawnAreaEffect reads only damage and speed axes. Its zero-damage area performs no healing. Preserve this behavior; do not add healing to Python or Rust beyond the oracle. This is not a Python crash.

- Early2 certificate finalized: early2-manifest.json/build6 record56 focused cases/109,541 ticks,12 terminal constructed games/30,702 ticks,80 imports,368 accepted plays,49.393x stepping,max per-root clone mean4.920us,3 new test methods and88 existing C56 tests,0 mismatches. Entry check_identity.sh passed allfour suites including8 recorded and24 random episodes. Human64 plan is frozen from44,939 eligible deck identities but has not been simulated.
- Build7's24 arena8 cases and3 reduced methods pass, but two existing IceGolem import controls fail at2. Broadening one-time area handling dropped the birth-boundary skip on death-created objects. Added an explicit scope_skip_birth flag based on _native_object_birth_tick and preserved it through import; scope timers now skip that boundary. Reference mechanics/shared/death_area.py:9-18, regression engine-rs/test_stage4_imports.py:13-44. Failure retained in death-area-birth-r7.json; build7 is not admitted. Build8 pending.
- Build8 passes88 C56 tests,all prior Stage6 reductions/ranking and24 arena8 cases. Mixed game3 first diverges3240 when four combat-born Tombstone children are absent from Rust's avoidance grid. Physical collision already sees them; avoidance must see them too, in registration order. Added incremental grid insertion before later component consumers. Reference battle.py:2045-2047,2299-2301 and native_spatial.py:23-48. Saved pinned fresh root arena8-root3239-r8.pkl and arena8-phase3240-r8.json. Regression test_arena8.Arena8.test_combat_births_join_avoidance_before_later_movers compares140 ticks and the original first divergent position. Build8 mixed gate is not admitted; build9 pending.

## Requested ranged group

- Resumed build10 receipts: ElectroWizard reduced2 methods pass and Hunter/ElectroWizard16 focused cases pass. IceWizard0 fails116. Exporter omitted projectile slow duration/multiplier; splash path applied only damage. Added serialized slow,live-shot state export,and a fresh post-damage splash status query. References src/clasher/entities.py:4020-4031,5699-5740. Regression test_ranged.Ranged.test_ice_wizard_projectile_slow_and_live_shot_import covers both seats,shot-in-flight import and slowed continuations. Retained requested-r10.json and frozen build10. Private build11 pending;no Python edit.
- Build11 first reduced run exposed an exporter field collision: Entity.slow_multiplier is target state,not a troop's projectile payload. Fresh template must use targetBuffData;live projectile import uses its own payload. Corrected by entity_kind. Retained ice70-r11.json and failing requested-r11.log. All88 old C56 regressions passed. Rerun needs fresh bridge pins although private binary is unchanged.
- Requested mixed game1 fails4863 despite32 passing focused cases. Phase trace shows ElectroWizard lethal secondary damage depletes Hunter546,then Python applies stun to the retained recipient and cancels its start-of-phase eligible shot. Native stun rejected zeroHP,so it emitted projectile562. Removed the alive guard from committed stun application,matching entities.py:610-624,984-1049,2987-3005 and battle.py:818-833. Pinned fresh saved root and160-tick continuation regression test_ranged.Ranged.test_lethal_secondary_stun_cancels_eligible_hunter_shot. No Python crash/change. Corrected-bridge88 C56 tests passed;building12 with all workers idle.
- Requested ranged group QUALIFIED build12:32 focused/64075ticks,12 terminal games/48697ticks,123imports,677accepted placements,45.978x,maxclone4.290us,20 cumulative reduced methods plus88C56 tests,0mismatches. Sealed requested-r12-manifest.json/build12;total24 incremental cards,42 remain. Opt-in controller roster extended to23 eligible new cards,excluding ThreeMusketeers;expanded ranking qualification pending.
- Reuse bundle40 focused and both-seat import controls pass,but mixed0 fails2680. Saved reuse-r12-root2679.pkl/meta and phase2680 trace. Ground-only Cannon projectile207 was launched while Vines grounded InfernoDragon198;after release Python Projectile._can_damage rejects the now-airborne target,while native direct branch damages it. References entities.py:5640-5660,5523-5541. Proposed hit-plane guard must preserve the explicit ground-jumper committed-hit exception. No fix applied while early100 planner is pinned. body-r12 worker covers six ordinary/base clock cards on unchangedbuild12 as the second heavy worker.
- Body mixedgame5 fails2712 because SkeletonKing soul-drop hook is unported. SoulCollector.on_tick counts nearby enemy corpses;on_death drops min(souls//2,10) Skeletons on a1.5-tile floating-point ring via _spawn_troop. Source mechanics/champion/skeleton_king.py:36-62,89-124;battle.py:1531-1578. Saved root2711 and phase2712 preserve6souls/3children counterexample. No Python issue/change. Port must preserve combat hook order,live soul state,and source ring math;body-r12 is not qualified.
- Body2 QUALIFIED on frozen build12-body2:nine cards GiantBuffer,GoblinDemolisher,RamRider,GoblinGiant,Monk,Ronin,MergeMaiden_Normal,LittlePrince,GoblinMachine;72 focused/128091ticks,12 terminal/36321ticks,93imports,419placements,45.250x,maxclone4.750us,18 seat import fixtures plus unchanged-build88 C56 tests,0mismatches. Total33 incremental cards,33 remain. Native controller for these nine remains pending while early100 holds controller pins.
- Early100 planner qualification COMPLETE on privatebuild12:100/100 searchable calls,2189 candidates,min21,ten early cards both seats,five ages,0candidate/action/score/trace/fullMT mismatches. Native ranking is exact with unchanged NumPy sample order. Sealed planner-early100-r12-manifest.json;earlier limited/partial receipts remain separate. Final expanded-scope100 calls remain pending.
- Repaired deployment5040 root reveals an oracle cache limitation,not an underground-obstacle exclusion:Drill493 has emerged at13,13,while Python retains a size1 mask created at its underground origin. get_building_placement_blocked_mask_world invalidates by live IDs,not position. Native recomputed from current footprints. Added read-only cached masks/signature export and native membership-keyed cache preserving float32 bounds. References battle.py:366-380,651-693,1198-1218. This source limitation is preserved without fixing Python. Build13 also ports SoulCollector collection/death drop and direct projectile hit-plane filter;qualification pending.
- Correction to Soul2712 interpretation:root actually has2souls. _drop_souls_as_skeletons calls get_card("Skeleton"),which resolves canonical Skeletons and _spawn_troop creates a3-body swarm for each dropped group. One group therefore creates3children. Preserved source alias behavior;native uses both-seat/lane templates within the source float ring. Added2/10/30souls controls. Build13 plane manual fixture accidentally used troop-only spawn primitive for Cannon;corrected fixture to Building. Exact retained roots for Vines release and deployment-cache pass. Build14 pending.
- reuse-r14 QUALIFIED:MiniSparkys,WitchMother,InfernoDragon,Vines,Heal;40 focused/87284ticks,12 terminal/49192ticks,125imports,845placements,48.260x,maxclone2.710us,0mismatches. Frozen source/native/receipts and immutable copies of shared recovery log.
- body-r14 QUALIFIED:Elixir Collector,ZapMachine,MovingCannon,SkeletonKing,Phoenix,ElectroGiant;48 focused/89795ticks,12 terminal/28986ticks,76imports,275placements,47.578x,maxclone2.490us,0mismatches. Frozen source/native/receipts and immutable copies of shared recovery log.
- repaired-r14 QUALIFIED:GoblinDrill,DarkMagic,GoblinCurse;24 focused/51672ticks,12 terminal/59989ticks,151imports,1190placements,50.595x,maxclone5.730us,0mismatches. Frozen source/native/receipts and immutable copies of shared recovery log.
- GoldenKnight1948 route issue reduced to first latent divergence1808:jumpSpeed400 without jumpHeight was interpreted as generic river jumping. Python pathfinding.py:655-696 selects water profile solely from bool(jump_height). Exporter now serializes generic jump_speed only with jump_height;special dash speeds remain separate mechanics to port. Saved golden-route-root1808-r14.pkl/meta and phase1948;test_golden.Golden compares300 ticks. Bridge-only fix on14 requires fresh pins,not relabelled14 certificates.
- Golden bridge-only root300 and8 focused cases pass. Bowler240 trace shows missing RollingProjectile class and immediate birth-frame rolling update. Ported directional/circular rolling samples,terminal enlarged radius,per-ID hits and push;source entities.py:4070-4107,6764-6941. EliteArcher104 trace shows omitted temporary homing shifts the finite ray endpoint by1tile;port initial distance guard,100ms steering,current-position endpoint renewal,import remaining target state and dead-target last position (entities.py:5192-5247). New private15 requires reductions/focused/mixed/C56 validation before qualification.
- Expanded46-card controller exposes GoblinDrill public-mask gap:the v5 reference resolves its even footprint in world coordinates before checking visible blockers,and separately excludes requested crown tiles. Native used ordinary requested-centre padding. Added native equivalent of contract_v5.py:529-550 with both-seat/deployed ranking regression fixtures. Private15 stillpassed3 new physics reductions and88 old regressions;no new group certificate on the failing controller gate. Build16 pending.
- EliteArcher674 reduction exposes missing enlarged launch collision:Source creates projectiles93/94 and immediately resolve_start_collision damages Knight45/46 by143. Native waited for flight. Export projectileStartExtraRadius and resolve fresh piercing start hits after ID reservation/before later combat consumers (entities.py:4169-4177,5350-5372). Failure retained projectile-r16-focused.json. Both-seat import regression already covers temporary steering;add launch-specific fixture. Private17 pending.
- Projectile group QUALIFIED build17:Bowler,EliteArcher,GoldenKnight;24 focused/45065ticks,12 terminal/44453ticks,113imports,583placements,49.843x,maxclone3.120us,31 cumulative reduced/controller methods plus88 C56 tests,0mismatches. Total50 incremental cards,16 remain. Read-only payload inventory confirms nested ElixirGolem splits and SkeletonBalloon explosive children for next bundle.
- Missing nested templates reduced with payload-inventory-r17.json. Read-only payload_snapshot.py serializes production/death children recursively and TimedExplosive._spawn_death_units separately;shared native spawn_death_templates retains existing geometry/freeze behavior. Bomb children dispatch after damage,matching entities.py:7089-7167;recursive mechanics match death_effects.py:94-295,spawner.py:114-196. Scope DarkWitch,LavaHound,ElixirGolem,BarbarianHut,SkeletonBalloon. Private18 pending focused/import/death/cumulative/C56 gates.
- Retained barrel137-r19.json shows source stillalive96HP/kamikaze_primed/timer0.5 while native already emitted bomb13. Payload-only kamikaze path precedes the ordinary hit callback. Added native delay/primed timer import and countdown;stun/push early returns preserve source pause semantics (entities.py:3867-3875,3923-3941). The prior both-seat800-tick payload/import regression is the reduction. Private20 pending.
- Barrel150-r20.json reduces runtime ring transforms:seven matching children differ because static demonstration offsets retain left-lane/blue constant-priority flips. Serialize spawn_const_priority and recompute nonzero radius ring using live lane/owner/facing per formations.py:199-243,entities.py:7120-7178. Carry container absoluteFreeze expiry even when children have500ms deploy delay. C56-r20 all88 pass;private21 pending.
- Payload group QUALIFIED build21:DarkWitch,SkeletonBalloon,LavaHound,ElixirGolem,BarbarianHut;40focused/75819ticks,12terminal/15890ticks,43imports,150placements,52.390x,maxclone11.240us,8 reduced methods including10 card/seat/import fixtures plus88 C56 tests,0mismatches. Total55 incremental cards,11 remain. No finalS122 admission.

- No prior Stage6 workers remain. Graveyard port adds absolute spawn deadlines, deterministic player/lane offsets and no-terrain-snap quarter-boundary children; references entities.py:7188-7311,battle.py:1912-2025. New both-seat/edge/import reducer and8 focused/12 mixed gates pending private22. Frozen46-controller drivers before extension to54 eligible cards.55 incremental core cards remain qualified;no final admission.

- Private22 Graveyard reduction retained: native child lane lookup used whole tiles against the half-tile path grid, causing route divergence after54-98 ticks. Corrected to cell()/36-wide native path lookup. Edge fixture0.5,0.5 was a blocked public placement; corrected to legal outer edge0.5,13.5. Frozen unqualified22 source/native before correction. Private23 pending.

- Private23 build completes. Graveyard live export supplies card identity absent from the Python carrier (card_stats=None, no spell_name); only native representation gains the lookup key. Starting Graveyard group+54-card controller reductions and88 C56 controls,atmost2 owned workers. No core/bridge edits during gates.

- Graveyard QUALIFIED frozen23:8focused/17600ticks,12terminal/46382ticks,117imports,635placements,53.684x,maxclone5.640us,13cumulative methods including54-card ranking plus88C56,0mismatches. Total56/66 incremental cards,10remain. Controller54 proof frozen before adding Graveyard to55 eligible. Next Rage/RageBarbarian/SuspiciousBush death-area/haste bundle;final human/planner gates remain open.

- Private24 building nested death-area carriers/start actions/delayed impact templates and target-owned haste effects; integer movement/attack buff-before-debuff,spawn combined-percent//2,independent expiry preserved. Generic death-area trigger now dispatches even without deathDamage. References death_area.py:9-18,57-285;entities.py:1295-1312,1370-1450,6426-6644;spawner.py:35-50. New test_haste coversbothseats,chainimports,production,composedbuff/slow/expiry;Rage/RageBarbarian/SuspiciousBush24focused/12mixed pending. Python/data unchanged.

- Private24 completes24focused/12terminal Rage/death-area games,16 cumulative methods and88C56,all0 mismatches. Qualification withheld because extra haste-ramp-r24 reducer fails61: DamageRamp.on_target_observed uses full attack work (damage_ramp.py:38-76),Rust lock time omitted haste. Private25 corrects lock/leaf arrival haste andadds ElectroDragon post-impact chain/fixed-vs-speed-based hops (electro_dragon.py:32-58,entities.py:5443-5461,5794-5961). Frozen24 source/native before changes. No Python/data edits;private25 gates pending.

- Private25 reducers19 methods (includinghaste-lock fix,Dragonlivehop/source-removed callback,controller55) and32 focused plus88C56 pass. Mixedgame4 fails;group is notqualified. Retaining actual savedroot/phase replay before nextport;noPythoncrash.

- Mixed25 firstdivergence2400 is an extra empty chain278: RageBarbarian kills Crown2 in combat beforeDragon277 reaches it. Python impact query rejects the dead crown;Rust newlyadded callback dispatched anyway. Retained pinned root2399/meta/phase2400;new180-tick regression. Native callbacks now require recipient alive at object-phase entry,retaining committed recipients killed by another same-phase projectile. References entities.py:5480-5494,5524-5546,5634-5637,battle.py:1144. Private26 building;25 remains unqualified,all previouscards preserved.

- Private26 compiler rejects missing BTreeSet import;no binary replacement. Corrected to fullyqualified type andsnapshot living recipients when projectile processing starts,afterpreceding area effects,matching queued impact queries. Private27 build pending;root2399 regression checks source/data/root hashes before continuation.

- Private27 build completes. Detached haste-dragon-r27 group reruns20 cumulative reducers,32 focused and12mixed;separatec56-r27 checks88 controls. Atmost2heavy workers;core/bridge/controller nowfixed until exit. Total56 certificates remain;Ragebundle remainsunqualified until correctedmixedgate passes.

- Private27 corrected Crown2399 continuation passes among20 cumulative reducers;focusedgate progressing, no mixedqualificationyet. Prepared report-only Bandit/BossBandit draft withoutchanging active core pins. Cleaned onlyidle ownedStage6 Cargo intermediates;private binary andall frozen snapshots retained.

- Haste/Dragon QUALIFIED frozen27:Rage,RageBarbarian,SuspiciousBush,ElectroDragon;32focused/70400ticks,12terminal/43481ticks,110imports,678placements,39.728x,maxclone5.840us,20 cumulative reductions/controller55 plus88C56,0mismatches. Total60/66 incremental cards,6remain:Assassin,MegaKnight,Fisherman,BossBandit,Clone,Mirror. Controller55 proof frozen before extension to59 eligible cards;new59 ranking pending. Previous24/25 failures retained.

- Private28 ports Assassin/BossBandit anticipation,live retarget/rangeband,inclusive integer bounds,speed-based travel,scaledhit,travel damage/status/push immunity andlanding damage-only tail. Read-only dash_snapshot.py exportslive state;nativecollisions skipcommitteddash bodies. References bandit.py:68-312;entities.py:1930-1987,3720-3750,3069-3080;new test_dash coversbothcards/seats,Zapcharge/travel andimportedcontinuations. Private28 building withall previousworkers gone.

- Private28 build exit0. Running new Bandit/BossBandit reducer first (bothseats,stationaryCannon rangeband,Zapwindup/travel andliveimports),oneheavyworker. Ifitpasses,the fullcumulative/differential/mixedgroup and88C56 gates follow. No core changes whilethisworker runs.

- Private28 newdash reducerPASS12 card/seat/Zap fixtures pluswindup/travel/idle imported100-tick continuations. Launchdash-r28 cumulativeStage6/59controller tests,16focused and12mixed;separatec56-r28 (88oldtests),2heavyworkers. No code/controller change until bothexit.60priorcertificates unchanged;Banditgroup notyetqualified.

- Private28 cumulative41 methods (59-cardcontroller included) and88C56 PASS. FocusedAssassin cases0-5 pass;case6 fails830 (missing194 ordinarydamage onBandit80). Groupstoppedbeforemixed;preserving fresh focusedroot/phase with replay_focused.py. No qualifieddashcardsyet;onlyreplayworkeractive. DraftMegaKnight code remainsreport-only,notinactivepins.

- Dash830 reduces to803 lethal landing:Sourcecleanup on_combat_target_removed publishesold100ms preload,overwritingliteralfull cooldown before get_clock reseeds;Rust immediatelyreloaded600ms. Added deferredclock_reseed,cleanupcancellation,andread-onlylivependingreset export. References bandit.py:205-223;entities.py:1672-1720;ordinary_combat_clock.py:34-68;battle.py:2382-2394. Pinned root802/meta,clockwindow andnew180-tick regression;private29 building. NoSourcebehaviorchange.

- Private29 build0. Runningdash-r29 cumulative42methods/59controller plus16focused/12mixed,andc56-r29 88controls;only2heavyworkers. New clockpending bridge can affectliveimports,so full controls rerun. Donoteditcore/bridge/controller while either runs.

- Private29 cumulative42/88C56 pass andAssassin6 nowclearsold830,butdiverges1558 onretainedtarget only:Source158 targetCrown5,nativeNone. Reducing cancellation/retarget transition beforefix. Groupnotqualified;oldfailedreceipts remain.

- Dash1558 pinnedroot1557 confirms lost128 duringwindup;Source_current_charge_target selectsCrown5 andwrites target_id beforebandfailure/cancel. Nativeassignedonlyinsideacceptedband. Recordnewcandidate beforethebandcheck;new180-tick savedroot regression matches retainedCrown5. Referencebandit.py:116-149. Private30 building,workersidle,prior60 certificates preserved.

- Private30 build0. Two quickworkers run3dashreducers and16focusedcases first;no thirdprocess/no oldworkers. Fullcumulative/88C56/mixedgate follows ifthesenewcontrols pass. Focusedoutputwillberesumed on samepins byfullgate,notrerun.

- Private30 three newdashreducersPASS,includingbothsavedroots;focusedAssassin8passesandBossBanditprogressing. Started88C56 in freedslot. Atmost2heavy;fullgroupwillreusealreadycompletedfocusedreceipt onidenticalpins.

- Private30 focused16/16 passes, including both formerly failing Assassin6 transitions. Started dash-r30 full cumulative43 methods/59-controller then resumes existing focused receipt and12 mixed games. C56-r30 is the second worker. No new source edits until both finish.

- Dash group QUALIFIED frozen30:Assassin,BossBandit;16 focused/25276ticks,12 terminal/23724ticks,62 imports,257 placements,36.434x,maxclone4.520us,43 cumulative methods/controller59 plus88C56,0mismatches. Total62/66. Controller59 proof frozen before extension to61 eligible cards.
- Integrating Mega Knight spawn slam, interruptible charge, fixed800ms leap/300ms landing, ground target/above-ground roller split and deferred cooldown reset. References mega_knight.py:69-345,unit_traits.py:147-203,entities.py:3255-3264. Private31 build pending;new test_leap covers both seats,spawn attack,charge stun,Log andlive imports. All prior workers exited before edits;Python/data/default extension unchanged.

- Private31 build completes in2m13s with26s compiler CPU; no duplicate/compiler errors. After all workers exit, corrected owned run/build wrappers to keep a minimum niceness10 without adding10 at every nested invocation (previous heavy children reached20/30). Existing/protected processes untouched. Starting Mega Knight reducers before broader gates.

- leap-reduced-r31 detachedlaunch disappears before anyexit receipt;logempty andPID52457 no longerexists,no matchingworker. Retainedemptylaunchlog;retrylabel leap-reduced-r31b afterpsaudit,notaduplicate. Private31 pins unchanged.

- Private31 Mega Knight flight/landing/stun/Log reducer passes bothseats;spawn-slam liveimport continuation fails121. Retaining firstphase/root via leap_spawn_diagnose.py beforefix. Onlyoneowneddiagnosticworker;no C56/nativegroup gate started onfailing31. NoPythoncrash/referencechange.

- Spawn121 rootcause is separate SpawnPushback after MegaKnightSlam,not damage/scaling. Its1-tile character query uses serialized flying height and pushback-all,so nearbyGiant is displaced despite mass immunity. Added generic exportedspawn-push tuple/livefired state andnativehook afterslam;reference spawn_pushback.py:16-52,mechanic_detector.py:272-289. Savedroot120/meta/phase121 andnew180-tick regression retained. Private32 building;31unqualified,reference367 unchanged.

- Private32 build0 in36.52s after wrapperniceness correction. Two quickworkers runMega Knight3 methods/bothseats/imports and8 focused cases;broadergate waits for these. CurrentSource/privatepins fixed,62 priorcertificates remain.

- Private32 Mega Knight3 reducers PASS bothseats/imports,8focused PASS. Launchleap-r32 cumulative46 methods/controller61,existing focusedreceipt resume and12 mixed games;parallelc56-r32 88 controls. Atmost2nice10 workers,core/bridge/controller fixed until bothexit.62 priorcards stayqualified;Mega Knight notyetqualified.

- Mega Knight QUALIFIED frozen32:8 focused/14189ticks,12 terminal/30627ticks,79 imports,312 placements,44.756x,maxclone2.860us,46 cumulative methods/controller61 plus88C56,0mismatches. Total63/66. Controller61 proof frozen beforeaddingMegaKnight to62 eligiblecards.
- Integrating Fisherman wind-up, moving-target hook flight, next-object-frame drag, self-pull tobuildings, forced-movement flags/interruption andBandit/MegaKnight hook exceptions. References fisherman.py:67-334,entities.py:1608-1668,3732-3750. New test_hook coversbothseats/Cannon/Giant/Zap/live phases andsyntheticarrivalinsideBandittravel. Private33 building withallpriorworkers gone;Python/data unchanged.

- Private33 builds0. Fisherman buildingpull/stun/import controls pass bothseats;movingGiant defaultcase fails186 afterdrag. Retainphase/root viahook_diagnose.py beforefix. Onlydiagnosticworkeractive;no group/C56 gate onfailing33,noPythoncrash.63 priorcards retaincertificates.

- Hook186 firstHPdifference is early253 towerhit byGiant;itsclock had1000ms too much idleload afterforceddrag. Sourceordinary_combat_clock.advance setsload_work0 whenpreloadblocked+timeline0. Added Clock.advance_with_load(defaultadvance remainselapsed) andnativeordinarydue-path selection. Referencesordinary_combat_clock.py:105-128,entities.py:1648-1656. Savedroot185/meta/phase186 andfreshboth-seatGiantfixture retainregression. Private34 building;33unqualified,63 priorcards preserved.

- Private34 build0. Two quickworkers rerunFisherman3 reducers and8 focusedcases first;no broad gate beforethese pass. Allnative/source pins stayfixed,63 qualifiedcards unchanged.

- Private34 three hookreducers PASS (8 building/Giant/seat/stunfixtures,livephases,Bandittravel exception,saveddrag continuation). Focused0-5 pass;Fisherman6 fails935. Retaining freshfocusedroot/phase viareplay_focused before nextfix. No broad/C56gate onfailing34;all63 priorcertificates unchanged.

- Hook935 reduces to pending literalweaponreset whileFisherman11 startsanotherhookwindup. Sourceget_clock isnotcalled whilemechanic consumescombat;native reseededbeforehook andlosttimeline1250,so laterdeadtargetremoval missedfinish1. Movependingreset consumption afterspecial handlers (retainfinish/river-jump clockboundaries);normalhookforced-interrupt doesnotconsumeoldpendingwrite. Referencesentities.py:3720-3750,1672-1720,ordinary_combat_clock.py:50-68. Savedroot899/meta andnew180-tick regression;root934/phase935 retained. Private35 building;34unqualified,63priorcards preserved.

- Private35 build0. Two quickworkers runfourhookreducers and8focusedcases onfixedpins;onlyownednice10 workers. Broader51-method/controller62/C56/mixedgates wait until these pass.

- Private35 fourhookreducers PASS;focusedFisherman0-6 PASS including old935. Case7 fails2004;pin freshroot/phase withhook-replay-r35 beforefix. No broadgroup/C56worker active;63 priorcertificates remain.

- Hook2004 firstlatent2003: Fisherman188 hasneverenteredordinaryweaponpath beforehook/drag;SourceclockNone,cooldown1.3. Nativeplaceholderclocklookedfullyloaded andfired194early. Addedclock_initialized export/nativebit andlazyseedfromcurrentcooldown atactualweapon/finish/jump access;targetcleanup onlydiscardspendingwrite ifaSourceclock exists. Referenceordinary_combat_clock.py:34-68. Savedroot2002/meta/clockwindow andnew180-tick regression;root2003/phase2004 retained. Private36 building;35unqualified,63priorcards preserved.

- build36 detachedlaunch disappears withemptylog/noexit andnoPID262/compiler;verifiedpsbefore freshbuild36b retry. Sourcepinsfixed andprivate35 binary remains until successfulbuild. No duplicate/protectedprocess touches.

- Private36 build36b exit0. Two quickworkers rerunfivehookreducers and8focused cases onfixednewpins. No duplicateworkers;private36 notqualified untilallgates pass,63priorcards preserved.

- Private36 five hookreducers PASS,8focused PASS including former935/2004. Startedhook-r36 cumulative51 methods/controller62,focusedreceiptresume then12mixed;parallelc56-r36 88controls. Atmost2nice10workers,core/bridge/controller fixed until bothexit.63priorcards remainqualified,Fisherman notyetadmitted. Clone Arc-prototype draft prepared only inreportspace.

- Private36 broadergate FAIL:7C56 and4Stage6 failures fromautomaticinitialization altering established special/knockback weapon paths. Noqualification. Narrowedlazy-clock fix: preserveinitializedbit tokeep pendinghookwrites throughcleanup;reseed onlyexplicit pendingwrites,not everyuninitializednative placeholder. Hook interruption alwayscapturesfullliteralwrite ifSourceclockabsent. Frozen36unqualified;private37 building afterallworkers exit. All63oldcertificates remainonoriginalpins.

- Private37 repeats7 C56/4 Stage6 failures despite5 Fisherman reducers/8 focused passes. hook-push-r37.json isolates imported knockback: Source clears forced_movement_active at130; native retained it and first diverged131. Diagnostic clearing only that flag yields180 exact ticks. Fixed native push completion and added explicit180-tick flag/digest regression. Source entities.py:3603-3607. Build37 frozen unqualified; all workers exited before private38 build. Earlier claim that automatic clock initialization explained all broader failures is superseded by this evidence.

- Fisherman QUALIFIED frozen38:8 focused/17600 ticks,12 terminal/54188 ticks,138 imports,912 placements,44.568x,max clone7.600us,52 cumulative Stage6/controller62 +88 C56 +47 earlier P16/Stage2/Stage3/Stage5/5b tests,0 mismatches. Total64/66 incremental cards. Frozen62-card controller drivers before adding Fisherman to63 eligible. Clone/Mirror and final S122 gates remain open.

- Clone private39 implementation: fresh immutable Arc prototypes exported from separate oracle battles, immediate friendly nonclone recipient snapshot, surviving1HP shields, suppressed deployment hooks, cloned production/death/bomb descendants. References spells.py:701-737,battle.py:1923-2047,mechanics/shared/shield.py:18-29,spawner.py:187,death_effects.py:268,entities.py:7147. New both-seat/shield/recursive-payload regressions prepared; no Python-engine behavior changes. Previous workers exited before edits.

- Clone39 reductions pass Knight/DarkPrince/Witch/ElixirGolem/SkeletonBalloon/MegaKnight/LavaHound both seats and broken-shield/reclone exclusion, but BattleHealer live imports fail31 in both seats. Imported suppressed Clone spawn hooks were reconstructed from SpawnAreaEffect._applied=False, reintroducing the area. Export now also respects clone _spawn_hook_fired (battle.py:2031-2032). Frozen39-unqualified; bridge-only39b needs fresh receipts. No Python engine crash/change.

- Clone QUALIFIED frozen39b:8 focused/17600 ticks,12 terminal/47714 ticks,122 imports,765 placements,41.332x,max clone6.240us,54 cumulative Stage6/controller63 +88 C56 +47 earlier tests,0 mismatches. Total65/66 incremental cards; Mirror remains. Frozen63-card controller drivers before adding Clone to64 eligible. Beginning Mirror with all prior workers exited.

- Mirror private40 implementation captures accepted own card/cost, leaves rejected/Mirror commands out of history, resolves payment/placement from level12 card tables and retains qualified payload keys through spells, death/production/chain children and imports. Public native mask resolves Mirror from own history without changing Python scoring. References battle.py:1158-1194,1298-1305;player.py:30-32,79-96;public_action_mask.py:229-255. New tests cover no-history/insufficient-elixir rejection and both-seat bodies/spells/nested live imports. No Python engine/script changes.

- Mirror oracle inventory121 base predecessors: Clone/Earthquake/Poison/Tornado reject level12 resolution. Clone inheritance is unimplemented; the others have unresolved crown-damage overrides. This is a normal Python Mirror rejection, not a crash. Native exporter must omit those templates and native action/mask must reject them without payment/history changes. Recorded python-issues.json and mirror-oracle-inventory.json; no Source change. Private40 broad gate remains unqualified; prior controls still active before fix.

- Private40 prior controls PASS88 C56+47 earlier; Mirror not qualified because exporter attempted rejected level12 spells. Frozen40-unqualified. Private41 now preflights Mirror with its unchanged Python resolver, omits rejected templates, and rejects missing Mirror payloads in action/public mask without spending or history changes. Added explicit Clone/Earthquake/Poison/Tornado rejection tests. Human64 driver prepared with original frozen decks/seeds and200-tick imports, not run.

- Resume 2026-10-05 after T3 restart: ps shows no surviving Stage6 build/gate workers. Mirror actually finished before cancellation: sealed build41,58 cumulative methods,8 focused cases,12 terminal mixed games/43450 ticks,110 imports,603 placements,43.128x,max clone6.520us;88 C56+47 earlier controls pass. All66 cards now have incremental body/core certificates, but final S122 gates and SkeletonKing active summon remain open. No final human/planner receipt exists; no interrupted final gate is credited. Retain prior interrupted launches and start fresh labels for resumed work. Required instructions read; protected processes untouched.

- SkeletonKing active summon now exports its own ability state and source ring offsets, rejects activation below20 souls while preserving the misleading public-ready bit, charges the dynamic cost, consumes20 souls after spawning15 three-Skeleton groups, and updates active/cooldown timers. Shared death-swarm placement preserves45 bodies and both-seat/lane behavior. References champion/skeleton_king.py,champion/ability.py,effects/spawn.py. GoldenKnight has no ability in the oracle. Added Mirror to the opt-in controller roster after its sealed certificate. Private42 build/reduced gates pending;Python behavior unchanged.

- Build42 compiler rejected the missing Skeleton enum death arm; no replacement occurred. Added explicit no-op matching inherited Python death behavior and retained build42.log/exit101. Fresh build42b retry; old empty build36/build37/leap-reduced-r31 launches already have completed superseding receipts and are not credited. No interrupted current gate found.

- Private42b build exit0. Started skeleton-reduced-r42 through detach as the only owned heavy worker; broad/final gates wait for this reducer. Added final_controls.sh to rerun every cumulative Stage6 reduction/controller test plus88 C56/47 earlier controls on final pins. Mirror ranking fixture now creates accepted history before deployment.

- SkeletonKing/GoldenKnight reducer PASS2 methods in42.163s, both seats with0/19/20/30 souls, exact45-body summon/payment/timers and100-tick live-import continuations. Started final-controls-r42 (60 cumulative methods/controller65 then88 C56/47 earlier) and human-r42 (frozen64+optional32 human-deck schedule) as two detached nice10 workers. Core/bridge/controller pins fixed until both exit. No final admission yet.

- Private42 reference audit PASS367 protected files. Cleaned128MiB owned idle Cargo intermediates and13 superseded unqualified binaries, retaining their source/pin/failure receipts and all qualified frozen builds. resume-r42-audit.json records deleted binary hashes. Human/control workers remain pinned; no protected process touched.

- Prospective numeric-threshold reserve frozen before any reserve game: human128-reserve.json repeats every original human64 episode in unchanged order with fresh paired seeds669000+pair then670000+pair. Use only if original64+32 miss1000 imports/4000 placements/coverage, stopping at first qualifying pair boundary. No deck/outcome selection or original-driver changes; current human/control workers continue fixed.

- Human-r42 has passed its first64 terminal games; current passing count69, imports871, placements2224. All66 required cards played. Numeric thresholds still pending, so the original frozen32 supplement runs in order. Froze private42 source/binary under build42/; prepared human_reserve.py to preserve all96 originals if reserve is required, and seal_final.py to reject mismatches/missing receipts while explicitly withholding full admission for ThreeMusketeers controller failure. Final controls still active; no source changes.

- Private42 cumulative60 Stage6/controller65 methods PASS in482.920s;88 C56 then47 earlier controls continue in the same worker. Human gate passed64 originals and is processing the supplement with no mismatches. Prepared separate SkeletonKing edge/centre-ring test for8 seat/position fixtures; it will run in a freed slot before final seal. Updated user AGENTS instructions acknowledged; no remote work or unrelated-process action needed.

- Original human64+32 COMPLETE:96 terminal games,1162 live imports,2919 public-legal accepted placements,all66 cards,0 mismatches,45.443x stepping,max clone17.610us. human-r42 exits1 solely because4000 placements are not yet met; retain this complete receipt, do not rerun its games. Frozen reserve will append when a slot frees. Started planner-suite-r42 in the freed human slot:8 SkeletonKing edge/centre-ring fixtures then100 searchable planner calls over10 late mechanics, includingMirror/Clone/SkeletonKing. Earlier controls remain the second worker.

- Skeleton edge fixture failed before four deployments because centre x8.5/9.5 at y4.5/27.5 overlaps the King tower. This is a test placement error, not a parity mismatch/Python crash; four outer-edge fixtures passed. Retained failed fixture/log/exit under r42, corrected all8 fixtures to legal y13.5/18.5, and retry as planner-suite-r42b on unchanged native/source pins. Planner itself has not run yet.

- Private42 final controls COMPLETE exit0:60 cumulative Stage6/controller65 methods,88 C56 and47 earlier P16/Stage2/3/5/5b tests,0 failures. Started human-reserve-r42 in the freed slot, preserving all96 original human results and their exact driver/source/native hashes. Planner-suite-r42b remains the second worker, currently checking corrected SkeletonKing edge fixtures. No source/private changes.

- Interrupted launch incident: planner-suite-r42b PID33881 vanished with an empty log and no wrapper/edge/planner exit receipts. ps confirms no matching Python child or planner remains. Discard this incomplete run entirely; no edge/planner credit. Preserve empty r42b.log and retry the whole corrected edge/planner chain under fresh planner-suite-r42c, unchanged source/native/test pins. Human reserve is still the only surviving owned heavy worker.

- Resume 2026-10-05T20:39:40Z (coordinator agent on f35 via ssh): the previous coordinator SIGSTOPped groups 41247 (human-reserve-r42) and 43204 (planner-suite-r42c) at about 07:49Z for about 12 h 50 min. Both were SIGCONTed unchanged. No rerun was needed: these drivers are deterministic parity gates, and their timing gates (stepping speed, clone us) use time.process_time, which a stop does not advance. human-reserve-r42 then exited 0 at 20:41Z: 136 terminal human-deck games, 1617 imports, 4017 placements, missing cards none, 45.447x stepping, max clone 17.610us, passed=true (original 96 games plus reserve appended in frozen order). planner-suite-r42c: skeleton edges exit 0, then planner-r42c FAILED at call 36, Fisherman-1-100 (seat 1, tick 100), after 35/100 PASS. AssertionError planner action/score/trace mismatch: score index 3 differs (py -0.0027909 vs rs -0.0016210), and trace 25 (pressure rollout, candidate action 806) diverges in rollout state digests. score_candidates runs without a deadline, so this is a genuine Fisherman seat-1 rollout parity defect, not an interruption artifact. Retained planner-r42c.json (35 passes), planner-r42c.failure.json/.pkl, planner-suite-r42c.log and exit 1. No source, private-build or test changes. Stage 6 is now waiting on a native fix (reduce from failure.pkl), then a fresh planner label. Human-reserve and final-controls receipts stay valid only on unchanged pins. No Stage 6 worker running.

## Build43 final-gate repair

The retained Fisherman seat1 pressure rollout first loses public parity at tick189, entity12 HP678 Python versus484 Rust. Zap at120 prematurely marked Fisherman17's ordinary clock initialized. Target7 death at186 then discarded the full1300ms hook reset; native started timeline1250 instead of50 at188. Removed stun_target_mode's consume_clock_reseed call, matching Python apply_stun. New both-seat test fails the old binary at121 and passes build43 through260 ticks plus180 imported ticks; all6 earlier Hook methods also pass. Root-cause evidence is stage6/hook-root-cause-r43.json.

The checkout already includes reviewed cleanup commit2def50e8d, changing23 protected Python hashes through unused import/binding removal. Exact parent/current matches and inspected changes are recorded in reference-cleanup-r43.json; historical entry/root hashes remain intact. No Python/data/admitted extension changes by this worker. Fresh identity and all final core gates are running; no admission claim yet.

Build43 then failed planner call51, Mirror-0-100, after50 exact calls. Every action/digest/MT trace matched, but24 rollout leaf scores differed. Ordinary level12 templates used the base mana cost; Python Mirror bodies carry the copied cost plus1. Build44 exports body and clone-prototype leaf shares from actual oracle Mirror formations, preserving independent secondary-body costs. Both-seat Knight/Archers/Witch/Cannon leaf fixtures fail build43; corrected build44 also passes GoblinGang secondary-body and Clone/import controls. Evidence: stage6/mirror-root-cause-r44.json. Fresh62-method controls, full planner, human/reserve and identity gates are running on build44.

Build45 passed64+88+47 controls,200 Stage5 roots,100 Stage6 planner calls,136 human games andfour identity modes. Its subsequent independent recorded replay failed at1895, so build45 is not qualified. InfernoDragon incorrectly targets a travelling BossBandit; Python continuous-damage channels reject that recipient. The failed independent receipt and historical seal are retained. Build46 repair and fresh gates are pending.

### 2026-10-08 01:45 UTC — shared-tree overwrite; exact build48 isolated retry
At~01:39UTC shared127x01checkout Rust lib.rs/hook.rs were reverted to46 and4reportdrivers overwritten (final_controls.sh,seal_final.py,independent_human.py,independent_recorded.py). Planner stopped37/100 andhumanreserve110games at source-fingerprint guard; NOparitymismatch. Preserved overwrittenfiles/audit in stage6/shared-tree-overwrite-20261008T0139. Cancelled remaining verifiedowned48workers, audit cancel-invalidated-r48-linux.json; allpartial/failure receipts retained. Did NOTtouchmirror/C56/S1/v4 jobs. Usernotified andaskedmirrorexclusion.
Created127x01 `/mpac/sdicks02/repos/clasher-stage6-build48` with separate source/engine-speed files and read-only shared-data links. Restored Rust from immutablebuild48archive and gate drivers from exact pinned local/03copies. Isolatedaudit proves SAMEsource e83c8e1fcfbae35d406f7d8058dc71e01b48472ec721ff50b1a9aab9ec6799d4, native78bd9950f1059bddbc2b2d2487158ff5dc51c722500c02969ec100efe1930689, allfrozendriverhashes,367protectedfiles. Nativecode unchanged; environmental retry usesbuild48 withsuffixr48b-linux.
All5core gates restartedfresh in isolatedtree, max6computeworkers/nice10/whoempty: {"stage6-stage5-r48b-linux-20261008": {"host": "127x01", "pid": 3369444, "root": "/mpac/sdicks02/repos/clasher-stage6-build48"}, "stage6-planner-r48b-linux-20261008": {"host": "127x01", "pid": 3369452, "root": "/mpac/sdicks02/repos/clasher-stage6-build48"}, "stage6-controls-r48b-linux-20261008": {"host": "127x01", "pid": 3369466, "root": "/mpac/sdicks02/repos/clasher-stage6-build48"}, "stage6-human-r48b-linux-20261008": {"host": "127x01", "pid": 3369482, "root": "/mpac/sdicks02/repos/clasher-stage6-build48"}, "stage6-identity-r48b-linux-20261008": {"host": "127x01", "pid": 3369504, "root": "/mpac/sdicks02/repos/clasher-stage6-build48"}}. Independent48+24PASS remainsvalid onUNCHANGED03 andsame48pins, all66coverage. Next monitor r48bcore receipts in ISOLATEDtree; seal via fleet_seal48b.py afterallpass. MainhubRust currentlyold46; authoritativebuild48source is isolatedtree/build48archive and03. Mirroronlydocs/smallJSON05.

### 2026-10-08 01:55 UTC — coordinator incident audit and per-gate disposition
Coordinator confirmed unrequested Macrsync overwrite01:39–01:45. Audited EVERYbuild46andactive48 source/native pin, driver pin, both frozenindependentplans and theirsourcepins, plus367protectedfiles on01and03. Fullhash ledgers mac-push-hash-audit-127x01-20261008.json / ...127x03.... 01build46/48archive mismatches0; protected/planmismatches0. Active01 had2Rust+4driver bytechanges, nowrestoredEXACT48 at01:54:11 (mac-push-restoration-20261008.json). NoPython/data/baseline change. 03active48source/native/independentdrivers/plans unchanged. 03neverhad46archivebodies orunusedcorehelperupdates; auditrecordsabsence explicitly, notcorruption.
Per-gate disposition (also machine-readable mac-push-gate-disposition-20261008.json):
- build46/build47 receipts: Pre-incident; retain as historical evidence. Native mismatches independently block those candidates; no incident reclassification.
- build48 freeze / saved-root regression: Finished before incident; archived source/native and passing reduction receipts stand.
- build48 independent recorded48 + human24: Finished before01:39 on unchanged127x03; exact source/native/driver/plan hashes verified afterincident; PASS stands.
- stage5-200-r48-linux: Finished before01:39 with verified pins;200/200PASS stands; also rerunning fresh r48b.
- identity P16/C56 r48: Finished before01:39;12/12 and7/7PASS stand; entire identity group reruns fresh r48b.
- human-r48-linux original96: Finished before01:39;96/96parityPASS stands; numeric placementdeficit expected. Entire human/reserve reruns fresh r48b.
- planner-r48-linux: INVALID: source changed at01:39:20; fingerprint guard stopped after37persisted passes. Preserved receipts; fresh r48b retry.
- human-reserve-r48-linux: INVALID: source changed at01:39:20; guard stopped after110persisted passing games. Preserved receipts; fresh r48b retry.
- final-controls-r48-linux: INVALID as aggregate: Stage6 69methods ended01:39:15, C56started01:39:15 and ran across Rust overwrite; earlier47notstarted. Conservatively rerun all69+88+47 under r48b.
- identity-recorded-r48-linux: INVALID in-flight group across overwrite; onefinished row preserved, all8replay fresh r48b. Random hadnotstarted.
- seal_final build48: Not run; await all fresh r48b core gates plus unaffected independent48PASS.
- r48b-linux groups: Fresh at isolated root after exact hash audit; no changed inputs under these workers. All5groups running, max6compute,nice10.
Authoritative runtime remains isolated `/mpac/sdicks02/repos/clasher-stage6-build48`; mainhub Stage6source/drivers restored48too. Sharedfleet scripts notusedbyStage6were notmodified; fleet_run.sh unaffected. r48b labels/PIDs remain in core-launches-r48b-linux.json.

### 2026-10-08 02:01 UTC — isolated r48b core milestones
Fresh isolated Stage5passed200/200; P16identity12/12 andC56identity7/7passed; Stage6regressions69/69passed (927.75swrapperwall). C5688nowrunning child3379173,earlier47follow. Originalhuman96/96paritypassed (1162imports,2919placements,66cards,37.2699xspeed,maxclone16.81326us); reserve109totalgamespassing. Planner37/100passing. Firstrecordedidentitygamepassed;2workerscontinue. No sourcefingerprintdrift orparityfailure in isolatedtree. Labels/PIDsremain core-launches-r48b-linux.json; next finishremaininggatesand fleet_seal48b.py.

### 2026-10-08 02:04 UTC — isolated human/reserve PASS
Fresh r48b human/reserve passed136terminalgames,1617liveimports>=1000,4017acceptedplacements>=4000,66/66cards,36.9799xstepping>=30,maxclone16.81326us<20. Corrected100-cloneprocessCPUdriver unchanged. Fullreceipt isolatedstage6/human-reserve-r48b-linux.json; small hashedsummary human-summary-r48b-linux.json mirrored05. Fleet stage6-human-r48b-linux-20261008 exit0. Planner46/100passing;C5688/earlier47andremainingidentitypending. Source/nativepins unchanged.

### 2026-10-08 02:07 UTC — isolated final-controls PASS
Allfreshbuild48/r48b controls completed69Stage6+88C56+47earlier=204methods,0failures; fleet stage6-controls-r48b-linux-20261008 exit0 at02:06:48. controls-summary-r48b-linux.json binds aggregate logSHA. Stage5andhuman/reserve alreadyPASS; expandedindependent48+24PASS unchanged03. Remainingplanner57/100 andrecordedidentity3/8;random24followsrecorded. Next finishthese2groups, then fleet_seal48b.py; runtimepins fixed.

### 2026-10-08 02:21 UTC — isolated planner100 PASS
Fresh planner-suite-r48b-linux exit0:100/100 searchablecalls,10focalcards×bothseats×5liveages, 2194candidates,0candidate/action/score/trace mismatches; parentrootpreservation passed. SkeletonEdges8/8alsoPASS. Allremainingwork isidentity:7/8recordedgamespassed (0..6),game7running,then24randomgames. AllothergatesPASS incl72expandedholdouts/all66cards. Next identityexit0 thenfleet_seal48b.py.

### 2026-10-08 02:32 UTC — build48 private core qualified; full Stage 6 blocked

All requested native parity gates passed and are sealed on `build48-linux`. Source fingerprint: `e83c8e1fcfbae35d406f7d8058dc71e01b48472ec721ff50b1a9aab9ec6799d4`. Native SHA: `78bd9950f1059bddbc2b2d2487158ff5dc51c722500c02969ec100efe1930689`. Archive pins SHA: `10c6a5e0514b4a5a310b2bea691cc5903969896165327fb3a6bf838e919e5055`.

| Gate | Result | Pass bar |
|---|---|---|
| Stage 5 | 200 roots, 3,993 candidates | 200 roots; zero mismatches |
| Planner suite | 100 calls, 2,194 candidates; SkeletonEdges 8/8 | 100 calls; zero candidate/action/score/trace mismatches |
| Final controls | 69 Stage 6 + 88 C56 + 47 earlier methods | All pass |
| Human/reserve | 136 terminal games, all 66 cards, 1,617 imports, 4,017 placements | At least 64 games, all cards, 1,000 imports, 4,000 placements |
| Performance | 36.9799x stepping; maximum clone time 16.81326 us | At least 30x; below 20 us |
| Four-mode identity | P16 12/12; C56 7/7; recorded 8/8; random 24/24 | Zero mismatches |
| Expanded independent verification | 48 recorded + 24 human games, 258,992 ticks; all 66 cards accepted | 72 terminal games; all 66 cards; zero mismatches |

Independent coverage totals 1,106 accepted Stage 6 plays, with at least two per card. The complete per-card counts are in `stage6/independent-summary-r48-linux.json`. The plans retain the pre-registered seed and selection rule; no cases were replaced after failures.

`seal_final.py` passed under fleet label `stage6-seal-r48b-linux-retry2-20261008`. The first aggregation-wrapper attempt stopped before invoking it because human receipts use a `drivers` map while recorded receipts use a singular `driver` field. That wrapper and its failed receipt are preserved. Only the unpinned aggregation wrapper was corrected; gate drivers, source, native binary, and results were unchanged.

Final receipts: `stage6/qualification-r48b-linux.json`, `final-r48b-linux.json`, `completion-audit-r48b-linux.json`, `independent-summary-r48-linux.json`, and the human/planner/controls/identity summary JSON files for `r48b-linux`.

The Rust repairs beyond draft46 clear DamageRamp locks on Fisherman drag, cancel a flying hook immediately when its spirit target becomes projectile-kind, reset Valkyrie's preload flag after a committed hit triggers Golem death knockback, and pause acquisition preload during interrupting pushback. Build46's four independent failures and build47's residual Valkyrie failure are preserved. Three new regression methods cover four saved-root cases and pass on build48. BeamDash's five pre-fix failures are preserved; its synthetic cases and saved tick1895 pass on builds46 and48.

The Mac push incident was audited by hash. Affected gates were invalidated and rerun under fresh `r48b-linux` labels in `/mpac/sdicks02/repos/clasher-stage6-build48`. Main-hub source and drivers were restored to exact build48 bytes. The completion audit verified both roots and all 367 protected files in each. The independent run finished before the incident on unchanged 127x03, and its pins were rechecked afterward. Per-gate dispositions are in `mac-push-gate-disposition-20261008.json`.

All owned gate jobs have finished. Full receipts also exist in the main hub's `engine-speed/stage6` directory; documentation and small JSON receipts are mirrored to 127x05. Python engine, gamedata, and admitted baselines were not edited. No commits or pushes were made.

**Verdict: private Stage 6 core QUALIFIED. Full Stage 6/S122 admission remains BLOCKED solely by the unchanged ThreeMusketeers Python controller `float(None)` exception (65/66 new controller cards).** The seal retains `final_s122_admitted=false`. No authorized gate work remains; the coordinator can review and commit the Rust/report changes. Repairing the Python oracle is outside this task.

Expanded independent accepted-play coverage (fixed pre-registered plans; full attempts/deck counts in independent-summary-r48-linux.json):

| Card | Recorded | Human | Total |
|---|---:|---:|---:|
| Assassin | 23 | 10 | 33 |
| AxeMan | 6 | 6 | 12 |
| BarbarianHut | 0 | 4 | 4 |
| Barbarians | 12 | 0 | 12 |
| BattleHealer | 0 | 2 | 2 |
| BattleRam | 26 | 6 | 32 |
| Bomber | 16 | 0 | 16 |
| BossBandit | 9 | 0 | 9 |
| Bowler | 47 | 0 | 47 |
| Clone | 6 | 7 | 13 |
| DarkMagic | 0 | 12 | 12 |
| DarkWitch | 28 | 10 | 38 |
| DartBarrell | 12 | 0 | 12 |
| ElectroDragon | 8 | 6 | 14 |
| ElectroGiant | 14 | 0 | 14 |
| ElectroWizard | 6 | 10 | 16 |
| EliteArcher | 8 | 0 | 8 |
| Elixir Collector | 0 | 8 | 8 |
| ElixirGolem | 8 | 0 | 8 |
| Fisherman | 23 | 8 | 31 |
| Freeze | 27 | 0 | 27 |
| GiantBuffer | 2 | 0 | 2 |
| GiantSkeleton | 18 | 6 | 24 |
| GoblinCage | 14 | 0 | 14 |
| GoblinCurse | 0 | 6 | 6 |
| GoblinDemolisher | 11 | 0 | 11 |
| GoblinDrill | 0 | 10 | 10 |
| GoblinGiant | 0 | 4 | 4 |
| GoblinMachine | 0 | 4 | 4 |
| GoldenKnight | 14 | 18 | 32 |
| Graveyard | 18 | 0 | 18 |
| Heal | 14 | 10 | 24 |
| Hunter | 36 | 3 | 39 |
| IceWizard | 20 | 4 | 24 |
| InfernoDragon | 24 | 10 | 34 |
| LavaHound | 4 | 0 | 4 |
| LittlePrince | 14 | 0 | 14 |
| MegaKnight | 0 | 17 | 17 |
| MegaMinion | 4 | 4 | 8 |
| MergeMaiden_Normal | 6 | 0 | 6 |
| MiniSparkys | 26 | 4 | 30 |
| Mirror | 0 | 2 | 2 |
| Monk | 2 | 0 | 2 |
| Mortar | 44 | 10 | 54 |
| MovingCannon | 16 | 0 | 16 |
| Pekka | 8 | 0 | 8 |
| Phoenix | 0 | 12 | 12 |
| Rage | 8 | 2 | 10 |
| RageBarbarian | 18 | 12 | 30 |
| RamRider | 4 | 0 | 4 |
| Ronin | 4 | 8 | 12 |
| RoyalGiant | 23 | 7 | 30 |
| RoyalRecruits | 8 | 0 | 8 |
| SkeletonBalloon | 30 | 9 | 39 |
| SkeletonDragons | 6 | 8 | 14 |
| SkeletonKing | 8 | 0 | 8 |
| SkeletonWarriors | 25 | 0 | 25 |
| Snowball | 20 | 18 | 38 |
| SpearGoblins | 0 | 2 | 2 |
| SuspiciousBush | 8 | 4 | 12 |
| ThreeMusketeers | 0 | 13 | 13 |
| Tombstone | 14 | 4 | 18 |
| Vines | 0 | 12 | 12 |
| Witch | 14 | 0 | 14 |
| WitchMother | 20 | 8 | 28 |
| ZapMachine | 2 | 0 | 2 |
