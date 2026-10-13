"""HR-2 mutation check: each mutant flips one rule of the watchdog's slow lane; hr2_scenarios must fail for every mutant."""
import json, os, sys, tempfile, shutil
from pathlib import Path
HERE = Path(sys.argv[1]); sys.path[:0] = [str(HERE.parents[2]), str(HERE.parents[2]/'src'), str(HERE)]
os.chdir('/tmp')
import test_x4s4_offline as T, x4s4io as io, studytree as st
os.environ['X4S4_GUARD'] = f"{os.getpid()}:{io.proc_stat(os.getpid())['starttime']}:offline-tests"; st.WATCHDOG_MAX_AGE = 1e9
M = {
 'disk walk back in the fast lane': ("        why = self.slow_verdict(now, time.monotonic(), r)", "        tree_bytes(self.job, 60.0)\n        why = self.slow_verdict(now, time.monotonic(), r)"),
 'no stuck-pass overdue': ("        if self.s_done is None and self.s_start is not None and now-self.s_start > self.a.slow_budget:", "        if False:"),
 'no stale-age check': ("        return f'slow measurement (PSS/disk) older than {a.slow_max_age:g} s' if now-slow['epoch'] > a.slow_max_age else None",
                        "        return None"),
 'no missing-at-start check': ("            return f'no slow measurement (PSS/disk) within {a.slow_max_age:g} s' if mono-self.started > a.slow_max_age else None",
                               "            return None"),
 'slow breach ignored': ("            elif self.breach is None: self.breach = (why, res)", "            elif False: self.breach = (why, res)"),
 'slow worker not started': ("        threading.Thread(target=self.slow_worker, daemon=True).start()     # HR-2", "        pass"),
 'max-age validation removed': ("    if a.slow_max_age <= a.slow_cycle+a.slow_budget: raise SystemExit('--slow-max-age must exceed --slow-cycle + --slow-budget')", "    pass"),
 'slow pass unbounded (walk and main thread)': ("        disk, vanished = tree_bytes(self.job, max(0.0, a.slow_budget-(t1-t0)))", "        disk, vanished = tree_bytes(self.job, 1e9)"),
}
src = (HERE/'watchdog.py').read_text(); report = {}
for name, (a, b) in M.items():
    s2 = src.replace(a, b) if src.count(a) == 1 else None
    if name == 'slow pass unbounded (walk and main thread)' and s2:
        s2 = s2.replace("        if self.s_done is None and self.s_start is not None and now-self.s_start > self.a.slow_budget:", "        if False:")
    if not s2: report[name] = dict(applied=False); continue
    tmp = Path(tempfile.mkdtemp(prefix='x4s4-hr2-mut-', dir='/dev/shm')); code = tmp/'code'; shutil.copytree(HERE, code, ignore=shutil.ignore_patterns('__pycache__'))
    (code/'watchdog.py').write_text(s2)
    try:
        r = T.hr2_scenarios(tmp/'w', code=code)
        report[name] = dict(applied=True, killed=not all(r.values()), failing=[k for k, v in r.items() if not v])
    except Exception as e:
        report[name] = dict(applied=True, killed=True, error=repr(e))
    finally:
        for p in tmp.rglob('*'):
            try: p.chmod(0o755) if p.is_dir() and not p.is_symlink() else None
            except OSError: pass
        shutil.rmtree(tmp, ignore_errors=True)
tmp = Path(tempfile.mkdtemp(prefix='x4s4-hr2-orig-', dir='/dev/shm')); orig = T.hr2_scenarios(tmp/'w'); shutil.rmtree(tmp, ignore_errors=True)
print(json.dumps(dict(original=orig, original_all_pass=all(orig.values()), mutants=report,
                      all_applied=all(v['applied'] for v in report.values()), all_killed=all(v.get('killed') for v in report.values())), indent=1))
