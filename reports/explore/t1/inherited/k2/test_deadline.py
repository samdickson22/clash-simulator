from types import SimpleNamespace
from planner import anytime, STYLES
import pytest

class Clock:
    now=0.
    def __call__(self): return self.now

def core():
    return SimpleNamespace(config=SimpleNamespace(horizon=160), info=SimpleNamespace(packet=SimpleNamespace(observation=SimpleNamespace(global_features=[0]*5+[.5]))))

def setup(cost=.01, values=None):
    c=Clock(); calls=[]
    def evaluate(a,s,h,r,root):
        calls.append((a,s,h));c.now+=cost
        return (values or {}).get((a,s),a/10000)
    return c,calls,evaluate


def test_zero_budget_fallback():
    c=core();clock,calls,evaluate=setup()
    assert anytime(c,None,0,[1,2304,2400,2401],0.,7,clock=clock,evaluate=evaluate)==7
    assert calls==[] and c.deadline_stats['fallback']

def test_complete_wait_survives_late_timed_wait():
    c=core();clock,calls,evaluate=setup(.05)
    assert anytime(c,None,0,[1,2304,2400,2401,2402],.2,7,clock=clock,evaluate=evaluate)==2304
    assert c.last['scores'][1]==c.last['scores'][2]
    assert c.last['scores'][0] is None and c.last['scores'][3:] == [None,None]
    assert not c.deadline_stats['fallback'] and len(calls)==4

def test_waits_before_scan_before_refinement():
    c=core();clock,calls,evaluate=setup(.001)
    anytime(c,None,0,list(range(12))+[2304,2400,2401,2402],None,7,clock=clock,evaluate=evaluate)
    assert [a for a,s,h in calls[:9]]==[2304]*3+[2401]*3+[2402]*3
    assert [a for a,s,h in calls[9:21]]==list(range(12))
    assert all(s=='balanced' for a,s,h in calls[9:21])
    assert sum(a==2400 for a,s,h in calls)==0
    assert c.last['candidates']==list(range(4,12))+[2304,2400,2401,2402]

def test_incomplete_scan_does_not_admit_play():
    c=core();clock,calls,evaluate=setup(.01)
    anytime(c,None,0,[1,2,2304,2400],.045,7,clock=clock,evaluate=evaluate)
    assert c.last['scores'][:2]==[None,None] and c.deadline_stats['completed']==2

def test_incomplete_refinement_is_discarded():
    c=core();values={(a,s):10. for a in (1,2) for s in STYLES}
    clock,calls,evaluate=setup(.01,values)
    assert anytime(c,None,0,[1,2,2304,2400],.075,7,clock=clock,evaluate=evaluate)==1
    assert c.last['scores'][0]==10. and c.last['scores'][1] is None

def test_exact_deadline_excluded():
    c=core();clock,calls,evaluate=setup(.1)
    assert anytime(c,None,0,[2304,2400],.3,9,clock=clock,evaluate=evaluate)==9
    assert c.deadline_stats['completed']==0

def test_h80_recomputes_balanced_at160():
    c=core();clock,calls,evaluate=setup(.001)
    anytime(c,None,0,[1,2304,2400],None,7,coarse_horizon=80,clock=clock,evaluate=evaluate)
    assert calls==[(2304,s,160) for s in STYLES]+[(1,'balanced',80)]+[(1,s,160) for s in STYLES]

def test_epsilon_tie_uses_original_order():
    c=core();clock,calls,evaluate=setup(.001,{(a,s):5. for a in range(12) for s in STYLES})
    assert anytime(c,None,0,list(range(12))+[2304,2400],None,7,clock=clock,evaluate=evaluate)==0
    assert c.last['candidates']==list(range(8))+[2304,2400]

def test_thread_scores_and_actions_identical():
    records=[]
    for threads in (1,2,4):
        c=core()
        def evaluate(a,s,h,r,root): return a/10000
        action=anytime(c,None,0,list(range(12))+[2304,2400,2401,2402],None,7,threads=threads,evaluate=evaluate)
        records.append((action,c.last))
    assert records[0]==records[1]==records[2]

def test_native_timeout_discards_root():
    c=core()
    def evaluate(a,s,h,r,root): raise TimeoutError()
    assert anytime(c,None,0,[1,2304,2400],.2,9,clock=lambda:0.,evaluate=evaluate)==9

