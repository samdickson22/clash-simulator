"""Admit reporting stages as final EMAs seal; reduce only after all cases finish."""
import hashlib
import json
import os
from pathlib import Path
import resource
import shlex
import subprocess
import time

job=Path('/mpac/sdicks02/jobs/clasher/exit-r1-student-screen-20261009-r1')
fit_hosts={'S-mix':'01','S-teacher':'04','S-human':'08'}
cpu_hosts={'S-mix':'01','S-teacher':'04','S-human':'03'}
workers={'03':56,'04':60,'01':44}
env=dict(os.environ,PYTHONPATH=str(job/'source')+':'+str(job/'source/src'),CLASHER_ROOT=str(job/'source'),
    CLASHER_EVAL_RUNTIME_ROOT=str(job/'source'),CLASHER_DELAY_NATIVE_DIR=str(job/'reporting-native-v1'),
    PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',
    RAYON_NUM_THREADS='1',XDG_CACHE_HOME=str(job/'cache'))
py='/mpac/sdicks02/repos/clasher/.venv/bin/python';local_cpu_seconds=0.
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def run(cmd):subprocess.run(cmd,check=True)
def ssh(host,cmd):return subprocess.check_output(['ssh','127x'+host,cmd],text=True)
def state(stage,**kw):
    p=job/'controller.json';tmp=p.with_suffix('.partial')
    tmp.write_text(json.dumps(dict(stage=stage,utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
        local_cpu_seconds=local_cpu_seconds,**kw),indent=2)+'\n');tmp.replace(p)
def local(args):
    global local_cpu_seconds
    before=resource.getrusage(resource.RUSAGE_CHILDREN)
    subprocess.run([py,'-B',*args],check=True,env=env,cwd=job/'source')
    after=resource.getrusage(resource.RUSAGE_CHILDREN)
    local_cpu_seconds+=after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime
def start_pool(host):
    cmd=['taskset','-c','62','python3','-B',str(job/'ops/staged_pool.py'),'--job',str(job),'--host',host,
         '--cores',*map(str,range(workers[host]))]
    prefix=' '.join(shlex.quote(k)+'='+shlex.quote(v) for k,v in env.items() if k in
        ('PYTHONPATH','CLASHER_ROOT','CLASHER_EVAL_RUNTIME_ROOT','CLASHER_DELAY_NATIVE_DIR',
         'PYTHONDONTWRITEBYTECODE','OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','RAYON_NUM_THREADS','XDG_CACHE_HOME'))
    command=f'nohup setsid nice -n 10 chrt --idle 0 env {prefix} '+shlex.join(cmd)+f' > {job}/staged-pool-{host}.log 2>&1 < /dev/null & echo $! > {job}/staged-pool-{host}.pid'
    if host=='03':run(['bash','-c',command])
    else:ssh(host,command)
def monitor_pools(started):
    for h in started:
        path=job/'reporting/staged-r1/progress.json'
        response=path.read_text() if h=='03' and path.exists() else (ssh(h,f'test ! -f {path} || cat {path}') if h!='03' else '')
        if response:
            progress=json.loads(response);assert not progress['failures'],(h,progress['failures'])
        exitpath=job/'reporting/staged-r1/exit.json'
        text=exitpath.read_text() if h=='03' and exitpath.exists() else (ssh(h,f'test ! -f {exitpath} || cat {exitpath}') if h!='03' else '')
        if text:assert json.loads(text)['complete'],(h,'pool ended incomplete')
