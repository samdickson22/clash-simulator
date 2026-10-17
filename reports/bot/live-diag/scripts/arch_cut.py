"""Per-archetype cut of -res vs base across the live-diag L16 paired banks (deck-search driver rows, s62 deck).

Pairs (bank, index, opponent, noise) between player 'res<suffix>' and 'base<suffix>' with the same suffix/noise.
Main table: clean history, no suffix (the deployed configuration). Archetype of the opponent deck by rule (first match).
"""
import json, glob, random, sys
from collections import Counter, defaultdict

L = '/mpac/sdicks02/jobs/clasher/bot-livediag/'
BANKS = {'BASE13 l16noise': ['l16noise'], 'BASE14 ownsize': ['ownsize'],
         'BASE15 cadab-clean': ['cadab-clean-s0', 'cadab-clean-s1', 'cadab-clean-s2'],
         'BASE15 cadab-delay': ['cadab-delay'], 'BASE16 budget': ['budget-s0', 'budget-s1']}
AIR = {'Minions', 'MinionHorde', 'Bats', 'MegaMinion', 'BabyDragon', 'InfernoDragon', 'SkeletonDragons',
       'ElectroDragon', 'Balloon', 'LavaHound', 'SkeletonBarrel', 'Phoenix'}
BUILD = {'Cannon', 'Tombstone', 'GoblinCage', 'InfernoTower', 'BombTower', 'GoblinHut', 'Furnace', 'Tesla',
         'BarbarianHut', 'ElixirCollector', 'Elixir Collector', 'GoblinDrill'}
SPELL = {'Zap', 'Arrows', 'Fireball', 'Log', 'Poison', 'Rocket', 'Lightning', 'Tornado', 'GiantSnowball',
         'BarbLog', 'Earthquake', 'Freeze', 'Rage', 'Heal', 'RoyalDelivery', 'GoblinCurse', 'Void', 'Clone', 'Mirror'}


def archetype(deck):
    d = set(deck)
    if 'RoyalGiant' in d:
        return 'royal-giant'
    if d & {'Xbow', 'Mortar'}:
        return 'siege'
    if d & {'Giant', 'Golem', 'ElectroGiant', 'GoblinGiant', 'Pekka', 'MegaKnight', 'GiantSkeleton', 'LavaHound'}:
        return 'beatdown' if not d & {'LavaHound', 'Balloon'} else 'air'
    if d & {'HogRider', 'BattleRam', 'RamRider', 'Miner', 'WallBreakers'}:
        return 'hog/cycle'
    if 'Balloon' in d or len(d & AIR) >= 3:
        return 'air'
    if 'GoblinBarrel' in d or 'Princess' in d or len(d & SPELL) >= 3:
        return 'bait/spell'
    if len(d & BUILD) >= 2:
        return 'building'
    return 'other'


def score(r):
    return .5 if r.get('draw') else float(r.get('win') or 0)


rows = defaultdict(dict)       # (bank, idx, opp, noise, suffix) -> {'base': s, 'res': s}
decks, vocab = {}, Counter()
for bank, dirs in BANKS.items():
    for d in dirs:
        for p in glob.glob(L + d + '/rows/*.json'):
            r = json.load(open(p))
            if r.get('error') or 'result' not in r:
                continue
            kind, _, suf = r['player'].partition('-')
            key = (bank, r['index'], r['opponent'], r['noise_arm'], suf)
            rows[key][kind] = score(r)
            decks[(bank, r['index'], r['opponent'])] = tuple(r['opponent_deck'])
for dk in set(decks.values()):
    vocab.update(dk)

pairs = [(k, v['res'] - v['base']) for k, v in rows.items() if 'res' in v and 'base' in v]


def ci(xs, seed=0):
    rng = random.Random(seed)
    m = sorted(sum(rng.choice(xs) for _ in xs) / len(xs) for _ in range(4000))
    return round(sum(xs) / len(xs), 3), [round(m[100], 3), round(m[3900], 3)]


def table(sel, title):
    by = defaultdict(list)
    for k, dlt in sel:
        by[(archetype(decks[k[:3]]), k[2])].append(dlt)
        by[(archetype(decks[k[:3]]), 'all')].append(dlt)
        by[('ALL', k[2])].append(dlt)
        by[('ALL', 'all')].append(dlt)
    print('\n##', title)
    print('| archetype | opponent | n | res - base [95% CI] | flag |')
    print('|---|---|---:|---|---|')
    for (a, o), v in sorted(by.items(), key=lambda kv: (kv[0][0] == 'ALL', kv[0][0], kv[0][1] != 'all', kv[0][1])):
        m, c = ci(v)
        flag = 'WORSE' if m < -0.10 and len(v) >= 20 else ('worse (CI<0)' if c[1] < 0 else '')
        print(f'| {a} | {o} | {len(v)} | {m:+.3f} [{c[0]:+.3f}, {c[1]:+.3f}] | {flag} |')


print('vocab', len(vocab), sorted(vocab))
arch = Counter(archetype(dk) for dk in set(decks.values()))
print('distinct opponent decks', len(set(decks.values())), dict(arch))
for a in sorted(arch):
    print(' ', a, [sorted(dk) for dk in set(decks.values()) if archetype(dk) == a][:2])
clean = [(k, d) for k, d in pairs if k[3] == 'clean' and k[4] == '']
table(clean, 'clean history, deployed config (base vs res, no suffix): all L16 banks')
noisy = [(k, d) for k, d in pairs if k[3] != 'clean' and k[4] == '']
table(noisy, 'noisy-history arms (live / own / delay), same pairing')
alls = [(k, d) for k, d in pairs]
table(alls, 'every matched pair (incl. si / K / T suffix twins and noise arms; not independent across arms)')