def test_hooks_preserve_eligibility_and_expand_refinement():
    c=core();clock,calls,evaluate=setup(.001)
    anytime(c,None,0,list(range(12))+[2304,2400],None,7,clock=clock,evaluate=evaluate,coarse_order=(0,11,0),refine_proposals=(0,999))
    assert [a for a,s,h in calls[3:15]]==[0,11]+list(range(1,11))
    assert c.last['candidates']==[0]+list(range(4,12))+[2304,2400]

@pytest.mark.parametrize("threads", [2,4])
def test_threads_retain_complete_sibling_on_timeout(threads):
    c=core()
    def evaluate(a,s,h,r,root):
        if a==2401: raise TimeoutError()
        return 1.
    action=anytime(c,None,0,[1,2304,2400,2401,2402],.2,7,threads=threads,clock=lambda:0.,evaluate=evaluate)
    assert action==2402 and c.last['scores'][3] is None and c.last['scores'][4] is not None


@pytest.mark.parametrize("threads", [2,4])
def test_collector_late_return_never_drains_or_changes_scores(threads, monkeypatch):
    import planner
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    started, release = Event(), Event()
    clock = Clock(); c = core()
    pool = ThreadPoolExecutor(max_workers=threads)
    def evaluate(a,s,h,r,root):
        started.set()
        release.wait(2)
        return 999.
    def late_wait(active, **kw):
        assert started.wait(1)
        assert kw['timeout'] == .2
        clock.now = .21  # Inject delayed collector wakeup past cutoff.
        return set(), set(active)
    monkeypatch.setattr(planner, 'wait', late_wait)
    try:
        assert anytime(c,None,0,[1,2304,2400],.2,7,threads=threads,
                       clock=clock,evaluate=evaluate,pool=pool)==7
        assert not release.is_set() and c.deadline_stats['completed']==0
        before = c.last.copy()
    finally:
        release.set();pool.shutdown(wait=True)
    assert c.last == before and c.last['scores']==[None]*3


@pytest.mark.parametrize("threads", [2,4])
def test_reused_pool_does_not_admit_previous_late_scores(threads, monkeypatch):
    import planner
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    started, release = Event(), Event(); clock=Clock(); c=core()
    pool=ThreadPoolExecutor(max_workers=threads)
    def evaluate(a,s,h,r,root):
        started.set();release.wait(2);return 999.
    real_wait=planner.wait
    def expire(active, **kw):
        assert started.wait(1);clock.now=.2;return set(),set(active)
    monkeypatch.setattr(planner,'wait',expire)
    try:
        assert anytime(c,None,0,[1,2304,2400],.2,7,threads=threads,clock=clock,evaluate=evaluate,pool=pool)==7
        release.set();monkeypatch.setattr(planner,'wait',real_wait)
        assert anytime(c,None,0,[1,2304,2400],None,7,threads=threads,
                       evaluate=lambda a,*args: 2. if a<2304 else 1.,pool=pool)==1
        assert c.last['scores'][0]==2. and all(x<3 for x in c.last['scores'])
    finally:
        release.set();pool.shutdown(wait=True)


def test_late_style_stops_before_next_style():
    c=core();clock,calls,evaluate=setup(.201)
    assert anytime(c,None,0,[2304,2400],.2,7,clock=clock,evaluate=evaluate)==7
    assert len(calls)==1 and c.deadline_stats['completed']==0


@pytest.mark.parametrize("threads", [2,4])
def test_completed_before_cutoff_is_kept_when_collection_is_late(threads, monkeypatch):
    import planner
    from concurrent.futures import Future
    class Pool:
        def submit(self, job, *args):
            f=Future();f.set_result(job(*args));return f
    clock=Clock();c=core()
    def late(active,**kw):
        clock.now=.21
        return set(),set(active)
    monkeypatch.setattr(planner,'wait',late)
    assert anytime(c,None,0,[2304,2400],.2,7,threads=threads,clock=clock,
                   evaluate=lambda *args:1.,pool=Pool())==2304
    assert c.deadline_stats['completed']==2 and c.last['scores'][0]==c.last['scores'][1]
