"""Ladder supervisor (Mac): keeps ONE long live session running. Crash recovery and boundary deploys only; it never taps,
never touches BlueStacks/adb, and writes only under ~/clasher-live/loop/ (supervisor/, logs/<session>.log, the boundary file).

  ~/clasher-live/venv/bin/python -B ladder_supervisor.py [--loop-dir ~/clasher-live/loop] [--first sNN]

  supervisor/launch.sh       zsh script, $1 = session name, execs the driver (run-fullpool.sh ...) in the foreground
  supervisor/staged/         a staged deploy: apply.sh (installs with backups, sha-checks; exit 0 = applied, exit 10 = NOT
                             applied and the old state verified restored; anything else or a timeout = uncertain -> ALERT and
                             the supervisor stops), optional launch.sh (replaces supervisor/launch.sh), READY (written last).
                             Applied only after a confirmed boundary exit (the driver took RESTART-AT-BOUNDARY) or with no
                             driver running at supervisor start, and while the supervisor itself holds driver.lock.
  SUPERVISOR-STOP            stop: no relaunch. Empty = the running driver ends at its next battle end (boundary file);
                             containing 'now' = TERM the driver immediately.

Loop: if a driver already holds driver.lock (e.g. a session started by hand), adopt it: wait for its PID. Otherwise launch
launch.sh <next session>. While it runs, a staged READY or a STOP file creates RESTART-AT-BOUNDARY (drive.py ends on the
result screen of the current battle). When the driver exits, for any reason: STOP -> exit; staged READY -> apply it;
then relaunch within ~2 s. Three sessions in a row that end within --min-session seconds without a battle (refusals,
crashes at load) -> ALERT file and exit, so a broken deploy cannot loop. Events: supervisor/supervisor.jsonl (UTC).
Signals: only STOP 'now' sends anything, a TERM to the driver it launched itself (its Popen child). An adopted driver
(started by someone else) is never signalled: STOP 'now' becomes a boundary request for it. A deploy applies only after a
boundary exit proven by the token the supervisor wrote into THIS boundary request (drive.py keeps the file's content
when it renames it .taken-<pid>), or with no driver running at supervisor start."""
import argparse, fcntl, json, os, re, shutil, signal, subprocess, sys, time
from pathlib import Path

SHELL = os.environ.get('LL_SUP_SHELL', '/bin/zsh')     # launch.sh / apply.sh interpreter (tests: bash on Linux)


def now():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


