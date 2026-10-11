"""X4S2 per-host supervisor (exploration, NEVER ADOPTABLE); copied from reports/explore/x4s/supervise.py.

Owns exactly one child process group (run.py + its fork pool). Polls every 10 s:
STOP file, hard stop time, host MemAvailable floor and the owned tree's PSS cap.
On any stop it signals only its own child process group, escalates to SIGKILL,
verifies that the group is empty and exits; it never uses pattern kills.
"""
import argparse, datetime, hashlib, json, os, resource, signal, socket, subprocess, time
from pathlib import Path


def utc(): return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
def who():
    try: return subprocess.run(['who'], capture_output=True, text=True, timeout=5).stdout
    except Exception as exc: return f'who failed: {exc!r}'
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def meminfo(key='MemAvailable:'):
    return int(next(x.split()[1] for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith(key)))*1024


def group(pgid):
    pids = []
    for d in Path('/proc').iterdir():
        if d.name.isdigit():
            try:
                if int((d/'stat').read_text().rsplit(')', 1)[1].split()[2]) == pgid:
                    pids.append(int(d.name))
            except (FileNotFoundError, ProcessLookupError, IndexError, ValueError):
                pass
    return pids


def pss(pids):
    total = 0
    for pid in pids:
        try:
            for line in Path(f'/proc/{pid}/smaps_rollup').read_text().splitlines():
                if line.startswith('Pss:'):
                    total += int(line.split()[1])*1024
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            pass
    return total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--job', type=Path, required=True)
    ap.add_argument('--phase', required=True)
    ap.add_argument('--worklist', type=Path, required=True)
    ap.add_argument('--workers', type=int)
    ap.add_argument('--config', type=Path)
    ap.add_argument('--stop-at', required=True)
    a = ap.parse_args()
    job = a.job
    host = socket.gethostname()
    assert host in ('127x03', '127x08') and os.sched_getaffinity(0) == {62}
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19 and os.sched_getscheduler(0) == os.SCHED_OTHER
    stop_at = datetime.datetime.strptime(a.stop_at, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=datetime.timezone.utc)
    console = who()
    workers = a.workers or (10 if console.strip() else 12)
    assert 1 <= workers <= 12
    out = job/a.phase
    assert not out.exists(), 'fresh output directory per phase'
    out.mkdir()
    # Per-host ceilings from the assignment: 08 must be empty by 09:30Z, 03 by 13:30Z.
    ceiling = {'127x08': '2026-10-11T09:25:00Z', '127x03': '2026-10-11T13:30:00Z'}[host]
    assert a.stop_at <= ceiling, (a.stop_at, ceiling)
    config = a.config or job/'repo/reports/explore/x4s2/plan.json'
    cmd = ['taskset', '-c', f'0-{workers*5-1}', 'bash', str(job/'repo/reports/explore/x4s2/runtime.sh'),
           'reports/explore/x4s2/run.py', '--config', str(config), '--out', str(out),
           '--workers', str(workers), '--worklist', str(a.worklist)]
    if (job/'STOP').exists():
        (out/'stop-reason.json').write_text(json.dumps(dict(utc=utc(), reason='STOP present before launch'))+'\n')
        raise SystemExit(3)
    t0 = time.monotonic(); before = resource.getrusage(resource.RUSAGE_CHILDREN)
    reason = None; min_mem = meminfo(); max_pss = 0
    log = (out/'worker.log').open('a')
    child = subprocess.Popen(cmd, stdout=log, stderr=log, stdin=subprocess.DEVNULL, start_new_session=True)
    pgid = child.pid
    (out/'launch.json').write_text(json.dumps(dict(
        utc=utc(), host=host, supervisor_pid=os.getpid(), supervisor_pgid=os.getpgrp(), child_pid=child.pid,
        child_pgid=pgid, command=cmd, who=console, workers=workers, slot_physical_cpus=list(range(workers*5)),
        worklist_sha256=sha(a.worklist), config_sha256=sha(config), stop_at=a.stop_at), indent=2)+'\n')

    requested = []
    def stop(why):
        # Bounded: <=45 s TERM grace + <=60 s KILL grace; idempotent.
        nonlocal reason
        if reason is not None:
            return
        reason = why
        (out/'stop-reason.json').write_text(json.dumps(dict(utc=utc(), reason=reason))+'\n')
        for sig, grace in ((signal.SIGTERM, 45), (signal.SIGKILL, 60)):
            try:
                os.killpg(pgid, sig)
            except ProcessLookupError:
                pass
            end = time.monotonic()+grace
            while time.monotonic() < end:
                child.poll()
                if not group(pgid):
                    return
                time.sleep(1)

    # Handlers only record the request; the main loop performs the bounded stop.
    signal.signal(signal.SIGTERM, lambda s, f: requested.append('supervisor_SIGTERM'))
    signal.signal(signal.SIGINT, lambda s, f: requested.append('supervisor_SIGINT'))
    rc = None
    try:
        while True:
            if requested:
                stop(requested[0]); break
            if child.poll() is not None:
                if group(pgid):
                    stop('runner_exited_with_live_workers')
                break
            mem = meminfo(); min_mem = min(min_mem, mem)
            tree = pss(group(pgid)); max_pss = max(max_pss, tree)
            if (job/'STOP').exists():
                stop('owned_STOP'); break
            if datetime.datetime.now(datetime.timezone.utc) >= stop_at:
                stop('hard_stop_time'); break
            if mem < 24*2**30 or tree > 50*2**30:
                stop('memory_guard'); break
            progress = dict(utc=utc(), host=host, phase=a.phase, completed_games=len(list((out/'games').glob('*.json'))),
                            complete_blocks=len(list((out/'blocks').glob('*.json'))), memavailable_GiB=mem/2**30,
                            owned_pss_GiB=tree/2**30, child_pgid=pgid, workers=workers, who=who())
            tmp = out/'progress.tmp'; tmp.write_text(json.dumps(progress)+'\n'); tmp.replace(out/'progress.json')
            with (out/'census.jsonl').open('a') as census:
                census.write(json.dumps(progress)+'\n')
            for _ in range(10):
                if requested or child.poll() is not None or (job/'STOP').exists():
                    break
                time.sleep(1)
    except BaseException as exc:
        stop(f'supervisor_exception: {exc!r}')
    finally:
        if group(pgid):
            stop(reason or 'supervisor_finally')
            if group(pgid):  # stop() returns early if already stopping; force once more
                try: os.killpg(pgid, signal.SIGKILL)
                except ProcessLookupError: pass
                time.sleep(2)
        rc = child.poll()
    left = group(pgid)
    after = resource.getrusage(resource.RUSAGE_CHILDREN); own = resource.getrusage(resource.RUSAGE_SELF)
    result = dict(utc=utc(), host=host, returncode=rc, reason=reason, remaining_group_pids=left,
                  min_memavailable_GiB=min_mem/2**30, max_owned_pss_GiB=max_pss/2**30,
                  wall_seconds=time.monotonic()-t0,
                  children_cpu_seconds=after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,
                  parent_cpu_seconds=own.ru_utime+own.ru_stime,
                  complete_blocks=len(list((out/'blocks').glob('*.json'))))
    (out/'supervisor-exit.json').write_text(json.dumps(result, indent=2)+'\n')
    raise SystemExit(0 if (rc == 0 and reason is None) else 1)


if __name__ == '__main__':
    main()
