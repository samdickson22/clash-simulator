#!/usr/bin/env python3
"""One detached workload per host; lease/resource checks every 60s; verified PID cleanup."""
import datetime as dt
import fcntl
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time

BASE = Path('/mpac/sdicks02/repos/clasher-lease')
HOST = socket.gethostname().split('.')[0]
CAPS = {'127x11': 96, '127x13': 64, '127x14': 64, '127x16': 48, '127x18': 48, '127x09': 96, '127x15': 96}
LEASE = Path('/mpac/sdicks02/fleet-leases') / (HOST + '.json')
COORDINATOR = '0523ae6f-baa3-4d4e-b233-b392671670db'
CHECK_INTERVAL = 60
POLL_INTERVAL = 1
TERM_AFTER = 24 * 60
KILL_AFTER = 25 * 60
PSS_HOSTS = {'127x09', '127x15'}
CONSOLE_HELPER = Path.home() / '.local/bin/fleet-console-users'

def utc():
    return dt.datetime.now(dt.timezone.utc).isoformat()

def atomic(path, value):
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, indent=2) + '\n')
    tmp.replace(path)

def lease():
    value = json.loads(LEASE.read_text())
    assert HOST in CAPS and value.get('project') == 'clasher' and value.get('coordinator_thread') == COORDINATOR
    assert not value.get('refused') and not value.get('reclaim'), 'refused or reclaimed'
    assert dt.datetime.fromisoformat(value['expected_end_utc'].replace('Z', '+00:00')) > dt.datetime.now(dt.timezone.utc), 'expired'
    return value

def console_users():
    if HOST in PSS_HOSTS:
        output = subprocess.check_output([str(CONSOLE_HELPER)], text=True, timeout=15).strip()
        if not output.isdigit():
            raise ValueError('fleet-console-users did not return a nonnegative count')
        return int(output)
    return int(bool(subprocess.check_output(['who'], text=True).strip()))

def tree_pss(known):
    total = 0
    for pid, start in known.items():
        p = Path('/proc') / str(pid)
        try:
            if (p / 'stat').read_text().rsplit(')', 1)[1].split()[19] != start:
                continue
            value = None
            for line in (p / 'smaps_rollup').read_text().splitlines():
                if line.startswith('Pss:'):
                    value = int(line.split()[1]) * 1024
                    break
            if value is None:
                raise ValueError('Pss missing for verified PID ' + str(pid))
            if (p / 'stat').read_text().rsplit(')', 1)[1].split()[19] == start:
                total += value
        except (FileNotFoundError, ProcessLookupError):
            continue
    return total

def processes():
    rows = {}
    for p in Path('/proc').iterdir():
        if not p.name.isdigit():
            continue
        try:
            parts = (p / 'stat').read_text().rsplit(')', 1)[1].split()
            rows[int(p.name)] = (int(parts[1]), parts[19], int(parts[21]) * os.sysconf('SC_PAGE_SIZE'), parts[0])
        except (OSError, ValueError, IndexError):
            pass
    return rows

def owned(rows, known):
    # PID start times prevent signaling a recycled PID. Retain reparented descendants.
    selected = {pid: start for pid, start in known.items() if pid in rows and rows[pid][1] == start and rows[pid][3] != 'Z'}
    selected[os.getpid()] = rows[os.getpid()][1]
    while True:
        new = {pid: r[1] for pid, r in rows.items() if r[0] in selected and r[3] != 'Z'}
        if new.keys() <= selected.keys():
            break
        selected.update(new)
    return selected

def send(known, sig):
    rows = processes()
    for pid, start in known.items():
        if pid == os.getpid():
            continue
        if pid in rows and rows[pid][1] == start:
            try:
                os.kill(pid, sig)
            except ProcessLookupError:
                pass

