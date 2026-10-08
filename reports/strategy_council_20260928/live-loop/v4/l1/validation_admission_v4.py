"""Authenticate completed T7 fit files before validation; never open heldout media.

This is a readiness command, not a replay, model selection, or heldout entry point.
It repeats the producer/registration/receipt admission before reading checkpoints.
"""
import argparse
import hashlib
import json
from pathlib import Path

from formal_guard import admit
from selection_guard_v4 import validate_t7_fit


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024**2), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(path.read_text())


def expected_sources():
    code = Path(__file__).resolve().parent
    root = code.parents[4]
    return [*[code/n for n in ('train_v4.py', 'data_v4.py', 'labels_v4.py', 'pixel_cache.py')],
            root/'src/clasher/vision/l1_v4.py', root/'gamedata.json',
            root/'reports/strategy_council_20260928/live-loop/l1/calibration.json',
            code.parent/'body-catalog.json']


def validate_run(run, source, split, phase_state, phase_exit):
    # Keep this first: premature or inauthentic producer completion must not
    # trigger checkpoint or match-payload reads, even for a previously fitted pilot.
    admission = admit(phase_state, phase_exit, source, split, Path(__file__).parent)
    saved_admission = read(run/'admission.json')
    if saved_admission != admission:
        raise ValueError('Formal run admission differs from current authenticated population')
    populations = {'train': {}, 'validation': {}}
    for receipt_path, expected in admission['receipts'].items():
        path = Path(receipt_path)
        if path.parent.parent.resolve() != source.resolve() or sha(path) != expected:
            raise ValueError('Admission receipt path/hash changed')
        receipt = read(path)  # receipt metadata only, including heldout counts.
        if receipt['episode'] != path.parent.name:
            raise ValueError('Episode identity differs from admitted receipt path')
        if receipt['split'] in populations:
            group = populations[receipt['split']]
            if receipt['episode'] in group:
                raise ValueError('Duplicate admitted episode')
            group[receipt['episode']] = expected
    if not populations['validation']:
        raise ValueError('Full validation population missing')
    model = run/'model'
    manifest, complete, inventory = (read(model/p) for p in ('manifest.json', 'complete.json', 'data/inventory.json'))
    measured = {str(p): sha(p) for p in expected_sources()}
    if manifest.get('source_hashes') != measured:
        raise ValueError('Current replay/training sources differ from measured fit')
    for path, digest in measured.items():
        if sha(model/'source'/Path(path).name) != digest:
            raise ValueError('Training source snapshot differs')
    if sha(model/'last.pt') != complete.get('checkpoint_sha256'):
        raise ValueError('Final checkpoint bytes changed')
    cache = Path(manifest.get('pixel_cache') or '')
    for ep, digest in manifest.get('cache_index_sha256', {}).items():
        if ep not in populations['train'] or sha(cache/ep/'index.json') != digest:
            raise ValueError('Training cache index changed')
    with (model/'training.jsonl').open() as f:
        logs = [json.loads(line) for line in f]
    import torch
    checkpoints = {}
    for epoch in range(1, 25):
        path = model/f'epoch-{epoch}.pt'
        digest = sha(path)
        state = torch.load(path, map_location='cpu', weights_only=True)
        if not isinstance(state.get('model'), dict) or not state['model']:
            raise ValueError('Missing epoch model state')
        checkpoints[epoch] = dict(step=state.get('step'), cards=state.get('cards'),
                                  bodies=state.get('bodies'), sha256=digest)
        del state
    result = validate_t7_fit(manifest, complete, inventory, logs,
        admitted_train_receipts=populations['train'], checkpoints=checkpoints,
        measured_source_hashes=measured)
    return dict(result, validation_matches=len(populations['validation']),
                validation_receipt_sha256=populations['validation'],
                checkpoint_sha256={str(k):v['sha256'] for k,v in checkpoints.items()},
                fit_manifest_sha256=sha(model/'manifest.json'),
                completion_sha256=sha(model/'complete.json'), admission_sha256=sha(run/'admission.json'),
                heldout_payloads_opened=False,
                limitations='Validation pixels/truth, timing conversion, replay, calibration and seal still required')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('run', 'source', 'split', 'phase-state', 'phase-exit', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    result = validate_run(args.run, args.source, args.split, args.phase_state, args.phase_exit)
    with args.output.open('x') as f:
        json.dump(result, f, indent=2)
        f.write('\n')
    print(json.dumps(result), flush=True)
