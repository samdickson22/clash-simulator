"""Detached, serial T2 -> T1 smoke -> Phase A driver, resumable from receipts."""
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
    p=argparse.ArgumentParser();p.add_argument('--wait-bench-pid',type=int);a=p.parse_args()
    with (HERE/'pipeline.lock').open('w') as lock:
      fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
      if a.wait_bench_pid:
        while True:
          command=subprocess.run(['/bin/ps','-p',str(a.wait_bench_pid),'-o','command='],text=True,capture_output=True).stdout
          if 'actuation/bench.py' not in command:break
          write(HERE/'pipeline-state.json',dict(stage='waiting for existing T2 bench',pid=os.getpid(),bench_pid=a.wait_bench_pid,time=time.time()))
          time.sleep(10)
      run('bench-resume',[str(HERE/'actuation/bench.py')])
      if not (HERE/'actuation/reproduction.json').exists():run('stale-reproduction',[str(HERE/'actuation/reproduce.py')])
      run('t2-report',[str(HERE/'report_t2.py')])
      # Freeze before the first smoke, then verify the same manifest at Phase A.
      if not (HERE/'frozen-manifest.json').exists():run('freeze',['scripts/collect_l1_stream_v4.py','--prepare'])
      run('smoke',['scripts/collect_l1_stream_v4.py','--smoke'])
      run('phase-a',['scripts/collect_l1_stream_v4.py'])
      write(HERE/'pipeline-state.json',dict(stage='complete',pid=os.getpid(),time=time.time()))

if __name__=='__main__':main()
