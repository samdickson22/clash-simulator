"""Standalone exact-binary placement contract: Cannon64 + static river/card matrix960.

Owner only after fresh review. No Runtime, policies, hidden-state oracle or workers.
The exclusive receipt retains partial evidence on failure; contradictions exit nonzero.
"""
from __future__ import annotations

import argparse
import hashlib
from importlib import metadata, util
import json
from pathlib import Path

from .placement import VERSION, ARENA_SHA256, CARDS_SHA256, card_kind, static_rules

PINS = dict(binary_sha256='97e03055332faeb986c91a12aa64c6e22ca65948b68351803d914e0a84eb43bb',
            calibration_sha256='4c7c3d95a2ee078da103b9570e9a65debbbe90480352ae00a5f0ac6b6f883ebf',
            arena_sha256=ARENA_SHA256, cards_sha256=CARDS_SHA256)
FAILED = ((15, 17), (9, 19), (10, 19), (14, 20), (13, 16))
CONTROLS = ((9, 10), (4, 14), (13, 14))
PATTERNS = ((False, False), (True, False), (False, True), (True, True))
DESCRIPTIVE_CARDS = ('Knight', 'Minions', 'Fireball')
DESCRIPTIVE_TILES = ((13, 16), (14, 16), (9, 10))
MATRIX_CARDS = ('Knight', 'Minions', 'Cannon', 'Miner', 'GoblinDrill', 'GoblinBarrel', 'Log', 'Fireball')
MATRIX_TILES = tuple((x, y) for y in (15, 16) for x in (2, 3, 4, 13, 14, 15)) + ((9, 16), (9, 10), (3, 20))
# Rust catalogue codes are independently exposed by the installed binary. Heal can
# carry troop territory as a spell (code0); SpellAsDeploy rolling cards carry code3.
KIND_CODES = dict(troop=(0,), ordinary=(1,), unrestricted=(2,), rolling=(0, 3),
                  water_spell=(4,), tunnel=(5,), mirror=(6,))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def installed_identity():
    import royalesim as rs
    data = Path(rs.data_dir())
    binary = Path(util.find_spec('royalesim.royalesim').origin)
    return dict(version=metadata.version('royalesim'), client='16.402', binary_path=str(binary), data_path=str(data.resolve()),
                binary_sha256=sha(binary), calibration_sha256=sha(data/'calibration.json'),
                arena_sha256=sha(data/'derived/arena.json'), cards_sha256=sha(data/'derived/cards.json'),
                placement_source_sha256=sha(Path(__file__).with_name('placement.py')), probe_source_sha256=sha(__file__))


def validate_identity(identity):
    if identity.get('version') != '0.1.34' or identity.get('client') != '16.402':
        raise ValueError(f'wrong installed simulator version/client: {identity}')
    for key, expected in PINS.items():
        if identity.get(key) != expected:
            raise ValueError(f'exact installed simulator pin mismatch: {key}')


def expected_verdict(card, xy, down):
    """Independent small analytical fixture table; not the adapter's grid predicate.

    Tile centres strictly inside either two-tile bridge are x3.5/14.5.
    Their edges touch WATER. Ordinary buildings never enter either river row;
    troops/Log enter an interior only after that public lane's princess falls.
    """
    x, y = xy
    if card == 'Fireball' or xy == (9, 10):
        return 'OK'
    if y in (15, 16) and x not in (3, 14):
        return 'WATER'
    if card == 'Cannon':
        return 'OUT_OF_TERRITORY'
    if card in ('Miner', 'GoblinDrill', 'GoblinBarrel'):
        return 'OK'
    return 'OK' if down[0 if x < 9 else 1] else 'OUT_OF_TERRITORY'


def cannon_fits_inward(row):
    if tuple(row['own_tile']) not in CONTROLS or row['own_tile'][1] != 14:
        return True
    centre = row.get('resolved_own_tiles')
    return (row.get('relocated') is True and centre == [row['own_tile'][0]+.5, 13.5]
            and centre[1]+1.5 <= 15)  # Whole3x3 box clears the river, in the acting seat's frame.


