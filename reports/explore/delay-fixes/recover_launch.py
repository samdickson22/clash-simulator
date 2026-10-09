"""Resource-policy recovery: no launches on 13/15; preserve completed games."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import json
from pathlib import Path
import shlex,subprocess,threading,time

HERE=Path(__file__).resolve().parent
LEASE='/mpac/sdicks02/repos/clasher-lease'
HOME='/mpac/sdicks02/repos/clasher'
HOSTS={'127x09':15,'127x14':15,'127x11':26,'127x08':26}
FIRST={'127x09':200,'127x14':75,'127x11':25}
queue=list(range(250,1250,25));lock=threading.Lock()
manifest=dict(paired_seed_target=1250,closed_hosts=['127x13','127x15'],workers=HOSTS,
              results=[],failed=[],unstarted_offsets=queue.copy())
def save():
    manifest['unstarted_offsets']=queue.copy()
    (HERE/'launch-recovery.json').write_text(json.dumps(manifest,indent=2)+'\n')
def lane(host):
    first=FIRST.get(host)
    while datetime.now(timezone.utc)<datetime(2026,10,9,4,15,tzinfo=timezone.utc):
        with lock:
            if first is not None:offset,first=first,None
            elif queue:offset=queue.pop(0)
            else:return
            save()
        workers=HOSTS[host];root=HOME if host=='127x08' else LEASE+'/delay-fixes-runtime'
        label=f'cpu-delay-fixes-p{offset:04d}-resource-r2'
        out=f'{root}/reports/explore/delay-fixes/shards/p{offset:04d}'
        command=['env',f'CLASHER_ROOT={root}',f'PYTHONPATH={root}:{root}/src:{root}/engine-rs',
                 'RAYON_NUM_THREADS=1']
        if host=='127x08':command += [f'CLASHER_DELAY_NATIVE_DIR={root}/reports/explore/delay-fixes/native']
        command += [(HOME if host=='127x08' else LEASE+'/repo')+'/.venv/bin/python','-m',
            'clasher.analysis.loss_review.delay_simulate','--out',out,'--pairs','25',
            '--pair-offset',str(offset),'--workers',str(workers),'--checkpoint',
            f'{root}/reports/explore/delay-fixes/inputs/main02.pt','--exclusions',
            f'{root}/reports/explore/loss-review/seeds.json','--gpu-guard','--resume']
        if host=='127x08':
            args=['nice','-n','10','bash',HOME+'/reports/strategy_council_20260928/fleet/fleet_run.sh',
                  '--worker',label]+command
        else:
            args=['bash',LEASE+'/run_v2.sh','--foreground','--max-processes',str(workers+4),
                  '--expected-pss-gb','12',label,'--']+command
        start=time.time()
        with (HERE/'receipts'/f'{label}.log').open('x') as log:
            run=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10',host,shlex.join(args)],
                               stdout=log,stderr=subprocess.STDOUT)
        row=dict(host=host,label=label,offset=offset,workers=workers,started=start,finished=time.time(),
                 exit_code=run.returncode,command=args)
        if host!='127x08':
            subprocess.run(['ssh','-o','BatchMode=yes',host,
                shlex.join(['rsync','-az',out+'/',f'127x08:{HOME}/reports/explore/delay-fixes/shards/p{offset:04d}/'])])
            subprocess.run(['rsync','-az',f'{host}:{LEASE}/jobs/{label}.exit.json',str(HERE/'receipts')+'/'])
        with lock:
            manifest['results' if run.returncode==0 else 'failed'].append(row)
            if run.returncode:queue.insert(0,offset)
            save()
        print(json.dumps(row),flush=True)
        if run.returncode:return  # Accept refusal; other admitted lanes can reuse the schedule.
with ThreadPoolExecutor(max_workers=len(HOSTS)) as pool:list(pool.map(lane,HOSTS))
save()
