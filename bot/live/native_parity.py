"""Native parity fixture for porting the planner core to another platform (LIVE track, exploration).

    # on the fleet (reference native 44874fd6):
    python -m bot.live.native_parity dump --out parity.json [--roots 40]
    # on the Mac, with the Mac-built native and its pin set:
    python -m bot.live.native_parity check --fixture parity.json

dump: plays short games in our engine (K4C's own poll cadence), takes `roots` public roots exactly as the search
builds them (Resources.root from the true public view + a belief sample), and records each root's payload JSON and
the native rollout value of WAIT + up to 4 legal plays x 3 styles with the frozen no-deadline budget (1e6 s).
check: rebuilds every root from its payload with the local native and requires bit-identical values. Equal values
on these roots are the minimum before Mac search timings or decisions are trusted (build48 had to pass the same).
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

STYLES = ('balanced', 'pressure', 'defense')


def rollout_args(R):
    from clasher.rl.c56_rollout_planner import C56SearchConfig
    c = C56SearchConfig(samples=16, threads=1, horizon=160, wait_screen8=False)
    return dict(command_delay=27, opponent_delay=27, horizon=160, interval=c.interval, elixir_weight=c.elixir_weight)


def config_sha(R):
    return hashlib.sha256(json.dumps(R.config, sort_keys=True).encode()).hexdigest()


def values(R, payload, seat, actions, args):
    import clasher_core
    root = clasher_core.BattleState(payload)
    out = []
    for a in actions:
        for s in STYLES:
            out.append(float(R.native.rollout_e1(root, seat, a, s, args['command_delay'], args['opponent_delay'],
                                                 args['horizon'], args['interval'], args['elixir_weight'], 1e6)))
    return out


def dump(rt, out, n_roots, base):
    from bot.players.ours import play_match, x4s_setup
    from bot.players.base import Decision, WAIT
    from bot.eval.headline import make_player
    from bot.live.levels import LevelRoot, Levels
    from fair_player import PublicPlanner
    R, args = rt.R, rollout_args(rt.R)
    lr = LevelRoot(R, Levels())
    roots = []

    class Taker:
        name, deadline_seconds = 'parity-taker', None

        def __init__(self, seed):
            self.inner = make_player(rt, 'v1')
            self.p = PublicPlanner(R, rt.PRIOR, seed)
            self.rng = np.random.default_rng(seed)

        def start(self, ctx):
            self.inner.start(ctx)

        def act(self, view):
            d = self.inner.act(view)
            self.p.belief.update(view.info.tick, view.info.events)
            if view.tick % 150 == 0 and len(roots) < n_roots:
                opp = self.p.belief.sample(self.rng)
                payload = lr.payload(view.info, opp, self.rng)
                mask = self.inner.poller.mask
                legal = [a for a in range(2304) if mask is not None and mask[a]]
                pick = sorted(self.rng.choice(legal, size=min(4, len(legal)), replace=False).tolist()) if legal else []
                actions = [WAIT] + [int(a) for a in pick]
                vals = values(R, payload, view.seat, actions, args)
                body = json.loads(payload)
                body.pop('config')               # shared, sha-checked below; re-attached by check
                roots.append(dict(tick=view.tick, seat=view.seat, payload=body, actions=actions, values=vals))
            return d

        def close(self):
            pass
    i = 0
    while len(roots) < n_roots:
        case = x4s_setup(rt, i, base)
        play_match(rt, {0: Taker(case['seed']), 1: make_player(rt, 'v1')}, seed=case['seed'], decks=case['decks'],
                   max_ticks=6001)
        i += 1
    native = Path(rt.native_dir) / 'clasher_core.abi3.so'
    from bot.players.runtime import sha256
    Path(out).write_text(json.dumps(dict(native_sha256=sha256(native), config_sha256=config_sha(R), args=args,
                                         roots=roots)))
    print(f'{len(roots)} roots, {sum(len(r["values"]) for r in roots)} values -> {out}')


def check(rt, fixture):
    from bot.players.runtime import sha256
    f = json.loads(Path(fixture).read_text())
    local = sha256(Path(rt.native_dir) / 'clasher_core.abi3.so')
    if config_sha(rt.R) != f['config_sha256']:
        raise SystemExit('engine config differs from the fixture: the runtime copy is not the reference runtime')
    bad = 0
    for r in f['roots']:
        payload = json.dumps(dict(r['payload'], config=rt.R.config))
        got = values(rt.R, payload, r['seat'], r['actions'], f['args'])
        if got != r['values']:
            bad += 1
            print('MISMATCH tick', r['tick'], [(a, b) for a, b in zip(got, r['values']) if a != b][:4])
    print(json.dumps(dict(reference_native=f['native_sha256'], local_native=local, roots=len(f['roots']),
                          mismatched_roots=bad, parity=bad == 0)))
    return bad == 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    d = sub.add_parser('dump'); d.add_argument('--out', required=True); d.add_argument('--roots', type=int, default=40)
    d.add_argument('--base', type=int, default=1455777415631152 + 2*10**6)
    c = sub.add_parser('check'); c.add_argument('--fixture', required=True)
    a = ap.parse_args()
    import torch
    torch.set_num_threads(1)
    from bot.players.runtime import Runtime
    rt = Runtime()
    if a.cmd == 'dump':
        dump(rt, a.out, a.roots, a.base)
    else:
        raise SystemExit(0 if check(rt, a.fixture) else 1)


if __name__ == '__main__':
    main()
