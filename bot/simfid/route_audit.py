"""Own-troop route audit: native public trajectory vs the engine's on an empty board (simfid diagnostics).

    PYTHONPATH=<engine src>:<repo> CLASHER_ROOT=... python -m bot.simfid.route_audit [--card HogRider] [--every 1]

For each own play of --card (exact tap tile + landing tick), the native body is tracked through the public records
while NO opponent body is within 6 tiles of it (an undisturbed walk); the engine deploys the same card at the same
tile for our NATIVE seat on an empty board (opponent towers alive) and steps the same number of ticks. Compared at
each record tick of the undisturbed stretch: distance native-engine. Reported: per stretch the error at the end and
the max; the share of stretches whose end error <= 1/4 tile; examples of the worst.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path

from bot.simfid import live_data as LD


def engine_route(card, x, y, seat, ticks, levels, rec=None):
    from bot.simfid.live_engine import LiveSim
    from clasher.arena import Position
    from clasher.entities import Troop
    sim = LiveSim()
    deck = [card] + [c for c in LD.HOG26 if c != card]
    b = sim.battle([deck, deck], [levels, {c: 11 for c in deck}] if seat == 0 else [{c: 11 for c in deck}, levels],
                   [9, 10] if seat == 0 else [10, 9])
    b.players[seat].elixir = 10
    rot = seat == 1
    if rec is not None:          # crown towers as the record shows them at the play
        sim.b, sim.seat = b, seat
        sim._set_towers(rec)
    ex, ey = (18 - x, 32 - y) if rot else (x, y)
    before = set(b.entities)
    if not b.deploy_card(seat, card, Position(ex, ey)):
        return None
    out = []
    for _ in range(ticks + 1):
        new = [e for k, e in b.entities.items() if k not in before and isinstance(e, Troop) and e.is_alive]
        if new:
            e = new[0]
            px, py = e.position.x, e.position.y
            out.append((18 - px, 32 - py) if rot else (px, py))
        else:
            out.append(None)
        b.step()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--card', default='HogRider')
    ap.add_argument('--every', type=int, default=1)
    ap.add_argument('--out')
    a = ap.parse_args()
    acc = json.loads(LD.ACCOUNT_LEVELS.read_text())['effective_levels']
    rows = []
    for d in LD.game_dirs()[::a.every]:
        sess = json.loads((d / 'session.json').read_text()) if (d / 'session.json').exists() else {}
        seat = int((sess.get('side') or {}).get('side') or 0)
        recs = LD.load_records(d)
        own, _ = LD.own_plays(d)
        for p in own:
            if p.card != a.card:
                continue
            path = []
            for r in recs:
                if r.tick < p.tick:
                    continue
                us = [u for u in r.units if u.owner == 0 and u.card == a.card]
                if not us:
                    if path:
                        break
                    continue
                if not path:
                    u = min(us, key=lambda u: math.hypot(u.x - p.x, u.y - p.y))
                    if math.hypot(u.x - p.x, u.y - p.y) > 1.0:
                        break
                else:
                    lx, ly = path[-1][1], path[-1][2]
                    u = min(us, key=lambda u: math.hypot(u.x - lx, u.y - ly))
                    if math.hypot(u.x - lx, u.y - ly) > 1.5:
                        break
                if any(v.owner == 1 and math.hypot(v.x - u.x, v.y - u.y) < 6 for v in r.units):
                    break
                path.append((r.tick - p.tick, u.x, u.y))
            if len(path) < 6:
                continue
            rec0 = max((r for r in recs if r.tick <= p.tick), key=lambda r: r.tick, default=None)
            sim = engine_route(a.card, p.x, p.y, seat, path[-1][0] + 2, acc, rec0)
            if not sim:
                continue
            errs = []
            for t, x, y in path:
                s = sim[t] if t < len(sim) else None
                errs.append(math.hypot(s[0] - x, s[1] - y) if s else 9.)
            rows.append(dict(game=str(d.relative_to(LD.MIRROR)), tick=p.tick, tile=(p.x, p.y), seat=seat, n=len(path),
                             end=errs[-1], max=max(errs), path=[(t, round(x, 2), round(y, 2)) for t, x, y in path[::4]],
                             sim=[(t, round(sim[t][0], 2), round(sim[t][1], 2)) for t, _, _ in path[::4] if sim[t]]))
    for lane in ('left', 'right'):
        sub = [r['end'] for r in rows if (r['tile'][0] < 9) == (lane == 'left')]
        if sub:
            print(f"  lane {lane}: n={len(sub)} end median {statistics.median(sub):.3f} <=1/4 "
                  f"{100 * sum(e <= .25 for e in sub) / len(sub):.1f}%")
    ends = [r['end'] for r in rows]
    print(f"{a.card}: {len(rows)} undisturbed stretches; end error median {statistics.median(ends):.3f}, "
          f"mean {statistics.mean(ends):.3f}, <=1/4 {100 * sum(e <= .25 for e in ends) / len(ends):.1f}%, "
          f"max-error median {statistics.median(r['max'] for r in rows):.3f}")
    for r in sorted(rows, key=lambda r: -r['end'])[:6]:
        print(' ', r['game'], r['tick'], r['tile'], 'seat', r['seat'], 'end', round(r['end'], 2))
        print('    native', r['path'][:12])
        print('    engine', r['sim'][:12])
    if a.out:
        Path(a.out).write_text(json.dumps(rows))


if __name__ == '__main__':
    main()
