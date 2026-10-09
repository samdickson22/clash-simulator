"""Admit reporting stages as final EMAs seal; reduce only after all cases finish."""
import hashlib
import json
import os
from pathlib import Path
import resource
import shlex
import subprocess
import time
from requeue08_v2 import recover

job=Path('/mpac/sdicks02/jobs/clasher/exit-r1-student-screen-20261009-r1')
fit_hosts={'S-mix':'01','S-teacher':'04','S-human':'08'}
cpu_hosts={'S-mix':'01','S-teacher':'04','S-human':'03'}
workers={'03':56,'04':60,'01':44,'08':48}
reclaimed=set()
env=dict(os.environ,PYTHONPATH=str(job/'source')+':'+str(job/'source/src'),CLASHER_ROOT=str(job/'source'),
    CLASHER_EVAL_RUNTIME_ROOT=str(job/'source'),CLASHER_DELAY_NATIVE_DIR=str(job/'reporting-native-v1'),
    PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',
    RAYON_NUM_THREADS='1',XDG_CACHE_HOME=str(job/'cache'))
py='/mpac/sdicks02/repos/clasher/.venv/bin/python';local_cpu_seconds=0.
previous=json.loads((job/'controller.json').read_text())
assert previous['stage']=='staged reporting games; awaiting remaining final EMAs'
local_cpu_seconds=previous['local_cpu_seconds'];reclaimed=set(previous.get('reclaimed_hosts',[]))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def run(cmd):subprocess.run(cmd,check=True)
def ssh(host,cmd):return subprocess.check_output(['bash','-c',cmd] if host=='03' else ['ssh','127x'+host,cmd],text=True)
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
    assert not ssh(host,f'test ! -f {job}/staged-pool-r2-{host}.pid || test ! -e /proc/$(cat {job}/staged-pool-r2-{host}.pid) || echo active').strip()
    cmd=['taskset','-c','50' if host=='08' else '62','python3','-B',str(job/'ops/staged_pool_v3.py'),'--job',str(job),'--host',host,
         '--cores',*map(str,range(2,50) if host=='08' else range(workers[host]))]
    if host=='08':cmd+=['--stop',str(job/'REPORTING08.STOP')]
    prefix=' '.join(shlex.quote(k)+'='+shlex.quote(v) for k,v in env.items() if k in
        ('PYTHONPATH','CLASHER_ROOT','CLASHER_EVAL_RUNTIME_ROOT','CLASHER_DELAY_NATIVE_DIR',
         'PYTHONDONTWRITEBYTECODE','OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','RAYON_NUM_THREADS','XDG_CACHE_HOME'))
    command=f'nohup setsid nice -n {19 if host=="08" else 10} chrt --idle 0 env {prefix} '+shlex.join(cmd)+f' > {job}/staged-pool-r2-{host}.log 2>&1 < /dev/null & echo $! > {job}/staged-pool-r2-{host}.pid'
    if host=='03':run(['bash','-c',command])
    else:ssh(host,command)
def monitor_pools(started):
    for h in started:
        if h in reclaimed:continue
        stopping=h=='08' and bool(ssh(h,f'test ! -f {job}/REPORTING08.STOP || echo stop').strip())
        path=job/'reporting/staged-r2/progress.json'
        response=path.read_text() if h=='03' and path.exists() else (ssh(h,f'test ! -f {path} || cat {path}') if h!='03' else '')
        if response:
            progress=json.loads(response);assert stopping or not progress['failures'],(h,progress['failures'])
        exitpath=job/'reporting/staged-r2/exit.json'
        text=exitpath.read_text() if h=='03' and exitpath.exists() else (ssh(h,f'test ! -f {exitpath} || cat {exitpath}') if h!='03' else '')
        if text:
            exitinfo=json.loads(text)
            if h=='08' and stopping and not exitinfo['complete']:
                recover(job);reclaimed.add(h)
            else:assert exitinfo['complete'],(h,'pool ended incomplete')
