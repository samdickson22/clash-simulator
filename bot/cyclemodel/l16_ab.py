"""Cycle-model A/B on live-diag's L16 RoyaleSim driver (exploration).

    python -m bot.cyclemodel.l16_ab [--driver l16_cadence] -- <driver args, e.g. --players res
        --noise clean,raw+cychard,raw+cycsoft --opponents LIVE-K4CW-r16 --cases 200 --base B --out DIR --workers W>

Runs live-diag's driver module (bot/livediag/l16_cadence.py or their cadence copy, found on PYTHONPATH) unchanged, with
bot.livediag.history_noise.NoisyPlayer replaced in-process by a subclass that understands two extra arm suffixes:

    raw+cychard   live-diag's raw noisy opponent stream (HistoryNoise guard off), then bot/cyclemodel/ab.py
                  CycleGuardPlayer 'hard' = the deployed translator's _consistent guard on both streams (today's bot)
    raw+cycsoft   same stream and guard on the D1 rows; cycle conflicts reach the search belief as 'card?' with P(real)
                  (BOT_CYCLE_PREAL); BOT_CYCLE_MODEL=<--soft-spec> is set only while this arm's player starts (the
                  planner installs the belief class at start), so clean/hard arms in the same worker run today's code.
'clean' and every other arm are the driver's own. The guard sits between NoisyPlayer and the player
(NoisyPlayer -> CycleGuardPlayer -> player), so bind_rsim / the recorder rows are untouched. Per-game guard and belief
counts land in the row's noise_counts (cyc_*, belief_*).
"""
from __future__ import annotations

import argparse
import os
import runpy
import sys

SUFFIXES = {'cychard': 'hard', 'cycsoft': 'soft'}


def install(soft_spec='soft'):
    from bot.livediag import history_noise as hn
    if getattr(hn.NoisyPlayer, '_cyc', False):
        return
    base = hn.NoisyPlayer

    class CycNoisyPlayer(base):
        _cyc = True

        def __init__(self, rt, inner, arm, name):
            mods = arm.split('+')
            mode = next((SUFFIXES[m] for m in mods if m in SUFFIXES), None)
            if mode is not None:
                if mods[0] != 'raw':
                    raise ValueError(f'{arm}: the cycle guard needs the raw (unguarded) stream')
                from bot.cyclemodel.ab import CycleGuardPlayer
                inner = CycleGuardPlayer(rt, inner, mode, f'cyc-{mode}:{getattr(inner, "name", "?")}')
                arm = '+'.join(m for m in mods if m not in SUFFIXES)
            self.cyc_mode = mode
            super().__init__(rt, inner, arm, name)

        def start(self, ctx):
            if self.cyc_mode != 'soft':
                return super().start(ctx)
            prev = os.environ.get('BOT_CYCLE_MODEL')
            os.environ['BOT_CYCLE_MODEL'] = soft_spec
            try:
                return super().start(ctx)
            finally:
                if prev is None:
                    os.environ.pop('BOT_CYCLE_MODEL', None)
                else:
                    os.environ['BOT_CYCLE_MODEL'] = prev

    hn.NoisyPlayer = CycNoisyPlayer


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    rest = []
    if '--' in argv:
        i = argv.index('--')
        argv, rest = argv[:i], argv[i + 1:]
    ap = argparse.ArgumentParser()
    ap.add_argument('--driver', default='l16_cadence')
    ap.add_argument('--soft-spec', default='soft')
    a = ap.parse_args(argv)
    if os.environ.get('BOT_CYCLE_MODEL'):
        raise SystemExit('BOT_CYCLE_MODEL must be unset globally (only the soft arm sets it, at its own start)')
    install(a.soft_spec)
    sys.argv = [a.driver] + rest
    runpy.run_module(a.driver, run_name='__main__', alter_sys=True)


if __name__ == '__main__':
    main()
