"""Technical continuation: rebind provenance ONLY; preserve all training state."""
import argparse
import json
from pathlib import Path
import torch
from .guards import frozen, sha, write_once


def equal(a, b):
    if isinstance(a, torch.Tensor): return isinstance(b, torch.Tensor) and torch.equal(a.cpu(), b.cpu())
    if isinstance(a, dict): return a.keys()==b.keys() and all(equal(a[k], b[k]) for k in a)
    if isinstance(a, (list, tuple)): return len(a)==len(b) and all(equal(x,y) for x,y in zip(a,b))
    return a==b


def main():
    p = argparse.ArgumentParser()
    for key in ('checkpoint','old-manifest','new-freeze','output'): p.add_argument('--'+key, required=True)
    a = p.parse_args(); root = Path(__file__).resolve().parents[2]
    manifest, pins = frozen(root, a.new_freeze)
    if manifest['amendment']['parent_manifest_sha256'] != sha(a.old_manifest):
        raise ValueError('migration parent mismatch')
    old_prereg = Path(a.old_manifest).parent/'PREREG.md'
    payload = torch.load(a.checkpoint, map_location='cpu', weights_only=True)
    if payload['hashes']['T5_manifest']!=sha(a.old_manifest) or payload['hashes']['T5_prereg']!=sha(old_prereg):
        raise ValueError('checkpoint parent registration mismatch')
    old_hashes = dict(payload['hashes'])
    for key in ('T4_code', 'T4_throughput'):
        if old_hashes[key] != pins[key]: raise ValueError('qualified T4 source changed')
    payload['hashes'] = {**old_hashes, **pins}
    out = Path(a.output); out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('xb') as f: torch.save(payload, f)
    restored = torch.load(out, map_location='cpu', weights_only=True)
    original = torch.load(a.checkpoint, map_location='cpu', weights_only=True)
    fields = [k for k in original if k!='hashes']
    if not all(equal(original[k], restored[k]) for k in fields):
        raise ValueError('state changed during provenance-only migration')
    write_once(str(out)+'.migration.json', {'passed': True, 'reason': 'recorded resource-r2 technical continuation',
               'source_checkpoint_sha256': sha(a.checkpoint), 'output_checkpoint_sha256': sha(out),
               'old_hashes': old_hashes, 'new_hashes': restored['hashes'],
               'bit_exact_fields': fields, 'state': {k:v for k,v in payload['state'].items() if k!='best_dev'}})


if __name__ == '__main__':
    main()
