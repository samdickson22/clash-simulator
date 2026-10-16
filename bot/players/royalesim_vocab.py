"""RoyaleSim row -> our contract-v5 entity vocabulary (token, kind, static columns).

The translator (royalesim_translate.py) needs, for every row RoyaleSim's state_json
can show (entities, spells, projectiles), the token and kind our engine would give
the same object, plus the per-body static v5 columns our engine fills from its own
entity attributes (23 base_speed, 24 attack_range, 25 sight_range, 26
collision_radius, 30 base_damage; also 9 hp_fraction for effects) and the public
unit level. All of these are card-data lookups, i.e. public once the body is
identified (public_observation.py REAL_PLAY_ENTITY_FEATURE_INDICES note).

Built empirically and deterministically: for every C56 card, one fixed-seed demo
in our Python engine (the same demo Resources uses for templates: the card at
(4.5, 13.5) for seat 0 vs a Knight and Archers; plus a 500-tick undefended push at the left
bridge so contact and death bodies appear) and the same scripts in RoyaleSim.
- Units: RoyaleSim `unit_type` names are the game's character names, which are our
  troop/building token names (case-insensitive; checked on every C56 card).
- Spell objects: a fixed (card, motion) table, read off the paired demos (SPELLS).
- Projectiles: RoyaleSim reports only the firing card (`firer_card_id`, -1 a crown
  tower); our engine's projectile token for that card is read off its own demo.
Unmapped rows are dropped by the translator and counted (never guessed).

    bot/players/run.sh -m bot.players.royalesim_vocab   # rebuild royalesim_vocab.json (~1 min)
"""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

VOCAB_PATH = Path(__file__).with_name('royalesim_vocab.json')
KINDS = ('Troop', 'Building', 'Projectile', 'AreaEffect', 'Entity')
STATIC_COLUMNS = (9, 23, 24, 25, 26, 30)
DEMO_TICKS = 200
PUSH_TICKS = 500

# Spell-object rows: (our card, RoyaleSim SPELL_MOTIONS code) -> (our token name, our kind).
# Read off the paired demos (scratch vocab-probe.json): e.g. the Log is AIRBORNE (1) then
# ROLLING (2) in RoyaleSim and one RollingProjectile 'Log' in ours; a Balloon's death bomb
# is a FLIGHT row in RoyaleSim and a TimedExplosive (AreaEffect 'Balloon') in ours.
SPELLS = {
    ('Arrows', 0): ('Arrows', 'Projectile'),
    ('Fireball', 0): ('Fireball', 'Projectile'),
    ('Rocket', 0): ('Rocket', 'Projectile'),
    ('GoblinBarrel', 0): ('GoblinBarrel', 'Projectile'),
    ('RoyalDelivery', 0): ('RoyalDelivery', 'Projectile'),
    ('RoyalDelivery', 6): ('RoyalDelivery', 'Projectile'),
    ('Log', 1): ('Log', 'Projectile'),
    ('Log', 2): ('Log', 'Projectile'),
    ('BarbLog', 1): ('BarbLog', 'Projectile'),
    ('BarbLog', 2): ('BarbLog', 'Projectile'),
    ('Earthquake', 4): ('Earthquake', 'AreaEffect'),
    ('Poison', 4): ('Poison', 'AreaEffect'),
    ('Tornado', 4): ('Tornado', 'AreaEffect'),
    ('Lightning', 6): ('Lightning', 'AreaEffect'),
    ('Balloon', 0): ('Balloon', 'AreaEffect'),
    ('BombTower', 0): ('BombTower', 'AreaEffect'),
    ('IceGolem', 3): ('FreezeIceGolemite', 'AreaEffect'),
}
# RoyaleSim bodies with no counterpart row in our engine (dropped, counted).
NO_COUNTERPART = {'SpearGoblin_Dummy'}   # the Goblin Hut's garrison sprite; ours has none
# RoyaleSim projectile firers with no counterpart projectile in ours: Lightning's bolts (ours shows
# the strike as its AreaEffect 'Lightning' row, which the spell table maps).
NO_COUNTERPART_FIRERS = {'Lightning'}


def rsim_battle(client='15.535.29'):
    import royalesim
    overrides = royalesim.client_arms(client) if client != '16.402' else {}
    return royalesim.Battle(card_names=None, slot_of_k=[[0, 1, 2], [0, 1, 2]],
                            calibration_overrides=overrides, level=11, tower_level=11)


