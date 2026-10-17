import math
from types import SimpleNamespace

from bot.search import priortb


class FakeFast:
    def __init__(self):
        self.cached = SimpleNamespace(sample=lambda packet, d1, generator=None: 2304, model=None, costs=None)
        self.poller = SimpleNamespace(poll=lambda tick, packet, events: 2304)


def setup(monkeypatch, table, prev=None):
    """table: tick -> ({play: log pi}, log pi wait) or None."""
    monkeypatch.setattr(priortb.FastPrior, 'logpi', lambda self, tick: table.get(tick))
    core = SimpleNamespace(info=SimpleNamespace(tick=10), reserve=prev)
    closed = []
    live = SimpleNamespace(fast=FakeFast(), name='x', close=lambda: closed.append(1))
    priortb.install(None, core, 0.01, live)
    return core, live, closed


def test_terms_waits_floor_and_missing(monkeypatch):
    table = {10: ({5: math.log(.5), 7: math.log(.1)}, math.log(.4))}
    core, live, _ = setup(monkeypatch, table, prev=lambda a, e: 1.0)
    pen = core.reserve
    assert abs(pen(5, 3.) - (1.0 - .01 * math.log(.5))) < 1e-12
    assert abs(pen(2304, 3.) - (1.0 - .01 * math.log(.4))) < 1e-12
    assert abs(pen(2401, 3.) - (1.0 - .01 * math.log(.4))) < 1e-12        # timed waits share the wait prior
    assert abs(pen(9, 3.) - (1.0 - .01 * math.log(priortb.FLOOR))) < 1e-12  # outside the prior's mask
    core.info.tick = 20                                                    # no poll at this tick: term 0
    assert pen(5, 3.) == 1.0
    c = core.prior_counts
    assert c['decisions'] == 2 and c['missing'] == 1
    assert c['top1_scored'] == 1 and c['top3_scored'] == 1


def test_idempotent_and_close_logs(monkeypatch, tmp_path):
    core, live, closed = setup(monkeypatch, {10: ({5: 0.}, -50.)})
    first = core.reserve
    priortb.install(None, core, 0.01, live)
    assert core.reserve is first
    monkeypatch.setenv('BOT_PRIORTB_LOG', str(tmp_path))
    core.reserve(5, 1.)
    live.close()
    assert closed == [1]
    lines = list(tmp_path.glob('*.jsonl'))[0].read_text().splitlines()
    assert len(lines) == 1 and '"decisions": 1' in lines[0]


def test_hooks_record_tick(monkeypatch):
    fast = FakeFast()
    p = priortb.FastPrior(fast)
    fast.poller.poll(15, 'pkt', [])
    assert p.tick == 15
    fast.cached.sample({'action_mask': None}, {'d1': 1})
    assert p.pending[0] == 15 and p.pending[2] == {'d1': 1}
    assert p.logpi(20) is None
