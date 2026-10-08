"""Train-only loader identity, fault timing, and synthetic checkpoint replay."""
import argparse, hashlib, json, os, resource, subprocess, sys, time
from pathlib import Path
import numpy as np
import torch
from imitation.model import batching
from imitation.model.store import PackedStore, epoch_indices
from imitation.model.synthetic_store import create
from imitation.t5.resources import BoundedBatchedStore, OriginalBatchedStore


def same(a,b):
    if isinstance(a,torch.Tensor): return torch.equal(a,b)
    if isinstance(a,dict): return a.keys()==b.keys() and all(same(a[k],b[k]) for k in a)
    if isinstance(a,(list,tuple)): return len(a)==len(b) and all(same(x,y) for x,y in zip(a,b))
    return a==b


def main():
    p=argparse.ArgumentParser()
    for n in ('source','output','store','assets','operations'):p.add_argument('--'+n,required=True)
    a=p.parse_args(); out=Path(a.output);out.mkdir(exist_ok=False)
    torch.set_num_threads(1)
    for role in ('train','dev'):create(out/role,role,16)
    flags=['--variant','main','--store',str(out/'train'),'--dev',str(out/'dev'),
           '--device','cpu','--synthetic-smoke','--batch-size','8','--microbatch','4',
           '--max-steps','2','--checkpoint-every','1','--seed','17','--workers','1']
    cmd=[sys.executable,'-B','-m','imitation.t5.train',*flags,'--output',str(out/'original')]
    with (out/'original.log').open('w') as f:subprocess.run(cmd,cwd=a.source,stdout=f,stderr=subprocess.STDOUT,check=True)
    script="import sys;sys.path.insert(0,"+repr(a.operations)+");from main02_loader4 import configure_loader;configure_loader();from imitation.t5.train import main;main()"
    cmd=[sys.executable,'-B','-c',script,*flags,'--output',str(out/'replayed'),'--resume',str(out/'original/step-00000001.pt')]
    with (out/'replayed.log').open('w') as f:subprocess.run(cmd,cwd=a.source,stdout=f,stderr=subprocess.STDOUT,check=True)
    first=torch.load(out/'original/step-00000002.pt',weights_only=True)
    second=torch.load(out/'replayed/step-00000002.pt',weights_only=True)
    checked=[k for k in first if k!='args']
    for k in checked:assert same(first[k],second[k]),k
    result={'synthetic_checkpoint_replay_bitexact':checked,'real_parameter_updates':False,'loader_modes':[]}
    store=PackedStore(a.store,'train',a.assets)
    ix=epoch_indices(store,0,2026100802)
    # Test batches from the resumed portion, sorted exactly as the qualified trainer.
    ix=ix[980*8192:988*8192].copy()
    counts=np.diff(store.column('entity_offsets'))
    for begin in range(0,len(ix),8192):
        part=ix[begin:begin+8192];ix[begin:begin+len(part)]=part[np.argsort(counts[part],kind='stable')]
    reference=None
    for mode,cls,workers in [('bounded1',BoundedBatchedStore,1),('original1',OriginalBatchedStore,1),('original4',OriginalBatchedStore,4)]:
        batching.BatchedStore=cls
        torch_before=torch.get_rng_state().clone();np_before=np.random.get_state()
        before=resource.getrusage(resource.RUSAGE_CHILDREN);start=time.monotonic(); hashes=[]
        for b,y in batching.batch_loader(store,8192,ix,workers=workers,seed=2026100802):
            h=hashlib.sha256()
            for group in (b,y):
                for key,value in sorted(group.items()):
                    h.update(key.encode());h.update(str(value.dtype).encode());h.update(str(tuple(value.shape)).encode());h.update(value.numpy().tobytes())
            hashes.append(h.hexdigest())
        elapsed=time.monotonic()-start;after=resource.getrusage(resource.RUSAGE_CHILDREN)
        assert torch.equal(torch_before,torch.get_rng_state())
        np_after=np.random.get_state();assert np_before[0]==np_after[0] and np.array_equal(np_before[1],np_after[1]) and np_before[2:]==np_after[2:]
        if reference is None:reference=hashes
        assert hashes==reference
        row={'mode':mode,'rows':len(ix),'batch_hashes':hashes,'seconds_including_hashing_and_worker_startup':elapsed,
             'rows_per_second':len(ix)/elapsed,'child_system_seconds':after.ru_stime-before.ru_stime,
             'child_user_seconds':after.ru_utime-before.ru_utime,'minor_faults':after.ru_minflt-before.ru_minflt,'major_faults':after.ru_majflt-before.ru_majflt}
        result['loader_modes'].append(row);print(json.dumps(row),flush=True)
    result['passed']=True
    (out/'PASS.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)

if __name__=='__main__':main()
