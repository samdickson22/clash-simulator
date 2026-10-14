"""Play one HEADLINE case in RoyaleSim (bot.players.royalesim_match) and save a RoyaleGym trace for RoyaleViser.

    ROYALEGYM_SRC=... CLASHER_BOT_RUNTIME=... python capture_rsim.py --index 164 --opponent rext-bc --out DIR

The match loop is unchanged; the RoyaleSim Battle it builds is wrapped so every multi-tick
advance runs as single ticks with a trace frame after each, and every command step is logged.
A RoyaleGym RustEngine supplies the header/arena/card table and the state decoder, pointed
at the match's own Battle. Writes DIR/rsim-case-<index>.msgpack (+ .json summary).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, '/mpac/sdicks02/repos/clasher-bot')


class RecordingBattle:
    def __init__(self, battle, client):
        self._b = battle
        self._client = client
        self.engine = None
        self.rec = None

    def __getattr__(self, name):
        return getattr(self._b, name)

    def reset(self, *, seed, decks, shuffle, start_tick, elixir_milli, tower_hp, spawns):
        out = self._b.reset(seed=seed, decks=decks, shuffle=shuffle, start_tick=start_tick,
                            elixir_milli=elixir_milli, tower_hp=tower_hp, spawns=spawns)
        import royalesim
        from royalegym.protocol import MatchSetup
        from royalegym.replay import ReplayRecorder
        from royalegym.rust_engine import RustEngine
        overrides = royalesim.client_arms(self._client) if self._client != '16.402' else {}
        # client_arms values are JSON-encoded ('"arm"'); RustEngine takes the bare arm name
        overrides = {k: json.loads(v) if isinstance(v, str) and v.startswith('"') else v for k, v in overrides.items()}
        try:
            eng = RustEngine(calibration_overrides=overrides)
        except Exception as ex:  # an override this wrapper reads itself: header/decoder only, so drop them
            print('RustEngine without overrides:', ex, file=sys.stderr)
            eng = RustEngine()
        eng._battle = self._b                    # decode/draw the match's own battle
        eng._reset_called = True
        eng._setup_cards = [(list(d), [0] * len(d)) for d in decks]
        self.engine = eng
        self.rec = ReplayRecorder(frame_every_tick=True)
        self.rec.begin(eng, seed, MatchSetup(decks=[list(d) for d in decks], shuffle=shuffle, start_tick=start_tick,
                                             elixir_milli=list(elixir_milli)))
        return out

    def step(self, commands, ticks):
        from royalegym.protocol import DeployCommand, DeployResult
        if ticks == 0 or commands:
            tick = self.engine.state().tick if commands else None
            rows = self._b.step(commands, ticks)
            if commands:
                cmds = [DeployCommand(*map(int, c)) for c in commands]
                res = [DeployResult(c.team, c.hand_slot, int(r[0]), self.engine._status(int(r[1])), int(r[2]),
                                    int(r[3]) if len(r) > 4 else c.x, int(r[4]) if len(r) > 4 else c.y)
                       for c, r in zip(cmds, rows)]
                self.rec.record_step(tick, ticks, cmds, res)
            if ticks:
                self.rec.record_frame(self.engine)
            return rows
        rows = []
        for _ in range(ticks):
            before = self.rec.trace.frames[-1].tick
            rows = self._b.step([], 1)
            self.rec.record_frame(self.engine)
            if self.rec.trace.frames[-1].tick == before:   # battle over: the engine stopped
                self.rec.trace.frames.pop()
                break
        return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--index', type=int, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--candidate', default='K4C-r16')
    ap.add_argument('--opponent', default='rext-bc')
    ap.add_argument('--client', default='15.535.29')
    a = ap.parse_args()
    import torch
    torch.set_num_threads(1)
    from bot.players.runtime import Runtime
    from bot.players.ours import x4s_setup
    from bot.eval.headline import make_player, HEADLINE_BASE
    rt = Runtime()
    src = os.environ['ROYALEGYM_SRC']
    sys.path.insert(0, str(Path(src).parent))
    import bot.players.royalesim_vocab as rv
    from bot.players.royalesim_match import play_match
    orig = rv.rsim_battle
    holder = {}

    def wrapped(client='15.535.29'):
        holder['b'] = RecordingBattle(orig(client), client)
        return holder['b']
    rv.rsim_battle = wrapped
    vocab = rv.load(rt)
    case = x4s_setup(rt, a.index, HEADLINE_BASE)
    seat = case['seat']
    players = {seat: make_player(rt, a.candidate), 1 - seat: make_player(rt, a.opponent)}
    t0 = time.time()
    res = play_match(rt, players, seed=case['seed'], decks=case['decks'], vocab=vocab, client=a.client)
    rb = holder['b']
    trace = rb.rec.end(rb.engine)
    from royalegym.replay import save_trace
    a.out.mkdir(parents=True, exist_ok=True)
    path = save_trace(trace, a.out / f'rsim-case-{a.index}.msgpack')
    summary = dict(index=a.index, seed=case['seed'], seat=seat, candidate=a.candidate, opponent=a.opponent,
                   winner=res['winner'], ticks=res['ticks'], crowns=res['crowns'], towers=res['towers'],
                   command_sha256=res['command_sha256'], frames=len(trace.frames), steps=len(trace.steps),
                   trace=str(path), wall_seconds=time.time() - t0)
    (a.out / f'rsim-case-{a.index}.json').write_text(json.dumps(summary, indent=1, default=str))
    print(json.dumps(summary, default=str))


if __name__ == '__main__':
    main()
