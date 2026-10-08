"""Operational supervisor regression checks; no model/store imports or fitting."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile

spec = importlib.util.spec_from_file_location('watch', Path(__file__).with_name('lease_watch_pss.py'))
w = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)

def fake(root, pid, start, pss):
    p = root / str(pid)
    p.mkdir()
    fields = ['S'] + ['0'] * 21
    fields[19] = str(start)
    (p / 'stat').write_text(str(pid) + ' (worker name) ' + ' '.join(fields))
    (p / 'smaps_rollup').write_text('Rss: 100000000 kB\nPss: ' + str(pss) + ' kB\nPss_Anon: 12 kB\n')

with tempfile.TemporaryDirectory(prefix='t5-pss-test-', dir=Path(__file__).parent) as tmp:
    root = Path(tmp)
    fake(root, 101, 7, 1000)
    fake(root, 102, 8, 2000)
    # Summed RSS would be200GB; PSS is3MB. Ignore Pss_Anon and stale identity.
    assert w.tree_pss({101:'7',102:'8',103:'9'}, root) == 3000*1024
    assert w.tree_pss({101:'wrong',102:'8'}, root) == 2000*1024
    (root/'101'/'smaps_rollup').write_text('Rss: 100000000 kB\n')
    try:
        w.tree_pss({101:'7'}, root)
    except ValueError:
        pass
    else:
        raise AssertionError('missing live PSS must fail closed')
assert w.pss_capped('127x13', {'shared':True})
assert w.pss_capped('127x14', {'shared':True})
assert w.pss_capped('127x16', {'shared':True})
assert w.pss_capped('127x18', {'shared':True})
assert not w.pss_capped('127x11', {'shared':True})
assert not w.pss_capped('127x13', {'shared':False})
rows=w.processes()
assert w.tree_pss({os.getpid():rows[os.getpid()][1]}) > 0
known=w.owned(rows,{})
assert os.getpid() in known
print(json.dumps({'passed':True,'checks':['PSS versus multiply counted RSS','exact Pss field','stale/vanished PID','missing PSS fails closed','shared host scope','real smaps_rollup','owned supervisor included']}))
