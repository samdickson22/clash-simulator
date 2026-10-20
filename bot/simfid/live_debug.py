"""Trace one LIVE segment: truth vs engine per frame, filtered to a card (simfid diagnostics).

    PYTHONPATH=<engine src>:<repo> CLASHER_ROOT=... python -m bot.simfid.live_debug OUT GAME T0 [--card C] [--every 10]
OUT is a live_run output dir (probes.json); GAME e.g. mem-c15/m37; T0 the segment start tick.
"""
import argparse
import json
from pathlib import Path

from bot.simfid import live_data as LD
from bot.simfid import live_run as LR


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out'); ap.add_argument('game'); ap.add_argument('t0', type=int)
    ap.add_argument('--card'); ap.add_argument('--every', type=int, default=10)
    ap.add_argument('--offset', type=int, default=0); ap.add_argument('--horizon', type=int, default=400)
    a = ap.parse_args()
    mains = json.loads(Path('/mpac/sdicks02/jobs/clasher/simfid-20261020/main-classes.json').read_text())
    probes = json.loads((Path(a.out) / 'probes.json').read_text())
    tp = {int(k): v for k, v in probes['towers'].items()}
    cp = {c: {int(k): v for k, v in d.items()} for c, d in probes['cards'].items()}
    game = LD.load_game(LD.MIRROR / a.game, mains)
    opp = LR.opponent_levels(game, tp, cp, mains)
    seg = next(s for s in LR.segments(game, a.horizon) if s['t0'] == a.t0)
    print('opp levels', opp[0], 'tower', opp[1])
    for p in seg['plays']:
        print('play', p)
    tr = []
    res = LR.run_segment(game, seg, a.offset, tp, cp, mains, opp, trace=tr)
    print('counters', res['counters'], 'drops', res['drops'])
    last = None
    for f in tr:
        if last is not None and f['tick'] - last < a.every:
            continue
        last = f['tick']
        T = sorted(u for u in f['truth'] if not a.card or u[1] == a.card)
        S = sorted(u for u in f['sim'] if not a.card or u[1] == a.card)
        print(f"t={f['tick']} truth {len(T)} sim {len(S)}")
        for u in T:
            print('   T', u)
        for u in S:
            print('   S', u)


if __name__ == '__main__':
    main()
