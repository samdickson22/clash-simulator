"""Continue the frozen screen after all three final EMA fits have completed."""
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import time
import resource

job=Path('/mpac/sdicks02/jobs/clasher/exit-r1-student-screen-20261009-r1')
hosts={'S-mix':'01','S-teacher':'04','S-human':'09'}
cpu_hosts=('03','04','01')  # 08 stays completely free for perception.
def state(stage,**kw):
    p=job/'controller.json';t=p.with_suffix('.partial')
    t.write_text(json.dumps(dict(stage=stage,utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),**kw),indent=2)+'\n');t.replace(p)
def run(cmd):subprocess.run(cmd,check=True)
def ssh(host,cmd):return subprocess.check_output(['ssh',f'127x{host}',cmd],text=True)
env=dict(os.environ,PYTHONPATH=str(job/'source')+':'+str(job/'source/src'),
    CLASHER_ROOT=str(job/'source'),CLASHER_EVAL_RUNTIME_ROOT=str(job/'source'),
    CLASHER_DELAY_NATIVE_DIR=str(job/'native'),PYTHONDONTWRITEBYTECODE='1',
    OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',RAYON_NUM_THREADS='1',
    XDG_CACHE_HOME=str(job/'cache'))
py='/mpac/sdicks02/repos/clasher/.venv/bin/python'
local_cpu_seconds=0.
def local(args):
    global local_cpu_seconds
    before=resource.getrusage(resource.RUSAGE_CHILDREN)
    subprocess.run([py,'-B',*args],check=True,env=env,cwd=job/'source')
    after=resource.getrusage(resource.RUSAGE_CHILDREN)
    local_cpu_seconds += after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime
