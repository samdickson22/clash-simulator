"""Explicit operational loader override; frozen T4/T5 scientific code stays intact."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import socket
import sys


def configure_loader():
    from imitation.t5 import train, resources
    from imitation.model import batching
    original = batching.batch_loader
    def install():
        batching.BatchedStore = resources.OriginalBatchedStore
    def loader(store, batch_size, indices=None, **kwargs):
        kwargs['workers'] = 4
        return original(store, batch_size, indices, **kwargs)
    train.install_rss_bound = install
    train.qualified_loader = loader


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument('--operational-freeze', required=True)
    p.add_argument('--operational-freeze-sha256', required=True)
    p.add_argument('--resume-sha256', required=True)
    p.add_argument('--loader-workers', type=int, required=True)
    a, remaining = p.parse_known_args()
    assert a.loader_workers == 4
    op = Path(a.operational_freeze)
    assert digest(op) == a.operational_freeze_sha256
    spec = json.loads(op.read_text())
    for name, expected in spec['files'].items():
        assert digest(op.parent/name) == expected, name
    assert digest(__file__) == spec['files'][Path(__file__).name]
    assert socket.gethostname().split('.')[0] == '127x11'
    lease = json.loads(Path('/mpac/sdicks02/fleet-leases/127x11.json').read_text())
    assert lease['project'] == 'clasher' and lease.get('shared') is False
    assert not lease.get('reclaim') and not lease.get('refused')
    assert datetime.now(timezone.utc) < datetime.fromisoformat(lease['expected_end_utc'].replace('Z','+00:00'))
    options = dict(zip(remaining[::2], remaining[1::2]))
    assert options['--variant'] == 'main' and options['--seed'] == '2026100802'
    assert Path(options['--output']).resolve() == Path(spec['output'])
    assert Path(options['--resume']).resolve().parent == Path(spec['output'])
    assert digest(options['--resume']) == a.resume_sha256
    assert digest(options['--freeze']) == spec['parent_manifest_sha256']
    assert options['--workers'] == '1'  # Parent recipe guard; actual override is explicit above.
    assert options['--stop-at'] == '2026-10-09T04:20:00Z'
    from imitation.t5.guards import frozen
    root = Path(spec['source'])
    frozen(root, Path(options['--freeze']))
    from imitation.t5 import train
    assert Path(train.__file__).resolve() == root/'imitation/t5/train.py'
    record = dict(at=datetime.now(timezone.utc).isoformat(), operational_freeze_sha256=digest(op),
                  actual_loader_workers=4, mmap_eviction=False, parent_recipe_workers=1,
                  resume=options['--resume'], resume_sha256=a.resume_sha256,
                  parent_manifest_sha256=spec['parent_manifest_sha256'])
    with (Path(spec['output'])/'loader-operations.jsonl').open('a') as f:
        f.write(json.dumps(record)+'\n')
    print(json.dumps({'event':'operational_loader_override', **record}), flush=True)
    configure_loader()
    sys.argv = [sys.argv[0], *remaining]
    train.main()


if __name__ == '__main__':
    main()
