"""Exploration adapter around frozen T11 sampling and qualified T4 training.

No edits to imported trainers. An extra RNG-neutral full-dev measurement at
the first batch >=25% enforces the prospectively frozen capacity kill rule.
"""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import inspect
import json
import math
import os
from pathlib import Path
import random
import sys
import time

import numpy as np
import torch


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1048576), b''):
            h.update(b)
    return h.hexdigest()


def write(path, value):
    path = Path(path)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    temp.replace(path)


class ScanExit(Exception):
    pass


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--config', required=True)
    p.add_argument('--freeze', required=True)
    p.add_argument('--source', required=True)
    p.add_argument('--store', required=True)
    p.add_argument('--inputs', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--resume')
    p.add_argument('--resume-sha256')
    a = p.parse_args()
    freeze = json.loads(Path(a.freeze).read_text())
    c = json.loads(Path(a.config).read_text())
    assert sha(a.config) == freeze['configs'][str(c['width'])]
    assert sha(__file__) == freeze['adapter_sha256']
    assert os.getpriority(os.PRIO_PROCESS, 0) >= 10
    root = Path(a.source).resolve()
    sys.path.insert(0, str(root))
    from imitation.t11.train import frozen
    manifest, pins = frozen(root, root/'imitation/gate-a-v2/executable-manifest.json')
    assert sha(root/'imitation/gate-a-v2/executable-manifest.json') == freeze['T11_manifest_sha256']
    from imitation.model import train as q, runner, batching
    from imitation.model.network import ModelConfig
    from imitation.model.store import PackedStore
    from imitation.t11 import sampling
    from imitation.t5.resources import install
    from imitation.t5.guards import role_guard
    inputs, store, output = Path(a.inputs), Path(a.store), Path(a.output)
    assert sha(inputs/'assets.npz') == manifest['assets_sha256']
    assert sha(inputs/'T11-STORE-PASS.json') == manifest['store_receipt_sha256']
    verified = json.loads((Path(a.freeze).parent/'store-verified.json').read_text())
    assert verified['passed'] and verified['store_manifest_sha256'] == manifest['store_manifest_sha256']

    class ScanStore(PackedStore):
        def __init__(self, directory, role, assets=None):
            role_guard(directory, role, manifest)
            super().__init__(directory, role, assets)
            self.hashes.update(pins)

    install()
    q.PackedStore = ScanStore
    q.ModelConfig = lambda **kw: ModelConfig(**{**asdict(ModelConfig(**kw)), **c['model']})
    q.epoch_indices = sampling.epoch_indices
    original_loader = batching.batch_loader
    sampling.qualified_loader = lambda s, *args, **kw: original_loader(s, *args, **{**kw, 'workers': c['loader_workers']})
    observed = {'rows': 0, 'step': 0}
    if a.resume:
        expected_resume = a.resume_sha256 or (freeze['control_resume_sha256'] if c['width']==192 else None)
        assert expected_resume and sha(a.resume) == expected_resume
        if c['width'] != 192:
            assert Path(a.resume).resolve().parent == output.resolve(), 'resume only own arm checkpoint'
        resumed = torch.load(a.resume, map_location='cpu', weights_only=True)
        observed.update(rows=resumed['state']['rows'], step=resumed['state']['step'])
        del resumed
    target = math.ceil(freeze['scheduled_rows'] / 4)
    captured = {}
    original_save = q.save_checkpoint
    original_step = q.optimizer_step

    def step(*args, **kwargs):
        frame = inspect.currentframe().f_back
        try:
            captured.update({name: frame.f_locals[name] for name in
                             ('model', 'ema', 'optimizer', 'scheduler', 'config', 'state', 'hashes', 'args')})
        finally:
            del frame
        if not done and captured['state']['rows'] >= target:
            assert captured['state']['rows'] == freeze['first_batch_matched_rows']
            measure_quarter()
        return original_step(*args, **kwargs)

    q.optimizer_step = step

    def save(path, model, ema, optimizer, scheduler, config, state, hashes, args):
        captured.update(model=model, ema=ema, optimizer=optimizer, scheduler=scheduler,
                        config=config, state=state, hashes=hashes, args=args)
        return original_save(path, model, ema, optimizer, scheduler, config, state, hashes, args)

    q.save_checkpoint = save
    done = (output/'kill-decision.json').exists()
    if done:
        assert not json.loads((output/'kill-decision.json').read_text())['killed'], 'scientifically killed arms must not resume'
    if c['width']==192 and (output/'quarter.json').exists():
        raise ValueError('control quarter already complete; do not repeat')

    def measure_quarter():
        nonlocal done
        assert captured and captured['state']['rows'] == observed['rows']
        state = captured['state']
        if (output/'quarter.json').exists():
            quarter=json.loads((output/'quarter.json').read_text())
            assert quarter['rows']==state['rows'] and quarter['config_sha256']==sha(a.config)
            nll=quarter['ema_joint_nll']
        else:
            save(output/f"quarter-step-{state['step']:08d}.pt", **captured)
            rng = (torch.get_rng_state(), torch.cuda.get_rng_state_all(),
                   np.random.get_state(), random.getstate())
            was_training = captured['model'].training
            dev = ScanStore(store/'dev', 'dev', inputs/'assets.npz')
            before = time.monotonic()
            try:
                nll = runner.dev_joint_nll(captured['model'], captured['ema'], dev,
                                          torch.device('cuda'), 1024, workers=1)
            finally:
                captured['model'].train(was_training)
                torch.set_rng_state(rng[0]); torch.cuda.set_rng_state_all(rng[1])
                np.random.set_state(rng[2]); random.setstate(rng[3])
            quarter = dict(width=c['width'], rows=state['rows'], step=state['step'],
                           scheduled_rows=freeze['scheduled_rows'], ema_joint_nll=nll,
                           dev_rows=len(dev), dev_seconds=time.monotonic()-before,
                           at=datetime.now(timezone.utc).isoformat(), config_sha256=sha(a.config))
            write(output/'quarter.json', quarter)
        done = True
        if c['width'] == 192:
            write(output/'scan-exit.json', dict(status='control_replay_complete', **quarter))
            raise ScanExit()
        control_path = output.parent/'control-quarter.json'
        while not control_path.exists():
            if (output.parent.parent/'STOP').exists():
                raise ScanExit('preempted_waiting_control')
            time.sleep(5)
        control = json.loads(control_path.read_text())
        assert control['width'] == 192 and control['rows'] == quarter['rows']
        gain = control['ema_joint_nll'] - nll
        killed = gain < 0.005
        write(output/'kill-decision.json', dict(killed=killed, gain=gain,
              threshold=0.005, control=control, arm=quarter))
        if killed:
            write(output/'scan-exit.json', dict(status='killed_dev_gain', **quarter, gain=gain))
            raise ScanExit()

    def loader(s, *args, **kwargs):
        for b, y in sampling.train_loader(s, *args, **kwargs):
            yield b, y
            # qualified.main has updated optimizer, EMA, cursor and log here.
            observed['rows'] += len(y['action'])
            observed['step'] += 1
            if not done and observed['rows'] >= target:
                measure_quarter()

    q.batch_loader = loader
    argv = ['scan', '--store', str(store/'train'), '--dev', str(store/'dev'),
            '--assets', str(inputs/'assets.npz'), '--qualification', str(inputs/'T11-STORE-PASS.json'),
            '--output', str(output), '--device', 'cuda']
    for key, value in c['trainer'].items():
        argv += ['--'+key.replace('_', '-'), str(value)]
    if a.resume:
        argv += ['--resume', a.resume]
    sys.argv = argv
    output.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc).isoformat(); before = time.monotonic()
    status = 'failed'
    try:
        q.main()
        status = 'complete'
    except ScanExit as e:
        status = str(e) or ('control_replay_complete' if c['width']==192 else 'killed_dev_gain')
    finally:
        with (output/'scan-segments.jsonl').open('a') as f:
            f.write(json.dumps(dict(started_at=started, ended_at=datetime.now(timezone.utc).isoformat(),
                    wall_seconds=time.monotonic()-before, status=status, **observed))+'\n')


if __name__ == '__main__':
    main()
