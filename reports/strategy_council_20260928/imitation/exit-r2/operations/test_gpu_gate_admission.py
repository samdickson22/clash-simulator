"""Metadata-only route/quiet/attempt admission and duplicate launch tests."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import pytest
import stage1_gpu_guard as guard
import remote_gpu_gates as remote
import controller_gpu_gates as controller

def write(path,data):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(data))

def test_quiet_noncomment_exact_host(tmp_path):
    p=tmp_path/'quiet';p.write_text('#08\n127x108\n13 #08\n');assert not guard.quiet08(p)
    p.write_text('127x08 # coordinator reclaim\n');assert guard.quiet08(p)

def test_08_deadline_blocks_gpu_scoring(tmp_path,monkeypatch):
    monkeypatch.setattr(guard.socket,'gethostname',lambda:'127x08');monkeypatch.setattr(guard.os,'getpriority',lambda *_:19);monkeypatch.setattr(guard.os,'sched_getscheduler',lambda *_:5);monkeypatch.setattr(guard.time,'time',lambda:1791609300)
    with pytest.raises(InterruptedError):guard.guard(tmp_path,'X3')

def test_fit_stop_reclaim_blocks_08(tmp_path,monkeypatch):
    monkeypatch.setattr(guard.socket,'gethostname',lambda:'127x08');monkeypatch.setattr(guard.os,'getpriority',lambda *_:19);monkeypatch.setattr(guard.os,'sched_getscheduler',lambda *_:5);monkeypatch.setattr(guard.time,'time',lambda:1791609200);monkeypatch.setattr(guard,'quiet08',lambda:False);(tmp_path/'FIT.STOP').touch()
    with pytest.raises(InterruptedError):guard.guard(tmp_path,'X3')

def test_home01_before_x4_exit_does_not_request_g_stop(tmp_path,monkeypatch):
    monkeypatch.setattr(remote.socket,'gethostname',lambda:'127x01');monkeypatch.setattr(remote,'snapshot',lambda *_:{'ready':False});calls=[];monkeypatch.setitem(sys.modules,'evaluation_k_yield',SimpleNamespace(admission=lambda *_:calls.append(1)))
    assert not remote.route_admission(tmp_path)['admitted'];assert not calls

def test_home03_retains_k_gate(tmp_path,monkeypatch):
    monkeypatch.setattr(remote.socket,'gethostname',lambda:'127x03');calls=[];monkeypatch.setitem(sys.modules,'evaluation_k_yield',SimpleNamespace(admission=lambda *args:calls.append(args[1]) or False))
    assert not remote.route_admission(tmp_path)['admitted'];assert calls==[['stage2 route']]

def test_home01_after_clean_exit_still_requires_g_drain(tmp_path,monkeypatch):
    monkeypatch.setattr(remote.socket,'gethostname',lambda:'127x01');monkeypatch.setattr(remote,'snapshot',lambda *_:{'ready':True});monkeypatch.setitem(sys.modules,'evaluation_k_yield',SimpleNamespace(admission=lambda *_:False));assert not remote.route_admission(tmp_path)['admitted']

def test_active_scoring_never_relaunched(tmp_path,monkeypatch):
    write(tmp_path/'stage1-X1-attempt1.log.identity.json',{'pid':456});monkeypatch.setattr(remote,'group_alive',lambda *_:True)
    assert remote.attempt_state(tmp_path,1,'X1')['status']=='active'
    monkeypatch.setattr(remote,'verify_amendment',lambda *_:None);monkeypatch.setattr(remote,'load_experiment',lambda *_:{})
    with pytest.raises(AssertionError):remote.start(tmp_path,1,'X1',[])

def test_closed_scoring_requires_clean_meter(tmp_path,monkeypatch):
    write(tmp_path/'stage1-X1-attempt1.log.identity.json',{'pid':456});write(tmp_path/'offline/X1.json',{'survives':True});write(tmp_path/'offline/X1-meter-456.json',{'exit_code':1,'reason':'resource stop'});monkeypatch.setattr(remote,'group_alive',lambda *_:False)
    assert remote.attempt_state(tmp_path,1,'X1')['status']=='failed'

def test_done_scoring_carries_meter_and_metrics(tmp_path,monkeypatch):
    write(tmp_path/'stage1-X1-attempt1.log.identity.json',{'pid':456});write(tmp_path/'offline/X1.json',{'survives':False});write(tmp_path/'offline/X1-meter-456.json',{'exit_code':0,'reason':None});monkeypatch.setattr(remote,'group_alive',lambda *_:False)
    assert remote.attempt_state(tmp_path,1,'X1')['status']=='done'

def test_cross_home_stage2_duplicate_is_rejected(tmp_path,monkeypatch):
    monkeypatch.setattr(controller,'remote',lambda *_:{'status':'active','pid':1})
    with pytest.raises(AssertionError):controller.existing_stage2(tmp_path,'X1')

def test_adopts_existing_stage2_on_other_home(tmp_path,monkeypatch):
    monkeypatch.setattr(controller,'remote',lambda job,host,*_:{'status':'active','pid':1} if host=='127x03' else {'status':'not-started'})
    assert controller.existing_stage2(tmp_path,'X1')[0]=='127x03'

def test_home03_checkpoint_prepare_never_scp_same_metric(tmp_path,monkeypatch):
    monkeypatch.setattr(controller,'load_experiment',lambda *_:{'arms':{'X1':{'steps':4883}}});calls=[];monkeypatch.setattr(controller.subprocess,'run',lambda cmd,**_:calls.append(cmd))
    controller.stage2_prepare(tmp_path,'X1','127x03');assert all(c[0]!='scp' for c in calls)
