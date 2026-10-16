"""Full-pool card names: the 122 ladder cards in the runtime (engine) name space, aliases, proxies (exploration).

Name spaces (all three differ; never mix them):
- ENGINE: R.config / R.costs / R.meta['cards'] keys and deck lists given to play_match. C56 = the 56 r1 names
  (Archers, IceGolem, IceSpirit, BarbLog, BlowdartGoblin, Ghost, ...); the new cards are bot/cards/scope.py
  EXTRA_CARDS (CARD LEAD, pin r1-cards1): Assassin, SkeletonWarriors, Snowball, ...
- VOCAB: builder.card_vocab (contract-v5 token walk, 122 names): Bandit, Guards, GiantSnowball, BarbarianBarrel,
  DartGoblin, RoyalGhost, MergeMaiden_Normal, ...
- DISPLAY / Battle Log / web lists: 'Mini P.E.K.K.A', 'Dart Goblin', 'Spear Goblins', ...
`engine_name(x)` resolves any of them (case/space/punctuation-insensitive) to the ENGINE name.

POOL = C56 + NEW (121 playable). MergeMaiden (Spirit Empress) is in the 122 but EXCLUDED by the scope (no card_vocab
card_action token); it stays out of every deck until the CARD LEAD adds it.
"""
from __future__ import annotations

C56 = (
    'AngryBarbarians', 'ArcherQueen', 'Archers', 'Arrows', 'BabyDragon', 'Balloon', 'BarbLog', 'Bats', 'Berserker',
    'BlowdartGoblin', 'BombTower', 'Cannon', 'DarkPrince', 'Earthquake', 'ElectroSpirit', 'FireSpirits', 'Fireball',
    'Firecracker', 'FirespiritHut', 'Ghost', 'Giant', 'GoblinBarrel', 'GoblinGang', 'GoblinHut', 'Goblins',
    'Goblinstein', 'Golem', 'HogRider', 'IceGolem', 'IceSpirit', 'InfernoTower', 'Knight', 'Lightning', 'Log',
    'MightyMiner', 'Miner', 'MiniPekka', 'MinionHorde', 'Minions', 'Musketeer', 'Poison', 'Prince', 'Princess',
    'Rascals', 'Rocket', 'RoyalDelivery', 'RoyalHogs', 'SkeletonArmy', 'Skeletons', 'Tesla', 'Tornado', 'Valkyrie',
    'Wallbreakers', 'Wizard', 'Xbow', 'Zap',
)
# = bot/cards/scope.py EXTRA_CARDS minus EXCLUDED (test_fullpool checks it when scope.py is importable).
NEW = (
    'Assassin', 'AxeMan', 'BarbarianHut', 'Barbarians', 'BattleHealer', 'BattleRam', 'Bomber', 'BossBandit',
    'Bowler', 'Clone', 'DarkMagic', 'DarkWitch', 'DartBarrell', 'ElectroDragon', 'ElectroGiant', 'ElectroWizard',
    'EliteArcher', 'Elixir Collector', 'ElixirGolem', 'Fisherman', 'Freeze', 'GiantBuffer', 'GiantSkeleton',
    'GoblinCage', 'GoblinCurse', 'GoblinDemolisher', 'GoblinDrill', 'GoblinGiant', 'GoblinMachine', 'GoldenKnight',
    'Graveyard', 'Heal', 'Hunter', 'IceWizard', 'InfernoDragon', 'LavaHound', 'LittlePrince', 'MegaKnight',
    'MegaMinion', 'MiniSparkys', 'Mirror', 'Monk', 'Mortar', 'MovingCannon', 'Pekka', 'Phoenix', 'Rage',
    'RageBarbarian', 'RamRider', 'Ronin', 'RoyalGiant', 'RoyalRecruits', 'SkeletonBalloon', 'SkeletonDragons',
    'SkeletonKing', 'SkeletonWarriors', 'Snowball', 'SpearGoblins', 'SuspiciousBush', 'ThreeMusketeers',
    'Tombstone', 'Vines', 'Witch', 'WitchMother', 'ZapMachine',
)
EXCLUDED = ('MergeMaiden',)
POOL = tuple(sorted(C56 + NEW))
assert len(C56) == 56 and len(NEW) == 65 and len(POOL) == 121 and not set(C56) & set(NEW)

# Real-game deck rule: at most one champion per deck.
CHAMPIONS = frozenset(('ArcherQueen', 'BossBandit', 'Goblinstein', 'GoldenKnight', 'LittlePrince', 'MightyMiner',
                       'Monk', 'SkeletonKing'))

# ENGINE -> VOCAB where they differ (card_vocab names; everything else is the same string).
VOCAB_NAME = {
    'BarbLog': 'BarbarianBarrel', 'BlowdartGoblin': 'DartGoblin', 'Ghost': 'RoyalGhost',
    'Assassin': 'Bandit', 'SkeletonWarriors': 'Guards', 'RageBarbarian': 'Lumberjack', 'EliteArcher': 'MagicArcher',
    'DarkWitch': 'NightWitch', 'SkeletonBalloon': 'SkeletonBarrel', 'Snowball': 'GiantSnowball',
    'MergeMaiden': 'MergeMaiden_Normal',
}

