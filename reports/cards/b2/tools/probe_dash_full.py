"""Batch B2 review r2: FULL-STATE native==Python for every effect source that meets a Bandit in dash travel.

Same driver as probe_dash_paths.py (offset sweep L between the cast/deploy and a forced dash launch, both seats), but
every tick compares the whole Python live export (live_snapshot.live_entity for every entity: hit sets, strike and
chain state, shot targets, buffs, slows, stun, scope state, ...) against native.snapshot(), plus players and next_id.
The complete root export is canonicalized through serde without stepping and compared in both directions;
`hit_ids` compare as sorted lists. Narrow representation exclusions are recorded with each mismatch.
Successful actions are required. Guard queries, rather than cast-window proximity, measure actual source contact.
Usage (PYTHONPATH = native : engine-rs : src : engine-speed): probe_dash_full.py OUT.json [CASE ...]
"""

import json, sys, traceback
from differential import config, initial, snapshot, battle_digest, clasher_core, Position, entity

P = (9.0, 10.5)  # the Bandit's point (blue seat)
FILL = ('Knight', 'Giant', 'Archers', 'Musketeer')
LEADS = list(range(-4, 36))
END = 45
ENEMY, OWN = 'enemy', 'own'
CASES = {
    'zap': ('Zap', ENEMY, P), 'fireball': ('Fireball', ENEMY, P), 'arrows': ('Arrows', ENEMY, P),
    'rocket': ('Rocket', ENEMY, P), 'lightning': ('Lightning', ENEMY, P), 'log': ('Log', ENEMY, (9.0, 18.5)),
    'barblog': ('BarbLog', ENEMY, (9.0, 18.5)), 'snowball': ('Snowball', ENEMY, P),
    'earthquake': ('Earthquake', ENEMY, P), 'poison': ('Poison', ENEMY, P), 'freeze': ('Freeze', ENEMY, P),
    'tornado': ('Tornado', ENEMY, P), 'goblin_curse': ('GoblinCurse', ENEMY, P), 'vines': ('Vines', ENEMY, P),
    'void': ('DarkMagic', ENEMY, P), 'electro_spirit': ('ElectroSpirit', ENEMY, (9.0, 17.5)),
    'ice_spirit': ('IceSpirit', ENEMY, (9.0, 17.5)),
    'rage': ('Rage', OWN, P), 'heal': ('Heal', OWN, P), 'clone': ('Clone', OWN, P),
}
B = (9.0, 17.5)  # enemy troops stand here; the dash toward the enemy King passes them
for _name, _card in (('bowler', 'Bowler'), ('magic_archer', 'MagicArcher'), ('executioner', 'Executioner'),
                     ('mega_knight', 'MegaKnight'), ('electro_dragon', 'ElectroDragon'), ('ice_wizard', 'IceWizard'),
                     ('electro_wizard', 'ElectroWizard'), ('fire_spirits', 'FireSpirits'), ('hunter', 'Hunter'),
                     ('valkyrie', 'Valkyrie'), ('princess', 'Princess')):
    CASES[_name] = (_card, ENEMY, B)
# This probe canonicalizes the complete Python export through Rust's serde schema WITHOUT stepping it.
# BattleState.__new__ only deserializes and validates dimensions/RNG, so this supplies exact serialized defaults
# without borrowing native mechanics to calculate expected state. Live native-only optional state is compared too.
# Config is immutable input, omitted from the equality walk (but still supplied for deserialization).
UNSET_TICKS = {'finish_tick', 'landed_tick', 'push_tick'}
TOWER_ARROW_FIELDS = {'age', 'attacked_current', 'lane', 'last_target', 'started'}


def norm(value):
    if isinstance(value, float):
        return round(value, 6)
    return value