def main():
    label, *command = sys.argv[1:]
    assert command and all(c.isalnum() or c in '._-' for c in label)
    os.nice(max(0, 10 - os.getpriority(os.PRIO_PROCESS, 0)))
    lock = (BASE / 'jobs/host-workload.lock').open('a')
    receipt = {'host': HOST, 'label': label, 'started_utc': utc(), 'command': command, 'supervisor_pid': os.getpid()}
    child = None
    known = {}
    stopping = None
    reason = None
    peak_count = peak_rss = peak_pss = 0
    pss = None
    console_count = None
    cap = None
    last_check = 0
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        current = lease()
        users = subprocess.check_output(['who'], text=True)
        console_count = console_users()
        print('who:', repr(users), 'console_users:', console_count, flush=True)
        child = subprocess.Popen(command, cwd=BASE / 'repo' if (BASE / 'repo').is_dir() else BASE, start_new_session=True)
        receipt['pid'] = child.pid
        while True:
            rows = processes()
            known = owned(rows, known)
            others = {pid: start for pid, start in known.items() if pid != os.getpid()}
            count = len(known)
            rss = sum(rows[pid][2] for pid in known if pid in rows)
            peak_count, peak_rss = max(count, peak_count), max(rss, peak_rss)
            now = time.monotonic()
            if now - last_check >= CHECK_INTERVAL:
                last_check = now
                try:
                    current = lease()
                    users = subprocess.check_output(['who'], text=True)
                    console_count = console_users()
                    cap = min(CAPS[HOST], int(current['max_workers']), 16 if users or console_count > 0 else 96)
                    assert count <= cap, 'process cap exceeded'
                    pss = tree_pss(known) if HOST in PSS_HOSTS else None
                    if pss is not None:
                        peak_pss = max(peak_pss, pss)
                    memory = pss if HOST in PSS_HOSTS else rss
                    assert not current.get('shared') or memory <= 64_000_000_000, '64 GB memory cap exceeded'
                    free = subprocess.check_output(['nvidia-smi', '--query-gpu=memory.free', '--format=csv,noheader,nounits'], text=True)
                    assert min(int(x) for x in free.split()) >= 8192, 'GPU free memory below 8 GiB'
                except Exception as exc:
                    if stopping is None:
                        stopping, reason = now, str(exc)
                        receipt['stop_requested_utc'] = utc()
                        print('STOP:', reason, flush=True)
                        # Default SIGTERM; checkpoint-aware jobs can opt into SIGUSR1.
                        checkpoint_signal = getattr(signal, os.environ.get('CLASHER_CHECKPOINT_SIGNAL', 'SIGTERM'))
                        if child.poll() is None:
                            os.kill(child.pid, checkpoint_signal)
                atomic(BASE / 'jobs' / (label + '.state.json'), {**receipt, 'checked_utc': utc(), 'processes': count, 'rss_bytes': rss, 'pss_bytes': pss, 'memory_metric': 'pss' if HOST in PSS_HOSTS else 'rss', 'console_users': console_count, 'effective_process_cap': cap, 'stop_reason': reason})
            if child.poll() is not None and not others:
                break
            if child.poll() is not None and stopping is None:
                stopping, reason = now, 'job exited with descendants still running'
                send(known, signal.SIGTERM)
            if stopping is not None:
                if now - stopping >= KILL_AFTER:
                    send(known, signal.SIGKILL)
                elif now - stopping >= TERM_AFTER:
                    send(known, signal.SIGTERM)
            time.sleep(POLL_INTERVAL)
        receipt.update(exit_code=child.returncode, status='stopped' if reason else ('pass' if child.returncode == 0 else 'fail'))
    except Exception as exc:
        receipt.update(status='fail', error=str(exc), exit_code=1)
        if child is not None:
            known = owned(processes(), known)
            send(known, signal.SIGTERM)
            time.sleep(2)
            send(known, signal.SIGKILL)
    finally:
        receipt.update(finished_utc=utc(), stop_reason=reason, peak_processes=peak_count, peak_rss_bytes=peak_rss, peak_sampled_pss_bytes=peak_pss if HOST in PSS_HOSTS else None, memory_metric='pss' if HOST in PSS_HOSTS else 'rss', console_users=console_count, effective_process_cap=cap)
        atomic(BASE / 'jobs' / (label + '.exit.json'), receipt)
        if reason:
            # Remove only our reclaimed/expired lease, after all tracked children have gone.
            rows = processes()
            alive = [pid for pid, start in known.items() if pid != os.getpid() and pid in rows and rows[pid][1] == start and rows[pid][3] != 'Z']
            try:
                value = json.loads(LEASE.read_text())
                expired = dt.datetime.fromisoformat(value['expected_end_utc'].replace('Z', '+00:00')) <= dt.datetime.now(dt.timezone.utc)
                if not alive and value.get('project') == 'clasher' and value.get('coordinator_thread') == COORDINATOR and (value.get('reclaim') or expired):
                    LEASE.unlink()
            except (OSError, ValueError, KeyError):
                pass
    return receipt.get('exit_code', 1) if not reason else 75

if __name__ == '__main__':
    sys.exit(main())
