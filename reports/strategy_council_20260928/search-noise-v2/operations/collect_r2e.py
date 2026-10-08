"""Outcome-blind collector/scheduler; fail closed on surviving-host loss.

Operational only: original launcher/worker/analysis and all sealed inputs stay
unchanged. Quarantine is checked once at the completion barrier, not retried.
"""
import collections
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import socket
import subprocess
import sys
import time
import traceback
from migration_r2e import HERE, OPS, JOBS, MANIFEST, mapping, verified, write

ROOT = HERE.parents[2]
HOSTS = ('127x04', '127x08')
SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10', '-o', 'ConnectionAttempts=1',
       '-o', 'ServerAliveInterval=10', '-o', 'ServerAliveCountMax=2']
sys.path.insert(0, str(HERE))
from cells import CELLS, H2H
MAN = json.loads((HERE / 'evaluation-manifest.json').read_text())
SCHEDULE = json.loads((HERE / 'schedule.json').read_text())
EXPECTED = [(ep, cell, seat) for ep in SCHEDULE['pairs'] for cell in
            (CELLS if ep['mode'] == 'scripts' else H2H) for seat in (0, 1)]
ASSIGN = {w['index']: w['host'] for w in mapping('analyze')['workers']}


def remote(host, code):
    p = subprocess.run(SSH + [host, str(ROOT / '.venv/bin/python'), '-B', '-'],
                       input=code, capture_output=True, text=True, timeout=45)
    if p.returncode:
        raise RuntimeError(f'{host} SSH/status failed: {p.returncode}: {p.stderr[-1500:]}')
    return json.loads(p.stdout)


def snapshot(host):
    return remote(host, f'''
from pathlib import Path
import json,subprocess,socket,time
h={host!r};s=Path({str(HERE)!r});j=Path({str(JOBS)!r})
assert socket.gethostname().split('.')[0]==h
out=dict(utc=time.time(),host=h,who=subprocess.check_output(['who'],text=True),attempts={{}})
for a in ('r2','r2e','r2f'):
 label=f's1-confirm-node-{{h}}-{{a}}'
 e=j/(label+'.exit');p=j/(label+'.pid');l=s/f'launch-{{h}}-{{a}}.json'
 d=dict(supervisor_exit=e.read_text().strip() if e.exists() else None,
        pid=p.read_text().strip() if p.exists() else None,partitions={{}})
 if l.exists():
  launch=json.loads(l.read_text());d['launch']=launch
  for w in launch['workers']:
   x=j/(w['label']+'.exit');done=s/f'worker-{{w["index"]}}-done.json'
   if x.exists():
    code=x.read_text().strip();entry=dict(exit=code,label=w['label'])
    if code=='0':
     assert done.exists(), ('success without done',w['index'])
     entry['done']=json.loads(done.read_text());entry['log']=(j/(w['label']+'.log')).read_text()
    d['partitions'][str(w['index'])]=entry
 out['attempts'][a]=d
out['processes']=subprocess.check_output(['ps','-u',str(__import__('os').getuid()),'-o','pid,ppid,ni,stat,comm,args','--no-headers'],text=True)
print(json.dumps(out))
''')


def fetch(host, dest):
    dest.mkdir(parents=True, exist_ok=True)
    p = subprocess.run(['rsync', '-a', '--ignore-existing', '--timeout=60', '--exclude=*.tmp',
                        '-e', shlex.join(SSH), f'{host}:{HERE}/confirmation/', str(dest) + '/'],
                       capture_output=True, text=True, timeout=90)
    if p.returncode:
        raise RuntimeError(f'{host} receipt transport failed {p.returncode}: {p.stderr[-1500:]}')


