"""Read-only CPU audit of a durable checkpoint, for exact-state migration."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import socket
import struct
import torch


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def fingerprint(value):
    """Stable typed digest of every value/tensor byte; independent of host paths."""
    h = hashlib.sha256()
    def token(tag, data=b''):
        h.update(tag); h.update(struct.pack('>Q', len(data))); h.update(data)
    def visit(v):
        if isinstance(v, torch.Tensor):
            token(b'T', str(v.dtype).encode()); visit(list(v.shape))
            token(b'B', v.detach().cpu().contiguous().reshape(-1).view(torch.uint8).numpy().tobytes())
        elif isinstance(v, dict):
            token(b'D', str(len(v)).encode())
            for k in sorted(v, key=lambda x: (type(x).__name__, repr(x))):
                visit(k); visit(v[k])
        elif isinstance(v, (list, tuple)):
            token(b'L' if isinstance(v, list) else b'U', str(len(v)).encode())
            for item in v:
                visit(item)
        elif v is None:
            token(b'N')
        elif isinstance(v, bool):
            token(b'Z', bytes([v]))
        elif isinstance(v, int):
            token(b'I', str(v).encode())
        elif isinstance(v, float):
            token(b'F', struct.pack('>d', v))
        elif isinstance(v, str):
            token(b'S', v.encode())
        else:
            raise TypeError(type(v).__name__)
    visit(value)
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--checkpoint', type=Path, required=True)
    p.add_argument('--freeze', type=Path, required=True)
    p.add_argument('--seed', type=int, choices=(2026100821, 2026100822), required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args(); host = socket.gethostname().split('.')[0]
    assert host in ('127x01', '127x04', '127x08', '127x16', '127x18')
    assert a.checkpoint.suffix == '.pt' and not a.output.exists()
    torch.set_num_threads(1); torch.set_num_interop_threads(1)
    manifest = json.loads(a.freeze.read_text())
    seal = json.loads((a.freeze.parent/'freeze.json').read_text())
    assert sha(a.freeze) == seal['manifest_sha256']
    assert sha(a.freeze.parent/'PREREG.md') == seal['prereg_sha256']
    before = sha(a.checkpoint)
    checkpoint = torch.load(a.checkpoint, map_location='cpu', weights_only=True)
    assert sha(a.checkpoint) == before, 'checkpoint changed during read'
    required = {'model', 'ema', 'optimizer', 'scheduler', 'state', 'config', 'args',
                'hashes', 'provenance', 'torch_rng', 'python_rng', 'numpy_rng', 'cuda_rng'}
    assert required == set(checkpoint)
    hashes = checkpoint['hashes']
    assert hashes['T11_manifest'] == seal['manifest_sha256'] and hashes['T11_prereg'] == seal['prereg_sha256']
    assert hashes['T4_code'] == manifest['qualified_code_sha256']
    for key, value in dict(seed=a.seed, epochs=6, batch_size=8192, microbatch=7168,
                           workers=1, tile_width=64, warmup=2000, patience=3, checkpoint_every=1000).items():
        assert checkpoint['args'][key] == value, key
    state = checkpoint['state']; assert state['step'] > 0 and state['cursor'] >= 0
    assert checkpoint['optimizer']['state'] and checkpoint['model'] and checkpoint['ema']
    assert checkpoint['scheduler']['last_epoch'] == state['step']
    assert checkpoint['torch_rng'].numel() and len(checkpoint['cuda_rng']) == 1
    section_hashes = {k: fingerprint(v) for k, v in checkpoint.items()}
    state = {k: (None if isinstance(v, float) and v == float('inf') else v) for k, v in state.items()}
    result = dict(passed=True, audited_at=datetime.now(timezone.utc).isoformat(), host=host,
                  checkpoint=str(a.checkpoint.resolve()), checkpoint_sha256=before,
                  bytes=a.checkpoint.stat().st_size, seed=a.seed, state=state,
                  section_sha256=section_hashes, frozen_hashes=hashes,
                  scheduler_last_epoch=checkpoint['scheduler']['last_epoch'],
                  optimizer_parameter_states=len(checkpoint['optimizer']['state']),
                  evaluator_invoked=False, auditor_sha256=sha(Path(__file__)),
                  fingerprint_schema='typed-recursive-tensor-bytes-v1')
    with a.output.open('x') as f:
        json.dump(result, f, indent=2, allow_nan=False); f.write('\n')
    print(json.dumps(result, allow_nan=False))


if __name__ == '__main__':
    main()
