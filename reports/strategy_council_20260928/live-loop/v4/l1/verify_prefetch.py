"""Compare new serial plans and parallel work to the historical augmentation."""
import argparse,json,random
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import cv2
import torch
from data_v4 import Windows
from reference_sample import original_sample


def equal(a,b):
    for k,v in a.items():
        if isinstance(v,dict):
            for key,x in v.items():assert torch.equal(x,b[k][key]),(k,key)
        else:assert torch.equal(v,b[k]),k


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--split',type=Path,required=True)
    p.add_argument('--cache',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    torch.set_num_threads(1);cv2.setNumThreads(1);a.output.mkdir(parents=True,exist_ok=False)
    data=Windows(a.source,a.split,a.output/'data',max_matches=1,pixel_cache=a.cache)
    rng=random.Random(6113);counts=dict(jpeg=0,affine=0,flip=0);initial=data.rng.getstate();plans=[]
    for i in range(32):
        index=rng.randrange(len(data));before=data.rng.getstate();plan=data.plan(index);after=data.rng.getstate()
        data.rng.setstate(before);old=original_sample(data,index)
        assert data.rng.getstate()==after,'RNG drift'
        new=data.sample(index,plan);equal(old,new)
        plans.append((index,plan))
        for key in counts:counts[key]+=bool(plan['quality'] if key=='jpeg' else plan[key])
    final=data.rng.getstate()
    with ThreadPoolExecutor(6) as pool:
        futures=[pool.submit(data.sample,index,plan) for index,plan in plans]
        for (index,plan),future in zip(plans,futures):equal(data.sample(index,plan),future.result())
    assert data.rng.getstate()==final,'Worker mutated RNG'
    result=dict(samples=32,historical_sampler_exact=True,parallel_tensors_exact=True,rng_exact=True,counts=counts,heldout_opened=False)
    (a.output/'complete.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)


if __name__=='__main__':main()
