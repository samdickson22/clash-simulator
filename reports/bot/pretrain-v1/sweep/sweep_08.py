#!/usr/bin/env python3
"""127x08 model-size / data-scaling sweep driver (pretrain-v1). Detached; never touches RL or other processes.

GPU protection (Sol R10): EVERY GPU phase of the sweep (smoke training, smoke selection, training, selection) runs
under a per-process allocator cap (PV1_GPU_FRACTION) and is admitted only when
    device total - external usage - sum(caps + context of our running GPU phases) - HEADROOM >= cap + context,
where external usage is the measured memory of every GPU process that is not ours (nvidia-smi per pid), plus
host MemAvailable >= 40 GiB and 1-min load < 85 (each phase also runs under run_guarded.sh: stop at MemAvailable
< 29 GiB or load > 90). Caps come from solo smoke runs of the COMPLETE workflow (500 train steps, DEV evaluation at
batch 1024, gate calibration at 2048, then select_bc at 2048), which must exit cleanly; cap = 1.5 x measured peak.
Smokes start only after the registered BC v3 seeds and their selection are gone and the GPU has no other process.

Runs (seed 2026102001, store f-ce6e509ee43a-b-1005dbb4): L, M (bf16 autocast), S50, S25 (fp32; nested train-donor
subsets; same warm-up steps as S100 and ~one full-data pass between evaluations). select_bc after each run, and on
the registered S seed-2026102001 run alone (S100, like-for-like single seed).
"""
import json, os, subprocess, time
from pathlib import Path

J = Path('/mpac/sdicks02/jobs/clasher/pretrain-v1')
SW = J/'bc-sweep'
CODE = '/mpac/sdicks02/repos/pretrain-v1-code'
PY = '/mpac/sdicks02/repos/clasher-bot-gpu/venv/bin/python'
STORE = '/mpac/sdicks02/datasets/pretrain-v1/f-ce6e509ee43a-b-1005dbb4'
SEED = 2026102001
TOTAL = 47.5          # GiB visible to processes on the A6000
HEADROOM = 4.0        # GiB never committed (co-tenant growth, non-allocator allocations)
CTX = 0.7             # GiB per process outside the allocator cap (CUDA context)
S_ARGS = ['--d', '192', '--layers', '4', '--heads', '6', '--ffn', '576']
SIZE_ARGS = {
    'L': ['--d', '512', '--layers', '8', '--heads', '8', '--ffn', '2048', '--drop', '0.1', '--lr', '1.5e-4',
          '--wd', '0.01', '--amp', 'bf16'],
    'M': ['--d', '320', '--layers', '6', '--heads', '8', '--ffn', '1280', '--drop', '0.1', '--lr', '2e-4',
          '--wd', '0.01', '--amp', 'bf16'],
    'S': S_ARGS,
}
JOBS = [('L', 'L', []), ('M', 'M', []),
        ('S50', 'S', ['--train-frac', '0.5', '--epochs', '16', '--eval-every', '2', '--warmup-steps', '6102']),
        ('S25', 'S', ['--train-frac', '0.25', '--epochs', '32', '--eval-every', '4', '--warmup-steps', '6102'])]
running = {}          # name -> (Popen, cap_gib)


def log(msg):
    with open(SW/'driver.log', 'a') as f:
        f.write(time.strftime('%Y-%m-%dT%H:%M:%S ') + msg + '\n')


def ps_args():
    out = subprocess.run(['ps', '-eo', 'pid=,args='], capture_output=True, text=True).stdout
    return {int(l.split(None, 1)[0]): (l.split(None, 1)[1] if len(l.split(None, 1)) > 1 else '')
            for l in out.splitlines() if l.strip()}


def gpu_apps():
    out = subprocess.run(['nvidia-smi', '--query-compute-apps=pid,used_memory', '--format=csv,noheader,nounits'],
                         capture_output=True, text=True).stdout
    apps = {}
    for l in out.splitlines():
        if l.strip():
            pid, mib = (x.strip() for x in l.split(','))
            apps[int(pid)] = float(mib)/1024
    return apps


def external_gib():
    args = ps_args()
    return sum(g for pid, g in gpu_apps().items() if '/bc-sweep/' not in args.get(pid, ''))


def mem_avail_gib():
    for l in open('/proc/meminfo'):
        if l.startswith('MemAvailable:'):
            return int(l.split()[1])/2**20
    return 0


def reap():
    for name, (p, cap) in list(running.items()):
        if p.poll() is not None:
            del running[name]


def budget():
    reap()
    return TOTAL - external_gib() - sum(cap + CTX for _, cap in running.values()) - HEADROOM


def admit(cap):
    while True:
        b = budget()
        if cap + CTX <= b and mem_avail_gib() >= 40 and os.getloadavg()[0] < 85:
            return b
        time.sleep(60)


