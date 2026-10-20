"""Formation audit: native first-frame deployment layouts vs the engine's, per card (simfid diagnostics).

    PYTHONPATH=<engine src>:<repo> CLASHER_ROOT=... python -m bot.simfid.formation_audit [--owner 1] [--every 1]

For each fresh public deployment (live_data.birth_clusters, no body of the card alive anywhere) whose first frame
shows all of its main bodies, the native layout is the bodies' offsets from the deployment's anchor (own plays: the
exact tap tile; opponent plays: the bodies' centroid). The engine deploys the same card at the same point for the
same NATIVE seat in an empty battle; its layout is read on the first tick its bodies exist. Error = mean distance of
an optimal body matching (tiles). Reported per card: deployments, median/mean error, share within 1/4 tile.
"""
from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path

from bot.simfid import live_data as LD
from bot.simfid.live_run import _assign

FILLER = ['Knight', 'Archers', 'Zap', 'Fireball', 'Cannon', 'Musketeer', 'Valkyrie', 'Giant', 'Arrows']


def engine_layout(card, x, y, seat_engine, rotate, level=11):
    from bot.simfid.live_engine import LiveSim
    from clasher.arena import Position
    from clasher.entities import Building, Troop
    sim = LiveSim()
    deck = [card] + [c for c in FILLER if c != card][:7]
    b = sim.battle([deck, deck], [{c: level for c in deck}] * 2, [11, 11])
    pid = seat_engine
    b.players[pid].elixir = 10
    before = set(b.entities)
    ex, ey = (18 - x, 32 - y) if rotate else (x, y)   # our frame -> native frame (rotated when we were seat 1)
    if not b.deploy_card(pid, card, Position(ex, ey)):
        return None
    for _ in range(30):
        new = [e for k, e in b.entities.items() if k not in before and isinstance(e, (Troop, Building))]
        if new:
            out = []
            for e in new:
                px, py = e.position.x, e.position.y
                out.append((18 - px, 32 - py) if rotate else (px, py))
            return out
        b.step()
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--owner', type=int, default=1)
    ap.add_argument('--every', type=int, default=1)
    ap.add_argument('--min', type=int, default=8)
    ap.add_argument('--out')
    a = ap.parse_args()
    mains = json.loads(Path('/mpac/sdicks02/jobs/clasher/simfid-20261020/main-classes.json').read_text())
    per = defaultdict(list)
    examples = {}
    for d in LD.game_dirs()[::a.every]:
        sess = json.loads((d / 'session.json').read_text()) if (d / 'session.json').exists() else {}
        seat = int((sess.get('side') or {}).get('side') or 0)
        deployer_seat = seat if a.owner == 0 else 1 - seat
        recs = LD.load_records(d)
        own = LD.own_plays(d)[0] if a.owner == 0 else []
        for c in LD.birth_clusters(recs, a.owner):
            card = c['card']
            if not c['fresh'] or card in LD.CARRIED_BODIES:
                continue
            main = set(mains.get(card) or [])
            bodies = [(b['x0'], b['y0']) for b in c['bodies'] if b['first'] == c['tick'] and (not main or b['cls'] in main)]
            if not bodies:
                continue
            if a.owner == 0:
                tap = next((p for p in own if p.card == card and -10 <= c['tick'] - p.tick <= 15), None)
                if tap is None:
                    continue
                ax, ay = tap.x, tap.y
            else:
                ax, ay = sum(x for x, _ in bodies) / len(bodies), sum(y for _, y in bodies) / len(bodies)
            sim = engine_layout(card, ax, ay, deployer_seat, seat == 1)
            if not sim:
                per[card].append(None)
                continue
            if a.owner == 1:   # compare shapes about their own centroids (the tap is unknown)
                sx, sy = sum(x for x, _ in sim) / len(sim), sum(y for _, y in sim) / len(sim)
                sim = [(x - sx + ax, y - sy + ay) for x, y in sim]
            pairs = _assign(bodies, sim)
            n = max(len(bodies), len(sim))
            err = (sum(dd for _, _, dd in pairs) + 2.0 * (n - len(pairs))) / n
            per[card].append(err)
            if card not in examples or err > examples[card][0]:
                examples[card] = (err, [(round(x, 2), round(y, 2)) for x, y in sorted(bodies)],
                                  [(round(x, 2), round(y, 2)) for x, y in sorted(sim)], round(ax, 2), round(ay, 2))
    rows = []
    for card, errs in per.items():
        ok = [e for e in errs if e is not None]
        if len(errs) < a.min:
            continue
        rows.append(dict(card=card, n=len(errs), refused=len(errs) - len(ok),
                         median=statistics.median(ok) if ok else None, mean=statistics.mean(ok) if ok else None,
                         within_q=sum(e <= .25 for e in ok) / len(ok) if ok else None, worst=examples.get(card)))
    rows.sort(key=lambda r: -(r['mean'] or 9) * r['n'])
    for r in rows:
        print(f"{r['card']:<18s} n={r['n']:>4d} refused={r['refused']:>3d} median={r['median'] or 0:.3f} "
              f"mean={r['mean'] or 0:.3f} within1/4={100 * (r['within_q'] or 0):5.1f}%  worst={r['worst']}")
    if a.out:
        Path(a.out).write_text(json.dumps(rows, indent=1))


if __name__ == '__main__':
    main()
