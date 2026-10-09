"""Width adapter for human capacity arms and pinned single-core proposer probe."""
import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import sys
import torch
from imitation.model.network import ModelConfig, SetPolicy
from imitation.model.inference import Policy, load_policy
from imitation.model.benchmark import bench
from .rows import sha,write_json


def config(width,base=None):
    if width<96 or width%6:raise ValueError('width must be >=96 and divisible by six')
    return ModelConfig(**{**asdict(base or ModelConfig()),'width':width,'heads':6,'ffn':4*width})


def kill_scan(base_nll,arm_nll,rows,scheduled_rows):
    if scheduled_rows<=0 or rows<0:raise ValueError('invalid matched-row checkpoint')
    return rows>=scheduled_rows*.25 and base_nll-arm_nll<.005


def main():
    p=argparse.ArgumentParser()
    sub=p.add_subparsers(dest='command',required=True)
    probe=sub.add_parser('probe');probe.add_argument('--widths',type=int,nargs='+',default=[192,288,384,768])
    probe.add_argument('--checkpoint',required=True);probe.add_argument('--iterations',type=int,default=1000)
    probe.add_argument('--entities',type=int,nargs='+',default=[10,25,64]);probe.add_argument('--core',type=int,default=63)
    probe.add_argument('--output',required=True)
    train=sub.add_parser('train',add_help=False);train.add_argument('--width',type=int,required=True)
    a,rest=p.parse_known_args()
    if a.command=='train':
        from imitation.model import train as qualified
        from .train import eligible
        from imitation.model.batching import batch_loader
        import numpy as np
        qualified.ModelConfig=lambda **kw:config(a.width,ModelConfig(**kw))
        qualified.epoch_indices=lambda store,epoch,seed,subset_fraction=1.: eligible(store,epoch,seed)
        def loader(store,*args,**kw):
            for b,y in batch_loader(store,*args,**kw):
                if store.role=='train' and 'corpus_s122' in store.arrays:
                    s122=torch.from_numpy(np.asarray(store.arrays['corpus_s122'][y['index'].numpy()]))
                    y['weight']=y['weight'].float()*torch.where(s122&(y['action']==2304),.5,1.)
                yield b,y
        qualified.batch_loader=loader
        sys.argv=[sys.argv[0],*rest]
        qualified.main()
        return
    if rest:p.error('unknown probe arguments')
    os.sched_setaffinity(0,{a.core});torch.set_num_threads(1);torch.set_num_interop_threads(1)
    source=load_policy(a.checkpoint);base=ModelConfig(**source.metadata['config'])
    records=[]
    for width in a.widths:
        torch.manual_seed(20261009)
        c=config(width,base)
        policy=source if c==base else Policy(SetPolicy(c,source.model.descriptors,source.model.tile_features,source.model.costs))
        r=dict(config=asdict(c),parameters=sum(p.numel() for p in policy.model.parameters()),
            random_weights=policy is not source,measurements=[bench(policy,a.iterations,n) for n in a.entities])
        r['within_15ms']=all(v['p99_ms']<=15 for v in r['measurements'])
        records.append(r)
        print(json.dumps(r),flush=True)
        write_json(a.output,dict(host=os.uname().nodename,threads=1,affinity=sorted(os.sched_getaffinity(0)),
            checkpoint_sha256=sha(a.checkpoint),synthetic_inputs=True,torch=torch.__version__,models=records))


if __name__=='__main__':main()