def validate_receipt(receipt, identity):
    validate_identity(identity)
    if receipt.get('protocol') != VERSION or receipt.get('identity') != identity or receipt.get('passed') is not True:
        raise ValueError('placement microprobe receipt is failed, stale or from different source/binary/data')
    expected = {(s, tuple(p), xy) for s in (0, 1) for p in PATTERNS for xy in FAILED + CONTROLS}
    rows = receipt.get('rows', [])
    keys = [(r['seat'], tuple(r['enemy_down']), tuple(r['own_tile'])) for r in rows]
    if len(keys) != 64 or set(keys) != expected or any(r.get('passed') is not True for r in rows):
        raise ValueError('placement microprobe lacks the complete passing Cannon64 fixture set')
    for row in rows:
        xy = tuple(row['own_tile'])
        reason = 'OK' if xy in CONTROLS else ('WATER' if xy == (13, 16) else 'OUT_OF_TERRITORY')
        if row.get('reason') != reason or row.get('accepted') is not (reason == 'OK') or not cannon_fits_inward(row):
            raise ValueError(f'Cannon verdict/inward3x3 footprint contradicts contract: {row}')
    matrix = receipt.get('river_matrix', [])
    expected = {(s, tuple(p), c, xy) for s in (0, 1) for p in PATTERNS for c in MATRIX_CARDS for xy in MATRIX_TILES}
    keys = [(r['seat'], tuple(r['enemy_down']), r['card'], tuple(r['own_tile'])) for r in matrix]
    if len(keys) != 960 or set(keys) != expected:
        raise ValueError('placement microprobe lacks complete960 river/card/seat/public-tower fixtures')
    for row in matrix:
        reason = expected_verdict(row['card'], tuple(row['own_tile']), row['enemy_down'])
        if row.get('reason') != reason or row.get('accepted') is not (reason == 'OK') or row.get('passed') is not True:
            raise ValueError(f'river/card classification or orientation contradicts contract: {row}')
    classifications = receipt.get('classifications', [])
    names = [r['card'] for r in classifications]
    _, static_cards = static_rules()
    if (len(names) != 145 or len(names) != len(set(names)) or set(names) != set(static_cards)
            or any(r.get('passed') is not True or r.get('kind') != card_kind(static_cards[r['card']], static_cards)
                   or r.get('placement') not in KIND_CODES.get(r.get('kind'), ())
                   for r in classifications)):
        raise ValueError('incomplete145 native catalogue or disagreement with static card classes')
    descriptive = receipt.get('nonbuilding_descriptive', [])
    keys = [(r['seat'], r['card'], tuple(r['own_tile'])) for r in descriptive]
    if len(keys) != 18 or set(keys) != {(s, c, xy) for s in (0, 1) for c in DESCRIPTIVE_CARDS for xy in DESCRIPTIVE_TILES}:
        raise ValueError('microprobe lacks complete18 original nonbuilding observations')
    for row in descriptive:
        reason = expected_verdict(row['card'], tuple(row['own_tile']), (True, True))
        if row.get('reason') != reason or row.get('accepted') is not (reason == 'OK'):
            raise ValueError('descriptive observations differ from certified river matrix')