def _is_spell(rt, name):
    return str(getattr(rt.R.builder.loader.get_card(name), 'card_type', '') or '').lower() == 'spell'


def _ours_demo(rt, name, variant='duel'):
    """Our engine. 'duel': Resources' fixed demo (fair_player.py:85-98), the card at (4.5, 13.5)
    vs a Knight and Archers, 200 ticks. 'push': the card alone at the left bridge (3.5, 14.5), a
    spell on the enemy left princess tower, 500 ticks, so contact/death bodies appear too
    (Wallbreaker blasts, death spawns, tower shots). Rows per (token, kind)."""
    import numpy as np
    from differential import initial, Position
    builder = rt.R.builder
    demo = initial(seed=880601, cards=(name, 'Knight', 'Archers', 'Fireball'))
    while demo.tick < 100:
        demo.step()
    demo.players[0].elixir = demo.players[1].elixir = 10.
    if variant == 'duel':
        demo.deploy_card(0, name, Position(4.5, 13.5))
        demo.deploy_card(1, 'Knight', Position(4.5, 18.5))
        demo.deploy_card(1, 'Archers', Position(7.5, 20.5))
    else:
        demo.deploy_card(0, name, Position(3.5, 25.5) if _is_spell(rt, name) else Position(3.5, 14.5))
    rows, projectiles, champions = [], Counter(), Counter()
    for t in range(DEMO_TICKS if variant == 'duel' else PUSH_TICKS):
        if variant == 'push' and t == 300:
            # end the push: own units die now, so death spawns and death bombs show up as well
            for e in list(demo.entities.values()):
                if e.player_id == 0 and e.is_alive and getattr(e.card_stats, 'name', '') not in ('KingTower', 'Tower'):
                    e.hitpoints = 0
        for seat in (0, 1):
            obs = builder.build_actor(demo, seat)
            for i in np.flatnonzero(obs.entity_mask):
                row = obs.entity_features[i]
                # motion in the canonical frame, sign-normalised to the owner's forward (+y)
                sign = 1. if row[2] > .5 else -1.
                rows.append((int(obs.entity_ids[i]), int(np.argmax(row[4:9])), int(obs.entity_levels[i]),
                             tuple(round(float(row[c]), 6) for c in STATIC_COLUMNS),
                             (round(sign*float(row[27]), 3), round(sign*float(row[28]), 3))))
        for e in demo.entities.values():
            if not e.is_alive:
                continue
            token, row = builder._entity_row(e, 0)
            stats = getattr(e.card_stats, 'name', '')
            if int(np.argmax(row[4:9])) == 2 and stats:
                projectiles[(int(e.player_id), stats, int(token))] += 1
        found = demo._champion_ability_mechanic(0)
        if found is not None:
            champions[builder.token_names[builder._entity_row(found[0], 0)[0]]] += 1
        demo.step()
    return rows, projectiles, champions


def _rsim_demo(name, client, variant='duel', spell=False):
    """RoyaleSim: the same script. Counter of shown rows (entity names, spell rows, firers)."""
    import royalesim as rs
    from .royalesim_adapter import royalesim_card, our_card
    b = rsim_battle(client)
    cat = json.loads(b.catalogue_json())
    ids = {r[0]: i for i, r in enumerate(cat)}
    types = json.loads(b.unit_types_json())
    F = {f: i for i, f in enumerate(rs.ENTITY_FIELDS)}
    SUB = rs.SUBTILE_PER_MILLITILE
    filler = [n for n in ('Knight', 'Archers', 'Fireball', 'Giant', 'Musketeer', 'Skeletons', 'Arrows', 'Log', 'Zap')
              if n != name]
    decks = [[name] + filler[:7], ['Knight', 'Archers', 'Fireball', 'Giant', 'Musketeer', 'Skeletons', 'Arrows', 'Log']]
    b.reset(seed=1, decks=[[ids[royalesim_card(n)] for n in d] for d in decks], shuffle=0, start_tick=0,
            elixir_milli=[10000, 10000], tower_hp=None, spawns=[])
    b.step([], 100)
    if variant == 'duel':
        b.step([(0, 0, 4500*SUB, 13500*SUB), (1, 0, 4500*SUB, 18500*SUB)], 0)
        b.step([], 1)
        b.step([(1, 1, 7500*SUB, 20500*SUB)], 0)
    else:
        b.step([(0, 0, 3500*SUB, (25500 if spell else 14500)*SUB)], 0)
    seen = Counter()
    for _ in range(DEMO_TICKS if variant == 'duel' else PUSH_TICKS):
        s = json.loads(b.state_json())
        for e in s['entities']:
            seen[('unit', types[e[F['unit_type']]], e[F['kind']])] += 1
        for sp in s['spells']:
            seen[('spell', our_card(cat[sp[1]][0]), sp[2])] += 1
        for p in s['projectiles']:
            seen[('projectile', our_card(cat[p[7]][0]) if p[7] >= 0 else p[7])] += 1
        b.step([], 1)
    return seen


