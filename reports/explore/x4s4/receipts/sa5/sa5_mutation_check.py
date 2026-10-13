"""SA-5 mutation check: each mutant flips one rule of qualify4 parity --final; sa5_scenarios must fail for every mutant."""
import json, os, sys, tempfile, shutil
from pathlib import Path
HERE = Path(sys.argv[1]); sys.path[:0] = [str(HERE.parents[2]), str(HERE.parents[2]/'src'), str(HERE)]
os.chdir('/tmp')
import test_x4s4_offline as T
import x4s4io as io, studytree as st
os.environ['X4S4_GUARD'] = f"{os.getpid()}:{io.proc_stat(os.getpid())['starttime']}:offline-tests"; st.WATCHDOG_MAX_AGE = 1e9
src = (HERE/'qualify4.py').read_text()
M = {
 'final mode still pauses': ("            if not final_mode: res['paused'] = pause(io.JOB, res)", "            res['paused'] = pause(io.JOB, res)"),
 'final flag ignored in parity': ("    final_mode = bool(getattr(a, 'final', False))", "    final_mode = False"),
 'final exit by verdict': ("        raise SystemExit(0 if final_check_completed(final) else 1)", "        raise SystemExit(0 if final['passed'] is True else 1)"),
 'final exit always 0': ("        raise SystemExit(0 if final_check_completed(final) else 1)", "        raise SystemExit(0)"),
 'rule ignores final': ("    return rec.get('final') is True and 'arms' in rec and", "    return 'arms' in rec and"),
 'rule ignores arms': ("rec.get('final') is True and 'arms' in rec and not", "rec.get('final') is True and not"),
 'rule ignores error': (" and not rec.get('error') and not rec.get('halted')", " and not rec.get('halted')"),
 'rule ignores halt': (" and not rec.get('error') and not rec.get('halted')", " and not rec.get('error')"),
 '--watch allowed': ("    if final_mode and a.watch: raise QualError('--final is a single final check (no --watch)')\n", ""),
}
report = {}
for name, (a, b) in M.items():
    if src.count(a) != 1: report[name] = dict(applied=False); continue
    tmp = Path(tempfile.mkdtemp(prefix='x4s4-sa5-mut-', dir='/dev/shm')); code = tmp/'code'; shutil.copytree(HERE, code, ignore=shutil.ignore_patterns('__pycache__'))
    (code/'qualify4.py').write_text(src.replace(a, b))
    try:
        r = T.sa5_scenarios(tmp/'w', code=code)
        report[name] = dict(applied=True, killed=not all(r.values()), failing=[k for k, v in r.items() if not v])
    except Exception as e:
        report[name] = dict(applied=True, killed=True, error=repr(e))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for m in [k for k in sys.modules if k.startswith('qualify4')]: del sys.modules[m]
tmp = Path(tempfile.mkdtemp(prefix='x4s4-sa5-orig-', dir='/dev/shm'))
orig = T.sa5_scenarios(tmp/'w'); shutil.rmtree(tmp, ignore_errors=True)
print(json.dumps(dict(original=orig, original_all_pass=all(orig.values()), mutants=report,
                      all_applied=all(v['applied'] for v in report.values()), all_killed=all(v.get('killed') for v in report.values())), indent=1))
