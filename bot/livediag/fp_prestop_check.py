"""Pre-stop check for a live player package (bot lead live-diag): run on the Mac code tree BEFORE stopping the loop.

1. Every file in the package's MANIFEST-LINES.sha256 is installed in --code with exactly that sha256.
2. Each --players name constructs through the deployed factory (bot.live.player.make_live_player) under the live env
   (run with loop/run-fullpool.sh's exports): -wint names give bot.search.interrupt.Interruptible wrapping a LivePlayer
   whose name is the full name; names without -wint give a plain LivePlayer (default-off); every search tier has its
   w<ms> deadline and the parsed K (samples) / reserve flags printed for the record.
No game, no taps, no writes outside --out. Exit status 0 only if every check passes.

    python -B -m bot.livediag.fp_prestop_check --code $CODE --lines MANIFEST-LINES.sha256 \
        --players LIVE-K4L-R-gs-rw-fc-w200-t4-p4-mk1a1-res,LIVE-K4L-R-gs-rw-fc-w200-t4-p4-mk1a1-res-K2-wint --out check.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--code', required=True, type=Path)
    ap.add_argument('--lines', required=True, type=Path, help='sha256sum-format lines: <sha256>  <path rel. to code>')
    ap.add_argument('--players', required=True)
    ap.add_argument('--out', required=True, type=Path)
    a = ap.parse_args(argv)
    out, ok = dict(files={}, players={}), True
    for line in a.lines.read_text().splitlines():
        if not line.strip():
            continue
        want, rel = line.split(None, 1)
        f = a.code / rel.strip()
        got = hashlib.sha256(f.read_bytes()).hexdigest() if f.exists() else None
        out['files'][rel.strip()] = dict(want=want, got=got, ok=got == want)
        ok &= got == want
    from bot.players.runtime import Runtime
    from bot.live.player import LivePlayer, make_live_player
    rt = Runtime()
    for name in a.players.split(','):
        try:
            p = make_live_player(rt, name)
            wrapped = type(p).__name__ == 'Interruptible'
            live = p.live if wrapped else p
            arm = getattr(live.search, 'arm', None)
            arm = dict(arm) if isinstance(arm, dict) else repr(arm)
            row = dict(type=f'{type(p).__module__}.{type(p).__name__}', inner=f'{type(live).__module__}.{type(live).__name__}',
                       name=p.name, deadline_s=live.deadline_seconds,
                       search=type(live.search).__name__, arm=arm,
                       samples=(arm.get('samples', 1) if isinstance(arm, dict) else None))
            good = isinstance(live, LivePlayer) and live.deadline_seconds is not None and p.name == name and \
                (wrapped == name.endswith('-wint')) and \
                (not wrapped or type(p).__module__ == 'bot.search.interrupt')
            row['ok'] = bool(good)
        except Exception as ex:
            row, good = dict(error=repr(ex)[:400], ok=False), False
        out['players'][name] = row
        ok &= good
    out['ok'] = bool(ok)
    a.out.write_text(json.dumps(out, indent=1, default=str) + '\n')
    print(json.dumps(out, indent=1, default=str))
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
