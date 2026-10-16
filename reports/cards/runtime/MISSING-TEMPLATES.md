# Public-object template closure (exploration tier)

Corrected class gate PASS:122 definitions/366 scenarios,96,171 checks,zero exceptions. Actual-root release gates remain pending. No sealing.
Sam’s updated 2026-10-16 routing permits reviewed opt-in release after real gates pass; active live pins remain LIVE-owned.

## Root cause and implementation

`Resources` registered exported templates from source card names, stopped walking when it encountered an entity,
and relied on 201-tick demonstrations sampled every tenth tick for the rest. That loses the exact public sensor
identity of a nested death/spawn object and misses short-lived objects. Lumberjack's one-tick
`BarbarianRageDamage/AreaEffect` is the reported example; it is nested inside the death container/buff chain.

`differential.entity` now exports the public sensor's ordered typed identity candidates, including the
TimedExplosive and ChainLightning namespace exceptions. It also exports static translator columns.
`Resources` recursively registers these exact identities after the original registration and demos, with
`setdefault`: every existing template retains priority. The full-scope merge remains base-first. This increases
the current full runtime's template table from 350 to 355 without changing the native binary or vocabulary.

The translator completes its measured vocabulary from runtime templates, preserving every existing row and
mapping. A `(token, kind)` registry covers exact child identities; missing source-card/motion rows use that
card's deterministic primary public carrier. This is a public-model prior, not new external visibility evidence.
The assembler now exports and overlays the committed `fair_player.py` as well as engine-cards, rather than
inheriting that file silently from the base runtime.

LIVE code remains read-only. Its independent vocabulary loader/constructor needs
[the supplied patch](patches/live-template-vocab.patch) to call the shared completion helper.
`bot/live/levels.py` uses the completed `R.templates`; no change to its duplicate template lookup is needed.

## Class gate and scope

[object_templates_probe.py](tools/object_templates_probe.py) audits all 122 ladder definitions, both seats,
Python deployment and stepping, and actual native `apply_action` deployment and stepping. It uses combat groups,
champion activation, repeated lethal damage, and 75-second lifetime scenarios. Python insertion journaling retains
objects that disappear inside a step; native objects are inspected at every tick boundary. Exact object IDs,
classes, source cards, names, buff-record families and table checks are retained in JSON receipts.

Each observed object must resolve in the typed vocabulary, Resources templates, translator objects/statics and
body metadata/script tables where applicable. Public sensor rows and full boards are passed through root
construction, native stepping/evaluation, and LIVE's level-aware duplicate root path. A recursive config audit
also checks nested child and Mirror templates that a particular combat trajectory does not emit.

Assumption: the existing action scope stays unchanged. Spirit Empress (`MergeMaiden`) has an UNK action token,
is excluded by `bot/cards/scope.py`, and its current Python compatibility deployment creates no objects. The probe
records that zero-object deployment; it does not send an empty formation to native or claim native action support.
All other admitted actions, including ladder aliases, use native deployment. Per-entity haste/slow/periodic buff
records are not standalone public objects and do not perform token/template lookups; their presence is inventoried.

## Runtime lookup audit

The [140-match source audit](receipts/missing-templates-lookup-audit.txt) covers per-object lookups and related
identity guards in the requested runtime/public-model trees. Relevant paths and dispositions:

| Runtime path | Per-object table | Disposition / coverage |
|---|---|---|
| Public sensor `_runtime_entity_token_id` | Typed vocabulary and ordered identity candidates | Export exact sensor ordering into config; every observed key must be typed |
| `fair_player.Resources.root` | `(token, public kind)` templates | Recursively complete nested exported identities; both-seat roots and native constructors |
| LIVE `LevelRoot.payload` | Same `R.templates` | Completed centrally; both-seat level-aware roots exercised; LIVE source read-only |
| Full card scope | Base/full templates | Preserve existing base-first merge and all previously registered entries |
| RoyaleSim vocabulary loaders | Units, spells, projectiles, statics and exact object registry | Shared completion; measured entries retained; separate LIVE two-call patch |
| Translator `_rows` / `_resolved_rows` / `_row` | Source selection, exact registry, templates and static columns | Every finite source mapping plus every exact observed carrier, both seats; documented parent aliases |
| Public scripted opponent and `c56_controller.metadata` | Token bodies, metadata body names and script styles | Equal Python/native checks for every observed troop/building; actual body/ranking paths in None audit |
| Native config and side cut | Exported child payloads and source-card labels | Recursive config identity census plus native deployment, callbacks, tick inventory and projected public board roots |

