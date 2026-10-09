"""Detached capacity process-tree guard; signals only verified owned PIDs."""
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time


def utc():
    return datetime.now(timezone.utc).isoformat()


def atomic(path, value):
    path = Path(path); tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, indent=2)+'\n'); tmp.replace(path)


def processes():
    rows = {}
    for p in Path('/proc').iterdir():
        if not p.name.isdigit():
            continue
        try:
            r = (p/'stat').read_text().rsplit(')', 1)[1].split()
            cmd = (p/'cmdline').read_bytes().replace(b'\0', b' ').decode(errors='replace')
            rows[int(p.name)] = dict(ppid=int(r[1]), start=r[19], state=r[0], nice=int(r[16]), cmd=cmd)
        except (OSError, ValueError, IndexError):
            pass
    return rows


def owned(rows, known):
    selected = {pid: start for pid, start in known.items()
                if pid in rows and rows[pid]['start']==start and rows[pid]['state']!='Z'}
    selected[os.getpid()] = rows[os.getpid()]['start']
    while True:
        new = {pid: r['start'] for pid, r in rows.items() if r['ppid'] in selected and r['state']!='Z'}
        if new.keys() <= selected.keys():
            return selected
        selected.update(new)


def send(known, sig):
    rows = processes()
    for pid, start in known.items():
        if pid!=os.getpid() and pid in rows and rows[pid]['start']==start:
            try:
                os.kill(pid, sig)
            except ProcessLookupError:
                pass


def main():
    work, label, *command = sys.argv[1:]; work = Path(work)
    host = socket.gethostname().split('.')[0]
    assert host in ('127x13', '127x14', '127x15', '127x16')
    os.nice(max(0, 10-os.getpriority(os.PRIO_PROCESS, 0)))
    lock = (work/'guard.lock').open('a'); fcntl.flock(lock, fcntl.LOCK_EX|fcntl.LOCK_NB)
    receipt = dict(label=label, host=host, started_at=utc(), supervisor_pid=os.getpid(), command=command)
    known = {}; child = None; stopping = None; reason = None
    peaks = dict(processes=0, pss_bytes=0); before=time.monotonic(); last_check=0
    def check(rows, selected):
        lease = json.loads(Path('/mpac/sdicks02/fleet-leases', host+'.json').read_text())
        assert lease['project']=='clasher' and lease['gpu'] and not lease.get('refused') and not lease.get('reclaim'), 'lease refusal/reclaim'
        assert lease['coordinator_thread']=='0523ae6f-baa3-4d4e-b233-b392671670db'
        now=datetime.now(timezone.utc)
        assert now < datetime.fromisoformat(lease['expected_end_utc'].replace('Z','+00:00')), 'lease expiry'
        assert now < datetime.fromisoformat('2026-10-11T03:30:00+00:00'), 'scan deadline'
        assert not (work/'STOP').exists(), 'owned STOP'
        # Add only this borrower's process footprints; never inspect owner paths.
        borrower = set(selected) | {pid for pid,r in rows.items()
                                  if r['state']!='Z' and '/mpac/sdicks02/' in r['cmd'] and 'clasher' in r['cmd']}
        assert len(borrower)<=min(16,int(lease['max_workers'])), 'borrower process cap'
        pss=0
        for pid in borrower:
            try:
                text=Path('/proc',str(pid),'smaps_rollup').read_text()
                pss+=sum(int(x.split()[1])*1024 for x in text.splitlines() if x.startswith('Pss:'))
            except (FileNotFoundError, ProcessLookupError):
                continue
        assert pss<=48_000_000_000, '48GB borrower PSS cap'
        assert all(rows[pid]['nice']>=10 for pid in selected), 'owned process nice cap'
        helper=Path.home()/'.local/bin/fleet-console-users'
        console=int(subprocess.check_output([str(helper)],text=True).strip()) if helper.exists() else 0
        free=min(int(x) for x in subprocess.check_output(
            ['nvidia-smi','--query-gpu=memory.free','--format=csv,noheader,nounits'],text=True).split())
        assert free>=8192, 'GPU headroom'
        peaks['processes']=max(peaks['processes'],len(borrower)); peaks['pss_bytes']=max(peaks['pss_bytes'],pss)
        atomic(work/(label+'-health.json'),dict(at=utc(), owned_pids=selected, borrower_processes=len(borrower),
               pss_bytes=pss, gpu_free_mib=free, console_users=console, peaks=peaks))
    try:
        rows=processes(); known=owned(rows,known); check(rows,known)
        child=subprocess.Popen(command, cwd=work/'source', start_new_session=True)
        receipt['pid']=child.pid; atomic(work/(label+'-launch.json'),receipt)
        while True:
            rows=processes(); known=owned(rows,known); now=time.monotonic()
            if now-last_check>=10:
                last_check=now
                try:
                    check(rows,known)
                except Exception as e:
                    if stopping is None:
                        reason=str(e); stopping=now; receipt['stop_requested_at']=utc()
                        send(known,signal.SIGTERM)
            if stopping is not None and now-stopping>=24*60:
                send(known,signal.SIGKILL)
            if child.poll() is not None:
                break
            time.sleep(1)
        receipt.update(exit_code=child.returncode,status='complete' if child.returncode==0 and reason is None else 'stopped',stop_reason=reason)
    except Exception as e:
        receipt.update(status='failed', error=str(e)); send(known,signal.SIGTERM)
        if child is not None:
            try:
                child.wait(timeout=60)
            except subprocess.TimeoutExpired:
                send(known,signal.SIGKILL); child.wait()
    finally:
        receipt.update(ended_at=utc(),wall_seconds=time.monotonic()-before,peaks=peaks)
        atomic(work/(label+'-exit.json'),receipt)
    if receipt['status']=='failed':
        raise SystemExit(1)


if __name__=='__main__':
    main()