try:
    admitted=list(previous['admitted']);started=set();
    for h in ('03','04','08'):
        if h in reclaimed:started.add(h);continue
        alive=ssh(h,f'test ! -f {job}/staged-pool-r2-{h}.pid || test ! -e /proc/$(cat {job}/staged-pool-r2-{h}.pid) || cat /proc/$(cat {job}/staged-pool-r2-{h}.pid)/cmdline')
        if alive:assert 'staged_pool_v3.py' in alive
        else:start_pool(h)
        started.add(h)
    deadline=time.monotonic()+36*3600
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
            available_hosts=[h for h in ('01','04','08','03') if h not in reclaimed]
            assignments={h:tasks[n::len(available_hosts)] for n,h in enumerate(available_hosts)} if arm=='S-mix' else {cpu:tasks}
            if arm=='S-teacher':
                assignments={'08':[t for t in tasks if t[2]<(128 if t[0]=='h2h' else 300)],
                             '04':[t for t in tasks if t[2]>=(128 if t[0]=='h2h' else 300)]}
            for cpu,assigned in assignments.items():
                q=job/'stage-queues-r2'/cpu;q.mkdir(parents=True,exist_ok=True)
                queue=q/f'100-{arm}.json';tmp=queue.with_suffix('.partial')
                tmp.write_text(json.dumps(dict(host=cpu,stage=arm,freeze=str(freeze),freeze_sha256=sha(freeze),tasks=assigned),indent=2)+'\n')
                if cpu!='03':
                    for directory in ('ops','inputs','reporting-native-v1'):
                        run(['rsync','-a','--quiet',str(job/directory),f'127x{cpu}:{job}/'])
                    ssh(cpu,f'mkdir -p {job}/stage-freezes {job}/stage-queues-r2/{cpu} {job}/source/reports/explore/e1 {job}/fits/{arm}')
                    run(['rsync','-a','--quiet',str(job/'source/reports/explore/e1')+'/',f'127x{cpu}:{job}/source/reports/explore/e1/'])
                    for name in ('pre-fit-pin.json','student-staged-reporting-amendment.json','student-reporting-native-amendment.json','student-reporting08-amendment.json','student-reporting-rebalance-amendment.json'):
                        run(['scp','-q',str(job/name),f'127x{cpu}:{job}/'])
                    if cpu!=host:run(['scp','-q',str(job/'fits'/arm/'step-00004883.pt'),f'127x{cpu}:{job}/fits/{arm}/'])
                    run(['scp','-q',str(freeze),f'127x{cpu}:{job}/stage-freezes/'])
                    run(['scp','-q',str(tmp),f'127x{cpu}:{job}/stage-queues-r2/{cpu}/'])
                    ssh(cpu,f'mv {job}/stage-queues-r2/{cpu}/{tmp.name} {job}/stage-queues-r2/{cpu}/{queue.name}')
                tmp.replace(queue)
                if cpu not in started:start_pool(cpu);started.add(cpu)
            admitted.append(arm)
        state('staged reporting games; awaiting remaining final EMAs',admitted=admitted,started_hosts=sorted(started),
              assigned_workers=workers,reporting08_stop=str(job/'REPORTING08.STOP'),reclaimed_hosts=sorted(reclaimed))
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
    for path in (job/'inputs/assets.npz',job/'pre-fit-pin.json',job/'student-staged-reporting-amendment.json',job/'student-reporting-native-amendment.json',job/'student-reporting08-amendment.json',job/'student-reporting-rebalance-amendment.json',job/'student-postprocessing-amendment.json',
                 report/'STUDENT-SCREEN-FREEZE-20261009.json'):f['files'][str(path)]=sha(path)
    (job/'execution-freeze.json').write_text(json.dumps(f,indent=2)+'\n');digest=sha(job/'execution-freeze.json')
    (job/'execution-freeze.sha256').write_text(digest+'\n')
    for host in started:
        if host=='03':continue  # Keep03 available until08 can no longer need requeue.
        else:ssh(host,f'touch {job}/stage-queues-r2/{host}/DRAIN')
    deadline=time.monotonic()+8*3600
    while True:
        monitor_pools(started);finished=[]
        if ssh('08',f'test ! -f {job}/reporting/staged-r2/exit.json || echo done').strip():
            (job/'stage-queues-r2/03/DRAIN').touch()
        for host in started:
            path=job/'reporting/staged-r2/exit.json'
            text=path.read_text() if host=='03' and path.exists() else (ssh(host,f'test ! -f {path} || cat {path}') if host!='03' else '')
            if text:
                e=json.loads(text);assert (e['complete'] or host in reclaimed) and e['own_workers_vacated'];finished.append(host)
        state('staged reporting games; all final EMAs sealed',finished_hosts=finished,freeze_sha256=digest)
        if len(finished)==len(started):break
        if time.monotonic()>deadline:raise TimeoutError('reporting exceeded8h')
        time.sleep(30)
    state('collecting staged reporting cases; analysis gate now open',freeze_sha256=digest)
    (job/'host-exits').mkdir(exist_ok=True)
    for host in ('03','01','04','08'):
        if host!='03':run(['rsync','-a','--quiet',f'127x{host}:{job}/stage-cases/',str(job/'stage-cases')+'/'])
        phases=[]
        for phase in ('staged-r1','staged-r2-startup-failed','staged-r2'):
            path=job/'reporting'/phase/'exit.json'
            content=(path.read_text() if path.exists() else '') if host=='03' else ssh(host,f'test ! -f {path} || cat {path}')
            if content:phases.append(dict(json.loads(content),phase=phase))
        assert phases and all(e['own_workers_vacated'] for e in phases)
        combined=dict(phases[-1],phases=phases,
            complete=all(e['complete'] or e.get('cost_only_failed_startup') or (host=='08' and e['stop_requested'] and host in reclaimed) for e in phases),
            completed=sum(e['completed'] for e in phases),tasks=sum(e['tasks'] for e in phases if not e.get('cost_only_failed_startup')),
            discarded_attempt_tasks=sum(e['tasks'] for e in phases if e.get('cost_only_failed_startup')),
            manager_cpu_seconds=sum(e['manager_cpu_seconds'] for e in phases),
            children_cpu_seconds=sum(e['children_cpu_seconds'] for e in phases),
            elapsed_seconds=sum(e['elapsed_seconds'] for e in phases),
            minimum_mem_available_bytes=min(e['minimum_mem_available_bytes'] for e in phases),
            peak_owned_processes=max(e['peak_owned_processes'] for e in phases),
            failures=[f for e in phases for f in e['failures']])
        (job/f'host-exits/{host}.json').write_text(json.dumps(combined,indent=2)+'\n')
    local([str(job/'ops/canonicalize_stages.py'),'--job',str(job)])
    local(['-m','imitation.exit_r1.pack','--roots',str(job/'heldout'),'--output',str(job/'heldout-corpus')])
    state('parallel frozen agreement diagnostics; all cases complete',freeze_sha256=digest)
    before=resource.getrusage(resource.RUSAGE_CHILDREN);processes=[]
    for arm,core in zip(fit_hosts,(58,59,60)):
        command=[py,'-B',str(job/'ops/arm_diagnostics.py'),'--job',str(job),
                 '--freeze-sha256',digest,'--arm',arm]
        stream=(job/f'agreement-{arm}.log').open('a')
        process=subprocess.Popen(['taskset','-c',str(core),*command],stdout=stream,stderr=subprocess.STDOUT,env=env,cwd=job/'source')
        processes.append((arm,process,stream))
    statuses=[]
    for arm,process,stream in processes:
        statuses.append((arm,process.wait()));stream.close()
    after=resource.getrusage(resource.RUSAGE_CHILDREN)
    local_cpu_seconds+=after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime
    assert all(rc==0 for arm,rc in statuses),statuses
    diag={arm:json.loads((job/'agreement'/f'{arm}.json').read_text()) for arm in fit_hosts}
    (job/'diagnostics.json').write_text(json.dumps(diag,indent=2)+'\n')
    local([str(job/'ops/supplement.py'),'--job',str(job),'--freeze-sha256',digest])
    state('complete',freeze_sha256=digest,aggregate_sha256=sha(job/'aggregate.json'))
    local([str(job/'ops/collect_results.py'),'--job',str(job)])
except Exception as e:
    (job/'REPORTING.STOP').touch()
    for host in ('01','04','08'):
        try:ssh(host,f'touch {job}/'+('REPORTING08.STOP' if host=='08' else 'REPORTING.STOP'))
        except Exception:pass
    state('failed',error=repr(e));raise
