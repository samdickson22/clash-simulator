"""Write live/nulls/night/scenes.json: scripted multi-card scenes for the 2nd Null's block (LIVE LEAD 10-17).

A scene = deploys [{side: ours|opp, card, x, y, at}] in native milli-tiles (x 0-18000, y 0-32000; ours = bottom =
native owner 1, y > 16000 for troops/buildings; opp = top = native owner 0). `at` = ticks after the scene starts;
each deploy is played in order once its card is in hand and affordable. <= 4 unique cards per side.
  python3 make_scenes.py
"""
import json
from pathlib import Path

OURS_TOWER = {'L': (3500, 25500), 'R': (14500, 25500)}
OPP_TOWER = {'L': (3500, 6500), 'R': (14500, 6500)}
OURS_FRONT = {'L': (3500, 23500), 'R': (14500, 23500)}
OPP_FRONT = {'L': (3500, 8500), 'R': (14500, 8500)}
OURS_BRIDGE = {'L': (3500, 17500), 'R': (14500, 17500)}
OPP_BRIDGE = {'L': (3500, 14500), 'R': (14500, 14500)}
OTHER = {'ours': 'opp', 'opp': 'ours'}


def d(side, card, xy, at):
    return dict(side=side, card=card, x=int(xy[0]), y=int(xy[1]), at=at)


def front(side, lane):
    return (OURS_FRONT if side == 'ours' else OPP_FRONT)[lane]


def tower(side, lane):
    return (OURS_TOWER if side == 'ours' else OPP_TOWER)[lane]


def bridge(side, lane):
    return (OURS_BRIDGE if side == 'ours' else OPP_BRIDGE)[lane]


def off(xy, dx=0, dy=0):
    return (xy[0] + dx, xy[1] + dy)


scenes = {}
# --- A: spells / projectiles in flight + landing, cast by each side onto defended units at the other side's tower
for spell in ['GoblinBarrel', 'Fireball', 'Rocket', 'Log', 'BarbLog', 'Arrows', 'Zap']:
    for caster in ('opp', 'ours'):
        tgt = OTHER[caster]
        lane = 'L' if caster == 'opp' else 'R'
        deps = [d(tgt, 'Knight', front(tgt, lane), 0), d(tgt, 'Archer', off(tower(tgt, lane), 0, 0), 0)]
        if spell in ('Log', 'BarbLog'):
            # rolling spells can't be placed on the enemy half: cast on the caster's own half behind its bridge and
            # roll forward into the target side's troops pushing over that bridge
            spot = off(bridge(caster, lane), 0, -1500 if caster == 'opp' else 1500)
            push = off(bridge(tgt, lane), 0, 1000 if tgt == 'ours' else -1000)
            deps = [d(tgt, 'Knight', push, 0), d(tgt, 'Skeletons', off(push, 0, 800 if tgt == 'ours' else -800), 15),
                    d(caster, spell, spot, 80)]
        else:
            deps += [d(caster, spell, tower(tgt, lane), 90)]
        if spell == 'GoblinBarrel':  # defender zaps the landed goblins (landing + spawn + stun)
            deps += [d(tgt, 'Zap', tower(tgt, lane), 175)]
        else:  # a second, different spell by the caster on the same spot later
            deps += [d(caster, 'Zap' if spell != 'Zap' else 'Arrows', tower(tgt, lane), 260)]
        scenes[f'spell_{spell}_{caster}'] = dict(group='A_spells', deploys=deps, max_ticks=700)

