"""HP1 P1 pilot trainer: the qualified T4 trainer with T11's mixed sampling, plus explicit, logged options.

The qualified loop is imitation/model/train.py, unchanged (byte-identical to T11's frozen copy; its source is
re-verified here against the T4 throughput qualification receipt, as T11 did). Like imitation/t11/train.py, this
wrapper only replaces module attributes before calling it:
  --layers/--ffn     ModelConfig shape (P1-cap: 6 layers, FFN 1536 = the rl5/f1a2 student shape)
  --init CKPT        start from a checkpoint's EMA weights (P1-lag: v2); config and asset buffers must match;
                     the optimizer starts fresh
  --lr               AdamW learning rate (T4 hard-codes 3e-4)
  --overlay DIR      train-role labels from imitation.hp1.lagshift (actions / supervision / weights); dev stays natural
  --stop-after-epochs K   checkpoint and exit after the dev pass that completes epoch K, keeping the full-run cosine
                     schedule (--epochs), so the run is a prefix of a full run and is resumable with --resume
  --max-gpu-gb G     per-process CUDA memory cap (shared GPU)
  --smoke            end-to-end check: needs --max-steps <= 50 and an output path containing '/smoke'; the dev pass
                     scores only the first 4096 dev rows. Smoke checkpoints are never used for evaluation.
  --block-shuffle    sequential whole-perspective chunks with a bounded RAM shuffle (default OFF);
                     --shuffle-buffer-gb sets the buffer (default 20 GiB, max 24); --workers 0 or 1
Everything else (loss, row selection, EMA, checkpoints, dev joint NLL) is T4/T11's. Hosts 127x01/04/08 only.
Wrapper options are logged to OUTPUT.hp1-options.jsonl NEXT TO the output directory (T4 requires a fresh, empty one)
and their hashes into every checkpoint's `hashes`.

  python -m imitation.hp1.train --store S/train --dev S/dev --assets A --qualification T11-STORE-PASS.json \\
      --output OUT --seed SEED [T4 args] [HP1 args]
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import sys
from dataclasses import asdict
from pathlib import Path

import numpy as np
import torch

from imitation.model import train as qualified, runner
from imitation.model.network import ModelConfig, SetPolicy
from imitation.model.store import PackedStore, sha256

V2_STORE_MANIFEST = '7180964c1d470807a97ad7a990ac8eb145fb25d15f1c95edf165b3f87743d20f'
HOSTS = ('127x01', '127x04', '127x08')
OVERLAY_FIELDS = ('expert_actions', 'expert_action_supervision_valid', 'weights')
ROOT = Path(__file__).resolve().parents[2]


def parse(argv):
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument('--layers', type=int, default=4); p.add_argument('--ffn', type=int, default=768)
    p.add_argument('--init', type=Path); p.add_argument('--lr', type=float, default=3e-4)
    p.add_argument('--overlay', type=Path); p.add_argument('--stop-after-epochs', type=int)
    p.add_argument('--max-gpu-gb', type=float); p.add_argument('--smoke', action='store_true')
    p.add_argument('--block-shuffle', action='store_true')
    p.add_argument('--shuffle-buffer-gb', type=float, default=20.)
    ext, remaining = p.parse_known_args(argv)
    if ext.block_shuffle:
        q = argparse.ArgumentParser(add_help=False)
        q.add_argument('--epoch-fraction', type=float, default=1.)
        full, _ = q.parse_known_args(remaining)
        if full.epoch_fraction != 1.:
            p.error('--block-shuffle requires --epoch-fraction 1 (complete T11 epoch)')
    return ext, remaining


def options_path(out):
    """Wrapper metadata lives beside, never inside, T4's output directory."""
    out = Path(out)
    return out.parent / f'{out.name}.hp1-options.jsonl'


