"""HR-2 r3 mutation check: each mutant flips one slow/fast-lane rule; hr2_scenarios must fail for every mutant."""
import json, os, sys, tempfile, shutil
from pathlib import Path
HERE = Path(sys.argv[1]); sys.path[:0] = [str(HERE.parents[2]), str(HERE.parents[2]/'src'), str(HERE)]
os.chdir('/tmp')
import test_x4s4_offline as T, x4s4io as io, studytree as st
os.environ['X4S4_GUARD'] = f"{os.getpid()}:{io.proc_stat(os.getpid())['starttime']}:offline-tests"; st.WATCHDOG_MAX_AGE = 1e9
SP = "            t0 = time.monotonic(); self.slow_pass = (t0, None)"
FP = "            t0 = time.monotonic(); self.fast_pass = (t0, None)"
M = {
 # HR-2 r1 rules
 'disk walk back in the fast lane': [("        why = self.slow_verdict(now, time.monotonic(), r)", "        tree_bytes(self.job, 60.0)\n        why = self.slow_verdict(now, time.monotonic(), r)")],
 'no stuck-pass overdue': [("        if sp is not None and sp[1] is None and now-sp[0] > self.a.slow_budget:", "        if False:")],
 'no stale-age check': [("        return f'slow measurement (PSS/disk) older than {a.slow_max_age:g} s' if age > a.slow_max_age else None", "        return None")],
 'no missing-at-start check': [("            return f'no slow measurement (PSS/disk) within {a.slow_max_age:g} s' if mono-self.started > a.slow_max_age else None", "            return None")],
 'slow breach ignored': [("            if why is not None and self.breach is None: self.breach = (why, res)", "            if False: self.breach = (why, res)")],
 'slow worker not started': [("        threading.Thread(target=self.slow_worker, daemon=True).start()     # HR-2", "        pass")],
 'max-age validation removed': [("    if a.slow_max_age <= a.slow_cycle+a.slow_budget: raise SystemExit('--slow-max-age must exceed --slow-cycle + --slow-budget')", "    pass")],
 'slow pass unbounded (walk, main thread, late check)': [("        disk, vanished = tree_bytes(self.job, max(0.0, a.slow_budget-(t1-t0)))", "        disk, vanished = tree_bytes(self.job, 1e9)"),
     ("        if sp is not None and sp[1] is None and now-sp[0] > self.a.slow_budget:", "        if False:"),
     ("            if why is None and t1-t0 > self.a.slow_budget:", "            if False:")],
 # Sol r1 findings
 'F1 slow: two-step publish': [(SP, "            t0 = time.monotonic(); self.slow_pass = ((self.slow_pass or (t0,))[0], None); self.slow_pass = (t0, None)")],
 'F1 fast: two-step publish': [(FP, "            t0 = time.monotonic(); self.fast_pass = ((self.fast_pass or (t0,))[0], None); self.fast_pass = (t0, None)")],
 'F2 slow: late return accepted': [("            if why is None and t1-t0 > self.a.slow_budget:", "            if False:")],
 'F2 fast: late return accepted': [("            if why is None and t1-t0 > self.a.measure_budget:", "            if False:")],
 'F2 boundary inclusive (>=)': [("            if why is None and t1-t0 > self.a.slow_budget:", "            if why is None and t1-t0 >= self.a.slow_budget:")],
 'F3 wall-clock age': [("        age = mono-slow['mono']", "        age = now-slow['epoch']")],
 # Sol r2 finding (HR2R2-F1): completion order
 'R2F1 r2 completion order restored (slow)': [('            if why is not None and self.breach is None: self.breach = (why, res)\n            self.slow_pass = (t0, t1)\n            if why is None: self.slow = dict(res, mono=t1)', '            if why is None: self.slow = dict(res, mono=t1)\n            elif self.breach is None: self.breach = (why, res)\n            self.slow_pass = (t0, t1)')],
 'R2F1 slow breach after completion': [('            if why is not None and self.breach is None: self.breach = (why, res)\n            self.slow_pass = (t0, t1)\n            if why is None: self.slow = dict(res, mono=t1)', '            self.slow_pass = (t0, t1)\n            if why is not None and self.breach is None: self.breach = (why, res)\n            if why is None: self.slow = dict(res, mono=t1)')],
 'R2F1 fast breach after completion': [('            if why and self.breach is None: self.breach = (why, readings)   # HR2R2-F1 order: the breach, then completion\n            self.fast_pass = (t0, t1); self.progress = t1', '            self.fast_pass = (t0, t1); self.progress = t1\n            if why and self.breach is None: self.breach = (why, readings)')],
}
src = (HERE/'watchdog.py').read_text(); report = {}
for name, edits in M.items():
    s2 = src; ok = True
    for a, b in edits:
        if s2.count(a) != 1: ok = False; break
        s2 = s2.replace(a, b)
    if not ok: report[name] = dict(applied=False); continue
    tmp = Path(tempfile.mkdtemp(prefix='x4s4-hr2r3-mut-', dir='/dev/shm')); code = tmp/'code'; shutil.copytree(HERE, code, ignore=shutil.ignore_patterns('__pycache__'))
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
tmp = Path(tempfile.mkdtemp(prefix='x4s4-hr2r3-orig-', dir='/dev/shm')); orig = T.hr2_scenarios(tmp/'w'); shutil.rmtree(tmp, ignore_errors=True)
print(json.dumps(dict(original=orig, original_all_pass=all(orig.values()), mutants=report,
                      all_applied=all(v['applied'] for v in report.values()), all_killed=all(v.get('killed') for v in report.values())), indent=1))
