"""125 frozen public histories: exact posterior arrays/ledger and RNG, deadline ON/OFF."""
import argparse,copy,hashlib,json,pickle,subprocess,time
from pathlib import Path
import numpy as np
import run

def main():
    p=argparse.ArgumentParser();p.add_argument('--corpus',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();run.initialize()
    from belief import Belief,FrozenBelief
    rows=pickle.loads((a.corpus/'states-ready.pkl').read_bytes());records=[]
    for row in rows:
        original=FrozenBelief(run.PRIOR,run.R.costs);info=row['info'];original.update(info.tick,info.events)
        for deadline in (None,float('inf')):
            changed=Belief(run.PRIOR,run.R.costs);changed.update(info.tick,info.events,deadline=deadline)
            for key in ('states','weights','cumulative'):np.testing.assert_array_equal(getattr(original,key),getattr(changed,key))
            for key in ('tick','refill','queue_len','elixir','events'):assert getattr(original,key)==getattr(changed,key)
            assert original.derived()==changed.derived()
            first=np.random.default_rng(row['seed']);second=np.random.default_rng(row['seed'])
            assert [original.sample(first) for _ in range(16)]==[changed.sample(second,deadline=deadline) for _ in range(16)]
            assert first.bit_generator.state==second.bit_generator.state
            records.append(dict(id=row['id'],deadline_on=deadline is not None,states=len(original.states)))
        if len(records)%50==0:print(json.dumps(dict(histories=len(records)//2,variants=len(records))),flush=True)
    assert len(rows)==125
    a.out.write_text(json.dumps(dict(utc=subprocess.check_output(['date','-u','+%Y-%m-%dT%H:%M:%SZ'],text=True).strip(),histories=125,exact_deadline_off=125,exact_deadline_on=125,posterior_ledger_samples_rng_exact=True,records=records),indent=2)+'\n')
if __name__=='__main__':main()