class Sup:
    def __init__(self, loop, min_session, first):
        self.loop = loop
        self.dir = loop/'supervisor'
        self.dir.mkdir(exist_ok=True)
        self.launch = self.dir/'launch.sh'
        self.staged = self.dir/'staged'
        self.stop = loop/'SUPERVISOR-STOP'
        self.alert = self.dir/'ALERT'
        self.boundary = loop/'RESTART-AT-BOUNDARY'
        self.min_session = min_session
        self.first = first
        self.token = None                                  # the current boundary request's token

    def log(self, ev, **kw):
        with open(self.dir/'supervisor.jsonl', 'a') as f:
            f.write(json.dumps(dict(ts=now(), ev=ev, **kw)) + '\n')

    def next_name(self):
        if self.first:
            name, self.first = self.first, None
            if not ((self.loop/'runs'/name).exists() or (self.loop/'logs'/f'{name}.log').exists()):
                return name
            self.log('first_name_taken', name=name)
        nums = [int(m.group(1)) for p in list((self.loop/'runs').glob('s*')) + list((self.loop/'logs').glob('s*.log'))
                if (m := re.fullmatch(r's(\d+)(?:-\d{6})?(?:\.log)?', p.name))]
        return f's{max(nums, default=0) + 1}'

    def lock_held(self):
        """(held, pid): whether some process holds driver.lock, and its PID if the lock file names a valid one (> 1)."""
        p = self.loop/'driver.lock'
        if not p.exists():
            return False, None
        with open(p, 'a+') as fd:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(fd, fcntl.LOCK_UN)
                return False, None
            except OSError:
                fd.seek(0)
                m = re.match(r'pid (\d+)', fd.read())
                pid = int(m.group(1)) if m else None
                return True, (pid if pid and pid > 1 else None)

    def hold_driver_lock(self):
        """Take driver.lock ourselves (no driver can start meanwhile) -> the open fd, or None if a driver holds it."""
        fd = open(self.loop/'driver.lock', 'a+')
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            fd.close()
            return None
        fd.seek(0); fd.truncate(); fd.write(f'supervisor {os.getpid()} applying a deploy {now()}\n'); fd.flush()
        return fd

    def request_boundary(self, why):
        if not self.boundary.exists():
            import uuid
            self.token = uuid.uuid4().hex
            tmp = self.loop/f'.RESTART-AT-BOUNDARY.tmp-{os.getpid()}'
            tmp.write_text(f'token {self.token} {now()} supervisor: {why}\n'); os.replace(tmp, self.boundary)
            self.log('boundary_requested', why=why, token=self.token)

    def watch(self, pid, proc=None):
        """Wait for the driver to exit; meanwhile turn READY/STOP into a boundary request (or TERM for STOP 'now').
        Adopted (proc None): it is gone once driver.lock is free or names another PID; it is never signalled."""
        termed = False
        while True:
            if proc is not None:
                if proc.poll() is not None:
                    return proc.returncode
            else:
                held, holder = self.lock_held()
                if not held:
                    return None
                if pid is not None and holder is not None and holder != pid:
                    return None                             # another driver took over: the caller re-adopts
            if self.stop.exists():
                if 'now' in self.stop.read_text(errors='replace').lower() and not termed:
                    if proc is not None:
                        self.log('stop_now', pid=proc.pid); proc.terminate(); termed = True
                    else:
                        self.log('stop_now_refused', pid=pid, why='adopted driver: never signalled; boundary request only')
                        self.request_boundary('stop (adopted driver)'); termed = True
                else:
                    self.request_boundary('stop')
            elif (self.staged/'READY').exists():
                self.request_boundary('staged deploy')
            time.sleep(1)

    def apply_staged(self):
        """-> True to relaunch, False = uncertain deploy state (ALERT written; the caller stops)."""
        ts = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
        apply = self.staged/'apply.sh'
        fd = self.hold_driver_lock()
        if fd is None:
            self.log('deploy_deferred', why='a driver holds driver.lock')
            return True
        rc, out = None, ''
        try:
            p = subprocess.Popen([SHELL, str(apply)], cwd=str(self.staged), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True, start_new_session=True)
            try:
                out = p.communicate(timeout=300)[0][-2000:]
                rc = p.returncode
            except subprocess.TimeoutExpired:
                out = 'TIMEOUT after 300 s'
            finally:
                _reap_group(p)                       # the whole apply session, before the lock is released
            if rc == 0 and (self.staged/'launch.sh').exists():
                if self.launch.exists():
                    shutil.copy2(self.launch, self.dir/f'launch.sh.bak-{ts}')
                tmp = self.dir/f'.launch.sh.tmp-{ts}'
                shutil.copy2(self.staged/'launch.sh', tmp); os.replace(tmp, self.launch)       # atomic publish
        except Exception as ex:
            rc, out = None, (out + ' ' + repr(ex))[-2000:]
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN); fd.close()
        try:
            (self.staged/'apply.out').write_text(out)
        except Exception:
            pass
        if rc not in (0, 10):
            self.staged.rename(self.dir/f'uncertain-{ts}')
            self.alert.write_text(f'{now()} staged deploy apply.sh rc={rc} (not 0/10: state uncertain); see '
                                  f'supervisor/uncertain-{ts}/apply.out. Supervisor stopped, no relaunch.\n')
            self.log('deploy_uncertain', rc=rc, dir=f'uncertain-{ts}', tail=out[-400:])
            return False
        if rc == 0:
            self.staged.rename(self.dir/f'applied-{ts}')
            self.log('deploy_applied', dir=f'applied-{ts}', launch_replaced=(self.dir/f'applied-{ts}'/'launch.sh').exists())
        else:
            self.staged.rename(self.dir/f'failed-{ts}')
            self.alert.write_text(f'{now()} staged deploy apply.sh rc={rc} (not applied, old state restored); see '
                                  f'supervisor/failed-{ts}/apply.out. Relaunching with the unchanged launch.sh.\n')
            self.log('deploy_failed', rc=rc, dir=f'failed-{ts}', tail=out[-400:])
        return True

    def took_boundary(self):
        """The last driver exited because it took THIS request (a .taken-<pid> file holding the current token); the
        receipt is retired (renamed .used-*) so it can never prove a later exit."""
        if self.token is None:
            return False
        ok = False
        for f in self.loop.glob('RESTART-AT-BOUNDARY.taken-*'):
            try:
                if f.read_text(errors='replace').split()[:2] == ['token', self.token]:
                    ok = True
                    f.rename(f.with_name(f.name.replace('.taken-', '.used-')))
            except OSError:
                pass
        if ok:
            self.token = None
        return ok

    def clear_stale_boundary(self):
        if self.boundary.exists():                     # a request nobody consumed must not end the next session early
            self.boundary.rename(self.loop/f'RESTART-AT-BOUNDARY.stale-{int(time.time())}')
            self.log('boundary_stale_cleared')

    def had_battle(self, name):
        run = self.loop/'runs'/name
        for ev in list(run.glob('m*/events.jsonl')) + list(run.glob('events.jsonl')):
            if '"match_start"' in ev.read_text(errors='replace'):
                return True
        return False

    def run(self):
        fails = 0
        if not self.stop.exists() and not (self.staged/'READY').exists():
            self.clear_stale_boundary()
        boundary_ok = True                                  # no driver yet: a staged deploy may apply
        while True:
            held, holder = self.lock_held()
            if held:                                        # a driver started by hand (or still starting): adopt it
                self.log('adopt', pid=holder)
                self.watch(holder)
                self.log('adopted_exit', pid=holder)
                boundary_ok = self.took_boundary()
                continue
            if self.stop.exists():
                self.log('stopped', why='SUPERVISOR-STOP')
                return 0
            if (self.staged/'READY').exists():
                if boundary_ok:
                    if not self.apply_staged():
                        return 3
                else:
                    self.log('deploy_waits', why='last exit was not a battle boundary (crash recovery first)')
            if self.stop.exists():                          # STOP may have arrived during apply
                self.log('stopped', why='SUPERVISOR-STOP')
                return 0
            self.clear_stale_boundary()
            name = self.next_name()
            t0 = time.monotonic()
            logf = open(self.loop/'logs'/f'{name}.log', 'ab')
            proc = subprocess.Popen([SHELL, str(self.launch), name], stdin=subprocess.DEVNULL, stdout=logf,
                                    stderr=subprocess.STDOUT, cwd=str(self.loop), start_new_session=True)
            logf.close()
            self.log('launch', session=name, pid=proc.pid, launch_sha=_sha(self.launch))
            rc = self.watch(proc.pid, proc)
            dt = time.monotonic() - t0
            boundary_ok = self.took_boundary()
            status = (self.loop/'status.txt').read_text(errors='replace')[:300] if (self.loop/'status.txt').exists() else ''
            battle = self.had_battle(name)
            self.log('exit', session=name, pid=proc.pid, rc=rc, seconds=round(dt, 1), battle=battle, status=status.strip())
            fails = fails + 1 if (dt < self.min_session and not battle) else 0
            if fails >= 3:
                self.alert.write_text(f'{now()} 3 sessions in a row ended within {self.min_session} s without a battle '
                                      f'(last {name}, rc {rc}, status {status.strip()!r}); supervisor exited, no relaunch.\n')
                self.log('give_up', session=name)
                return 2
            time.sleep(2 if fails == 0 else 10)