def validate(path, physical_host=None, quarantine=False):
    i = int(path.stem)
    assert 0 <= i < 4992 and path.name == f'{i:05d}.json'
    r = json.loads(path.read_text())
    ep, cell, seat = EXPECTED[i]
    assert r['terminal'] and r['manifest'] == MANIFEST and r['job'] == i, ('identity', i)
    for key, want in [('seed', ep['seed']), ('noise_seed', ep['noise_seed']), ('pair', ep['pair']),
                      ('seat', seat), ('variant', cell), ('mode', ep['mode'])]:
        assert r[key] == want, (i, key)
    host = r['host']['hostname'].split('.')[0]
    if physical_host is not None:
        assert host == physical_host, ('physical host', i, host, physical_host)
    if quarantine:
        assert host == '127x07' and 48 <= i % 248 < 148
    else:
        assert host == ASSIGN[i % 248], ('host mapping', i, host)
    assert r['started'] >= MAN['sealed_unix'] and r['host']['nice'] >= 10
    assert r['host']['native_threads'] == 1
    assert len(r['action_sha256']) == 64
    if host == '127x04' and r['started'] < 1791424462.27:
        assert r['started'] + r['elapsed'] < 1791423540, ('excluded incident receipt', i)
    # Only identity, terminal/execution metadata, action digest and CPU are accessed.
    return r


def admit(host):
    stage = OPS / 'staged-receipts-r2e' / host
    fetch(host, stage)
    target = HERE / 'confirmation'
    target.mkdir(exist_ok=True)
    for path in sorted(stage.glob('*.json')):
        r = validate(path)
        dest = target / path.name
        if r['host']['hostname'].split('.')[0] != host:
            # The existing hub backup mirrors all hub data to 04 every 30 min.
            # Accept its presence only as an exact already-admitted replica.
            assert dest.exists() and dest.read_bytes() == path.read_bytes(), ('unproven backup replica', host, path.name)
            continue
        if dest.exists():
            old = validate(dest)
            assert old['action_sha256'] == r['action_sha256'], ('action mismatch', path.name)
            assert dest.read_bytes() == path.read_bytes(), ('immutable receipt changed', path.name)
        else:
            # First valid receipt admitted; later copies cannot overwrite it.
            with dest.open('xb') as stream:
                stream.write(path.read_bytes())


def collect_status(host, snap):
    status = HERE / 'collected-status'
    status.mkdir(exist_ok=True)
    for attempt, state in snap['attempts'].items():
        if (host == '127x04' and attempt == 'r2') or (host == '127x08' and attempt == 'r2e'):
            continue  # Original 04 failure remains preserved; only r2e replaces it.
        if state['pid'] is not None and state['supervisor_exit'] is None:
            rows = {line.split(None, 1)[0]: line for line in snap['processes'].splitlines()}
            assert state['pid'] in rows, ('supervisor vanished without exit', host, attempt, state['pid'])
            assert f's1-confirm-node-{host}-{attempt}' in rows[state['pid']], ('supervisor PID reused', host, attempt)
        if state['supervisor_exit'] not in (None, '0'):
            raise RuntimeError(f'{host} {attempt} supervisor failed: {state["supervisor_exit"]}')
        if 'launch' in state:
            expected = ([i for i in range(248) if ASSIGN[i] == host and 48 <= i < 148]
                        if attempt == 'r2f' else list(range(48)) if host == '127x04' else list(range(148, 248)))
            assert [w['index'] for w in state['launch']['workers']] == expected, ('launched index set', host, attempt)
            write(HERE / f'launch-{host}-{attempt}.json', state['launch'])
        for key, entry in state['partitions'].items():
            i = int(key)
            assert ASSIGN[i] == host
            assert entry['exit'] == '0', ('worker failure', host, i, entry['exit'])
            assert entry['done']['complete'] and entry['done']['manifest'] == MANIFEST
            write(status / f'worker-{i}-done.json', entry['done'])
            (status / f'worker-{i}.exit').write_text('0\n')
            (status / f'worker-{i}.log').write_text(entry['log'])


def technical(nodes):
    counts = collections.Counter()
    cpu = 0.
    for p in sorted((HERE / 'confirmation').glob('*.json')):
        r = validate(p)
        counts[r['host']['hostname'].split('.')[0]] += 1
        cpu += r['cpu_seconds']
    complete = 0
    for i in range(248):
        d = HERE / 'collected-status' / f'worker-{i}-done.json'
        e = HERE / 'collected-status' / f'worker-{i}.exit'
        if d.exists() and e.exists():
            row = json.loads(d.read_text())
            assert row['complete'] and row['manifest'] == MANIFEST and e.read_text().strip() == '0'
            complete += 1
    supervisors_complete = all(nodes[h]['attempts'][a]['supervisor_exit'] == '0'
                               for h in HOSTS for a in (('r2e', 'r2f') if h == '127x04' else ('r2', 'r2f')))
    return dict(utc=time.time(), manifest=MANIFEST, valid_terminal_receipts=sum(counts.values()),
                expected_receipts=4992, successful_collected_partitions=complete, expected_partitions=248,
                per_host_receipts=dict(counts), completed_game_cpu_hours=cpu / 3600,
                complete_only_ready=sum(counts.values()) == 4992 and complete == 248 and supervisors_complete,
                outcomes_inspected=False,
                nodes={h: {a: dict(supervisor_exit=s['supervisor_exit'], pid=s['pid'],
                                  completed_partitions=len(s['partitions']))
                            for a, s in n['attempts'].items()} for h, n in nodes.items()})


