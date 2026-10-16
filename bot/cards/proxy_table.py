"""Proxy table: non-C56 ladder cards mapped onto the 56 cards the engine supports (C56).

Generated draft from gamedata.json (cost, kind, bodies count, SHARED_BODY) and
reports/cards/tools/pool.py, with hand-chosen proxies. The live translator imports this table.

Selection rules for proxy_card: kind must match (hard). For troops, air must match (hard, because
a flying unit must get a flying proxy). Then the nearest elixir cost, then a role match, then HP.
Spells pick damage-vs-control first, then cost.

Assumptions (see each entry "why"):
- air = body in src/clasher/unit_traits.py AIR_UNIT_NAMES, plus DartBarrell (Flying Machine), which
  that list omits even though the card flies. Air buildings do not exist.
- Spells have body_map {} and proxy_body '' (the spec rule). Heal (HealSpirit), Graveyard and
  MergeMaiden put bodies on the board in game, but that is not modelled here.
- ElectroWizard, IceWizard and ThreeMusketeers have no summonCharacterData in gamedata; their body
  names are assumed (card name, card name, Musketeer). bodies for ThreeMusketeers is 3 (hand-set).
- Evolved forms (evolvedSpellsData) are ignored. Vines, Clone and Freeze effects follow the card name.
- bodies = gamedata summonNumber (1 when absent); spells are 0.
- Lead review (2026-10-16): never proxy onto a champion (ability state) or a body with side mechanics
  (Miner tunnel, IceGolemite death freeze, Golem/Giant as a troop-targeter); 11 entries corrected.
- Card names are RoyaleSim-style as in bot/fidelity/c56_native_ids.json (`Archer`, `IceGolemite`,
  `IceSpirits`); the translator normalises to its own spelling (Archers, IceGolem, IceSpirit).

CLASS_ONLY (perception UNKNOWN_UNIT / UNKNOWN_BUILDING) must NOT be counted in the opponent's
revealed 8-card set: those entities have no card identity. The proxy only stands in for the board
entity. The cycle and elixir trackers keep the TRUE card id for NAMED cards.
"""

C56 = frozenset((
    'AngryBarbarians', 'Archer', 'ArcherQueen', 'Arrows', 'BabyDragon', 'Balloon',
    'BarbLog', 'Bats', 'Berserker', 'BlowdartGoblin', 'BombTower', 'Cannon',
    'DarkPrince', 'Earthquake', 'ElectroSpirit', 'FireSpirits', 'Fireball', 'Firecracker',
    'FirespiritHut', 'Ghost', 'Giant', 'GoblinBarrel', 'GoblinGang', 'GoblinHut',
    'Goblins', 'Goblinstein', 'Golem', 'HogRider', 'IceGolemite', 'IceSpirits',
    'InfernoTower', 'Knight', 'Lightning', 'Log', 'MightyMiner', 'Miner',
    'MiniPekka', 'MinionHorde', 'Minions', 'Musketeer', 'Poison', 'Prince',
    'Princess', 'Rascals', 'Rocket', 'RoyalDelivery', 'RoyalHogs', 'SkeletonArmy',
    'Skeletons', 'Tesla', 'Tornado', 'Valkyrie', 'Wallbreakers', 'Wizard',
    'Xbow', 'Zap',
))

BODIES_47 = frozenset((
    'AngryBarbarian', 'Archer', 'ArcherQueen', 'BabyDragon', 'Balloon', 'Barbarian',
    'Bat', 'Berserker', 'BlowdartGoblin', 'BombTower', 'Cannon', 'DarkPrince',
    'DeliveryRecruit', 'ElectroSpirit', 'FireSpirits', 'Firecracker', 'Furnace_rework', 'Ghost',
    'Giant', 'Goblin', 'GoblinHut_Rework', 'Goblin_Stab', 'Golem', 'HogRider',
    'IceGolemite', 'IceSpirits', 'InfernoTower', 'Knight', 'MightyMiner', 'Miner',
    'MiniPekka', 'Minion', 'Musketeer', 'Prince', 'Princess', 'RascalBoy',
    'RascalGirl', 'RoyalHog', 'Skeleton', 'SpearGoblin', 'Tesla', 'Valkyrie',
    'Wallbreaker', 'Wizard', 'Xbow', 'goblinstein', 'goblinstein_doctor',
))