Other matched guards reject invalid confidence, schema, settings or source-build input. Buff records are
inventoried separately from public objects. Historical synthetic projectile-template kind aliases remain
unchanged to preserve C56 output; constructor signatures must match their existing frozen templates. This
is lookup/root totality evidence, not a new mechanics or perception-equivalence certification.

## Object / card / table / fix

Original r2 has350 templates; the candidate has355. The five missing exact identities are:

| Object | Card | Table | Fix |
|---|---|---|---|
| BarbarianRageDamage / AreaEffect | RageBarbarian (Lumberjack) | Resources, public model, translator statics/carriers | Recurse death buff chain; retain exact sensor identity |
| RageDamage / AreaEffect | Rage | Same | Recurse nested damage effect |
| GoblinDrillDamage / AreaEffect | GoblinDrill | Same | Register exact spawn effect |
| IceWizardCold / AreaEffect | IceWizard | Same | Register exact spawn effect |
| ElectroWizardZap / AreaEffect | ElectroWizard | Same | Register exact spawn effect |

Translator completion covers355 object/static rows (267 new statics),142 canonical unit mappings (95 new),
45 projectile source mappings (21 new),204 spell/motion mappings (187 new). Existing rows retain priority.
Actual source-motion outputs can be parent carriers rather than their nested damage child: the corrected probe
records these aliases separately and exercises each exact child through the shared production formatter.
The inventory below is regenerated from the accepted complete corrected full-class receipts; the earlier development evidence remains separate.

Corrected five-object pilot receipt: `receipts/missing-templates-pilot-ad961ee93.json` (approved sourcead961ee93).
All five exact objects passed the production translator formatter and projected board R.root/LIVE-level root
for both seats, and each materialized in the native constructor before stepping:

| Exact child | Both-seat formatter / native board | Native gameplay tick-boundary emission | Actual source-motion mapping |
|---|---|---|---|
| BarbarianRageDamage27 | PASS | Observed | Parent BarbarianRage26 (nested child identity unavailable in source schema) |
| RageDamage269 | PASS | Observed | Parent Rage264 |
| GoblinDrillDamage147 | PASS | Within-step birth, not observed at native boundary | Exact147 |
| IceWizardCold200 | PASS | Within-step birth, not observed at native boundary | Exact200 |
| ElectroWizardZap88 | PASS | Within-step birth, not observed at native boundary | Exact88 |

No child identity is inferred from a coarser external row. Exact carriers share the production formatter;
source-motion selection is tested separately and retains the parent aliases above. Native constructor
materialization of all five is recorded separately from native gameplay emission.


## Gates and releases

Accepted receipts retained independently:

| Gate | Result | Receipt |
|---|---|---|
| K4L HEADLINE | 12/12 identical command hashes | receipts/missing-templates-k4l.json |
| Assembler original safety/overlay | 11/11 PASS | receipts/missing-templates-assembler-tests.txt |
| Assembler review regression | 12/12 PASS | receipts/missing-templates-assembler-review-tests.txt |
| Full-pool None-stat audit | 55,834 checks, zero exceptions | receipts/missing-templates-none-stats-dev.json |
| C56 ranking parity | 8,496/8,496 identical | Same None-stat receipt |
| Game5000110 r2 negative control | Exact BarbarianRageDamage failure reproduced | receipts/missing-templates-replay-5000110-r2.json |
| Initial class run | Development only:122 definitions/366 scenarios,56,354 checks,0 errors; coverage gaps | receipts/missing-templates-class-dev.json |
| Corrected class run | PASS122/366,96,171checks,0exceptions;187observed/187materialized;142/142configidentities | receipts/missing-templates-class-ad961ee93.json |