def launch_if_ready(host, snap):
    original = snap['attempts']['r2e' if host == '127x04' else 'r2']
    migrated = snap['attempts']['r2f']
    if original['supervisor_exit'] != '0' or migrated['pid'] is not None:
        return
    assert len(original['partitions']) == (48 if host == '127x04' else 100)
    if snap['who'].strip() and host == '127x04':
        return  # C56 reservation alone exceeds the console limit: no new work.
    # Count every Python compute process conservatively, including supervisors.
    processes = [line for line in snap['processes'].splitlines()
                 if len(line.split(None, 5)) == 6 and line.split(None, 5)[4].startswith('python')]
    ceiling = 16 if snap['who'].strip() else 80
    indices = [i for i, h in ASSIGN.items() if h == host and 48 <= i < 148]
    planned = min(len(indices), 4 if snap['who'].strip() else 80)
    if len(processes) + planned + 1 > ceiling:
        return
    command = ['bash', str(ROOT / 'reports/strategy_council_20260928/fleet/fleet_run.sh'),
               f's1-confirm-node-{host}-r2f', str(ROOT / '.venv/bin/python'), '-B',
               str(OPS / 'migration_r2e.py'), 'launch']
    # No retry after an ambiguous launch response. Persist intent beforehand.
    intent = OPS / f'launch-intent-{host}-r2f.json'
    assert not intent.exists(), 'Prior launch intent exists; reconcile PIDs manually'
    write(intent, dict(utc=time.time(), host=host, command=command, indices=indices,
                       current_python_processes=len(processes), ceiling=ceiling))
    p = subprocess.run(SSH + [host, shlex.join(command)], capture_output=True, text=True, timeout=45)
    write(OPS / f'launch-response-{host}-r2f.json', dict(utc=time.time(), exit=p.returncode,
                                                       stdout=p.stdout, stderr=p.stderr))
    assert p.returncode == 0, ('launch failed', host, p.stderr)


def quarantine():
    receipt = OPS / 'quarantine-r2e.json'
    if receipt.exists():
        old = json.loads(receipt.read_text())
        assert old.get('mismatches') == 0
        return old
    p = subprocess.run(SSH + ['127x07', 'hostname'], capture_output=True, text=True, timeout=35)
    if p.returncode:
        out = dict(utc=time.time(), reachable=False, exit=p.returncode, error=p.stderr[-1500:],
                   valid_receipts=0, comparisons=0, mismatches=0, original_process_state='unknown',
                   policy='single bounded completion-barrier probe; no restart, signals or retry')
        write(receipt, out)
        return out
    assert p.stdout.strip().split('.')[0] == '127x07'
    dest = OPS / 'quarantine-127x07-r2e'
    fetch('127x07', dest)
    count = 0
    cpu = 0.
    for path in sorted(dest.glob('*.json')):
        r = validate(path, '127x07', quarantine=True)
        admitted = validate(HERE / 'confirmation' / path.name)
        if r['action_sha256'] != admitted['action_sha256']:
            write(receipt, dict(utc=time.time(), reachable=True, mismatches=1, game=r['job'],
                                comparisons=count, admitted_action=admitted['action_sha256'],
                                quarantined_action=r['action_sha256']))
            raise RuntimeError(f'Hard determinism mismatch: game {r["job"]}')
        count += 1
        cpu += r['cpu_seconds']
    out = dict(utc=time.time(), reachable=True, valid_receipts=count, comparisons=count, mismatches=0,
               quarantined_game_cpu_hours=cpu / 3600, admitted_from_quarantine=0,
               policy='first validated hub receipt retained; quarantine duplicates compared, never overwritten',
               original_process_state='not altered; quarantine read only')
    write(receipt, out)
    return out


