"""W integration: common-root admission, timed-wait lifetime and default gating."""
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
import time

import numpy as np
import pytest
from clasher.live.decision import RustPlanner
from clasher.rl.c56_rollout_planner import C56SearchConfig


def snapshot(tick=100, episode='one'):
    return SimpleNamespace(tick=tick, episode=episode, pending=None, public=object(),
                           own=dict(hand=['Knight']*4,cycle=[],refill=0,elixir=2),roots=(1,2,3,4))


def planner(enabled=True):
    p=object.__new__(RustPlanner)
    packet=SimpleNamespace(observation=SimpleNamespace(terminal=False,global_features=np.zeros(18)))
    packet.observation.global_features[5]=.2
    p.wait_screen8=enabled;p.wait_until_tick=0;p.wait_episode=None
    p.delay_aware=True;p.delay_ticks=27;p.backend='native';p.timing=dict(p50_ms=1,p99_ms=2)
    p.packets=SimpleNamespace(build=lambda public,tick:(packet,{}))
    p.model_hypothesis=lambda packet:packet;p.hook=None;p.rng=None
    candidates=[0,2304,2400,2401,2402] if enabled else [0,2304]
    p.cores=[SimpleNamespace(candidates=lambda packet:(candidates,None)) for _ in range(4)]
    p.resources=SimpleNamespace(root=lambda *args:object())
    p.pool=ThreadPoolExecutor(max_workers=4)
    p.score=lambda *args:[0.,.1,.1,.2,.3] if enabled else [1.,0.]
    return p


def test_default_off_requires_explicit_boolean():
    assert C56SearchConfig().wait_screen8 is False
    for invalid in ('yes',1,None):
        with pytest.raises(ValueError):C56SearchConfig(wait_screen8=invalid)


def test_wait_suppression_covers_events_until_tick_and_resets_between_episodes():
    p=planner()
    try:
        action,meta=p.decide(snapshot(),time.monotonic()+10)
        assert action==2402 and meta['selected_wait_ticks']==40 and meta['wait_until_tick']==140
        p.packets.build=lambda *args:pytest.fail('active WAIT must precede packet/search work')
        action,meta=p.decide(snapshot(139),time.monotonic()+10)
        assert action==2304 and meta['reason']=='timed_wait'
        p.packets.build=lambda *args:(SimpleNamespace(observation=SimpleNamespace(terminal=True)),{})
        assert p.decide(snapshot(140),time.monotonic()+10)[1]['reason']=='public_match_result'
        assert p.decide(snapshot(90,'two'),time.monotonic()+10)[1]['reason']=='public_match_result'
        assert p.wait_until_tick==0
    finally:p.close()


def test_four_roots_require_full_scores_on_every_root():
    p=planner()
    try:
        calls=iter([[.8,.1,.1,.2,.3],[None,.1,.1,.2,.3],[.8,.1,.1,.2,.3],[.8,.1,.1,.2,.3]])
        p.score=lambda *args:next(calls)
        action,meta=p.decide(snapshot(),time.monotonic()+10)
        assert action==2402 and meta['completed']==4
        p.wait_until_tick=0
        p.score=lambda *args:[None]*5
        action,meta=p.decide(snapshot(150),time.monotonic()+10)
        assert action==2304 and meta['completed']==0 and meta['selected_wait_ticks']==0
    finally:p.close()


def test_flag_off_does_not_enter_wait_suppression():
    p=planner(False)
    try:
        p.wait_episode='one';p.wait_until_tick=200
        action,meta=p.decide(snapshot(),time.monotonic()+10)
        assert action==0 and 'wait_until_tick' not in meta
    finally:p.close()