def differences(expected, actual, path='state'):
    """Compare both directions, including native-only fields and nested list items."""
    if isinstance(expected, dict) and isinstance(actual, dict):
        for key in sorted(set(expected) | set(actual)):
            if key not in expected or key not in actual:
                yield dict(field=f'{path}.{key}', python=expected.get(key), native=actual.get(key))
            else:
                yield from differences(expected[key], actual[key], f'{path}.{key}')
        return
    if isinstance(expected, list) and isinstance(actual, list):
        if path.endswith('.hit_ids'):
            if sorted(expected) != sorted(actual):
                yield dict(field=path, python=expected, native=actual)
            return
        if len(expected) != len(actual):
            yield dict(field=path, python=expected, native=actual)
            return
        for index, (left, right) in enumerate(zip(expected, actual)):
            yield from differences(left, right, f'{path}[{index}]')
        return
    if norm(expected) != norm(actual):
        yield dict(field=path, python=expected, native=actual)


def full_compare(battle, native, cfg):
    # No stepping of the expected state: the constructor is a serde round-trip only (lib.rs:BattleState::new).
    expected = json.loads(clasher_core.BattleState(snapshot(battle, cfg)).snapshot())
    actual = json.loads(native.snapshot())
    py_entities = {str(row['id']): row for row in expected.pop('entities') if row.get('alive', True)}
    rs_entities = {str(row['id']): row for row in actual.pop('entities') if row.get('alive', True)}
    expected.pop('config'); actual.pop('config')
    ignored = []
    for eid in py_entities.keys() & rs_entities.keys():
        left, right = py_entities[eid], rs_entities[eid]
        entity = battle.entities[int(eid)]
        keys = set()
        # Only the unrecorded birth value is synthesized by Python; real object birth fields remain compared.
        if getattr(entity, '_native_object_birth_tick', None) is None:
            keys.add('birth')
        if left['class'] == 'Troop':
            # Established export/cache differences; this remains an explicit limit of the comparator.
            keys.update(('cooldown', 'route_occupied'))
        tower_arrow = left['class'] == 'Projectile' and left.get('stats', {}).get('name') == 'Tower'
        if tower_arrow:
            keys.update(TOWER_ARROW_FIELDS)
            for key in ('max_hp', 'sight'):
                left['stats'].pop(key, None); right['stats'].pop(key, None)
                ignored.append(f'entities.{eid}.stats.{key}')
        for key in keys:
            left.pop(key, None); right.pop(key, None)
            ignored.append(f'entities.{eid}.{key}')
        for key in UNSET_TICKS:
            if left.get(key) in (-1, 0) and right.get(key) in (-1, 0):
                left[key] = right[key] = 0
    expected['entities'], actual['entities'] = py_entities, rs_entities
    out = []
    for delta in differences(expected, actual):
        parts = delta['field'].split('.')
        if len(parts) > 2 and parts[1] == 'entities':
            row = py_entities.get(parts[2], rs_entities.get(parts[2], {}))
            delta.update(entity_class=row.get('class'), spell_name=row.get('spell_name'),
                         stats_name=row.get('stats', {}).get('name'))
        out.append(delta)
    return out, ignored


def source_key(name):
    return str(name or '').replace('_', '').lower()


def observe_effect_queries(bandit, card, events):
    """Observe real Python guard queries on this recipient; preserve each method's return value."""
    for method in ('can_receive_area_damage', 'can_receive_effect'):
        original = getattr(bandit, method)
        def observed(*args, _method=method, _original=original, **kwargs):
            result = _original(*args, **kwargs)
            if getattr(bandit, '_bandit_dashing', False):
                source = args[0] if args else kwargs.get('source_kind')
                item = dict(method=_method, source=source, allowed=bool(result))
                if source_key(source) == source_key(card):
                    events.append(item)
            return result
        setattr(bandit, method, observed)


def mirror(t, seat):
    return t if seat == 0 else (18 - t[0], 32 - t[1])


