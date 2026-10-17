"""DECK SEARCH v3: owned cards, reachable levels, candidate decks and upgrade costs (read-only; no account actions).

Inputs (job dir copies, never the live tree): the live collection.json (owned cards, levels, held copies, gold,
wild cards) and the official rarity-aware upgrade table (bot-deckopt2/official-upgrade-table.json). Rarity and
elixir come from the pinned gamedata (bot-deckopt2/upgrade-source-gamedata.json).

Reachable level (row A): the highest level each card reaches from its HELD copies plus gold, one card at a time,
no wild cards (the 4 rare wilds stay reserved for Valkyrie; the 54 common wilds are kept), no gems. Sam's eight
cards have no upgrade completable from held copies, so they stay at their current levels. BabyDragon (epic) is
capped at L10 (14,400 gold); L11 would cost another 15,000. Every deck's total gold must fit under gold minus the
5,000 reserve in the account's spending rule.
"""
from __future__ import annotations

import json
from pathlib import Path

JOB = Path('/mpac/sdicks02/jobs/clasher/bot-deckopt3')
INPUTS = JOB / 'inputs'
COLLECTION = INPUTS / 'collection-live-20261017T2022Z.json'
TABLE = INPUTS / 'official-upgrade-table.json'
GAMEDATA = Path('/mpac/sdicks02/jobs/clasher/bot-deckopt2/upgrade-source-gamedata.json')
RESERVE_GOLD = 5000
CAPS = {'BabyDragon': 10}
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
    's-bd4bats': swap(SAM, Bats='BabyDragon'),
    's-bd4valk': swap(SAM, Valkyrie='BabyDragon'),
    's-arrows': swap(SAM, Zap='Arrows'),
    's-skel': swap(SAM, Bats='Skeletons'),
    's-wiz4valk': swap(SAM, Valkyrie='Wizard'),
    's-skdrag': swap(SAM, Bats='SkeletonDragons'),
    's-espirit': swap(SAM, Bats='ElectroSpirit'),
    's-cage': swap(SAM, Cannon='GoblinCage'),
    's-spear': swap(SAM, Bats='SpearGoblins'),
    # double swaps from Sam's deck
    's-inf-bd': swap(SAM, Cannon='InfernoTower', Bats='BabyDragon'),
    's-inf-arrows': swap(SAM, Cannon='InfernoTower', Zap='Arrows'),
    's-inf-skel': swap(SAM, Cannon='InfernoTower', Bats='Skeletons'),
    's-bd-arrows': swap(SAM, Bats='BabyDragon', Zap='Arrows'),
    's-inf-bd4valk': swap(SAM, Cannon='InfernoTower', Valkyrie='BabyDragon'),
    # swaps from last night's winner
    'w-zap': swap(DK2, Goblins='Zap'),
    'w-bd': swap(DK2, Goblins='BabyDragon'),
    'w-bats': swap(DK2, Skeletons='Bats'),
    # archetypes
    'a-ram-bd': ['BattleRam', 'BabyDragon', 'Valkyrie', 'Archers', 'InfernoTower', 'Fireball', 'Zap', 'Skeletons'],
    'a-giant-bd': ['Giant', 'BabyDragon', 'MiniPekka', 'Archers', 'InfernoTower', 'Fireball', 'Zap', 'Skeletons'],
    'a-mortar': ['Mortar', 'Archers', 'Skeletons', 'Valkyrie', 'Bats', 'InfernoTower', 'Fireball', 'Zap'],
}


def load():
    collection = json.loads(COLLECTION.read_text())
    account = collection.pop('_account')
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
    elif t['upgradeMaterialCount'][index] != entry['needed']:
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
