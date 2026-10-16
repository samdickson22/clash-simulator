"""Replay a logged live match (perception.jsonl = the exact LiveSession.step records) through the LIVE harness with
the deterministic K4L-R-gs search tier, logging every search decision and the pocket counterfactual (exploration).

    python -m bot.pocket.live_replay RUN_DIR --out FILE.jsonl --fast student:<ckpt>@<thr> [--cf-from TICK]

Harness: bot.live.translate.LiveTranslator + LiveSession and bot.live.player.LivePlayer, as built by the live loop
from RUN_DIR/session-config.json (deck, translator, session options), unedited. The only substitution is the search
tier: LIVE-K4L-R-gs-rw-fc-w200-t4-p4 -> its deterministic twin K4L-R-gs (no wall clock), wrapped by
bot.pocket.diag.Logged (read-only; counterfactual at every search decision from --cf-from on with a dead enemy princess
tower). Rows: kind 'search' as bot.pocket.diag, plus 'step' rows (tick, action, LivePlayer source) for every decision.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


class ReplaySearch:
    """Logged(K4L-R-gs) with the search-tier call signature LivePlayer uses."""

    def __init__(self, logged):
        self.logged = logged

    def __getattr__(self, name):
        return getattr(self.logged.inner, name)

    @property
    def name(self):
        return self.logged.name

    def start(self, ctx):
        self.logged.start(ctx)

    def act(self, view, *, wall0=None, default=None):
        return self.logged.act(view)

    def close(self):
        self.logged.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('run', type=Path)
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--fast', required=True)
    ap.add_argument('--search', default='K4L-R-gs')
    ap.add_argument('--cf-every', type=int, default=10)
    a = ap.parse_args()
    os.environ.setdefault('PYTHONHASHSEED', '0')
    import torch
    torch.set_num_threads(1)
    from bot.players.runtime import Runtime
    from bot.live.player import LivePlayer
    from bot.live.translate import LiveSession, LiveTranslator
    from bot.pocket.diag import Logged, make_player
    cfg = json.loads((a.run / 'session-config.json').read_text())
    rt = Runtime()
    sink = open(a.out, 'w')
    live = LivePlayer(rt, tier='search', fast_spec=a.fast, cutoff_default='it5s2', name=cfg['player'] + '~replay')
    live.search = ReplaySearch(Logged(make_player(rt, a.search), rt, sink, dict(run=a.run.name),
                                      cf_every=a.cf_every))
    tcfg, scfg = cfg['translator'], cfg['session']
    tr = LiveTranslator(rt, cfg['deck'], unknown_card=tcfg['unknown_card'], plays_from=tcfg['plays_from'])
    s = LiveSession(rt, live, cfg['deck'], seed=scfg['seed'], command_delay=scfg['command_delay'],
                    expire=scfg['expire'], translator=tr)
    errors = 0
    for line in open(a.run / 'perception.jsonl'):
        rec = json.loads(line)
        # as live/loop/drive.py: floor the HUD elixir at OUR still-pending reservations (the replayed bot's own
        # reservations differ from the live run's), and keep feeding frames after an exception
        rec['elixir'] = max(rec['elixir'], sum(c.cost for c in s.ch.pending))
        # the deterministic K4L path passes info.tick into the native root (i64): floor the fractional tick
        # (poll ticks are multiples of 5 either way, so the poll schedule is unchanged)
        if rec.get('tick') is not None:
            rec['tick'] = int(rec['tick'])
        try:
            d = s.step(rec)
        except Exception as ex:
            errors += 1
            sink.write(json.dumps(dict(run=a.run.name, kind='error', tick=rec.get('tick'), error=repr(ex)[:300])) + '\n')
            continue
        if d is not None and d.stats is not None:
            sink.write(json.dumps(dict(run=a.run.name, kind='step', tick=s.log[-1]['tick'], action=int(d.action),
                                       wait_ticks=d.wait_ticks, source=d.stats.get('source'),
                                       error=d.stats.get('error'))) + '\n')
            sink.flush()
    s.close()
    sink.write(json.dumps(dict(run=a.run.name, kind='end', errors=errors, tr_stats=dict(tr.stats))) + '\n')


if __name__ == '__main__':
    main()
