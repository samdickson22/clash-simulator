"""DECK SEARCH v3: owned cards, reachable levels, candidate decks and upgrade costs (read-only; no account actions).

Inputs (job dir copies, never the live tree): the live collection.json (owned cards, levels, held copies, gold,
wild cards) and the official rarity-aware upgrade table (bot-deckopt2/official-upgrade-table.json). Rarity and
elixir come from the pinned gamedata (bot-deckopt2/upgrade-source-gamedata.json).

Reachable level (row A): the highest level each card reaches from its HELD copies plus gold, one card at a time,
no wild cards (the 4 rare wilds stay reserved for Valkyrie; the 54 common wilds are kept), no gems. Sam's eight
cards have no upgrade completable from held copies, so they stay at their current levels. Every deck's total gold
must fit under gold minus the 5,000 reserve in the account's spending rule.
Identity correction (LIVE LEAD fresh zoom 2026-10-17T21:17Z): the entry stored as "BabyDragon" (Level 3, 184/2,
orange strip) is the in-game card "Minion Giant", absent from the pinned gamedata and the full-scope runtime. It is
dropped (NOT_OWNED) and no Baby Dragon deck is a candidate (PREREG amendment 3).
"""
from __future__ import annotations

import json
from pathlib import Path

JOB = Path('/mpac/sdicks02/jobs/clasher/bot-deckopt3')
INPUTS = JOB / 'inputs'
COLLECTION = INPUTS / 'collection-20261017b.json'  # Sam's 42-card snapshot 22:25Z (sha256 0078ecde...); amendment 9
OVERRIDES = {'Bats': 8, 'Fireball': 7, 'Zap': 9}  # Sam's upgrades after 22:25Z (Battle Deck screenshot)
OVERRIDE_COPIES = {'Zap': 200}  # 600 held - 400 for 8->9
NAME_MAP = {'FireSpirit': 'FireSpirits', 'Guards': 'SkeletonWarriors', 'FlyingMachine': 'DartBarrell'}
TABLE = INPUTS / 'official-upgrade-table.json'
GAMEDATA = Path('/mpac/sdicks02/jobs/clasher/bot-deckopt2/upgrade-source-gamedata.json')
RESERVE_GOLD = 5000
SAM5 = ['HogRider', 'Archers', 'Cannon', 'Skeletons', 'Fireball', 'Zap', 'ElectroSpirit', 'Bats']  # Sam's live deck 22:30Z
CAPS = {}
NOT_OWNED = {'MinionGiant', 'ThreeMusketeers'}  # no runtime mapping (Minion Giant) / rejected by the full-scope vocab (ThreeMusketeers)
NAME_FIX = {'Archers': 'Archer'}  # gamedata spells[].name where it differs from the engine / collection name
START = {'Common': 1, 'Rare': 3, 'Epic': 6, 'Legendary': 9, 'Champion': 11}

WARN = []
SAM = ['Valkyrie', 'Archers', 'Bats', 'Cannon', 'Fireball', 'Zap', 'MiniPekka', 'Giant']
DK2 = ['Valkyrie', 'Archers', 'Goblins', 'InfernoTower', 'Fireball', 'Giant', 'MiniPekka', 'Skeletons']


def swap(deck, **out_in):
    deck = list(deck)
    for old, new in out_in.items():
        deck[deck.index(old)] = new
    return deck


