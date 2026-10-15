"""Which runtime files does the live bot actually read? (for the Mac copy list; LIVE track)

    python -m bot.live.runtime_manifest --out manifest.json [--ticks 900]

Runs Runtime() + LivePlayer (search tier, w200-t4, and the fast tier) for a short game in our engine with an audit
hook on open(), then lists every file opened or imported under the runtime root, the bot repo and the it5s2 dir,
with sizes, plus peak RSS. Our-engine game physics (src/clasher Python engine) is included because the harness uses
it; the live loop itself only needs what the players open (flagged 'player').
"""
from __future__ import annotations

import argparse
import json
import os
import resource
import sys
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--ticks', type=int, default=900)
    a = ap.parse_args()
    opened, phase = {}, ['setup']

    def hook(event, args):
        if event == 'open' and args and isinstance(args[0], (str, bytes, os.PathLike)):
            p = os.fsdecode(args[0])
            opened.setdefault(os.path.realpath(p), phase[0])
    sys.addaudithook(hook)
    import torch
    torch.set_num_threads(1)
    from bot.players.runtime import Runtime
    from bot.players.ours import play_match, x4s_setup
    from bot.live.player import LivePlayer, make_live_player
    rt = Runtime()
    rt.STUDENT
    case = x4s_setup(rt, 0, 1455777415631152 + 3*10**6)
    phase[0] = 'player'
    for tier in ('search', 'fast'):
        bot = LivePlayer(rt, tier=tier, wall_ms=200, threads=4)
        play_match(rt, {case['seat']: bot, 1-case['seat']: make_live_player(rt, 'v1')}, seed=case['seed'],
                   decks=case['decks'], max_ticks=a.ticks)
    mods = {os.path.realpath(m.__file__) for m in list(sys.modules.values()) if getattr(m, '__file__', None)}
    roots = {'runtime': str(rt.root), 'repo': str(Path(__file__).resolve().parents[2]),
             'students': str(Path(os.environ.get('CLASHER_LIVE_FAST', '').split(':', 1)[-1].rsplit('@', 1)[0]).parent)}
    files = {}
    for p in set(opened) | mods:
        for name, r in roots.items():
            if p.startswith(os.path.realpath(r) + '/') and os.path.isfile(p):
                files[p] = dict(root=name, rel=os.path.relpath(p, os.path.realpath(r)), bytes=os.path.getsize(p),
                                phase=opened.get(p, 'import'))
    by_root = {}
    for f in files.values():
        by_root.setdefault(f['root'], [0, 0])
        by_root[f['root']][0] += 1
        by_root[f['root']][1] += f['bytes']
    out = dict(roots=roots, totals={k: dict(files=n, mb=round(b/2**20, 1)) for k, (n, b) in by_root.items()},
               peak_rss_mb=round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024, 1),
               files=sorted(files.values(), key=lambda f: (f['root'], f['rel'])))
    Path(a.out).write_text(json.dumps(out, indent=1))
    print(json.dumps(dict(totals=out['totals'], peak_rss_mb=out['peak_rss_mb'])))


if __name__ == '__main__':
    main()
