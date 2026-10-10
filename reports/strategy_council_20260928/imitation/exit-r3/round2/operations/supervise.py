"""Owned fit process group: lease, reserve, process and deadline guards."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import re
import resource
import subprocess
import time

LEASED={'127x09','127x13','127x14','127x15','127x16'}
DEADLINE=1791695700  # 2026-10-11T05:15:00Z, leaves lease return margin.

def utc():return subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip()
def write(p,value):
    tmp=Path(str(p)+'.tmp');tmp.write_text(json.dumps(value,indent=2)+'\n');tmp.replace(p)
def tree(pid):
    result=[pid]
    i=0
    while i<len(result):
        p=result[i];i+=1
        try:result.extend(map(int,Path(f'/proc/{p}/task/{p}/children').read_text().split()))
        except FileNotFoundError:pass
    return result
def lease(host):
    d=json.loads(Path(f'/mpac/sdicks02/fleet-leases/{host}.json').read_text())
    from datetime import datetime,timezone
    end=datetime.fromisoformat(d['expected_end_utc'].replace('Z','+00:00'))
    if d.get('project')!='clasher' or not d.get('gpu') or d.get('reclaim') or d.get('refused') or end<=datetime.now(timezone.utc):
        raise RuntimeError('lease refuses GPU work')
    return d
def quiet08():
    p=Path.home()/'.config/fleet-top/quiet'
    return p.exists() and any(re.search(r'(?<!\d)(?:127x)?08(?!\d)', line.split('#',1)[0]) for line in p.read_text().splitlines())
def own_pss(pids):
    total=0
    for pid in pids:
        try:total+=int(next(s.split()[1] for s in Path(f'/proc/{pid}/smaps_rollup').read_text().splitlines() if s.startswith('Pss:')))*1024
        except (FileNotFoundError,ProcessLookupError):pass
    return total
def clasher_pids():
    result=[]
    for p in Path('/proc').iterdir():
        if not p.name.isdigit():continue
        try:
            cmd=(p/'cmdline').read_bytes().replace(b'\x00',b' ')
            if b'/mpac/sdicks02/jobs/clasher/' in cmd or b'/mpac/sdicks02/repos/clasher' in cmd:
                if not cmd.startswith((b'ssh ',b'sshd:',b'rsync ')):result.append(int(p.name))
        except (FileNotFoundError,ProcessLookupError,PermissionError):pass
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--job',required=True);p.add_argument('--arm',required=True)
    p.add_argument('--resume');a=p.parse_args();j=Path(a.job);host=socket.gethostname().split('.')[0]
    assert host in {'127x09','127x16','127x13'}
    assert os.getpriority(os.PRIO_PROCESS,0)>=10
    if host in LEASED:lease(host)
    f=json.loads((j/'freeze.json').read_text());audit=json.loads((j/'seed-audit.json').read_text())
    assert audit['passed'] and f['seed_audit_passed'] and f['committed_before_launch']
    assert f['arms'][a.arm]['host']==host
    if host=='127x08' and (quiet08() or time.time()>=1791609300):raise RuntimeError('08 quiet/deadline veto; do not launch')
    for relative,expected in f['files'].items():
        actual=hashlib.sha256((j/relative).read_bytes()).hexdigest()
        if actual!=expected:raise RuntimeError('frozen input changed: '+relative)
    pushed=json.loads((j/'prelaunch.json').read_text())
    assert pushed['pushed'] and pushed['freeze_sha256']==hashlib.sha256((j/'freeze.json').read_bytes()).hexdigest()
    occupied=subprocess.check_output(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader'],text=True).strip()
    if occupied:raise RuntimeError('GPU occupied; never preempt another job')
    command=['taskset','-c','118,119,126','bash',str(j/'ops/run_fit.sh'),a.arm]
    if a.resume:command.append(a.resume)
    started=time.monotonic();child=subprocess.Popen(command,start_new_session=True)
    write(j/f'{a.arm}-launch.json',dict(utc=utc(),host=host,supervisor_pid=os.getpid(),supervisor_pgid=os.getpgrp(),
        trainer_pid=child.pid,trainer_pgid=child.pid,command=command,stop_file=str(j/'FIT.STOP'),
        checkpoint_stop_deadline='2026-10-10T05:15:00Z' if host=='127x08' else '2026-10-11T05:15:00Z'))
    reason=None;stop_at=None;peak_pss=0;max_processes=0;minimum_free=1<<62
    def stop(cause):
        nonlocal reason,stop_at
        if reason is None:
            reason=cause;stop_at=time.monotonic()
            try:os.kill(child.pid,signal.SIGTERM)
            except ProcessLookupError:pass
    signal.signal(signal.SIGTERM,lambda *_:stop('supervisor SIGTERM'))
    signal.signal(signal.SIGINT,lambda *_:stop('supervisor SIGINT'))
    while child.poll() is None:
        try:
            if time.time()>=DEADLINE:stop('05:15Z deadline')
            if host=='127x08' and (quiet08() or time.time()>=1791609300):
                (j/'FIT.STOP').touch()
                stop('08 quiet/reclaim or Oct10 05:15Z stop; vacate by05:30Z')
            if (j/'FIT.STOP').exists():stop('owned FIT.STOP')
            if host in LEASED:lease(host)
            pids=tree(child.pid)+[os.getpid()];pss=own_pss(clasher_pids() if host in LEASED else pids);peak_pss=max(peak_pss,pss)
            free=int(subprocess.check_output(['nvidia-smi','--query-gpu=memory.free','--format=csv,noheader,nounits'],text=True).strip())*2**20
            minimum_free=min(minimum_free,free)
            count=len(clasher_pids()) if host in LEASED else len(pids);max_processes=max(max_processes,count)
            if host in LEASED and (pss>46_000_000_000 or count>16 or free<8*2**30):stop('leased resource floor')
            if stop_at is not None and time.monotonic()-stop_at>120:
                os.killpg(child.pid,signal.SIGKILL)
            write(j/f'{a.arm}-health.json',dict(utc=utc(),pid=child.pid,pss=pss,processes=count,
                gpu_free_bytes=free,reason=reason,wall_seconds=time.monotonic()-started))
        except Exception as e:stop(str(e))
        time.sleep(1 if host=='127x08' else 10)
    code=child.wait();own=resource.getrusage(resource.RUSAGE_SELF);kids=resource.getrusage(resource.RUSAGE_CHILDREN)
    write(j/f'{a.arm}-exit.json',dict(utc=utc(),exit_code=code,reason=reason,
        supervisor_cpu_seconds=own.ru_utime+own.ru_stime,trainer_tree_cpu_seconds=kids.ru_utime+kids.ru_stime,
        wall_seconds=time.monotonic()-started,peak_pss_bytes=peak_pss,max_processes=max_processes,min_gpu_free_bytes=minimum_free))
    raise SystemExit(code)

if __name__=='__main__':main()
