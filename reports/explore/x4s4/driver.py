"""X4S-4 driver on 127x01 (exploration, NEVER ADOPTABLE), copied from X4S-3 driver r6. Stdlib only.

X4S-4 deltas (PLAN r3, design frozen at 87809ae0): job path; hard stop read from <job>/HARD-STOP-UTC.txt
(written at first launch, <= launch + 24 h); three mandatory fits R5, R5-rep (data/O-VERIFIED.json) and R5W
(data/OW-VERIFIED.json), one at a time, never beside a reporting phase; reporting phases are dispatched ONLY when
no fit is running and all three fits are done and calibrated (C4), in the fixed ABBA order R3a, R5, R5-rep,
R3a-rep, R5W (K4S-120 then S-200 each; E6); every student's games always run (E1: no futility stop, and the driver
never reads a game outcome); R3a-rep is a staged fixed student (rt-R3a-rep/READY.json); the X4S-3 union-fit/S-200
juggling and the R4-DC gate are removed.
X4S-3 description follows (fit and student names there read R3a-rep/R4-D/R4-DC).


Sequences, from on-disk state only:
  fits (one at a time on the GPU): R3a-rep, R4-D (after data/G-UNION-VERIFIED.json), R4-DC;
  calibration -> <job>/inputs/<ID>.pt (read-only) -> runtime copy <job>/rt-<ID> (plan.json student block);
  reporting phases, one (student, arm) at a time on cores 0-49, via supervise.py, only after <job>/REPORTING.GO.
Guards: no new phase is dispatched while MemAvailable < 24 GiB or memory PSI some avg10 > 10%;
<job>/STOP (-e or -L) stops the fit (SIGTERM; the trainer checkpoints) and pauses everything;
hard stop; fit NaN/divergence, 2x wall and GPU > 40 GB. Seeds of interrupted games are retired for every
later phase and never re-run. R4-DC games run only if the pooled R4-D minus R3a point estimate is < 0
(computed once both are terminal). Anomalies go to <job>/driver/ANOMALY-*.json and pause the affected lane.
"""
import datetime, hashlib, json, math, os, shutil, signal, subprocess, sys, time
from pathlib import Path

