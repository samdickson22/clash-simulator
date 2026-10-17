"""Pre-stop check for a live player package (bot lead live-diag): run on the Mac code tree BEFORE stopping the loop.

1. Every file in the package's MANIFEST-LINES.sha256 is installed in --code with exactly that sha256 (regular files).
2. Each --players name constructs through the deployed factory (bot.live.player.make_live_player) imported FROM --code
   (sys.path is set from --code; the origins of bot.live.player, bot.search.lopp_fast, bot.search.interrupt and
   bot.search.lopp are verified to lie inside --code), and the constructed config matches the name's tokens:
     -wint (last token)  <=> bot.search.interrupt.Interruptible wrapping a bot.live.player.LivePlayer, else a plain
                             LivePlayer (default-off);
     w<ms>               == the LivePlayer's deadline (ms/1000) and the search tier's deadline;
     K<n>                == the search arm's samples (default 1);
     res                 <=> the search arm's reserve flag;
     the player's name   == the full name.
No game, no taps, no writes outside --out. Supervised like fp_mac_bench (own session, --deadline-s, TERM->KILL->reap).
Exit 0 only if every check passes; 1 = a check failed, 124 = deadline, 130 = signal.

    python -B fp_prestop_check.py --code $CODE --lines MANIFEST-LINES.sha256 --players NAME1,NAME2 --out check.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
from pathlib import Path

CHILD_FLAG = '--_supervised-child'


def supervise(argv, deadline_s):
    child = subprocess.Popen([sys.executable, '-B', os.path.abspath(__file__), CHILD_FLAG, *argv], start_new_session=True)
    state = dict(sig=None)

    def kill_group():
        for sig in (signal.SIGTERM, signal.SIGKILL):
            try:
                os.killpg(child.pid, sig)
            except ProcessLookupError:
                break
            try:
                child.wait(timeout=5)
                break
            except subprocess.TimeoutExpired:
                continue
        child.wait()

    def on_signal(sig, frame):
        state['sig'] = sig
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)
    try:
        return child.wait(timeout=deadline_s)
    except subprocess.TimeoutExpired:
        print(f'fp_prestop_check: deadline {deadline_s}s exceeded', file=sys.stderr)
        kill_group()
        return 124
    except KeyboardInterrupt:
        print(f'fp_prestop_check: signal {state["sig"]}', file=sys.stderr)
        kill_group()
        return 130


def expect(name):
    toks = name.split('-')
    w = next((int(t[1:]) for t in toks if re.fullmatch(r'w\d+', t)), None)
    k = next((int(t[1:]) for t in toks if re.fullmatch(r'K\d+', t)), 1)
    return dict(wint=name.endswith('-wint'), deadline_s=None if w is None else w / 1000, samples=k, reserve='res' in toks)


def child_main(a):
    code = Path(a.code).resolve()
    sys.path[:0] = [str(code), str(code / 'src'), str(code / 'live' / 'perception')]
    out, ok = dict(code=str(code), files={}, players={}), True
    for line in a.lines.read_text().splitlines():
        if not line.strip():
            continue
        want, rel = line.split(None, 1)
        f = code / rel.strip()
        got = hashlib.sha256(f.read_bytes()).hexdigest() if f.is_file() else None
        out['files'][rel.strip()] = dict(want=want, got=got, ok=got == want)
        ok &= got == want
    from bot.players.runtime import Runtime
    from bot.live.player import LivePlayer, make_live_player
    rt = Runtime()
    for name in a.players.split(','):
        try:
            e = expect(name)
            p = make_live_player(rt, name)
            wrapped = type(p).__name__ == 'Interruptible'
            live = p.live if wrapped else p
            arm = getattr(live.search, 'arm', None)
            arm = dict(arm) if isinstance(arm, dict) else {}
            got = dict(wint=wrapped and type(p).__module__ == 'bot.search.interrupt',
                       deadline_s=live.deadline_seconds, search_deadline_s=getattr(live.search, 'deadline_seconds', None),
                       samples=arm.get('samples', 1), reserve=bool(arm.get('reserve')))
            checks = dict(type=type(live) is LivePlayer, wint=got['wint'] == e['wint'] and wrapped == e['wint'],
                          deadline=e['deadline_s'] is not None and got['deadline_s'] is not None and
                          abs(got['deadline_s'] - e['deadline_s']) < 1e-9 and got['search_deadline_s'] is not None and
                          abs(got['search_deadline_s'] - e['deadline_s']) < 1e-9,
                          samples=got['samples'] == e['samples'], reserve=got['reserve'] == e['reserve'],
                          name=p.name == name)
            row = dict(type=f'{type(p).__module__}.{type(p).__name__}', expected=e, got=got, arm=arm, checks=checks,
                       ok=all(checks.values()))
        except Exception as ex:
            row = dict(error=repr(ex)[:400], ok=False)
        out['players'][name] = row
        ok &= row['ok']
    origins = {}
    for n in ('bot.live.player', 'bot.search.lopp_fast', 'bot.search.lopp', 'bot.search.interrupt', 'bot.players.runtime'):
        m = sys.modules.get(n)
        f = getattr(m, '__file__', None) if m else None
        if m is not None:
            origins[n] = dict(file=f, inside_code=bool(f) and Path(f).resolve().is_relative_to(code))
            ok &= origins[n]['inside_code']
    out['import_origins'] = origins
    out['ok'] = bool(ok)
    a.out.write_text(json.dumps(out, indent=1, default=str) + '\n')
    print(json.dumps(out, indent=1, default=str))
    return 0 if ok else 1


def parse(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--code', required=True, type=Path)
    ap.add_argument('--lines', required=True, type=Path, help='sha256sum-format lines: <sha256>  <path rel. to code>')
    ap.add_argument('--players', required=True)
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--deadline-s', type=float, default=300)
    return ap.parse_args(argv)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == CHILD_FLAG:
        sys.exit(child_main(parse(argv[1:])))
    sys.exit(supervise(argv, parse(argv).deadline_s))


if __name__ == '__main__':
    main()
