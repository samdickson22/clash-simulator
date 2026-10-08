"""Coordinator-authorized same-seed host-loss rerun; frozen science unchanged."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import sys


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    p.add_argument('--operational-freeze', required=True)
    p.add_argument('--operational-freeze-sha256', required=True)
    a, rest = p.parse_known_args()
    frozen_path = Path(a.operational_freeze)
    assert sha(frozen_path) == a.operational_freeze_sha256
    spec = json.loads(frozen_path.read_text())
    assert socket.gethostname().split('.')[0] == '127x01'
    assert rest == spec['training_argv']
    assert '--resume' not in rest
    for name, expected in spec['files'].items():
        assert sha(frozen_path.parent/name) == expected, name
    assert sha(__file__) == spec['files'][Path(__file__).name]
    from imitation.t5.guards import frozen, role_guard
    from imitation.t5 import train
    root = Path(spec['source'])
    assert Path(train.__file__).resolve() == root/'imitation/t5/train.py'
    manifest, _ = frozen(root, spec['scientific_manifest'])
    assert sha(spec['scientific_manifest']) == spec['parent_manifest_sha256']
    for role in ('train', 'dev'):
        role_guard(Path(spec['store'])/role, role, manifest)
    assert sha(spec['assets']) == manifest['assets_sha256']
    output = Path(spec['output'])
    output.mkdir(parents=True, exist_ok=False)
    record = dict(at=datetime.now(timezone.utc).isoformat(), pid=os.getpid(),
                  operational_freeze_sha256=sha(frozen_path),
                  reason='coordinator-authorized host11 loss; fresh same-seed technical rerun',
                  actual_loader_workers=4, parent_recipe_workers=1, mmap_eviction=False,
                  cuda_allocator_fraction=0.75, initialization='fresh; no resume',
                  excluded_host11_output=spec['excluded_host11_output'])
    (output/'hostloss-operations.json').write_text(json.dumps(record, indent=2)+'\n')
    from main02_loader4_v2 import configure_loader
    from gpu_headroom import configure
    configure_loader()
    configure()
    print(json.dumps({'event': 'hostloss_technical_rerun', **record}), flush=True)
    sys.argv = [sys.argv[0], *rest]
    train.main()


if __name__ == '__main__':
    main()
