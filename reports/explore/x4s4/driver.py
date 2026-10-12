"""X4S-4 driver on 127x01 (exploration, NEVER ADOPTABLE). r3 after Sol script review r2. Stdlib only, Python 3.8+.

Design (PLAN r3, frozen at 87809ae0): hard stop read from <job>/HARD-STOP-UTC.txt (written once at first launch,
T+24 h, never reset); three mandatory fits R5, R5-rep (after data/O-VERIFIED.json) and R5W (after
data/OW-VERIFIED.json), one at a time on the GPU (cores 56-61), never beside a reporting phase; reporting phases only
after <job>/REPORTING.GO, when no fit runs and all three fits are done and calibrated (C4), one (student, arm) at a
time on cores 0-49 through reports/explore/x4s4/supervise.py, in the fixed ABBA order R3a, R5, R5-rep, R3a-rep, R5W
(K4S-120 then S-200 each; E6); every student's games always run (E1: no futility stop); no game outcome is read.

r3 (Sol r2):
  * R2-F1: every read, write and subprocess goes through x4s4io (canonical no-follow walks, exclusive creation,
    atomic replace over single-link files only, no-follow appends, fd-based removal, explicit absolute argv). The
    runtime overlay rt-<ID> is a fresh copy of <job>/base made by x4s4io.copy_tree_fresh; its plan.json is replaced
    through the gate (a symlinked or hard-linked plan.json or ancestor refuses).
  * R2-F2: each launch has a launch_id. Reaped exit codes are durable child_exit events carrying that launch_id. A
    reporting attempt settles only when the reaped child status and the supervisor's exit receipt agree (clean:
    receipt reason None, rc 0, child 0; permitted guard stop: child 1 with a PERMITTED_STOPS reason). Anything else -
    including an unknown child status after a driver restart - is an anomaly until an ACK bound to that exact attempt
    (launch_id, pid, starttime, launch-receipt SHA, disposition) is supplied; the ACK is consumed and the evidence
    (child status, receipt, ACK) is kept in SETTLED.json. Fits use the same exact-attempt ACK for an unknown exit.
  * R2-F3: fit admission requires readable memory/PSI, the study tree + 10 reserved fit processes <= 70, disk <= 100 GB,
    and GPU readable with <= 8 GiB already used (room for the <= 40 GB fit); reporting admission reserves 53
    processes. While a fit runs it is stopped on MemAvailable < 24 GiB or unreadable, GPU unreadable or > 40 GB, the
    fit tree's PSS > 50 GiB (the frozen rule) or unreadable, NaN/divergence, 2x wall, STOP or the hard stop. Every
    unresolved ANOMALY blocks all new dispatch. Dispatch and the O-holdout diagnostic share an exclusive flock on
    driver/DISPATCH.lock, so the diagnostic lock check and a launch cannot interleave. Signals go to verified PIDs of
    owned groups only (the trainer PID first, then the group's remaining verified PIDs).
  * Only a wall_over_2x fit auto-resumes, after the O_W gate (R2-11); divergence never does.
"""
import datetime, fcntl, json, math, os, secrets, signal, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import x4s4io as io                                    # noqa: E402
import studytree                                        # noqa: E402

J = io.JOB
D = J+'/driver'
STOP_AT = studytree.hard_stop_at(J)
FIXED = ['R3a', 'R3a-rep']
STUDENT_ORDER = ['R3a', 'R5', 'R5-rep', 'R3a-rep', 'R5W']   # ABBA (E6)
ARMS = ['K4S-120', 'S-200']
N = 1200
FITS = {'R5': dict(steps=2500, gate=J+'/data/O-VERIFIED.json'), 'R5-rep': dict(steps=2500, gate=J+'/data/O-VERIFIED.json'),
        'R5W': dict(steps=2500, gate=J+'/data/OW-VERIFIED.json')}
FIT_ORDER = ['R5', 'R5-rep', 'R5W']
STEP_SECONDS, LOAD_SECONDS = 1.9, 600
GPU_LIMIT_MIB, GPU_ADMIT_MIB = 40*1024, 8*1024
GPU_PY = '/mpac/sdicks02/envs/clasher-gpu/bin/python'
FIT_PROCESSES, PHASE_PROCESSES = 10, 53
PERMITTED_STOPS = ('memory_guard', 'console_user', 'owned_STOP', 'hard_stop_time', 'supervisor_SIGTERM', 'study_tree_cap')
RUNTIME_FILES = ('reports/explore/x4s4/supervise.py', 'reports/explore/x4s4/x4s4io.py', 'reports/explore/x4s4/studytree.py',
                 'reports/explore/x4s4/qualify4.py', 'reports/explore/x4s3/run.py', 'reports/explore/x4s3/runtime.sh')
