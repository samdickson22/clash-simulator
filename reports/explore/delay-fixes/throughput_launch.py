"""Adopt running shards, drain 08, obey live coordinator caps, never target11."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import json,shlex,subprocess,threading,time
from pathlib import Path

HERE=Path(__file__).resolve().parent
LEASE='/mpac/sdicks02/repos/clasher-lease';HOME='/mpac/sdicks02/repos/clasher'
ADOPT={'127x14': (600, 'cpu-delay-fixes-p0600-127x14-fine-r4'), '127x15': (585, 'cpu-delay-fixes-p0585-127x15-fine-r4'), '127x13': (590, 'cpu-delay-fixes-p0590-127x13-fine-r4'), '127x09': (605, 'cpu-delay-fixes-p0605-127x09-fine-r4'), '127x16': (595, 'cpu-delay-fixes-p0595-127x16-fine-r4')}
FIRST={}
queue=json.loads((HERE/'launch-fine-r4.json').read_text())['unstarted_offsets']
lock=threading.Lock()
manifest=dict(paired_seed_target=1250,prior_manifest='launch-fine-r4.json',shard_pairs=5,
    down_hosts=['127x11'],results=[],failed=[],held_unknown=[],unstarted_offsets=queue.copy())
def save():
    manifest['unstarted_offsets']=queue.copy()
    (HERE/'launch-throughput-v5.json').write_text(json.dumps(manifest,indent=2)+'\n')
def ssh(host,args,**kwargs):
    return subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=5',
        '-o','ServerAliveInterval=10','-o','ServerAliveCountMax=2',host,
        shlex.join(args)],**kwargs)
def collect(host,offset,label):
    if host=='127x08':return
    root=LEASE+'/delay-fixes-runtime';out=f'{root}/reports/explore/delay-fixes/shards/p{offset:04d}'
    ssh(host,['rsync','-az',out+'/',f'127x08:{HOME}/reports/explore/delay-fixes/shards/p{offset:04d}/'],
        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    subprocess.run(['rsync','-az','-e','ssh -o BatchMode=yes -o ConnectTimeout=5',
        f'{host}:{LEASE}/jobs/{label}.exit.json',str(HERE/'receipts')+'/'],
        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
def adopt(host,entry):
    offset,label=entry
    path=(f'/mpac/sdicks02/jobs/clasher/{label}.exit' if host=='127x08'
          else f'{LEASE}/jobs/{label}.exit.json')
    while datetime.now(timezone.utc)<datetime(2026,10,9,4,30,tzinfo=timezone.utc):
        run=ssh(host,['cat',path],capture_output=True,text=True)
        if run.returncode==0:
            status=int(run.stdout) if host=='127x08' else json.loads(run.stdout)['exit_code']
            collect(host,offset,label)
            with lock:
                manifest['results' if status==0 else 'failed'].append(dict(host=host,offset=offset,label=label,
                    adopted=True,exit_code=status,finished=time.time()))
                if status:queue.insert(0,offset)
                save()
            return status==0
        if run.returncode==255:
            with lock:manifest['held_unknown'].append(dict(host=host,offset=offset,label=label));save()
            return False
        time.sleep(20)
    return False
def lane(host):
    if host in ADOPT and not adopt(host,ADOPT[host]):return
    first=FIRST.get(host)
    while datetime.now(timezone.utc)<datetime(2026,10,9,4,15,tzinfo=timezone.utc):
        workers=json.loads((HERE/'resource-policy.json').read_text()).get(host,0)
        with lock:
            if not queue and first is None:return
        if not workers:time.sleep(10);continue
        with lock:
            if first is not None:offset,first=first,None
            elif queue:offset=queue.pop(0)
            else:return
            save()
        root=HOME if host=='127x08' else LEASE+'/delay-fixes-runtime'
        label=f'cpu-delay-fixes-p{offset:04d}-{host}-throughput-v5'
        out=f'{root}/reports/explore/delay-fixes/shards/p{offset:04d}'
        command=['env',f'CLASHER_ROOT={root}',f'PYTHONPATH={root}:{root}/src:{root}/engine-rs','RAYON_NUM_THREADS=1']
        if host=='127x08':command+=[f'CLASHER_DELAY_NATIVE_DIR={root}/reports/explore/delay-fixes/native']
        command += [(HOME if host=='127x08' else LEASE+'/repo')+'/.venv/bin/python','-m',
            'clasher.analysis.loss_review.delay_simulate','--out',out,'--pairs',str(25 if offset==325 else 5),
            '--pair-offset',str(offset),'--workers',str(workers),'--checkpoint',
            f'{root}/reports/explore/delay-fixes/inputs/main02.pt','--exclusions',
            f'{root}/reports/explore/loss-review/seeds.json','--gpu-guard','--resume']
        args=(['nice','-n','10','bash',HOME+'/reports/strategy_council_20260928/fleet/fleet_run.sh',
            '--worker',label] if host=='127x08' else ['bash',LEASE+'/run_v2.sh','--foreground',
            '--max-processes',str(workers+4),'--expected-pss-gb',str(18 if workers>16 else 12),label,'--'])+command
        started=time.time()
        with (HERE/'receipts'/f'{label}.log').open('x') as log:
            run=ssh(host,args,stdout=log,stderr=subprocess.STDOUT)
        collect(host,offset,label)
        row=dict(host=host,offset=offset,label=label,workers=workers,started=started,
                 finished=time.time(),exit_code=run.returncode,command=args)
        with lock:
            manifest['results' if run.returncode==0 else 'failed'].append(row)
            if run.returncode==255:manifest['held_unknown'].append(row)
            elif run.returncode:queue.insert(0,offset)
            save()
        print(json.dumps(row),flush=True)
        if run.returncode:return  # No retry of a refusal or unverified remote job.
save()
with ThreadPoolExecutor(max_workers=6) as pool:
    list(pool.map(lane,['127x09','127x14','127x13','127x15','127x16','127x08']))
save()
