"""SA-4 mutation check: each mutant flips one rule of supervise.parity_watch; sa4_scenarios must fail for every mutant."""
import json, os, sys, tempfile, shutil
from pathlib import Path
HERE = Path(sys.argv[1]); sys.path[:0] = [str(HERE.parents[2]), str(HERE.parents[2]/'src'), str(HERE)]
os.chdir('/tmp')
import test_x4s4_offline as T
import x4s4io as io, studytree as st
os.environ['X4S4_GUARD'] = f"{os.getpid()}:{io.proc_stat(os.getpid())['starttime']}:offline-tests"; st.WATCHDOG_MAX_AGE = 1e9
src = (HERE/'supervise.py').read_text()
M = {
 'direction flipped (< instead of >)': ("r['pct'][k] > r['x4s3_r3a'][k] + 2.0", "r['pct'][k] < r['x4s3_r3a'][k] - 2.0"),
 'no +2 pp margin': ("r['pct'][k] > r['x4s3_r3a'][k] + 2.0", "r['pct'][k] > r['x4s3_r3a'][k]"),
 'any -> all metrics': ("and any(r['pct'][k]", "and all(r['pct'][k]"),
 'cutoff only': ("PARITY_METRICS = ('cutoff', 'student_default', 'overrun')", "PARITY_METRICS = ('cutoff',)"),
 'evaluated ignored': ("if r['evaluated'] and any(", "if any("),
 'low side pauses': ("    try:\n        io.append_json_line(job+'/receipts/parity-lowside.jsonl'", "    qualify4.pause(job, res); return 'parity_pause'\n    try:\n        io.append_json_line(job+'/receipts/parity-lowside.jsonl'"),
 'low side not recorded': ("        io.append_json_line(job+'/receipts/parity-lowside.jsonl', dict(", "        (lambda *a, **k: None)(job+'/receipts/parity-lowside.jsonl', dict("),
 'record failure ignored': ("        return f'parity_monitor_failed: low-side record: {exc!r}'", "        return None"),
 'monitor exception ignored': ("        return f'parity_monitor_failed: {exc!r}'\n    if not res", "        return None\n    if not res"),
 'high side not paused': ("        qualify4.pause(job, dict(res, high_side=high)); return 'parity_pause'", "        return None"),
}
report = {}
for name, (a, b) in M.items():
    if src.count(a) != 1: report[name] = dict(applied=False); continue
    tmp = Path(tempfile.mkdtemp(prefix='x4s4-sa4-mut-', dir='/dev/shm')); f = HERE/'supervise_sa4mut.py'
    f.write_text(src.replace(a, b))
    try:
        mod = T.load_fresh('supervise_mut', f); r = T.sa4_scenarios(mod, tmp)
        report[name] = dict(applied=True, killed=not all(r.values()), failing=[k for k, v in r.items() if not v])
    except Exception as e:
        report[name] = dict(applied=True, killed=True, error=repr(e))
    finally:
        f.unlink(); shutil.rmtree(tmp, ignore_errors=True)
tmp = Path(tempfile.mkdtemp(prefix='x4s4-sa4-orig-', dir='/dev/shm'))
orig = T.sa4_scenarios(T.load_fresh('supervise_orig', HERE/'supervise.py'), tmp); shutil.rmtree(tmp, ignore_errors=True)
print(json.dumps(dict(original_all_pass=all(orig.values()), mutants=report,
                      all_applied=all(v['applied'] for v in report.values()), all_killed=all(v.get('killed') for v in report.values())), indent=1))