EXIT, LAUNCHED = {}, {}                                  # reaped pid -> exit code; live child pid -> launch_id


def utc(): return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
def now(): return datetime.datetime.now(datetime.timezone.utc)
def sha(p): return io.sha256_file(p)


def jload(p):
    """JSON state file; None only if absent. A symlink, hard link or malformed file raises (fail closed)."""
    if not io.lexists(p): return None
    return io.read_json(p, 64 << 20)


def jwrite(p, obj): io.replace_json(p, obj)
def event(**kw): io.append_json_line(D+'/events.jsonl', dict(utc=utc(), **kw))
def stop_present(): return io.lexists(J+'/STOP')


def anomaly(name, **kw):
    p = f'{D}/ANOMALY-{name}.json'
    if not io.lexists(p): jwrite(p, dict(utc=utc(), **kw)); event(kind='anomaly', name=name, **kw)


def unresolved_anomalies():
    """Every ANOMALY-* without its ACK blocks all new dispatch (fits and phases)."""
    out = []
    for n in io.listdir(D):
        if n.startswith('ANOMALY-') and n.endswith('.json'):
            key = n[len('ANOMALY-'):-len('.json')]
            if not io.lexists(f'{D}/ACK-{key}.json'): out.append(key)
    return out


def mem_available(): return studytree.mem_available()
def psi_some_avg10(): return studytree.psi_some_avg10()


def gpu_used_mib():
    try:
        r = io.run_checked(['/usr/bin/nvidia-smi', '--query-gpu=memory.used', '--format=csv,noheader,nounits'], 20, 4096,
                           env={'LC_ALL': 'C', 'PATH': '/usr/bin:/bin'})
        v = int(r.stdout.split()[0]); return v if v >= 0 else None
    except (io.Refusal, ValueError, IndexError):
        return None                                      # unreadable -> blocks fit dispatch; stops a running fit


def diagnostic_live():
    r = jload(D+'/DIAGNOSTIC.lock')
    if r is None: return False
    st = io.proc_stat(r.get('pid', -1))
    return bool(st and st['starttime'] == r.get('starttime'))


def resources_ok(for_fit=False):
    """Dispatch admission, fail closed on any unreadable measurement (R2-F3)."""
    mem, psi = mem_available(), psi_some_avg10()
    if mem is None or mem < studytree.MEM_FLOOR or psi is None or psi > 10.0: return False
    if not studytree.admission(J, FIT_PROCESSES if for_fit else PHASE_PROCESSES)[0]: return False
    if for_fit:
        g = gpu_used_mib()
        if g is None or g > GPU_ADMIT_MIB: return False
    return not diagnostic_live()


class DispatchLock:
    """Exclusive flock on driver/DISPATCH.lock, shared with diagnose.py (no interleaving of checks and launches)."""
    def __enter__(self):
        self.fd = io.open_append(D+'/DISPATCH.lock', roles=('driver',))
        fcntl.flock(self.fd, fcntl.LOCK_EX)
        return self
    def __exit__(self, *exc):
        fcntl.flock(self.fd, fcntl.LOCK_UN); os.close(self.fd); return False


def launch(name, argv, log, receipt, env, cwd=None):
    """Spawn an owned child and record its launch receipt (launch_id, pid, pgid, starttime)."""
    lid = secrets.token_hex(8)
    child = io.spawn(argv, log, env, roles=('logs',), cwd=cwd)
    LAUNCHED[child['pid']] = lid
    rec = dict(launched_at_utc=utc(), launch_id=lid, pid=child['pid'], pgid=child['pgid'], starttime=child['starttime'],
               command=argv, name=name)
    io.write_json_once(receipt, rec, roles=('receipts',), mode=0o444)
    event(kind='launch', name=name, launch_id=lid, pid=child['pid'])
    return rec


