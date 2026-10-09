"""Light command-center orchestration; all simulation executes under lease v2.

Each host runs one short foreground wrapper at a time. Wrapper refusals stop
that host's lane; no cap bypass. New shards cease at04:15Z, jobs at04:29Z.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import json
from pathlib import Path
import shlex
import subprocess
import threading
import time

ROOT='/mpac/sdicks02/repos/clasher-lease/delay-fixes-runtime'
BASE='/mpac/sdicks02/repos/clasher-lease'
OUT=Path(__file__).resolve().parent
HOSTS=['127x09','127x11','127x13','127x14','127x15','127x16']


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--pairs',type=int,default=1000)
    ap.add_argument('--shard-pairs',type=int,default=25);ap.add_argument('--tag',default='v1')
    ap.add_argument('--start-offset',type=int,default=0);ap.add_argument('--hosts',nargs='+',default=HOSTS)
    ap.add_argument('--manifest',default='launch.json')
    a=ap.parse_args();assert a.pairs%a.shard_pairs==0
    shards=list(range(a.start_offset,a.start_offset+a.pairs,a.shard_pairs));lock=threading.Lock()
    (OUT/'receipts').mkdir(exist_ok=True)
    manifest=dict(pairs=a.pairs,shard_pairs=a.shard_pairs,arms=['U0','U27','S0','S27','N2','N4','I0','IF'],
        seed_base=2**48+50000,tag=a.tag,results=[],failed=[])
    (OUT/a.manifest).write_text(json.dumps(manifest,indent=2)+'\n')
    def lane(host):
        while True:
            if datetime.now(timezone.utc)>=datetime(2026,10,9,4,15,tzinfo=timezone.utc):return
            with lock:
                if not shards:return
                offset=shards.pop(0)
            # Current v1+search-ab declarations leave26 process slots on80-cap
            # hosts;26 includes22 workers, main, supervisor and monitoring.
            workers=26 if host in ('127x11','127x16') else 22
            declared=workers+4
            label=f'cpu-delay-fixes-p{offset:04d}-{a.tag}'
            args=['bash',BASE+'/run_v2.sh','--foreground','--max-processes',str(declared),
                '--expected-pss-gb','12',label,'--','env',f'CLASHER_ROOT={ROOT}',
                f'PYTHONPATH={ROOT}:{ROOT}/src:{ROOT}/engine-rs',BASE+'/repo/.venv/bin/python',
                '-m','clasher.analysis.loss_review.delay_simulate','--out',
                f'{ROOT}/reports/explore/delay-fixes/shards/p{offset:04d}',
                '--pairs',str(a.shard_pairs),'--pair-offset',str(offset),'--workers',str(workers),
                '--checkpoint',f'{ROOT}/reports/explore/delay-fixes/inputs/main02.pt',
                '--exclusions',f'{ROOT}/reports/explore/loss-review/seeds.json','--gpu-guard']
            started=time.time()
            with (OUT/'receipts'/f'{label}.log').open('x') as log:
                process=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10',host,
                    shlex.join(args)],stdout=log,stderr=subprocess.STDOUT)
            row=dict(host=host,label=label,offset=offset,pairs=a.shard_pairs,
                workers=workers,declared_processes=declared,started=started,finished=time.time(),
                exit_code=process.returncode,command=args)
            # Small completed reductions and receipts only; checkpoint/raw traces
            # stay lease-local. Larger archives can be copied to a home host later.
            subprocess.run(['ssh','-o','BatchMode=yes',host,
                shlex.join(['rsync','-az',f'{ROOT}/reports/explore/delay-fixes/shards/p{offset:04d}/',
                    f'127x08:/mpac/sdicks02/repos/clasher/reports/explore/delay-fixes/shards/p{offset:04d}/'])],stdout=subprocess.DEVNULL)
            subprocess.run(['rsync','-az',f'{host}:{BASE}/jobs/{label}.exit.json',str(OUT/'receipts')+'/'],stdout=subprocess.DEVNULL)
            with lock:
                manifest['results' if process.returncode==0 else 'failed'].append(row)
                manifest['unstarted_offsets']=list(shards)
                (OUT/a.manifest).write_text(json.dumps(manifest,indent=2)+'\n')
            print(json.dumps(row),flush=True)
            if process.returncode:return
    with ThreadPoolExecutor(max_workers=6) as pool:list(pool.map(lane,a.hosts))
    manifest['unstarted_offsets']=shards
    (OUT/a.manifest).write_text(json.dumps(manifest,indent=2)+'\n')


if __name__=='__main__':main()