Independent implementation review APPROVE binds checkpoint1802e899cea14807f659ee234dcd67839b392f46;
its full brief, findings and hashes are in receipts/missing-templates-implementation-review-1802e899c.json.
Host-script approval is separate. Final release helper, totality helper and end-to-end release protocol have independent approval; actual corrected class acceptance, accepted-main integration and host prerequisites remain required. Native full-board checks are projected synthetic carrier stress, using only
public entity columns with a normal HUD/global scaffold. Native constructor materialization and native gameplay
emission are recorded separately, especially for within-step spawn effects. Corrected probe checkpointad961ee93 changes only its synthetic source catalogue to cover vocabulary body aliases;
production code remains approved at1802e899c. The failed startup attempt and superseded queues are retained in the scoped audit.
No r3 roots are published yet;
no release verification receipts exist on03/04/08. Publication awaits accepted main integration and host prerequisites; final acceptance requires actual-root gates,
with rollback by choosing untouched r2 roots. Candidate PIN_SETS entries do not change defaults or active pins.

All work uses `/mpac/sdicks02/jobs/clasher/cards/missing-templates-r3`, nice 15,
`PYTHONHASHSEED=0`, `PYTHONDONTWRITEBYTECODE=1` and one thread per numerical library. Compute on 04/08 is admitted
through `bot/exit/cpu_job.sh` with leases no larger than four. Existing runtime roots are immutable inputs.

## Accepted class inventory (187 observed keys)

Complete four-shard sweep:122 distinct definitions/366 completed scenarios, both seats and both engines,
450 combat/450 death/1,500 lifetime ticks. Native actions retain the explicit121/122 frozen-v5 exclusion.
All142 config identities observed; all187 observed keys materialized by native constructors; zero native-only
inventory omissions (native-only keys in this run:0). Seven keys appear only in Python birth journaling rather
than native tick snapshots: GoblinDrillDamage,IceWizardCold,ElectroWizardZap and HealSpiritProjectile,
IceSpiritsProjectile,ElectroSpiritProjectile,FireSpiritsProjectile. Allseven still pass native constructor/root
and lookup checks. There are157 inherited synthetic projectile-kind aliases; their frozen signatures remain.

Native table checks include3,610 templates,3,610 typed identities,3,610 statics,3,610 exactregistry checks,
7,220 exactformatter seat checks,1,812 body/name checks and5,436 scriptedbody checks. Source-mapping checks
3,144; public/native full-board checks5,856 each; individual public/native root checks464/448. Five repaired
areas pass10 exactformatter seat paths and10 fullnativeboard seat paths. Source aliases and within-step
native-emission limitations stay explicit above. Buff occurrences:haste2,261/slow4,276/periodicdamage1,236;
these are per-entity records, not standalone public tokens.

The card column records scenarios observing the object, including common target fixtures and Crown towers;
it is not an inferred source-card identity. The five-defect table above gives the exact originating cards.
All122 scenario lists and engine/class/name/mode provenance are retained in the linked machine receipt.