def run(receipt=None):
    import royalesim as rs
    receipt = {} if receipt is None else receipt
    receipt.update(protocol=VERSION, identity=installed_identity(), passed=False,
                   rows=[], river_matrix=[], nonbuilding_descriptive=[], classifications=[])
    validate_identity(receipt['identity'])
    _, static_cards = static_rules()
    b = rs.Battle(card_names=None, slot_of_k=[[0, 1, 2], [0, 1, 2]], level=11, tower_level=11)
    b.set_command_delay_ticks(0, 0)
    fields = {name: i for i, name in enumerate(rs.ENTITY_FIELDS)}
    catalogue = json.loads(b.catalogue_json())
    if tuple(rs.CATALOGUE_FIELDS[:8]) != ('name', 'placement', 'elixir', 'count', 'radius', 'flying', 'hitpoints', 'footprint_tiles'):
        raise ValueError(f'unexpected installed catalogue schema: {rs.CATALOGUE_FIELDS}')
    ids = {row[0]: i for i, row in enumerate(catalogue)}
    if len(catalogue) != 145 or len(ids) != 145 or set(ids) != set(static_cards):
        raise ValueError('installed native catalogue must expose all145 pinned static card names exactly once')
    for row in catalogue:
        kind = card_kind(static_cards[row[0]], static_cards)
        receipt['classifications'].append(dict(card=row[0], kind=kind, placement=row[1], flying=row[5],
                                               passed=row[1] in KIND_CODES.get(kind, ())))
    mismatches = [r for r in receipt['classifications'] if not r['passed']]
    if mismatches:
        raise ValueError(f'static classification disagrees with installed catalogue: {mismatches}')
    deck = [ids[n] for n in ('Knight', 'Archer', 'Cannon', 'Giant', 'Fireball', 'Arrows', 'Minions', 'Musketeer')]
    b.reset(seed=1, decks=[deck, deck], shuffle=0, start_tick=100, elixir_milli=[10000, 10000],
            tower_hp=None, spawns=[], levels=[[11]*8]*2, tower_levels=[11, 11])
    full = [p['tower_max_hp'] for p in json.loads(b.state_json())['players']]

    def tap(card, seat, down, xy, *, settle=False):
        current = list(deck)
        if ids[card] in current:
            index = current.index(ids[card])
            current[2], current[index] = current[index], current[2]
        else:
            current[2] = ids[card]
        if len(set(current)) != 8:
            raise ValueError(f'nonunique fixture deck for {card}')
        hp = [list(side) for side in full]
        for slot, dead in zip((1, 2) if seat == 0 else (2, 1), down):
            if dead:
                hp[1-seat][slot] = 0
        b.reset(seed=1, decks=[current, current], shuffle=0, start_tick=100, elixir_milli=[10000, 10000],
                tower_hp=hp, spawns=[], levels=[[11]*8]*2, tower_levels=[11, 11])
        before = json.loads(b.state_json())
        if (any(e[fields['kind']] not in (2, 3) for e in before['entities']) or before['tick'] != 100
                or before['players'][seat]['hand'][2] != ids[card]
                or before['players'][seat]['elixir_milli'] != 10000 or [p['tower_hp'] for p in before['players']] != hp):
            raise ValueError(f'not an empty post-lockout/full-elixir/slot2 fixture: {card}, seat{seat}, {xy}')
        x, y = xy[0]+.5, xy[1]+.5
        wx, wy = (x, y) if seat == 0 else (18-x, 32-y)
        command = [round(wx*18000), round(wy*18000)]
        results = b.step([(seat, 2, *command)], 0)
        if len(results) != 1 or len(results[0]) < 5:
            raise ValueError(f'unexpected installed command schema: {results}')
        raw = list(results[0])
        accepted, reason = raw[1] == 0, rs.DEPLOY_REASONS[raw[1]]
        resolved = raw[3:5]
        if accepted and settle:
            b.step([], 25)
            bodies = [e for e in json.loads(b.state_json())['entities'] if e[fields['kind']] not in (2, 3)
                      and e[fields['team']] == seat and e[fields['card_id']] == ids[card]]
            if len(bodies) != 1:
                raise ValueError(f'accepted {card} did not materialize uniquely: {bodies}')
            resolved = [bodies[0][fields[k]] for k in ('x', 'y')]
        world = [v/18000 for v in resolved]
        own = world if seat == 0 else [18-world[0], 32-world[1]]
        return dict(seat=seat, enemy_down=list(down), card=card, own_tile=list(xy), tap_subtiles=command,
                    reported_resolved_subtiles=raw[3:5], resolved_subtiles=resolved, resolved_world_tiles=world,
                    resolved_own_tiles=own, reason=reason, accepted=accepted, relocated=accepted and resolved != command,
                    result=raw)

    for seat in (0, 1):
        for down in PATTERNS:
            for xy in FAILED + CONTROLS:
                row = tap('Cannon', seat, down, xy, settle=True)
                reason = 'OK' if xy in CONTROLS else ('WATER' if xy == (13, 16) else 'OUT_OF_TERRITORY')
                row.update(raw_box_crosses_river=xy in CONTROLS and xy[1] == 14,
                           passed=row['reason'] == reason and cannon_fits_inward(row))
                receipt['rows'].append(row)
                print(json.dumps(dict(category='Cannon64', **row), sort_keys=True), flush=True)
            for card in MATRIX_CARDS:
                for xy in MATRIX_TILES:
                    row = tap(card, seat, down, xy)
                    row.update(expected_reason=expected_verdict(card, xy, down))
                    row['passed'] = row['reason'] == row['expected_reason']
                    receipt['river_matrix'].append(row)
                    if down == (True, True) and card in DESCRIPTIVE_CARDS and xy in DESCRIPTIVE_TILES:
                        receipt['nonbuilding_descriptive'].append(dict(row))
                    print(json.dumps(dict(category='river_matrix', **row), sort_keys=True), flush=True)
    receipt.update(passed=all(r['passed'] for r in receipt['rows']+receipt['river_matrix']),
                   fixture=dict(hand_slot=2, level=11, tower_level=11, tick=100, elixir_milli=10000,
                                command_delay_ticks=0, non_tower_bodies=0, cannon_taps=64, matrix_taps=960,
                                units='18000 integer subtiles/tile; closed half-cells; Cannon3x3 box'),
                   geometry_note='Static WATER intersection only; base public territory/occupancy remain. Native physics unchanged.')
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    with args.out.open('x') as stream:
        receipt = dict(protocol=VERSION, passed=False)
        try:
            run(receipt)
            validate_receipt(receipt, installed_identity())
        except Exception as exc:
            receipt.update(passed=False, error=repr(exc))
        stream.write(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
    print(json.dumps(dict(passed=receipt['passed'], receipt=str(args.out))), flush=True)
    return 0 if receipt['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
