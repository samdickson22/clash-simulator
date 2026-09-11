import copy

import pytest

from scripts.hog26_scalar_pilot_protocol import (
    assert_source_unchanged,
    build_pilot_plan,
    validate_pilot_plan,
)


@pytest.fixture
def authority():
    cards = [f"Card{i}" for i in range(8)]
    return {"sources": {"scripts/collector.py": "a" * 64}, "contract": {
        "decks": [{"name": f"deck-{i}", "split": "train", "family_id": f"family-{i // 4:03d}",
                   "cards": cards} for i in range(32)],
        "learner_template": cards, "canonical_names": cards,
        "requirements": {"gates": {"minimum_nll_improvement": .02}},
    }}


def test_full_pilot_pairs_same_scenario(authority):
    plan = build_pilot_plan(authority=authority)
    assert validate_pilot_plan(plan, authority)["collection_allowed"] is False
    assert len(plan["schedules"]) == 192
    assert len({s["metadata"]["scenarios"][0]["scenario_id"] for s in plan["schedules"]}) == 192
    assert all(s["learner_seats"] == [0, 1] for s in plan["schedules"])
    assert {s["external_authority"]["campaign_seed"] for s in plan["schedules"]} == {"1279261", "1279262", "1279263"}


@pytest.mark.parametrize("mutation", ["gate", "missing_game", "permission", "source", "opening"])
def test_tampered_plan_rejected(authority, mutation):
    plan = build_pilot_plan(authority=authority)
    if mutation == "gate":
        plan["requirements"]["gates"]["minimum_nll_improvement"] = 0
    elif mutation == "missing_game":
        plan["schedules"].pop()
    elif mutation == "permission":
        plan["collection_allowed"] = True
    elif mutation == "source":
        plan["source_authority"]["sources"]["scripts/collector.py"] = "b" * 64
    else:
        plan["schedules"][0]["metadata"]["scenarios"][0]["stream_seeds"]["battle"] = "1"
    with pytest.raises(ValueError):
        validate_pilot_plan(plan, authority)


def test_missing_training_family_rejected(authority):
    authority["contract"]["decks"].pop()
    with pytest.raises(ValueError, match="all 32"):
        build_pilot_plan(authority=authority)


def test_external_source_pin_required(authority):
    changed = copy.deepcopy(authority)
    changed["sources"]["scripts/new.py"] = "b" * 64
    with pytest.raises(ValueError, match="authority changed"):
        assert_source_unchanged(authority, changed)


def test_frozen_requires_external_preflight(authority):
    from scripts.hog26_scalar_openings import digest
    preflight = {"status": "passed", "source_authority_sha256": digest(authority),
                 "evidence": {"audit.json": "c" * 64}}
    plan = build_pilot_plan(authority=authority, preflight=preflight)
    assert plan["frozen"] and not plan["fitting_allowed"]
    assert validate_pilot_plan(plan, authority, expected_preflight=preflight)["collection_allowed"]
    with pytest.raises(ValueError):
        validate_pilot_plan(plan, authority)
    preflight["source_authority_sha256"] = "d" * 64
    with pytest.raises(ValueError, match="exact source"):
        build_pilot_plan(authority=authority, preflight=preflight)


def test_fingerprint_detects_untracked_source_and_resource_change(tmp_path):
    import json

    import torch

    from scripts.hog26_scalar_pilot_protocol import (
        INHERITED,
        LEARNER,
        MANIFEST,
        PROTOCOL,
        source_fingerprint,
    )

    for directory in ("scripts", "src/clasher", "reports", "training_decks"):
        (tmp_path / directory).mkdir(parents=True)
    (tmp_path / "scripts/collector.py").write_text("pass\n")
    (tmp_path / MANIFEST).write_text(json.dumps({"decks": [
        {"name": "learner", "cards": LEARNER}]}))
    protocol = {key: {"exact": "unchanged"} for key in INHERITED}
    protocol.update(replication={"rule": "all-three", "counterfactual_rule": "after-gates"},
                    development_selection={"expected_games": 1024},
                    probability_calibration={"expected_games": 1024},
                    final_holdout={"generated": {"expected_games": 1536},
                                   "reserved_original": {"expected_games": 36}, "controlled_draw": {}},
                    corrected_draw_controls={"training": {}, "validation": {}})
    (tmp_path / PROTOCOL).write_text(json.dumps(protocol))
    for name in ("checkpoint", "cards"):
        (tmp_path / name).write_text(name)
    kwargs = {"resource_paths": {"checkpoint": "checkpoint", "card_data": "cards"},
              "vocabulary_sha256": "e" * 64, "card_definitions": dict.fromkeys(LEARNER)}
    previous_threads = torch.get_num_threads()
    torch.set_num_threads(1)
    try:
        pin = source_fingerprint(tmp_path, **kwargs)
        assert pin["contract"]["requirements"]["gates"] == protocol["gates"]
        (tmp_path / "scripts/new_untracked.py").write_text("pass\n")
        with pytest.raises(ValueError):
            assert_source_unchanged(pin, source_fingerprint(tmp_path, **kwargs))
        pin = source_fingerprint(tmp_path, **kwargs)
        (tmp_path / "cards").write_text("changed")
        with pytest.raises(ValueError):
            assert_source_unchanged(pin, source_fingerprint(tmp_path, **kwargs))
    finally:
        torch.set_num_threads(previous_threads)