J = Path('/mpac/sdicks02/jobs/clasher/x4s4-onpolicy')
D = J/'driver'
STOP_AT = datetime.datetime.strptime((J/'HARD-STOP-UTC.txt').read_text().strip(), '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=datetime.timezone.utc)
FIXED = ['R3a', 'R3a-rep']
STUDENT_ORDER = ['R3a', 'R5', 'R5-rep', 'R3a-rep', 'R5W']   # ABBA (E6)
ARMS = ['K4S-120', 'S-200']
N = 1200
FITS = {'R5': dict(steps=2500, gate=J/'data'/'O-VERIFIED.json'), 'R5-rep': dict(steps=2500, gate=J/'data'/'O-VERIFIED.json'),
        'R5W': dict(steps=2500, gate=J/'data'/'OW-VERIFIED.json')}
FIT_ORDER = ['R5', 'R5-rep', 'R5W']
STEP_SECONDS, LOAD_SECONDS = 1.9, 600
GPU_LIMIT_MIB = 40 * 1024
GPU_PY = '/mpac/sdicks02/envs/clasher-gpu/bin/python'


def utc(): return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
def now(): return datetime.datetime.now(datetime.timezone.utc)
def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()
def jload(p):
    try: return json.loads(Path(p).read_text())
    except (FileNotFoundError, json.JSONDecodeError): return None
def jwrite(p, obj):
    p = Path(p); tmp = p.with_name(p.name+'.tmp'); tmp.write_text(json.dumps(obj, indent=2)+'\n'); tmp.replace(p)
def event(**kw):
    kw = dict(utc=utc(), **kw)
    with (D/'events.jsonl').open('a') as f: f.write(json.dumps(kw)+'\n')
    print(json.dumps(kw), flush=True)
def stop_present(): return os.path.lexists(J/'STOP')
def anomaly(name, **kw):
    p = D/f'ANOMALY-{name}.json'
    if not p.exists(): jwrite(p, dict(utc=utc(), **kw)); event(kind='anomaly', name=name, **kw)
def group_alive(pgid):
    try: os.killpg(pgid, 0); return True
    except ProcessLookupError: return False
    except PermissionError: return True
def mem_available():
    return int(next(x.split()[1] for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:')))*1024
def psi_some_avg10():
    try: return float(Path('/proc/pressure/memory').read_text().split()[1].split('=')[1])
    except Exception: return 0.
def gpu_used_mib():
    try:
        return int(subprocess.run(['nvidia-smi', '--query-gpu=memory.used', '--format=csv,noheader,nounits'],
                                  capture_output=True, text=True, timeout=20).stdout.split()[0])
    except Exception: return -1


def detach(log, receipt, cmd, cpus):
    """setsid child in its own group; returns pgid. Inherits the driver's nice 10."""
    Path(log).parent.mkdir(parents=True, exist_ok=True)
    with open(log, 'ab') as lf:
        p = subprocess.Popen(['taskset', '-c', cpus, *cmd], stdout=lf, stderr=lf, stdin=subprocess.DEVNULL, start_new_session=True)
    jwrite(receipt, dict(launched_at_utc=utc(), pid=p.pid, pgid=p.pid, command=cmd, cpus=cpus))
    return p


# ---------------- fits ----------------
def fit_state(fid):
    out = J/'fits'/fid; done = jload(out/'complete.json'); rec = jload(J/'receipts'/f'fit-{fid}-launch.json')
    if rec and group_alive(rec['pgid']): return 'running', rec
    if done and not done['stopped'] and done['step'] == FITS[fid]['steps']: return 'done', rec
    if done and done['stopped']: return 'stopped', rec
    if rec: return 'failed', rec
    return 'pending', rec


class Fits:
    def __init__(self): self.procs = {}
    def tick(self, games_ok):
        running = [f for f in FIT_ORDER if fit_state(f)[0] == 'running']
        for fid in running: self.guard(fid)
        if running or stop_present() or now() >= STOP_AT: return
        for fid in FIT_ORDER:
            st, rec = fit_state(fid)
            if st in ('done',): continue
            if (D/f'ANOMALY-fit-{fid}.json').exists(): return  # owner must clear
            if st == 'failed': anomaly(f'fit-{fid}', reason='fit process gone without complete.json'); return
            if not FITS[fid]['gate'].is_file(): continue           # all fits are mandatory (C1, C3)
            if live_supervisor(): return                            # never beside a reporting phase (C4)
            self.launch(fid, st); return
    def launch(self, fid, st):
        out = J/'fits'/fid; extra = []
        if st == 'stopped':
            done = jload(out/'complete.json'); ck = out/f"step-{done['step']:08d}.pt"
            k = len(list(out.glob('segment-attempt*.json')))+1
            for n in ('segment.json', 'complete.json'):
                if (out/n).exists(): (out/n).rename(out/f'{n[:-5]}-attempt{k}.json')
            extra = [str(ck)]
        rec = J/'receipts'/f'fit-{fid}-launch.json'
        if rec.exists(): rec.rename(J/'receipts'/f'fit-{fid}-launch-{int(time.time())}.json')
        detach(J/'logs'/f'fit-{fid}.log', rec, ['bash', str(J/'fit'/'run_fit.sh'), fid, *extra], '56-61')
        event(kind='fit_launch', fit=fid, resume=extra)
    def guard(self, fid):
        st, rec = fit_state(fid)
        why = None
        if stop_present(): why = 'STOP'
        elif now() >= STOP_AT: why = 'hard_stop'
        else:
            start = datetime.datetime.strptime(rec['launched_at_utc'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=datetime.timezone.utc)
            done = jload(J/'fits'/fid/'complete.json')
            if done and not done['stopped'] and done['step'] == FITS[fid]['steps']:
                return  # finished; the trainer is only tearing down
            # 2x expected wall time for this segment (resumed segments get the full budget; conservative).
            limit = 2*(FITS[fid]['steps']*STEP_SECONDS+LOAD_SECONDS)
            if (now()-start).total_seconds() > limit: why = 'wall_over_2x'
            losses = []
            try:
                for line in (J/'fits'/fid/'train.jsonl').read_text().splitlines()[-200:]:
                    r = json.loads(line); losses.append(r['loss'])
            except (FileNotFoundError, json.JSONDecodeError): pass
            if losses and (not all(math.isfinite(x) for x in losses) or losses[-1] > 10*min(losses+[1e9])): why = 'nan_or_divergent'
            g = gpu_used_mib()
            if g > GPU_LIMIT_MIB: why = 'gpu_over_40GB'
        if why:
            # SIGTERM the trainer itself (run_fit.sh execs python, so pid == trainer): it finishes the step,
            # checkpoints and shuts its loaders down. A group signal would kill the loaders first.
            try: os.kill(rec['pid'], signal.SIGTERM)
            except ProcessLookupError: pass
            event(kind='fit_stop', fit=fid, reason=why)
            if why not in ('STOP', 'hard_stop'): anomaly(f'fit-{fid}', reason=why)
            for _ in range(120):
                if not group_alive(rec['pgid']): break
                time.sleep(1)
            else:
                try: os.killpg(rec['pgid'], signal.SIGKILL)
                except ProcessLookupError: pass


# ---------------- calibration / runtimes ----------------
def ready_students():
    """Students with a runtime copy, in order of readiness (fixed students first)."""
    out = ['R3a'] + [s for s in FIXED[1:] if (J/f'rt-{s}'/'READY.json').is_file()]
    for fid in FIT_ORDER:
        if (J/f'rt-{fid}'/'READY.json').is_file(): out.append(fid)
    return sorted(out, key=lambda s: (s not in FIXED, FIXED.index(s) if s in FIXED else 0,
                                      jload(J/f'rt-{s}'/'READY.json')['utc'] if s not in FIXED else ''))


def prepare_students():
    for fid in FIT_ORDER:
        if fit_state(fid)[0] != 'done' or (J/f'rt-{fid}'/'READY.json').exists(): continue
        if (D/f'ANOMALY-calibration-{fid}.json').exists(): continue
        steps = FITS[fid]['steps']; ck = J/'fits'/fid/f'step-{steps:08d}.pt'
        dest = J/'inputs'/f'{fid}.pt'
        if not dest.exists():
            shutil.copyfile(ck, dest); os.chmod(dest, 0o444)
        if sha(dest) != sha(ck): anomaly(f'calibration-{fid}', reason='checkpoint copy SHA mismatch'); continue
        cal = J/'calibration'/f'{fid}.json'
        if not cal.exists():
            env = dict(os.environ, PYTHONPATH=f'{J}/fit/source:{J}/fit/source/src:{J}/fit/ops', PYTHONDONTWRITEBYTECODE='1', OMP_NUM_THREADS='1')
            r = subprocess.run(['taskset', '-c', '56-61', GPU_PY, '-B', str(J/'fit/ops/calibrate.py'), '--id', fid, '--checkpoint', str(dest),
                                '--assets', str(J/'inputs/assets.npz'), '--out', str(cal)], cwd=J/'fit/source', env=env,
                               capture_output=True, text=True, timeout=1800)
            (J/'logs'/f'calibrate-{fid}.log').write_text(r.stdout+r.stderr)
            if r.returncode or not cal.exists(): anomaly(f'calibration-{fid}', reason=f'calibrate rc {r.returncode}'); continue
        c = jload(cal)
        if c['checkpoint_sha256'] != sha(dest) or not 0 < c['threshold'] < 1: anomaly(f'calibration-{fid}', reason='bad calibration'); continue
        rt = J/f'rt-{fid}'
        if rt.exists(): shutil.rmtree(rt)
        shutil.copytree(J/'base', rt, symlinks=True)
        pj = rt/'repo/reports/explore/x4s3/plan.json'; plan = json.loads(pj.read_text())
        plan['student'] = dict(id=fid, checkpoint=str(dest), checkpoint_sha256=c['checkpoint_sha256'], threshold=c['threshold'],
                               calibration_sha256=sha(cal), status=f'X4S-3 {fid} student; exploration only; NEVER ADOPTABLE')
        pj.write_text(json.dumps(plan, indent=2)+'\n')
        jwrite(rt/'READY.json', dict(utc=utc(), id=fid, plan_sha256=sha(pj), student=plan['student']))
        event(kind='student_ready', id=fid, threshold=c['threshold'], play_rate=c['actual_play_rate'], checkpoint_sha256=c['checkpoint_sha256'])


# ---------------- games ----------------
def phase_dirs(sid, arm): return sorted((J/'games'/sid/arm).glob('a*'))


def phase_status(sid, arm, retired):
    """(completed indices, live supervisor rec or None, last exit or None)."""
    done = set()
    for d in phase_dirs(sid, arm):
        done |= {int(p.stem) for p in (d/'blocks').glob('*.json')}
    return done


def retired_set():
    r = jload(D/'retired.json') or dict(indices=[], why=[])
    return set(r['indices']), r


def retire(new, why):
    s, r = retired_set(); add = sorted(set(new)-s)
    if add:
        r['indices'] = sorted(s | set(add)); r['why'].append(dict(utc=utc(), indices=add, why=why)); jwrite(D/'retired.json', r)
        event(kind='retire', indices=add, why=why)


def settle_attempt(d):
    """After a supervisor exit: retire seeds whose games may have started but did not complete."""
    if (d/'SETTLED.json').exists(): return
    ex = jload(d/'supervisor-exit.json'); sched = jload(d/'schedule.json'); launch = jload(d/'launch.json')
    if ex is None: return
    order = sched['indices'] if sched else json.loads((d/'indices.json').read_text())
    done = {int(p.stem) for p in (d/'blocks').glob('*.json')}
    pos = [i for i, x in enumerate(order) if x in done]
    workers = launch['workers'] if launch else 50
    horizon = (max(pos)+1 if pos else 0)+workers+1
    started = {x for i, x in enumerate(order[:horizon]) if x not in done}
    started |= {int(p.name.split('-')[1]) for p in (d/'games').glob('sim-*.json')} - done
    if ex.get('reason') is not None or ex.get('returncode') != 0:
        retire(started, f'interrupted {d.relative_to(J)}: {ex.get("reason")} rc={ex.get("returncode")}')
    elif started:
        anomaly(f'unfinished-{d.parent.parent.name}-{d.parent.name}-{d.name}', reason='clean exit with unfinished indices', indices=sorted(started))
    jwrite(d/'SETTLED.json', dict(utc=utc(), completed=len(done), retired_or_flagged=sorted(started), exit=ex))


def live_supervisor():
    for rec in (J/'receipts').glob('phase-*-launch.json'):
        r = jload(rec)
        if r and group_alive(r['pgid']): return r
    return None


def fits_settled():
    """Reporting may start only when no fit runs and every fit is done and its student calibrated (C4)."""
    return all(fit_state(f)[0] == 'done' for f in FIT_ORDER) and all((J/f'rt-{f}'/'READY.json').is_file() for f in FIT_ORDER)


def next_phase():
    if not fits_settled():
        return None
    retired, _ = retired_set()
    ready = set(ready_students())
    for sid in STUDENT_ORDER:
        if sid not in ready:
            return None                                   # fixed order; never skip ahead
        for arm in ARMS:
            if (D/f'ANOMALY-phase-{sid}-{arm}.json').exists(): return None
            done = phase_status(sid, arm, retired)
            todo = [i for i in range(N) if i not in done and i not in retired]
            if todo: return sid, arm, todo
    return None


def launch_phase(sid, arm, todo):
    k = len(phase_dirs(sid, arm))+1
    if k > 6: anomaly(f'phase-{sid}-{arm}', reason='more than 6 attempts'); return
    name = f'games/{sid}/{arm}/a{k}'
    (J/'games'/sid/arm).mkdir(parents=True, exist_ok=True)
    idx = J/'games'/sid/arm/f'indices-a{k}.json'; idx.write_text(json.dumps(todo)+'\n')
    rt = J/f'rt-{sid}'
    cmd = ['bash', str(rt/'repo/reports/explore/x4s3/runtime.sh'), 'reports/explore/x4s3/supervise.py', '--job', str(J), '--rt', str(rt),
           '--phase', name, '--range', 'reporting', '--indices', str(idx), '--arms', arm, '--stop-at', STOP_AT.strftime('%Y-%m-%dT%H:%M:%SZ')]
    env_rt = dict(os.environ, X4S3_RT=str(rt))
    rec = J/'receipts'/f'phase-{sid}-{arm}-a{k}-launch.json'
    with open(J/'logs'/f'phase-{sid}-{arm}-a{k}.log', 'ab') as lf:
        p = subprocess.Popen(['taskset', '-c', '0-49', *cmd], stdout=lf, stderr=lf, stdin=subprocess.DEVNULL, start_new_session=True, env=env_rt)
    jwrite(rec, dict(launched_at_utc=utc(), pid=p.pid, pgid=p.pid, command=cmd, phase=name, todo=len(todo)))
    event(kind='phase_launch', student=sid, arm=arm, attempt=k, todo=len(todo))


def games_tick():
    for d in (J/'games').glob('*/*/a*'):
        if d.is_dir() and (d/'supervisor-exit.json').exists(): settle_attempt(d)
    if live_supervisor() or stop_present() or now() >= STOP_AT: return
    if not (J/'REPORTING.GO').is_file(): return
    for d in (J/'games').glob('*/*/a*'):
        ex = jload(d/'supervisor-exit.json')
        if d.is_dir() and not (d/'supervisor-exit.json').exists():
            # supervisor gone without exit receipt
            anomaly(f'phase-{d.parent.parent.name}-{d.parent.name}', reason=f'{d.relative_to(J)} has no supervisor-exit.json and no live supervisor'); return
    # waits after guard stops
    last = sorted((J/'games').glob('*/*/a*/supervisor-exit.json'), key=lambda p: p.stat().st_mtime)
    if last:
        ex = jload(last[-1])
        if ex.get('reason') == 'memory_guard' and mem_available() < 32*2**30: return
        if ex.get('reason') == 'hard_stop_time': return
        if ex.get('reason') == 'owned_STOP' and not (D/'RESUME-AFTER-STOP').exists(): return
        if ex.get('reason') == 'console_user' and time.time()-last[-1].stat().st_mtime < 120: return
        if ex.get('reason') not in (None, 'memory_guard', 'console_user', 'owned_STOP'):
            if not (D/f'ACK-{last[-1].parent.relative_to(J).as_posix().replace("/", "_")}').exists():
                anomaly(f'exit-{last[-1].parent.relative_to(J).as_posix().replace("/", "_")}', reason=ex.get('reason'), rc=ex.get('returncode')); return
    # Plan: stop dispatching while MemAvailable < 24 GiB or memory PSI some avg10 > 10%.
    if mem_available() < 24*2**30 or psi_some_avg10() > 10.:
        return
    nxt = next_phase()
    if nxt: launch_phase(*nxt)


def main():
    D.mkdir(exist_ok=True)
    if not (os.uname().nodename == '127x01' and os.getpriority(os.PRIO_PROCESS, 0) == 10): raise SystemExit("driver.py: check failed: os.uname().nodename == '127x01' and os.getpriority(os.PRIO_PROCESS, 0) == 10")
    lock = D/'driver.pid'
    other = jload(lock)
    if other and Path(f"/proc/{other['pid']}").exists() and other['pid'] != os.getpid():
        raise SystemExit('another driver is live')
    jwrite(lock, dict(pid=os.getpid(), pgid=os.getpgrp(), started=utc()))
    event(kind='driver_start', pid=os.getpid())
    fits = Fits()
    stop = []
    signal.signal(signal.SIGTERM, lambda *a: stop.append('SIGTERM'))
    beat = 0
    while not stop:
        # Reap exited children (supervisors, fits) so a zombie never keeps its process group "alive".
        while True:
            try:
                pid, _ = os.waitpid(-1, os.WNOHANG)
            except ChildProcessError:
                break
            if pid == 0: break
        try:
            fits.tick(True); prepare_students(); games_tick()
        except Exception as e:
            anomaly('driver-exception', error=repr(e))
            time.sleep(60)
        if now() >= STOP_AT and not live_supervisor() and all(fit_state(f)[0] != 'running' for f in FIT_ORDER):
            event(kind='driver_exit', reason='hard stop reached; nothing live'); break
        if time.time()-beat > 300:
            jwrite(D/'heartbeat.json', dict(utc=utc(), mem_available_GiB=mem_available()/2**30, gpu_used_MiB=gpu_used_mib(),
                                             fits={f: fit_state(f)[0] for f in FIT_ORDER}, ready=ready_students(),
                                             retired=len(retired_set()[0]), stop=stop_present())); beat = time.time()
        for _ in range(10):
            if stop: break
            time.sleep(1)
    event(kind='driver_exit', reason=stop[0] if stop else 'loop end')


if __name__ == '__main__':
    main()
