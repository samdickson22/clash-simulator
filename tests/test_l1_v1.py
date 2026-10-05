"""Timing, ownership of observations and absence handling for L1 v1."""
from dataclasses import replace
from pathlib import Path
import threading

import numpy as np
import pytest

from clasher.rl.live_inference_contract import PublicVisionFrame, PublicPlayEvent, VisionEntity
from clasher.vision.l1_temporal import DeploymentTracker


def frame(t,entities=(),events=()):
    return PublicVisionFrame('episode',str(t),t,179.,1.,5.,1.,
        ('Knight','Giant','Zap','Archers'),(1.,)*4,'Skeletons',1.,tuple(entities),tuple(events))


def test_tracking_survives_one_missing_frame_without_second_play():
    t=DeploymentTracker();t.update(frame(0))
    e=VisionEntity('ignored','Knight','troop',0,3.,12.,.9)
    born=t.update(frame(100,[e]));assert len(born.play_events)==1
    t.update(frame(200));back=t.update(frame(300,[replace(e,y_tiles=12.3)]))
    assert not back.play_events
    assert back.entities[0].track_id==born.entities[0].track_id


def test_initial_population_is_not_relabelled_as_deployments():
    e=VisionEntity('ignored','Knight','troop',0,3.,12.,.9)
    assert not DeploymentTracker().update(frame(100,[e])).play_events


def test_hud_change_requires_previous_next_card_and_leaves_location_unknown():
    tracker=DeploymentTracker();tracker.update(frame(0))
    changed=replace(frame(100),own_hand=('Skeletons','Giant','Zap','Archers'),own_next_card='HogRider')
    assert not tracker.update(changed).play_events
    out=tracker.update(replace(changed,timestamp_ms=300,frame_id='300'))
    assert len(out.play_events)==1
    assert out.play_events[0].card=='Knight'
    assert out.play_events[0].x_tiles is None
    tracker=DeploymentTracker();tracker.update(frame(0))
    assert not tracker.update(replace(changed,own_hand=('Tesla','Giant','Zap','Archers'))).play_events


def test_event_window_is_causal_and_missing_placement_stays_in_denominator(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]/'scripts'))
    from evaluate_l1_v1 import timed_events
    expected=[dict(episode_id='episode',tick=10,player_id=0,card='Knight',x_tiles=3,y_tiles=12)]
    e=PublicPlayEvent('e',0,'Knight',.9)
    for t in (499,1001):
        assert timed_events([frame(t,events=[e])],expected)['matched_within_500_ms']==0
    result=timed_events([frame(1000,events=[e])],expected)
    assert result['matched_within_500_ms']==1
    assert result['placement_within_one_detected']==0
    assert result['placement_readings']==0


def test_event_matching_is_one_to_one(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]/'scripts'))
    from evaluate_l1_v1 import timed_events
    expected=[dict(episode_id='episode',tick=10,player_id=0,card='Knight',x_tiles=3,y_tiles=12)]
    e=PublicPlayEvent('e',0,'Knight',.9,3.,12.)
    result=timed_events([frame(600,events=[e,replace(e,event_id='duplicate')])],expected)
    assert result['matched_within_500_ms']==1
    assert result['false_positive']==1


def test_empty_slot_refill_is_not_a_card_play():
    tracker=DeploymentTracker()
    tracker.update(replace(frame(0),own_hand=('empty','Giant','Zap','Archers')))
    changed=replace(frame(100),own_hand=('Skeletons','Giant','Zap','Archers'))
    assert not tracker.update(changed).play_events
    assert not tracker.update(replace(changed,timestamp_ms=300,frame_id='300')).play_events


def test_stream_timestamp_barrier_rejects_stale_decodes():
    from clasher.vision.l1_stream import ScreenStream,ScreenFrame
    stream=ScreenStream.__new__(ScreenStream)
    stream.condition=threading.Condition();stream.stop=threading.Event();stream.error=None
    stream.latest=ScreenFrame(7,10.,np.zeros((2,2,3),np.uint8))
    with pytest.raises(TimeoutError):stream.read(after_time=11.,timeout=.001)
    assert stream.read(after_sequence=6,after_time=10.) is stream.latest


def test_validation_metrics_match_cpu_reference_and_restore_mps(tmp_path, monkeypatch):
    import socket
    from types import SimpleNamespace
    import torch
    if not torch.backends.mps.is_available():pytest.skip('MPS boundary check')
    from clasher.vision.l1_offline import offline_ml
    monkeypatch.setattr(socket.socket,'connect',socket.socket.connect)
    offline_ml(tmp_path/'ultralytics')
    from clasher.vision.l1_training import CompleteValidation
    from ultralytics.models.yolo.detect.val import DetectionValidator
    batch=dict(batch_idx=torch.tensor([0.,1.]),cls=torch.tensor([[0.],[1.]]),
               bboxes=torch.tensor([[.5,.5,.1,.1],[.25,.25,.1,.1]]),
               img=torch.zeros((2,3,640,640),dtype=torch.uint8),ori_shape=[(640,640)]*2,
               ratio_pad=[((1.,1.),(0.,0.))]*2,im_file=['a.jpg','b.jpg'])
    predictions=[torch.tensor([[288.,288.,352.,352.,.9,0.]]),
                 torch.tensor([[128.,128.,192.,192.,.8,1.],[0.,0.,20.,20.,.5,0.]])]
    validators=[]
    for cls,device in [(DetectionValidator,'cpu'),(CompleteValidation,'mps')]:
        v=cls.__new__(cls);v.device=torch.device(device);v.iouv=torch.linspace(.5,.95,10,device=device)
        v.niou=10;v.seen=0;v.stats={key:[] for key in ('tp','conf','pred_cls','target_cls')}
        v.args=SimpleNamespace(single_cls=False,plots=False,save_json=False,save_txt=False)
        data={key:value.to(device) if isinstance(value,torch.Tensor) else value for key,value in batch.items()}
        v.update_metrics([p.clone() for p in predictions],data)
        assert v.device==torch.device(device)
        validators.append(v)
    assert validators[1].seen==2
    for key in validators[0].stats:
        for a,b in zip(validators[0].stats[key],validators[1].stats[key]):
            assert b.device.type=='cpu'
            assert torch.equal(a,b)
