"""Board-noise injection: schedule determinism and the relabel on synthetic packets.
    PYTHONHASHSEED=0 .venv/bin/python -m pytest -q bot/livediag/test_board_noise.py"""
from dataclasses import dataclass, replace
from types import SimpleNamespace

import numpy as np

from bot.livediag import board_noise as bn


@dataclass(frozen=True)
class Obs:
    entity_ids: np.ndarray
    entity_features: np.ndarray
    entity_mask: np.ndarray


@dataclass(frozen=True)
class Packet:
    observation: Obs


def packet(rows):
    """rows: (token, own, x_tiles, y_tiles)"""
    n = 8
    ids = np.zeros(n, np.int64); f = np.zeros((n, 32), np.float32); m = np.zeros(n, bool)
    for i, (t, own, x, y) in enumerate(rows):
        ids[i] = t; m[i] = True
        f[i, 0], f[i, 1] = x / 18, y / 32
        f[i, 2], f[i, 3] = (1., 0.) if own else (0., 1.)
        f[i, 4] = 1.                                   # Troop
    return Packet(Obs(ids, f, m))


def test_schedule_deterministic_and_paired():
    a = bn.schedule('v11', 12345, 0)
    assert a == bn.schedule('v11', 12345, 0) and a != bn.schedule('v11', 12346, 0)
    assert bn.schedule('off', 1, 0) == []
    x3 = bn.schedule('v11x3', 12345, 0)
    assert len(x3) % 3 == 0 and len(x3) >= len(a) or len(a) == 0
    assert all(bn.START_TICK <= t < bn.END_TICK for t, _, _ in a)
    cards = {c for _, c, _ in bn.schedule('v11', 7, 1)}
    assert cards <= {'Bats', 'Valkyrie', 'Archers', 'MiniPekka', 'Giant'}


def test_relabel_and_tracking(monkeypatch):
    noise = bn.BoardNoise.__new__(bn.BoardNoise)
    noise.rt = SimpleNamespace(R=SimpleNamespace(costs={'Zap': 2.0}))
    noise.pending = [(100, 'Bats', 2)]
    noise.active, noise.shown, noise.last_tick = [], [], None
    noise.counts = dict(runs_scheduled=1, runs_applied=0, runs_dropped=0, flipped_unit_polls=0, phantom_polls=0,
                        phantom_near_plays=0, phantom_near_elixir=0.0)
    noise.upr = {'Bats': 1.305}
    noise.bodies = {'Bats': {7}}
    p = packet([(7, True, 5, 8), (7, True, 5.5, 8.5), (7, True, 12, 25), (9, False, 9, 20)])
    assert noise.step(p.observation, 95) == []                       # before the start
    rows = noise.step(p.observation, 100)
    assert sorted(rows) == [0] or sorted(rows) == [1]                # 1.305 -> 1 unit, our half, nearest our king
    q = bn.BoardNoise.relabel(p, rows)
    f = q.observation.entity_features
    assert f[rows[0], 2] == 0 and f[rows[0], 3] == 1 and p.observation.entity_features[rows[0], 2] == 1
    assert noise.step(p.observation, 100) == rows                    # same tick: same rows, no extra count
    assert noise.counts['flipped_unit_polls'] == 1
    assert len(noise.step(p.observation, 105)) == 1                  # second (last) poll of the run
    assert noise.step(p.observation, 110) == []                      # run over
    assert noise.counts['runs_applied'] == 1 and noise.counts['flipped_unit_polls'] == 2


def test_run_waits_then_drops():
    noise = bn.BoardNoise.__new__(bn.BoardNoise)
    noise.rt = None
    noise.pending = [(100, 'Giant', 3)]
    noise.active, noise.shown, noise.last_tick = [], [], None
    noise.counts = dict(runs_scheduled=1, runs_applied=0, runs_dropped=0, flipped_unit_polls=0, phantom_polls=0,
                        phantom_near_plays=0, phantom_near_elixir=0.0)
    noise.upr, noise.bodies = {}, {'Giant': {11}}
    p = packet([(9, False, 9, 20)])
    for t in range(100, 100 + bn.WAIT_TICKS + 10, 5):
        assert noise.step(p.observation, t) == []
    assert noise.counts['runs_dropped'] == 1 and not noise.active