# Extra spellings seen in display lists / the Battle Log / bot.cards.proxy_table (-> ENGINE).
_ALIASES = {
    'Archer': 'Archers', 'IceGolemite': 'IceGolem', 'IceSpirits': 'IceSpirit', 'Ice Golem': 'IceGolem',
    'Ice Spirit': 'IceSpirit', 'Fire Spirit': 'FireSpirits', 'Fire Spirits': 'FireSpirits',
    'P.E.K.K.A': 'Pekka', 'PEKKA': 'Pekka', 'Mini P.E.K.K.A': 'MiniPekka', 'Mini PEKKA': 'MiniPekka',
    'Guards': 'SkeletonWarriors', 'Sparky': 'ZapMachine', 'Lumberjack': 'RageBarbarian', 'Dart Goblin': 'BlowdartGoblin',
    'Elite Barbarians': 'AngryBarbarians', 'Executioner': 'AxeMan', 'Bandit': 'Assassin', 'Night Witch': 'DarkWitch',
    'Royal Ghost': 'Ghost', 'Zappies': 'MiniSparkys', 'Cannon Cart': 'MovingCannon', 'Flying Machine': 'DartBarrell',
    'Wall Breakers': 'Wallbreakers', 'Magic Archer': 'EliteArcher', 'Mother Witch': 'WitchMother',
    'Rune Giant': 'GiantBuffer', 'X-Bow': 'Xbow', 'Furnace': 'FirespiritHut', 'The Log': 'Log',
    'Barbarian Barrel': 'BarbLog', 'Heal Spirit': 'Heal', 'Giant Snowball': 'Snowball', 'Void': 'DarkMagic',
    'Spirit Empress': 'MergeMaiden', 'Skeleton Barrel': 'SkeletonBalloon', 'Elixir Collector': 'Elixir Collector',
    'Battle Ram': 'BattleRam', 'Ram Rider': 'RamRider', 'Skeleton Dragons': 'SkeletonDragons',
    'Goblin Machine': 'GoblinMachine', 'Electro Giant': 'ElectroGiant', 'Royal Recruits': 'RoyalRecruits',
    'Three Musketeers': 'ThreeMusketeers', 'Giant Skeleton': 'GiantSkeleton', 'Barbarian Hut': 'BarbarianHut',
    'Goblin Cage': 'GoblinCage', 'Goblin Hut': 'GoblinHut', 'Spear Goblins': 'SpearGoblins',
    'Goblin Giant': 'GoblinGiant', 'Goblin Drill': 'GoblinDrill', 'Goblin Curse': 'GoblinCurse',
    'Goblin Demolisher': 'GoblinDemolisher', 'Mega Minion': 'MegaMinion', 'Mega Knight': 'MegaKnight',
    'Minion Horde': 'MinionHorde', 'Skeleton Army': 'SkeletonArmy', 'Royal Hogs': 'RoyalHogs',
    'Royal Giant': 'RoyalGiant', 'Royal Delivery': 'RoyalDelivery', 'Bomb Tower': 'BombTower',
    'Inferno Tower': 'InfernoTower', 'Inferno Dragon': 'InfernoDragon', 'Baby Dragon': 'BabyDragon',
    'Electro Spirit': 'ElectroSpirit', 'Electro Wizard': 'ElectroWizard', 'Electro Dragon': 'ElectroDragon',
    'Ice Wizard': 'IceWizard', 'Hog Rider': 'HogRider', 'Dark Prince': 'DarkPrince', 'Goblin Barrel': 'GoblinBarrel',
    'Golden Knight': 'GoldenKnight', 'Skeleton King': 'SkeletonKing', 'Archer Queen': 'ArcherQueen',
    'Mighty Miner': 'MightyMiner', 'Little Prince': 'LittlePrince', 'Boss Bandit': 'BossBandit',
    'Battle Healer': 'BattleHealer', 'Lava Hound': 'LavaHound', 'Suspicious Bush': 'SuspiciousBush',
    'Elixir Golem': 'ElixirGolem', 'ElixirCollector': 'Elixir Collector',
}


def _norm(name):
    return ''.join(ch for ch in str(name).casefold() if ch.isalnum())


_INDEX = {}
for _n in POOL + EXCLUDED:
    _INDEX[_norm(_n)] = _n
for _e, _v in VOCAB_NAME.items():
    _INDEX.setdefault(_norm(_v), _e)
for _a, _e in _ALIASES.items():
    _INDEX.setdefault(_norm(_a), _e)


def engine_name(name, *, strict=True):
    """Any spelling (engine, vocab, display, Battle Log) -> ENGINE name; None (or KeyError if strict) if unknown."""
    hit = _INDEX.get(_norm(name))
    if hit is None and strict:
        raise KeyError(f'unknown card name {name!r}')
    return hit


def vocab_name(engine):
    return VOCAB_NAME.get(engine, engine)


def proxy_card(engine):
    """The C56 ENGINE card a new card is initialised from (bot/cards/proxy_table NAMED[*].proxy_card); C56 -> itself."""
    if engine in C56:
        return engine
    from bot.cards.proxy_table import NAMED
    proxy = NAMED[engine]['proxy_card']
    assert proxy in C56, (engine, proxy)
    return proxy


def body_proxies(engine):
    """{true body name: C56 proxy body name or None} for a new card (proxy_table body_map)."""
    from bot.cards.proxy_table import NAMED
    return dict(NAMED[engine]['body_map']) if engine in NAMED else {}
