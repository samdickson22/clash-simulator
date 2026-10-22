"""Serial guarded M scaling and next-snapshot training. Never runs on 04 or launches L."""
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import time

HERE = Path(__file__).resolve()
CODE = HERE.parents[4]
OUT = Path('/mpac/sdicks02/jobs/clasher/pretrain-v1/followup-20261022')
OLD = OUT.parent/'bc-sweep'
NEW_STORE = Path('/mpac/sdicks02/datasets/pretrain-v1/snapshot-20261022-b083')


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    assert os.uname().nodename.split('.')[0] == '127x08'
    OUT.mkdir(parents=True, exist_ok=True)
    locks = []
    for p in [OLD/'driver.lock', OUT/'owner.lock']:
        f = p.open('a'); fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB); locks.append(f)
    spec = importlib.util.spec_from_file_location('base_sweep', HERE.with_name('sweep_08.py'))
    b = importlib.util.module_from_spec(spec); spec.loader.exec_module(b)
    b.SW, b.CODE = OUT, str(CODE)
    peaks = {s: json.loads((OLD/f'peaks-{s}.json').read_text()) for s in ['S', 'M']}
    # The model, trainer and selector are byte-identical to the runtime whose complete-workflow peaks were measured.
    original = Path('/mpac/sdicks02/repos/pretrain-v1-code/bot/pretrain_v1')
    for n in ['model.py', 'train_bc.py', 'select_bc.py', 'featurize.py', 'admit_bc.py']:
        assert sha(CODE/'bot/pretrain_v1'/n) == sha(original/n), n
    identity = dict(code=str(CODE), source_hashes={n: sha(CODE/'bot/pretrain_v1'/n)
                    for n in ['model.py', 'train_bc.py', 'select_bc.py', 'featurize.py']}, peaks=peaks)
    (OUT/'owner.json').write_text(json.dumps(dict(pid=os.getpid(), started=time.time(), **identity), indent=1)+'\n')

    def phase(name, command, cap, artifact):
        receipt = OUT/f'completed-{name}.json'
        expected = dict(command=command, cap_gib=cap, **identity)
        if receipt.exists():
            d = json.loads(receipt.read_text())
            assert all(d[k] == v for k, v in expected.items()), 'phase identity changed'
            assert sha(artifact) == d['artifact_sha256'], 'phase artifact changed'
            return
        if artifact.parent.exists() and any(artifact.parent.iterdir()):
            raise SystemExit(f'partial unreceipted phase {name}; inspect, never silently restart training')
        # Publish an exclusive launch intent BEFORE admission/spawn. A killed owner cannot silently launch
        # a second copy, even if its surviving guard has not yet created the run directory or active.json.
        intent = OUT/f'intent-{name}.json'
        with intent.open('x') as f:
            f.write(json.dumps(dict(owner_pid=os.getpid(), created=time.time(), **expected))+'\n')
        b.log(f'phase {name} waiting for existing GPU and host admission')
        p = b.launch(name, command, cap, OUT/f'{name}.log')
        (OUT/'active.json').write_text(json.dumps(dict(name=name, guard_pid=p.pid, command=command))+'\n')
        rc = p.wait(); b.reap()
        if rc or not artifact.is_file():
            (OUT/f'failed-{name}.json').write_text(json.dumps(dict(returncode=rc, command=command))+'\n')
            raise SystemExit(f'{name} stopped ({rc}); inspect log, no automatic retry')
        receipt.write_text(json.dumps(dict(**expected, artifact_sha256=sha(artifact), finished=time.time()), indent=1)+'\n')

    def run(name, size, extra):
        run = OUT/name
        phase(name, b.train_cmd(run, size, extra), 1.5*peaks[size]['train'], run/'summary.json')
        selected = OUT/f'select-{name}'
        phase(f'select-{name}', b.select_cmd([run], selected), 1.5*peaks[size]['select'], selected/'selection.json')

    run('M50', 'M', ['--train-frac', '0.5', '--epochs', '16', '--eval-every', '2', '--warmup-steps', '6102'])
    run('M25', 'M', ['--train-frac', '0.25', '--epochs', '32', '--eval-every', '4', '--warmup-steps', '6102'])
    b.log('v3 M scaling complete; waiting for frozen larger snapshot')
    ready = NEW_STORE/'STORE-READY.json'
    while not ready.exists():
        time.sleep(60)
    d = json.loads(ready.read_text())
    store = NEW_STORE/d['store_name']
    assert sha(store/'MANIFEST.jsonl') == d['manifest_sha256']
    assert d['batches'] == 83 and d['rows'] > 3902495
    b.STORE = str(store)
    run('next-S100', 'S', [])
    run('next-M100', 'M', [])
    (OUT/'complete.json').write_text(json.dumps(dict(finished=time.time(), status='complete'))+'\n')
    b.log('M scaling and next-snapshot training/selection complete')


if __name__ == '__main__':
    main()
