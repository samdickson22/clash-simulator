#!/usr/bin/env python3
"""Shared lease accounting. Only signal descendants started by this supervisor.

The v1 lock is observed through /proc/locks, never opened or flocked. A separate
short-lived exclusive flock serializes v2 admissions and aggregate snapshots.
Resource checks are a sampled backstop, as in v1, rather than kernel quotas.
"""
import argparse
from contextlib import contextmanager
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import sys
import time

BASE = Path('/mpac/sdicks02/repos/clasher-lease')
HOST = socket.gethostname().split('.')[0]
LEASE = Path('/mpac/sdicks02/fleet-leases') / (HOST + '.json')
POLICY = Path('/mpac/sdicks02/cc/FLEET-SHARING.md')
# The command-center policy is not mounted on all leased hosts. This is the
# extracted limits text read there for this additive deployment. A local live
# policy, if present, always supersedes this snapshot. No extra host file needed.
POLICY_SNAPSHOT = '''Total worker processes per host ≤96 of 128, ≤16 if `~/.local/bin/fleet-console-users` reports a console user. It counts seats that are unlocked or recently active, plus other users' remote logins; `-v` explains each session. Everything nice 10+.
GPU borrowers leave ≥8 GB of GPU memory free.
The owner keeps its own processes within 128 − max_workers − 16 headroom, and the borrower keeps memory ≤ 64 GB of the ~125 GB, measured as PSS summed over the borrower's process tree.
'''
POLICY_SNAPSHOT_ORIGINAL_SHA256 = 'd6b20afa8aecc0c8c69bcdf094adc6e930fff6ffc1e34342a72f56a67aa8fd0b'
COORDINATOR = '0523ae6f-baa3-4d4e-b233-b392671670db'
HOST_CAPS = {'127x09': 80, '127x11': 96, '127x13': 80,
             '127x14': 80, '127x15': 80, '127x16': 96}
CONSOLE_HELPER = Path.home() / '.local/bin/fleet-console-users'
CHECK_INTERVAL = 60
POLL_INTERVAL = 1
TERM_AFTER = 24 * 60
KILL_AFTER = 25 * 60
STOP_AT = dt.datetime(2026, 10, 9, 4, 30, tzinfo=dt.timezone.utc)
EXIT_BY = dt.datetime(2026, 10, 9, 5, 0, tzinfo=dt.timezone.utc)


def utc():
    return dt.datetime.now(dt.timezone.utc)


def stamp():
    return utc().isoformat()


def atomic(path, value):
    tmp = path.with_name(path.name + '.' + str(os.getpid()) + '.tmp')
    tmp.write_text(json.dumps(value, indent=2) + '\n')
    tmp.replace(path)


