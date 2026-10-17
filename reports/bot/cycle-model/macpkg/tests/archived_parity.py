"""Deterministic default-off parity on ARCHIVED live battles (cycle-model owner; fleet only, never on the Mac).

    TREE=<pkg tree> source .../guardfix/cycpkg-env.sh; python archived_parity.py RUN NAME OUT.json

Adapted from the translator owner's guardfix/shadow.py: every archived battle of RUN is replayed through the
translator + LiveSession of the tree on PYTHONPATH (bot.live.audit_plays.replay_battle, loaded by file path from the
main checkout so the tree under test stays the only `bot` package). At every poll the player NAME (a deterministic
twin: no wall deadline, fixed seeds) decides on the view; the replay itself follows the logged submissions, so every
arm sees the same views iff the translator emits the same views. Output: per-battle list of (tick, can_act, action,
wait_ticks), its sha256, errors, translator stats, belief cycle_stats. Default-off parity = identical sha256 for the
deployed tree and the package tree with BOT_CYCLE_MODEL unset.
"""
import hashlib
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

run, name, out_path = sys.argv[1:4]
spec = importlib.util.spec_from_file_location(
    'audit_plays_main', '/mpac/sdicks02/repos/clasher-bot-cycle/bot/live/audit_plays.py')
A = importlib.util.module_from_spec(spec)
spec.loader.exec_module(A)
from bot.live import translate as T          # noqa: E402  (the tree under test)
from bot.live.player import make_live_player  # noqa: E402
from bot.players.runtime import Runtime       # noqa: E402

rt = Runtime()
# harness only (as guardfix/shadow.py): the replay's base LiveSession skips a few polls the live SyncSession serves; let
# the 5-tick standalone gate resume after a gap instead of raising forever. Identical in every arm; search untouched.
from imitation.evaluation.standalone import StandalonePlayer as _SP  # noqa: E402
GAPS = [0]
_od = _SP.decide


def _decide(self, tick, *a, **k):
    if self.last_tick is not None and tick - self.last_tick != 5:
        GAPS[0] += 1
        self.last_tick = tick - 5
    return _od(self, tick, *a, **k)


_SP.decide = _decide
real = make_live_player(rt, name)
ACT, C, SESS = [], Counter(), []
OS = T.LiveSession.__init__


def init(self, *a, **k):
    OS(self, *a, **k)
    SESS.append(self)


T.LiveSession.__init__ = init


class Shadow(A.ReplayPlayer):
    def start(self, ctx):
        real.start(ctx)
        return super().start(ctx)

    def act(self, view):
        try:
            d = real.act(view)
            ACT.append((int(view.tick), bool(view.can_act), int(d.action), int(d.wait_ticks)))
            C['ok'] += 1
        except BaseException as ex:
            if isinstance(ex, (KeyboardInterrupt, SystemExit)):
                raise
            ACT.append((int(view.tick), bool(view.can_act), 'error', f'{type(ex).__name__}: {ex!s:.120}'))
            C['error'] += 1
        return super().act(view)


A.ReplayPlayer = Shadow
d = A.RUNS_ROOT / run
cfg = json.loads((d / 'session-config.json').read_text())
import inspect  # noqa: E402
known = set(inspect.signature(OS).parameters)
cfg = dict(cfg, session={k: v for k, v in cfg.get('session', {}).items() if k in known})
recs, ev, dec = A.jsonl(d / 'perception.jsonl'), A.jsonl(d / 'events.jsonl', optional=True), A.jsonl(d / 'decisions.jsonl', optional=True)
battles = []
for anchor, rows in A.battles(recs, ev):
    ACT.clear()
    r = A.replay_battle(rt, cfg, rows, ev, dec, anchor, None, None)
    bel = getattr(getattr(real, 'p', None), 'belief', None)
    battles.append(dict(polls=len(ACT), actions_sha256=hashlib.sha256(json.dumps(ACT).encode()).hexdigest(),
                        decisions=sum(1 for a in ACT if a[1]), errors_player=sum(1 for a in ACT if a[2] == 'error'),
                        errors_replay=len(r['errors']),
                        translator_stats={k: v for k, v in r['translator_stats'].items() if 'cycle' in k},
                        belief=type(bel).__name__ if bel is not None else None,
                        cycle_stats=getattr(bel, 'cycle_stats', None), actions=list(ACT)))
Path(out_path).write_text(json.dumps(dict(run=run, player=name, counts=dict(C), gate_gaps=GAPS[0], battles=battles), default=str))
print(json.dumps(dict(run=run, battles=[{k: v for k, v in b.items() if k != 'actions'} for b in battles]), default=str))