def mirror():
    names = ['PREREG.md', 'PREREG-r2b-DEVIATION.md', 'PROGRESS.md', 'RESUME.md', 'RESULTS.md',
             'result.json', 'evaluation-manifest.json', 'execution.json', 'preflight.json']
    files = [str(HERE / name) for name in names if (HERE / name).exists()]
    p = subprocess.run(['rsync', '-a', '-e', shlex.join(SSH), *files, f'127x05:{HERE}/'],
                       capture_output=True, text=True, timeout=45)
    assert p.returncode == 0, ('mirror docs', p.stderr)
    files = [str(p) for p in OPS.iterdir() if p.is_file() and
             (any(tag in p.name for tag in ('r2b','r2e','r2f'))) and p.stat().st_size < 300000]
    p = subprocess.run(['rsync', '-a', '-e', shlex.join(SSH), *files, f'127x05:{OPS}/'],
                       capture_output=True, text=True, timeout=45)
    assert p.returncode == 0, ('mirror audits', p.stderr)


def checkpoint(report, stopped=None):
    write(OPS / 'migration-monitor-r2e.json', report)
    text = '\n## Recovery r2e live checkpoint\n\n' + time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())
    text += '\n\n```json\n' + json.dumps(report, indent=2) + '\n```\n'
    if stopped:
        text += '\nSTOPPED: ' + stopped + '\nNo host retry or automatic resubmission. Inspect operations/collector-error-r2e.json and verified PIDs before resuming.\n'
    resume = HERE / 'RESUME.md'
    prior = resume.read_text().split('\n## Recovery r2e live checkpoint')[0]
    resume.write_text(prior + text)


def main():
    assert socket.gethostname().split('.')[0] == '127x01'
    verified()
    last = {}
    try:
        while True:
            nodes = {}
            for host in HOSTS:
                nodes[host] = snapshot(host)
                write(OPS / f'node-status-{host}-r2e.json', nodes[host])
                admit(host)
                collect_status(host, nodes[host])
            last = technical(nodes)
            checkpoint(last)
            print(json.dumps(last), flush=True)
            mirror()
            if last['complete_only_ready']:
                quarantine()
                verified()
                subprocess.run([sys.executable, '-B', str(OPS / 'migration_r2e.py'), 'analyze'], check=True)
                results = HERE / 'RESULTS.md'
                shutil.copyfile(results, OPS / 'RESULTS-generated-r2e.md')
                results.write_text(results.read_text().replace(
                    'The shared native build retains the documented Electro Spirit and Fisherman defects. This study compares beliefs under that build; it does not certify engine parity or live-client strength.',
                    'The qualified r2 build is 13e908c5cb235a3d81cd585b12caf6c2e5fa624888ed3a3cc0ede14933a5f309, including the Electro Spirit and Inferno Dragon dash-channel fixes. The hub parity qualification is not full Stage 6 admission or live-client certification. See PREREG.md and PREREG-r2b-DEVIATION.md.'))
                with results.open('a') as stream:
                    stream.write('\nOperational host migration and quarantine audit: operations/migration-split-r2b.json, operations/migration-proof-r2b.json, operations/quarantine-r2e.json. Original generated report retained in operations/RESULTS-generated-r2e.md.\n')
                results.write_text(results.read_text().replace('No completed game was excluded.', 'All eligible games are included. The 94 original 04 receipts completed at or after the incident cutoff were preserved and replayed under the coordinator-authorized technical recovery; no outcome-based exclusion occurred.'))
                last['outcomes_inspected'] = True
                last['analysis_complete'] = True
                checkpoint(last)
                mirror()
                return
            for host in HOSTS:
                launch_if_ready(host, nodes[host])
            time.sleep(60)
    except BaseException as error:
        failure = dict(utc=time.time(), error=repr(error), traceback=traceback.format_exc(),
                       last_complete_poll=last, no_automatic_retry=True)
        write(OPS / 'collector-error-r2e.json', failure)
        checkpoint(last, repr(error))
        with (HERE / 'PROGRESS.md').open('a') as stream:
            stream.write('\n' + time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime()) +
                         ': r2e collector stopped without retry: ' + repr(error) + '\n')
        try:
            mirror()
        except Exception:
            traceback.print_exc()
        raise


if __name__ == '__main__':
    main()