# --- B: our new live deck as OURS (team 0) in dense mixed fights with look-alikes
B = {
    'hog_vs_skarmy_goblins': [d('ours', 'HogRider', OURS_BRIDGE['R'], 0), d('ours', 'ElectroSpirit', off(OURS_BRIDGE['R'], 0, 1000), 10),
                              d('opp', 'SkeletonArmy', OPP_FRONT['R'], 70), d('opp', 'Goblins', off(OPP_FRONT['R'], -1000, -500), 90)],
    'skeletons_vs_witch_tombstone': [d('opp', 'Witch', OPP_BRIDGE['L'], 0), d('opp', 'Tombstone', (4500, 11000), 30),
                                     d('ours', 'Skeletons', OURS_FRONT['L'], 120), d('ours', 'Bats', off(OURS_FRONT['L'], 1000, 0), 135),
                                     d('ours', 'ElectroSpirit', off(OURS_FRONT['L'], -500, 500), 160)],
    'spirits_lookalikes': [d('ours', 'Archer', OURS_FRONT['L'], 0), d('opp', 'IceSpirits', OPP_BRIDGE['L'], 40),
                           d('opp', 'Heal', off(OPP_BRIDGE['L'], 1000, -500), 55), d('ours', 'ElectroSpirit', off(OURS_BRIDGE['L'], 0, 1500), 90),
                           d('opp', 'FireSpirits', off(OPP_BRIDGE['L'], -500, -1000), 120), d('ours', 'Skeletons', OURS_FRONT['L'], 160)],
    'goblins_vs_archers_bats_cannon': [d('ours', 'Cannon', (9000, 21000), 0), d('ours', 'Archer', OURS_FRONT['R'], 10),
                                       d('opp', 'Goblins', OPP_BRIDGE['R'], 60), d('opp', 'SpearGoblins', off(OPP_BRIDGE['R'], -1000, -1000), 75),
                                       d('ours', 'Bats', off(OURS_FRONT['R'], 0, -1500), 120), d('opp', 'GoblinGang', off(OPP_BRIDGE['R'], 0, -1500), 170)],
    'hog_vs_rams_hogs': [d('ours', 'HogRider', OURS_BRIDGE['L'], 0), d('opp', 'BattleRam', OPP_BRIDGE['R'], 20),
                         d('ours', 'Cannon', (9000, 21000), 60), d('ours', 'Skeletons', off(OURS_TOWER['R'], 0, -2000), 120),
                         d('opp', 'RamRider', OPP_BRIDGE['R'], 200), d('opp', 'RoyalHogs', OPP_BRIDGE['L'], 330)],
    'bats_vs_minions_witch': [d('opp', 'Witch', OPP_BRIDGE['R'], 0), d('ours', 'Bats', off(OURS_FRONT['R'], 0, -1000), 80),
                              d('opp', 'Minions', off(OPP_BRIDGE['R'], 0, -1000), 100), d('ours', 'Archer', OURS_FRONT['R'], 110),
                              d('ours', 'ElectroSpirit', off(OURS_FRONT['R'], 1000, 0), 150)],
}
for k, v in B.items():
    scenes[f'deck_{k}'] = dict(group='B_our_deck', deploys=v, max_ticks=1200)

# --- C: the 12 newly owned cards as OURS (and mirrored as OPP) in 4-v-4 fights
owned = [['BabyDragon', 'Witch', 'Musketeer', 'Knight'], ['Pekka', 'SkeletonWarriors', 'Wizard', 'MegaMinion'],
         ['SkeletonArmy', 'RoyalHogs', 'BattleRam', 'InfernoTower']]
foes = [['SkeletonArmy', 'MegaMinion', 'Wizard', 'SkeletonWarriors'], ['Knight', 'Musketeer', 'BabyDragon', 'Witch'],
        ['Pekka', 'SkeletonWarriors', 'Musketeer', 'Knight']]
POS_OURS = [OURS_BRIDGE['L'], off(OURS_FRONT['L'], 1000, 0), off(OURS_BRIDGE['L'], 0, 2500), off(OURS_FRONT['L'], -500, -1500)]
POS_OPP = [OPP_BRIDGE['L'], off(OPP_FRONT['L'], 1000, 0), off(OPP_BRIDGE['L'], 0, -2500), off(OPP_FRONT['L'], -500, 1500)]
for n, (mine, theirs) in enumerate(zip(owned, foes)):
    for swap in (False, True):
        a, b = (mine, theirs) if not swap else (theirs, mine)
        deps = []
        for i in range(4):
            ca, cb = a[i], b[i]
            pa = (6000, 21500) if ca == 'InfernoTower' else POS_OURS[i]
            pb = (6000, 10500) if cb == 'InfernoTower' else POS_OPP[i]
            deps += [d('ours', ca, pa, 120 * i), d('opp', cb, pb, 120 * i + 40)]
        scenes[f'owned{n}{"_swap" if swap else ""}'] = dict(group='C_owned12', deploys=deps, max_ticks=1600)

# --- D: our Cannon in the centre pulling Hog / Ram / Royal Hogs pushes from either bridge
for att in ['HogRider', 'BattleRam', 'RoyalHogs']:
    for lane in ('L', 'R'):
        for cy in (21000, 22500):
            deps = [d('ours', 'Cannon', (8500 if lane == 'L' else 9500, cy), 0), d('opp', att, OPP_BRIDGE[lane], 40),
                    d('ours', 'Skeletons', off(OURS_TOWER[lane], 0, -2500), 150)]
            scenes[f'pull_{att}_{lane}_{cy}'] = dict(group='D_cannon_pull', deploys=deps, max_ticks=700)

for k, s in scenes.items():
    for side in ('ours', 'opp'):
        uniq = {x['card'] for x in s['deploys'] if x['side'] == side}
        assert len(uniq) <= 4, (k, side, uniq)
    for x in s['deploys']:
        assert 0 <= x['x'] <= 18000 and 0 <= x['y'] <= 32000, (k, x)
Path(__file__).with_name('scenes.json').write_text(json.dumps(scenes, indent=1))
from collections import Counter
print(len(scenes), Counter(s['group'] for s in scenes.values()))
