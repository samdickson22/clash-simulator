"""Engineering-only union admission and augmented tensor parity before timing."""
import json
import random
from concurrent.futures import ThreadPoolExecutor
from cache_union_v4 import UnionPixelCache
from formal_guard import SPLIT_SHA
from pixel_cache import sha


def open_union(source,split,runtime):
    from data_v4 import inventory
    if sha(split)!=SPLIT_SHA:raise ValueError('Frozen split mismatch')
    config=json.loads(runtime.read_text())
    if config.get('schema')!='clasher.v4.engineering-union.v1':raise ValueError('Engineering union declaration required')
    rows=inventory(source,split,'train')[0]+inventory(source,split,'validation')[0]
    if {r['episode']:r['receipt_sha256'] for r in rows}!=config['receipt_sha256']:
        raise ValueError('Union must cover the entire staged train/validation snapshot')
    return UnionPixelCache(rows,config['shards'])


def parity(data,union):
    import torch
    from reference_sample import original_sample
    from cache_transport_v4 import RemotePixelCache
    def equal(a,b):
        for k,v in a.items():
            if isinstance(v,dict):
                for key,x in v.items():
                    if not torch.equal(x,b[k][key]):raise ValueError('Augmented target mismatch: '+key)
            elif not torch.equal(v,b[k]):raise ValueError('Augmented input mismatch: '+k)
    groups={remote:[i for i,(ep,_) in enumerate(data.examples)
                    if isinstance(union.readers[ep],RemotePixelCache)==remote] for remote in (False,True)}
    if any(not x for x in groups.values()):raise ValueError('Parity needs local and remote training examples')
    rng=random.Random(6114);saved=data.rng.getstate();counts=dict(jpeg=0,affine=0,flip=0);plans=[]
    try:
        for remote in (False,True):
            for _ in range(8):
                index=rng.choice(groups[remote]);before=data.rng.getstate();plan=data.plan(index);after=data.rng.getstate()
                data.rng.setstate(before);old=original_sample(data,index)
                if data.rng.getstate()!=after:raise ValueError('Sampler RNG drift')
                equal(old,data.sample(index,plan));plans.append((index,plan))
                for key in counts:counts[key]+=bool(plan['quality'] if key=='jpeg' else plan[key])
        final=data.rng.getstate()
        with ThreadPoolExecutor(6) as pool:
            futures=[pool.submit(data.sample,index,plan) for index,plan in plans]
            for (index,plan),future in zip(plans,futures):equal(data.sample(index,plan),future.result())
        if data.rng.getstate()!=final:raise ValueError('Worker mutated RNG')
        if not all(counts.values()):raise ValueError('Parity must exercise all augmentation kinds')
        return dict(samples=16,local=8,remote=8,counts=counts,historical_sampler_exact=True,
                    parallel_tensors_exact=True,rng_exact=True,heldout_opened=False,engineering_only=True)
    finally:data.rng.setstate(saved)
