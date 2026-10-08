"""Synthetic-only full replay for combined qualified loader and allocator controls."""
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
    script='import sys;sys.path.insert(0,'+repr(a.operations)+');from gpu_headroom import configure;from main02_loader4_v2 import configure_loader;configure_loader();configure();from imitation.t5.train import main;main()'
    second=[sys.executable,'-B','-c',script,*flags,'--output',str(out/'capped'),'--resume',str(out/'original/step-00000001.pt')]
    for name,cmd in [('original',first),('capped',second)]:
        with (out/(name+'.log')).open('w') as f:subprocess.run(cmd,cwd=a.source,stdout=f,stderr=subprocess.STDOUT,check=True)
    c1=torch.load(out/'original/step-00000002.pt',map_location='cpu',weights_only=True)
    c2=torch.load(out/'capped/step-00000002.pt',map_location='cpu',weights_only=True)
    for k in c1:
        if k!='args':assert same(c1[k],c2[k]),k
    result={'synthetic_gpu_replay_all_payload_except_args_bitexact':True,'real_fitting':False,'real_tail_probes':[]}
    result['passed']=True;(out/'PASS.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)

if __name__=='__main__':main()