# Screen candidates: anchors, single / double swaps from Sam's deck and from last night's winner, and three
# archetype decks. Each keeps a win condition, a spell, air defence and (except siege) one building.
CANDIDATES = {
    'sam': SAM,
    'dk2': DK2,
    # single swaps from Sam's deck
    's-inferno': swap(SAM, Cannon='InfernoTower'),
    's-arrows': swap(SAM, Zap='Arrows'),
    's-skel': swap(SAM, Bats='Skeletons'),
    's-wiz4valk': swap(SAM, Valkyrie='Wizard'),
    's-skdrag': swap(SAM, Bats='SkeletonDragons'),
    's-espirit': swap(SAM, Bats='ElectroSpirit'),
    's-cage': swap(SAM, Cannon='GoblinCage'),
    's-spear': swap(SAM, Bats='SpearGoblins'),
    's-mm4bats': swap(SAM, Bats='MegaMinion'),             # amendment 3 (replaces s-bd4bats)
    # double swaps from Sam's deck
    's-inf-arrows': swap(SAM, Cannon='InfernoTower', Zap='Arrows'),
    's-inf-skel': swap(SAM, Cannon='InfernoTower', Bats='Skeletons'),
    's-inf-wiz4valk': swap(SAM, Cannon='InfernoTower', Valkyrie='Wizard'),   # amendment 3
    # swaps from last night's winner
    'w-zap': swap(DK2, Goblins='Zap'),
    'w-bats': swap(DK2, Skeletons='Bats'),
    'w-wiz': swap(DK2, Goblins='Wizard'),                   # amendment 3 (replaces w-bd)
    # archetypes
    'a-ram': ['BattleRam', 'Wizard', 'Valkyrie', 'Archers', 'InfernoTower', 'Fireball', 'Zap', 'Skeletons'],   # amendment 3
    'a-giant-wiz': ['Giant', 'Wizard', 'MiniPekka', 'Archers', 'InfernoTower', 'Fireball', 'Zap', 'Skeletons'],  # amendment 3
    'a-mortar': ['Mortar', 'Archers', 'Skeletons', 'Valkyrie', 'Bats', 'InfernoTower', 'Fireball', 'Zap'],
}


# HOG stage (PREREG-HOG.md): Hog Rider owned since 2026-10-17T22:16Z (free reward). Screened at HogRider L7 until the
# reached level L is confirmed; finals at L, L+1, L+2 (arm suffix @<level>).
HOG = {
    'h-classic': ['HogRider', 'Cannon', 'Musketeer', 'Fireball', 'Zap', 'Skeletons', 'ElectroSpirit', 'Knight'],
    'h-valk': ['HogRider', 'Cannon', 'Musketeer', 'Fireball', 'Zap', 'Skeletons', 'ElectroSpirit', 'Valkyrie'],
    'h-archers': ['HogRider', 'Cannon', 'Archers', 'Fireball', 'Zap', 'Skeletons', 'ElectroSpirit', 'Valkyrie'],
    'h-bats': ['HogRider', 'Cannon', 'Musketeer', 'Fireball', 'Zap', 'Skeletons', 'Bats', 'Valkyrie'],
    'h-sam': swap(SAM, Giant='HogRider'),
    'h-sam-arrows': swap(SAM, Giant='HogRider', Zap='Arrows'),
    'h-classic-arrows': ['HogRider', 'Cannon', 'Musketeer', 'Fireball', 'Arrows', 'Skeletons', 'ElectroSpirit', 'Knight'],
    'h-hog4bats': swap(SAM, Bats='HogRider'),
}


def load():
    raw = json.loads(COLLECTION.read_text())
    if 'owned_cards' in raw and isinstance(raw['owned_cards'][0].get('level'), str):  # 20261017b (Sam's screenshots)
        collection = {}
        for c in raw['owned_cards']:
            lv = int(c['level'].split()[-1])
            if c['name'] == 'ElectroSpirit':  # boosted display; base null; 425 copies at needed=2 = L1 base -> L8 from held
                lv = None
            collection[NAME_MAP.get(c['name'], c['name'])] = dict(level=lv, copies=c['copies'], needed=c['needed'])
        for card, lv in OVERRIDES.items():  # Sam's own upgrades after the 22:25Z screenshots (Battle Deck 22:30Z)
            collection[card] = dict(level=lv, copies=OVERRIDE_COPIES.get(card, 0), needed=None)
        a = raw['account']
        account = dict(gold=a['gold'], gems=a['gems'], wild_cards=a['wild_cards'], king_tower_level=7,
                       last_observed_utc=raw['observed_at_utc'])
    elif 'owned_cards' in raw:  # verified snapshot format (list of owned cards + account block)
        collection = {c['name']: dict(level=c['level'], copies=c['copies'], needed=c['needed']) for c in raw['owned_cards']}
        a = raw['account']
        account = dict(gold=a['gold'], gems=a['gems'], wild_cards=a['wild_cards'], king_tower_level=a['king_level'],
                       last_observed_utc=raw['observed_at_utc'])
    else:
        collection = raw
        account = collection.pop('_account')
    collection = {k: v for k, v in collection.items() if k not in NOT_OWNED}
    table = json.loads(TABLE.read_text())
    spells = {s['name']: s for s in json.loads(GAMEDATA.read_text())['items']['spells']}
    info = {}
    for card in collection:
        s = spells[NAME_FIX.get(card, card)]
        info[card] = dict(rarity=s['rarity'], elixir=int(s['manaCost']))
    return collection, account, table, info