@contextmanager
def accounting():
    with (BASE / 'jobs/aggregate-v2.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        path = BASE / 'jobs/aggregate-v2.json'
        value = json.loads(path.read_text()) if path.exists() else {
            'version': 2, 'jobs': {}, 'next_sequence': 0, 'last_check': 0}
        if value.get('version') != 2:
            raise ValueError('unknown aggregate registry version')
        try:
            yield value
        finally:
            atomic(path, value)


def timestamp(value):
    parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('lease timestamps must include a timezone')
    return parsed


def read_lease():
    value = json.loads(LEASE.read_text())
    if HOST not in HOST_CAPS or value.get('project') != 'clasher' or value.get('coordinator_thread') != COORDINATOR:
        raise ValueError('wrong host, borrower or coordinator')
    if value.get('refused') or value.get('reclaim'):
        raise ValueError('refused or reclaimed')
    if timestamp(value['expected_end_utc']) <= utc():
        raise ValueError('expired lease')
    if int(value['max_workers']) <= 0:
        raise ValueError('invalid lease process cap')
    return value


def limits(current, users, policy):
    # Read the live agreement, but never relax the stricter limits in this brief.
    # Missing/unrecognizable controls fail closed instead of silently ignoring it.
    def number(pattern):
        match = re.search(pattern, policy)
        if not match:
            raise ValueError('unrecognized fleet sharing policy: ' + pattern)
        return int(match.group(1))
    procs = number(r'Total worker processes per host\s*≤\s*(\d+)')
    console = number(r'≤\s*(\d+)\s+if\s+`~/.local/bin/fleet-console-users`')
    memory = number(r'borrower keeps memory\s*≤\s*(\d+)\s*GB') * 1_000_000_000
    nice = number(r'Everything nice\s+(\d+)\+')
    gpu = number(r'GPU borrowers leave\s*≥\s*(\d+)\s*GB') * 1024
    return {'processes': min(HOST_CAPS[HOST], int(current['max_workers']), procs,
                             min(console, 16) if users else 96),
            'pss_bytes': min(memory, 64_000_000_000),
            'nice': max(nice, 10), 'gpu_free_mib': max(gpu, 8192)}


def console_users():
    output = subprocess.check_output([str(CONSOLE_HELPER)], text=True, timeout=15).strip()
    if not output.isdigit():
        raise ValueError('fleet-console-users did not return a nonnegative count')
    return int(output)


def read_policy():
    try:
        return POLICY.read_text(), str(POLICY)
    except FileNotFoundError:
        return POLICY_SNAPSHOT, 'bundled FLEET-SHARING.md limits snapshot (2026-10-08)'


def processes():
    # pid -> (ppid, start ticks, rss bytes, state, nice). No owner paths inspected.
    rows = {}
    for p in Path('/proc').iterdir():
        if not p.name.isdigit():
            continue
        try:
            parts = (p / 'stat').read_text().rsplit(')', 1)[1].split()
            rows[int(p.name)] = (int(parts[1]), parts[19],
                                int(parts[21]) * os.sysconf('SC_PAGE_SIZE'),
                                parts[0], int(parts[16]))
        except (FileNotFoundError, ProcessLookupError):
            continue
    return rows


def expand(rows, known):
    selected = {int(pid): start for pid, start in known.items()
                if int(pid) in rows and rows[int(pid)][1] == start and rows[int(pid)][3] != 'Z'}
    while True:
        new = {pid: row[1] for pid, row in rows.items()
               if row[0] in selected and row[3] != 'Z' and pid not in selected}
        if not new:
            return selected
        selected.update(new)


def tree_pss(known):
    total = 0
    for pid, start in known.items():
        p = Path('/proc') / str(pid)
        try:
            if (p / 'stat').read_text().rsplit(')', 1)[1].split()[19] != start:
                continue
            value = next((int(line.split()[1]) * 1024
                          for line in (p / 'smaps_rollup').read_text().splitlines()
                          if line.startswith('Pss:')), None)
            if value is None:
                raise ValueError('PSS missing for verified PID ' + str(pid))
            if (p / 'stat').read_text().rsplit(')', 1)[1].split()[19] == start:
                total += value
        except (FileNotFoundError, ProcessLookupError):
            continue
    return total


def legacy_holders():
    path = BASE / 'jobs/host-workload.lock'
    if not path.exists():
        return []
    stat = path.stat()
    key = (os.major(stat.st_dev), os.minor(stat.st_dev), stat.st_ino)
    result = []
    for line in Path('/proc/locks').read_text().splitlines():
        fields = line.split()
        if len(fields) < 8 or fields[1:4] != ['FLOCK', 'ADVISORY', 'WRITE']:
            continue
        major, minor, inode = fields[5].split(':')
        if (int(major, 16), int(minor, 16), int(inode)) == key:
            pid = int(fields[4])
            if pid <= 0:
                raise ValueError('v1 lock has an unidentifiable holder')
            result.append(pid)
    return result


def refresh(registry, rows, discover=False):
    jobs = registry['jobs']
    for pid in legacy_holders():
        if pid not in rows or rows[pid][3] == 'Z':
            continue
        key = 'v1:' + str(pid) + ':' + rows[pid][1]
        jobs.setdefault(key, {'kind': 'v1', 'known': {str(pid): rows[pid][1]},
                              'sequence': -1, 'supervisor_pid': pid})
    for key, job in list(jobs.items()):
        known = expand(rows, job['known'])
        if not known:
            del jobs[key]
        else:
            job['known'] = {str(pid): start for pid, start in known.items()}
    if discover:
        # Also count unwrapped Clasher processes/sidecars in this footprint.
        # Only our UID's argv is read, never any repository/job/cache of the owner.
        covered = {int(pid) for job in jobs.values() for pid in job['known']}
        for pid, row in rows.items():
            if pid in covered or pid == os.getpid() or row[3] == 'Z':
                continue
            path = Path('/proc') / str(pid)
            try:
                if path.stat().st_uid != os.getuid():
                    continue
                argv = (path / 'cmdline').read_bytes().split(b'\0')
            except (FileNotFoundError, ProcessLookupError):
                continue
            # Pending launchers haven't acquired capacity yet; serialized
            # admission accounts for each of them before starting a workload.
            if str(BASE / 'lease_watch_v2.py').encode() in argv or str(BASE / 'run_v2.sh').encode() in argv:
                continue
            if any(arg.startswith((str(BASE) + '/').encode()) for arg in argv):
                key = 'external:' + str(pid) + ':' + row[1]
                jobs[key] = {'kind': 'external', 'sequence': -1,
                             'known': {str(p): s for p, s in expand(rows, {pid: row[1]}).items()}}


def measure(registry, rows):
    seen = set()
    total_count = total_pss = 0
    for job in registry['jobs'].values():
        known = {int(pid): start for pid, start in job['known'].items() if int(pid) not in seen}
        seen.update(known)
        job['processes'] = len(known)
        job['pss_bytes'] = tree_pss(known)
        job['rss_bytes'] = sum(rows[pid][2] for pid in known)
        job['minimum_nice'] = min((rows[pid][4] for pid in known), default=10)
        total_count += job['processes']
        total_pss += job['pss_bytes']
    return {'processes': total_count, 'pss_bytes': total_pss}


def reserved_usage(jobs):
    # Reserving the greater of declaration and usage prevents concurrent small
    # startups from all consuming the same spare capacity when they later grow.
    return {metric: sum(max(job.get(metric, 0), job.get('declared_' + metric, 0))
                        for job in jobs.values())
            for metric in ('processes', 'pss_bytes')}


def admission(jobs, cap, declared_processes, declared_pss):
    used = reserved_usage(jobs)
    for metric, amount in (('processes', declared_processes), ('pss_bytes', declared_pss)):
        if used[metric] + amount > cap[metric]:
            raise ValueError('admission exceeds aggregate ' + metric + ' cap: ' +
                             str(used[metric]) + ' + ' + str(amount) + ' > ' + str(cap[metric]))
    return used


def mark_stop(job, reason):
    if job.get('kind') == 'v2' and not job.get('stop_reason'):
        job.update(stop_reason=reason, stop_requested_utc=stamp(), stop_requested_epoch=time.time())


def newest_victims(jobs, cap):
    remaining = {metric: sum(job.get(metric, 0) for job in jobs.values()
                             if not job.get('stop_reason'))
                 for metric in ('processes', 'pss_bytes')}
    victims = []
    for key, job in sorted(jobs.items(), key=lambda item: item[1]['sequence'], reverse=True):
        if all(remaining[metric] <= cap[metric] for metric in remaining):
            break
        if job['kind'] != 'v2' or job.get('stop_reason'):
            continue
        victims.append(key)
        for metric in remaining:
            remaining[metric] -= job.get(metric, 0)
    return victims


def deadlines(current):
    end = timestamp(current['expected_end_utc'])
    return min(STOP_AT, end - dt.timedelta(hours=1)), min(EXIT_BY, end - dt.timedelta(minutes=30))


def check_all(registry, rows):
    registry['last_check'] = time.time()
    try:
        refresh(registry, rows, discover=True)
        aggregate = measure(registry, rows)
        registry['aggregate'] = aggregate
        current = read_lease()
        users = console_users()
        policy, source = read_policy()
        cap = limits(current, users, policy)
        registry.update(console_users=users, limits=cap, policy_source=source,
                        policy_controls_sha256=hashlib.sha256(policy.encode()).hexdigest())
        stop_at, exit_by = deadlines(current)
        registry.update(stop_at_utc=stop_at.isoformat(), exit_by_utc=exit_by.isoformat())
        if utc() >= stop_at:
            raise ValueError('scheduled checkpoint deadline reached')
        for job in registry['jobs'].values():
            if job['kind'] != 'v2':
                continue
            if job['processes'] > job['declared_processes']:
                mark_stop(job, 'declared process cap exceeded')
            if job['pss_bytes'] > job['declared_pss_bytes']:
                mark_stop(job, 'declared PSS cap exceeded')
            if job['minimum_nice'] < cap['nice']:
                mark_stop(job, 'nice below required minimum')
        for key in newest_victims(registry['jobs'], cap):
            mark_stop(registry['jobs'][key], 'aggregate cap exceeded; newest admitted first')
        gpu_jobs = [job for job in registry['jobs'].values() if job['kind'] == 'v2' and job.get('gpu')]
        if gpu_jobs:
            if not current.get('gpu'):
                raise ValueError('lease does not permit GPU work')
            free = subprocess.check_output(['nvidia-smi', '--query-gpu=memory.free',
                                            '--format=csv,noheader,nounits'], text=True, timeout=15)
            if not free.split() or min(int(x) for x in free.split()) < cap['gpu_free_mib']:
                for job in gpu_jobs:
                    mark_stop(job, 'GPU free memory below 8 GiB')
        registry['check_error'] = None
    except Exception as exc:
        registry['check_error'] = str(exc)
        for job in registry['jobs'].values():
            mark_stop(job, str(exc))
    registry['checked_utc'] = stamp()


def send(known, sig):
    rows = processes()
    for pid, start in known.items():
        pid = int(pid)
        if pid != os.getpid() and pid in rows and rows[pid][1] == start and rows[pid][3] != 'Z':
            try:
                os.kill(pid, sig)
            except ProcessLookupError:
                pass


def return_lease_if_idle(registry):
    """V1 return semantics, with the additional host-wide idle requirement."""
    refresh(registry, processes(), discover=True)
    if registry['jobs']:
        return
    try:
        value = json.loads(LEASE.read_text())
        ours = value.get('project') == 'clasher' and value.get('coordinator_thread') == COORDINATOR
        expired = timestamp(value['expected_end_utc']) <= utc()
        if ours and (value.get('reclaim') or expired):
            LEASE.unlink()
    except (OSError, ValueError, KeyError):
        pass


def supervise(args, child, receipt, known, key):
    stopping = None
    reason = None
    peak_count = peak_rss = peak_pss = 0
    last_state = None
    cap = None
    users = None
    aggregate = None
    exit_by = timestamp(receipt['exit_by_utc'])
    try:
        while True:
            rows = processes()
            known = expand(rows, known)
            count = len(known)
            rss = sum(rows[pid][2] for pid in known)
            peak_count, peak_rss = max(peak_count, count), max(peak_rss, rss)
            now = time.monotonic()
            with accounting() as registry:
                refresh(registry, rows)
                own = registry['jobs'][key]
                # Refresh all known descendants every second, including reparented
                # ones, but sample PSS and external controls once per minute.
                if time.time() - registry['last_check'] >= CHECK_INTERVAL:
                    check_all(registry, rows)
                cap, users = registry.get('limits'), registry.get('console_users')
                aggregate = registry.get('aggregate')
                exit_by = min(exit_by, timestamp(registry.get('exit_by_utc', receipt['exit_by_utc'])))
                stop_at = timestamp(registry.get('stop_at_utc', receipt['stop_at_utc']))
                if utc() >= stop_at:
                    mark_stop(own, 'scheduled checkpoint deadline reached')
                if count > args.max_processes:
                    mark_stop(own, 'declared process cap exceeded')
                peak_pss = max(peak_pss, own.get('pss_bytes', 0))
                if own.get('stop_reason') and stopping is None:
                    # Preserve elapsed reclaim time if another supervisor detected it.
                    elapsed = max(0, time.time() - own['stop_requested_epoch'])
                    stopping, reason = now - elapsed, own['stop_reason']
                    receipt['stop_requested_utc'] = own['stop_requested_utc']
                    print('STOP:', reason, flush=True)
                    if child.poll() is None:
                        send({child.pid: known.get(child.pid)}, args.checkpoint_signal)
                checked = registry.get('checked_utc')
                if checked != last_state or reason:
                    last_state = checked
                    atomic(BASE / 'jobs' / (args.label + '.state.json'), {
                        **receipt, 'checked_utc': stamp(), 'processes': count,
                        'rss_bytes': rss, 'pss_bytes': own.get('pss_bytes'),
                        'memory_metric': 'pss', 'console_users': users,
                        'effective_process_cap': cap['processes'] if cap else None,
                        'aggregate': aggregate, 'accounted_jobs': job_summary(registry), 'stop_reason': reason})
            child_exited = child.poll() is not None
            # poll() can reap a child that was live in the earlier /proc
            # snapshot. That child alone is not a surviving descendant.
            others = {pid: start for pid, start in known.items()
                      if pid != os.getpid() and not (child_exited and pid == child.pid)}
            if child_exited and not others:
                break
            if child_exited and stopping is None:
                stopping, reason = now, 'job exited with descendants still running'
                receipt['stop_requested_utc'] = stamp()
                send(known, signal.SIGTERM)
                with accounting() as registry:
                    mark_stop(registry['jobs'][key], reason)
            if utc() >= exit_by or (stopping is not None and now - stopping >= KILL_AFTER):
                send(known, signal.SIGKILL)
            elif stopping is not None and now - stopping >= TERM_AFTER:
                send(known, signal.SIGTERM)
            time.sleep(POLL_INTERVAL)
        receipt.update(exit_code=child.returncode,
                       status='stopped' if reason else ('pass' if child.returncode == 0 else 'fail'))
    except Exception as exc:
        receipt.update(status='fail', error=str(exc), exit_code=1)
        # Unexpected accounting/measurement errors still take the v1 checkpoint
        # path; never release capacity while verified descendants remain alive.
        reason = reason or ('supervision error: ' + str(exc))
        receipt.setdefault('stop_requested_utc', stamp())
        send(known, args.checkpoint_signal)
        stopping = time.monotonic()
        while True:
            known = expand(processes(), known)
            if child.poll() is not None and not [pid for pid in known if pid != os.getpid()]:
                break
            elapsed = time.monotonic() - stopping
            if elapsed >= KILL_AFTER or utc() >= exit_by:
                send(known, signal.SIGKILL)
            elif elapsed >= TERM_AFTER:
                send(known, signal.SIGTERM)
            time.sleep(POLL_INTERVAL)
    finally:
        receipt.update(finished_utc=stamp(), stop_reason=reason, peak_processes=peak_count,
                       peak_rss_bytes=peak_rss, peak_sampled_pss_bytes=peak_pss,
                       memory_metric='pss', console_users=users, aggregate=aggregate,
                       effective_process_cap=cap['processes'] if cap else None)
        atomic(BASE / 'jobs' / (args.label + '.exit.json'), receipt)
        with accounting() as registry:
            registry['jobs'].pop(key, None)
            registry['last_check'] = 0
            if reason:
                return_lease_if_idle(registry)
    return 75 if reason else receipt.get('exit_code', 1)


def job_summary(registry):
    return {key: {field: job.get(field) for field in
                  ('kind', 'sequence', 'supervisor_pid', 'processes', 'pss_bytes', 'stop_reason')}
            for key, job in registry['jobs'].items()}


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--max-processes', type=int, required=True, help='includes supervisor and ALL descendants')
    parser.add_argument('--expected-pss-gb', type=float, required=True, help='hard job PSS cap, decimal GB; includes supervisor')
    parser.add_argument('--gpu', action='store_true', help='enforce GPU permission and 8192 MiB free reserve')
    parser.add_argument('--foreground', action='store_true', help='stay attached (for diagnostics/tests)')
    parser.add_argument('label')
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    if args.command[:1] == ['--']:
        args.command = args.command[1:]
    if not re.fullmatch(r'[a-zA-Z0-9._-]+', args.label) or not args.command:
        parser.error('provide a fresh safe label and a command after --')
    if args.max_processes < 2 or not 0 < args.expected_pss_gb <= 64:
        parser.error('declare at least 2 processes and 0 < PSS GB <= 64')
    args.pss_bytes = int(args.expected_pss_gb * 1_000_000_000)
    args.checkpoint_signal = getattr(signal, os.environ.get('CLASHER_CHECKPOINT_SIGNAL', 'SIGTERM'))
    if args.checkpoint_signal not in (signal.SIGTERM, signal.SIGUSR1, signal.SIGUSR2, signal.SIGINT):
        parser.error('checkpoint signal must be SIGTERM, SIGUSR1, SIGUSR2 or SIGINT')
    return args


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    os.nice(max(0, 10 - os.getpriority(os.PRIO_PROCESS, 0)))
    (BASE / 'jobs').mkdir(exist_ok=True)
    receipt = {'version': 2, 'host': HOST, 'label': args.label, 'command': args.command,
               'started_utc': stamp(), 'declared_processes': args.max_processes,
               'declared_pss_bytes': args.pss_bytes, 'gpu': args.gpu}
    admitted = False
    child = None
    try:
        with accounting() as registry:
            if any((BASE / 'jobs' / (args.label + suffix)).exists()
                   for suffix in ('.launch.pid', '.exit.json', '.state.json', '.log')):
                raise FileExistsError('Use a fresh label')
            check_all(registry, processes())
            if registry.get('check_error'):
                raise ValueError(registry['check_error'])
            current = read_lease()
            if args.gpu and not current.get('gpu'):
                raise ValueError('lease does not permit GPU work')
            if not args.gpu and current.get('gpu_only'):
                raise ValueError('lease permits GPU work only')
            cap = registry['limits']
            if any(job.get('minimum_nice', 10) < cap['nice'] for job in registry['jobs'].values()):
                raise ValueError('existing Clasher process below nice minimum')
            receipt['admission_usage'] = admission(registry['jobs'], cap, args.max_processes, args.pss_bytes)
            if args.gpu:
                free = subprocess.check_output(['nvidia-smi', '--query-gpu=memory.free',
                                                '--format=csv,noheader,nounits'], text=True, timeout=15)
                if not free.split() or min(int(x) for x in free.split()) < cap['gpu_free_mib']:
                    raise ValueError('GPU free memory below 8 GiB')
            if any(job.get('stop_reason') for job in registry['jobs'].values()):
                raise ValueError('host has stopping jobs; retry after their receipts')
            os.nice(max(0, cap['nice'] - os.getpriority(os.PRIO_PROCESS, 0)))
            receipt.update(policy_source=registry['policy_source'],
                           policy_controls_sha256=registry['policy_controls_sha256'],
                           bundled_policy_original_sha256=POLICY_SNAPSHOT_ORIGINAL_SHA256,
                           stop_at_utc=registry['stop_at_utc'], exit_by_utc=registry['exit_by_utc'],
                           admission_aggregate=registry['aggregate'], admission_jobs=job_summary(registry))
            if not args.foreground:
                pid = os.fork()
                if pid:
                    # Parent must not unlock the flock shared with its fork;
                    # closing its copy preserves the child's serialized startup.
                    print('pid=' + str(pid) + ' log=' + str(BASE / 'jobs' / (args.label + '.log')), flush=True)
                    # _exit skips the accounting context's atomic write. A
                    # normal return would race the child's registry update.
                    os._exit(0)
                os.setsid()
                with (BASE / 'jobs' / (args.label + '.log')).open('x') as log, open(os.devnull) as devnull:
                    os.dup2(devnull.fileno(), 0)
                    os.dup2(log.fileno(), 1)
                    os.dup2(log.fileno(), 2)
            receipt['supervisor_pid'] = os.getpid()
            rows = processes()
            known = {os.getpid(): rows[os.getpid()][1]}
            registry['next_sequence'] += 1
            key = 'v2:' + args.label
            registry['jobs'][key] = {'kind': 'v2', 'sequence': registry['next_sequence'],
                'supervisor_pid': os.getpid(), 'known': {str(pid): start for pid, start in known.items()},
                'declared_processes': args.max_processes, 'declared_pss_bytes': args.pss_bytes, 'gpu': args.gpu}
            receipt['admission_sequence'] = registry['next_sequence']
            admitted = True
            child = subprocess.Popen(args.command, cwd=BASE / 'repo' if (BASE / 'repo').is_dir() else BASE,
                                     start_new_session=True)
            receipt['pid'] = child.pid
            rows = processes()
            if child.pid in rows:
                known[child.pid] = rows[child.pid][1]
            registry['jobs'][key]['known'] = {str(pid): start for pid, start in known.items()}
            (BASE / 'jobs' / (args.label + '.launch.pid')).write_text(str(os.getpid()) + '\n')
            registry['last_check'] = 0
        return supervise(args, child, receipt, known, key)
    except Exception as exc:
        if admitted and child is not None:
            # Hand startup failures to the same checkpoint/cleanup path.
            receipt.update(error=str(exc))
            with accounting() as registry:
                mark_stop(registry['jobs'][key], 'startup error: ' + str(exc))
            return supervise(args, child, receipt, known, key)
        receipt.update(status='fail', error=str(exc), exit_code=1, finished_utc=stamp())
        # Never overwrite another job's receipts on duplicate-label rejection.
        if not isinstance(exc, FileExistsError):
            atomic(BASE / 'jobs' / (args.label + '.exit.json'), receipt)
        if admitted:
            with accounting() as registry:
                registry['jobs'].pop(key, None)
        print('REFUSED:', str(exc), file=sys.stderr, flush=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
