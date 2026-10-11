from types import SimpleNamespace
from planner import anytime,STYLES
import pytest

class Clock:
    now=0.
    def __call__(self):return self.now

def core():
    return SimpleNamespace(arm='W',config=SimpleNamespace(horizon=160),info=SimpleNamespace(packet=SimpleNamespace(observation=SimpleNamespace(global_features=[0]*5+[.5]))))

def setup(cost=.01,values=None):
    clock=Clock();calls=[]
    def evaluate(a,s,r):
        assert r>0;calls.append((a,s));clock.now+=cost
        return (values or {}).get((a,s),a/10000)
    return clock,calls,evaluate

def test_zero_budget():
    c=core();clock,calls,ev=setup()
    assert anytime(c,None,0,[1,2304,2400],0.,7,clock=clock,evaluate=ev)==7
    assert calls==[] and c.deadline_stats['fallback']

def test_coarse_before_every_complete_root():
    c=core();clock,calls,ev=setup()
    assert anytime(c,None,0,list(range(12))+[2304,2400],.05,7,clock=clock,evaluate=ev)==7
    assert all(s=='balanced' and a<2304 for a,s in calls)
    assert c.deadline_stats['completed']==0

def test_partial_refinement_never_admitted():
    c=core();clock,calls,ev=setup()
    assert anytime(c,None,0,[1,2,2304,2400],.04,7,clock=clock,evaluate=ev)==7
    assert c.deadline_stats['completed']==0

def test_complete_play_survives_later_cutoff():
    c=core();clock,calls,ev=setup()
    assert anytime(c,None,0,[1,2,2304,2400],.05,7,clock=clock,evaluate=ev)==1
    assert c.deadline_stats['completed']==1 and c.last['scores'][1] is None

def test_wait_alias_uses_full_wait_score():
    c=core();clock,calls,ev=setup()
    assert anytime(c,None,0,[2304,2400,2401],.04,7,clock=clock,evaluate=ev)==2304
    assert c.last['scores'][0]==c.last['scores'][1] and c.last['scores'][2] is None

def test_no_deadline_original_ties():
    c=core();clock,calls,ev=setup(.001,{(a,s):5. for a in range(12) for s in STYLES})
    assert anytime(c,None,0,list(range(12))+[2304,2400],None,7,clock=clock,evaluate=ev)==0
    assert c.last['candidates']==list(range(8))+[2304,2400]

def test_exact_cutoff_excludes_root():
    c=core();clock,calls,ev=setup(.1)
    assert anytime(c,None,0,[2304,2400],.3,7,clock=clock,evaluate=ev)==7
    assert c.deadline_stats['completed']==0

def test_native_timeout_does_not_mutate_admission():
    c=core()
    def ev(*args):raise TimeoutError()
    assert anytime(c,None,0,[1,2304,2400],.2,7,clock=lambda:0.,evaluate=ev)==7
    assert c.last['scores']==[None]*3
