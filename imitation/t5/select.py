"""Selection receipts use uncalibrated EMA dev scores only."""
import argparse
import json
from pathlib import Path
from .guards import sha, canonical_hash, write_once

EXPECTED = {'main-2026100801': ('main', 2026100801), 'main-2026100802': ('main', 2026100802),
            'main-2026100803': ('main', 2026100803), 'noD1-2026100801': ('noD1', 2026100801),
            'gru-2026100801': ('gru', 2026100801)}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('mode', choices=('run', 'combine', 'release'))
    p.add_argument('--input', nargs='+', required=True); p.add_argument('--output', required=True)
    p.add_argument('--run'); p.add_argument('--manifest'); p.add_argument('--selection')
    a = p.parse_args()
    if a.mode == 'run':
        import torch
        root = Path(a.input[0]); complete = json.loads((root/'complete.json').read_text())
        if complete['stopped_by_signal']:
            raise ValueError('run paused, not finished')
        events = [json.loads(line) for line in (root/'train.jsonl').read_text().splitlines()]
        choices = [e for e in events if e['event']=='dev']
        winner = min(choices, key=lambda e: (e['ema_joint_nll'], e['step']))
        variant, seed = EXPECTED[a.run]
        checkpoint = root/f"best-dev-step-{winner['step']:08d}.pt"
        ckpt = torch.load(checkpoint, map_location='cpu', weights_only=True)
        if ckpt['hashes']['T5_variant'] != variant or ckpt['args']['seed'] != seed:
            raise ValueError('run identity mismatch')
        if ckpt['hashes']['T5_manifest'] != sha(a.manifest) or ckpt['state']['best_dev'] != winner['ema_joint_nll']:
            raise ValueError('checkpoint/dev selection mismatch')
        result = {'run': a.run, 'variant': variant, 'seed': seed, 'step': winner['step'],
                  'dev_joint_nll': winner['ema_joint_nll'], 'checkpoint': str(checkpoint),
                  'checkpoint_sha256': sha(checkpoint), 'manifest_sha256': sha(a.manifest),
                  'train_log_sha256': sha(root/'train.jsonl'), 'complete_sha256': sha(root/'complete.json')}
    elif a.mode == 'combine':
        items = [json.loads(Path(f).read_text()) for f in a.input]
        runs = {r['run']: r for r in items}
        if len(items)!=5 or set(runs)!=set(EXPECTED) or any(r['manifest_sha256']!=sha(a.manifest) for r in items):
            raise ValueError('need exactly five registered selections with identical freeze')
        primary = min((r for r in items if r['variant']=='main'), key=lambda r:(r['dev_joint_nll'], r['step'], r['seed']))
        result = {'manifest_sha256': sha(a.manifest), 'primary': primary['run'], 'runs': runs,
                  'selection_metric': 'lowest uncalibrated EMA dev joint NLL; ties earliest step then lower seed'}
    else:
        selection = json.loads(Path(a.selection).read_text())
        items = [json.loads(Path(f).read_text()) for f in a.input]
        if len(items)!=5 or {r['run'] for r in items}!=set(EXPECTED):
            raise ValueError('need exactly five dev calibrations')
        runs = {}
        for path, item in zip(a.input, items):
            run = item['run']
            if (item['role']!='dev' or item['selection_sha256']!=sha(a.selection)
                    or item['checkpoint_sha256']!=selection['runs'][run]['checkpoint_sha256']):
                raise ValueError('calibration selection provenance mismatch')
            runs[run] = {'checkpoint_sha256': item['checkpoint_sha256'], 'calibration': item,
                         'temperature_file_sha256': sha(path), 'temperature_content_sha256': canonical_hash(item)}
        result = {'selection_sha256': sha(a.selection), 'primary': selection['primary'], 'runs': runs}
    write_once(a.output, result)


if __name__ == '__main__':
    main()
