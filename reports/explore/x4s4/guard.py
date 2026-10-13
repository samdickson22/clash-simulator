"""X4S-4 guard runner (r8, Sol r7 R7-F1..F3; exploration, NEVER ADOPTABLE). Stdlib only, Python 3.8+.

One reviewed wrapper for every long-running or spawning study step that is not itself a supervising parent
(supervise.py and driver.py carry the same Enforcer internally). Usage, on 127x01 at nice 10:

  guard.py --name NAME [--add N] [--gpu] [--readout] [--cwd DIR] [--output PATH]... [--new-files PREFIX]... -- ARGV...

  1. Fresh destinations: the receipt <job>/receipts/guard-NAME.json and every --output must not exist (no resume).
  2. Admission (studytree.admit): cheap STOP/deadline, then dispatch_ok + admission(+N processes) [+ GPU readable and
     <= 8 GiB used with --gpu] as ONE bounded measurement (a miss refuses), then STOP/deadline again LAST; the runner
     and the child group are registered (receipts/cpujob-guard-*), and a final cheap check runs right before spawn.
  3. The child runs in its own process group with X4S4_GUARD=<runner pid>:<starttime>:<name>; owned entry points
     refuse to run without it and end themselves if the runner disappears (studytree.require_guard).
  4. Live monitor: a thread runs the frozen running-work rules (studytree.monitor on the child group [+ GPU readable and
     <= 40 GB]) every MONITOR_PERIOD s. Independent expiry: studytree.Enforcer checks STOP/deadline and the age of the
     last completed verdict every second without measuring; STOP, the deadline, a breach or a verdict older than
     MONITOR_STALE s stops the child by verified PIDs (TERM, then KILL), writes the failed receipt and exits 3. A stuck
     measurement therefore cannot delay expiry beyond the stop budget. SIGTERM to the runner is handled the same way.
  5. Acceptance, only after the child exited 0: every --output exists (a directory must re-verify its complete seal;
     its identity is its manifest SHA), new files under each --new-files prefix are hashed; then a FRESH bounded
     resource verdict, then STOP/deadline LAST, then the receipt is written with passed=true - under the same lock the
     breach path uses, so a breach can never be overtaken by a success. Any nonzero/unknown exit, missing output, failed
     seal or breach writes passed=false. Consumers accept an output only through studytree.guarded_output.
  --readout (contention.py, reduce.py, write_report.py only): post-study readout; the immutable deadline does not
  apply (E8: the reduction follows the stop); STOP and every resource rule still do.
"""
import argparse, json, os, re, signal, sys, threading, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import x4s4io as io                                    # noqa: E402
import studytree                                        # noqa: E402

READOUT_SCRIPTS = ('reports/explore/x4s4/contention.py', 'reports/explore/x4s4/reduce.py', 'reports/explore/x4s4/write_report.py')
GPU_ADMIT_MIB, GPU_LIMIT_MIB = 8*1024, 40*1024


def utc(): return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def gpu_used_mib():
    try:
        r = io.run_checked(['/usr/bin/nvidia-smi', '--query-gpu=memory.used', '--format=csv,noheader,nounits'], 20, 4096,
                           env={'LC_ALL': 'C', 'PATH': '/usr/bin:/bin'})
        v = int(r.stdout.split()[0]); return v if v >= 0 else None
    except (io.Refusal, ValueError, IndexError):
        return None


def gpu_admit():
    g = gpu_used_mib()
    return None if g is not None and g <= GPU_ADMIT_MIB else f'GPU unreadable or {g} MiB already used'


def gpu_live():
    g = gpu_used_mib()
    return None if g is not None and g <= GPU_LIMIT_MIB else 'gpu_unreadable_or_over_40GB'