def load_overlay(directory, store_dir):
    directory, store_dir = Path(directory), Path(store_dir)
    meta = json.loads((directory / 'overlay.json').read_text())
    if meta.get('schema') != 'clasher.hp1.lag-overlay.v1':
        raise ValueError('not an HP1 lag overlay')
    if meta['store_manifest_sha256'] != sha256(store_dir.parent / 'manifest.json'):
        raise ValueError('overlay built for another store')
    if meta['role_manifest_sha256'] != sha256(store_dir / 'manifest.json'):
        raise ValueError('overlay built for another role')
    if meta['mask_table_sha256'] != sha256(store_dir.parent / 'mask_table.npy'):
        raise ValueError('overlay built against another mask table')
    arrays = {}
    for name in OVERLAY_FIELDS:
        path = directory / f'{name}.npy'
        if sha256(path) != meta['files'][name]:
            raise ValueError(f'overlay file changed: {name}')
        arrays[name] = np.load(path, mmap_mode='r', allow_pickle=False)
    return meta, arrays


def apply_overlay(store, overlay, overlay_sha):
    for name in OVERLAY_FIELDS:
        if overlay[name].shape != store.arrays[name].shape or overlay[name].dtype != store.arrays[name].dtype:
            raise ValueError(f'overlay shape/dtype mismatch: {name}')
        store.arrays[name] = overlay[name]
    store.hashes['hp1_overlay'] = overlay_sha


def config_factory(layers, ffn):
    def make_config(**kw):
        return ModelConfig(**kw, layers=layers, ffn=ffn)
    return make_config


def model_factory(init):
    """T4 calls SetPolicy(config, descriptors, tiles, costs); with --init the EMA weights replace the fresh ones."""
    def make_model(config, descriptors, tiles, costs):
        model = SetPolicy(config, descriptors, tiles, costs)
        if init:
            ck = torch.load(init, map_location='cpu', weights_only=True)
            if ck['config'] != asdict(config):
                raise ValueError(f'--init config {ck["config"]} differs from the run config {asdict(config)}')
            sd = ck['ema']
            for buf in ('descriptors', 'tile_features', 'costs'):
                if not torch.equal(sd[buf].cpu(), model.state_dict()[buf].cpu()):
                    raise ValueError(f'--init buffer {buf} differs from the store assets')
            model.load_state_dict(sd, strict=True)
        return model
    return make_model


class SmokeDev:
    """Dev store proxy with only the first 4096 rows (smoke runs only)."""
    def __init__(self, store):
        self._store = store

    def __getattr__(self, name):
        if name.startswith('__') or name == '_store':    # keeps pickling (loader workers) from recursing
            raise AttributeError(name)
        return getattr(self._store, name)

    def __len__(self):
        return min(4096, len(self._store))