def reachable(card, entry, rarity, table):
    """Level after every upgrade completable from held copies (+ gold), and the steps taken."""
    t = table[rarity]
    level = entry['level'] if entry['level'] is not None else START[rarity]
    copies = entry['copies']
    # consistency: the collection's 'needed' must equal the table's next-step material count
    index = level - t['relativeLevel'] - 1
    if not 0 <= index < len(t['upgradeMaterialCount']):
        # an out-of-range level whose 'needed' matches the rarity's first step = a card at its starting level
        assert entry['needed'] == t['upgradeMaterialCount'][0], (card, entry, rarity)
        WARN.append(f'{card}: recorded level {entry["level"]} is below the {rarity} start; needed={entry["needed"]} = first step, so L{START[rarity]}')
        level = START[rarity]
    elif entry['needed'] is not None and t['upgradeMaterialCount'][index] != entry['needed']:
        WARN.append(f'{card}: recorded needed {entry["needed"]} != table {t["upgradeMaterialCount"][index]} at L{level}; level + table used')
    steps = []
    while True:
        index = level - t['relativeLevel'] - 1
        need, gold = t['upgradeMaterialCount'][index], t['upgradeCost'][index]
        if not need or copies < need or level >= CAPS.get(card, 99):
            break
        copies -= need
        steps.append(dict(card=card, frm=level, to=level + 1, copies=need, gold=gold))
        level += 1
    return level, steps


def levels():
    collection, account, table, info = load()
    out = {}
    for card, entry in sorted(collection.items()):
        level, steps = reachable(card, entry, info[card]['rarity'], table)
        out[card] = dict(level=level, current=entry['level'], steps=steps, gold=sum(s['gold'] for s in steps), **info[card])
    return out, account


def our_levels_arg(lv, account):
    return ','.join(f'{c}={v["level"]}' for c, v in sorted(lv.items())) + f',King={account["king_tower_level"]}'


def deck_summary(name, deck, lv, account):
    gold = sum(lv[c]['gold'] for c in deck)
    budget = account['gold'] - RESERVE_GOLD
    assert gold <= budget, (name, gold, budget)
    mean = sum(lv[c]['level'] for c in deck) / 8
    return dict(name=name, deck=deck, levels={c: lv[c]['level'] for c in deck}, mean_level=mean,
                elixir=sum(lv[c]['elixir'] for c in deck) / 8, gold=gold,
                steps=[s for c in deck for s in lv[c]['steps']])


if __name__ == '__main__':
    lv, account = levels()
    for c, v in lv.items():
        print(f"{c:16s} {v['rarity']:7s} e{v['elixir']} L{v['current']}->{v['level']} gold {v['gold']}")
    print(our_levels_arg(lv, account))
    print('\n'.join(WARN))
    for name, deck in CANDIDATES.items():
        assert len(set(deck)) == 8 and all(c in lv for c in deck), name
        s = deck_summary(name, deck, lv, account)
        cards = ' '.join(c + str(lv[c]['level']) for c in deck)
        print(f"{name:14s} mean L{s['mean_level']:.2f} elixir {s['elixir']:.2f} gold {s['gold']:6d}  {cards}")