def exit_status(rec):
    """Reaped exit code of exactly this launch (durable child_exit events carry the launch_id); None if unknown."""
    if rec['pid'] in EXIT and LAUNCHED.get(rec['pid']) == rec['launch_id']: return EXIT[rec['pid']]
    path = D+'/events.jsonl'
    if not io.lexists(path): return None
    code = None
    for line in io.read_text(path, 256 << 20).splitlines():
        e = io.loads_strict(line.encode())
        if e.get('kind') == 'child_exit' and e.get('launch_id') == rec['launch_id']: code = e['exit_code']
    return code


def ack_for(key, rec, receipt_path):
    """An ACK bound to this exact attempt: {launch_id, pid, starttime, receipt_sha256, disposition, owner}."""
    p = f'{D}/ACK-{key}.json'
    if not io.lexists(p): return None
    a = io.read_json(p, 1 << 20)
    want = dict(launch_id=rec['launch_id'], pid=rec['pid'], starttime=rec['starttime'], receipt_sha256=sha(receipt_path))
    if any(a.get(k) != v for k, v in want.items()) or not a.get('owner') or a.get('disposition') not in ('success', 'retire'):
        anomaly(f'stale-ack-{key}', reason='ACK not bound to this exact attempt', ack=a, want=want); return None
    return a


def consume_ack(key):
    """Archive a used ACK and the anomaly it resolved (an ACK is never reusable for a later attempt)."""
    t = int(time.time())
    io.rename_path(f'{D}/ACK-{key}.json', f'{D}/ACK-{key}.consumed-{t}.json', roles=('driver',))
    if io.lexists(f'{D}/ANOMALY-{key}.json'):
        io.rename_path(f'{D}/ANOMALY-{key}.json', f'{D}/RESOLVED-{key}-{t}.json', roles=('driver',))


# ---------------- fits ----------------
def fit_receipt(fid): return f'{J}/receipts/fit-{fid}-launch.json'


def fit_state(fid):
    out = f'{J}/fits/{fid}'; done = jload(out+'/complete.json'); rp = fit_receipt(fid); rec = jload(rp)
    if rec and io.group_alive(rec['pgid'], rec['starttime']): return 'running', rec
    seg = jload(out+'/segment.json')
    if done and not done['stopped'] and done['step'] == FITS[fid]['steps']:
        status = exit_status(rec) if rec else None
        res = jload(f'{J}/receipts/fit-{fid}-exit-resolution.json')
        if status is None and rec and not (res and res.get('launch_id') == rec['launch_id']):
            a = ack_for(f'fit-{fid}-exit', rec, rp)
            if a and a['disposition'] == 'success':
                io.write_json_once(f'{J}/receipts/fit-{fid}-exit-resolution.json', dict(utc=utc(), launch_id=rec['launch_id'], ack=a),
                                   roles=('receipts',))
                consume_ack(f'fit-{fid}-exit'); res = jload(f'{J}/receipts/fit-{fid}-exit-resolution.json')
        clean = status == 0 or (status is None and rec is not None and bool(res) and res.get('launch_id') == rec['launch_id'])
        if seg and seg.get('status') == 'returned' and clean: return 'done', rec
        return 'failed', rec                                       # completion without a clean return + known zero exit
    if done and done['stopped']: return 'stopped', rec
    if rec: return 'failed', rec
    return 'pending', rec


def prepare_fit_dirs(fid):
    """Validate/create every directory the frozen trainer and run_fit.sh will write, before launch (R2-F1)."""
    for d in (f'fits/{fid}', 'cache/fit/cuda', 'cache/fit/torch', 'cache/fit/triton', 'cache/fit/tmp', 'logs'):
        io.mkdirs(f'{J}/{d}')
    inv = jload(J+'/RUNTIME-INVENTORY.json') or {}
    if inv.get('fit/run_fit.sh') is None or sha(J+'/fit/run_fit.sh') != inv['fit/run_fit.sh']:
        raise io.Refusal('inventory', 'fit/run_fit.sh differs from RUNTIME-INVENTORY')