try:
    admitted=[];started={'03'};deadline=time.monotonic()+36*3600
    while len(admitted)<3:
        assert not (job/'CONTROLLER.STOP').exists() and not (job/'REPORTING.STOP').exists()
        monitor_pools(started)
        for arm,host in fit_hosts.items():
            if arm in admitted:continue
            text=ssh(host,f'test ! -f {job}/fits/{arm}/complete.json || cat {job}/fits/{arm}/complete.json')
            if not text:continue
            done=json.loads(text)
            if done['step']!=4883 or done['stopped']:continue
            segment=json.loads(ssh(host,f'cat {job}/fits/{arm}/segment.json'))
            if segment['status']!='returned' or segment['cursor_start']+segment['optimizer_steps']!=4883:continue
            if ssh(host,f'test ! -e /proc/{segment["pid"]} || echo active').strip():continue
            (job/'fits'/arm).mkdir(parents=True,exist_ok=True)
            run(['rsync','-a','--quiet',f'127x{host}:{job}/fits/{arm}/',str(job/'fits'/arm)+'/'])
            (job/'loader-qualification'/arm).mkdir(parents=True,exist_ok=True)
            run(['scp','-q',f'127x{host}:{job}/loader-qualification/{arm}/PASS.json',str(job/'loader-qualification'/arm)+'/'])
            if arm=='S-human':
                (job/'allocator-qualification/S-human').mkdir(parents=True,exist_ok=True)
                run(['scp','-q',f'127x{host}:{job}/allocator-qualification/S-human/PASS.json',str(job/'allocator-qualification/S-human')+'/'])
            local([str(job/'ops/staged_freeze.py'),'--job',str(job),'--stage',arm,'--arm',arm])
            freeze=job/'stage-freezes'/f'{arm}.json';cpu=cpu_hosts[arm]
            tasks=[]
            for i in range(600):
                if i<256:tasks.append(['h2h',arm,i])
                tasks.append(['fallback',arm,i])
            q=job/'stage-queues'/cpu;q.mkdir(parents=True,exist_ok=True)
            queue=q/f'100-{arm}.json';tmp=queue.with_suffix('.partial')
            tmp.write_text(json.dumps(dict(host=cpu,stage=arm,freeze=str(freeze),freeze_sha256=sha(freeze),tasks=tasks),indent=2)+'\n')
            if cpu!='03':
                for directory in ('ops','inputs','reporting-native-v1'):
                    run(['rsync','-a','--quiet',str(job/directory),f'127x{cpu}:{job}/'])
                ssh(cpu,f'mkdir -p {job}/stage-freezes {job}/stage-queues/{cpu} {job}/source/reports/explore/e1')
                run(['rsync','-a','--quiet',str(job/'source/reports/explore/e1')+'/',f'127x{cpu}:{job}/source/reports/explore/e1/'])
                run(['scp','-q',str(freeze),str(job/'pre-fit-pin.json'),str(job/'student-staged-reporting-amendment.json'),str(job/'student-reporting-native-amendment.json'),f'127x{cpu}:{job}/'])
                # The freeze must keep the same absolute path on every home host.
                run(['scp','-q',str(freeze),f'127x{cpu}:{job}/stage-freezes/'])
                run(['scp','-q',str(tmp),f'127x{cpu}:{job}/stage-queues/{cpu}/'])
                ssh(cpu,f'mv {job}/stage-queues/{cpu}/{tmp.name} {job}/stage-queues/{cpu}/{queue.name}')
            tmp.replace(queue)
            if cpu not in started:start_pool(cpu);started.add(cpu)
            admitted.append(arm)
        state('staged reporting games; awaiting remaining final EMAs',admitted=admitted,started_hosts=sorted(started),
              assigned_workers=workers,unused_reporting_host='08')
        if time.monotonic()>deadline:raise TimeoutError('final EMAs exceeded36h')
        if len(admitted)<3:time.sleep(30)
    report=job/'source/reports/strategy_council_20260928/imitation/exit-r1'
    local(['-m','imitation.exit_r1.freeze_screen','--plan',str(report/'STUDENT-SCREEN-PLAN.md'),
        '--plan-sha256','d98fdd74f2c59a23806aae1cfd85852016796d40f6d8d71e2ed6b3c9171b6138',
        '--seed-audit',str(report/'receipts/student-seed-audit.json'),'--init',str(job/'inputs/main02.pt'),
        '--S-mix',str(job/'fits/S-mix/step-00004883.pt'),'--S-teacher',str(job/'fits/S-teacher/step-00004883.pt'),
        '--S-human',str(job/'fits/S-human/step-00004883.pt'),'--native',str(job/'reporting-native-v1/clasher_core.abi3.so'),
        '--output',str(job/'execution-freeze.json')])
    f=json.loads((job/'execution-freeze.json').read_text())
    for path in (job/'inputs/assets.npz',job/'pre-fit-pin.json',job/'student-staged-reporting-amendment.json',job/'student-reporting-native-amendment.json',
                 report/'STUDENT-SCREEN-FREEZE-20261009.json'):f['files'][str(path)]=sha(path)
    (job/'execution-freeze.json').write_text(json.dumps(f,indent=2)+'\n');digest=sha(job/'execution-freeze.json')
    (job/'execution-freeze.sha256').write_text(digest+'\n')
    for host in started:
        if host=='03':(job/'stage-queues/03/DRAIN').touch()
        else:ssh(host,f'touch {job}/stage-queues/{host}/DRAIN')
    deadline=time.monotonic()+8*3600
    while True:
        monitor_pools(started);finished=[]
        for host in started:
            path=job/'reporting/staged-r1/exit.json'
            text=path.read_text() if host=='03' and path.exists() else (ssh(host,f'test ! -f {path} || cat {path}') if host!='03' else '')
            if text:
                e=json.loads(text);assert e['complete'] and e['own_workers_vacated'];finished.append(host)
        state('staged reporting games; all final EMAs sealed',finished_hosts=finished,freeze_sha256=digest)
        if len(finished)==3:break
        if time.monotonic()>deadline:raise TimeoutError('reporting exceeded8h')
        time.sleep(30)
    state('collecting staged reporting cases; analysis gate now open',freeze_sha256=digest)
    (job/'host-exits').mkdir(exist_ok=True)
    for host in ('01','04'):
        run(['rsync','-a','--quiet',f'127x{host}:{job}/stage-cases/',str(job/'stage-cases')+'/'])
        run(['scp','-q',f'127x{host}:{job}/reporting/staged-r1/exit.json',str(job/f'host-exits/{host}.json')])
    run(['cp',str(job/'reporting/staged-r1/exit.json'),str(job/'host-exits/03.json')])
    local([str(job/'ops/canonicalize_stages.py'),'--job',str(job)])
    local(['-m','imitation.exit_r1.pack','--roots',str(job/'heldout'),'--output',str(job/'heldout-corpus')])
    diag={}
    for arm in fit_hosts:
        local(['-m','imitation.exit_r1.screen','--freeze',str(job/'execution-freeze.json'),'--freeze-sha256',digest,
            '--mode','agreement','--arm',arm,'--teacher-store',str(job/'heldout-corpus'),
            '--assets',str(job/'inputs/assets.npz'),'--output',str(job/'agreement'),'--stop',str(job/'REPORTING.STOP')])
        diag[arm]=json.loads((job/'agreement'/f'{arm}.json').read_text())
        local([str(job/'ops/supplement.py'),'--job',str(job),'--freeze-sha256',digest,'--arm',arm])
    (job/'diagnostics.json').write_text(json.dumps(diag,indent=2)+'\n')
    local([str(job/'ops/supplement.py'),'--job',str(job),'--freeze-sha256',digest])
    state('complete',freeze_sha256=digest,aggregate_sha256=sha(job/'aggregate.json'))
    local([str(job/'ops/collect_results.py'),'--job',str(job)])
except Exception as e:
    (job/'REPORTING.STOP').touch()
    for host in ('01','04'):
        try:ssh(host,f'touch {job}/REPORTING.STOP')
        except Exception:pass
    state('failed',error=repr(e));raise
