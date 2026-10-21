#!/usr/bin/env python3
"""127x08 model-size / data-scaling sweep driver (pretrain-v1). Detached; never touches RL processes.

Waits for the registered BC v3 seeds and their anchor selection to finish, measures each configuration's GPU peak
with a short solo smoke, then launches the sweep runs (seed 2026102001, store f-ce6e509ee43a-b-1005dbb4) whenever
the measured peak fits next to the running ones, host MemAvailable >= 40 GiB and load < 85 (each job also runs under
run_guarded.sh: stop at MemAvailable < 29 GiB or load > 90). After each run: select_bc on it (gate calibration +
full-DEV admission). Also selects S seed 2026102001 alone (S at 100% data, like-for-like single seed).
"""
import json, os, re, subprocess, time
from pathlib import Path

J = Path('/mpac/sdicks02/jobs/clasher/pretrain-v1')
SW = J/'bc-sweep'
CODE = '/mpac/sdicks02/repos/pretrain-v1-code'
PY = '/mpac/sdicks02/repos/clasher-bot-gpu/venv/bin/python'
STORE = '/mpac/sdicks02/datasets/pretrain-v1/f-ce6e509ee43a-b-1005dbb4'
SEED = 2026102001
TOTAL_GIB = 47.5
S_ARGS = ['--d', '192', '--layers', '4', '--heads', '6', '--ffn', '576']
JOBS = {
    'L': dict(args=['--d', '512', '--layers', '8', '--heads', '8', '--ffn', '2048', '--drop', '0.1', '--lr', '1.5e-4',
                    '--wd', '0.01', '--amp', 'bf16'], smoke='L'),
    'M': dict(args=['--d', '320', '--layers', '6', '--heads', '8', '--ffn', '1280', '--drop', '0.1', '--lr', '2e-4',
                    '--wd', '0.01', '--amp', 'bf16'], smoke='M'),
    'S50': dict(args=S_ARGS + ['--train-frac', '0.5', '--epochs', '16', '--eval-every', '2'], smoke='S'),
    'S25': dict(args=S_ARGS + ['--train-frac', '0.25', '--epochs', '32', '--eval-every', '4'], smoke='S'),
}
SMOKE = {'L': JOBS['L']['args'], 'M': JOBS['M']['args'], 'S': S_ARGS}


def log(msg):
    with open(SW/'driver.log', 'a') as f:
        f.write(time.strftime('%Y-%m-%dT%H:%M:%S ') + msg + '\n')


def running(pattern):
    out = subprocess.run(['ps', '-eo', 'pid,args'], capture_output=True, text=True).stdout
    return [l for l in out.splitlines() if pattern in l and 'run_guarded' not in l and 'sweep_08' not in l]


def mem_avail_gib():
    for l in open('/proc/meminfo'):
        if l.startswith('MemAvailable:'):
            return int(l.split()[1])/2**20
    return 0


def gpu_used_gib():
    out = subprocess.run(['nvidia-smi', '--query-gpu=memory.used', '--format=csv,noheader,nounits'],
                         capture_output=True, text=True).stdout
    return float(out.split()[0])/1024


def train_cmd(out, extra, steps=None, epochs=None):
    cmd = [PY, '-B', '-m', 'bot.pretrain_v1.train_bc', '--store', STORE, '--out', str(out), '--seed', str(SEED),
           '--device', 'cuda', '--threads', '3'] + extra
    if steps:
        cmd += ['--epochs', '1', '--steps-per-epoch', str(steps), '--dev-cap', '2000']
    return cmd


def env(frac=None):
    e = dict(os.environ, PYTHONPATH=CODE, GPU='0', OMP_NUM_THREADS='3')
    if frac:
        e['PV1_GPU_FRACTION'] = f'{frac:.3f}'
    return e


def smoke(name):
    out = SW/f'smoke-{name}'
    logf = SW/f'smoke-{name}.log'
    subprocess.run(['bash', f'{CODE}/bot/pretrain_v1/run_guarded.sh', str(logf), '--'] + train_cmd(out, SMOKE[name], steps=500),
                   cwd=CODE, env=env())
    peaks = [float(m) for m in re.findall(r'"gpu_reserved_gib": ([0-9.]+)', logf.read_text())]
    return max(peaks) if peaks else None


def select(name, runs):
    out = SW/f'select-{name}'
    if (out/'selection.json').exists():
        return
    logf = SW/f'select-{name}.log'
    subprocess.run(['bash', f'{CODE}/bot/pretrain_v1/run_guarded.sh', str(logf), '--', PY, '-B', '-m',
                    'bot.pretrain_v1.select_bc', '--store', STORE, '--runs'] + [str(r) for r in runs] +
                   ['--out', str(out), '--device', 'cuda'], cwd=CODE, env=env())
    log(f'select {name}: {"ok" if (out/"selection.json").exists() else "FAILED"}')


def main():
    SW.mkdir(parents=True, exist_ok=True)
    log('driver start; waiting for BC v3 seeds and the registered selection')
    while running('bot.pretrain_v1.train_bc --store') or running('bot.pretrain_v1.select_bc') \
            or not (J/'bc-v3-select'/'selection.json').exists():
        time.sleep(60)
    log('GPU free of BC v3; smoke-measuring peaks')
    peaks = {}
    for k in ('L', 'M', 'S'):
        if (SW/f'peak-{k}').exists():
            peaks[k] = float((SW/f'peak-{k}').read_text())
            continue
        p = smoke(k)
        peaks[k] = p
        (SW/f'peak-{k}').write_text(str(p))
        log(f'peak {k}: {p} GiB reserved at batch 512')
    select('S100', [J/'bc-v3'/'s1'])                    # S at 100% data, seed 2026102001 alone
    started, done, needs = {}, set(), {}
    while len(done) < len(JOBS):
        for name, spec in JOBS.items():
            if name in started:
                continue
            need = 1.3*peaks[spec['smoke']] if peaks[spec['smoke']] else 16
            reserved = sum(needs[n] for n, pp in started.items() if pp is not None and n not in done)
            budget = TOTAL_GIB - max(gpu_used_gib(), reserved) - 2
            if need <= budget and mem_avail_gib() >= 40 and os.getloadavg()[0] < 85:
                out = SW/name
                if out.exists() and (out/'summary.json').exists():
                    started[name] = None
                    continue
                frac = min(0.95, need/TOTAL_GIB)
                p = subprocess.Popen(['bash', f'{CODE}/bot/pretrain_v1/run_guarded.sh', str(SW/f'{name}.log'), '--']
                                     + train_cmd(out, spec['args']), cwd=CODE, env=env(frac),
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
                started[name] = p
                needs[name] = need
                log(f'launched {name} (gpu fraction {frac:.3f}, need {need:.1f} GiB, budget {budget:.1f})')
                time.sleep(120)                          # let it allocate before the next admission decision
        for name, p in list(started.items()):
            if name in done:
                continue
            if p is None or p.poll() is not None:
                done.add(name)
                ok = (SW/name/'summary.json').exists()
                log(f'{name} finished: {"ok" if ok else "FAILED (see log)"}')
                if ok:
                    select(name, [SW/name])
        time.sleep(60)
    log('sweep training + selection complete')


if __name__ == '__main__':
    main()