AIR_BODY_NAMES = frozenset((
    'BabyDragon', 'Balloon', 'Bat', 'Bats', 'ElectroDragon', 'FlyingMachine',
    'InfernoDragon', 'LavaHound', 'LavaPup', 'LavaPups', 'MegaMinion', 'Minion',
    'MinionHorde', 'Minions', 'Phoenix', 'SkeletonBalloon', 'SkeletonDragon', 'SkeletonDragons',
))

NAMED = {
    'Assassin': dict(
        cost=3.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='Knight', proxy_body='Knight',
        body_map={'Assassin': 'Knight'},
        why='melee single, cost 3 (no Miner: tunnel state)'),
    'AxeMan': dict(
        cost=5.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='Wizard', proxy_body='Wizard',
        body_map={'AxeMan': 'Wizard'},
        why='ranged splash, cost 5 (never a champion proxy)'),
    'BarbarianHut': dict(
        cost=6.0, cls='building', kind='building', air=False, bodies=1,
        proxy_card='GoblinHut', proxy_body='GoblinHut_Rework',
        body_map={'BarbarianHut': 'GoblinHut_Rework', 'Barbarian': 'Barbarian'},
        why='spawner building, cost 4 (role over Xbow cost 6)'),
    'Barbarians': dict(
        cost=5.0, cls='troop', kind='troop', air=False, bodies=5,
        proxy_card='Rascals', proxy_body='Barbarian',
        body_map={'Barbarian': 'Barbarian'},
        why='ground melee swarm, cost 5; body is 47-list self'),
    'BattleHealer': dict(
        cost=4.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='Musketeer', proxy_body='Musketeer',
        body_map={'BattleHealer': 'Musketeer'},
        why='ranged single support, cost 4'),
    'BattleRam': dict(
        cost=4.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='HogRider', proxy_body='HogRider',
        body_map={'BattleRam': 'HogRider', 'Barbarian': 'Barbarian'},
        why='building-targeting ram, cost 4; death spawns Barbarian'),
    'Bomber': dict(
        cost=2.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='Firecracker', proxy_body='Firecracker',
        body_map={'Bomber': 'Firecracker'},
        why='ground ranged splash, cost 3 (no cost-2 splash card)'),
    'BossBandit': dict(
        cost=6.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='AngryBarbarians', proxy_body='AngryBarbarian',
        body_map={'BossBandit': 'AngryBarbarian'},
        why='melee tank, cost 6'),
    'Bowler': dict(
        cost=5.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='Wizard', proxy_body='Wizard',
        body_map={'Bowler': 'Wizard'},
        why='ground ranged splash, cost 5'),
    'Clone': dict(
        cost=3.0, cls='spell', kind='spell', air=False, bodies=0,
        proxy_card='Tornado', proxy_body='',
        body_map={},
        why='control, cost 3'),
    'DarkMagic': dict(
        cost=3.0, cls='spell', kind='spell', air=False, bodies=0,
        proxy_card='Arrows', proxy_body='',
        body_map={},
        why='damage area, cost 3'),
    'DarkWitch': dict(
        cost=4.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='DarkPrince', proxy_body='Wizard',
        body_map={'DarkWitch': 'Wizard', 'Bat': 'Bat'},
        why='splash caster cost 4; spawns Bats'),
    'DartBarrell': dict(
        cost=4.0, cls='troop', kind='troop', air=True, bodies=1,
        proxy_card='BabyDragon', proxy_body='BabyDragon',
        body_map={'DartBarrell': 'BabyDragon'},
        why='air ranged single, cost 4'),
    'ElectroDragon': dict(
        cost=5.0, cls='troop', kind='troop', air=True, bodies=1,
        proxy_card='MinionHorde', proxy_body='BabyDragon',
        body_map={'ElectroDragon': 'BabyDragon'},
        why='air ranged, cost 4-5 nearest air'),
    'ElectroGiant': dict(
        cost=7.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='Golem', proxy_body='Golem',
        body_map={'ElectroGiant': 'Golem'},
        why='building-targeting tank, cost 8 (nearest to 7)'),
    'ElectroWizard': dict(
        cost=4.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='Musketeer', proxy_body='Wizard',
        body_map={'ElectroWizard': 'Wizard'},
        why='ranged single, cost 4; no summonCharacterData in gamedata, body keyed by card name'),
    'EliteArcher': dict(
        cost=4.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='Musketeer', proxy_body='Musketeer',
        body_map={'EliteArcher': 'Musketeer'},
        why='ranged single, cost 4'),
    'Elixir Collector': dict(
        cost=6.0, cls='building', kind='building', air=False, bodies=1,
        proxy_card='Xbow', proxy_body='Cannon',
        body_map={'ElixirCollector': 'Cannon'},
        why='only cost-6 building in pool; no 47-list non-attacking body, static Cannon stands in'),
    'ElixirGolem': dict(
        cost=3.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='Knight', proxy_body='Knight',
        body_map={'ElixirGolem1': 'Knight', 'ElixirGolem2': 'Knight', 'ElixirGolem4': 'Knight'},
        why='building-targeting tank pieces; Knight body (IceGolemite has a death freeze)'),
    'Fisherman': dict(
        cost=3.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='Archer', proxy_body='Archer',
        body_map={'Fisherman': 'Archer'},
        why='ranged single, cost 3'),
    'Freeze': dict(
        cost=4.0, cls='spell', kind='spell', air=False, bodies=0,
        proxy_card='Zap', proxy_body='',
        body_map={},
        why='control stun area; control-first over cost'),
    'GiantBuffer': dict(
        cost=4.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='HogRider', proxy_body='Giant',
        body_map={'GiantBuffer': 'Giant'},
        why='building-targeting tank, cost 4'),
    'GiantSkeleton': dict(
        cost=6.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='AngryBarbarians', proxy_body='Prince',
        body_map={'GiantSkeleton': 'Prince', 'GiantSkeletonBomb': 'Skeleton'},
        why='melee tank cost 6; ground-target; bomb proxied by small ground body'),
    'GoblinCage': dict(
        cost=4.0, cls='building', kind='building', air=False, bodies=1,
        proxy_card='Cannon', proxy_body='Cannon',
        body_map={'GoblinCage': 'Cannon', 'GoblinBrawler': 'Knight'},
        why='defensive building, cost 3; Brawler as Knight (melee single)'),
    'GoblinCurse': dict(
        cost=2.0, cls='spell', kind='spell', air=False, bodies=0,
        proxy_card='Log', proxy_body='',
        body_map={},
        why='damage area, cost 2'),
    'GoblinDemolisher': dict(
        cost=4.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='HogRider', proxy_body='RoyalHog',
        body_map={'GoblinDemolisher': 'RoyalHog'},
        why='building-targeting, cost 4'),
    'GoblinDrill': dict(
        cost=4.0, cls='building', kind='building', air=False, bodies=1,
        proxy_card='GoblinHut', proxy_body='GoblinHut_Rework',
        body_map={'GoblinDrillDig': 'GoblinHut_Rework'},
        why='spawner building, cost 4'),
    'GoblinGiant': dict(
        cost=6.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='Giant', proxy_body='Giant',
        body_map={'GoblinGiant': 'Giant', 'SpearGoblinGiant': 'SpearGoblin', 'SpearGoblin': 'SpearGoblin'},
        why='building tank, cost 6 (nearest Giant 5)'),
    'GoblinMachine': dict(
        cost=5.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='Prince', proxy_body='Valkyrie',
        body_map={'GoblinMachine': 'Valkyrie'},
        why='ground melee tank, cost 5 (never a champion proxy)'),
    'GoldenKnight': dict(
        cost=4.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='MiniPekka', proxy_body='Knight',
        body_map={'GoldenKnight': 'Knight'},
        why='melee, cost 4'),
    'Graveyard': dict(
        cost=5.0, cls='spell', kind='spell', air=False, bodies=0,
        proxy_card='Poison', proxy_body='',
        body_map={},
        why='damage over time area, cost 4 nearest C56 damage spell'),
    'Heal': dict(
        cost=1.0, cls='spell', kind='spell', air=False, bodies=0,
        proxy_card='Zap', proxy_body='',
        body_map={},
        why='non-damage, cost 2 nearest; HealSpirit body not modelled (spell rule)'),
    'Hunter': dict(
        cost=4.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='Musketeer', proxy_body='Musketeer',
        body_map={'Hunter': 'Musketeer'},
        why='ranged single, cost 4'),
    'IceWizard': dict(
        cost=3.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='Archer', proxy_body='Wizard',
        body_map={'IceWizard': 'Wizard'},
        why='ranged, cost 3; no summonCharacterData, body keyed by card name'),
    'InfernoDragon': dict(
        cost=4.0, cls='troop', kind='troop', air=True, bodies=1,
        proxy_card='BabyDragon', proxy_body='BabyDragon',
        body_map={'InfernoDragon': 'BabyDragon'},
        why='air ranged, cost 4'),
    'LavaHound': dict(
        cost=7.0, cls='troop', kind='troop', air=True, bodies=1,
        proxy_card='Balloon', proxy_body='Balloon',
        body_map={'LavaHound': 'Balloon', 'LavaPups': 'Minion'},
        why='air building-targeting tank, cost 7 (nearest air Balloon)'),
    'LittlePrince': dict(
        cost=3.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='Archer', proxy_body='Musketeer',
        body_map={'LittlePrince': 'Musketeer'},
        why='ranged single, cost 3'),
    'MegaKnight': dict(
        cost=7.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='Golem', proxy_body='Valkyrie',
        body_map={'MegaKnight': 'Valkyrie'},
        why='splash melee tank; Valkyrie body (Golem body targets buildings only)'),
    'MegaMinion': dict(
        cost=3.0, cls='troop', kind='troop', air=True, bodies=1,
        proxy_card='Minions', proxy_body='Minion',
        body_map={'MegaMinion': 'Minion'},
        why='air melee single, cost 3'),
    'MergeMaiden': dict(
        cost=6.0, cls='spell', kind='spell', air=False, bodies=0,
        proxy_card='Lightning', proxy_body='',
        body_map={},
        why='damage area, cost 6'),
    'MiniSparkys': dict(
        cost=4.0, cls='troop', kind='troop', air=False, bodies=3,
        proxy_card='Musketeer', proxy_body='Musketeer',
        body_map={'MiniZapMachine': 'Musketeer'},
        why='ranged, cost 4'),
    'Mirror': dict(
        cost=1.0, cls='spell', kind='spell', air=False, bodies=0,
        proxy_card='Zap', proxy_body='',
        body_map={},
        why='non-damage, cost 2 nearest (Mirror is cost 1)'),
    'Monk': dict(
        cost=5.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='Prince', proxy_body='Prince',
        body_map={'Monk': 'Prince'},
        why='melee tank, cost 5'),
    'Mortar': dict(
        cost=4.0, cls='building', kind='building', air=False, bodies=1,
        proxy_card='BombTower', proxy_body='BombTower',
        body_map={'Mortar': 'BombTower'},
        why='siege ground building, cost 4'),
    'MovingCannon': dict(
        cost=5.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='Wizard', proxy_body='Musketeer',
        body_map={'MovingCannon': 'Musketeer'},
        why='ranged ground single, cost 5 (never a champion proxy)'),
    'Pekka': dict(
        cost=7.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='MiniPekka', proxy_body='MiniPekka',
        body_map={'Pekka': 'MiniPekka'},
        why='heavy melee single target'),
    'Phoenix': dict(
        cost=4.0, cls='troop', kind='troop', air=True, bodies=1,
        proxy_card='BabyDragon', proxy_body='BabyDragon',
        body_map={'Phoenix': 'BabyDragon'},
        why='air melee, cost 4'),
    'Rage': dict(
        cost=2.0, cls='spell', kind='spell', air=False, bodies=0,
        proxy_card='Zap', proxy_body='',
        body_map={},
        why='non-damage area buff, cost 2'),
    'RageBarbarian': dict(
        cost=4.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='MiniPekka', proxy_body='AngryBarbarian',
        body_map={'RageBarbarian': 'AngryBarbarian'},
        why='melee, cost 4'),
    'RamRider': dict(
        cost=5.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='HogRider', proxy_body='HogRider',
        body_map={'Ram': 'HogRider', 'RamRider': 'Musketeer'},
        why='building-targeter (never a champion proxy)'),
    'Ronin': dict(
        cost=5.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='Prince', proxy_body='Prince',
        body_map={'Ronin': 'Prince'},
        why='melee, cost 5'),
    'RoyalGiant': dict(
        cost=6.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='Giant', proxy_body='Giant',
        body_map={'RoyalGiant': 'Giant'},
        why='building tank, cost 6 (nearest Giant 5)'),
    'RoyalRecruits': dict(
        cost=7.0, cls='troop', kind='troop', air=False, bodies=6,
        proxy_card='AngryBarbarians', proxy_body='Knight',
        body_map={'Recruit': 'Knight'},
        why='melee group, cost 7; Recruit body not in 47'),
    'SkeletonBalloon': dict(
        cost=3.0, cls='troop', kind='troop', air=True, bodies=1,
        proxy_card='Minions', proxy_body='Balloon',
        body_map={'SkeletonBalloon': 'Balloon', 'SkeletonContainerNew': 'Skeleton'},
        why='air building-targeting, cost 3'),
    'SkeletonDragons': dict(
        cost=4.0, cls='troop', kind='troop', air=True, bodies=2,
        proxy_card='BabyDragon', proxy_body='BabyDragon',
        body_map={'SkeletonDragon': 'BabyDragon'},
        why='air ranged swarm, cost 4'),
    'SkeletonKing': dict(
        cost=4.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='MiniPekka', proxy_body='Knight',
        body_map={'SkeletonKing': 'Knight'},
        why='melee tank, cost 4'),
    'SkeletonWarriors': dict(
        cost=3.0, cls='troop', kind='troop', air=False, bodies=3,
        proxy_card='SkeletonArmy', proxy_body='Skeleton',
        body_map={'SkeletonWarrior': 'Skeleton'},
        why='melee swarm, cost 3'),
    'Snowball': dict(
        cost=2.0, cls='spell', kind='spell', air=False, bodies=0,
        proxy_card='BarbLog', proxy_body='',
        body_map={},
        why='rolling damage, cost 2'),
    'SpearGoblins': dict(
        cost=2.0, cls='troop', kind='troop', air=False, bodies=3,
        proxy_card='Goblins', proxy_body='SpearGoblin',
        body_map={'SpearGoblin': 'SpearGoblin'},
        why='ranged swarm, cost 2'),
    'SuspiciousBush': dict(
        cost=2.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='Wallbreakers', proxy_body='Wallbreaker',
        body_map={'SuspiciousBush': 'Wallbreaker'},
        why='building-targeting melee, cost 2'),
    'ThreeMusketeers': dict(
        cost=9.0, cls='troop', kind='troop', air=False, bodies=3,
        proxy_card='Golem', proxy_body='Musketeer',
        body_map={'Musketeer': 'Musketeer'},
        why='ranged swarm, cost 9 (nearest Golem 8); no summon data, body assumed Musketeer'),
    'Tombstone': dict(
        cost=3.0, cls='building', kind='building', air=False, bodies=1,
        proxy_card='GoblinHut', proxy_body='GoblinHut_Rework',
        body_map={'Tombstone': 'GoblinHut_Rework', 'Skeleton': 'Skeleton'},
        why='spawner building, cost 3 (nearest 4)'),
    'Vines': dict(
        cost=3.0, cls='spell', kind='spell', air=False, bodies=0,
        proxy_card='Tornado', proxy_body='',
        body_map={},
        why='control, cost 3; effect assumed from name'),
    'Witch': dict(
        cost=5.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='Wizard', proxy_body='Wizard',
        body_map={'Witch': 'Wizard', 'Skeleton': 'Skeleton'},
        why='splash caster, cost 5'),
    'WitchMother': dict(
        cost=4.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='Musketeer', proxy_body='Musketeer',
        body_map={'WitchMother': 'Musketeer'},
        why='ranged single, cost 4'),
    'ZapMachine': dict(
        cost=6.0, cls='troop', kind='troop', air=False, bodies=1,
        proxy_card='Wizard', proxy_body='Wizard',
        body_map={'ZapMachine': 'Wizard'},
        why='ranged splash ground (never a champion proxy)'),
}

