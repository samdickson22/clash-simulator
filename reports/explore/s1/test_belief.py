import copy
from types import SimpleNamespace
import numpy as np
import pytest
from belief import Belief,FrozenBelief
from derived_public_state import PublicEvent

PRIOR={'decks':[{'cards':list('ABCDEFGH'),'frequency':2}, {'cards':list('ABCDEFGI'),'frequency':3}]}
COSTS=dict.fromkeys('ABCDEFGHI',3)

def equal(a,b):
    for key in ('states','weights','cumulative'):np.testing.assert_array_equal(getattr(a,key),getattr(b,key))
    for key in ('tick','refill','queue_len','elixir','events'):assert getattr(a,key)==getattr(b,key)
    assert a.derived()==b.derived()
    ra=np.random.default_rng(5);rb=np.random.default_rng(5)
    assert [a.sample(ra) for _ in range(20)]==[b.sample(rb) for _ in range(20)]
    assert ra.bit_generator.state==rb.bit_generator.state


def test_bounded_update_exact_across_events_refills_and_samples():
    a=FrozenBelief(PRIOR,COSTS);b=Belief(PRIOR,COSTS);b.block_rows=17
    events=[]
    for tick,event in [(100,PublicEvent(100,'card','A')),(121,PublicEvent(121,'card','B')),(145,PublicEvent(145,'collector',amount=1)),(250,PublicEvent(250,'ability',amount=.2))]:
        events.append(event);a.update(tick,events);b.update(tick,events,deadline=1e6,clock=lambda:0.);equal(a,b)
    a.update(4900,events);b.update(4900,events,deadline=1e6,clock=lambda:0.);equal(a,b)


def test_cutoff_suspends_without_partial_commit_then_resumes_newer_events():
    a=FrozenBelief(PRIOR,COSTS);b=Belief(PRIOR,COSTS);b.block_rows=17
    before=copy.deepcopy(b.__dict__);clock=SimpleNamespace(now=0.)
    def tick_clock():clock.now+=.001;return clock.now
    events=[PublicEvent(1,'card','A')]
    with pytest.raises(TimeoutError):b.update(1,events,deadline=.02,clock=tick_clock)
    np.testing.assert_array_equal(b.states,before['states']);assert b.events==[] and b.tick==0
    assert b._pending is not None
    events.append(PublicEvent(25,'card','B'))
    b.update(40,events,deadline=1e6,clock=lambda:0.);a.update(40,events);equal(a,b)


def test_no_deadline_discards_private_progress_and_matches_frozen():
    a=FrozenBelief(PRIOR,COSTS);b=Belief(PRIOR,COSTS)
    events=[PublicEvent(1,'card','A')]
    with pytest.raises(TimeoutError):b.update(1,events,deadline=0.,clock=lambda:0.)
    b.update(30,events);a.update(30,events);equal(a,b)


def test_late_sample_does_not_consume_rng_or_publish_partial_derived():
    b=Belief(PRIOR,COSTS);b._derived=None;rng=np.random.default_rng(5);before=copy.deepcopy(rng.bit_generator.state)
    with pytest.raises(TimeoutError):b.sample(rng,deadline=0.,clock=lambda:0.)
    assert rng.bit_generator.state==before and b._derived is None
