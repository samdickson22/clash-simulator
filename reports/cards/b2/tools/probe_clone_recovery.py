"""Exact review-r2 Clone water/building recovery regression, both seats.

Inject an already-active slide at the reviewed legal point, then run ten normal
battle ticks. Assert legal ground and building clearance in each engine, and slide
completion. This focused state fixture complements public Clone casting scenarios.
Usage: probe_clone_recovery.py OUT.json (same environment as probe_dash_full.py).
"""
import json
import sys
import traceback
from differential import config, initial, snapshot, battle_digest, clasher_core, Position
from clasher.entities import Building
from clasher.native_tilemap import native_spawn_tile_blocked
from clasher.kinematics import tiles_to_logic_units

CARDS = ('Clone', 'Knight', 'Cannon', 'Giant', 'Archers')


def legal(x, y, radius, buildings):
    xu, yu = tiles_to_logic_units(x), tiles_to_logic_units(y)
    assert 0 <= xu < 18000 and 0 <= yu < 32000, (x, y, 'arena')
    assert not native_spawn_tile_blocked(xu // 500, yu // 500), (x, y, 'water')
    for bx, by, br in buildings:
        reach = tiles_to_logic_units(br) + tiles_to_logic_units(radius)
        assert (abs(xu - tiles_to_logic_units(bx)) >= reach or
                abs(yu - tiles_to_logic_units(by)) >= reach), (x, y, bx, by, 'building')


def one(seat):
    mirror = (lambda p: p) if seat == 0 else (lambda p: (18 - p[0], 32 - p[1]))
    cfg = config(CARDS)
    b = initial(7, cards=CARDS)
    p = b.players[seat]
    p.hand = ['Knight', 'Cannon', 'Clone', 'Giant']
    p.cycle_queue.clear(); p.cycle_queue.extend(['Archers'])
    p.elixir = 10.0
    assert b.deploy_card(seat, 'Knight', Position(*mirror((7.5, 10.5))))
    assert b.deploy_card(seat, 'Cannon', Position(*mirror((4.5, 10.5))))
    for _ in range(25):
        b.step()
    knight = next(e for e in b.entities.values() if e.player_id == seat and e.card_stats.name == 'Knight')
    cannon = next(e for e in b.entities.values() if e.player_id == seat and e.card_stats.name == 'Cannon')
    cannon.position = Position(*mirror((8.0, 14.0)))
    knight.position = Position(*mirror((9.15, 14.95)))
    knight._clone_slide = [0, 125 if seat == 0 else -125, 10]
    knight._native_ground_route_cells = []
    knight._ground_path_cache_key = None
    buildings = [(e.position.x, e.position.y, e.get_collision_radius()) for e in b.entities.values()
                 if e.is_alive and isinstance(e, Building)]
    legal(knight.position.x, knight.position.y, knight.get_collision_radius(), buildings)
    native = clasher_core.BattleState(snapshot(b, cfg))
    positions = []
    for tick in range(10):
        b.step(); native.step(1)
        rows = {r['id']: r for r in json.loads(native.snapshot())['entities']}
        row = rows[knight.id]
        legal(knight.position.x, knight.position.y, knight.get_collision_radius(), buildings)
        legal(row['x'], row['y'], row['stats']['radius'], buildings)
        assert native.digest() == battle_digest(b), f'digest at {tick}'
        assert (knight.position.x, knight.position.y) == (row['x'], row['y']), f'position at {tick}'
        if tick == 0 and seat == 0:
            assert (round(row['x'], 3), round(row['y'], 3)) == (9.15, 14.95), 'failed old legal point fallback'
        positions.append([row['x'], row['y']])
    assert knight._clone_slide is None and not row.get('clone_slide'), 'slide did not finish'
    return dict(case='water_building_recovery', seat=seat, ticks=10, positions=positions, ok=True)


if __name__ == '__main__':
    rows = []
    for seat in (0, 1):
        try:
            result = one(seat)
        except Exception:
            result = dict(case='water_building_recovery', seat=seat, ok=False,
                          error=traceback.format_exc(limit=5))
        rows.append(result)
        print(json.dumps(result), flush=True)
    with open(sys.argv[1], 'w') as out:
        json.dump(rows, out, indent=1)
    sys.exit(0 if all(r['ok'] for r in rows) else 1)
