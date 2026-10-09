"""Read-only T11 baseline and bounded supervision of our own experiment only."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import time

TRAIN = Path('/mpac/sdicks02/repos/clasher-t11-home-v1/runs/main-2026100822-hostloss-20261008-v1/train.jsonl')
T11_PID = 455568


def last_step(path=TRAIN):
    with path.open('rb') as f:
        f.seek(0, 2); size = f.tell(); f.seek(max(0, size-131072))
        lines = f.read().splitlines()
    for line in reversed(lines):
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if row.get('event') == 'step':
            return {k: row[k] for k in ('step', 'rows', 'epoch', 'rows_per_second_including_loader')}
    raise ValueError('No T11 step record')


def sample():
    gpu = subprocess.check_output(['nvidia-smi', '--query-gpu=memory.free,utilization.gpu',
                                  '--format=csv,noheader,nounits'], text=True).strip()
    memory = {row.split(':')[0]: int(row.split()[1]) for row in Path('/proc/meminfo').read_text().splitlines()}
    return dict(at=datetime.now(timezone.utc).isoformat(), monotonic=time.monotonic(),
        t11=last_step(), gpu=[list(map(int, row.split(','))) for row in gpu.splitlines()],
        mem_available_kib=memory['MemAvailable'], t11_alive=Path(f'/proc/{T11_PID}').exists())


def write_new(path, value):
    with path.open('x') as f:
        json.dump(value, f, indent=2, allow_nan=False); f.write('\n')


def baseline(seconds, output):
    if socket.gethostname().split('.')[0] != '127x01' or seconds < 300:
        raise ValueError('Five-minute01 baseline required')
    first = sample(); samples = [first]
    for _ in range(7):
        time.sleep(.5); samples.append(sample())
    deadline = first['monotonic']+seconds
    while time.monotonic() < deadline:
        time.sleep(min(10, max(0., deadline-time.monotonic())))
    last = sample(); samples.append(last)
    elapsed = last['monotonic']-first['monotonic']
    value = dict(schema='clasher.v4.lockstep-t11-baseline.v1', seconds=elapsed,
        rows_per_second=(last['t11']['rows']-first['t11']['rows'])/elapsed,
        mean_gpu_percent=sum(s['gpu'][0][1] for s in samples[:8])/8, samples=samples,
        t11_untouched=True, gpu_work_launched=False)
    write_new(output, value); print(json.dumps(value), flush=True)


def supervise(a):
    if socket.gethostname().split('.')[0] != '127x01':
        raise ValueError('01 development only;02 GPU excluded')
    proof = json.loads(a.baseline.read_text())
    if proof['schema'] != 'clasher.v4.lockstep-t11-baseline.v1' or proof['seconds'] < 300:
        raise ValueError('Actual five-minute baseline required')
    if not a.command:
        raise ValueError('Experiment command required')
    before = sample()
    if before['mem_available_kib'] < 24*1024**2 or not before['t11_alive']:
        raise ValueError('01 CPU/memory/T11 preflight refused')
    if before['gpu'][0][0] < 8*1024:
        raise ValueError('GPU reserve')
    env = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1',
               PYTHONDONTWRITEBYTECODE='1', CLASHER_LOCKSTEP_GPU_AUTHORIZED='127x01',
               CLASHER_LOCKSTEP_GPU_LIMIT_GIB='8')
    samples = [before]; reason = None; started = time.monotonic()
    with a.log.open('x') as log:
        child = subprocess.Popen(['nice', '-n', '10', *a.command], env=env, stdout=log, stderr=subprocess.STDOUT,
                                 start_new_session=True)
        try:
            while child.poll() is None:
                time.sleep(5); current = sample(); samples.append(current)
                recent = next((s for s in reversed(samples[:-1]) if current['monotonic']-s['monotonic'] >= 10), before)
                elapsed = current['monotonic']-recent['monotonic']
                fps = (current['t11']['rows']-recent['t11']['rows'])/elapsed
                if current['mem_available_kib'] < 24*1024**2 or not current['t11_alive']:
                    reason = 'memory_or_T11_guard'
                if elapsed >= 10 and fps < .95*proof['rows_per_second']:
                    reason = 'T11_rows_per_second_dropped_over5percent'
                if time.monotonic()-started >= a.max_seconds:
                    reason = 'bounded_probe_deadline'
                # Query only our process's GPU memory, never cancel another PID.
                apps = subprocess.check_output(['nvidia-smi', '--query-compute-apps=pid,used_memory',
                                                '--format=csv,noheader,nounits'], text=True)
                for line in apps.splitlines():
                    pid, memory = map(int, line.split(','))
                    if pid == child.pid and memory > 8192:
                        reason = 'our_GPU_memory_exceeded8GiB'
                if reason:
                    os.killpg(child.pid, signal.SIGTERM); break
            try:
                code = child.wait(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL); code = child.wait()
        finally:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGTERM); child.wait(timeout=15)
    after = sample(); samples.append(after)
    elapsed = after['monotonic']-before['monotonic']
    rps = (after['t11']['rows']-before['t11']['rows'])/elapsed
    if reason is None and rps < .95*proof['rows_per_second']:
        reason = 'post_probe_T11_rows_per_second_dropped_over5percent'
    value = dict(schema='clasher.v4.lockstep-resource-supervision.v1', code=code, reason=reason,
        our_pid=child.pid, seconds=elapsed, baseline_rows_per_second=proof['rows_per_second'],
        concurrent_t11_rows_per_second=rps, ratio=rps/proof['rows_per_second'], samples=samples,
        stopped_only_our_process_group=True, t11_untouched=True)
    write_new(a.output, value); print(json.dumps(value), flush=True)
    if code or reason or rps < .95*proof['rows_per_second']:
        raise SystemExit(1)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--baseline', type=Path); p.add_argument('--seconds', type=int, default=300)
    p.add_argument('--max-seconds', type=int, default=300); p.add_argument('--log', type=Path)
    p.add_argument('command', nargs=argparse.REMAINDER)
    a = p.parse_args()
    if a.command[:1] == ['--']:
        a.command = a.command[1:]
    if a.baseline:
        supervise(a)
    else:
        baseline(a.seconds, a.output)