def _reap_group(p):
    """TERM then KILL the process group of a child started with start_new_session (pgid = its pid), and reap it."""
    for sig, wait in ((signal.SIGTERM, 5), (signal.SIGKILL, 5)):
        try:
            os.killpg(p.pid, sig)
        except (ProcessLookupError, PermissionError):
            break
        t = time.monotonic() + wait
        while time.monotonic() < t:
            try:
                os.killpg(p.pid, 0)
            except (ProcessLookupError, PermissionError):
                break
            time.sleep(.1)
    try:
        p.wait(timeout=5)
    except Exception:
        pass


def _sha(p):
    import hashlib
    return hashlib.sha256(p.read_bytes()).hexdigest()[:12] if p.exists() else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--loop-dir', default='~/clasher-live/loop')
    ap.add_argument('--min-session', type=float, default=120.)
    ap.add_argument('--first', default=None, help='name of the first session it launches (default: next sNN)')
    a = ap.parse_args()
    loop = Path(os.path.expanduser(a.loop_dir))
    sup = Sup(loop, a.min_session, a.first)
    lockfd = open(sup.dir/'supervisor.lock', 'a+')
    try:
        fcntl.flock(lockfd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        sys.exit('another supervisor is running')
    lockfd.seek(0); lockfd.truncate(); lockfd.write(f'pid {os.getpid()} started {now()}\n'); lockfd.flush()
    if not sup.launch.exists():
        sys.exit(f'missing {sup.launch}')
    sup.log('start', pid=os.getpid(), launch_sha=_sha(sup.launch))
    signal.signal(signal.SIGTERM, lambda s, f: (sup.log('supervisor_term'), sys.exit(0)))   # the driver keeps running
    return sup.run()


if __name__ == '__main__':
    sys.exit(main())
