"""Injected clocks qualify defaults, eligibility, and inference accounting."""
from types import SimpleNamespace
from unittest.mock import patch
from sdefault import select_default,poll_before_search
from planner import anytime,STYLES

def test_pre_scan_complete_wait_uses_declared_default():
    for source,default in [('v1_polled',2),('student_argmax',1),('student_argmax',2304)]:
        clock=SimpleNamespace(now=0.)
        core=SimpleNamespace(config=SimpleNamespace(horizon=160),info=SimpleNamespace(packet=SimpleNamespace(observation=SimpleNamespace(global_features=[0]*5+[.5]))))
        def evaluate(a,s,h,remaining,root):
            clock.now+=.01
            return 10. if a<2304 else 0.
        action=anytime(core,None,0,[1,2,2304,2400],.045,default,clock=lambda:clock.now,evaluate=evaluate)
        assert core.deadline_stats['hit'] and core.deadline_stats['completed']==2
        assert select_default(core,action,default,source,.045)==default
        assert core.deadline_stats['default_used']

def test_complete_refined_play_keeps_frozen_best_score():
    for source,default in [('v1_polled',2),('student_argmax',2)]:
        clock=SimpleNamespace(now=0.)
        core=SimpleNamespace(config=SimpleNamespace(horizon=160),info=SimpleNamespace(packet=SimpleNamespace(observation=SimpleNamespace(global_features=[0]*5+[.5]))))
        def evaluate(a,s,h,remaining,root):
            clock.now+=.01
            return 10. if a<2304 else 0.
        action=anytime(core,None,0,[1,2,2304,2400],.075,default,clock=lambda:clock.now,evaluate=evaluate)
        assert action==1 and core.deadline_stats['hit']
        assert select_default(core,action,default,source,.075)==1
        assert not core.deadline_stats['default_used'] and core.deadline_stats['complete_play_scores']==1

def test_complete_play_keeps_best_wait_too():
    core=SimpleNamespace(last={'candidates':[1,2304],'scores':[-1.,2.]},deadline_stats={'hit':True},selected_wait_ticks=10)
    assert select_default(core,2304,1,'student_argmax',.1)==2304
    assert not core.deadline_stats['default_used'] and core.selected_wait_ticks==10

def test_no_deadline_and_no_cutoff_do_not_override():
    core=SimpleNamespace(last={'candidates':[1,2304],'scores':[None,2.]},deadline_stats={'hit':False},selected_wait_ticks=10)
    assert select_default(core,2304,1,'student_argmax',None)==2304
    assert select_default(core,2304,1,'student_argmax',.1)==2304

def test_student_inference_precedes_v1_and_consumes_absolute_cutoff():
    clock=SimpleNamespace(now=0.)
    order=[];latencies=[];defaults={};core=SimpleNamespace()
    owner=SimpleNamespace(actor=0,student_tracker=SimpleNamespace(update=lambda *_:{}),
        player=SimpleNamespace(mask_builder=SimpleNamespace(build=lambda _:[True]*2306)))
    def infer(*args):
        order.append('student');clock.now+=.21
        return 7,(7,3)
    def poll(*args):
        order.append('v1');return 3
    wall0=clock.now;cutoff=wall0+.2-.008
    with patch('sdefault.student_choice',side_effect=infer),patch('clasher.rl.public_action_mask.PublicActionMaskInput.from_confidence_observation',return_value=None):
        action=poll_before_search(owner,90,None,[],object(),core,defaults,poll,latencies,lambda:clock.now)
    assert order==['student','v1'] and action==7 and clock.now>=cutoff
    assert latencies==[.21] and core.coarse_order==(7,3) and core.refine_proposals==(7,3)
    # This is the frozen K runner's pre-scoring cutoff branch, using returned fallback.
    assert action==defaults[0] and cutoff==.192

def test_control_pre_scan_uses_v1_poll():
    owner=SimpleNamespace(actor=0);defaults={}
    assert poll_before_search(owner,90,None,[],None,SimpleNamespace(),defaults,lambda *_:9,[],lambda:0.)==9
    assert defaults[0]==9

def test_ability_default_is_wait():
    owner=SimpleNamespace(actor=0);defaults={}
    assert poll_before_search(owner,90,None,[],None,SimpleNamespace(),defaults,lambda *_:2305,[],lambda:0.)==2304
