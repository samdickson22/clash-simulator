# Public-object template closure (exploration tier)

Candidate implementation checkpoint; corrected class coverage and implementation review are pending. No sealing.
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
The inventory below is retained **development evidence**, not corrected class acceptance; it will be regenerated from accepted receipts.

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
| Corrected class run | Five-card/15-scenario corrected checkpoint pilot queued; full122/366 pending | Separate reviewed source, source hashes in scoped audit |

Independent implementation review APPROVE binds checkpoint1802e899cea14807f659ee234dcd67839b392f46;
its full brief, findings and hashes are in receipts/missing-templates-implementation-review-1802e899c.json.
Host-script approval is separate; corrected class acceptance and release-script approval remain prerequisites. Native full-board checks are projected synthetic carrier stress, using only
public entity columns with a normal HUD/global scaffold. Native constructor materialization and native gameplay
emission are recorded separately, especially for within-step spawn effects. No r3 roots are published yet;
no release verification receipts exist on03/04/08. Publication awaits corrected coverage/review/remaining gates,
with rollback by choosing untouched r2 roots. Candidate PIN_SETS entries do not change defaults or active pins.

All work uses `/mpac/sdicks02/jobs/clasher/cards/missing-templates-r3`, nice 15,
`PYTHONHASHSEED=0`, `PYTHONDONTWRITEBYTECODE=1` and one thread per numerical library. Compute on 04/08 is admitted
through `bot/exit/cpu_job.sh` with leases no larger than four. Existing runtime roots are immutable inputs.

## Development object inventory (187 observed keys; corrected run pending)

