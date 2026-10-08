"""Dev calibration and once-only held-out sufficient-statistic generation.

Each role has a fixed claim beside its selected training checkpoint. A crashed
attempt can resume only with an explicit recorded technical reason and reuses
all committed batch files. Analysis never imports this entry point.
"""
import argparse
from contextlib import nullcontext
from datetime import datetime, timezone
import json
from pathlib import Path
import time
import os
import resource
import numpy as np
import torch
from imitation.model.network import ModelConfig
from imitation.model.store import PackedStore
from imitation.model import runner
from imitation.model.evaluate import metric_rows, frequency_output, fit_temperature
from .guards import frozen, role_guard, sha, write_once
from .train import indexed_loader
from .variants import create_policy
from .baseline import frequency_rows


class HeldoutStore(PackedStore):
    def __init__(self, directory, role, assets, manifest):
        # Separate T5 authorization; T4's train/dev constructor is not relaxed.
        role_guard(directory, role, manifest, heldout=True)
        self.root = Path(directory).resolve()
        self.manifest_path = self.root/'manifest.json'
        self.manifest = json.loads(self.manifest_path.read_text())
        if self.manifest['role'] != role or 'perspectives' not in self.manifest:
            raise ValueError('heldout requires exact released T3 schema/role')
        self.t3 = True
        self._load_t3(role, assets)


def load_model(checkpoint, device, pins, variant):
    ckpt = torch.load(checkpoint, map_location='cpu', weights_only=True)
    for key, value in {**pins, 'T5_variant': variant}.items():
        if ckpt['hashes'].get(key) != value:
            raise ValueError('checkpoint provenance mismatch: '+key)
    state = ckpt['ema']
    model = create_policy(variant, ModelConfig(**ckpt['config']), state['descriptors'],
                          state['tile_features'], state['costs'])
    model.load_state_dict(state)
    return model.to(device).eval(), ckpt