def one(card, side_kind, tile, lead, seat, cfg, cards):
    bs = seat                      # the Bandit's side
    cs = bs if side_kind == OWN else 1 - bs
    b = initial(7, cards=cards)
    for s in (0, 1):
        want = ['Bandit'] if s == bs else []
        if s == cs:
            want.append(card)
        p = b.players[s]
        p.elixir = 10.0
        p.hand = (want + [c for c in cards if c not in want])[:4]
        p.cycle_queue.clear(); p.cycle_queue.extend(c for c in cards if c not in p.hand)
    assert b.deploy_card(bs, 'Bandit', Position(*mirror(P, seat)))
    for _ in range(25):
        b.step()
    for p in b.players:
        p.elixir = 10.0
    bandit = next(e for e in b.entities.values() if e.player_id == bs and e.is_alive
                  and any(type(m).__name__ == 'BanditDash' for m in getattr(e, 'mechanics', [])))
    king = next(e for e in b.entities.values() if e.player_id == 1 - bs and getattr(e, '_crown_tower_slot', None) == 'king')
    dash = next(m for m in bandit.mechanics if type(m).__name__ == 'BanditDash')
    q = mirror(tile, seat)
    out = dict(lead=lead, first=None, field=None, cast=None, gate_queries=[], differences=[])
    observe_effect_queries(bandit, card, out['gate_queries'])
    if card == 'Heal':
        bandit.hitpoints = min(bandit.hitpoints, bandit.max_hitpoints / 2)
    def cast(native=None):
        pa = bool(b.deploy_card(cs, card, Position(*q)))
        ra = None if native is None else bool(native.apply_action(cs, card, *q))
        out['cast'] = dict(python=pa, native=ra, before_export=native is None)
        if not pa or (native is not None and not ra):
            raise AssertionError(f'required cast rejected: {card} side={cs} tile={q}: {out["cast"]}')
    if lead > 0:
        bandit.position = Position(*mirror(P, seat))
        cast()
        for _ in range(lead):
            b.step()
    bandit.position = Position(*mirror(P, seat))
    bandit._bandit_charging = False
    dash._launch_dash(bandit, king)
    native = clasher_core.BattleState(snapshot(b, cfg))
    bid = bandit.id
    for t in range(END):
        if lead <= 0 and t == -lead:
            cast(native)
        b.step(); native.step(1)
        delta, ignored = full_compare(b, native, cfg)
        digest_equal = native.digest() == battle_digest(b)
        if delta or not digest_equal:
            out.update(first=t, field=delta[0]['field'] if delta else 'digest',
                       differences=delta, digest_equal=digest_equal, ignored_fields=ignored)
            break
    if out['cast'] is None:
        raise AssertionError('required cast was never attempted')
    return out


if __name__ == '__main__':
    names = sys.argv[2:] or list(CASES)
    res = []
    for n in names:
        card, kind, tile = CASES[n]
        cards = tuple(dict.fromkeys(('Bandit', card) + FILL))[:8]
        cfg = config(cards)
        for seat in (0, 1):
            rows = []
            for lead in LEADS:
                try:
                    rows.append(one(card, kind, tile, lead, seat, cfg, cards))
                except Exception:
                    rows.append(dict(lead=lead, error=traceback.format_exc(limit=4)[-600:]))
            bad = [r for r in rows if r.get('first') is not None or 'error' in r]
            rec = dict(case=n, seat=('blue', 'red')[seat], runs=len(rows), mismatches=len(bad),
                       cast_successes=sum(1 for r in rows if r.get('cast', {}).get('python') is True and
                                          (r['cast']['before_export'] or r['cast']['native'] is True)),
                       queried_runs=sum(bool(r.get('gate_queries')) for r in rows),
                       query_count=sum(len(r.get('gate_queries', [])) for r in rows),
                       first_bad=bad[0] if bad else None, rows=rows)
            res.append(rec)
            print(json.dumps({k: v for k, v in rec.items() if k != 'rows'}), flush=True)
    json.dump(res, open(sys.argv[1], 'w'), indent=1)
