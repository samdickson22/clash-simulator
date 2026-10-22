"""Frozen, size-independent case draws for the registered outcome-RL stage.

This module uses no engine or model imports. Populations are supplied explicitly;
missing strata are errors, never invitations to substitute a different opponent.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import random

SEEDS = (2026102101, 2026102102, 2026102103)
LEAGUE = {'current': 30, 'reservoir': 20, 'bc': 15, 'hp1_v330': 15, 'live': 15, 'script': 5}
DECKS = {'hog': 50, 'meta': 30, 'random': 20}
LEVELS = {'empirical': 70, 'adjacent': 20, 'stress': 10}
HOG = dict(Skeletons=8, Musketeer=7, IceGolem=7, Cannon=9, Fireball=8, Zap=9, IceSpirit=8, HogRider=10)
HP1_SHA = '73bbbd860625a24e4e61f15dd30596c78542d04c4eedfcf2ab1346183de2c70e'
ANCHORS = {'M': '947af5cb5ac2b47fe666b329f21326e180b4b0d742bd97b1867603446cad79f4',
           'S100': '74c7640776fd2c00fdd20c8c732dc07f4ed94c98964b5f816de4a60ae7cc332f'}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def encoded(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(obj):
    return hashlib.sha256(encoded(obj)).hexdigest()


def file_sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def pinned(ref):
    require(set(ref) == {'path', 'sha256'}, 'artifact requires exact path and SHA256')
    path = Path(ref['path']).resolve()
    require(file_sha(path) == ref['sha256'], f'artifact SHA mismatch: {path}')
    return path


def rng(seed, index, label):
    return random.Random(int(digest(['pv1-registered-v1', seed, index, label]), 16))


def pick(rows, generator):
    return generator.choices(rows, weights=[r['weight'] for r in rows], k=1)[0]


def category(weights, generator):
    return generator.choices(list(weights), weights=list(weights.values()), k=1)[0]


def profile(row, vocabulary):
    require(isinstance(row, dict) and set(row) >= {'deck', 'cards', 'tower', 'weight'}, 'incomplete population row')
    deck, cards = row['deck'], row['cards']
    require(len(deck) == len(set(deck)) == 8 and set(deck) <= vocabulary, 'deck outside qualified vocabulary')
    require(set(cards) == set(deck), 'incomplete or excess level map')
    require(all(type(v) is int and 1 <= v <= 16 for v in cards.values()), 'invalid card level')
    require(type(row['tower']) is int and 1 <= row['tower'] <= 16, 'invalid tower level')
    require(type(row['weight']) in (int, float) and math.isfinite(row['weight']) and row['weight'] > 0,
            'population weight must be positive and finite')


def validate_populations(pop):
    require(pop.get('schema') == 'pv1-rl-populations-v1', 'population schema')
    vocabulary = set(pop['vocabulary'])
    require(len(vocabulary) == len(pop['vocabulary']) and set(HOG) <= vocabulary, 'vocabulary mismatch')
    require(set(pop['opponents']) == set(LEVELS), 'all three opponent strata required')
    for family, rows in pop['opponents'].items():
        require(bool(rows), f'missing opponent stratum: {family}')
        for row in rows:
            profile(row, vocabulary)
            require(bool(row.get('source_id')), 'historical/smoothing/stress provenance required')
            if family == 'stress':
                require(all(12 <= v <= 16 for v in row['cards'].values()) and 12 <= row['tower'] <= 16,
                        'stress levels must be 12..16')
    require(bool(pop['meta']), 'frequency-weighted meta population required')
    for row in pop['meta']:
        profile(row, vocabulary)
        require(row.get('level_kind') in ('realistic', 'stress'), 'meta level kind required')
        require(8 <= row['tower'] <= 11 if row['level_kind'] == 'realistic' else 12 <= row['tower'] <= 16,
                'meta tower levels outside registered bands')
    realistic = sum(r['weight'] for r in pop['meta'] if r['level_kind'] == 'realistic')
    total = sum(r['weight'] for r in pop['meta'])
    require(math.isclose(realistic/total, .8, abs_tol=1e-12), 'meta profiles must be 80% realistic / 20% stress')
    require(set(pop['random_card_levels']) == vocabulary, 'random decks need complete explicit levels')
    require(all(type(v) is int and 1 <= v <= 16 for v in pop['random_card_levels'].values()), 'random card levels')
    require(type(pop['random_tower']) is int and 1 <= pop['random_tower'] <= 16, 'random tower')
    require(set(pop['champions']) <= vocabulary, 'champion identity outside vocabulary')
    require(len(vocabulary-set(pop['champions'])) >= 7, 'insufficient nonchampion random-deck vocabulary')
    require(bool(pop.get('excluded_mass')) and bool(pop.get('sources')), 'source pins and excluded mass required')
    return pop


class Schedule:
    def __init__(self, populations, seed):
        require(seed in SEEDS, 'unregistered seed')
        self.pop, self.seed = validate_populations(populations), seed
        self.sha256 = digest({'seed': seed, 'populations': populations, 'league': LEAGUE,
                              'decks': DECKS, 'levels': LEVELS, 'algorithm': 'pv1-registered-v1'})

    def case(self, index):
        require(type(index) is int and index >= 0, 'invalid game sequence')
        own_kind = category(DECKS, rng(self.seed, index, 'deck-kind'))
        level_kind = category(LEVELS, rng(self.seed, index, 'level-kind'))
        opponent = pick(self.pop['opponents'][level_kind], rng(self.seed, index, 'opponent-profile'))
        if own_kind == 'hog':
            own = dict(deck=list(HOG), cards=dict(HOG), tower=9)
        elif own_kind == 'meta':
            own = pick(self.pop['meta'], rng(self.seed, index, 'meta'))
        else:
            generator = rng(self.seed, index, 'random-deck')
            pool, deck = sorted(self.pop['vocabulary']), []
            while len(deck) < 8:
                card = generator.choice(pool)
                deck.append(card)
                pool.remove(card)
                if card in self.pop['champions']:
                    pool = [c for c in pool if c not in self.pop['champions']]
            own = dict(deck=deck, cards={c: self.pop['random_card_levels'][c] for c in deck},
                       tower=self.pop['random_tower'])
        seat = index % 2
        decks, cards, towers = [None, None], {}, {}
        for s, row in ((seat, own), (1-seat, opponent)):
            decks[s] = list(row['deck'])
            rng(self.seed, index, f'order-{s}').shuffle(decks[s])
            cards[s], towers[s] = dict(row['cards']), row['tower']
        require(index < 2**48, 'case index exceeds registered training seed namespace')
        return dict(index=index, seat=seat, seed=(1 << 60)+(SEEDS.index(self.seed) << 48)+index,
                    decks=decks, levels=dict(cards=cards, towers=towers, planner='l11'),
                    own_kind=own_kind, level_kind=level_kind,
                    league=category(LEAGUE, rng(self.seed, index, 'league')),
                    reservoir_u=rng(self.seed, index, 'reservoir').random(), schedule_sha256=self.sha256)


def validate_banks(banks, seed):
    require(banks.get('schema') == 'pv1-rl-banks-v1' and banks['seed'] == seed, 'bank identity')
    require(set(banks['dev']) == {'0', '10', '20', '30'}, 'DEV snapshots must be 0/10/20/30')
    seen = set(banks['excluded_engine_seeds'])
    require(bool(seen), 'explicit BC/DEV/training exclusion inventory required')
    require(all(rows == banks['dev']['0'] for rows in banks['dev'].values()),
            'all DEV snapshots must use the same fixed 200 assignments')
    for name, rows in [('primary', banks['primary']), ('dev', banks['dev']['0'])]:
        require(len(rows) == (1600 if name == 'primary' else 200), 'incorrect evaluation assignment count')
        local = set()
        for index, row in enumerate(rows):
            require(row['index'] == index, 'evaluation assignment index mismatch')
            require(type(row['seed']) is int and 0 < row['seed'] < 1 << 60
                    and row['opponent'] == 'live' and row['seed'] not in seen and row['seed'] not in local,
                    'evaluation must be fresh, unique and current LIVE only')
            seat = row['seat']
            require(type(seat) is int and seat in (0, 1), 'bank seat')
            cards = row['levels']['cards']
            own = cards[str(seat)] if str(seat) in cards else cards[seat]
            towers = row['levels']['towers']
            require(own == HOG and towers[seat] == 9 and set(row['decks'][seat]) == set(HOG),
                    'evaluation own account Hog levels required')
            require(row['levels']['planner'] == 'l11', 'public planner only')
            for s in (0, 1):
                level_map = cards[str(s)] if str(s) in cards else cards[s]
                profile(dict(deck=row['decks'][s], cards=level_map, tower=towers[s], weight=1),
                        set(row['decks'][s]))
            local.add(row['seed'])
        seen |= local
    require(set(banks['audits']) == {'defense', 'spell'}, 'defense and spell audit roots required')
    for ref in banks['audits'].values():
        pinned(ref)
    inventory = json.loads(pinned(banks['exclusion_inventory']).read_text())
    require(inventory['seeds'] == banks['excluded_engine_seeds'], 'exclusion inventory mismatch')
    from .rl_exclusions import validate
    validate(inventory)
    audit_files = json.loads(pinned(banks['audit_input_manifest']).read_text())
    require(bool(audit_files), 'complete audit input manifest required')
    for ref in audit_files:
        pinned(ref)
    return banks
