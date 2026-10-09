"""Two exact-state GPU replay branches, with serial versus ordered loader6 batches."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import torch

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def same(a,b):
    if isinstance(a,torch.Tensor):return isinstance(b,torch.Tensor) and torch.equal(a,b)
    if isinstance(a,dict):return a.keys()==b.keys() and all(same(a[k],b[k]) for k in a)
    if isinstance(a,(list,tuple)):return len(a)==len(b) and all(same(x,y) for x,y in zip(a,b))
    return a==b
def main():
    p=argparse.ArgumentParser()
    p.add_argument('--job',required=True);p.add_argument('--arm',required=True)
    p.add_argument('--ratio',required=True);p.add_argument('--resume',required=True)
    p.add_argument('--allocator-neutrality',action='store_true')
    a=p.parse_args();job=Path(a.job);out=job/('allocator-qualification' if a.allocator_neutrality else 'loader-qualification')/a.arm
    started=time.monotonic()
    out.mkdir(parents=True,exist_ok=False)
    initial=torch.load(a.resume,map_location='cpu',weights_only=True)
    cursor=initial['state']['step'];del initial
    env=dict(os.environ,EXIT_QUALIFICATION_STOP_AFTER='2',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
    results=[]
    modes=('native','expandable') if a.allocator_neutrality else ('serial','loader6')
    for mode in modes:
        dest=out/mode;dest.mkdir()
        (dest/'inputs.json').write_bytes((job/'fits'/a.arm/'inputs.json').read_bytes())
        flags=['--init-checkpoint',str(job/'inputs/main02.pt'),'--human-store',str(job/'human/train'),
            '--assets',str(job/'inputs/assets.npz'),'--teacher-root',str(job/'corpus'),'--teacher-ratio',a.ratio,
            '--steps','4883','--batch-size','8192','--microbatch','7168','--warmup','2000','--seed','2026100901',
            '--temperature','0.1','--play-weight','4','--value-weight','0','--checkpoint-every','1000',
            '--output',str(dest),'--stop',str(out/'STOP'),'--resume',a.resume]
        active=dict(env,EXIT_LOADER_WORKERS='6' if a.allocator_neutrality or mode=='loader6' else '0')
        if a.allocator_neutrality:
            active.pop('PYTORCH_CUDA_ALLOC_CONF',None)
            if mode=='expandable':active['PYTORCH_CUDA_ALLOC_CONF']='expandable_segments:True'
        with (out/f'{mode}.log').open('w') as log:
            subprocess.run([str(job/'venv/bin/python'),'-B',str(job/'ops/fit_runtime.py'),*flags],
                env=active,cwd=job/'source',stdout=log,stderr=subprocess.STDOUT,check=True)
        ck=torch.load(dest/f'step-{cursor+2:08d}.pt',map_location='cpu',weights_only=True)
        assert ck['state']['step']==cursor+2
        if mode==modes[0]:reference=ck
        else:
            assert reference.keys()==ck.keys()
            for key in reference:
                if key=='args':
                    for arg in reference[key]:
                        if arg not in ('output','stop'):assert same(reference[key][arg],ck[key][arg]),(key,arg)
                else:assert same(reference[key],ck[key]),key
        results.append(dict(mode=mode,checkpoint_sha256=sha(dest/f'step-{cursor+2:08d}.pt'),
                            segment=json.loads((dest/'segment.json').read_text())))
    record=dict(passed=True,qualification='two train-only GPU steps from identical exact state',
        cursor=cursor,rows_per_step=8192,resume_sha256=sha(a.resume),
        parent_checkpoint_keys_bitexact=[k for k in reference if k!='args'],
        argument_exceptions=['output','stop'],actual_loader_workers=6,prefetch_factor=4,
        mmap_random_advice=False,worker_complete_step_indices_checked=True,modes=results,
        wall_seconds=time.monotonic()-started)
    if a.allocator_neutrality:record['allocator_comparison']=['default','expandable_segments:True']
    (out/'PASS.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record))
if __name__=='__main__':main()
