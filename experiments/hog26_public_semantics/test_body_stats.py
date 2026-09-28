import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from body_stats import STATIC_INDICES, compile_body_table, descriptor


def test_primary_body_does_not_inherit_spawn_count_or_child_flying():
    stats = SimpleNamespace(hitpoints=500, damage=100, hit_speed=2000,
                            summon_count=5, _card_def=None)
    values, confidence, detail = descriptor(
        stats, {"flyingHeight": 0, "spawned": {"flyingHeight": 10}})
    assert detail["raw"]["base_direct_dps"] == 50
    assert values[3] == 0 and confidence[3] == 1
    assert not confidence[4:7].any()


def test_missing_damage_remains_unknown():
    values, confidence, _ = descriptor(SimpleNamespace(hit_speed=1000), {})
    assert not values[:2].any() and not confidence[:2].any()


def test_known_body_table_matches_all_recorded_static_fields():
    root = Path(__file__).resolve().parents[2]
    plan = json.loads((root / "reports/hog26_residual_margin_frozen_plan_20260912.json").read_text())
    table = compile_body_table(plan["data"]["vocabulary"])
    audit = json.loads((root / "reports/hog26_public_body_registry_audit_20260912.json").read_text())
    assert len(audit["tokens"]) == 54
    for item in audit["tokens"]:
        token = item["token_id"]
        assert table.resolved[token]
        expected = np.array([item["observed_static_field_ranges"][str(i)][0]
                             for i in STATIC_INDICES], dtype=np.float32)
        np.testing.assert_array_equal(table.expected_static[token], expected)
    with pytest.raises(ValueError, match="read-only"):
        table.values[0, 0] = 1