try:
    # Admission and fitting remain guarded by each host's live lease/resource rules.
    # Slow cold mmap gathering must not cause the reporting waiter to abandon a fit.
    deadline=time.monotonic()+36*3600
    while True:
        if (job/'CONTROLLER.STOP').exists():raise InterruptedError('owned controller STOP')
        ready=[]
        for arm,host in hosts.items():
            response=ssh(host,f'test ! -f {job}/fits/{arm}/complete.json || cat {job}/fits/{arm}/complete.json')
            if response:
                receipt=json.loads(response)
                assert receipt['step']==4883 and not receipt['stopped'],(arm,receipt)
                ready.append(arm)
        state('waiting for final EMA fits',finished=ready)
        if len(ready)==3:break
        if time.monotonic()>deadline:raise TimeoutError('fits did not finish within 36 hours')
        time.sleep(30)
    state('collecting final checkpoints')
    for arm,host in hosts.items():
        (job/'fits'/arm).mkdir(parents=True,exist_ok=True)
        run(['rsync','-a','--quiet',f'127x{host}:{job}/fits/{arm}/',str(job/'fits'/arm)+'/'])
    (job/'inputs').mkdir(exist_ok=True)
    run(['scp','-q',f'127x01:{job}/inputs/main02.pt',f'127x01:{job}/inputs/assets.npz',
         f'127x01:{job}/inputs/assets.npz.json',str(job/'inputs')+'/'])
    (job/'native').mkdir(exist_ok=True)
    run(['cp','/mpac/sdicks02/jobs/clasher/exit-r1-20261009-r1/native/clasher_core.abi3.so',str(job/'native')+'/'])
    report=job/'source/reports/strategy_council_20260928/imitation/exit-r1'
    local(['-m','imitation.exit_r1.freeze_screen','--plan',str(report/'STUDENT-SCREEN-PLAN.md'),
        '--plan-sha256','d98fdd74f2c59a23806aae1cfd85852016796d40f6d8d71e2ed6b3c9171b6138',
        '--seed-audit',str(report/'receipts/student-seed-audit.json'),
        '--init',str(job/'inputs/main02.pt'),
        '--S-mix',str(job/'fits/S-mix/step-00004883.pt'),
        '--S-teacher',str(job/'fits/S-teacher/step-00004883.pt'),
        '--S-human',str(job/'fits/S-human/step-00004883.pt'),
        '--native',str(job/'native/clasher_core.abi3.so'),'--output',str(job/'execution-freeze.json')])
    f=json.loads((job/'execution-freeze.json').read_text())
    for p in (job/'inputs/assets.npz',job/'pre-fit-pin.json',report/'STUDENT-SCREEN-FREEZE-20261009.json'):
        f['files'][str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
    (job/'execution-freeze.json').write_text(json.dumps(f,indent=2)+'\n')
    digest=hashlib.sha256((job/'execution-freeze.json').read_bytes()).hexdigest()
    (job/'execution-freeze.sha256').write_text(digest+'\n')
    tasks={h:[] for h in cpu_hosts}
    for i in range(64):tasks['03'].append(['teacher','init',i])
    for i in range(256):
        for arm in hosts:tasks[cpu_hosts[i%3]].append(['h2h',arm,i])
    for i in range(600):
        for arm in ('init',*hosts):tasks[cpu_hosts[i%3]].append(['fallback',arm,i])
    for host in cpu_hosts:(job/f'tasks-{host}.json').write_text(json.dumps(tasks[host])+'\n')
    for host in ('01','04'):
        for directory in ('source','ops','fits','inputs','native'):
            run(['rsync','-a','--quiet',str(job/directory),f'127x{host}:{job}/'])
        run(['scp','-q',str(job/'execution-freeze.json'),str(job/'pre-fit-pin.json'),
             str(job/f'tasks-{host}.json'),f'127x{host}:{job}/'])
    state('reporting games',freeze_sha256=digest,counts={h:len(v) for h,v in tasks.items()},
          assigned_workers={'03':60,'04':60,'01':44},unused_host='08')
    for host in cpu_hosts:
        cores=list(range(44 if host=='01' else 60))
        cmd=['taskset','-c','62','python3','-B',str(job/'ops/pool.py'),'--job',str(job),
             '--tasks',str(job/f'tasks-{host}.json'),'--cores',*map(str,cores),
             '--freeze-sha256',digest,'--label','frozen-r1']
        prefix=' '.join(shlex.quote(k)+'='+shlex.quote(v) for k,v in env.items()
                        if k in ('PYTHONPATH','CLASHER_ROOT','CLASHER_EVAL_RUNTIME_ROOT',
                                 'CLASHER_DELAY_NATIVE_DIR','PYTHONDONTWRITEBYTECODE',
                                 'OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','RAYON_NUM_THREADS','XDG_CACHE_HOME'))
        command=f'nohup setsid nice -n 10 chrt --idle 0 env {prefix} '+shlex.join(cmd)+f' > {job}/pool.log 2>&1 < /dev/null & echo $! > {job}/pool.pid'
        if host=='03':run(['bash','-c',command])
        else:ssh(host,command)
    deadline=time.monotonic()+8*3600
    while True:
        finished=[]
        for host in cpu_hosts:
            p=job/'reporting/frozen-r1/exit.json'
            text=p.read_text() if host=='03' and p.exists() else (ssh(host,f'test ! -f {p} || cat {p}') if host!='03' else '')
            if text:
                r=json.loads(text);assert r['complete'] and r['own_workers_vacated'],(host,r)
                finished.append(host)
        state('reporting games',freeze_sha256=digest,finished_hosts=finished)
        if len(finished)==3:break
        if time.monotonic()>deadline:raise TimeoutError('reporting games exceeded 8 hours')
        if (job/'CONTROLLER.STOP').exists():raise InterruptedError('owned controller STOP')
        time.sleep(30)
    state('collecting reporting cases',freeze_sha256=digest)
    for host in ('01','04'):
        run(['rsync','-a','--quiet',f'127x{host}:{job}/cases/',str(job/'cases')+'/'])
        (job/'host-exits').mkdir(exist_ok=True)
        run(['scp','-q',f'127x{host}:{job}/reporting/frozen-r1/exit.json',str(job/f'host-exits/{host}.json')])
    run(['cp',str(job/'reporting/frozen-r1/exit.json'),str(job/'host-exits/03.json')])
    local(['-m','imitation.exit_r1.pack','--roots',str(job/'heldout'),'--output',str(job/'heldout-corpus')])
    diag={}
    for arm in hosts:
        local(['-m','imitation.exit_r1.screen','--freeze',str(job/'execution-freeze.json'),
            '--freeze-sha256',digest,'--mode','agreement','--arm',arm,
            '--teacher-store',str(job/'heldout-corpus'),'--assets',str(job/'inputs/assets.npz'),
            '--output',str(job/'agreement'),'--stop',str(job/'REPORTING.STOP')])
        diag[arm]=json.loads((job/'agreement'/f'{arm}.json').read_text())
        local([str(job/'ops/supplement.py'),'--job',str(job),'--freeze-sha256',digest,'--arm',arm])
    (job/'diagnostics.json').write_text(json.dumps(diag,indent=2)+'\n')
    local([str(job/'ops/supplement.py'),'--job',str(job),'--freeze-sha256',digest])
    state('complete',freeze_sha256=digest,aggregate_sha256=hashlib.sha256((job/'aggregate.json').read_bytes()).hexdigest(),
          local_cpu_seconds=local_cpu_seconds)
    local([str(job/'ops/collect_results.py'),'--job',str(job)])
except Exception as e:
    previous=json.loads((job/'controller.json').read_text()) if (job/'controller.json').exists() else {}
    if 'reporting' in previous.get('stage',''):
        (job/'REPORTING.STOP').touch()
        for host in ('01','04'):
            try:ssh(host,f'touch {job}/REPORTING.STOP')
            except Exception:pass
    state('failed',error=repr(e));raise
