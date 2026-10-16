"""Per-card native-vs-Python differential for the ladder pool (exploration probe).

Root layout: ROOT/engine-rs (native sources + differential.py), ROOT/src, the built clasher_core on PYTHONPATH.
For each card: export config((card,)+CARDS); seat 0 plays the card at (9,8) (spells at (14.5,25.5) by seat 0;
bridge spam etc. not covered), seat 1 answers with Knight at (9,24) at t=40; step both engines 900 ticks and compare
battle_digest each tick. Records: config status, apply_action agreement, first digest mismatch tick, native errors.
Usage: probe_native.py OUT.json [CARD ...]
"""
import json, sys, traceback
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
from pool import ladder_pool
import differential as D
from differential import config, initial, snapshot, battle_digest, clasher_core, Position

BASE = ("Knight", "Archers", "Giant", "Musketeer")


def one(card, kind, ticks=900):
    out = dict(card=card)
    try:
        cards = (card,) + tuple(c for c in BASE if c != card)
        cfg = config(cards)
        out['config'] = 'ok' if card in cfg['cards'] else 'missing'
    except Exception:
        out['config'] = 'error'
        out['error'] = traceback.format_exc(limit=4)[-700:]
        return out
    try:
        b = initial(7, cards=cards)
        for p in b.players:
            p.elixir = 10.0
        native = clasher_core.BattleState(snapshot(b, cfg))
        x, y = (14.5, 25.5) if kind == 'spell' else (9.0, 8.0)
        pa = b.deploy_card(0, card, Position(x, y))
        ra = native.apply_action(0, card, x, y)
        out['deploy'] = [bool(pa), bool(ra)]
        out['first_mismatch'] = None
        for t in range(ticks):
            if t == 40:
                pk = b.deploy_card(1, 'Knight', Position(9.0, 24.0))
                rk = native.apply_action(1, 'Knight', 9.0, 24.0)
                if pk != rk:
                    out['first_mismatch'] = out['first_mismatch'] or f'answer@{t}'
            b.step()
            native.step(1)
            if out['first_mismatch'] is None and native.digest() != battle_digest(b):
                out['first_mismatch'] = t
                break
        out['native'] = 'ok'
    except BaseException as e:  # pyo3 panics surface as PanicException (BaseException)
        out['native'] = 'error'
        out['error'] = (type(e).__name__ + ': ' + traceback.format_exc(limit=4))[-700:]
    return out


if __name__ == '__main__':
    pool = {c['name']: c['kind'] for c in ladder_pool()}
    names = sys.argv[2:] or list(pool)
    res = []
    for n in names:
        r = one(n, pool[n]); res.append(r)
        print(n, r.get('config'), r.get('deploy'), r.get('native'), r.get('first_mismatch'),
              (r.get('error') or '').strip().splitlines()[-1:], flush=True)
    json.dump(res, open(sys.argv[1], 'w'), indent=1)
