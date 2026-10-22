"""Two serial M BC seeds on the frozen 119,970-source-match snapshot, GPU08 only."""
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import time
import interim_pins as pins

CODE = Path(__file__).resolve().parents[4]
OUT = Path('/mpac/sdicks02/jobs/clasher/pretrain-v1/interim-20261022-b240')
ROOT = Path('/mpac/sdicks02/datasets/pretrain-v1/05/interim-20261022-b240')
PY = '/mpac/sdicks02/repos/clasher-bot-gpu/venv/bin/python'
SEEDS = (2026102001, 2026102002)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    pin_identity = pins.verify(CODE)
    assert os.uname().nodename.split('.')[0] == '127x08'
    OUT.mkdir(parents=True, exist_ok=True)
    locks = []
    for path in (OUT/'owner.lock', OUT.parent/'bc-sweep/driver.lock', OUT.parent/'followup-20261022/owner.lock'):
        f = path.open('a'); fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB); locks.append(f)
    spec = importlib.util.spec_from_file_location('sweep', CODE/'reports/bot/pretrain-v1/sweep/sweep_08.py')
    b = importlib.util.module_from_spec(spec); spec.loader.exec_module(b)
    b.SW = OUT
    ready = json.loads((ROOT/'STORE-READY.json').read_text())
    assert ready['batches'] == 240
    assert ready['input_sha256'] == '2422eb7321982a60b14f5152d3a4338f456294d1cd249b6cbb973de834c765c2'
    store = ROOT/ready['store_name']
    assert sha(store/'MANIFEST.jsonl') == ready['manifest_sha256']
    expected_batches = {json.loads(l)['batch'] for l in (store/'MANIFEST.jsonl').read_text().splitlines()}
    assert {p.name for p in (store/'shards').iterdir() if p.is_dir() and not p.name.startswith('.')} == expected_batches
    for name, digest in ready['files'].items():
        assert sha(ROOT/name) == digest, name
    peaks = json.loads((OUT.parent/'bc-sweep/peaks-M.json').read_text())
    caps = {'train': 1.5*peaks['train'], 'select': 1.5*peaks['select']}
    assert 2*(caps['train'] + b.CTX) > b.TOTAL - b.HEADROOM
    identity = dict(launch_pin=pin_identity, code=str(CODE), source_hashes={str(p.relative_to(CODE)): sha(p)
                    for p in sorted((CODE/'bot/pretrain_v1').rglob('*.py'))}, ready_sha256=sha(ROOT/'STORE-READY.json'),
                    seeds=SEEDS, caps_gib=caps)
    (OUT/'owner.json').write_text(json.dumps(dict(pid=os.getpid(), started=time.time(), **identity), indent=1)+'\n')
    env = dict(os.environ, PYTHONPATH=str(CODE), CUDA_VISIBLE_DEVICES='0', OMP_NUM_THREADS='3',
               PYTHONDONTWRITEBYTECODE='1', PYTHONHASHSEED='0', NUMPY_MADVISE_HUGEPAGE='0',
               PV1_HOST_MIN_AVAILABLE_GIB='29', PV1_HOST_MAX_LOAD='90')

    def phase(name, command, cap, artifact):
        receipt = OUT/f'completed-{name}.json'
        expected = dict(command=command, cap_gib=cap, **identity)
        if receipt.exists():
            old = json.loads(receipt.read_text())
            assert json.dumps({k: old[k] for k in expected}, sort_keys=True) == json.dumps(expected, sort_keys=True)
            assert sha(artifact) == old['artifact_sha256']
            return
        assert not artifact.parent.exists(), f'partial phase {name}; no automatic restart'
        with (OUT/f'intent-{name}.json').open('x') as f:
            json.dump(dict(owner_pid=os.getpid(), created=time.time(), **expected), f, indent=1)
        # Require an empty GPU and no BC worker/legacy driver, even if locks were orphaned.
        while True:
            procs = b.ps_args()
            duplicate = any(('bot.pretrain_v1.train_bc' in args or 'bot.pretrain_v1.select_bc' in args
                            or 'followup_08.py' in args or 'sweep_08.py' in args)
                            for pid, (_, args) in procs.items() if pid != os.getpid())
            if not duplicate and not b.gpu_apps() and b.mem_avail_gib() >= 50 and os.getloadavg()[0] < 80:
                assert cap + b.CTX <= b.TOTAL - b.HEADROOM
                break
            time.sleep(20)
        pins.verify(CODE)
        child_env = dict(env, PV1_GPU_FRACTION=f'{cap/b.TOTAL:.4f}')
        started = time.time()
        with (OUT/f'{name}.log').open('x') as log:
            child = subprocess.Popen(['nice', '-n', '10'] + command, cwd=CODE, env=child_env,
                                     stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        (OUT/'active.json').write_text(json.dumps(dict(name=name, pid=child.pid, started=started, command=command))+'\n')
        rc = child.wait()
        if rc or not artifact.is_file():
            (OUT/f'failed-{name}.json').write_text(json.dumps(dict(returncode=rc, command=command))+'\n')
            raise SystemExit(f'{name} failed {rc}; inspect, no retry')
        receipt.write_text(json.dumps(dict(**expected, artifact_sha256=sha(artifact), finished=time.time(),
                                          wall_s=time.time()-started), indent=1)+'\n')

    runs = []
    for seed in SEEDS:
        run = OUT/f'M-s{seed}'; runs.append(run)
        command = [PY, '-B', '-m', 'bot.pretrain_v1.train_bc', '--store', str(store), '--out', str(run),
                   '--seed', str(seed), '--device', 'cuda', '--threads', '3', '--d', '320', '--layers', '6',
                   '--heads', '8', '--ffn', '1280', '--drop', '0', '--lr', '2e-4', '--wd', '0.01',
                   '--amp', 'bf16', '--bs', '512', '--epochs', '8', '--patience', '2']
        phase(run.name, command, caps['train'], run/'summary.json')
    selected = OUT/'select-M'
    phase('select-M', [PY, '-B', '-m', 'bot.pretrain_v1.select_bc', '--store', str(store), '--runs']
          + [str(p) for p in runs] + ['--out', str(selected), '--device', 'cuda'], caps['select'], selected/'selection.json')
    (OUT/'complete.json').write_text(json.dumps(dict(finished=time.time(), status='complete'))+'\n')


if __name__ == '__main__':
    main()
