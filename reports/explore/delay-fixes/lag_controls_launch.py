"""Matched-cadence zero-lag controls; launch only after the original run drains."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import shlex
import subprocess
import threading
import time

HERE = Path(__file__).resolve().parent
LEASE = '/mpac/sdicks02/repos/clasher-lease'
HOME_ROOT = '/mpac/sdicks02/repos/clasher'
HOSTS = ['127x09', '127x14', '127x13', '127x15', '127x08']
queue = list(range(0, 1250, 25))
lock = threading.Lock()
manifest = dict(paired_seed_target=1250, shard_pairs=25, results=[], failed=[],
                held_unknown=[], unstarted_offsets=queue.copy(),
                reason='Matched-cadence controls added after code audit, before outcome inspection',
                source_arms=['S0', 'S27'], result_arms=['R0', 'R27'], opponent_delay=0,
                opponent_interval=10, original_manifest='launch-throughput-v5.json')


def save():
    manifest['unstarted_offsets'] = queue.copy()
    path = HERE / 'launch-lag-controls.json'
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(manifest, indent=2) + '\n')
    temporary.replace(path)


def ssh(host, arguments, **kwargs):
    return subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=5',
                           '-o', 'ServerAliveInterval=10', '-o', 'ServerAliveCountMax=2',
                           host, shlex.join(arguments)], **kwargs)


def collect(host, offset, label):
    if host == '127x08':
        return
    out = f'{LEASE}/delay-fixes-runtime/reports/explore/delay-fixes/lag-only/shards/p{offset:04d}'
    ssh(host, ['rsync', '-az', out + '/',
               f'127x08:{HOME_ROOT}/reports/explore/delay-fixes/lag-only/shards/p{offset:04d}/'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(['rsync', '-az', '-e', 'ssh -o BatchMode=yes -o ConnectTimeout=5',
                    f'{host}:{LEASE}/jobs/{label}.exit.json', str(HERE / 'receipts') + '/'],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def lane(host):
    while datetime.now(timezone.utc) < datetime(2026, 10, 9, 4, 15, tzinfo=timezone.utc):
        workers = json.loads((HERE / 'resource-policy.json').read_text()).get(host, 0)
        with lock:
            if not queue:
                return
        if not workers:
            time.sleep(10)
            continue
        if host != '127x08':
            probe = ssh(host, ['nice', '-n', '10', LEASE + '/repo/.venv/bin/python',
                              LEASE + '/delay-fixes-runtime/reports/explore/delay-fixes/nice_probe.py'],
                        capture_output=True, text=True)
            with (HERE / 'receipts' / f'nice-check-{host}.jsonl').open('a') as receipt:
                receipt.write(probe.stdout or json.dumps(dict(host=host, probe_exit=probe.returncode)) + '\n')
            if probe.returncode:
                time.sleep(20)
                continue  # Check again; do not attempt admission while a process is below nice 10.
        with lock:
            if not queue:
                return
            offset = queue.pop(0)
            save()
        root = HOME_ROOT if host == '127x08' else LEASE + '/delay-fixes-runtime'
        label = f'cpu-delay-fixes-lag0-p{offset:04d}-{host}-r1'
        out = f'{root}/reports/explore/delay-fixes/lag-only/shards/p{offset:04d}'
        command = ['env', f'CLASHER_ROOT={root}', f'PYTHONPATH={root}:{root}/src:{root}/engine-rs',
                   'RAYON_NUM_THREADS=1',
                   f'CLASHER_THROUGHPUT_CONFIG={root}/reports/explore/delay-fixes/guard-config.json']
        if host == '127x08':
            command += [f'CLASHER_DELAY_NATIVE_DIR={root}/reports/explore/delay-fixes/native']
        python = (HOME_ROOT if host == '127x08' else LEASE + '/repo') + '/.venv/bin/python'
        command += [python, '-m', 'clasher.analysis.loss_review.delay_simulate', '--out', out,
                    '--pairs', '25', '--pair-offset', str(offset), '--workers', str(workers),
                    '--arms', 'S0', 'S27', '--opponent-delay', '0', '--opponent-interval', '10',
                    '--checkpoint', f'{root}/reports/explore/delay-fixes/inputs/main02.pt',
                    '--exclusions', f'{root}/reports/explore/loss-review/seeds.json',
                    '--gpu-guard', '--resume']
        arguments = (['nice', '-n', '10', 'bash', HOME_ROOT +
                      '/reports/strategy_council_20260928/fleet/fleet_run.sh', '--worker', label]
                     if host == '127x08' else
                     ['bash', LEASE + '/run_v2.sh', '--foreground', '--max-processes', str(workers + 4),
                      '--expected-pss-gb', '12', label, '--']) + command
        started = time.time()
        with (HERE / 'receipts' / f'{label}.log').open('x') as log:
            run = ssh(host, arguments, stdout=log, stderr=subprocess.STDOUT)
        collect(host, offset, label)
        row = dict(host=host, offset=offset, label=label, workers=workers, started=started,
                   finished=time.time(), exit_code=run.returncode, command=arguments)
        with lock:
            manifest['results' if run.returncode == 0 else 'failed'].append(row)
            if run.returncode == 255:
                manifest['held_unknown'].append(row)
            elif run.returncode:
                queue.insert(0, offset)
            save()
        print(json.dumps(row), flush=True)
        if run.returncode:
            return  # Accept a refusal; never retry an unverified remote job.


save()
while Path('/proc/916210/cmdline').exists():
    try:
        command = Path('/proc/916210/cmdline').read_bytes()
    except FileNotFoundError:
        break
    if b'throughput_launch.py' not in command:
        break
    time.sleep(10)
original = json.loads((HERE / 'launch-throughput-v5.json').read_text())
if original['unstarted_offsets'] or original['held_unknown']:
    raise RuntimeError('Original paired run has not completed safely; do not start controls')
with ThreadPoolExecutor(max_workers=5) as pool:
    list(pool.map(lane, HOSTS))
save()
