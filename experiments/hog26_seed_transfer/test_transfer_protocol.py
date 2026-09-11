import copy
import json
from pathlib import Path

import pytest
from scripts.hog26_scalar_openings import digest
from transfer_protocol import ORIGINAL, ROLE, build_pilot_plan, validate_pilot_plan

ROOT = Path(__file__).resolve().parents[2]


def authority():
    old = json.loads((ROOT/ORIGINAL).read_text())
    value = copy.deepcopy(old['source_authority'])
    value['resources']['original_pilot_plan'] = {'path': str(ROOT/ORIGINAL), 'sha256': 'fixture'}
    return value, old


def test_exact_quota_new_role_preserved_requirements_and_decks():
    value, old = authority()
    result = build_pilot_plan(authority=value)
    assert not result['collection_allowed'] and not result['fitting_allowed']
    assert result['requirements'] == old['requirements']
    assert len(result['schedules']) == 192
    for before, after in zip(old['schedules'], result['schedules'], strict=True):
        assert before['family_id'] == after['family_id']
        assert before['learner_seats'] == after['learner_seats'] == [0, 1]
        for key in ('relative_templates', 'deck_name', 'opponent_style', 'episodes'):
            assert before['external_authority'][key] == after['external_authority'][key]
        assert after['external_authority']['role'] == ROLE
        assert before['metadata'] != after['metadata']


def test_frozen_plan_rejects_seed_quota_role_or_source_mutation():
    value, _ = authority()
    pin = {'status': 'passed', 'source_authority_sha256': digest(value), 'evidence': {'fixture': 'fixture'}}
    plan = build_pilot_plan(authority=value, preflight=pin)
    validate_pilot_plan(plan, value, expected_preflight=pin)
    for key, replacement in (('campaign_seed', '1'), ('episodes', 2), ('role', 'train')):
        changed = copy.deepcopy(plan)
        changed['schedules'][0]['external_authority'][key] = replacement
        with pytest.raises(ValueError):
            validate_pilot_plan(changed, value, expected_preflight=pin)
    changed = copy.deepcopy(value)
    changed['runtime']['torch_threads'] = 2
    with pytest.raises(ValueError):
        validate_pilot_plan(plan, changed, expected_preflight=pin)


def test_collector_and_loader_only_change_protocol_import_and_root():
    collector = (ROOT/'scripts/collect_hog26_scalar_pilot.py').read_text()
    collector = collector.replace('from scripts.hog26_scalar_pilot_protocol import (', 'from transfer_protocol import (')
    collector = collector.replace('root = Path(__file__).resolve().parents[1]', 'root = Path(__file__).resolve().parents[2]')
    assert collector == (ROOT/'experiments/hog26_seed_transfer/collect_transfer.py').read_text()
    loader = (ROOT/'experiments/hog26_scalar_pilot/scalar_dataset.py').read_text()
    loader = loader.replace('from scripts.hog26_scalar_pilot_protocol import validate_pilot_plan', 'from transfer_protocol import validate_pilot_plan')
    assert loader == (ROOT/'experiments/hog26_seed_transfer/transfer_dataset.py').read_text()
