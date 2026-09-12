import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from scaling_dataset import load_combined_training, validate_combined_games
from scaling_protocol import ROLE, build_pilot_plan, validate_pilot_plan

from scripts.hog26_scalar_openings import digest

ROOT = Path(__file__).resolve().parents[2]


def authority():
    path = ROOT/'reports/hog26_scalar_birthfixed_frozen_plan_20260911.json'
    old = json.loads(path.read_text())
    value = copy.deepcopy(old['source_authority'])
    value['resources']['original_pilot_plan'] = {'path':str(path),'sha256':'fixture'}
    value['resources']['diagnostic_plan'] = {'path':str(ROOT/'reports/hog26_seed_transfer_frozen_plan_20260911.json'),'sha256':'fixture'}
    return value, old


def test_fixed_extension_and_reserved_roles():
    value, old = authority()
    plan = build_pilot_plan(authority=value)
    assert plan['expected_natural_games'] == 1152
    assert plan['independent_paired_scenarios'] == 576
    assert plan['requirements'] == old['requirements']
    assert not plan['collection_allowed'] and not plan['fitting_allowed']
    assert len(plan['schedules']) == 192
    for before, after in zip(old['schedules'], plan['schedules'], strict=True):
        assert after['external_authority']['episodes'] == 3
        assert after['external_authority']['role'] == ROLE
        assert before['family_id'] == after['family_id']
        assert before['external_authority']['relative_templates'] == after['external_authority']['relative_templates']
        assert before['external_authority']['opponent_style'] == after['external_authority']['opponent_style']


def test_frozen_extension_rejects_quota_mutation():
    value, _ = authority()
    pin = {'status':'passed','source_authority_sha256':digest(value),'evidence':{'test':'fixture'}}
    plan = build_pilot_plan(authority=value, preflight=pin)
    validate_pilot_plan(plan, value, expected_preflight=pin)
    plan['expected_natural_games'] = 384
    with pytest.raises(ValueError):
        validate_pilot_plan(plan, value, expected_preflight=pin)


def fixtures():
    def rows(prefix, per_family):
        return [SimpleNamespace(family=f'family-{f:03d}',cluster=f'{prefix}-{f}-{j//2}')
                for f in range(8) for j in range(per_family)]
    return rows('original',48), rows('new',144)


def test_combined_folds_and_diagnostic_isolation():
    old, new = fixtures()
    assert len(validate_combined_games(old,new,{'diagnostic'})) == 1536
    with pytest.raises(ValueError,match='overlap'):
        validate_combined_games(old,new,{new[0].cluster})
    new[0].cluster = old[0].cluster
    with pytest.raises(ValueError):
        validate_combined_games(old,new,set())


def test_wrong_counts_and_family_quota_fail():
    old, new = fixtures()
    with pytest.raises(ValueError):
        validate_combined_games(old,new[:-1],set())
    new[0].family='family-001'
    with pytest.raises(ValueError,match='family quota'):
        validate_combined_games(old,new,set())


def test_partial_extension_refused_before_array_access(tmp_path):
    plan=tmp_path/'plan.json'
    plan.write_text(json.dumps({'source_authority':{'resources':{'manifest':{'path':str(ROOT/'training_decks/hog26_procedural_supported_seed1278401.json')}}}}))
    with pytest.raises(ValueError,match='extension incomplete'):
        load_combined_training(tmp_path/'absent',extension_plan=plan,extension_preflight=tmp_path/'missing')
