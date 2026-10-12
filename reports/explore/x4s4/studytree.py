"""X4S-4 study-wide process tree and aggregate admission (Sol r1 F9; exploration, NEVER ADOPTABLE). Stdlib only.

The X4S-4 tree is every process group recorded under the job: the driver (driver/driver.pid), fits
(receipts/fit-*-launch*.json), reporting supervisors (receipts/phase-*-launch.json), every supervisor/child group
of a games/collect/qual/smoke phase (<phase>/launch.json) and every registered CPU job (receipts/cpujob-*.json,
written by label.py and collect_w.py at start). Admission for a new unit of work requires <= 70 live processes in
that tree and <= 100 GB under the job (du, cached 300 s); an unreadable measurement blocks (fail closed).
"""
import json, os, subprocess, time
from pathlib import Path

import confine

MAX_PROCESSES, MAX_DISK_BYTES, DISK_CACHE_SECONDS = 70, 100*10**9, 300
_disk = dict(t=0.0, bytes=None)


def _pgid(path, key):
    try: return int(json.loads(Path(path).read_text())[key])
    except (OSError, ValueError, KeyError, TypeError): return None


def groups(job):
    job = Path(job); out = {os.getpgrp()}
    recs = [(job/'driver'/'driver.pid', 'pgid'), *[(p, 'pgid') for p in sorted((job/'receipts').glob('fit-*-launch*.json'))],
            *[(p, 'pgid') for p in sorted((job/'receipts').glob('phase-*-launch.json'))],
            *[(p, 'pgid') for p in sorted((job/'receipts').glob('cpujob-*.json'))]]
    for role in ('games', 'collect', 'qual', 'smoke'):
        for p in sorted((job/role).glob('**/launch.json')):
            recs += [(p, 'child_pgid'), (p, 'supervisor_pgid')]
    for p, key in recs:
        g = _pgid(p, key)
        if g is not None: out.add(g)
    return out


def processes(pgids):
    pids = []
    for d in Path('/proc').iterdir():
        if not d.name.isdigit(): continue
        try:
            if int((d/'stat').read_text().rsplit(')', 1)[1].split()[2]) in pgids: pids.append(int(d.name))
        except (FileNotFoundError, ProcessLookupError, IndexError, ValueError): pass
    return pids


def disk_bytes(job):
    if _disk['bytes'] is None or time.time()-_disk['t'] > DISK_CACHE_SECONDS:
        try:
            r = subprocess.run(['du', '-sb', str(job)], capture_output=True, text=True, timeout=600)
            _disk['bytes'] = int(r.stdout.split()[0]) if r.returncode == 0 else None
        except Exception: _disk['bytes'] = None
        _disk['t'] = time.time()
    return _disk['bytes']


def admission(job, disk=True):
    """(ok, reason): <= 70 processes in the X4S-4 tree and (if disk) <= 100 GB under the job; unreadable blocks."""
    try: n = len(processes(groups(job)))
    except OSError: return False, 'process scan failed'
    if n > MAX_PROCESSES: return False, f'{n} X4S-4 processes > {MAX_PROCESSES}'
    if disk:
        b = disk_bytes(job)
        if b is None: return False, 'disk usage unreadable'
        if b > MAX_DISK_BYTES: return False, f'{b} bytes under the job > {MAX_DISK_BYTES}'
    return True, None


def register(job, name):
    """Record this CPU job's process group so the driver, supervisors and admission count it."""
    p = confine.writable(str(Path(job)/'receipts'/f'cpujob-{name}-{os.getpid()}.json'), roles=('receipts',), must_not_exist=True)
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    with os.fdopen(fd, 'w') as f:
        f.write(json.dumps(dict(name=name, pid=os.getpid(), pgid=os.getpgrp(), utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())))+'\n')
    return p
