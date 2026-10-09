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


def test_offline_default_on_keeps_explicit_off_and_requires_boolean():
    assert C56SearchConfig().wait_screen8 is True
    assert C56SearchConfig(wait_screen8=False).wait_screen8 is False
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


def test_native_selection_preserves_paths_and_checks_already_loaded_library(monkeypatch,tmp_path):
    import sys
    from clasher.rl.wait_screen8 import load_native
    native=SimpleNamespace(__file__=str(tmp_path/'clasher_core.abi3.so'),
                           NativeScripts=SimpleNamespace(score_wait_screen8=object()))
    monkeypatch.setitem(sys.modules,'clasher_core',native)
    original=sys.path[:]
    assert load_native(tmp_path) is native and sys.path==original
    different=tmp_path/'other';different.mkdir()
    with pytest.raises(ValueError,match='fresh process'):load_native(different)
    assert sys.path==original


def test_native_selection_rejects_a_library_without_the_extension(monkeypatch,tmp_path):
    import sys
    from clasher.rl.wait_screen8 import load_native
    native=SimpleNamespace(__file__=str(tmp_path/'clasher_core.abi3.so'),NativeScripts=object())
    monkeypatch.setitem(sys.modules,'clasher_core',native)
    with pytest.raises(ValueError,match='separately built'):load_native(tmp_path)


def test_live_opt_in_loads_native_before_resource_initialization(monkeypatch):
    from clasher.rl import wait_screen8
    class Selected(Exception):pass
    def select(directory):
        assert directory=='/versioned/native'
        raise Selected
    monkeypatch.setattr(wait_screen8,'load_native',select)
    with pytest.raises(Selected):
        RustPlanner(dict(wait_screen8=True,wait_screen8_native_dir='/versioned/native'))


def test_live_default_does_not_load_screen8_native(monkeypatch):
    from clasher.rl import wait_screen8
    from clasher.live import decision
    class ResourcesReached(Exception):pass
    monkeypatch.setattr(wait_screen8, 'load_native',
                        lambda *args:pytest.fail('live default must remain OFF'))
    def stop_at_resources(*args):raise ResourcesReached
    monkeypatch.setattr(decision, 'module', stop_at_resources)
    with pytest.raises(ResourcesReached):RustPlanner({})


def test_live_default_passes_explicit_off_to_every_core(monkeypatch):
    from clasher.live import decision, tower_model
    resources=SimpleNamespace(builder=object(), bots={}, native=object(), config={})
    packet=SimpleNamespace(PacketBuilder=lambda builder:object(),model_hypothesis=lambda p:p)
    def module(name,path):
        if name=='clasher_live_fair_player':return SimpleNamespace(Resources=lambda:resources)
        if name=='clasher_live_packet_builder':return packet
        return SimpleNamespace()
    monkeypatch.setattr(decision,'module',module)
    monkeypatch.setattr(tower_model,'tower_packet_builder',lambda cls,**kwargs:cls)
    monkeypatch.setattr(decision,'planner_timing',lambda config:('native',None,{},27))
    cores=[]
    def core(*args,**kwargs):
        cores.append(kwargs['config']);return SimpleNamespace()
    monkeypatch.setattr(decision,'delay_module',lambda:SimpleNamespace(DelayAwarePlanner=core))
    p=RustPlanner({})
    try:
        assert p.wait_screen8 is False and len(cores)==4
        assert all(c.wait_screen8 is False for c in cores)
    finally:p.close()
