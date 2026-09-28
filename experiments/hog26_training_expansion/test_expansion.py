import copy
import json
from pathlib import Path

import pytest
from expansion_protocol import (
    COMPLETE_PATHS,
    PLAN_PATHS,
    ROLE,
    build_pilot_plan,
    preflight_schedules,
    validate_pilot_plan,
)

from scripts.hog26_scalar_opening_audit import audit_scalar_opening_metadata
from scripts.hog26_scalar_openings import digest

ROOT = Path(__file__).resolve().parents[2]


def fixture_authority():
    original = json.loads((ROOT / PLAN_PATHS[0]).read_text())
    authority = copy.deepcopy(original["source_authority"])
    for relative in (*PLAN_PATHS, *COMPLETE_PATHS):
        authority["resources"][relative] = {"path": str(ROOT / relative), "sha256": "fixture"}
    return authority, original


def test_complete_unfiltered_schedule_and_reserved_roles():
    authority, original = fixture_authority()
    plan = build_pilot_plan(authority=authority)
    assert plan["expected_natural_games"] == 4608
    assert plan["independent_paired_scenarios"] == 2304
    assert plan["combined_training_games"] == 6144
    assert plan["requirements"] == original["requirements"]
    assert not plan["collection_allowed"] and not plan["fitting_allowed"]
    assert len(plan["schedules"]) == 192
    for before, after in zip(original["schedules"], plan["schedules"], strict=True):
        assert after["external_authority"]["role"] == ROLE
        assert after["external_authority"]["episodes"] == 12
        assert after["family_id"] == before["family_id"]
        assert after["learner_seats"] == before["learner_seats"]
        assert after["external_authority"]["relative_templates"] == before["external_authority"]["relative_templates"]
        assert after["external_authority"]["opponent_style"] == before["external_authority"]["opponent_style"]


def test_frozen_plan_requires_excluded_preflight_and_refuses_changed_quota():
    authority, _ = fixture_authority()
    draft = build_pilot_plan(authority=authority)
    schedules = preflight_schedules(draft)
    assert len(schedules) == 6
    clusters = [scenario.cluster_id for schedule in schedules for scenario in audit_scalar_opening_metadata(
        schedule["metadata"], expected_authority=schedule["external_authority"])]
    pin = {"status": "passed", "source_authority_sha256": digest(authority),
           "evidence": {"synthetic_test": True}, "preflight_clusters": clusters}
    plan = build_pilot_plan(authority=authority, preflight=pin)
    validate_pilot_plan(plan, authority, expected_preflight=pin)
    plan["expected_natural_games"] = 384
    with pytest.raises(ValueError, match="fixed external contract"):
        validate_pilot_plan(plan, authority, expected_preflight=pin)
    pin["preflight_clusters"] = []
    with pytest.raises(ValueError, match="six independently audited"):
        build_pilot_plan(authority=authority, preflight=pin)


def test_partial_preflight_refuses_before_archive_access(tmp_path):
    from publish_plan import audit_preflight

    (tmp_path / "complete.json").write_text(json.dumps({"status": "partial"}))
    with pytest.raises(ValueError, match="complete matching twelve-game"):
        audit_preflight(tmp_path, {}, {})
