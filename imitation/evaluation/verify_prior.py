"""Full-array and RNG parity on actual recorded smoke event streams."""
import argparse
import hashlib
import json
from pathlib import Path
import time
import numpy as np
from .paths import setup
setup()
from derived_public_state import DerivedPublicState, PublicEvent
from .fast_prior import ExactFastPrior
from clasher.data import CardDataLoader


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--games',type=Path,required=True)
    ap.add_argument('--prior',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args();prior=json.loads(args.prior.read_text());loader=CardDataLoader()
    names={n for d in prior['decks'] for n in d['cards']}
    costs={n:float(loader.get_card(n).mana_cost) for n in names}
    records=[];total=0
    for path in sorted(args.games.glob('game-*.json'))[:8]:
        row=json.loads(path.read_text());seat=row['seat']
        original=DerivedPublicState(prior,costs);fast=ExactFastPrior(prior,costs)
        streams=[PublicEvent(e['tick'],e['kind'],e['name'],e['amount']) for e in row['public_events'] if e['seat']!=seat]
        # Check after every event and every subsequent refill boundary, including
        # multiple same-tick events. Whole-state comparisons preserve multiplicity.
        rng1=np.random.default_rng(779);rng2=np.random.default_rng(779)
        timings=[[],[]];checks=0;prefix=[]
        for event in streams:
            prefix.append(event)
            for obj,t in zip((original,fast),timings):
                start=time.perf_counter();obj.update(event.tick,prefix);t.append((time.perf_counter()-start)*1000)
            for key in ('states','weights','cumulative'):
                assert np.array_equal(getattr(original,key),getattr(fast,key)),(path,event.tick,key)
            assert original.elixir==fast.elixir and original.refill==fast.refill and original.queue_len==fast.queue_len
            assert original.derived()==fast.derived(),(path,event.tick,'derived')
            assert original.sample(rng1)==fast.sample(rng2),(path,event.tick,'sample')
            assert rng1.bit_generator.state==rng2.bit_generator.state
            checks+=1
        original.update(row['ticks'],streams);fast.update(row['ticks'],streams)
        assert np.array_equal(original.states,fast.states)
        assert original.derived()==fast.derived() and original.elixir==fast.elixir
        total+=checks
        records.append({'game':path.name,'checks':checks,'original_max_ms':max(timings[0]),
                        'fast_max_ms':max(timings[1]),'byte_exact':True})
        print(json.dumps(records[-1]),flush=True)
    assert len(records)==8
    # Short targeted stream covers explicit grants/ability debit without needing
    # hidden simulator state or manipulating any engine source.
    a=DerivedPublicState(prior,costs);b=ExactFastPrior(prior,costs)
    events=[PublicEvent(90,'collector','',1.),PublicEvent(95,'ability','',1.)]
    for tick in (95,2401,4801):
        a.update(tick,events);b.update(tick,events)
        assert a.elixir==b.elixir and a.refill==b.refill and np.array_equal(a.states,b.states)
    with open(args.output,'x') as f:json.dump({'complete':True,'byte_exact':True,'games':records,'events':total,
        'source_sha256':hashlib.sha256(Path(__file__).with_name('fast_prior.py').read_bytes()).hexdigest()},f,indent=2)


if __name__=='__main__':main()
