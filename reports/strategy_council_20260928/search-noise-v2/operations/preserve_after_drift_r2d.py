"""Read-only peer backup after external seal overwrite; never resume or analyze."""
from pathlib import Path
import collections
import hashlib
import json
import shlex
import socket
import subprocess
import sys
import time
import traceback

HERE = Path(__file__).resolve().parents[1]
OPS = HERE / 'operations'
INCIDENT = OPS / 'incident-seal-overwrite-r2b'
FROZEN = INCIDENT / 'frozen-r2'
EXPECTED_SHA = '3ad63c0a7ad1634bac32bf5b031a7a312013497d8863aeaa3b0e2b0e077e5677'
SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10', '-o', 'ConnectionAttempts=1',
       '-o', 'ServerAliveInterval=10', '-o', 'ServerAliveCountMax=2']
assert socket.gethostname().split('.')[0] == '127x01'
manifest = json.loads((FROZEN / 'evaluation-manifest.json').read_text())
assert hashlib.sha256((FROZEN / 'evaluation-manifest.json').read_bytes()).hexdigest() == EXPECTED_SHA
for rel, want in manifest['files'].items():
    assert hashlib.sha256((FROZEN / rel).read_bytes()).hexdigest() == want, rel
scope = {}
exec(compile((FROZEN / 'cells.py').read_text(), str(FROZEN / 'cells.py'), 'exec'), scope)
schedule = json.loads((FROZEN / 'schedule.json').read_text())
expected = [(ep, cell, seat) for ep in schedule['pairs'] for cell in
            (scope['CELLS'] if ep['mode'] == 'scripts' else scope['H2H']) for seat in (0, 1)]


def write(path, value):
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(value, indent=2) + '\n')
    tmp.replace(path)


def validate(path):
    i = int(path.stem)
    assert 0 <= i < 4992
    r = json.loads(path.read_text())
    ep, cell, seat = expected[i]
    for key, want in [('manifest', EXPECTED_SHA), ('terminal', True), ('job', i), ('seed', ep['seed']),
                      ('noise_seed', ep['noise_seed']), ('pair', ep['pair']), ('seat', seat),
                      ('variant', cell), ('mode', ep['mode'])]:
        assert r[key] == want, (i, key)
    host = r['host']['hostname'].split('.')[0]
    assert (host == '127x04' and i % 248 < 48) or (host == '127x08' and i % 248 >= 148)
    assert r['started'] >= manifest['sealed_unix'] and r['host']['nice'] >= 10 and r['host']['native_threads'] == 1
    return r


end = time.time() + 6 * 3600
last = {}
try:
    while True:
        nodes = {}
        unique = {}
        cpu = 0.
        counts = collections.Counter()
        for host in ('127x04', '127x08'):
            target = INCIDENT / 'preserved-receipts' / host
            target.mkdir(parents=True, exist_ok=True)
            p = subprocess.run(['rsync', '-a', '--ignore-existing', '--exclude=*.tmp', '--timeout=60',
                                '-e', shlex.join(SSH), f'{host}:{HERE}/confirmation/', str(target) + '/'],
                               capture_output=True, text=True, timeout=90)
            assert p.returncode == 0, ('host transport stopped; no retry', host, p.stderr)
            code = f'''
from pathlib import Path
import json,subprocess,time,os
j=Path('/mpac/sdicks02/jobs/clasher');s=Path({str(HERE)!r});h={host!r}
indices=range(48) if h=='127x04' else range(148,248)
workers={{}}
for i in indices:
 e=j/f's1-confirm-{{i}}-r2.exit';p=j/f's1-confirm-{{i}}-r2.pid'
 if e.exists():
  workers[str(i)]=dict(exit=e.read_text().strip(),pid=p.read_text().strip() if p.exists() else None)
  if e.read_text().strip()!='0':workers[str(i)]['log']=(j/f's1-confirm-{{i}}-r2.log').read_text()
e=j/f's1-confirm-node-{{h}}-r2.exit'
print(json.dumps(dict(utc=time.time(),supervisor_exit=e.read_text().strip() if e.exists() else None,
 workers=workers,processes=subprocess.check_output(['ps','-u',str(os.getuid()),'-o','pid,ppid,ni,stat,args','--no-headers'],text=True))))
'''
            p = subprocess.run(SSH + [host, '/mpac/sdicks02/repos/clasher/.venv/bin/python', '-B', '-'],
                               input=code, capture_output=True, text=True, timeout=40)
            assert p.returncode == 0, ('host status stopped; no retry', host, p.stderr)
            state = json.loads(p.stdout)
            write(INCIDENT / f'preserved-status-{host}.json', state)
            nodes[host] = dict(supervisor_exit=state['supervisor_exit'],
                               exited_workers=len(state['workers']),
                               failed_indices=[int(i) for i, w in state['workers'].items() if w['exit'] != '0'],
                               successful_indices=[int(i) for i, w in state['workers'].items() if w['exit'] == '0'])
            for path in sorted(target.glob('*.json')):
                r = validate(path)
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                if r['job'] in unique:
                    assert unique[r['job']] == digest, ('duplicate changed', r['job'])
                    continue
                unique[r['job']] = digest
                counts[r['host']['hostname'].split('.')[0]] += 1
                cpu += r['cpu_seconds']
        last = dict(utc=time.time(),scope='backup only after external seal overwrite; no admission, restart or analysis',
                    identity_valid_preserved_receipts=len(unique), per_physical_host=dict(counts),
                    recorded_game_cpu_hours=cpu / 3600, nodes=nodes, outcomes_inspected=False,
                    qualification='Receipt identities pass against preserved r2 manifest; runtime integrity incident requires adjudication')
        write(OPS / 'preservation-monitor-r2d.json', last)
        print(json.dumps(last), flush=True)
        subprocess.run(['rsync', '-a', '-e', shlex.join(SSH), str(OPS / 'preservation-monitor-r2d.json'),
                        f'127x05:{OPS}/'], check=True, timeout=40)
        if all(n['supervisor_exit'] is not None for n in nodes.values()):
            break
        if time.time() >= end:
            raise RuntimeError('Six-hour preservation window exhausted; no retry')
        time.sleep(60)
except BaseException as e:
    write(OPS / 'preservation-error-r2d.json', dict(utc=time.time(),error=repr(e),traceback=traceback.format_exc(),last=last))
    raise
