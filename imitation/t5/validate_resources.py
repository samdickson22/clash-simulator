"""Technical r2 validation: worker-count replay and unfitted GRU memory probe."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
import numpy as np
import torch
from imitation.model.synthetic_store import create
from imitation.model.store import PackedStore, epoch_indices
from imitation.model.network import ModelConfig
from imitation.model.batching import build_batch
from imitation.model.train import optimizer_step
from .variants import create_policy
from .resources import release_pages
from .guards import write_once


def main():
    p = argparse.ArgumentParser()
    for key in ('old-source','output','store','assets'): p.add_argument('--'+key, required=True)
    a=p.parse_args(); out=Path(a.output);out.mkdir(parents=True,exist_ok=False)
    torch.set_num_threads(1); start=time.monotonic()
    for role in ('train','dev'): create(out/role,role,16)
    results={'technical_reason':'observed shared RSS stops and GRU CUDA OOM','real_fitting':False,'replay':{}}
    for variant in ('main','noD1','gru'):
        flags=['--variant',variant,'--store',str(out/'train'),'--dev',str(out/'dev'),'--device','cpu',
               '--synthetic-smoke','--batch-size','8','--microbatch','4','--max-steps','2',
               '--checkpoint-every','1','--seed','17']
        first=out/(variant+'-old');second=out/(variant+'-new')
        cmd=[sys.executable,'-B','-m','imitation.t5.train',*flags]
        with (out/(variant+'-old.log')).open('w') as f:
            subprocess.run([*cmd,'--workers','4','--output',str(first)],cwd=a.old_source,stdout=f,stderr=subprocess.STDOUT,check=True)
        with (out/(variant+'-new.log')).open('w') as f:
            subprocess.run([*cmd,'--workers','1','--output',str(second),'--resume',str(first/'step-00000001.pt')],stdout=f,stderr=subprocess.STDOUT,check=True)
        old=torch.load(first/'step-00000002.pt',weights_only=True);new=torch.load(second/'step-00000002.pt',weights_only=True)
        for key in ('model','ema'):
            assert all(torch.equal(old[key][name],new[key][name]) for name in old[key]),(variant,key)
        assert old['state']==new['state']
        results['replay'][variant]='bit-exact model/EMA/state across old workers4 -> r2 workers1, checkpoint step1 -> step2'
    store=PackedStore(a.store,'train',a.assets)
    indices=epoch_indices(store,0,2026100801)[:8192]
    offsets=store.arrays['entity_offsets'];counts=offsets[indices+1]-offsets[indices]
    indices=indices[np.argsort(counts,kind='stable')]
    b,y=build_batch(store,indices);b['row_index']=y['index'];release_pages(store)
    y['weight']=y['weight'].float()*torch.where(y['action']==2304,4.,1.)
    torch.manual_seed(2026100801); assets=store.assets
    model=create_policy('gru',ModelConfig(),*[torch.tensor(assets[k]) for k in ('descriptors','tiles','costs')]).cuda()
    model.bind_store(store)
    before={k:v.detach().cpu().clone() for k,v in model.state_dict().items()}
    class NoUpdate(torch.optim.AdamW):
        def step(self,closure=None):
            return None  # This probe MUST NOT fit parameters or optimizer state.
    opt=NoUpdate(model.parameters(),lr=3e-4,weight_decay=.05)
    loss=optimizer_step(model,opt,b,y,7168,torch.device('cuda'))
    assert not opt.state
    assert all(torch.equal(before[k],v.cpu()) for k,v in model.state_dict().items())
    results['gru_memory']={'rows':8192,'primary_microbatch':7168,'history_chunk':1024,
                          'parameter_update':False,'optimizer_state_created':False,
                          'loss':loss,'peak_allocated_mib':torch.cuda.max_memory_allocated()/2**20,
                          'peak_reserved_mib':torch.cuda.max_memory_reserved()/2**20}
    results.update(passed=True,wall_seconds=time.monotonic()-start)
    write_once(out/'PASS.json',results);print(json.dumps(results),flush=True)


if __name__=='__main__': main()
