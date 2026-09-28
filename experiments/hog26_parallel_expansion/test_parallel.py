import json
from pathlib import Path

import numpy as np
import pytest
from parallel_engine import initialize
from parallel_io import publish_archive, publish_json
from parallel_protocol import (
    BASE_PLAN,
    build_plan,
    case_at,
    cases_for,
    expected_metadata,
    source_fingerprint,
    validate_plan,
)

ROOT = Path(__file__).resolve().parents[2]


def test_atomic_publication_never_overwrites(tmp_path):
    source, final = tmp_path / "temporary", tmp_path / "final"
    source.write_bytes(b"one")
    publish_archive(source, final)
    assert final.read_bytes() == b"one" and not source.exists()
    source.write_bytes(b"two")
    with pytest.raises(FileExistsError):
        publish_archive(source, final)
    assert final.read_bytes() == b"one" and source.read_bytes() == b"two"
    record = tmp_path / "record.json"
    publish_json(record, {"value": 1})
    publish_json(record, {"value": 1})
    with pytest.raises(ValueError, match="record differs"):
        publish_json(record, {"value": 2})


def test_parallel_schedule_is_exactly_the_sequential_population():
    original = json.loads((ROOT / BASE_PLAN).read_text())
    engine = initialize(ROOT, original["source_authority"]["contract"]["canonical_names"])
    authority = source_fingerprint(ROOT, resource_paths={
        "checkpoint": ROOT / "checkpoints/hog26_direct_constant_event_seed1263001/candidate.pt",
        "card_data": Path(engine.builder.loader.data_file)}, vocabulary_sha256=engine.vocabulary.sha256,
        card_definitions=engine.builder.loader.load_card_definitions())
    plan = build_plan(authority=authority)
    assert plan["schedules"] == original["schedules"] and plan["requirements"] == original["requirements"]
    assert not plan["collection_allowed"] and not plan["fitting_allowed"]
    for mode in ("preflight", "collect"):
        _, cases = cases_for(plan, mode)
        for index, case in enumerate(cases):
            direct = case_at(plan, mode, index)
            assert {key: direct[key] for key in case} == case
    plan["parallel_execution"]["workers"] = 4
    with pytest.raises(ValueError, match="frozen authority"):
        validate_plan(plan, authority)


def test_resume_metadata_matches_the_parity_tested_engine():
    directory = ROOT / "reports/hog26_parallel_collection_probe8_20260913"
    plan = json.loads((directory / "plan.json").read_text())
    engine = initialize(ROOT, plan["source_authority"]["contract"]["canonical_names"])
    for case in plan["cases"]:
        with np.load(directory / case["name"], allow_pickle=False) as archive:
            actual = json.loads(str(archive["metadata_json"]))
        assert expected_metadata(engine, plan, case, "preflight") == actual