def build(rt, client='15.535.29'):
    import royalesim as rs
    from c56_controller import CARDS
    builder = rt.R.builder
    names = builder.token_names
    static = defaultdict(Counter)
    levels = defaultdict(Counter)
    moving = defaultdict(Counter)
    by_name = {}
    projectile_rows = {}
    tower_projectiles = Counter()
    champions = Counter()
    rsim_seen = {}
    for card in CARDS:
        projectile_rows[card], rsim_seen[card] = Counter(), Counter()
        for variant in ('duel', 'push'):
            rows, projectiles, champ = _ours_demo(rt, card, variant)
            for token, kind, level, cols, moves in rows:
                static[(token, kind)][cols] += 1
                levels[(token, kind)][level] += 1
                moving[(token, kind)]['none' if moves == (0., 0.) else 'forward' if moves == (0., 1.) else 'dynamic'] += 1
                by_name.setdefault((names[token], kind), token)
            projectile_rows[card].update(projectiles)
            for (seat, stats, token), n in projectiles.items():
                if stats in ('KingTower', 'Tower'):
                    tower_projectiles[(stats, token)] += n
            champions.update(champ)
            rsim_seen[card].update(_rsim_demo(card, client, variant, _is_spell(rt, card)))

    def token_of(name, kind):
        token = by_name.get((name, KINDS.index(kind)))
        if token is None:
            ns = {'Troop': 'troop_body', 'Building': 'building_body', 'Projectile': 'projectile',
                  'AreaEffect': 'area_effect'}[kind]
            token = builder.token_id(name, namespace=ns)
        return int(token) if token and token > 1 else None

    lower = {n.lower(): n for n in names if not n.startswith('<')}
    units, unresolved = {}, []
    for card, seen in rsim_seen.items():
        for key in seen:
            if key[0] != 'unit' or key[2] in (2, 3) or key[1] in units or key[1] in NO_COUNTERPART:
                continue
            kind = 'Troop' if key[2] == 0 else 'Building'
            token = token_of(lower.get(key[1].lower(), key[1]), kind)
            if token is None:
                unresolved.append(key[1])
            else:
                units[key[1]] = [token, KINDS.index(kind)]
    towers = {}
    for kind, tname in ((2, 'KingTower'), (3, 'Tower')):
        towers[str(kind)] = [int(builder.token_id(tname, namespace='tower')), KINDS.index('Building')]
    spells = {}
    for (card, motion), (tname, kind) in SPELLS.items():
        token = token_of(tname, kind)
        if token is None:
            raise ValueError(f'spell row {card}/{motion}: no token {tname}/{kind}')
        spells[f'{card}/{motion}'] = [token, KINDS.index(kind)]
    projectiles = {}
    for card, rows in projectile_rows.items():
        own = Counter()
        for (seat, stats, token), n in rows.items():
            if seat == 0 and stats not in ('KingTower', 'Tower'):
                own[(stats, token)] += n
        if not own:
            continue
        named = [(n, st, t) for (st, t), n in own.items() if st == card]
        pick = max(named) if named else max((n, st, t) for (st, t), n in own.items())
        projectiles[card] = pick[2]
    for stats, key in (('KingTower', 'king'), ('Tower', 'princess')):
        options = [(n, t) for (s, t), n in tower_projectiles.items() if s == stats]
        if options:
            projectiles[key] = max(options)[1]
        else:   # the king never fires in the demos: the alias Resources registers for tower shots
            projectiles[key] = int(builder.token_id(stats, namespace='projectile'))
    seen_keys = {k for seen in rsim_seen.values() for k in seen}
    unresolved_projectiles = sorted({str(k[1]) for k in seen_keys if k[0] == 'projectile' and k[1] != -1
                                     and k[1] not in projectiles and k[1] not in NO_COUNTERPART_FIRERS})
    unresolved_spells = sorted({f'{k[1]}/{k[2]}' for k in seen_keys if k[0] == 'spell'} - set(spells))
    statics = {}
    for (token, kind), counts in static.items():
        cols = counts.most_common(1)[0][0]
        statics[f'{token}/{kind}'] = dict(cols=dict(zip(map(str, STATIC_COLUMNS), cols)),
                                          level=levels[(token, kind)].most_common(1)[0][0],
                                          motion=_motion_mode(moving[(token, kind)]),
                                          motion_counts=dict(moving[(token, kind)]),
                                          name=names[token], kind=KINDS[kind])
    champion_units = sorted({u for u in units if u.lower() in {c.lower() for c in champions}})
    probe = rsim_battle(client)
    templates = {(int(t), KINDS.index(k)) for (t, k) in rt.R.templates}
    mapped = [tuple(v) for v in [*units.values(), *towers.values(), *spells.values()]]
    mapped += [(t, 2) for t in projectiles.values()]
    no_template = sorted({f'{names[t]}/{KINDS[k]}' for t, k in mapped if (t, k) not in templates})
    no_static = sorted({f'{names[t]}/{KINDS[k]}' for t, k in mapped if f'{t}/{k}' not in statics})
    return dict(
        meta=dict(royalesim=__import__('importlib.metadata').metadata.version('royalesim'), client=client,
                  unit_types_digest=probe.unit_types_digest(),
                  token_sha256=hashlib.sha256('\n'.join(names).encode()).hexdigest(),
                  cards=list(CARDS), demo_ticks=DEMO_TICKS, push_ticks=PUSH_TICKS),
        units=units, towers=towers, spells=spells, projectiles=projectiles, statics=statics,
        no_counterpart_units=sorted(NO_COUNTERPART), no_counterpart_firers=sorted(NO_COUNTERPART_FIRERS),
        champion_units=champion_units, unresolved_units=sorted(set(unresolved)),
        unresolved_projectiles=unresolved_projectiles, unresolved_spells=unresolved_spells,
        no_template=no_template, no_static=no_static,
        rsim_rows={card: sorted([list(k) + [n] for k, n in seen.items()], key=str) for card, seen in rsim_seen.items()})


