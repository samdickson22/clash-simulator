"""Native-vs-Python lockstep on the fidelity scenarios (exploration probe; extends reports/cards/tools/probe_native.py).

For each card and each of its fidelity scenarios (batchA/tools/scenarios.py `script`, same tiles and command ticks),
both engines start from the same exported state (differential.initial/config/snapshot), apply the same deploys and
are compared by battle_digest every tick. Records the first mismatch tick and the deploy results.
Usage (PYTHONPATH = native : engine-rs : src : engine-speed): probe_native_scen.py OUT.json CARD ... | OUT.json --cases
"""
import json, sys, traceback
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from scenarios import script, scenarios
from differential import config, initial, snapshot, battle_digest, clasher_core, Position

FILL = ('Knight', 'Archers', 'Giant', 'Musketeer')
KIND = {}


# Extra native==Python cases from the Batch A review (Sol, 2026-10-16): (side, card, tile, command tick) scripts.
CASES = {
    # A frozen Tombstone dies: its death Skeletons inherit the Freeze before their first update.
    'frozen_tombstone_death': ([(0, 'Tombstone', (4.5, 10.5), 0), (1, 'Freeze', (4.5, 10.5), 40),
                                (1, 'Rocket', (4.5, 10.5), 41)], 400),
    'frozen_tombstone_death_red': ([(1, 'Tombstone', (13.5, 21.5), 0), (0, 'Freeze', (13.5, 21.5), 40),
                                    (0, 'Rocket', (13.5, 21.5), 41)], 400),
    # A Witch in a corner: her clamped ring of Skeletons overlaps; wave members stay apart in their first update.
    # The corner tile is not deployable, so SETUP deploys her legally in Python, steps Python alone to just
    # before her first wave (deploy end 20 + 19 ticks) and moves her into the corner; the shared snapshot is
    # exported from that state.
    'witch_corner': ([], 600),
    'witch_corner_red': ([], 600),
}
SETUP = {
    'witch_corner': (0, 'Witch', (0.5, 1.5), (0.5, 0.5), 37),
    'witch_corner_red': (1, 'Witch', (17.5, 30.5), (17.5, 31.5), 37),
}


def one(card, kind, scenario):
    seq, end = CASES[scenario] if scenario in CASES else script(dict(name=card, kind=kind), scenario)
    setup = SETUP.get(scenario)
    names = list(dict.fromkeys([n for _, n, _, _ in seq] + ([setup[1]] if setup else []) + list(FILL)))
    out = dict(card=card, scenario=scenario, ticks=end)
    try:
        cards = tuple(names[:8])
        cfg = config(cards)
        b = initial(7, cards=cards)
        for p in b.players:
            p.elixir = 10.0
            p.hand = [n for _, n, _, _ in seq if True][:0] or list(cards[:4])
        # Put every scripted card in its side's hand (4 slots suffice for every script).
        for side in (0, 1):
            mine = list(dict.fromkeys(n for s, n, _, _ in seq if s == side))
            p = b.players[side]
            p.hand = (mine + [c for c in cards if c not in mine])[:4]
            p.cycle_queue.clear(); p.cycle_queue.extend(c for c in cards if c not in p.hand)
        if setup:
            side, name, tile, corner, pre = setup
            b.players[side].hand[0] = name
            old_ids = set(b.entities)
            assert b.deploy_card(side, name, Position(*tile))
            for _ in range(pre):
                b.step()
            for k in set(b.entities) - old_ids:
                b.entities[k].position = Position(*corner)
            out['setup'] = [side, name, tile, corner, pre]
        native = clasher_core.BattleState(snapshot(b, cfg))
        out['deploys'], out['first_mismatch'] = [], None
        bytick = {}
        for s, n, tile, t in seq:
            bytick.setdefault(t, []).append((s, n, tile))
        for t in range(end):
            for s, n, (x, y) in bytick.get(t, []):
                pa = bool(b.deploy_card(s, n, Position(x, y)))
                ra = bool(native.apply_action(s, n, x, y))
                out['deploys'].append([t, s, n, pa, ra])
                if pa != ra and out['first_mismatch'] is None:
                    out['first_mismatch'] = f'deploy@{t}'
            b.step(); native.step(1)
            if out['first_mismatch'] is None and native.digest() != battle_digest(b):
                out['first_mismatch'] = t
                break
        out['native'] = 'ok'
        out['final_digest'] = str(battle_digest(b))
    except BaseException as e:
        out['native'] = 'error'
        out['error'] = (type(e).__name__ + ': ' + traceback.format_exc(limit=5))[-900:]
    return out


if __name__ == '__main__':
    pool = {c['name']: c['kind'] for c in json.load(open(Path(__file__).resolve().parent / 'pool.json'))}
    res = []
    if sys.argv[2:3] == ['--cases']:
        for name in CASES:
            r = one(name, 'case', name); res.append(r)
            print(name, r.get('native'), r.get('first_mismatch'), r.get('deploys'),
                  (r.get('error') or '').strip().splitlines()[-1:], flush=True)
        json.dump(res, open(sys.argv[1], 'w'), indent=1)
        sys.exit(0)
    for card in sys.argv[2:]:
        for sc in scenarios(dict(name=card, kind=pool[card])):
            r = one(card, pool[card], sc); res.append(r)
            print(card, sc, r.get('native'), r.get('first_mismatch'), [d for d in r.get('deploys', []) if not d[3] or not d[4]],
                  (r.get('error') or '').strip().splitlines()[-1:], flush=True)
    json.dump(res, open(sys.argv[1], 'w'), indent=1)