CLASS_ONLY = {
    'troop': dict(proxy_body='Knight', cost=4.0),
    'building': dict(proxy_body='BombTower', cost=4.0),
    'air': dict(proxy_body='BabyDragon', cost=4.0),
}

SHARED_BODY = {
    'Assassin': [],
    'AxeMan': [],
    'BarbarianHut': ['BarbLog'],
    'Barbarians': ['BarbLog'],
    'BattleHealer': [],
    'BattleRam': ['BarbLog'],
    'Bomber': [],
    'BossBandit': [],
    'Bowler': [],
    'Clone': [],
    'DarkMagic': [],
    'DarkWitch': ['Bats'],
    'DartBarrell': [],
    'ElectroDragon': [],
    'ElectroGiant': [],
    'ElectroWizard': [],
    'EliteArcher': [],
    'Elixir Collector': [],
    'ElixirGolem': [],
    'Fisherman': [],
    'Freeze': [],
    'GiantBuffer': [],
    'GiantSkeleton': [],
    'GoblinCage': [],
    'GoblinCurse': ['GoblinBarrel'],
    'GoblinDemolisher': [],
    'GoblinDrill': ['GoblinBarrel'],
    'GoblinGiant': ['GoblinGang', 'GoblinHut'],
    'GoblinMachine': [],
    'GoldenKnight': [],
    'Graveyard': [],
    'Heal': [],
    'Hunter': [],
    'IceWizard': [],
    'InfernoDragon': [],
    'LavaHound': [],
    'LittlePrince': [],
    'MegaKnight': [],
    'MegaMinion': [],
    'MergeMaiden': [],
    'MiniSparkys': [],
    'Mirror': [],
    'Monk': [],
    'Mortar': [],
    'MovingCannon': [],
    'Pekka': [],
    'Phoenix': [],
    'Rage': [],
    'RageBarbarian': [],
    'RamRider': [],
    'Ronin': [],
    'RoyalGiant': [],
    'RoyalRecruits': [],
    'SkeletonBalloon': [],
    'SkeletonDragons': [],
    'SkeletonKing': [],
    'SkeletonWarriors': [],
    'Snowball': [],
    'SpearGoblins': ['GoblinGang', 'GoblinHut'],
    'SuspiciousBush': [],
    'ThreeMusketeers': [],
    'Tombstone': ['SkeletonArmy', 'Skeletons'],
    'Vines': [],
    'Witch': ['SkeletonArmy', 'Skeletons'],
    'WitchMother': [],
    'ZapMachine': [],
}

_BODY_INDEX = {}
for _card, _entry in NAMED.items():
    for _true, _proxy in _entry['body_map'].items():
        if _BODY_INDEX.setdefault(_true, _proxy) != _proxy:
            raise ValueError(f'body {_true} maps to two proxies: {_card}')


def proxy_body(true_body: str, *, kind=None, air=None):
    """Proxy body for a true body name: body_map first, then the 47-list itself, then CLASS_ONLY."""
    if true_body in _BODY_INDEX:
        return _BODY_INDEX[true_body]
    if true_body in BODIES_47:
        return true_body
    if kind == 'building':
        return CLASS_ONLY['building']['proxy_body']
    if kind == 'troop':
        return CLASS_ONLY['air' if air else 'troop']['proxy_body']
    return None