def _motion_mode(counts):
    """How our engine fills v5 motion (27, 28) for a body: 'none' (always 0), 'forward' (always
    the owner's forward, e.g. spells and shots) or 'dynamic' (the unit's facing). A body seen with
    facing that sometimes equals forward is dynamic (a walking troop faces forward most of the time)."""
    if counts['dynamic']:
        return 'dynamic'
    if counts['forward'] and counts['none']:
        return 'dynamic'
    return 'forward' if counts['forward'] else 'none'


def load(rt, *, path=VOCAB_PATH):
    """Cached vocabulary; refuses a file built on another token list or unit-type table."""
    vocab = json.loads(Path(path).read_text())
    names = rt.R.builder.token_names
    if vocab['meta']['token_sha256'] != hashlib.sha256('\n'.join(names).encode()).hexdigest():
        raise ValueError('royalesim_vocab.json was built for another token vocabulary: rebuild it')
    if vocab['meta']['unit_types_digest'] != rsim_battle(vocab['meta']['client']).unit_types_digest():
        raise ValueError('royalesim_vocab.json was built for another RoyaleSim unit-type table: rebuild it')
    from .royalesim_translate import complete_vocab
    return complete_vocab(rt, vocab)


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--client', default='15.535.29')
    ap.add_argument('--out', type=Path, default=VOCAB_PATH)
    a = ap.parse_args()
    from .runtime import Runtime
    vocab = build(Runtime(), a.client)
    a.out.write_text(json.dumps(vocab, indent=1, sort_keys=True) + '\n')
    print(json.dumps({k: vocab[k] for k in ('units', 'towers', 'spells', 'projectiles', 'champion_units',
                                            'unresolved_units', 'unresolved_projectiles', 'unresolved_spells',
                                            'no_template', 'no_static')}, indent=1))


if __name__ == '__main__':
    main()
