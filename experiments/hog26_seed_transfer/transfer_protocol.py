"""Fixed fresh-seed diagnostic; existing models stay frozen and no fitting is allowed."""
import copy
import json
from pathlib import Path

from scripts.hog26_scalar_openings import CanonicalOpeningSchedule, digest
from scripts.hog26_scalar_opening_audit import audit_scalar_opening_metadata
from scripts.hog26_scalar_pilot_protocol import (
    assert_source_unchanged,
    build_pilot_plan as original_plan,
    source_fingerprint as original_fingerprint,
)

ROLE = 'diagnostic-frozen-model-seed-transfer'
SEEDS = (1279601, 1279602, 1279603)
ORIGINAL = 'reports/hog26_scalar_birthfixed_frozen_plan_20260911.json'


def source_fingerprint(root, *, resource_paths, vocabulary_sha256, card_definitions):
    root = Path(root)
    paths = dict(resource_paths)
    paths['original_pilot_plan'] = root / ORIGINAL
    paths['transfer_evaluation_spec'] = root / 'reports/hog26_seed_transfer_spec_20260911.json'
    for directory in ('experiments/hog26_seed_transfer', 'experiments/hog26_scalar_pilot'):
        for path in sorted((root / directory).glob('*.py')):
            paths[str(path.relative_to(root))] = path
    for model in ('globals', 'tree', 'entity'):
        directory = root / f'reports/hog26_scalar_birthfixed_{model}_comparison_20260911'
        paths[f'{model}_manifest'] = directory / 'fitting_manifest.json'
        paths[f'{model}_complete'] = directory / 'complete.json'
        for path in sorted(directory.glob('*')):
            if path.suffix in ('.pt', '.pkl'):
                paths[str(path.relative_to(root))] = path
    return original_fingerprint(root, resource_paths=paths,
                                vocabulary_sha256=vocabulary_sha256,
                                card_definitions=card_definitions)


def build_pilot_plan(*, authority, preflight=None):
    result = original_plan(authority=authority, preflight=preflight)
    old = json.loads(Path(authority['resources']['original_pilot_plan']['path']).read_text())
    old_clusters = set()
    for schedule in old['schedules']:
        old_clusters.update(s.cluster_id for s in audit_scalar_opening_metadata(
            schedule['metadata'], expected_authority=schedule['external_authority']))
    new_clusters = set()
    for index, schedule in enumerate(result['schedules']):
        pin = copy.deepcopy(schedule['external_authority'])
        pin['role'] = ROLE
        pin['campaign_seed'] = str(SEEDS[index // 64])
        metadata = CanonicalOpeningSchedule(
            campaign_seed=int(pin['campaign_seed']), role=ROLE,
            deck_name=pin['deck_name'], opponent_style=pin['opponent_style'],
            learner_template=pin['relative_templates'][0],
            opponent_template=pin['relative_templates'][1],
            canonical_names=pin['canonical_names'], episodes=1).metadata()
        scenarios = audit_scalar_opening_metadata(metadata, expected_authority=pin)
        for scenario in scenarios:
            if scenario.cluster_id in old_clusters | new_clusters:
                raise ValueError('fresh-seed diagnostic repeats an existing relative deal')
            new_clusters.add(scenario.cluster_id)
        schedule.update(external_authority=pin, metadata=metadata)
    if len(new_clusters) != 192:
        raise ValueError('fresh-seed quota changed')
    if result['requirements'] != old['requirements']:
        raise ValueError('reserved roles or acceptance requirements changed')
    result['diagnostic_scope'] = 'Frozen-model inference on fresh seeds; both seen-family and excluded-family metrics. No fitting or promotion.'
    result['original_training_plan_sha256'] = digest(old)
    return result


def validate_pilot_plan(plan, current_authority, *, expected_preflight=None):
    assert_source_unchanged(plan.get('source_authority'), current_authority)
    if plan != build_pilot_plan(authority=current_authority, preflight=expected_preflight):
        raise ValueError('fresh-seed plan differs from fixed external contract')
    return {'status': 'valid-frozen' if expected_preflight else 'valid-draft',
            'natural_games': 384, 'collection_allowed': expected_preflight is not None}
