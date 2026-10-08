"""Synthetic GPU replay through dev and subsequent training; no real fitting."""
import argparse,json,subprocess,sys,time
from pathlib import Path
import torch,numpy as np
from imitation.model.synthetic_store import create
from imitation.model.store import PackedStore,epoch_indices
from imitation.model.network import ModelConfig
from imitation.model.batching import build_batch
from imitation.model.train import optimizer_step
from imitation.t5.variants import create_policy
from main03_dev_memory import configure


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
           '--synthetic-smoke','--batch-size','8','--microbatch','4','--max-steps','4','--checkpoint-every','1','--seed','17','--workers','1']
    first=[sys.executable,'-B','-m','imitation.t5.train',*flags,'--output',str(out/'original')]
    script='import sys;sys.path.insert(0,'+repr(a.operations)+');from main03_dev_memory import configure;configure();from imitation.t5.train import main;main()'
    second=[sys.executable,'-B','-c',script,*flags,'--output',str(out/'capped'),'--resume',str(out/'original/step-00000001.pt')]
    for name,cmd in [('original',first),('capped',second)]:
        with (out/(name+'.log')).open('w') as f:subprocess.run(cmd,cwd=a.source,stdout=f,stderr=subprocess.STDOUT,check=True)
    c1=torch.load(out/'original/epoch-001-step-00000004.pt',map_location='cpu',weights_only=True)
    c2=torch.load(out/'capped/epoch-001-step-00000004.pt',map_location='cpu',weights_only=True)
    for k in c1:
        if k!='args':assert same(c1[k],c2[k]),k
    original_dev=[json.loads(x) for x in (out/'original/train.jsonl').read_text().splitlines() if json.loads(x)['event']=='dev']
    capped_dev=[json.loads(x) for x in (out/'capped/train.jsonl').read_text().splitlines() if json.loads(x)['event']=='dev']
    assert len(original_dev)==2 and original_dev==capped_dev
    result={'synthetic_gpu_replay_all_payload_except_args_bitexact':True,
            'two_dev_scores_bitexact':True,'subsequent_training_bitexact':True,
            'real_fitting':False,'passed':True,'dev':original_dev}
    (out/'PASS.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)

if __name__=='__main__':main()
