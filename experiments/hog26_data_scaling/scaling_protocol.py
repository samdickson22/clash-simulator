"""Fixed1152-game training extension; collection alone never authorizes fitting."""
import copy
import json
from pathlib import Path

from scripts.hog26_scalar_opening_audit import audit_scalar_opening_metadata
from scripts.hog26_scalar_openings import CanonicalOpeningSchedule, digest
from scripts.hog26_scalar_pilot_protocol import (
    assert_source_unchanged,
)
from scripts.hog26_scalar_pilot_protocol import (
    build_pilot_plan as original_plan,
)
from scripts.hog26_scalar_pilot_protocol import (
    source_fingerprint as original_fingerprint,
)

ROLE = 'train-scalar-data-scaling'
SEEDS = (1279701, 1279702, 1279703)
ORIGINAL = 'reports/hog26_scalar_birthfixed_frozen_plan_20260911.json'


def source_fingerprint(root, *, resource_paths, vocabulary_sha256, card_definitions):
    root = Path(root)
    paths = dict(resource_paths)
    paths['original_pilot_plan'] = root / ORIGINAL
    paths['scaling_spec'] = root / 'reports/hog26_data_scaling_draft_20260912.json'
    paths['diagnostic_plan'] = root / 'reports/hog26_seed_transfer_frozen_plan_20260911.json'
    paths['original_training_complete'] = root / 'datasets/derived/hog26_scalar_birthfixed_pilot_seed1279261_20260911/complete.json'
    paths['diagnostic_complete'] = root / 'datasets/derived/hog26_seed_transfer_seed1279601_20260911/complete.json'
    for directory in ('experiments/hog26_data_scaling', 'experiments/hog26_scalar_pilot'):
        for path in sorted((root / directory).glob('*.py')):
            paths[str(path.relative_to(root))] = path
    return original_fingerprint(root, resource_paths=paths,
                                vocabulary_sha256=vocabulary_sha256,
                                card_definitions=card_definitions)


def build_pilot_plan(*, authority, preflight=None):
    result = original_plan(authority=authority, preflight=preflight)
    old = json.loads(Path(authority['resources']['original_pilot_plan']['path']).read_text())
    old_clusters = set()
    diagnostic = json.loads(Path(authority['resources']['diagnostic_plan']['path']).read_text())
    for schedule in old['schedules'] + diagnostic['schedules']:
        old_clusters.update(s.cluster_id for s in audit_scalar_opening_metadata(
            schedule['metadata'], expected_authority=schedule['external_authority']))
    new_clusters = set()
    for index, schedule in enumerate(result['schedules']):
        pin = copy.deepcopy(schedule['external_authority'])
        pin['role'] = ROLE
        pin['episodes'] = 3
        pin['campaign_seed'] = str(SEEDS[index // 64])
        metadata = CanonicalOpeningSchedule(
            campaign_seed=int(pin['campaign_seed']), role=ROLE,
            deck_name=pin['deck_name'], opponent_style=pin['opponent_style'],
            learner_template=pin['relative_templates'][0],
            opponent_template=pin['relative_templates'][1],
            canonical_names=pin['canonical_names'], episodes=3).metadata()
        scenarios = audit_scalar_opening_metadata(metadata, expected_authority=pin)
        for scenario in scenarios:
            if scenario.cluster_id in old_clusters | new_clusters:
                raise ValueError('training extension repeats an existing relative deal')
            new_clusters.add(scenario.cluster_id)
        schedule.update(external_authority=pin, metadata=metadata)
    if len(new_clusters) != 576:
        raise ValueError('training extension quota changed')
    if result['requirements'] != old['requirements']:
        raise ValueError('reserved roles or acceptance requirements changed')
    result['expected_natural_games'] = 1152
    result['independent_paired_scenarios'] = 576
    result['combined_training_games'] = 1536
    result['extension_scope'] = 'New training games only. Requires separate combined-corpus audit and fitting authority; no automatic fitting or promotion.'
    result['original_training_plan_sha256'] = digest(old)
    return result


def validate_pilot_plan(plan, current_authority, *, expected_preflight=None):
    assert_source_unchanged(plan.get('source_authority'), current_authority)
    if plan != build_pilot_plan(authority=current_authority, preflight=expected_preflight):
        raise ValueError('training extension plan differs from fixed external contract')
    return {'status': 'valid-frozen' if expected_preflight else 'valid-draft',
            'natural_games': 1152, 'collection_allowed': expected_preflight is not None}