def launch(name, cmd, cap, logf):
    b = admit(cap)
    env = dict(os.environ, PYTHONPATH=CODE, GPU='0', OMP_NUM_THREADS='3', PV1_GPU_FRACTION=f'{cap/TOTAL:.4f}')
    p = subprocess.Popen(['bash', f'{CODE}/bot/pretrain_v1/run_guarded.sh', str(logf), '--'] + cmd, cwd=CODE, env=env,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    running[name] = (p, cap)
    log(f'launched {name}: cap {cap:.1f} GiB, budget was {b:.1f} GiB')
    return p


def train_cmd(out, size, extra, smoke=False):
    cmd = [PY, '-B', '-m', 'bot.pretrain_v1.train_bc', '--store', STORE, '--out', str(out), '--seed', str(SEED),
           '--device', 'cuda', '--threads', '3'] + SIZE_ARGS[size] + extra
    if smoke:
        cmd += ['--epochs', '1', '--steps-per-epoch', '500', '--dev-cap', '20000']
    return cmd


def select_cmd(runs, out, smoke=False):
    return ([PY, '-B', '-m', 'bot.pretrain_v1.select_bc', '--store', STORE, '--runs'] + [str(r) for r in runs]
            + ['--out', str(out), '--device', 'cuda'] + (['--smoke-games', '200'] if smoke else []))


def measure(size):
    """Solo smoke of the full workflow -> (train peak, select peak) GiB, or raise."""
    f = SW/f'peaks-{size}.json'
    if f.exists():
        return json.loads(f.read_text())
    out = SW/f'smoke-{size}'
    p = launch(f'smoke-{size}', train_cmd(out, size, [], smoke=True), 0.8*TOTAL - CTX - HEADROOM, SW/f'smoke-{size}.log')
    if p.wait() != 0 or not (out/'summary.json').exists():
        raise SystemExit(f'smoke {size} failed (see smoke-{size}.log)')
    tp = json.loads((out/'summary.json').read_text())['gpu_peak_reserved_gib']
    sel = SW/f'smoke-select-{size}'
    p = launch(f'smoke-select-{size}', select_cmd([out], sel, smoke=True), 0.8*TOTAL - CTX - HEADROOM,
               SW/f'smoke-select-{size}.log')
    if p.wait() != 0 or not (sel/'selection.json').exists():
        raise SystemExit(f'smoke select {size} failed')
    sp = json.loads((sel/'selection.json').read_text())['gpu_peak_reserved_gib']
    peaks = dict(train=tp, select=sp)
    f.write_text(json.dumps(peaks))
    log(f'peaks {size}: train {tp:.2f} GiB, select {sp:.2f} GiB (full workflow, batch 512 / 1024 / 2048)')
    return peaks


def select(name, runs, cap):
    out = SW/f'select-{name}'
    if (out/'selection.json').exists():
        return None
    return launch(f'select-{name}', select_cmd(runs, out), cap, SW/f'select-{name}.log')


def main():
    SW.mkdir(parents=True, exist_ok=True)
    log('driver (R10 accounting) start; waiting for BC v3 seeds, their selection and an idle GPU')
    while True:
        args = ' '.join(ps_args().values())
        busy = 'bot.pretrain_v1.train_bc --store' in args or 'bot.pretrain_v1.select_bc' in args
        if not busy and (J/'bc-v3-select'/'selection.json').exists() and not gpu_apps():
            break
        time.sleep(60)
    log('GPU idle; measuring full-workflow peaks (solo)')
    peaks = {s: measure(s) for s in ('L', 'M', 'S')}
    pending = list(JOBS)
    sel_pending = [('S100', [J/'bc-v3'/'s1'], 'S')]
    procs = {}
    while pending or sel_pending or running:
        reap()
        for item in list(sel_pending):
            name, runs, size = item
            if f'select-{name}' not in running:
                p = select(name, runs, 1.5*peaks[size]['select'])
                if p is not None:
                    procs[f'select-{name}'] = p
                sel_pending.remove(item)
        for item in list(pending):
            name, size, extra = item
            out = SW/name
            if (out/'summary.json').exists():
                pending.remove(item)
                sel_pending.append((name, [out], size))
                continue
            cap = 1.5*peaks[size]['train']
            if cap + CTX <= budget() and mem_avail_gib() >= 40 and os.getloadavg()[0] < 85:
                procs[name] = launch(name, train_cmd(out, size, extra), cap, SW/f'{name}.log')
                pending.remove(item)
                time.sleep(120)
        for name, p in list(procs.items()):
            if p.poll() is not None:
                del procs[name]
                if name.startswith('select-'):
                    ok = (SW/name/'selection.json').exists()
                    log(f'{name} finished: {"ok" if ok else "FAILED"}')
                else:
                    ok = (SW/name/'summary.json').exists()
                    log(f'{name} finished: {"ok" if ok else "FAILED (see log)"}')
                    if ok:
                        size = next(s for n, s, _ in JOBS if n == name)
                        sel_pending.append((name, [SW/name], size))
        time.sleep(60)
    log('sweep training + selection complete')


if __name__ == '__main__':
    main()
