"""Detached T1 smoke -> readiness -> Phase A driver, resumable from receipts."""
import argparse
import fcntl
import os
from pathlib import Path
import subprocess
import sys
import time
from common import HERE,ROOT,write


def run(label, args):
    print(f'{label} starting',flush=True)
    write(HERE/'pipeline-state.json',dict(stage=label,pid=os.getpid(),time=time.time(),args=args))
    with (HERE/(label+'.log')).open('a') as log:
        result=subprocess.run([sys.executable,'-u',*args],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,close_fds=False)
    write(HERE/(label+'-exit.json'),dict(code=result.returncode,time=time.time()))
    if result.returncode:raise RuntimeError(f'{label} failed; inspect {label}.log, preserve receipts and resume')


def main():
    p=argparse.ArgumentParser()
    modes=p.add_mutually_exclusive_group()
    modes.add_argument('--smoke-only',action='store_true')
    modes.add_argument('--phase-a-only',action='store_true')
    a=p.parse_args()
    with (HERE/'pipeline.lock').open('w') as lock:
      fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
      # T2 evidence is complete and retained; never restart its renderer bench.
      if not (HERE/'frozen-manifest.json').exists():run('freeze',['scripts/collect_l1_stream_v4.py','--prepare'])
      if not a.phase_a_only:run('smoke',['scripts/collect_l1_stream_v4.py','--smoke'])
      if not a.smoke_only:
        from collector import require_hub_ready
        while True:
          try:require_hub_ready();break
          except Exception as error:
            write(HERE/'pipeline-state.json',dict(stage='waiting for hub readiness and verified smoke',pid=os.getpid(),time=time.time(),error=str(error)))
            print('Phase A admission waiting: '+str(error),flush=True)
            time.sleep(30)
        run('phase-a',['scripts/collect_l1_stream_v4.py'])
      write(HERE/'pipeline-state.json',dict(stage='smoke complete' if a.smoke_only else 'complete',pid=os.getpid(),time=time.time()))

if __name__=='__main__':main()
