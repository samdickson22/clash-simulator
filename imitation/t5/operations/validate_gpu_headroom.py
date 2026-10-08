"""Synthetic GPU replay plus unfitted real tail-batch allocator check."""
import argparse,json,subprocess,sys,time
from pathlib import Path
import torch,numpy as np
from imitation.model.synthetic_store import create
from imitation.model.store import PackedStore,epoch_indices
from imitation.model.network import ModelConfig
from imitation.model.batching import build_batch
from imitation.model.train import optimizer_step
from imitation.t5.variants import create_policy
from gpu_headroom import configure


def same(a,b):
    if isinstance(a,torch.Tensor):return torch.equal(a,b)
    if isinstance(a,dict):return a.keys()==b.keys() and all(same(a[k],b[k]) for k in a)
    if isinstance(a,(tuple,list)):return len(a)==len(b) and all(same(x,y) for x,y in zip(a,b))
    return a==b


def main():
    p=argparse.ArgumentParser()
    for k in ('source','operations','output','store','assets'):p.add_argument('--'+k,required=True)
    a=p.parse_args();out=Path(a.output);out.mkdir(exist_ok=False);torch.set_num_threads(1)
    for role in ('train','dev'):create(out/role,role,16)
    flags=['--variant','main','--store',str(out/'train'),'--dev',str(out/'dev'),'--device','cuda',
           '--synthetic-smoke','--batch-size','8','--microbatch','4','--max-steps','2','--checkpoint-every','1','--seed','17','--workers','1']
    first=[sys.executable,'-B','-m','imitation.t5.train',*flags,'--output',str(out/'original')]
    script='import sys;sys.path.insert(0,'+repr(a.operations)+');from gpu_headroom import configure;configure();from imitation.t5.train import main;main()'
    second=[sys.executable,'-B','-c',script,*flags,'--output',str(out/'capped'),'--resume',str(out/'original/step-00000001.pt')]
    for name,cmd in [('original',first),('capped',second)]:
        with (out/(name+'.log')).open('w') as f:subprocess.run(cmd,cwd=a.source,stdout=f,stderr=subprocess.STDOUT,check=True)
    c1=torch.load(out/'original/step-00000002.pt',map_location='cpu',weights_only=True)
    c2=torch.load(out/'capped/step-00000002.pt',map_location='cpu',weights_only=True)
    for k in c1:
        if k!='args':assert same(c1[k],c2[k]),k
    result={'synthetic_gpu_replay_all_payload_except_args_bitexact':True,'real_fitting':False,'real_tail_probes':[]}
    configure();store=PackedStore(a.store,'train',a.assets);ix=epoch_indices(store,2,2026100801)
    tail=ix[(len(ix)//8192)*8192:];counts=np.diff(store.column('entity_offsets'));tail=tail[np.argsort(counts[tail],kind='stable')]
    b,y=build_batch(store,tail);b['row_index']=y['index'];y['weight']=y['weight'].float()*torch.where(y['action']==2304,4.,1.)
    class NoUpdate(torch.optim.AdamW):
        def step(self,closure=None):return None
    for variant in ('main','noD1'):
        torch.manual_seed(2026100801);torch.cuda.empty_cache();torch.cuda.reset_peak_memory_stats()
        model=create_policy(variant,ModelConfig(tile_width=64),*[torch.tensor(store.assets[k]) for k in ('descriptors','tiles','costs')]).cuda()
        before={k:v.detach().cpu().clone() for k,v in model.state_dict().items()};opt=NoUpdate(model.parameters(),lr=3e-4,weight_decay=.05)
        t=time.monotonic();loss=optimizer_step(model,opt,b,y,7168,torch.device('cuda'))
        assert not opt.state and all(torch.equal(before[k],v.cpu()) for k,v in model.state_dict().items())
        allocated=torch.cuda.max_memory_allocated();reserved=torch.cuda.max_memory_reserved();free,total=torch.cuda.mem_get_info()
        assert free>=8192*2**20 and reserved<=total*.75
        result['real_tail_probes'].append({'variant':variant,'rows':len(tail),'loss':loss,'seconds':time.monotonic()-t,'peak_allocated_mib':allocated/2**20,'peak_reserved_mib':reserved/2**20,'free_mib':free/2**20,'parameter_or_optimizer_update':False})
        del model,opt,before;torch.cuda.empty_cache()
    result['passed']=True;(out/'PASS.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)

if __name__=='__main__':main()
