"""X4S-4 supervisor on 127x01 (exploration, NEVER ADOPTABLE). r3 after Sol script review r2.

Derived from the X4S-3 supervisor (one child process group = the runner and its fork pool; polls every 10 s).
X4S-4 behaviour:
  * --script: the child is the unchanged x4s3/run.py (default) or x4s4/collect.py (same CLI). The child gets
    X4S4_SUPERVISOR=<pid>:<starttime>; collect.py refuses to run without it and stops its own group if this
    supervisor disappears (R2-F8 monitor death).
  * All I/O goes through x4s4io (R2-F1): --job must be the canonical job, --phase a fresh confined relative path,
    every file is created exclusively, replaced atomically or appended without following links.
  * Admission (R2-F3, R3-F2), immediately before spawning: MemAvailable >= 24 GiB, memory PSI readable and <= 10, and
    the study tree plus this phase's workers <= 70 processes with the job <= 100 GB.
  * Live stops (R2-F3): STOP (lexists), the study hard stop (--stop-at must equal <job>/HARD-STOP-UTC.txt, T+24 h),
    MemAvailable < 24 GiB or unreadable, the child group's PSS > 50 GiB or unreadable, the study tree > 70 processes
    or > 100 GB, a console user (yield). Stops signal verified PIDs of the owned child group only (TERM, then KILL).
  * Census rows every poll (C5/R2-9/E7): psi_some_avg10 and foreign_cores_host (host busy CPU over the interval
    minus the X4S-4 tree's own CPU, own processes keyed by (pid, starttime)); None when unreadable or non-finite; a
    baseline before the child starts and a final row at exit; reduced_concurrency.
  * Collection (x4s4/collect.py on bank C): the C7b parity watch runs INSIDE this loop every 300 s over every
    collection phase of the arm; out of band (>= 100 block-proved games per evaluated arm) writes a PARITY-PAUSE
    receipt, creates <job>/STOP and stops with reason parity_pause; a watch failure stops with parity_monitor_failed.
Exit status: 0 only if the child exited 0 with no stop reason; 1 otherwise; 3 if it never launched.
"""
import argparse, datetime, hashlib, json, math, os, resource, signal, socket, sys, threading, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import x4s4io as io                                   # noqa: E402
import studytree                                       # noqa: E402

PHASE_ROLES = ('games', 'collect', 'qual', 'smoke')
PARITY_PERIOD, PARITY_MIN_GAMES = 300, 100
FLEET_CONSOLE = '/home/sdicks02/.local/bin/fleet-console-users'


def utc(): return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def who():
    try: return io.run_checked(['/usr/bin/who'], 5, 1 << 16, env={'LC_ALL': 'C'}).stdout.decode('utf-8', 'replace')
    except io.Refusal as exc: return f'who failed: {exc}'


def console_users():
    try: return int(io.run_checked([FLEET_CONSOLE], 10, 4096, env={'LC_ALL': 'C', 'PATH': '/usr/bin:/bin'}).stdout.split()[0])
    except (io.Refusal, ValueError, IndexError): return 0 if not who().strip() else 1   # helper failed: plain who


def host_busy_ticks():
    """Host-wide busy CPU ticks (user+nice+system+irq+softirq+steal) from /proc/stat; None if unreadable."""
    try:
        with open('/proc/stat') as f: v = [int(x) for x in f.readline().split()[1:]]
        return v[0]+v[1]+v[2]+v[5]+v[6]+v[7]
    except Exception:
        return None


def own_tree_ticks(job):
    """{(pid, starttime): utime+stime} for live processes of the X4S-4 tree."""
    out = {}
    for pid in studytree.processes(studytree.groups(job)):
        st = io.proc_stat(pid)
        if st: out[(pid, st['starttime'])] = st['utime']+st['stime']
    return out


class ForeignCensus:
    """Foreign CPU over an interval = host busy-tick delta minus the X4S-4 tree's tick delta (Sol r1 F7). An own
    process first seen in the interval contributes all its ticks; one that exited contributes nothing more, so its
    last partial interval counts as foreign (conservative). Unreadable or non-finite -> None (a BAD interval)."""
    def __init__(self, job):
        self.job = job; self.t = self.busy = self.own = None
        self.sample()                                        # baseline before the first census interval

    def sample(self):
        hz = os.sysconf('SC_CLK_TCK'); t = time.monotonic(); busy = host_busy_ticks()
        own = own_tree_ticks(self.job)
        value = None
        if busy is not None and self.busy is not None and self.t is not None and t > self.t:
            own_delta = sum(v-self.own.get(k, 0) for k, v in own.items())
            value = max(0.0, (busy-self.busy-own_delta)/hz/(t-self.t))
            if not math.isfinite(value): value = None
        self.t, self.busy, self.own = t, busy, own
        return value