class Fits:
    def tick(self):
        running = [f for f in FIT_ORDER if fit_state(f)[0] == 'running']
        for fid in running: self.guard(fid)
        if running or stop_present() or now() >= STOP_AT: return
        for fid in FIT_ORDER:
            st, rec = fit_state(fid)
            if st == 'done': continue
            an = jload(f'{D}/ANOMALY-fit-{fid}.json')
            if an:
                if not (an.get('reason') == 'wall_over_2x' and st == 'stopped' and io.lexists(J+'/data/OW-VERIFIED.json')):
                    return
                io.rename_path(f'{D}/ANOMALY-fit-{fid}.json', f'{D}/RESOLVED-fit-{fid}-autoresumed-{int(time.time())}.json', roles=('driver',))
                event(kind='fit_autoresume', fit=fid, after='wall_over_2x')
            if unresolved_anomalies(): return
            if st == 'failed': anomaly(f'fit-{fid}-exit', reason='fit gone without a clean return and a known zero exit'); return
            if not io.lexists(FITS[fid]['gate']): continue          # all fits are mandatory (C1, C3)
            with DispatchLock():
                if live_supervisor() or not resources_ok(for_fit=True): return
                self.launch(fid, st)
            return

    def launch(self, fid, st):
        out = f'{J}/fits/{fid}'; extra = []
        prepare_fit_dirs(fid)
        if st == 'stopped':
            done = jload(out+'/complete.json'); ck = f"{out}/step-{done['step']:08d}.pt"
            k = len([n for n in io.listdir(out) if n.startswith('segment-attempt')])+1
            for n in ('segment', 'complete'):
                if io.lexists(f'{out}/{n}.json'): io.rename_path(f'{out}/{n}.json', f'{out}/{n}-attempt{k}.json', roles=('fits',))
            extra = [ck]
        rp = fit_receipt(fid)
        if io.lexists(rp): io.rename_path(rp, f'{J}/receipts/fit-{fid}-launch-{int(time.time())}.json', roles=('receipts',))
        launch(f'fit-{fid}', ['/usr/bin/taskset', '-c', '56-61', '/bin/bash', J+'/fit/run_fit.sh', fid, *extra],
               f'{J}/logs/fit-{fid}.log', rp, dict(os.environ))

    def guard(self, fid):
        st, rec = fit_state(fid)
        why = None
        if stop_present(): why = 'STOP'
        elif now() >= STOP_AT: why = 'hard_stop'
        else:
            done = jload(f'{J}/fits/{fid}/complete.json')
            if done and not done['stopped'] and done['step'] == FITS[fid]['steps']: return   # tearing down
            start = datetime.datetime.strptime(rec['launched_at_utc'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=datetime.timezone.utc)
            if (now()-start).total_seconds() > 2*(FITS[fid]['steps']*STEP_SECONDS+LOAD_SECONDS): why = 'wall_over_2x'
            losses = []
            tj = f'{J}/fits/{fid}/train.jsonl'
            if io.lexists(tj):
                for line in io.read_text(tj, 512 << 20).splitlines()[-200:]:
                    try: losses.append(float(json.loads(line)['loss']))      # the fit's TRAINING loss, not a game outcome
                    except (ValueError, KeyError, TypeError): losses.append(float('nan'))
            if losses and (not all(math.isfinite(x) for x in losses) or losses[-1] > 10*min(losses+[1e9])): why = 'nan_or_divergent'
            mem = mem_available()
            if mem is None or mem < studytree.MEM_FLOOR: why = 'memory_floor'
            g = gpu_used_mib()
            if g is None: why = 'gpu_unreadable'
            elif g > GPU_LIMIT_MIB: why = 'gpu_over_40GB'
            p = studytree.pss_bytes(io.owned_pids(rec['pgid'], rec['starttime']))
            if p is None or p > studytree.PSS_LIMIT: why = 'fit_pss_over_50GiB_or_unreadable'
        if why:
            # SIGTERM the verified trainer PID (run_fit.sh execs python, so pid == trainer): it finishes the step and
            # checkpoints. Then the group's remaining verified PIDs get TERM/KILL.
            io.signal_pid(rec['pid'], rec['pgid'], rec['starttime'], signal.SIGTERM)
            event(kind='fit_stop', fit=fid, reason=why)
            if why not in ('STOP', 'hard_stop'): anomaly(f'fit-{fid}', reason=why)
            for _ in range(120):
                if not io.group_alive(rec['pgid'], rec['starttime']): break
                time.sleep(1)
            else:
                io.stop_owned(rec['pgid'], rec['starttime'], term_grace=15, kill_grace=60)


# ---------------- calibration / runtimes ----------------
def ready_students():
    out = ['R3a'] + [s for s in FIXED[1:] if io.lexists(f'{J}/rt-{s}/READY.json')]
    for fid in FIT_ORDER:
        if io.lexists(f'{J}/rt-{fid}/READY.json'): out.append(fid)
    return sorted(out, key=lambda s: (s not in FIXED, FIXED.index(s) if s in FIXED else 0,
                                      jload(f'{J}/rt-{s}/READY.json')['utc'] if s not in FIXED else ''))


def prepare_students():
    for fid in FIT_ORDER:
        if fit_state(fid)[0] != 'done' or io.lexists(f'{J}/rt-{fid}/READY.json'): continue
        if io.lexists(f'{D}/ANOMALY-calibration-{fid}.json'): continue
        ck = f"{J}/fits/{fid}/step-{FITS[fid]['steps']:08d}.pt"; dest = f'{J}/inputs/{fid}.pt'
        if not io.lexists(dest): io.copy_file(ck, dest, roles=('inputs',), mode=0o444)
        if sha(dest) != sha(ck): anomaly(f'calibration-{fid}', reason='checkpoint copy SHA mismatch'); continue
        cal = f'{J}/calibration/{fid}.json'
        if not io.lexists(cal):
            io.check_writable(cal, roles=('calibration',), must_not_exist=True); io.mkdirs(J+'/calibration')
            env = dict(PATH='/usr/bin:/bin', PYTHONPATH=f'{J}/fit/source:{J}/fit/source/src:{J}/fit/ops', PYTHONDONTWRITEBYTECODE='1',
                       OMP_NUM_THREADS='1', HOME=os.environ.get('HOME', '/nonexistent'))
            try:
                r = io.run_checked(['/usr/bin/taskset', '-c', '56-61', GPU_PY, '-B', f'{J}/fit/ops/calibrate.py', '--id', fid,
                                    '--checkpoint', dest, '--assets', f'{J}/inputs/assets.npz', '--out', cal], 1800, 16 << 20,
                                   env=env, cwd=f'{J}/fit/source')
                io.replace_bytes(f'{J}/logs/calibrate-{fid}.log', r.stdout+r.stderr, roles=('logs',))
            except io.Refusal as e:
                anomaly(f'calibration-{fid}', reason=f'calibrate failed: {e}'); continue
            if not io.lexists(cal): anomaly(f'calibration-{fid}', reason='calibrate wrote no output'); continue
        c = jload(cal)
        if c['checkpoint_sha256'] != sha(dest) or not 0 < c['threshold'] < 1: anomaly(f'calibration-{fid}', reason='bad calibration'); continue
        rt = f'{J}/rt-{fid}'
        if io.lexists(rt): io.remove_tree(rt)                      # an unfinished overlay (no READY): rebuild it
        io.copy_tree_fresh(J+'/base', rt)                           # fresh confined copy; links copied as links
        pj = rt+'/repo/reports/explore/x4s3/plan.json'; plan = io.read_json(pj, 4 << 20)
        plan['student'] = dict(id=fid, checkpoint=dest, checkpoint_sha256=c['checkpoint_sha256'], threshold=c['threshold'],
                               calibration_sha256=sha(cal), status=f'X4S-4 {fid} student; exploration only; NEVER ADOPTABLE')
        io.replace_json(pj, plan)                                    # refuses a symlinked/hard-linked plan or ancestor
        io.write_json_once(rt+'/READY.json', dict(utc=utc(), id=fid, plan_sha256=sha(pj), student=plan['student']), mode=0o444)
        event(kind='student_ready', id=fid, threshold=c['threshold'], play_rate=c.get('actual_play_rate'), checkpoint_sha256=c['checkpoint_sha256'])


# ---------------- games ----------------
def phase_dirs(sid, arm):
    base = f'{J}/games/{sid}/{arm}'
    if not io.lexists(base): return []
    return [f'{base}/{n}' for n in io.listdir(base) if n.startswith('a') and io.is_real_dir(f'{base}/{n}')]


def all_phase_dirs():
    return [d for sid in STUDENT_ORDER for arm in ARMS for d in phase_dirs(sid, arm)]


def blocks_of(d):
    b = d+'/blocks'
    return {int(n[:-5]) for n in io.listdir(b) if n.endswith('.json')} if io.lexists(b) else set()


def phase_status(sid, arm, retired):
    done = set()
    for d in phase_dirs(sid, arm): done |= blocks_of(d)
    return done


def retired_set():
    r = jload(D+'/retired.json') or dict(indices=[], why=[])
    return set(r['indices']), r


def retire(new, why):
    s, r = retired_set(); add = sorted(set(new)-s)
    if add:
        r['indices'] = sorted(s | set(add)); r['why'].append(dict(utc=utc(), indices=add, why=why)); jwrite(D+'/retired.json', r)
        event(kind='retire', indices=add, why=why)


def phase_key(d): return d[len(J)+1:].replace('/', '_')
def phase_receipt(d):
    sid, arm, a = d.split('/')[-3:]
    return f'{J}/receipts/phase-{sid}-{arm}-{a}-launch.json'


def settle_attempt(d):
    """R2-F2: bind launch receipt + reaped child status + supervisor exit receipt; retire unfinished seeds only for a
    consistent permitted guard stop or an exact-attempt ACK; otherwise an anomaly stops dispatch."""
    if io.lexists(d+'/SETTLED.json'): return
    ex = jload(d+'/supervisor-exit.json'); sched = jload(d+'/schedule.json'); lj = jload(d+'/launch.json')
    rp = phase_receipt(d); rec = jload(rp)
    if ex is None: return
    key = 'exit-'+phase_key(d)
    if rec is None: anomaly(key, reason='no launch receipt for this attempt'); return
    order = sched['indices'] if sched else []
    done = blocks_of(d)
    pos = [i for i, x in enumerate(order) if x in done]
    workers = lj['workers'] if lj else 50
    horizon = (max(pos)+1 if pos else 0)+workers+1
    started = {x for i, x in enumerate(order[:horizon]) if x not in done}
    gdir = d+'/games'
    if io.lexists(gdir): started |= {int(n.split('-')[1]) for n in io.listdir(gdir) if n.startswith('sim-')} - done
    reason, rc, child = ex.get('reason'), ex.get('returncode'), exit_status(rec)
    clean = reason is None and rc == 0 and child == 0 and not started
    guard = reason in PERMITTED_STOPS and child == 1
    a = None
    if not (clean or guard):
        a = ack_for(key, rec, rp)
        if a is None:
            anomaly(key, reason=reason, rc=rc, child_exit=child, unfinished=sorted(started)); return
    if not clean: retire(started, f'interrupted {d[len(J)+1:]}: reason={reason} rc={rc} child={child}')
    jwrite(d+'/SETTLED.json', dict(utc=utc(), completed=len(done), retired_or_flagged=sorted(started), exit=ex,
                                   child_exit=child, launch_id=rec['launch_id'], ack=a,
                                   disposition='clean' if clean else ('guard_stop' if guard else 'owner_ack')))
    if a: consume_ack(key)


def live_supervisor():
    base = J+'/receipts'
    for n in io.listdir(base):
        if n.startswith('phase-') and n.endswith('-launch.json'):
            r = jload(f'{base}/{n}')
            if r and io.group_alive(r['pgid'], r['starttime']): return r
    return None


def fits_settled():
    return all(fit_state(f)[0] == 'done' for f in FIT_ORDER) and all(io.lexists(f'{J}/rt-{f}/READY.json') for f in FIT_ORDER)


def next_phase():
    if not fits_settled(): return None
    retired, _ = retired_set()
    ready = set(ready_students())
    for sid in STUDENT_ORDER:
        if sid not in ready: return None                 # fixed order; never skip ahead
        for arm in ARMS:
            done = phase_status(sid, arm, retired)
            todo = [i for i in range(N) if i not in done and i not in retired]
            if todo: return sid, arm, todo
    return None


def launch_phase(sid, arm, todo):
    k = len(phase_dirs(sid, arm))+1
    if k > 6: anomaly(f'phase-{sid}-{arm}', reason='more than 6 attempts'); return
    name = f'games/{sid}/{arm}/a{k}'
    rt = f'{J}/rt-{sid}'
    inv = jload(J+'/RUNTIME-INVENTORY.json') or {}
    for rel in RUNTIME_FILES:                            # the executed files are the reviewed bytes (Sol r1 F8)
        p = f'{rt}/repo/{rel}'
        if not (rel in inv and io.lexists(p) and sha(p) == inv[rel]):
            anomaly(f'phase-{sid}-{arm}', reason=f'runtime inventory mismatch: {rel}'); return
    idx = f'{J}/games/{sid}/{arm}/indices-a{k}.json'
    io.write_json_once(idx, todo, roles=('games',), mode=0o444)
    cmd = ['/usr/bin/taskset', '-c', '0-49', '/bin/bash', rt+'/repo/reports/explore/x4s3/runtime.sh', 'reports/explore/x4s4/supervise.py',
           '--job', J, '--rt', rt, '--phase', name, '--range', 'reporting', '--indices', idx, '--arms', arm,
           '--stop-at', STOP_AT.strftime('%Y-%m-%dT%H:%M:%SZ')]
    launch(f'phase-{sid}-{arm}-a{k}', cmd, f'{J}/logs/phase-{sid}-{arm}-a{k}.log', f'{J}/receipts/phase-{sid}-{arm}-a{k}-launch.json',
           dict(os.environ, X4S3_RT=rt))


def games_tick():
    for d in all_phase_dirs():
        if io.lexists(d+'/supervisor-exit.json'): settle_attempt(d)
    if live_supervisor() or stop_present() or now() >= STOP_AT: return
    if not io.lexists(J+'/REPORTING.GO'): return
    for d in all_phase_dirs():
        if not io.lexists(d+'/supervisor-exit.json'):
            anomaly('phase-'+phase_key(d), reason='attempt has no supervisor-exit.json and no live supervisor'); return
    if unresolved_anomalies(): return
    if any(not io.lexists(d+'/SETTLED.json') for d in all_phase_dirs()): return
    exits = [(io.stat_leaf(d+'/supervisor-exit.json').st_mtime_ns, d) for d in all_phase_dirs()]
    if exits:
        d = max(exits)[1]; ex = jload(d+'/supervisor-exit.json')
        mem = mem_available()
        if ex.get('reason') == 'memory_guard' and (mem is None or mem < 32*2**30): return
        if ex.get('reason') == 'hard_stop_time': return
        if ex.get('reason') == 'owned_STOP' and not io.lexists(D+'/RESUME-AFTER-STOP'): return
        if ex.get('reason') == 'console_user' and time.time()-max(exits)[0]/1e9 < 120: return
    with DispatchLock():
        if not resources_ok(): return
        nxt = next_phase()
        if nxt: launch_phase(*nxt)


def exit_code(status):
    if os.WIFEXITED(status): return os.WEXITSTATUS(status)
    if os.WIFSIGNALED(status): return -os.WTERMSIG(status)
    return None


def main():
    io.mkdirs(D)
    if not (os.uname().nodename == '127x01' and os.getpriority(os.PRIO_PROCESS, 0) == 10): raise SystemExit('driver.py: requires 127x01 at nice 10')
    other = jload(D+'/driver.pid')
    if other and io.group_alive(other.get('pgid'), other.get('starttime')) and other.get('pid') != os.getpid():
        raise SystemExit('another driver is live')
    me = io.own_identity()
    jwrite(D+'/driver.pid', dict(pid=me['pid'], pgid=me['pgid'], starttime=me['starttime'], started=utc()))
    event(kind='driver_start', pid=me['pid'])
    fits = Fits(); stop = []
    signal.signal(signal.SIGTERM, lambda *a: stop.append('SIGTERM'))
    beat = 0
    while not stop:
        while True:                                    # reap: zombies never keep a group alive; statuses are durable
            try: pid, status = os.waitpid(-1, os.WNOHANG)
            except ChildProcessError: break
            if pid == 0: break
            EXIT[pid] = exit_code(status)
            event(kind='child_exit', pid=pid, launch_id=LAUNCHED.get(pid), exit_code=EXIT[pid])
        try:
            fits.tick(); prepare_students(); games_tick()
        except Exception as e:
            anomaly('driver-exception', error=repr(e))      # blocks every new dispatch until ACKed
            time.sleep(60)
        if now() >= STOP_AT and not live_supervisor() and all(fit_state(f)[0] != 'running' for f in FIT_ORDER):
            event(kind='driver_exit', reason='hard stop reached; nothing live'); break
        if time.time()-beat > 300:
            mem = mem_available()
            jwrite(D+'/heartbeat.json', dict(utc=utc(), mem_available_GiB=None if mem is None else mem/2**30, gpu_used_MiB=gpu_used_mib(),
                                             fits={f: fit_state(f)[0] for f in FIT_ORDER}, ready=ready_students(),
                                             retired=len(retired_set()[0]), stop=stop_present())); beat = time.time()
        for _ in range(10):
            if stop: break
            time.sleep(1)
    event(kind='driver_exit', reason=stop[0] if stop else 'loop end')


if __name__ == '__main__':
    main()
