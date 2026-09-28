"""A separate public feature cache for audited training controls."""

import json
from pathlib import Path

from stream_contract import PIN as ONLINE_PIN
from stream_contract import validate as validate_online
from training_contract import OUTPUT as CORPUS
from training_contract import PIN as COLLECTION_PIN
from training_contract import validate as validate_collection
from value_contract import ROOT, publish, sha

PIN = ROOT / 'reports/hog26_mirror_training_features_pin_20260913.json'
OUTPUT = ROOT / 'reports/hog26_mirror_training_features_20260913'
RESULT = OUTPUT / 'complete.json'


def sources():
    return {str(p.relative_to(ROOT)): sha(p) for p in sorted(Path(__file__).parent.glob('*.py'))}


def prepare():
    collection, online = validate_collection(), validate_online()
    complete = json.loads((CORPUS / 'complete.json').read_text())
    if complete['status'] != 'complete-audited-scalar-mirror-training-controls' or complete['physical_games'] != 256 or complete['actor_views'] != 512:
        raise ValueError('complete independently audited control collection required')
    resources = {str(COLLECTION_PIN.relative_to(ROOT)): sha(COLLECTION_PIN), str(ONLINE_PIN.relative_to(ROOT)): sha(ONLINE_PIN),
                 str((CORPUS / 'complete.json').relative_to(ROOT)): sha(CORPUS / 'complete.json')}
    resources.update(collection['sources'])
    resources.update(online['sources'])
    resources.update(online['resources'])
    records = []
    for ordinal in range(256):
        directory = CORPUS / f'game{ordinal:04}'
        completion = directory / 'complete.json'
        if sha(completion) != complete['resources'][str(completion.relative_to(CORPUS))]:
            raise ValueError('control completion changed')
        game = json.loads(completion.read_text())
        resources[str(completion.relative_to(ROOT))] = sha(completion)
        for seat in (0, 1):
            path = directory / f'seat{seat}.npz'
            expected = game['artifacts'][path.name]
            if sha(path) != expected:
                raise ValueError('raw public control changed')
            resources[str(path.relative_to(ROOT))] = expected
            records.append({'path': str(path), 'sha256': expected, 'rows': game['rows_each'], 'seat': seat,
                            'physical_game': game['scenario_id'], 'cluster': game['cluster_id'], 'ordinal': ordinal,
                            'role': game['role']})
    publish(PIN, {'schema': 'clasher.hog26.mirror-training-features.v1', 'sources': sources(), 'resources': resources,
                  'games': records, 'rows': complete['rows'], 'features': 814, 'physical_clusters': 256,
                  'scope': 'Encoding-only cache, separate from natural games. All814public columns reproduce streaming/batch bytes on every control frame. Labels remain separate; raw WDL explicitly reversed into canonical LDW. Both views share physical cluster. No model fitting, selection or natural frequency calibration.',
                  'acceptance': False, 'fitting_performed': False})


def validate():
    validate_collection()
    validate_online()
    pin = json.loads(PIN.read_text())
    if pin['sources'] != sources() or pin['features'] != 814 or len(pin['games']) != 512 or pin['acceptance']:
        raise ValueError('control cache authority changed')
    for path, expected in pin['resources'].items():
        if sha(ROOT / path) != expected:
            raise ValueError('control cache input changed: ' + path)
    return pin