def collection_phases(job, phase_dir):
    """Every collection phase of this arm: <job>/collect/<arm>/a*."""
    arm_dir = os.path.dirname(phase_dir)
    return [arm_dir+'/'+n for n in io.listdir(arm_dir) if n.startswith('a') and io.is_real_dir(arm_dir+'/'+n)]


def admit_phase(job, add, stop_at=None):
    """R3-F2/R4-F2: admission immediately before the child is spawned - also for direct collection/qualification
    calls, not only driver launches: no STOP (lexists), the study hard stop not reached (both the --stop-at value and
    <job>/HARD-STOP-UTC.txt), MemAvailable >= 24 GiB and memory PSI readable and <= 10 (dispatch inhibition only), and
    the study tree + this phase's processes <= 70 with the job <= 100 GB. Returns None or the refusal reason."""
    why = studytree.watchdog_ok(job)                    # SR-1: no study work without the external watchdog
    if why: return 'admission: watchdog: '+why
    if io.lexists(job+'/STOP'): return 'admission: STOP present'
    if studytree.hard_stop_passed(job) or (stop_at is not None and datetime.datetime.now(datetime.timezone.utc) >= stop_at):
        return 'admission: study hard stop reached'
    why = studytree.admit(job, add)                     # R7-F2: one bounded measurement, then STOP/deadline LAST
    if why: return why
    if stop_at is not None and datetime.datetime.now(datetime.timezone.utc) >= stop_at: return 'admission: study hard stop reached'
    return None


def guard_reason(why):
    """Map a studytree verdict onto the supervisor's declared guard-stop reasons (PERMITTED stops)."""
    if why in ('owned_STOP', 'hard_stop_time', 'monitor_stale'): return why
    if why.startswith('study_tree_cap'): return 'study_tree_cap'
    if why == 'measurement_timeout' or why.startswith('enforcer_failed'): return 'monitor_stale'
    return 'memory_guard'                                # memory, PSS or PSI unreadable


def final_reason(job):
    """R7-F1: before a clean exit is recorded - a fresh bounded resource verdict, then STOP/deadline LAST."""
    why = studytree.fresh_verdict(job)
    return guard_reason(why) if why else None


def final_check(job, stop_at):
    """R5-F1: the cheap STOP/deadline check repeated immediately before io.spawn, after every slow step."""
    if io.lexists(job+'/STOP'): return 'final: STOP present'
    if studytree.hard_stop_passed(job) or datetime.datetime.now(datetime.timezone.utc) >= stop_at:
        return 'final: study hard stop reached'
    return None