class Runner:
    def __init__(self, job, name, argv, add=1, gpu=False, readout=False, cwd=None, outputs=(), new_files=()):
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,80}', name): raise SystemExit('--name: [A-Za-z0-9._-], at most 81 characters')
        if not argv: raise SystemExit('a command is required after --')
        if readout and not any(a.endswith(READOUT_SCRIPTS) for a in argv):
            raise SystemExit('--readout is only for contention.py, reduce.py and write_report.py')
        self.job, self.name, self.argv, self.add, self.gpu, self.readout = job, name, list(argv), add, gpu, readout
        self.cwd, self.outputs, self.new_prefixes = cwd, [str(p) for p in outputs], [str(p) for p in new_files]
        self.receipt = f'{job}/receipts/guard-{name}.json'
        self.lock, self.finalized, self.breach, self.child, self.exit = threading.Lock(), False, None, None, os._exit
        self.done, self.breach_done = threading.Event(), threading.Event()

    # -------------------------------------------------------------- receipt (exactly one, exclusive)
    def write(self, passed, **kw):
        body = dict(schema='x4s4.guard.v1', name=self.name, argv=self.argv, cwd=self.cwd, readout=self.readout, gpu=self.gpu,
                    add=self.add, child={k: self.child[k] for k in ('pid', 'pgid', 'starttime')} if self.child else None,
                    passed=bool(passed), utc=utc(), label='X4S-4 guarded step, exploration, NEVER ADOPTABLE', **kw)
        io.write_json_once(self.receipt, body, roles=('receipts',), mode=0o444)
        return body

    def fail(self, why, code=3, **kw):
        """Terminal failure (refusal or breach): one failed receipt, then the process ends."""
        with self.lock:
            if self.finalized: return None
            self.finalized = True
            rc = self.child['popen'].poll() if self.child else None
            body = self.write(False, error=why, breach=self.breach, returncode=rc, **kw)
        print(json.dumps(dict(guard=self.name, passed=False, error=why)), flush=True)
        self.exit(code)
        return body

    # -------------------------------------------------------------- live guards
    def on_breach(self, why):
        """Enforcer callback (never measures): stop the child by verified PIDs, then the failed receipt and exit 3."""
        self.breach = why
        try:
            if self.child and self.child['popen'].poll() is None:
                io.stop_owned(self.child['pgid'], self.child['starttime'], term_grace=30, kill_grace=30)
            self.fail(f'guard breach: {why}')
        finally:
            self.breach_done.set()

    def _monitor(self):
        own = (self.child['pgid'], self.child['starttime'])
        while not self.done.is_set():
            try: why = studytree.monitor(self.job, own=own, deadline=not self.readout) or (gpu_live() if self.gpu else None)
            except Exception as exc: why = f'monitor_failed: {exc!r}'
            self.enforcer.verdict(why)
            if why or self.done.wait(studytree.MONITOR_PERIOD): return

    # -------------------------------------------------------------- the run
    def run(self, env=None):
        main = threading.current_thread() is threading.main_thread()
        prev = signal.getsignal(signal.SIGTERM) if main else None
        try: return self._run(env)
        finally:
            if main: signal.signal(signal.SIGTERM, prev)               # restore (matters only for in-process callers)

    def _run(self, env=None):
        for p in [self.receipt]+self.outputs:
            io.check_writable(p, roles=io.ROLES, must_not_exist=True, report=p.startswith(io.REPORT_ROOT+'/'))
        why = studytree.admit(self.job, self.add, gpu_admit if self.gpu else None, deadline=not self.readout)
        if why: return self.fail(why)
        before = {p: set(self._matches(p)) for p in self.new_prefixes}
        studytree.register(self.job, f'guard-{self.name}-runner')
        why = studytree.cheap_halt(self.job, not self.readout)          # LAST, immediately before the child exists
        if why: return self.fail('admission: '+why)
        me = io.own_identity()
        env = dict(os.environ if env is None else env, X4S4_GUARD=f"{me['pid']}:{me['starttime']}:{self.name}")
        self.child = io.spawn(self.argv, f'{self.job}/logs/guard-{self.name}.log', env, cwd=self.cwd)
        io.write_json_once(f'{self.job}/receipts/cpujob-guard-{self.name}.json',
                           dict(name=f'guard-{self.name}', pid=self.child['pid'], pgid=self.child['pgid'],
                                starttime=self.child['starttime'], utc=utc()), roles=('receipts',), mode=0o644)
        # staleness applies while the child lives; STOP/deadline also through acceptance (seal verification may be long)
        self.enforcer = studytree.Enforcer(self.job, self.on_breach, deadline=not self.readout,
                                           active=lambda: not self.done.is_set()).start()
        if threading.current_thread() is threading.main_thread():    # SIGTERM to the runner: stop the child, fail
            signal.signal(signal.SIGTERM, lambda *a: threading.Thread(target=self.enforcer.fire, args=('runner_SIGTERM',), daemon=True).start())
        threading.Thread(target=self._monitor, daemon=True).start()
        rc = self.child['popen'].wait()
        self.done.set()                                               # the enforcer keeps running through acceptance
        if self.breach is not None:                                   # the breach path owns the outcome
            self.breach_done.wait(180); return None
        if self.finalized: return None
        if rc != 0: return self.fail(f'child exit {rc}', code=1)
        outputs, new_files = {}, {}
        try:
            for p in self.outputs:
                if not io.lexists(p): return self.fail(f'declared output missing: {p}', code=1)
                if io.is_real_dir(p): io.verify_sealed_dir(p)
                outputs[p] = studytree.output_identity(p)
            for pre in self.new_prefixes:
                for p in sorted(set(self._matches(pre)) - before[pre]): new_files[p] = io.sha256_file(p)
        except io.Refusal as exc:
            return self.fail(f'output verification: {exc}', code=1)
        why = studytree.fresh_verdict(self.job, extra=gpu_live if self.gpu else None, deadline=not self.readout)
        with self.lock:
            if self.finalized: return None
            if why is None: why = studytree.cheap_halt(self.job, not self.readout)   # LAST, under the acceptance lock
            if why is None:
                self.finalized = True; self.enforcer.stop()
                body = self.write(True, returncode=rc, outputs=outputs, new_files=new_files, final_verdict=None)
        if why is not None: return self.fail(f'final guard: {why}', code=1)
        print(json.dumps(dict(guard=self.name, passed=True, outputs=outputs, new_files=sorted(new_files))), flush=True)
        return body

    @staticmethod
    def _matches(prefix):
        d, stem = os.path.dirname(prefix), os.path.basename(prefix)
        if not io.is_real_dir(d): return []
        return [f'{d}/{n}' for n in io.listdir(d) if n.startswith(stem)]


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if '--' not in argv: raise SystemExit('usage: guard.py --name NAME [options] -- COMMAND...')
    k = argv.index('--')
    ap = argparse.ArgumentParser()
    ap.add_argument('--name', required=True); ap.add_argument('--add', type=int, default=1)
    ap.add_argument('--gpu', action='store_true'); ap.add_argument('--readout', action='store_true'); ap.add_argument('--cwd')
    ap.add_argument('--output', action='append', default=[]); ap.add_argument('--new-files', action='append', default=[])
    a = ap.parse_args(argv[:k])
    if not 1 <= a.add <= studytree.MAX_PROCESSES: raise SystemExit('--add must be within 1..70')
    if os.getpriority(os.PRIO_PROCESS, 0) < 10: raise SystemExit('guard.py runs at nice >= 10')
    r = Runner(io.JOB, a.name, argv[k+1:], a.add, a.gpu, a.readout, a.cwd, a.output, a.new_files)
    body = r.run()
    raise SystemExit(0 if body and body.get('passed') is True else 1)


if __name__ == '__main__':
    main()
