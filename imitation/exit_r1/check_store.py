"""Acceptance: mmap batch tensors equal the gate-c scalar serving path."""
import argparse
import json
from pathlib import Path
import numpy as np
import torch
from imitation.model.store import collate
from .student import TeacherStore


def main():
    p=argparse.ArgumentParser();p.add_argument('--shard',required=True);p.add_argument('--assets',required=True)
    a=p.parse_args();s=TeacherStore(a.shard,a.assets)
    ix=np.unique(np.linspace(0,len(s)-1,32,dtype=int))
    b,y=s.batch(ix)
    ref,ry=collate([s[int(i)] for i in ix])
    for k,v in b.items():
        assert torch.equal(v,ref[k]),k
    from .train import step
    from imitation.model.synthetic import model
    from imitation.model.network import ModelConfig
    m=model(ModelConfig(width=48,heads=6,layers=1,ffn=96,dropout=0))
    opt=torch.optim.AdamW(m.parameters(),lr=3e-4)
    result=step(m,opt,None,(b,y),1.,8,torch.device('cpu'),.1,4.,0.)
    assert np.isfinite(result['loss'])
    print(json.dumps(dict(vector_scalar_byte_equal=True,rows=len(ix),teacher_optimizer=result)))


if __name__=='__main__':main()
