"""Multi-body play counting on recorded perception (LIVE translator check, exploration tier).

Runs the births UnitTracker alone over the integration VALIDATION dump (live/perception/dump_records.py: per frame
the perception record `pred` and the dense-label truth record `truth`, header = the true plays) and counts, per true
card, how many plays the tracker derives for each true deployment. A multi-body card must count as ONE play; death or
production spawns as none.

    PYTHONPATH=. python -m bot.live.multibody_eval --source pred|truth [--tracker old|new] [--matches N] --out F.json

Per true play (owner o, card c, tile, tick): the derived plays of the same owner and sprite family within `tiles`
and [tick-10, tick+80] are its counted plays (ideal: exactly one, of card c); `right` = card c among all derived plays
nearby. Derived plays near no true play are extras,
attributed to the nearest live/recent spawner or death (spawn) or not (other). Both owners are scored (the live
translator only uses the opponent's derived plays; ours come from our own commands)."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path

from bot.live.real_replay import DUMP, load_dump, mirror, true_plays

MULTI = ('SkeletonArmy', 'Skeletons', 'Goblins', 'GoblinGang', 'Minions', 'MinionHorde', 'Bats', 'Archers',
         'Wallbreakers', 'RoyalHogs', 'Rascals', 'Goblinstein', 'AngryBarbarians', 'GoblinHut', 'FirespiritHut', 'Golem',
         'FireSpirits', 'IceGolem')


def frames(rows, source):
    for r in rows:
        rec = r[source] if source == 'truth' else r['pred']
        yield int(r['tick']), mirror(rec)


def run(cards, rows, plays, tracker_factory, source, tiles=3.5, lo=-10, hi=80):
    tr = tracker_factory(cards)
    derived = []
    for tick, rec in frames(rows, source):
        units = []
        for u in rec.get('units', ()):
            card = u.get('card') or u.get('cls')
            if not cards.is_card(card):
                continue
            units.append(dict(card=card, owner=int(u['owner']), x=float(u['x']), y=float(u['y']),
                              score=u.get('score'))
                         if getattr(tr, 'wants_dicts', False) else
                         (card, 0 if int(u['owner']) == 0 else 1, float(u['x']), float(u['y']), u.get('score')))
        own = {t['side']: t.get('alive', True) for t in rec.get('towers', ()) if t['owner'] == 0 and t['kind'] == 'princess'}
        _, p = tr.update(tick, units, own)
        derived += [dict(owner=o, card=c, x=x, y=y, tick=t) for o, c, x, y, t in p]
    t0, t1 = int(rows[0]['tick']), int(rows[-1]['tick'])
    truth = [p for p in plays if t0 + 5 <= p['tick'] <= t1 - hi]
    per, used = [], set()
    for p in truth:
        near = [i for i, d in enumerate(derived) if d['owner'] == p['owner'] and lo <= d['tick'] - p['tick'] <= hi
                and math.hypot(d['x'] - p['x'], d['y'] - p['y']) <= tiles]
        used.update(near)
        # plays counted for this deployment: those of its sprite family (another card deployed alongside is its own
        # play); `cards` lists every derived play nearby
        fam = [i for i in near if cards.fam(derived[i]['card']) == cards.fam(p['card'])]
        per.append(dict(owner=p['owner'], card=p['card'], n=len(fam), cards=[derived[i]['card'] for i in near],
                        tick=int(p['tick']), x=round(p['x'], 1), y=round(p['y'], 1)))
    extras = [d for i, d in enumerate(derived) if i not in used and t0 + 5 <= d['tick'] <= t1 - hi]
    return per, extras, tr.stats


def table(per, extras):
    rows = defaultdict(lambda: dict(true=0, counted=0, exact1=0, zero=0, multi=0, right_card=0, confused=Counter()))
    for p in per:
        r = rows[(p['owner'], p['card'])]
        r['true'] += 1
        r['counted'] += p['n']
        r['exact1'] += p['n'] == 1
        r['zero'] += p['n'] == 0
        r['multi'] += p['n'] > 1
        r['right_card'] += p['card'] in p['cards']
        for c in p['cards']:
            if c != p['card']:
                r['confused'][c] += 1
    ex = Counter((d['owner'], d['card']) for d in extras)
    return rows, ex


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--source', default='pred', choices=('pred', 'truth'))
    ap.add_argument('--tracker', default='new', choices=('old', 'new'))
    ap.add_argument('--legacy', default='', help='births.py copy whose UnitTracker is --tracker old')
    ap.add_argument('--matches', type=int, default=0)
    ap.add_argument('--kw', default='{}', help='UnitTracker keyword overrides (JSON)')
    ap.add_argument('--oov', action='store_true', help='register the proxy table\'s off-vocab pseudo-cards '
                    '(bot/live/oov.py; R15 inferred spawners active, the opponent allowed every card)')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    from bot.players.runtime import Runtime
    from bot.live import births
    rt = Runtime()
    cards = births.CardBodies(rt)
    if a.oov:
        from bot.live.oov import OffVocab
        o = OffVocab(cards, rt.R.costs)
        if not o.pseudo:
            raise SystemExit('--oov: bot.cards.proxy_table is not available')
        cards.add_named(o.pseudo, o.shared)
    if a.tracker == 'old':
        import importlib.util
        spec = importlib.util.spec_from_file_location('births_legacy', a.legacy)
        legacy = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(legacy)
        factory = lambda cb: legacy.UnitTracker(legacy.CardBodies(rt))
    else:
        kw = json.loads(a.kw)
        factory = lambda cb: births.UnitTracker(cb, **kw)
    paths = sorted(DUMP.glob('*.jsonl.gz'))[:a.matches or None]
    per, extras, stats = [], [], Counter()
    for path in paths:
        head, rows = load_dump(path)
        p, e, s = run(cards, rows, true_plays(head), factory, a.source)
        per += p
        extras += e
        stats.update(s)
    rows, ex = table(per, extras)
    out = dict(source=a.source, tracker=a.tracker, kw=a.kw, oov=a.oov, matches=len(paths),
               cards={f'{o}:{c}': dict(r, confused=dict(r['confused'])) for (o, c), r in sorted(rows.items())},
               extras={f'{o}:{c}': n for (o, c), n in sorted(ex.items())}, stats=dict(stats))
    Path(a.out).write_text(json.dumps(out, indent=1))
    print(f'{"owner:card":24s} true counted exact1 zero multi right  extras  confused')
    for (o, c), r in sorted(rows.items(), key=lambda kv: (kv[0][1] not in MULTI, kv[0])):
        print(f'{o}:{c:22s} {r["true"]:4d} {r["counted"]:7d} {r["exact1"]:6d} {r["zero"]:4d} {r["multi"]:5d} '
              f'{r["right_card"]:5d} {ex.get((o, c), 0):6d}  {dict(r["confused"])}')
    print('extras without a true play:', sorted(((f'{o}:{c}', n) for (o, c), n in ex.items()), key=lambda kv: -kv[1]))
    print('stats:', {k: v for k, v in stats.items() if not k.startswith('no_body')})


if __name__ == '__main__':
    main()
