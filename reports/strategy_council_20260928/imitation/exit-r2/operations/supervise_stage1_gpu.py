"""Detached two-process scoring attempt, whole CPU/GPU meter and guards."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time
from experiment_x7 import load_experiment
from fit_collection_ready_x7 import snapshot
from stage1_gpu_guard import guard,verify_amendment,own_tree,resources,digest

def write(path,d):
    p=Path(str(path)+'.tmp');p.write_text(json.dumps(d,indent=2)+'\n');p.replace(path)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--job',required=True);ap.add_argument('--arm',required=True);a=ap.parse_args();j=Path(a.job)
    start=time.monotonic();child=None;reason=None;code=None;peak=0;minimum=1<<62
    out=j/'offline';out.mkdir(exist_ok=True)
    lock=(out/f'{a.arm}.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    assert not (out/f'{a.arm}.json').exists(),'already scored: never duplicate'
    try:
        verify_amendment(j);f=load_experiment(j);guard(j,a.arm)
        ready=snapshot(j,a.arm,f['arms'][a.arm]['steps']);assert ready['ready'],ready
        assert json.loads((j/f'stage1-staging-{a.arm}.json').read_text())['passed']
        occupied=subprocess.check_output(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader'],text=True).strip()
        assert not occupied,'fit/scoring GPU occupied; never preempt'
        checkpoint=j/'fits'/a.arm/f"step-{f['arms'][a.arm]['steps']:08d}.pt"
        child=subprocess.Popen([sys.executable,'-B',str(j/'ops/offline_gpu.py'),'--job',str(j),'--arm',a.arm,'--checkpoint',str(checkpoint)],start_new_session=True)
        write(out/f'{a.arm}-launch.json',dict(utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip(),supervisor_pid=os.getpid(),supervisor_pgid=os.getpgrp(),worker_pid=child.pid,worker_pgid=child.pid,checkpoint=str(checkpoint)))
        def stop(*_):
            nonlocal reason
            reason=reason or 'owned supervisor stop';child.terminate()
        signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
        stopped=None;checked=0
        while child.poll() is None:
            try:
                guard(j,a.arm)
                if time.monotonic()-checked>=10:
                    r=resources(own_tree(child.pid)+[os.getpid()]);peak=max(peak,r['pss_bytes']);minimum=min(minimum,r['gpu_free_bytes']);checked=time.monotonic()
                    if r['processes']>8 or r['pss_bytes']>46_000_000_000 or r['gpu_free_bytes']<8*2**30:raise RuntimeError('scoring resource guard')
                    write(out/f'{a.arm}-health.json',dict(r,reason=reason,wall_seconds=time.monotonic()-start))
            except Exception as e:
                reason=reason or str(e);child.terminate()
            if reason:
                stopped=stopped or time.monotonic()
                if time.monotonic()-stopped>30:os.killpg(child.pid,signal.SIGKILL)
            time.sleep(1)
        code=child.wait()
    except Exception as e:
        reason=reason or str(e);code=1;raise
    finally:
        if child and child.poll() is None:child.terminate();child.wait(timeout=30)
        own=resource.getrusage(resource.RUSAGE_SELF);kids=resource.getrusage(resource.RUSAGE_CHILDREN)
        write(out/f'{a.arm}-meter-{os.getpid()}.json',dict(utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip(),arm=a.arm,exit_code=code,reason=reason,parent_cpu_seconds=own.ru_utime+own.ru_stime,children_cpu_seconds=kids.ru_utime+kids.ru_stime,gpu_wall_seconds=time.monotonic()-start,peak_pss_bytes=peak,min_gpu_free_bytes=minimum,note='Whole parent+child CPU once; child result CPU is nested, never add separately. Failed/reaped attempts retained.'))
    raise SystemExit(code)

if __name__=='__main__':main()
