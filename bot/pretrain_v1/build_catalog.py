"""Build the pinned pretrain-v1 catalog (catalog/catalog.json) from the deployed memory package's card data.

    python -m bot.pretrain_v1.build_catalog          # rewrites catalog/catalog.json (then commit it)

Inputs (all vendored, hash-checked, never read from a live tree at run time):
  vendor/livemem/data/cards-122.json    deployed live/mem/data/cards-122.json (sha 289d240f...): name, native id, kind,
                                        cost, bodies
  vendor/livemem/data/card-aliases.json deployed aliases (sha 3b2533b9...): client names -> the bot's card names
  vendor/livemem/extra_bodies.json      every character name of the live16402b-r3 runtime (the re-drive projection's
                                        extra_bodies; every class seen in 535,700 live records is in it)

The featurizer reads only catalog.json. Its card/body vocabularies are the model's identity vocabularies; index 0 is
padding and 1 is "unknown" (a name outside the pinned pool), so a new card never aliases an old one.

Placement classes (public placement geometry, featurize.tile_mask): engine-cards rules at 1831241d2
(arena.can_deploy_at, rl/action_space._is_legal_deploy, balance.py canDeployOnEnemySide):
  ground     troops and buildings: own deploy zone (+ pocket after an enemy princess falls), not on a live tower
  enemy      Miner, GoblinDrill: any non-fence tile not on a live tower
  territory  Log, BarbLog (Barbarian Barrel), RoyalDelivery (rolling / spellAsDeploy spells): own deploy zone, towers allowed
  spell      every other spell: any non-fence tile
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
VENDOR = HERE/'vendor'/'livemem'
PINS = {
    'data/cards-122.json': '289d240fc2ba09fe40cec12c6a50b08c1d145dca0fe06b0b94fbc23bc0599bec',
    'data/card-aliases.json': '3b2533b934ef225aecd678852afa488fe054ac3368264cf8846852c7affe71a7',
    'extra_bodies.json': '978b23718a96a59530ec1cb418aabcdda1b72ca4ac152f110cd12262624954cb',
    'state.py': '9085e33798b009aed7e5f40e192fb80713cf7d21aa6958b2faf9145b61c6223c',
}
ENEMY_SIDE = {'Miner', 'GoblinDrill'}
TERRITORY = {'Log', 'BarbLog', 'RoyalDelivery'}
# rfextras.SPELL_CARRIERS (deployed rfextras.py sha 513088f2...): carriers with a public in-flight aim
SPELL_CARRIERS = ('Arrows', 'Fireball', 'GoblinBarrel', 'Rocket', 'RoyalDelivery', 'Snowball')


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def check_pins():
    for rel, want in PINS.items():
        got = sha256(VENDOR/rel)
        if got != want:
            raise SystemExit(f'vendored {rel}: sha256 {got} != pinned {want}')


def build():
    check_pins()
    alias = json.loads((VENDOR/'data'/'card-aliases.json').read_text())['aliases']
    rows = json.loads((VENDOR/'data'/'cards-122.json').read_text())
    cards = []
    for r in rows:
        name = alias.get(r['name'], r['name'])
        kind = r['kind']
        place = ('enemy' if name in ENEMY_SIDE else 'territory' if name in TERRITORY else
                 'spell' if kind == 'spell' else 'ground')
        cards.append(dict(name=name, id=int(r['id']), kind=kind, cost=int(r['cost']), bodies=list(r.get('bodies') or ()),
                          place=place))
    cards.sort(key=lambda c: c['name'])
    names = [c['name'] for c in cards]
    if len(set(names)) != len(names) or len({c['id'] for c in cards}) != len(cards):
        raise SystemExit('duplicate card names / ids')
    missing = (ENEMY_SIDE | TERRITORY | set(SPELL_CARRIERS)) - set(names)
    if missing:
        raise SystemExit(f'placement / carrier names not in the pool: {sorted(missing)}')
    bodies = set(json.loads((VENDOR/'extra_bodies.json').read_text())) | {'Goblin'}
    for c in cards:
        bodies |= set(c['bodies'])
    return dict(schema='clasher.pretrain_v1.catalog.v1', sources=PINS, cards=cards, bodies=sorted(bodies),
                spell_carriers=list(SPELL_CARRIERS))


def main():
    cat = build()
    out = HERE/'catalog'/'catalog.json'
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(cat, indent=1, sort_keys=True) + '\n')
    print(f'{out}: {len(cat["cards"])} cards, {len(cat["bodies"])} bodies, sha256 {sha256(out)}')


if __name__ == '__main__':
    main()