def parity_watch(job, out):
    """One C7b watch step for a collection phase: None if in band, else the stop reason (pause or monitor failure)."""
    try:
        import qualify4
        res = qualify4.parity_once(collection_phases(job, out), PARITY_MIN_GAMES, require_both=False)
    except Exception as exc:
        return f'parity_monitor_failed: {exc!r}'
    if res['out_of_band']:
        qualify4.pause(job, res); return 'parity_pause'
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--job', required=True)
    ap.add_argument('--rt', required=True)
    ap.add_argument('--phase', required=True)
    ap.add_argument('--range', choices=['reporting', 'smoke', 'qualification'], required=True)
    ap.add_argument('--indices', required=True)
    ap.add_argument('--workers', type=int)
    ap.add_argument('--config')
    ap.add_argument('--arms', nargs='+')
    ap.add_argument('--stop-at', required=True)
    ap.add_argument('--script', default='reports/explore/x4s3/run.py',
                    choices=['reports/explore/x4s3/run.py', 'reports/explore/x4s4/collect.py'])
    a = ap.parse_args()
    job = a.job
    if job != io.JOB: raise SystemExit(f'--job must be {io.JOB}')
    io.check_rel(a.phase)
    out = f'{job}/{a.phase}'
    io.check_writable(out, roles=PHASE_ROLES, must_not_exist=True)          # before any mutation (R2-F1)
    host = socket.gethostname()
    if not (host == '127x01' and os.sched_getaffinity(0) == set(range(50))): raise SystemExit('supervise.py: requires 127x01 on cores 0-49')
    if not (os.getpriority(os.PRIO_PROCESS, 0) == 10 and os.sched_getscheduler(0) == os.SCHED_OTHER): raise SystemExit('supervise.py: requires nice 10, SCHED_OTHER')
    if os.environ.get('X4S4_STUDY') != job or 'X4S4_READOUT' in os.environ:
        raise SystemExit(f'supervise.py requires X4S4_STUDY={job} and no X4S4_READOUT (the watchdog study markers)')
    if a.stop_at != studytree.hard_stop_at(job).strftime('%Y-%m-%dT%H:%M:%SZ'): raise SystemExit('--stop-at must equal <job>/HARD-STOP-UTC.txt')
    stop_at = datetime.datetime.strptime(a.stop_at, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=datetime.timezone.utc)
    console = who(); seats = console_users()
    config = a.config or a.rt+'/repo/reports/explore/x4s3/plan.json'
    cfg = io.read_json(config, 4 << 20)
    arms = a.arms or list(cfg['arms'])
    width = 1 if all(cfg['arms'][x]['threads'] == 1 for x in arms) else 5
    workers = a.workers or (50//width)
    if seats: workers = min(workers, 16//width)              # <=16 game processes with a console user
    if not (1 <= workers*width <= 50): raise SystemExit('supervise.py: 1 <= workers*width <= 50 required')
    collecting = a.script.endswith('collect.py') and a.range == 'reporting'
    if collecting and not a.phase.startswith('collect/'): raise SystemExit('bank-C collection phases live under collect/')
    io.mkdirs(out, roles=PHASE_ROLES)
    if io.lexists(job+'/STOP'):
        io.replace_json(out+'/stop-reason.json', dict(utc=utc(), reason='STOP present before launch'), roles=PHASE_ROLES)
        raise SystemExit(3)
    why = admit_phase(job, workers*width+3, stop_at)        # runner + pool + this supervisor (reservation)
    if why:
        io.replace_json(out+'/stop-reason.json', dict(utc=utc(), reason=why), roles=PHASE_ROLES)
        raise SystemExit(3)
    me = io.own_identity()
    rt_runtime = a.rt+'/repo/reports/explore/x4s3/runtime.sh'
    cmd = ['/usr/bin/taskset', '-c', f'0-{workers*width-1}', '/bin/bash', rt_runtime,
           a.script, '--config', config, '--out', out, '--workers', str(workers), '--indices', a.indices, '--range', a.range]
    if a.arms: cmd += ['--arms', *a.arms]
    env = dict(os.environ, X4S3_RT=a.rt, X4S4_SUPERVISOR=f"{me['pid']}:{me['starttime']}")
    t0 = time.monotonic(); before = resource.getrusage(resource.RUSAGE_CHILDREN)
    reason = None; min_mem = studytree.mem_available() or 0; max_pss = 0
    census_cpu = ForeignCensus(job)                                   # host/own baseline before the child exists
    late = final_check(job, stop_at)                                  # R5-F1: after the slow admission and census
    if late:
        io.replace_json(out+'/stop-reason.json', dict(utc=utc(), reason=late), roles=PHASE_ROLES)
        raise SystemExit(3)
    child = io.spawn(cmd, out+'/worker.log', env, roles=PHASE_ROLES)
    proc, pgid, cstart = child['popen'], child['pgid'], child['starttime']
    io.write_json_once(out+'/launch.json', dict(
        utc=utc(), host=host, supervisor_pid=me['pid'], supervisor_pgid=me['pgid'], supervisor_starttime=me['starttime'],
        child_pid=proc.pid, child_pgid=pgid, child_starttime=cstart, command=cmd, who=console, console_seats=seats,
        workers=workers, lane_width=width, slot_physical_cpus=list(range(workers*width)), runtime=a.rt,
        indices_sha256=io.sha256_file(a.indices), config_sha256=io.sha256_file(config), stop_at=a.stop_at, script=a.script),
        roles=PHASE_ROLES, mode=0o444)

    requested = []; stop_lock = threading.Lock()
    def stop(why):
        nonlocal reason
        with stop_lock:                                               # main loop and the Enforcer thread
            if reason is not None: return
            reason = why
        io.replace_json(out+'/stop-reason.json', dict(utc=utc(), reason=reason), roles=PHASE_ROLES)
        io.stop_owned(pgid, cstart)                                   # verified PIDs of the owned child group only
    # R7-F2: independent expiry - STOP, the deadline, or no completed loop iteration (all measurements) for
    # MONITOR_STALE s stops the child from the Enforcer thread, even while the loop is blocked in a measurement.
    enforcer = studytree.Enforcer(job, lambda why: stop(guard_reason(why))).start()

    signal.signal(signal.SIGTERM, lambda s, f: requested.append('supervisor_SIGTERM'))
    signal.signal(signal.SIGINT, lambda s, f: requested.append('supervisor_SIGINT'))
    rc = None; last_parity = time.monotonic()

    def census_row(final):
        nonlocal min_mem, max_pss
        mem = studytree.mem_available(); tree = studytree.pss_bytes(io.owned_pids(pgid, cstart))
        if mem is not None: min_mem = min(min_mem, mem)
        if tree is not None: max_pss = max(max_pss, tree)
        seats_now = console_users()
        row = dict(utc=utc(), host=host, phase=a.phase, final=final,
                   complete_blocks=len([n for n in io.listdir(out+'/blocks')]) if io.is_real_dir(out+'/blocks') else 0,
                   memavailable_GiB=None if mem is None else mem/2**30, owned_pss_GiB=None if tree is None else tree/2**30,
                   psi_some_avg10=studytree.psi_some_avg10(), foreign_cores_host=census_cpu.sample(),
                   child_pgid=pgid, workers=workers, full_workers=50//width, console_seats=seats_now,
                   reduced_concurrency=bool(workers < 50//width or seats_now))
        io.replace_json(out+'/progress.json', row, roles=PHASE_ROLES)
        io.append_json_line(out+'/census.jsonl', row, roles=PHASE_ROLES)

    try:
        while True:
            if reason is not None: break                              # the Enforcer stopped the child
            if requested: stop(requested[0]); break
            if proc.poll() is not None:
                if io.owned_pids(pgid, cstart): stop('runner_exited_with_live_workers')
                break
            mem = studytree.mem_available(); tree = studytree.pss_bytes(io.owned_pids(pgid, cstart))
            if io.lexists(job+'/STOP'): stop('owned_STOP'); break
            if datetime.datetime.now(datetime.timezone.utc) >= stop_at: stop('hard_stop_time'); break
            if mem is None or mem < studytree.MEM_FLOOR or tree is None or tree > studytree.PSS_LIMIT:
                stop('memory_guard'); break                            # also unreadable memory/PSS (fail closed)
            ok, why = studytree.admission(job, 0)
            if not ok: stop('study_tree_cap'); break
            enforcer.verdict(None)                                    # each bounded measurement block completed

            if not seats and console_users(): stop('console_user'); break
            if collecting and time.monotonic()-last_parity >= PARITY_PERIOD:
                last_parity = time.monotonic()
                why = parity_watch(job, out)
                if why: stop(why); break
                enforcer.verdict(None)
            census_row(final=False)
            enforcer.verdict(None)                                    # a complete, healthy iteration
            for _ in range(10):
                if requested or proc.poll() is not None or io.lexists(job+'/STOP'): break
                time.sleep(1)
    except BaseException as exc:
        stop(f'supervisor_exception: {exc!r}')
    finally:
        enforcer.stop()
        if io.owned_pids(pgid, cstart): stop(reason or 'supervisor_finally')
        rc = proc.poll()
        if rc is None:
            try: rc = proc.wait(timeout=30)
            except Exception: rc = None
        try: census_row(final=True)                                   # cover the final interval
        except Exception: pass
    left = io.owned_pids(pgid, cstart)
    if reason is None and rc == 0 and not left:
        reason = final_reason(job)                                    # R7-F1: fresh guards before a clean exit
    after = resource.getrusage(resource.RUSAGE_CHILDREN); own = resource.getrusage(resource.RUSAGE_SELF)
    result = dict(utc=utc(), host=host, returncode=rc, reason=reason, remaining_group_pids=left,
                  min_memavailable_GiB=min_mem/2**30, max_owned_pss_GiB=max_pss/2**30, wall_seconds=time.monotonic()-t0,
                  children_cpu_seconds=after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,
                  parent_cpu_seconds=own.ru_utime+own.ru_stime,
                  complete_blocks=len(io.listdir(out+'/blocks')) if io.is_real_dir(out+'/blocks') else 0)
    io.write_json_once(out+'/supervisor-exit.json', result, roles=PHASE_ROLES, mode=0o444)
    raise SystemExit(0 if (rc == 0 and reason is None and not left) else 1)


if __name__ == '__main__':
    main()