def main(argv=None):
    ext, remaining = parse(sys.argv[1:] if argv is None else argv)
    host = socket.gethostname().split('.')[0]
    if host not in HOSTS:
        raise SystemExit(f'host {host} outside HP1 allocation {HOSTS}')
    opts = dict(zip(remaining[::2], remaining[1::2]))
    for forbidden in ('--subset-fraction', '--overfit-rows', '--synthetic-smoke'):
        if forbidden in remaining:
            raise SystemExit(f'{forbidden} is not an HP1 option')
    if ext.init and '--resume' in opts:
        raise SystemExit('--init starts a run; --resume continues one (its weights come from the checkpoint)')
    out = Path(opts['--output'])
    if ext.smoke and not ('--max-steps' in opts and int(opts['--max-steps']) <= 50 and '/smoke' in str(out)):
        raise SystemExit('--smoke needs --max-steps <= 50 and an output path containing /smoke')
    if not ext.smoke and '--max-steps' in opts:
        raise SystemExit('--max-steps changes the cosine schedule; use --stop-after-epochs (or --smoke)')
    store_dir = Path(opts['--store'])
    if sha256(store_dir.parent / 'manifest.json') != V2_STORE_MANIFEST:
        raise SystemExit('HP1 trains on the v2 packed store only')
    from imitation.t5.guards import qualification
    receipt, receipt_sha = qualification(ROOT)            # qualified T4 source, as T11 checked it
    pins = {'T4_code': receipt['code_sha256'], 'T4_throughput': receipt_sha,
            'HP1_train': sha256(Path(__file__)), 'HP1_lagshift': sha256(Path(__file__).with_name('lagshift.py')),
            'T11_sampling': sha256(ROOT / 'imitation/t11/sampling.py'),
            'T5_bounded_loader': sha256(ROOT / 'imitation/t5/resources.py')}
    block = None
    if ext.block_shuffle:
        from imitation.hp1.block_shuffle import BlockShuffle
        block = BlockShuffle(ext.shuffle_buffer_gb)
        if int(opts.get('--workers', 2)) not in (0, 1):
            raise SystemExit('--block-shuffle needs --workers 0 or 1 (one shared RAM buffer)')
        pins['HP1_block_shuffle'] = sha256(Path(__file__).with_name('block_shuffle.py'))
        pins['HP1_sampling_options'] = block.pin()
    if ext.init:
        pins['HP1_init'] = sha256(ext.init)
    if '--resume' in opts:            # a run started with --init keeps its init pin; T4 then checks every hash for equality
        resumed = torch.load(opts['--resume'], map_location='cpu', weights_only=True)['hashes']
        if 'HP1_init' in resumed:
            pins['HP1_init'] = resumed['HP1_init']
    if ext.max_gpu_gb and torch.cuda.is_available():
        total = torch.cuda.get_device_properties(0).total_memory / 2**30
        torch.cuda.set_per_process_memory_fraction(min(1., ext.max_gpu_gb / total), 0)
    overlay_meta, overlay, overlay_sha = None, None, None
    if ext.overlay:
        overlay_meta, overlay = load_overlay(ext.overlay, store_dir)
        overlay_sha = sha256(ext.overlay / 'overlay.json')

    class TrainingStore(PackedStore):
        def __init__(self, directory, role, assets=None):
            super().__init__(directory, role, assets)
            if not self.t3 or json.loads((self.root.parent / 'manifest.json').read_text()).get('version') != 'v2':
                raise ValueError('expected the v2 T3 packed store')
            self.hashes.update(pins)
            if overlay is not None and role == 'train':
                apply_overlay(self, overlay, overlay_sha)

    original_dev = runner.dev_joint_nll
    done_before = 0
    if '--resume' in opts:
        done_before = int(torch.load(opts['--resume'], map_location='cpu', weights_only=True)['state']['epoch'])
    dev_calls = [0]

    def dev_then_maybe_stop(model, ema, store, *args, **kwargs):
        score = original_dev(model, ema, SmokeDev(store) if ext.smoke else store, *args, **kwargs)
        dev_calls[0] += 1
        if ext.stop_after_epochs and done_before + dev_calls[0] >= ext.stop_after_epochs:
            os.kill(os.getpid(), signal.SIGTERM)    # T4's handler: checkpoint at the epoch boundary, then exit
        return score

    original_adamw = torch.optim.AdamW

    def adamw(params, lr, weight_decay):
        return original_adamw(params, lr=ext.lr, weight_decay=weight_decay)

    from imitation.t5.resources import install as install_bounded_loader
    from imitation.t11.sampling import epoch_indices, train_loader
    install_bounded_loader()
    qualified.PackedStore = TrainingStore
    qualified.epoch_indices = block.epoch_indices if block else epoch_indices
    qualified.batch_loader = block.train_loader if block else train_loader
    qualified.ModelConfig = config_factory(ext.layers, ext.ffn)
    qualified.SetPolicy = model_factory(ext.init)
    torch.optim.AdamW = adamw
    runner.dev_joint_nll = dev_then_maybe_stop
    out.parent.mkdir(parents=True, exist_ok=True)
    with options_path(out).open('a') as f:
        f.write(json.dumps(dict(host=host, pins=pins, hp1=dict(
            layers=ext.layers, ffn=ext.ffn, init=str(ext.init) if ext.init else None, lr=ext.lr,
            overlay=str(ext.overlay) if ext.overlay else None, overlay_stats=overlay_meta['stats'] if overlay_meta else None,
            stop_after_epochs=ext.stop_after_epochs, max_gpu_gb=ext.max_gpu_gb, smoke=ext.smoke,
            block_shuffle=ext.block_shuffle, shuffle_buffer_gb=ext.shuffle_buffer_gb), t4_args=remaining)) + '\n')
    sys.argv = [sys.argv[0], *remaining]
    try:
        qualified.main()
    finally:
        torch.optim.AdamW = original_adamw


if __name__ == '__main__':
    main()
