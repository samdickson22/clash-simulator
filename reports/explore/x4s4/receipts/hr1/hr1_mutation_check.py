"""HR-1 mutation check: each mutant flips one rule of the disk walk (studytree.tree_bytes / disk_bytes / watchdog);
hr1_scenarios + hr1_live must fail for every mutant."""
import json, os, sys, tempfile, shutil
from pathlib import Path
HERE = Path(sys.argv[1]); sys.path[:0] = [str(HERE.parents[2]), str(HERE.parents[2]/'src'), str(HERE)]
os.chdir('/tmp')
import test_x4s4_offline as T
M = {
 'vanished entry raises': ('studytree.py', "                    if exc.errno in VANISHED: vanished += 1; continue\n", "                    raise\n"),
 'EACCES tolerated': ('studytree.py', "VANISHED = (errno.ENOENT, errno.ENOTDIR)", "VANISHED = (errno.ENOENT, errno.ENOTDIR, errno.EACCES)"),
 'EIO tolerated': ('studytree.py', "VANISHED = (errno.ENOENT, errno.ENOTDIR)", "VANISHED = (errno.ENOENT, errno.ENOTDIR, errno.EIO)"),
 'root errors tolerated': ('studytree.py', "            if d != root and exc.errno in VANISHED: vanished += 1; continue\n", "            if exc.errno in VANISHED: vanished += 1; continue\n"),
 'ENOTDIR not tolerated': ('studytree.py', "VANISHED = (errno.ENOENT, errno.ENOTDIR)", "VANISHED = (errno.ENOENT,)"),
 'no timeout': ('studytree.py', "    end = time.monotonic()+timeout\n", "    end = float('inf')\n"),
 'hard links twice': ('studytree.py', "                if key in seen: continue", "                if False: continue"),
 'symlinks followed': ('studytree.py', "                try: s = e.stat(follow_symlinks=False)", "                try: s = e.stat(follow_symlinks=True)"),
 'mid-iteration vanish raises': ('studytree.py', "                    if d != root and exc.errno in VANISHED: vanished += 1; break\n", "                    raise\n"),
 'disk_bytes 0 on error': ('studytree.py', "            _disk['bytes'] = None\n        _disk['t'] = time.time()", "            _disk['bytes'] = 0\n        _disk['t'] = time.time()"),
 'watchdog back to du': ('watchdog.py', "        disk, r['disk_vanished'] = tree_bytes(self.job, a.du_timeout)",
                          "        disk = int(run_bounded(['/usr/bin/du', '-sb', '--', self.job], a.du_timeout).split()[0]); r['disk_vanished'] = 0"),
}
report = {}
for name, (f, a, b) in M.items():
    src = (HERE/f).read_text()
    if src.count(a) != 1: report[name] = dict(applied=False); continue
    tmp = Path(tempfile.mkdtemp(prefix='x4s4-hr1-mut-', dir='/dev/shm')); code = tmp/'code'; shutil.copytree(HERE, code, ignore=shutil.ignore_patterns('__pycache__'))
    (code/f).write_text(src.replace(a, b))
    try:
        r = T.hr1_scenarios(tmp/'w', code=code); live = T.hr1_live(tmp/'l', code=code)
        r['live'] = live['no_halt'] and live['beats'] >= 6
        report[name] = dict(applied=True, killed=not all(r.values()), failing=[k for k, v in r.items() if not v])
    except Exception as e:
        report[name] = dict(applied=True, killed=True, error=repr(e))
    finally:
        for p in tmp.rglob('*'):
            try: p.chmod(0o755) if p.is_dir() and not p.is_symlink() else None
            except OSError: pass
        shutil.rmtree(tmp, ignore_errors=True)
tmp = Path(tempfile.mkdtemp(prefix='x4s4-hr1-orig-', dir='/dev/shm'))
orig = T.hr1_scenarios(tmp/'w'); live = T.hr1_live(tmp/'l'); orig['live'] = live['no_halt'] and live['beats'] >= 6
shutil.rmtree(tmp, ignore_errors=True)
print(json.dumps(dict(original=orig, original_all_pass=all(orig.values()), mutants=report,
                      all_applied=all(v['applied'] for v in report.values()), all_killed=all(v.get('killed') for v in report.values())), indent=1))
