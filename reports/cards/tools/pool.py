"""The current ladder card pool from gamedata.json (visible cards, no tower troops)."""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
KIND = dict(spells_characters='troop', spells_buildings='building', spells_other='spell')

# Live/ladder names that differ from the internal gamedata name.
DISPLAY = dict(
    Archer='Archers', Pekka='P.E.K.K.A', MiniPekka='Mini P.E.K.K.A', SkeletonWarriors='Guards',
    ZapMachine='Sparky', RageBarbarian='Lumberjack', IceGolemite='Ice Golem', BlowdartGoblin='Dart Goblin',
    AngryBarbarians='Elite Barbarians', AxeMan='Executioner', Assassin='Bandit', DarkWitch='Night Witch',
    Ghost='Royal Ghost', MiniSparkys='Zappies', MovingCannon='Cannon Cart', DartBarrell='Flying Machine',
    Wallbreakers='Wall Breakers', EliteArcher='Magic Archer', WitchMother='Mother Witch',
    GiantBuffer='Rune Giant', BossBandit='Boss Bandit', Xbow='X-Bow', FirespiritHut='Furnace',
    Log='The Log', BarbLog='Barbarian Barrel', Heal='Heal Spirit', Snowball='Giant Snowball',
    DarkMagic='Void', MergeMaiden='Spirit Empress', SkeletonBalloon='Skeleton Barrel'
)


def ladder_pool(path=None):
    path = path or os.environ.get('CARDS_GAMEDATA') or ROOT / 'gamedata.json'
    items = json.loads(Path(path).read_text())['items']
    arenas = {a['name']: a for a in items['arenas']}
    out = []
    for s in items['spells']:
        if s.get('notVisible') or s.get('source') not in KIND:
            continue
        a = arenas.get(s.get('unlockArena'), {})
        out.append(dict(name=s['name'], kind=KIND[s['source']], cost=s.get('manaCost'), rarity=s.get('rarity'),
                        arena=a.get('arena'), trophies=a.get('trophyLimit'), id=s.get('id'),
                        display=DISPLAY.get(s['name'], s['name'])))
    return out
