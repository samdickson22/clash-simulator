"""Probe which ladder cards the Python engine plays and the native config exporter accepts.

Run from the repo root: PYTHONPATH=engine-rs:src python -B reports/cards/tools/probe_engines.py OUT.json
For each card: deploy it for seat 0 at (9, 8) (spells at the enemy princess tower), step 600 ticks,
record exceptions and how many entities of the card appeared. Then try differential.config((card,)).
"""
import json, random, sys, traceback
from collections import deque
sys.path.insert(0, 'reports/cards/tools')
from pool import ladder_pool
from clasher.battle import BattleState
from clasher.arena import Position

FILLER = ["Knight", "Archer", "Giant", "Musketeer", "Fireball", "Zap", "Valkyrie"]


def battle(card):
    b = BattleState(rng=random.Random(1))
    deck = [card] + [c for c in FILLER if c != card][:7]
    for p in b.players:
        p.hand = deck[:4]
        p.deck = list(deck)
        p.cycle_queue = deque(deck[4:8])
        p.elixir = 10
    return b


def probe(card, kind):
    out = dict(card=card)
    try:
        b = battle(card)
        before = set(b.entities)
        pos = Position(14.5, 25.5) if kind == 'spell' else Position(9.0, 8.0)
        ok = b.deploy_card(0, card, pos)
        out['deployed'] = bool(ok)
        new = [b.entities[i] for i in b.entities if i not in before]
        out['spawned'] = sorted({type(e).__name__ + ':' + str(getattr(getattr(e, 'card_stats', None), 'name', '?')) for e in new})
        names = set()
        for t in range(600):
            b.step()
            for e in b.entities.values():
                names.add(type(e).__name__ + ':' + str(getattr(getattr(e, 'card_stats', None), 'name', '?')))
        out['seen'] = sorted(names)
        out['python'] = 'ok'
    except Exception as e:
        out['python'] = 'error'
        out['python_error'] = traceback.format_exc(limit=3)[-600:]
    try:
        from differential import config
        cfg = config((card,))
        c = cfg['cards'].get(card)
        out['config'] = 'ok' if c else 'missing'
        out['config_kind'] = sorted(c.keys()) if c else None
    except Exception as e:
        out['config'] = 'error'
        out['config_error'] = traceback.format_exc(limit=3)[-600:]
    return out


if __name__ == '__main__':
    res = [probe(c['name'], c['kind']) for c in ladder_pool()]
    json.dump(res, open(sys.argv[1], 'w'), indent=1)
    for r in res:
        print(r['card'], r['python'], r.get('deployed'), r['config'], (r.get('python_error') or r.get('config_error') or '').strip().splitlines()[-1:] )