| Object / kind | Cards that emitted it | Table / fix |
|---|---|---|
| Balloon / AreaEffect | Balloon | Existing template/static rows retained |
| BarbarianRage / AreaEffect | RageBarbarian | translator static/carrier completion |
| BarbarianRageDamage / AreaEffect | RageBarbarian | Resources recursive exact template; translator static/carrier completion |
| BattleHealerSpawnHeal / AreaEffect | BattleHealer | translator static/carrier completion |
| BombTower / AreaEffect | BombTower | Existing template/static rows retained |
| DarkMagic / AreaEffect | DarkMagic | translator static/carrier completion |
| Earthquake / AreaEffect | Earthquake | Existing template/static rows retained |
| ElectroDragonProjectile / AreaEffect | ElectroDragon | translator static/carrier completion |
| ElectroSpiritProjectile / AreaEffect | ElectroSpirit | Existing template/static rows retained |
| ElectroWizardZap / AreaEffect | ElectroWizard | Resources recursive exact template; translator static/carrier completion |
| Freeze / AreaEffect | Freeze | translator static/carrier completion |
| FreezeIceGolemite / AreaEffect | IceGolemite | Existing template/static rows retained |
| GiantSkeleton / AreaEffect | GiantSkeleton | translator static/carrier completion |
| GoblinCurse / AreaEffect | GoblinCurse | translator static/carrier completion |
| GoblinDrillDamage / AreaEffect | GoblinDrill | Resources recursive exact template; translator static/carrier completion |
| Graveyard / AreaEffect | Graveyard | translator static/carrier completion |
| HealSpirit / AreaEffect | Heal | translator static/carrier completion |
| IceWizardCold / AreaEffect | IceWizard | Resources recursive exact template; translator static/carrier completion |
| Lightning / AreaEffect | Lightning | Existing template/static rows retained |
| MightyMiner / AreaEffect | MightyMiner | translator static/carrier completion |
| Poison / AreaEffect | Poison | Existing template/static rows retained |
| Rage / AreaEffect | Rage | translator static/carrier completion |
| RageDamage / AreaEffect | Rage | Resources recursive exact template; translator static/carrier completion |
| SkeletonBalloon / AreaEffect | SkeletonBalloon | translator static/carrier completion |
| SuspiciousBush_DummyAEO / AreaEffect | SuspiciousBush | translator static/carrier completion |
| Tornado / AreaEffect | Tornado | Existing template/static rows retained |
| Vines / AreaEffect | Vines | translator static/carrier completion |
| BarbarianHut / Building | BarbarianHut | translator static/carrier completion |
| BombTower / Building | BombTower | Existing template/static rows retained |
| Cannon / Building | AngryBarbarians, Archer, ArcherQueen, Arrows, Assassin, AxeMan, BabyDragon, Balloon, BarbLog, BarbarianHut, Barbarians, Bats, BattleHealer, BattleRam, Berserker, BlowdartGoblin, BombTower, Bomber, BossBandit, Bowler, Cannon, Clone, DarkMagic, DarkPrince, DarkWitch, DartBarrell, Earthquake, ElectroDragon, ElectroGiant, ElectroSpirit, ElectroWizard, EliteArcher, Elixir Collector, ElixirGolem, FireSpirits, Fireball, Firecracker, FirespiritHut, Fisherman, Freeze, Ghost, Giant, GiantBuffer, GiantSkeleton, GoblinBarrel, GoblinCage, GoblinCurse, GoblinDemolisher, GoblinDrill, GoblinGang, GoblinGiant, GoblinHut, GoblinMachine, Goblins, Goblinstein, GoldenKnight, Golem, Graveyard, Heal, HogRider, Hunter, IceGolemite, IceSpirits, IceWizard, InfernoDragon, InfernoTower, Knight, LavaHound, Lightning, LittlePrince, Log, MegaKnight, MegaMinion, MergeMaiden, MightyMiner, Miner, MiniPekka, MiniSparkys, MinionHorde, Minions, Mirror, Monk, Mortar, MovingCannon, Musketeer, Pekka, Phoenix, Poison, Prince, Princess, Rage, RageBarbarian, RamRider, Rascals, Rocket, Ronin, RoyalDelivery, RoyalGiant, RoyalHogs, RoyalRecruits, SkeletonArmy, SkeletonBalloon, SkeletonDragons, SkeletonKing, SkeletonWarriors, Skeletons, Snowball, SpearGoblins, SuspiciousBush, Tesla, ThreeMusketeers, Tombstone, Tornado, Valkyrie, Vines, Wallbreakers, Witch, WitchMother, Wizard, Xbow, Zap, ZapMachine | Existing template/static rows retained |
| ElixirCollector / Building | Elixir Collector | translator static/carrier completion |
| GoblinCage / Building | GoblinCage | translator static/carrier completion |
| GoblinDrill / Building | GoblinDrill | translator static/carrier completion |
| GoblinHut_Rework / Building | GoblinHut | Existing template/static rows retained |
| InfernoTower / Building | InfernoTower | Existing template/static rows retained |
| KingTower / Building | AngryBarbarians, Archer, ArcherQueen, Arrows, Assassin, AxeMan, BabyDragon, Balloon, BarbLog, BarbarianHut, Barbarians, Bats, BattleHealer, BattleRam, Berserker, BlowdartGoblin, BombTower, Bomber, BossBandit, Bowler, Cannon, Clone, DarkMagic, DarkPrince, DarkWitch, DartBarrell, Earthquake, ElectroDragon, ElectroGiant, ElectroSpirit, ElectroWizard, EliteArcher, Elixir Collector, ElixirGolem, FireSpirits, Fireball, Firecracker, FirespiritHut, Fisherman, Freeze, Ghost, Giant, GiantBuffer, GiantSkeleton, GoblinBarrel, GoblinCage, GoblinCurse, GoblinDemolisher, GoblinDrill, GoblinGang, GoblinGiant, GoblinHut, GoblinMachine, Goblins, Goblinstein, GoldenKnight, Golem, Graveyard, Heal, HogRider, Hunter, IceGolemite, IceSpirits, IceWizard, InfernoDragon, InfernoTower, Knight, LavaHound, Lightning, LittlePrince, Log, MegaKnight, MegaMinion, MergeMaiden, MightyMiner, Miner, MiniPekka, MiniSparkys, MinionHorde, Minions, Mirror, Monk, Mortar, MovingCannon, Musketeer, Pekka, Phoenix, Poison, Prince, Princess, Rage, RageBarbarian, RamRider, Rascals, Rocket, Ronin, RoyalDelivery, RoyalGiant, RoyalHogs, RoyalRecruits, SkeletonArmy, SkeletonBalloon, SkeletonDragons, SkeletonKing, SkeletonWarriors, Skeletons, Snowball, SpearGoblins, SuspiciousBush, Tesla, ThreeMusketeers, Tombstone, Tornado, Valkyrie, Vines, Wallbreakers, Witch, WitchMother, Wizard, Xbow, Zap, ZapMachine | Existing template/static rows retained |
| Mortar / Building | Mortar | translator static/carrier completion |
| Tesla / Building | Tesla | Existing template/static rows retained |
| Tombstone / Building | Tombstone | translator static/carrier completion |
| Tower / Building | AngryBarbarians, Archer, ArcherQueen, Arrows, Assassin, AxeMan, BabyDragon, Balloon, BarbLog, BarbarianHut, Barbarians, Bats, BattleHealer, BattleRam, Berserker, BlowdartGoblin, BombTower, Bomber, BossBandit, Bowler, Cannon, Clone, DarkMagic, DarkPrince, DarkWitch, DartBarrell, Earthquake, ElectroDragon, ElectroGiant, ElectroSpirit, ElectroWizard, EliteArcher, Elixir Collector, ElixirGolem, FireSpirits, Fireball, Firecracker, FirespiritHut, Fisherman, Freeze, Ghost, Giant, GiantBuffer, GiantSkeleton, GoblinBarrel, GoblinCage, GoblinCurse, GoblinDemolisher, GoblinDrill, GoblinGang, GoblinGiant, GoblinHut, GoblinMachine, Goblins, Goblinstein, GoldenKnight, Golem, Graveyard, Heal, HogRider, Hunter, IceGolemite, IceSpirits, IceWizard, InfernoDragon, InfernoTower, Knight, LavaHound, Lightning, LittlePrince, Log, MegaKnight, MegaMinion, MergeMaiden, MightyMiner, Miner, MiniPekka, MiniSparkys, MinionHorde, Minions, Mirror, Monk, Mortar, MovingCannon, Musketeer, Pekka, Phoenix, Poison, Prince, Princess, Rage, RageBarbarian, RamRider, Rascals, Rocket, Ronin, RoyalDelivery, RoyalGiant, RoyalHogs, RoyalRecruits, SkeletonArmy, SkeletonBalloon, SkeletonDragons, SkeletonKing, SkeletonWarriors, Skeletons, Snowball, SpearGoblins, SuspiciousBush, Tesla, ThreeMusketeers, Tombstone, Tornado, Valkyrie, Vines, Wallbreakers, Witch, WitchMother, Wizard, Xbow, Zap, ZapMachine | Existing template/static rows retained |
| Xbow / Building | Xbow | Existing template/static rows retained |
| ArcherArrow / Projectile | AngryBarbarians, Archer, ArcherQueen, Arrows, Assassin, AxeMan, BabyDragon, Balloon, BarbLog, BarbarianHut, Barbarians, Bats, BattleHealer, BattleRam, Berserker, BlowdartGoblin, BombTower, Bomber, BossBandit, Bowler, Cannon, Clone, DarkMagic, DarkPrince, DarkWitch, DartBarrell, Earthquake, ElectroDragon, ElectroGiant, ElectroSpirit, ElectroWizard, EliteArcher, Elixir Collector, ElixirGolem, FireSpirits, Fireball, Firecracker, FirespiritHut, Fisherman, Freeze, Ghost, Giant, GiantBuffer, GiantSkeleton, GoblinBarrel, GoblinCage, GoblinCurse, GoblinDemolisher, GoblinDrill, GoblinGang, GoblinGiant, GoblinHut, GoblinMachine, Goblins, Goblinstein, GoldenKnight, Golem, Graveyard, Heal, HogRider, Hunter, IceGolemite, IceSpirits, IceWizard, InfernoDragon, InfernoTower, Knight, LavaHound, Lightning, LittlePrince, Log, MegaKnight, MegaMinion, MergeMaiden, MightyMiner, Miner, MiniPekka, MiniSparkys, MinionHorde, Minions, Mirror, Monk, Mortar, MovingCannon, Musketeer, Pekka, Phoenix, Poison, Prince, Princess, Rage, RageBarbarian, RamRider, Rascals, Rocket, Ronin, RoyalDelivery, RoyalGiant, RoyalHogs, RoyalRecruits, SkeletonArmy, SkeletonBalloon, SkeletonDragons, SkeletonKing, SkeletonWarriors, Skeletons, Snowball, SpearGoblins, SuspiciousBush, Tesla, ThreeMusketeers, Tombstone, Tornado, Valkyrie, Vines, Wallbreakers, Witch, WitchMother, Wizard, Xbow, Zap, ZapMachine | Existing template/static rows retained |
| ArcherQueenArrow / Projectile | ArcherQueen | Existing template/static rows retained |
| Arrows / Projectile | Arrows | Existing template/static rows retained |
| AxeManProjectile / Projectile | AxeMan | translator static/carrier completion |
| BabyDragonProjectile / Projectile | BabyDragon | Existing template/static rows retained |
| BarbLog / Projectile | BarbLog | Existing template/static rows retained |
| BlowdartGoblinProjectile / Projectile | BlowdartGoblin | Existing template/static rows retained |
| BombSkeletonProjectile / Projectile | Bomber | translator static/carrier completion |
| BombTowerProjectile / Projectile | BombTower | Existing template/static rows retained |
| BowlerProjectile / Projectile | Bowler | translator static/carrier completion |
| Chr_wizardProjectile / Projectile | Wizard | Existing template/static rows retained |
| DartBarrellProjectile / Projectile | DartBarrell | translator static/carrier completion |
| ElectroDragonProjectile / Projectile | ElectroDragon | translator static/carrier completion |
| ElectroSpiritProjectile / Projectile | ElectroSpirit | Existing template/static rows retained |
| EliteArcherArrow / Projectile | EliteArcher | translator static/carrier completion |
| FireSpiritsProjectile / Projectile | FireSpirits, FirespiritHut | Existing template/static rows retained |
| Fireball / Projectile | Fireball | Existing template/static rows retained |
| FirecrackerExplosion / Projectile | Firecracker | Existing template/static rows retained |
| Furnace_Rework_Projectile / Projectile | FirespiritHut | Existing template/static rows retained |
| GoblinBarrel / Projectile | GoblinBarrel | Existing template/static rows retained |
| GoblinDemolisherProjectile / Projectile | GoblinDemolisher | translator static/carrier completion |
| HealSpiritProjectile / Projectile | Heal | translator static/carrier completion |
| HunterProjectile / Projectile | Hunter | translator static/carrier completion |
| IceSpiritsProjectile / Projectile | IceSpirits | Existing template/static rows retained |
| Ice_wizardProjectile / Projectile | IceWizard | translator static/carrier completion |
| KingTower / Projectile | ElixirGolem, Giant, Golem, RoyalGiant | Existing template/static rows retained |
| LavaHoundProjectile / Projectile | LavaHound | translator static/carrier completion |
| LavaPupProjectile / Projectile | LavaHound | translator static/carrier completion |
| LittlePrinceProjectile / Projectile | LittlePrince | translator static/carrier completion |
| Log / Projectile | Log | Existing template/static rows retained |
| MegaMinionSpit / Projectile | MegaMinion | translator static/carrier completion |
| MinionSpit / Projectile | AngryBarbarians, Archer, ArcherQueen, Arrows, Assassin, AxeMan, BabyDragon, Balloon, BarbLog, BarbarianHut, Barbarians, Bats, BattleHealer, BattleRam, Berserker, BlowdartGoblin, BombTower, Bomber, BossBandit, Bowler, Cannon, Clone, DarkMagic, DarkPrince, DarkWitch, DartBarrell, Earthquake, ElectroDragon, ElectroGiant, ElectroSpirit, ElectroWizard, EliteArcher, Elixir Collector, ElixirGolem, FireSpirits, Fireball, Firecracker, FirespiritHut, Fisherman, Freeze, Ghost, Giant, GiantBuffer, GiantSkeleton, GoblinBarrel, GoblinCage, GoblinCurse, GoblinDemolisher, GoblinDrill, GoblinGang, GoblinGiant, GoblinHut, GoblinMachine, Goblins, Goblinstein, GoldenKnight, Golem, Graveyard, Heal, HogRider, Hunter, IceGolemite, IceSpirits, IceWizard, InfernoDragon, InfernoTower, Knight, LavaHound, Lightning, LittlePrince, Log, MegaKnight, MegaMinion, MergeMaiden, MightyMiner, Miner, MiniPekka, MiniSparkys, MinionHorde, Minions, Mirror, Monk, Mortar, MovingCannon, Musketeer, Pekka, Phoenix, Poison, Prince, Princess, Rage, RageBarbarian, RamRider, Rascals, Rocket, Ronin, RoyalDelivery, RoyalGiant, RoyalHogs, RoyalRecruits, SkeletonArmy, SkeletonBalloon, SkeletonDragons, SkeletonKing, SkeletonWarriors, Skeletons, Snowball, SpearGoblins, SuspiciousBush, Tesla, ThreeMusketeers, Tombstone, Tornado, Valkyrie, Vines, Wallbreakers, Witch, WitchMother, Wizard, Xbow, Zap, ZapMachine | Existing template/static rows retained |
| MortarProjectile / Projectile | Mortar | translator static/carrier completion |
| MovingCannonProjectile / Projectile | MovingCannon | translator static/carrier completion |
| MusketeerProjectile / Projectile | Musketeer | Existing template/static rows retained |
| PrincessProjectile / Projectile | Princess | Existing template/static rows retained |
| Prj_goblinstein_doctor / Projectile | Goblinstein | Existing template/static rows retained |
| RascalGirlProjectile / Projectile | Rascals | Existing template/static rows retained |
| Rocket / Projectile | Rocket | Existing template/static rows retained |
| RoyalDelivery / Projectile | RoyalDelivery | Existing template/static rows retained |
| RoyalGiantProjectile / Projectile | RoyalGiant | translator static/carrier completion |
| SkeletonDragonProjectile / Projectile | SkeletonDragons | translator static/carrier completion |
| Snowball / Projectile | Snowball | translator static/carrier completion |
| SpearGoblinProjectile / Projectile | GoblinGang, GoblinHut, SpearGoblins | Existing template/static rows retained |
| Tower / Projectile | AngryBarbarians, Arrows, Assassin, Balloon, BarbLog, BarbarianHut, Barbarians, BattleRam, Berserker, BossBandit, ElectroGiant, ElectroWizard, ElixirGolem, Fisherman, Giant, GiantBuffer, GiantSkeleton, GoblinBarrel, GoblinDrill, GoblinGang, GoblinGiant, GoblinHut, Goblins, Goblinstein, Golem, Graveyard, HogRider, IceGolemite, Knight, LavaHound, MiniSparkys, MinionHorde, Minions, Mirror, Monk, RageBarbarian, RamRider, RoyalGiant, RoyalHogs, RoyalRecruits, SkeletonArmy, SkeletonBalloon, SkeletonWarriors, SuspiciousBush, Tombstone, Wallbreakers, Witch | Existing template/static rows retained |
| TowerCannonball / Projectile | BarbLog, Barbarians, BattleRam, Cannon, ElectroGiant, ElectroWizard, ElixirGolem, Fisherman, Giant, GiantBuffer, GoblinBarrel, GoblinDrill, GoblinGiant, GoblinHut, Goblinstein, Golem, Graveyard, HogRider, IceGolemite, RamRider, RoyalGiant, RoyalHogs, SkeletonBalloon, SuspiciousBush, Wallbreakers | Existing template/static rows retained |
| VoodooProjectile / Projectile | WitchMother | translator static/carrier completion |
| WallbreakerProjectile / Projectile | Wallbreakers | Existing template/static rows retained |
| WitchProjectile / Projectile | Witch | translator static/carrier completion |
| Xbow_projectile / Projectile | Xbow | Existing template/static rows retained |
| ZapMachineProjectile / Projectile | ZapMachine | translator static/carrier completion |
| AngryBarbarian / Troop | AngryBarbarians | Existing template/static rows retained |
| Archer / Troop | AngryBarbarians, Archer, ArcherQueen, Arrows, Assassin, AxeMan, BabyDragon, Balloon, BarbLog, BarbarianHut, Barbarians, Bats, BattleHealer, BattleRam, Berserker, BlowdartGoblin, BombTower, Bomber, BossBandit, Bowler, Cannon, Clone, DarkMagic, DarkPrince, DarkWitch, DartBarrell, Earthquake, ElectroDragon, ElectroGiant, ElectroSpirit, ElectroWizard, EliteArcher, Elixir Collector, ElixirGolem, FireSpirits, Fireball, Firecracker, FirespiritHut, Fisherman, Freeze, Ghost, Giant, GiantBuffer, GiantSkeleton, GoblinBarrel, GoblinCage, GoblinCurse, GoblinDemolisher, GoblinDrill, GoblinGang, GoblinGiant, GoblinHut, GoblinMachine, Goblins, Goblinstein, GoldenKnight, Golem, Graveyard, Heal, HogRider, Hunter, IceGolemite, IceSpirits, IceWizard, InfernoDragon, InfernoTower, Knight, LavaHound, Lightning, LittlePrince, Log, MegaKnight, MegaMinion, MergeMaiden, MightyMiner, Miner, MiniPekka, MiniSparkys, MinionHorde, Minions, Mirror, Monk, Mortar, MovingCannon, Musketeer, Pekka, Phoenix, Poison, Prince, Princess, Rage, RageBarbarian, RamRider, Rascals, Rocket, Ronin, RoyalDelivery, RoyalGiant, RoyalHogs, RoyalRecruits, SkeletonArmy, SkeletonBalloon, SkeletonDragons, SkeletonKing, SkeletonWarriors, Skeletons, Snowball, SpearGoblins, SuspiciousBush, Tesla, ThreeMusketeers, Tombstone, Tornado, Valkyrie, Vines, Wallbreakers, Witch, WitchMother, Wizard, Xbow, Zap, ZapMachine | Existing template/static rows retained |
| ArcherQueen / Troop | ArcherQueen | Existing template/static rows retained |
| Assassin / Troop | Assassin | translator static/carrier completion |
| AxeMan / Troop | AxeMan | translator static/carrier completion |
| BabyDragon / Troop | BabyDragon | Existing template/static rows retained |
| Balloon / Troop | Balloon | Existing template/static rows retained |
| Barbarian / Troop | BarbLog, BarbarianHut, Barbarians, BattleRam | Existing template/static rows retained |
| Bat / Troop | Bats, DarkWitch | Existing template/static rows retained |
| BattleHealer / Troop | BattleHealer | translator static/carrier completion |
| BattleRam / Troop | BattleRam | translator static/carrier completion |
| Berserker / Troop | Berserker | Existing template/static rows retained |
| BlowdartGoblin / Troop | BlowdartGoblin | Existing template/static rows retained |
| Bomber / Troop | Bomber | translator static/carrier completion |
| BossBandit / Troop | BossBandit | translator static/carrier completion |
| Bowler / Troop | Bowler | translator static/carrier completion |
| BushGoblin / Troop | SuspiciousBush | translator static/carrier completion |
| DarkPrince / Troop | DarkPrince | Existing template/static rows retained |
| DarkWitch / Troop | DarkWitch | translator static/carrier completion |
| DartBarrell / Troop | DartBarrell | translator static/carrier completion |
| DeliveryRecruit / Troop | RoyalDelivery | Existing template/static rows retained |
| ElectroDragon / Troop | ElectroDragon | translator static/carrier completion |
| ElectroGiant / Troop | ElectroGiant | translator static/carrier completion |
| ElectroSpirit / Troop | ElectroSpirit | Existing template/static rows retained |
| ElectroWizard / Troop | ElectroWizard | translator static/carrier completion |
| EliteArcher / Troop | EliteArcher | translator static/carrier completion |
| ElixirGolem1 / Troop | ElixirGolem | translator static/carrier completion |
| ElixirGolem2 / Troop | ElixirGolem | translator static/carrier completion |
| ElixirGolem4 / Troop | ElixirGolem | translator static/carrier completion |
| FireSpirits / Troop | FireSpirits, FirespiritHut | Existing template/static rows retained |
| Firecracker / Troop | Firecracker | Existing template/static rows retained |
| Fisherman / Troop | Fisherman | translator static/carrier completion |
| Furnace_rework / Troop | FirespiritHut | Existing template/static rows retained |
| Ghost / Troop | Ghost | Existing template/static rows retained |
| Giant / Troop | Giant | Existing template/static rows retained |
| GiantBuffer / Troop | GiantBuffer | translator static/carrier completion |
| GiantSkeleton / Troop | GiantSkeleton | translator static/carrier completion |
| Goblin / Troop | GoblinBarrel, GoblinDrill | Existing template/static rows retained |
| GoblinBrawler / Troop | GoblinCage | translator static/carrier completion |
| GoblinDemolisher / Troop | GoblinDemolisher | translator static/carrier completion |
| GoblinGiant / Troop | GoblinGiant | translator static/carrier completion |
| GoblinMachine / Troop | GoblinMachine | translator static/carrier completion |
| Goblin_Stab / Troop | GoblinGang, Goblins | Existing template/static rows retained |
| Goblinstein / Troop | Goblinstein | Existing template/static rows retained |
| Goblinstein_doctor / Troop | Goblinstein | Existing template/static rows retained |
| GoldenKnight / Troop | GoldenKnight | translator static/carrier completion |
| Golem / Troop | Golem | Existing template/static rows retained |
| Golemite / Troop | Golem | Existing template/static rows retained |
| HealSpirit / Troop | Heal | translator static/carrier completion |
| HogRider / Troop | HogRider | Existing template/static rows retained |
| Hunter / Troop | Hunter | translator static/carrier completion |
| IceGolemite / Troop | IceGolemite | Existing template/static rows retained |
| IceSpirits / Troop | IceSpirits | Existing template/static rows retained |
| IceWizard / Troop | IceWizard | translator static/carrier completion |
| InfernoDragon / Troop | InfernoDragon | translator static/carrier completion |
| Knight / Troop | AngryBarbarians, Archer, ArcherQueen, Arrows, Assassin, AxeMan, BabyDragon, Balloon, BarbLog, BarbarianHut, Barbarians, Bats, BattleHealer, BattleRam, Berserker, BlowdartGoblin, BombTower, Bomber, BossBandit, Bowler, Cannon, Clone, DarkMagic, DarkPrince, DarkWitch, DartBarrell, Earthquake, ElectroDragon, ElectroGiant, ElectroSpirit, ElectroWizard, EliteArcher, Elixir Collector, ElixirGolem, FireSpirits, Fireball, Firecracker, FirespiritHut, Fisherman, Freeze, Ghost, Giant, GiantBuffer, GiantSkeleton, GoblinBarrel, GoblinCage, GoblinCurse, GoblinDemolisher, GoblinDrill, GoblinGang, GoblinGiant, GoblinHut, GoblinMachine, Goblins, Goblinstein, GoldenKnight, Golem, Graveyard, Heal, HogRider, Hunter, IceGolemite, IceSpirits, IceWizard, InfernoDragon, InfernoTower, Knight, LavaHound, Lightning, LittlePrince, Log, MegaKnight, MegaMinion, MergeMaiden, MightyMiner, Miner, MiniPekka, MiniSparkys, MinionHorde, Minions, Mirror, Monk, Mortar, MovingCannon, Musketeer, Pekka, Phoenix, Poison, Prince, Princess, Rage, RageBarbarian, RamRider, Rascals, Rocket, Ronin, RoyalDelivery, RoyalGiant, RoyalHogs, RoyalRecruits, SkeletonArmy, SkeletonBalloon, SkeletonDragons, SkeletonKing, SkeletonWarriors, Skeletons, Snowball, SpearGoblins, SuspiciousBush, Tesla, ThreeMusketeers, Tombstone, Tornado, Valkyrie, Vines, Wallbreakers, Witch, WitchMother, Wizard, Xbow, Zap, ZapMachine | Existing template/static rows retained |
| LavaHound / Troop | LavaHound | translator static/carrier completion |
| LavaPups / Troop | LavaHound | translator static/carrier completion |
| LittlePrince / Troop | LittlePrince | translator static/carrier completion |
| MegaKnight / Troop | MegaKnight | translator static/carrier completion |
| MegaMinion / Troop | MegaMinion | translator static/carrier completion |
| MightyMiner / Troop | MightyMiner | Existing template/static rows retained |
| Miner / Troop | Miner | Existing template/static rows retained |
| MiniPekka / Troop | MiniPekka | Existing template/static rows retained |
| MiniZapMachine / Troop | MiniSparkys | translator static/carrier completion |
| Minion / Troop | AngryBarbarians, Archer, ArcherQueen, Arrows, Assassin, AxeMan, BabyDragon, Balloon, BarbLog, BarbarianHut, Barbarians, Bats, BattleHealer, BattleRam, Berserker, BlowdartGoblin, BombTower, Bomber, BossBandit, Bowler, Cannon, Clone, DarkMagic, DarkPrince, DarkWitch, DartBarrell, Earthquake, ElectroDragon, ElectroGiant, ElectroSpirit, ElectroWizard, EliteArcher, Elixir Collector, ElixirGolem, FireSpirits, Fireball, Firecracker, FirespiritHut, Fisherman, Freeze, Ghost, Giant, GiantBuffer, GiantSkeleton, GoblinBarrel, GoblinCage, GoblinCurse, GoblinDemolisher, GoblinDrill, GoblinGang, GoblinGiant, GoblinHut, GoblinMachine, Goblins, Goblinstein, GoldenKnight, Golem, Graveyard, Heal, HogRider, Hunter, IceGolemite, IceSpirits, IceWizard, InfernoDragon, InfernoTower, Knight, LavaHound, Lightning, LittlePrince, Log, MegaKnight, MegaMinion, MergeMaiden, MightyMiner, Miner, MiniPekka, MiniSparkys, MinionHorde, Minions, Mirror, Monk, Mortar, MovingCannon, Musketeer, Pekka, Phoenix, Poison, Prince, Princess, Rage, RageBarbarian, RamRider, Rascals, Rocket, Ronin, RoyalDelivery, RoyalGiant, RoyalHogs, RoyalRecruits, SkeletonArmy, SkeletonBalloon, SkeletonDragons, SkeletonKing, SkeletonWarriors, Skeletons, Snowball, SpearGoblins, SuspiciousBush, Tesla, ThreeMusketeers, Tombstone, Tornado, Valkyrie, Vines, Wallbreakers, Witch, WitchMother, Wizard, Xbow, Zap, ZapMachine | Existing template/static rows retained |
| Monk / Troop | Monk | translator static/carrier completion |
| MovingCannon / Troop | MovingCannon | translator static/carrier completion |
| Musketeer / Troop | Musketeer | Existing template/static rows retained |
| Pekka / Troop | Pekka | translator static/carrier completion |
| Phoenix / Troop | Phoenix | translator static/carrier completion |
| Prince / Troop | Prince | Existing template/static rows retained |
| Princess / Troop | Princess | Existing template/static rows retained |
| RageBarbarian / Troop | RageBarbarian | translator static/carrier completion |
| Ram / Troop | RamRider | translator static/carrier completion |
| RascalBoy / Troop | Rascals | Existing template/static rows retained |
| RascalGirl / Troop | Rascals | Existing template/static rows retained |
| Recruit / Troop | RoyalRecruits | translator static/carrier completion |
| Ronin / Troop | Ronin | translator static/carrier completion |
| RoyalGiant / Troop | RoyalGiant | translator static/carrier completion |
| RoyalHog / Troop | RoyalHogs | Existing template/static rows retained |
| Skeleton / Troop | Graveyard, SkeletonArmy, SkeletonBalloon, Skeletons, Tombstone, Witch | Existing template/static rows retained |
| SkeletonBalloon / Troop | SkeletonBalloon | translator static/carrier completion |
| SkeletonDragon / Troop | SkeletonDragons | translator static/carrier completion |
| SkeletonKing / Troop | SkeletonKing | translator static/carrier completion |
| SkeletonWarrior / Troop | SkeletonWarriors | translator static/carrier completion |
| SpearGoblin / Troop | GoblinGang, GoblinHut, SpearGoblins | Existing template/static rows retained |
| SuspiciousBush / Troop | SuspiciousBush | translator static/carrier completion |
| ThreeMusketeers / Troop | ThreeMusketeers | translator static/carrier completion |
| Valkyrie / Troop | Valkyrie | Existing template/static rows retained |
| Wallbreaker / Troop | Wallbreakers | Existing template/static rows retained |
| Witch / Troop | Witch | translator static/carrier completion |
| WitchMother / Troop | WitchMother | translator static/carrier completion |
| Wizard / Troop | Wizard | Existing template/static rows retained |
| ZapMachine / Troop | ZapMachine | translator static/carrier completion |
