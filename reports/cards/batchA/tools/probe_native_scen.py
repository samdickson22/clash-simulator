"""Native-vs-Python lockstep on the fidelity scenarios (exploration probe; extends reports/cards/tools/probe_native.py).

For each card and each of its fidelity scenarios (batchA/tools/scenarios.py `script`, same tiles and command ticks),
both engines start from the same exported state (differential.initial/config/snapshot), apply the same deploys and
are compared by battle_digest every tick. Records the first mismatch tick and the deploy results.
Usage (PYTHONPATH = native : engine-rs : src : engine-speed): probe_native_scen.py OUT.json CARD ...
"""
import json, sys, traceback
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from scenarios import script, scenarios
from differential import config, initial, snapshot, battle_digest, clasher_core, Position

FILL = ('Knight', 'Archers', 'Giant', 'Musketeer')
KIND = {}


def one(card, kind, scenario):
    seq, end = script(dict(name=card, kind=kind), scenario)
    names = list(dict.fromkeys([n for _, n, _, _ in seq] + list(FILL)))
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
    except BaseException as e:
        out['native'] = 'error'
        out['error'] = (type(e).__name__ + ': ' + traceback.format_exc(limit=5))[-900:]
    return out


if __name__ == '__main__':
    pool = {c['name']: c['kind'] for c in json.load(open(Path(__file__).resolve().parent / 'pool.json'))}
    res = []
    for card in sys.argv[2:]:
        for sc in scenarios(dict(name=card, kind=pool[card])):
            r = one(card, pool[card], sc); res.append(r)
            print(card, sc, r.get('native'), r.get('first_mismatch'), [d for d in r.get('deploys', []) if not d[3] or not d[4]],
                  (r.get('error') or '').strip().splitlines()[-1:], flush=True)
    json.dump(res, open(sys.argv[1], 'w'), indent=1)
