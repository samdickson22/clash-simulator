"""Fleet-only synthetic resume, dev-stop and eager-bf16 extension checks."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import torch
from imitation.model.synthetic_store import create
from imitation.model.store import PackedStore
from imitation.model.batching import build_batch
from imitation.model.network import ModelConfig
from imitation.model.train import optimizer_step
from .variants import create_policy
from .guards import write_once


def main():
    p = argparse.ArgumentParser(); p.add_argument('--output', required=True); p.add_argument('--cuda', action='store_true')
    a = p.parse_args(); out = Path(a.output); out.mkdir(parents=True, exist_ok=False)
    start = time.monotonic(); torch.set_num_threads(1)
    for role in ('train', 'dev'):
        create(out/role, role, 16)
    result = {'synthetic_only': True, 'resume': {}, 'dev_signal': None, 'cuda_bf16': {}}
    for variant in ('main', 'noD1', 'gru'):
        flags = ['--variant', variant, '--store', str(out/'train'), '--dev', str(out/'dev'),
                 '--device', 'cpu', '--synthetic-smoke', '--workers', '0', '--batch-size', '8',
                 '--microbatch', '4', '--max-steps', '2', '--checkpoint-every', '1', '--seed', '17']
        run = out/(variant+'-full'); resumed = out/(variant+'-resume')
        command = [sys.executable, '-B', '-m', 'imitation.t5.train', *flags]
        with (out/(variant+'-full.log')).open('w') as log:
            subprocess.run([*command, '--output', str(run)], stdout=log, stderr=subprocess.STDOUT, check=True)
        with (out/(variant+'-resume.log')).open('w') as log:
            subprocess.run([*command, '--output', str(resumed), '--resume', str(run/'step-00000001.pt')],
                           stdout=log, stderr=subprocess.STDOUT, check=True)
        x = torch.load(run/'step-00000002.pt', weights_only=True)
        y = torch.load(resumed/'step-00000002.pt', weights_only=True)
        for section in ('model', 'ema'):
            assert all(torch.equal(x[section][k], y[section][k]) for k in x[section]), (variant, section)
        assert x['state'] == y['state']
        result['resume'][variant] = 'model/EMA/state bit-exact at step2 from step1'
    # Trigger a real SIGTERM at entry to dev. The pre-dev checkpoint must exist;
    # the injected loader guard must exit before evaluating any dev batch.
    script = '''import os,signal
from imitation.model import runner
original=runner.dev_joint_nll
def stop(*a,**k):
 os.kill(os.getpid(),signal.SIGTERM)
 return original(*a,**k)
runner.dev_joint_nll=stop
from imitation.t5.train import main
main()
'''
    stopped = out/'signal-dev'
    with (out/'signal-dev.log').open('w') as log:
        subprocess.run([sys.executable, '-B', '-c', script, '--variant', 'main', '--store', str(out/'train'),
                        '--dev', str(out/'dev'), '--device', 'cpu', '--synthetic-smoke', '--workers', '0',
                        '--batch-size', '8', '--microbatch', '4', '--max-steps', '1', '--output', str(stopped)],
                       stdout=log, stderr=subprocess.STDOUT, check=True)
    assert (stopped/'step-00000001.pt').exists()
    segment = json.loads((stopped/'segments.jsonl').read_text().splitlines()[-1])
    assert segment['status'] == 'checkpointed_during_dev'
    assert not any(json.loads(line)['event']=='dev' for line in (stopped/'train.jsonl').read_text().splitlines())
    result['dev_signal'] = 'SIGTERM exits with pre-dev resumable checkpoint and no dev evaluation'
    if a.cuda:
        device = torch.device('cuda'); store = PackedStore(out/'train', 'train')
        for variant in ('main', 'noD1', 'gru'):
            assets = store.assets
            model = create_policy(variant, ModelConfig(), *[torch.tensor(assets[k]) for k in ('descriptors','tiles','costs')]).to(device)
            if variant == 'gru': model.bind_store(store)
            b, y = build_batch(store, [0, 3, 7]); b['row_index'] = y['index']
            optimizer = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=.05)
            loss = optimizer_step(model, optimizer, b, y, 3, device)
            result['cuda_bf16'][variant] = loss
    result['passed'] = True; result['wall_seconds'] = time.monotonic()-start
    write_once(out/'PASS.json', result)
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