| Object / kind | Card scenario(s) observing it | Table / fix |
|---|---|---|
| Balloon / AreaEffect | Balloon | Existing template/static rows retained |
| BarbarianRage / AreaEffect | RageBarbarian | Existing template; translator static/carrier completion |
| BarbarianRageDamage / AreaEffect | RageBarbarian | Resources recursive exact template; translator static/carrier completion |
| BattleHealerSpawnHeal / AreaEffect | BattleHealer | Existing template; translator static/carrier completion |
| BombTower / AreaEffect | BombTower | Existing template/static rows retained |
| DarkMagic / AreaEffect | DarkMagic | Existing template; translator static/carrier completion |
| Earthquake / AreaEffect | Earthquake | Existing template/static rows retained |
| ElectroDragonProjectile / AreaEffect | ElectroDragon | Existing template; translator static/carrier completion |
| ElectroSpiritProjectile / AreaEffect | ElectroSpirit | Existing template/static rows retained |
| ElectroWizardZap / AreaEffect | ElectroWizard | Resources recursive exact template; translator static/carrier completion |
| Freeze / AreaEffect | Freeze | Existing template; translator static/carrier completion |
| FreezeIceGolemite / AreaEffect | IceGolemite | Existing template/static rows retained |
| GiantSkeleton / AreaEffect | GiantSkeleton | Existing template; translator static/carrier completion |
| GoblinCurse / AreaEffect | GoblinCurse | Existing template; translator static/carrier completion |
| GoblinDrillDamage / AreaEffect | GoblinDrill | Resources recursive exact template; translator static/carrier completion |
| Graveyard / AreaEffect | Graveyard | Existing template; translator static/carrier completion |
| HealSpirit / AreaEffect | Heal | Existing template; translator static/carrier completion |
| IceWizardCold / AreaEffect | IceWizard | Resources recursive exact template; translator static/carrier completion |
| Lightning / AreaEffect | Lightning | Existing template/static rows retained |
| MightyMiner / AreaEffect | MightyMiner | Existing template; translator static/carrier completion |
| Poison / AreaEffect | Poison | Existing template/static rows retained |
| Rage / AreaEffect | Rage | Existing template; translator static/carrier completion |
| RageDamage / AreaEffect | Rage | Resources recursive exact template; translator static/carrier completion |
| SkeletonBalloon / AreaEffect | SkeletonBalloon | Existing template; translator static/carrier completion |
| SuspiciousBush_DummyAEO / AreaEffect | SuspiciousBush | Existing template; translator static/carrier completion |
| Tornado / AreaEffect | Tornado | Existing template/static rows retained |
| Vines / AreaEffect | Vines | Existing template; translator static/carrier completion |
| BarbarianHut / Building | BarbarianHut | Existing template; translator static/carrier completion |
| BombTower / Building | BombTower | Existing template/static rows retained |
| Cannon / Building | All122 definitions (includes common fixtures) | Existing template/static rows retained |
| ElixirCollector / Building | Elixir Collector | Existing template; translator static/carrier completion |
| GoblinCage / Building | GoblinCage | Existing template; translator static/carrier completion |
| GoblinDrill / Building | GoblinDrill | Existing template; translator static/carrier completion |
| GoblinHut_Rework / Building | GoblinHut | Existing template/static rows retained |
| InfernoTower / Building | InfernoTower | Existing template/static rows retained |
| KingTower / Building | All122 definitions (includes common fixtures) | Existing template/static rows retained |
| Mortar / Building | Mortar | Existing template; translator static/carrier completion |
| Tesla / Building | Tesla | Existing template/static rows retained |
| Tombstone / Building | Tombstone | Existing template; translator static/carrier completion |
| Tower / Building | All122 definitions (includes common fixtures) | Existing template/static rows retained |
| Xbow / Building | Xbow | Existing template/static rows retained |
| ArcherArrow / Projectile | All122 definitions (includes common fixtures) | Existing template/static rows retained |
| ArcherQueenArrow / Projectile | ArcherQueen | Existing template/static rows retained |
| Arrows / Projectile | Arrows | Existing template/static rows retained |
| AxeManProjectile / Projectile | AxeMan | Existing template; translator static/carrier completion |
| BabyDragonProjectile / Projectile | BabyDragon | Existing template/static rows retained |
| BarbLog / Projectile | BarbLog | Existing template/static rows retained |
| BlowdartGoblinProjectile / Projectile | BlowdartGoblin | Existing template/static rows retained |
| BombSkeletonProjectile / Projectile | Bomber | Existing template; translator static/carrier completion |
| BombTowerProjectile / Projectile | BombTower | Existing template/static rows retained |
| BowlerProjectile / Projectile | Bowler | Existing template; translator static/carrier completion |
| Chr_wizardProjectile / Projectile | Wizard | Existing template/static rows retained |
| DartBarrellProjectile / Projectile | DartBarrell | Existing template; translator static/carrier completion |
| ElectroDragonProjectile / Projectile | ElectroDragon | Existing template; translator static/carrier completion |
| ElectroSpiritProjectile / Projectile | ElectroSpirit | Existing template/static rows retained |
| EliteArcherArrow / Projectile | EliteArcher | Existing template; translator static/carrier completion |
| FireSpiritsProjectile / Projectile | FireSpirits, FirespiritHut | Existing template/static rows retained |
| Fireball / Projectile | Fireball | Existing template/static rows retained |
| FirecrackerExplosion / Projectile | Firecracker | Existing template/static rows retained |
| Furnace_Rework_Projectile / Projectile | FirespiritHut | Existing template/static rows retained |
| GoblinBarrel / Projectile | GoblinBarrel | Existing template/static rows retained |
| GoblinDemolisherProjectile / Projectile | GoblinDemolisher | Existing template; translator static/carrier completion |
| HealSpiritProjectile / Projectile | Heal | Existing template; translator static/carrier completion |
| HunterProjectile / Projectile | Hunter | Existing template; translator static/carrier completion |
| IceSpiritsProjectile / Projectile | IceSpirits | Existing template/static rows retained |
| Ice_wizardProjectile / Projectile | IceWizard | Existing template; translator static/carrier completion |
| KingTower / Projectile | ElixirGolem, Giant, Golem, RoyalGiant | Existing template/static rows retained |
| LavaHoundProjectile / Projectile | LavaHound | Existing template; translator static/carrier completion |
| LavaPupProjectile / Projectile | LavaHound | Existing template; translator static/carrier completion |
| LittlePrinceProjectile / Projectile | LittlePrince | Existing template; translator static/carrier completion |
| Log / Projectile | Log | Existing template/static rows retained |
| MegaMinionSpit / Projectile | MegaMinion | Existing template; translator static/carrier completion |
| MinionSpit / Projectile | All122 definitions (includes common fixtures) | Existing template/static rows retained |
| MortarProjectile / Projectile | Mortar | Existing template; translator static/carrier completion |
| MovingCannonProjectile / Projectile | MovingCannon | Existing template; translator static/carrier completion |
| MusketeerProjectile / Projectile | Musketeer | Existing template/static rows retained |
| PrincessProjectile / Projectile | Princess | Existing template/static rows retained |
| Prj_goblinstein_doctor / Projectile | Goblinstein | Existing template/static rows retained |
| RascalGirlProjectile / Projectile | Rascals | Existing template/static rows retained |
| Rocket / Projectile | Rocket | Existing template/static rows retained |
| RoyalDelivery / Projectile | RoyalDelivery | Existing template/static rows retained |
| RoyalGiantProjectile / Projectile | RoyalGiant | Existing template; translator static/carrier completion |
| SkeletonDragonProjectile / Projectile | SkeletonDragons | Existing template; translator static/carrier completion |
| Snowball / Projectile | Snowball | Existing template; translator static/carrier completion |
| SpearGoblinProjectile / Projectile | GoblinGang, GoblinHut, SpearGoblins | Existing template/static rows retained |
| Tower / Projectile | AngryBarbarians, Arrows, Assassin, Balloon, BarbLog, BarbarianHut, Barbarians, BattleRam, Berserker, BossBandit, ElectroGiant, ElectroWizard, ElixirGolem, Fisherman, Giant, GiantBuffer, GiantSkeleton, GoblinBarrel, GoblinDrill, GoblinGang, GoblinGiant, GoblinHut, Goblins, Goblinstein, Golem, Graveyard, HogRider, IceGolemite, Knight, LavaHound, MiniSparkys, MinionHorde, Minions, Mirror, Monk, RageBarbarian, RamRider, RoyalGiant, RoyalHogs, RoyalRecruits, SkeletonArmy, SkeletonBalloon, SkeletonWarriors, SuspiciousBush, Tombstone, Wallbreakers, Witch | Existing template/static rows retained |
| TowerCannonball / Projectile | BarbLog, Barbarians, BattleRam, Cannon, ElectroGiant, ElectroWizard, ElixirGolem, Fisherman, Giant, GiantBuffer, GoblinBarrel, GoblinDrill, GoblinGiant, GoblinHut, Goblinstein, Golem, Graveyard, HogRider, IceGolemite, RamRider, RoyalGiant, RoyalHogs, SkeletonBalloon, SuspiciousBush, Wallbreakers | Existing template/static rows retained |
| VoodooProjectile / Projectile | WitchMother | Existing template; translator static/carrier completion |
| WallbreakerProjectile / Projectile | Wallbreakers | Existing template/static rows retained |
| WitchProjectile / Projectile | Witch | Existing template; translator static/carrier completion |
| Xbow_projectile / Projectile | Xbow | Existing template/static rows retained |
| ZapMachineProjectile / Projectile | ZapMachine | Existing template; translator static/carrier completion |
| AngryBarbarian / Troop | AngryBarbarians | Existing template/static rows retained |
| Archer / Troop | All122 definitions (includes common fixtures) | Existing template/static rows retained |
| ArcherQueen / Troop | ArcherQueen | Existing template/static rows retained |
| Assassin / Troop | Assassin | Existing template; translator static/carrier completion |
| AxeMan / Troop | AxeMan | Existing template; translator static/carrier completion |
| BabyDragon / Troop | BabyDragon | Existing template/static rows retained |
| Balloon / Troop | Balloon | Existing template/static rows retained |
| Barbarian / Troop | BarbLog, BarbarianHut, Barbarians, BattleRam | Existing template/static rows retained |
| Bat / Troop | Bats, DarkWitch | Existing template/static rows retained |
| BattleHealer / Troop | BattleHealer | Existing template; translator static/carrier completion |
| BattleRam / Troop | BattleRam | Existing template; translator static/carrier completion |
| Berserker / Troop | Berserker | Existing template/static rows retained |
| BlowdartGoblin / Troop | BlowdartGoblin | Existing template/static rows retained |
| Bomber / Troop | Bomber | Existing template; translator static/carrier completion |
| BossBandit / Troop | BossBandit | Existing template; translator static/carrier completion |
| Bowler / Troop | Bowler | Existing template; translator static/carrier completion |
| BushGoblin / Troop | SuspiciousBush | Existing template; translator static/carrier completion |
| DarkPrince / Troop | DarkPrince | Existing template/static rows retained |
| DarkWitch / Troop | DarkWitch | Existing template; translator static/carrier completion |
| DartBarrell / Troop | DartBarrell | Existing template; translator static/carrier completion |
| DeliveryRecruit / Troop | RoyalDelivery | Existing template/static rows retained |
| ElectroDragon / Troop | ElectroDragon | Existing template; translator static/carrier completion |
| ElectroGiant / Troop | ElectroGiant | Existing template; translator static/carrier completion |
| ElectroSpirit / Troop | ElectroSpirit | Existing template/static rows retained |
| ElectroWizard / Troop | ElectroWizard | Existing template; translator static/carrier completion |
| EliteArcher / Troop | EliteArcher | Existing template; translator static/carrier completion |
| ElixirGolem1 / Troop | ElixirGolem | Existing template; translator static/carrier completion |
| ElixirGolem2 / Troop | ElixirGolem | Existing template; translator static/carrier completion |
| ElixirGolem4 / Troop | ElixirGolem | Existing template; translator static/carrier completion |
| FireSpirits / Troop | FireSpirits, FirespiritHut | Existing template/static rows retained |
| Firecracker / Troop | Firecracker | Existing template/static rows retained |
| Fisherman / Troop | Fisherman | Existing template; translator static/carrier completion |
| Furnace_rework / Troop | FirespiritHut | Existing template/static rows retained |
| Ghost / Troop | Ghost | Existing template/static rows retained |
| Giant / Troop | Giant | Existing template/static rows retained |
| GiantBuffer / Troop | GiantBuffer | Existing template; translator static/carrier completion |
| GiantSkeleton / Troop | GiantSkeleton | Existing template; translator static/carrier completion |
| Goblin / Troop | GoblinBarrel, GoblinDrill | Existing template/static rows retained |
| GoblinBrawler / Troop | GoblinCage | Existing template; translator static/carrier completion |
| GoblinDemolisher / Troop | GoblinDemolisher | Existing template; translator static/carrier completion |
| GoblinGiant / Troop | GoblinGiant | Existing template; translator static/carrier completion |
| GoblinMachine / Troop | GoblinMachine | Existing template; translator static/carrier completion |
| Goblin_Stab / Troop | GoblinGang, Goblins | Existing template/static rows retained |
| Goblinstein / Troop | Goblinstein | Existing template/static rows retained |
| Goblinstein_doctor / Troop | Goblinstein | Existing template/static rows retained |
| GoldenKnight / Troop | GoldenKnight | Existing template; translator static/carrier completion |
| Golem / Troop | Golem | Existing template/static rows retained |
| Golemite / Troop | Golem | Existing template/static rows retained |
| HealSpirit / Troop | Heal | Existing template; translator static/carrier completion |
| HogRider / Troop | HogRider | Existing template/static rows retained |
| Hunter / Troop | Hunter | Existing template; translator static/carrier completion |
| IceGolemite / Troop | IceGolemite | Existing template/static rows retained |
| IceSpirits / Troop | IceSpirits | Existing template/static rows retained |
| IceWizard / Troop | IceWizard | Existing template; translator static/carrier completion |
| InfernoDragon / Troop | InfernoDragon | Existing template; translator static/carrier completion |
| Knight / Troop | All122 definitions (includes common fixtures) | Existing template/static rows retained |
| LavaHound / Troop | LavaHound | Existing template; translator static/carrier completion |
| LavaPups / Troop | LavaHound | Existing template; translator static/carrier completion |
| LittlePrince / Troop | LittlePrince | Existing template; translator static/carrier completion |
| MegaKnight / Troop | MegaKnight | Existing template; translator static/carrier completion |
| MegaMinion / Troop | MegaMinion | Existing template; translator static/carrier completion |
| MightyMiner / Troop | MightyMiner | Existing template/static rows retained |
| Miner / Troop | Miner | Existing template/static rows retained |
| MiniPekka / Troop | MiniPekka | Existing template/static rows retained |
| MiniZapMachine / Troop | MiniSparkys | Existing template; translator static/carrier completion |
| Minion / Troop | All122 definitions (includes common fixtures) | Existing template/static rows retained |
| Monk / Troop | Monk | Existing template; translator static/carrier completion |
| MovingCannon / Troop | MovingCannon | Existing template; translator static/carrier completion |
| Musketeer / Troop | Musketeer | Existing template/static rows retained |
| Pekka / Troop | Pekka | Existing template; translator static/carrier completion |
| Phoenix / Troop | Phoenix | Existing template; translator static/carrier completion |
| Prince / Troop | Prince | Existing template/static rows retained |
| Princess / Troop | Princess | Existing template/static rows retained |
| RageBarbarian / Troop | RageBarbarian | Existing template; translator static/carrier completion |
| Ram / Troop | RamRider | Existing template; translator static/carrier completion |
| RascalBoy / Troop | Rascals | Existing template/static rows retained |
| RascalGirl / Troop | Rascals | Existing template/static rows retained |
| Recruit / Troop | RoyalRecruits | Existing template; translator static/carrier completion |
| Ronin / Troop | Ronin | Existing template; translator static/carrier completion |
| RoyalGiant / Troop | RoyalGiant | Existing template; translator static/carrier completion |
| RoyalHog / Troop | RoyalHogs | Existing template/static rows retained |
| Skeleton / Troop | Graveyard, SkeletonArmy, SkeletonBalloon, Skeletons, Tombstone, Witch | Existing template/static rows retained |
| SkeletonBalloon / Troop | SkeletonBalloon | Existing template; translator static/carrier completion |
| SkeletonDragon / Troop | SkeletonDragons | Existing template; translator static/carrier completion |
| SkeletonKing / Troop | SkeletonKing | Existing template; translator static/carrier completion |
| SkeletonWarrior / Troop | SkeletonWarriors | Existing template; translator static/carrier completion |
| SpearGoblin / Troop | GoblinGang, GoblinHut, SpearGoblins | Existing template/static rows retained |
| SuspiciousBush / Troop | SuspiciousBush | Existing template; translator static/carrier completion |
| ThreeMusketeers / Troop | ThreeMusketeers | Existing template; translator static/carrier completion |
| Valkyrie / Troop | Valkyrie | Existing template/static rows retained |
| Wallbreaker / Troop | Wallbreakers | Existing template/static rows retained |
| Witch / Troop | Witch | Existing template; translator static/carrier completion |
| WitchMother / Troop | WitchMother | Existing template; translator static/carrier completion |
| Wizard / Troop | Wizard | Existing template/static rows retained |
| ZapMachine / Troop | ZapMachine | Existing template; translator static/carrier completion |

## Final release protocol

The [reviewed protocol](MISSING-TEMPLATES-RELEASE-PROTOCOL.md) binds committed source bytes and extraction
permissions, immutable parent/source/native/data/content manifests, per-host create/verify receipts, and
actual-r3 totality/None/replay gates. Its [independent round-two approval](receipts/missing-templates-release-protocol-review.json)
resolves two provenance findings: archive modes must be preserved and verified before patch `copy2`, and a
path-only historical replay cannot prove a same-policy pair. The original r2 failure stays intact; final
replay acceptance requires a fresh sequential r2 negative and r3 terminal run on the same frozen policies and
fullpool source, with matching pre/post input hashes. No old exited job is resumed. All roots are opt-in;
rollback selects the retained matching r2 root/pin, and active LIVE pin selection remains LIVE-owned.