def main():
    p = argparse.ArgumentParser()
    p.add_argument('mode', choices=('calibrate', 'score'))
    for name in ('freeze', 'checkpoint', 'store', 'assets', 'output', 'selection', 'run'):
        p.add_argument('--'+name, required=True)
    p.add_argument('--release'); p.add_argument('--frequency-counts')
    p.add_argument('--roles')
    p.add_argument('--technical-resume')
    p.add_argument('--device', default='cuda')
    a = p.parse_args()
    torch.set_num_threads(1); torch.set_num_interop_threads(1)
    root = Path(__file__).resolve().parents[2]
    manifest, pins = frozen(root, a.freeze)
    selection = json.loads(Path(a.selection).read_text())
    if selection['manifest_sha256'] != pins['T5_manifest']:
        raise ValueError('selection uses different freeze')
    chosen = selection['runs'][a.run]
    checkpoint_hash = sha(a.checkpoint)
    if chosen['checkpoint_sha256'] != checkpoint_hash:
        raise ValueError('checkpoint is not dev-selected')
    device = torch.device(a.device)
    role = Path(a.store).name
    out = Path(a.output)
    started = time.monotonic()
    model, ckpt = load_model(a.checkpoint, device, pins, chosen['variant'])
    if sha(a.assets) != manifest['assets_sha256']:
        raise ValueError('asset content mismatch')
    if a.mode == 'calibrate':
        if role != 'dev':
            raise ValueError('calibration must be dev')
        role_guard(a.store, role, manifest)
        store = PackedStore(a.store, role, a.assets)
        if chosen['variant'] == 'gru':
            model.bind_store(store)
        runner.batch_loader = indexed_loader
        data = runner.calibration_data(model, store, device, 1024, cap=100000, seed=1, workers=2)
        temps = [fit_temperature(*data[k], role='dev') for k in ('gate', 'card', 'tile')]
        write_once(out, {'run': a.run, 'role': 'dev', 'checkpoint_sha256': checkpoint_hash,
                         'selection_sha256': sha(a.selection), 'manifest_sha256': pins['T5_manifest'],
                         'temperatures': temps, 'sample_seed': 1, 'sample_cap': 100000,
                         'head_rows': {k: len(v[2]) for k, v in data.items()},
                         'wall_seconds': time.monotonic()-started})
        return
    if not a.release or not a.frequency_counts or not a.roles:
        raise ValueError('heldout requires all-run release and pinned baseline')
    release = json.loads(Path(a.release).read_text())
    if (release['selection_sha256'] != sha(a.selection) or set(release['runs']) != set(selection['runs'])
            or len(release['runs']) != 5):
        raise ValueError('all five selected checkpoints/temperatures must be released before scoring')
    item = release['runs'][a.run]
    if item['checkpoint_sha256'] != checkpoint_hash or item['calibration']['checkpoint_sha256'] != checkpoint_hash:
        raise ValueError('temperature/checkpoint mismatch')
    from .guards import canonical_hash
    if canonical_hash(item['calibration']) != item['temperature_content_sha256']:
        raise ValueError('temperature content changed')
    temperatures = item['calibration']['temperatures']
    role_guard(a.store, role, manifest, heldout=True)
    if sha(a.frequency_counts) != manifest['frequency_counts_sha256']:
        raise ValueError('frequency baseline counts changed')
    if sha(a.roles) != manifest['role_file_sha256']:
        raise ValueError('role metadata changed')
    claim = Path(a.checkpoint).parent/f'heldout-{role}.claim.json'
    contract = {'run': a.run, 'role': role, 'output': str(out.resolve()),
                'checkpoint_sha256': checkpoint_hash, 'release_sha256': sha(a.release), **pins}
    if claim.exists():
        if json.loads(claim.read_text()) != contract or not a.technical_resume:
            raise ValueError('role already claimed; technical resume with identical contract required')
        if (out/'complete.json').exists():
            raise ValueError('role already scored; use saved statistics')
        with (out/'technical-resumes.jsonl').open('a') as f:
            f.write(json.dumps({'at': datetime.now(timezone.utc).isoformat(), 'reason': a.technical_resume})+'\n')
    else:
        if out.exists():
            raise ValueError('fresh score output required')
        write_once(claim, contract)
        out.mkdir(parents=True)
    store = HeldoutStore(a.store, role, a.assets, manifest)
    roles = json.loads(Path(a.roles).read_text())
    plan = json.loads((store.root.parent/'plan.json').read_text())
    metadata = {'engine_phases': [u['key'].split('/')[0] for u in plan['units']], 'perspectives': {}}
    names = store.assets['names'].tolist()
    for item in store.perspectives:
        summary = item['summary']; start = item['target_start']
        pid = str(int(store.arrays['perspective_ids'][start]))
        metadata['perspectives'][pid] = {
            'identity': item['identity'], 'start': start, 'rows': item['rows'], 'family': roles['family'][item['identity']],
            'mode': summary['info'].get('battle_type', 'other'), 'end_tick': summary['playable_end_tick'],
            'ability_attributable': bool(summary['ability_attributable']),
            'forms': {str(names.index(n)): f for n, f in zip(summary['own_deck'], summary['own_forms'])}}
    if not (out/'slice-metadata.json').exists():
        write_once(out/'slice-metadata.json', metadata)
    elif json.loads((out/'slice-metadata.json').read_text()) != metadata:
        raise ValueError('slice metadata changed across technical continuation')
    if chosen['variant'] == 'gru':
        model.bind_store(store)
    with np.load(a.frequency_counts, allow_pickle=False) as z:
        counts = {k: z[k] for k in ('gate', 'cards', 'tiles')}
    cursor = 0
    for path in sorted(out.glob('batch-*.npz')):
        with np.load(path, allow_pickle=False) as z:
            ix = z['index']
            if not np.array_equal(ix, np.arange(cursor, cursor+len(ix))):
                raise ValueError('saved batch prefix has gaps/overlap')
            cursor += len(ix)
    with torch.inference_mode():
        for b, y in indexed_loader(store, 1024, np.arange(cursor, len(store)), workers=2, pin_memory=device.type == 'cuda'):
            b, y = runner.transfer(b, device), runner.transfer(y, device)
            with torch.autocast('cuda', dtype=torch.bfloat16) if device.type == 'cuda' else nullcontext():
                o = model(b, torch.empty(0, dtype=torch.long, device=device))
            values = {}
            for stage, temps in (('before', (1., 1., 1.)), ('after', temperatures)):
                values.update({stage+'__'+k: v for k, v in metric_rows(o, y, b['ids'][:, :4], temps).items()})
            ix = y['index'].cpu().numpy()
            baseline = frequency_rows(store, ix, counts)
            values.update({'frequency__'+k: baseline[k] for k in ('joint_nll', 'play_wait_nll', 'card_nll', 'tile_nll')})
            values.update(index=ix, row_id=y['row_id'].cpu().numpy(), perspective=y['perspective'].cpu().numpy(),
                          p16=np.array(store.arrays['p16'][ix]), submitted_ticks=np.array(store.arrays['submitted_ticks'][ix]),
                          source_unit=np.array(store.arrays['source_unit'][ix]))
            final = out/f'batch-{cursor:09d}.npz'
            # Commit the full statistics of this forward pass atomically.
            temporary = final.with_suffix('.partial')
            if temporary.exists():
                # Preserve an incomplete write from the explicitly recorded
                # technical attempt; never overwrite or discard its evidence.
                temporary.rename(out/(temporary.name+'.failed-'+str(time.time_ns())))
            with temporary.open('xb') as f:
                np.savez(f, **values)
            temporary.replace(final)
            cursor += len(ix)
            print(json.dumps({'role': role, 'rows': cursor, 'seconds': time.monotonic()-started}), flush=True)
    write_once(out/'complete.json', {**contract, 'rows': cursor, 'wall_seconds': time.monotonic()-started,
                                    'slice_metadata_sha256': sha(out/'slice-metadata.json'),
                                    'batches': {p.name: sha(p) for p in sorted(out.glob('batch-*.npz'))}})


if __name__ == '__main__':
    import sys
    started = time.monotonic(); success = False
    try:
        main(); success = True
    finally:
        if '--output' in sys.argv:
            target = Path(sys.argv[sys.argv.index('--output')+1])
            parent = target if target.is_dir() else target.parent
            if parent.exists():
                own, child = resource.getrusage(resource.RUSAGE_SELF), resource.getrusage(resource.RUSAGE_CHILDREN)
                write_once(parent/f'{target.name}-compute-{os.getpid()}.json', {
                    'passed': success, 'wall_seconds': time.monotonic()-started,
                    'cpu_seconds': own.ru_utime+own.ru_stime+child.ru_utime+child.ru_stime,
                    'peak_self_rss_kib': own.ru_maxrss, 'pid': os.getpid()})
