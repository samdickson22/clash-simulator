"""Detached T4 single/concurrent measurement supervisor, never full training."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def run_group(args, name, microbatch, runs):
    root=Path(args.output)/name
    root.mkdir(parents=True,exist_ok=False)
    children=[];logs=[];samples=[];wall=time.time()
    for i in range(runs):
        log=(root/f'worker-{i}.log').open('w');logs.append(log)
        cmd=[sys.executable,'-B','-m','imitation.model.throughput','benchmark',
             '--store',args.store,'--assets',args.assets,'--qualification',args.qualification,
             '--output',str(root/f'worker-{i}'),'--microbatch',str(microbatch),'--workers','4','--steps',str(args.steps)]
        children.append(subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT))
    failure=None
    try:
        while any(p.poll() is None for p in children):
            raw=subprocess.check_output(['nvidia-smi','--query-gpu=memory.used,memory.free,utilization.gpu','--format=csv,noheader,nounits'],text=True)
            used,free,util=map(int,raw.strip().split(','))
            samples.append({'time':time.time(),'used_mib':used,'free_mib':free,'gpu_utilization_percent':util})
            if free < 8192:
                failure='measured device headroom below8GiB'
                # Only our exact Popen children, never name-based process killing.
                for p in children:
                    if p.poll() is None:p.terminate()
                break
            time.sleep(1)
        exits=[p.wait() for p in children]
    finally:
        for log in logs:log.close()
    result={'group':name,'microbatch':microbatch,'runs':runs,'started_unix':wall,'ended_unix':time.time(),
            'child_pids':[p.pid for p in children],'exits':exits,'failure':failure,
            'minimum_device_free_mib':min(s['free_mib'] for s in samples),
            'maximum_device_used_mib':max(s['used_mib'] for s in samples),'gpu_samples':samples}
    if exits==[0]*runs and failure is None:
        receipts=[json.loads((root/f'worker-{i}'/'benchmark.json').read_text()) for i in range(runs)]
        result['workers']=receipts
        result['sum_rows_per_second_including_loader']=sum(r['rows_per_second_including_loader'] for r in receipts)
    result['passed']=exits==[0]*runs and failure is None
    (root/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('gpu_samples','workers')}),flush=True)
    if not result['passed']:raise RuntimeError(str(result))
    return result


def main():
    p=argparse.ArgumentParser()
    for name in ('store','assets','qualification','output'):p.add_argument('--'+name,required=True)
    p.add_argument('--steps',type=int,default=64)
    a=p.parse_args()
    who=subprocess.check_output(['who'],text=True)
    if who.strip():raise RuntimeError('console/user present; defer benchmark')
    comm=subprocess.check_output(['ps','-u',str(os.getuid()),'-o','comm='],text=True).splitlines()
    workers=sum(any(k in line for k in ('python','rsync','cargo','rustc')) for line in comm)
    if workers+14>80:raise RuntimeError('worker cap insufficient for paired run')
    result={'single':run_group(a,'single',7168,1),'concurrent':run_group(a,'concurrent',3072,2)}
    (Path(a.output)/'complete.json').write_text(json.dumps({'passed':True,'groups':{k:{x:v[x] for x in ('microbatch','runs','minimum_device_free_mib','maximum_device_used_mib','sum_rows_per_second_including_loader')} for k,v in result.items()}},indent=2)+'\n')


if __name__=='__main__':main()
