"""Campaign orchestration tests; synthetic validators do not establish native parity."""

import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_calibration_collection import (
    frozen as frozen,  # noqa: PLC0414 -- pytest fixture re-export
)

from clasher.rl.calibration_families import (
    claim_acceptance_branches,
    claim_acceptance_collection,
    require_unopened_acceptance,
)
from clasher.rl.native_match_registry import canonical_digest


@pytest.fixture
def evaluator(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    module = importlib.import_module("evaluate_prospective_calibration")
    monkeypatch.setattr(
        module,
        "NativeProjectileCatalog",
        SimpleNamespace(from_csv=lambda *a, **k: object()),
    )
    return module


def test_missing_index_entries_fail_and_consume_evaluation(frozen, evaluator, tmp_path):
    path, args, _ = frozen
    index = tmp_path / "index.json"
    index.write_text("{}")
    result = evaluator.evaluate(
        path, args["registry"], index, args["catalog"], args["workspace"]
    )
    assert not result["acceptance_passed"] and result["ranking_failed_families"] == 1
    with pytest.raises(ValueError, match="opened"):
        evaluator.evaluate(
            path, args["registry"], index, args["catalog"], args["workspace"]
        )


@pytest.mark.parametrize("independent_vocabulary", [False, True])
def test_complete_synthetic_flow_opens_cohort_before_reading_scores(
    frozen, evaluator, tmp_path, monkeypatch, independent_vocabulary
):
    path, args, family = frozen
    sha = evaluator.artifact_digest(path)
    config = canonical_digest(args["config"])
    capture = tmp_path / "capture"
    capture.mkdir()
    (capture / "artifact-receipt.json").write_text("{}")
    branches = tmp_path / "branches"
    branches.mkdir()
    (branches / "artifact-receipt.json").write_text("{}")
    protocol = {
        "role": "acceptance",
        "collection_protocol_sha256": sha,
        "family": "f",
        "owner": 0,
        "response_seeds": [1],
        "root_duplicate_group_id": family.root_ids[0],
        "candidates": [{"name": "wait"}, {"name": "recorded"}],
    }
    claim_acceptance_collection(
        args["registry"],
        family_id="f",
        root_id=family.root_ids[0],
        protocol_sha256=sha,
        output_path=capture,
    )
    claim_acceptance_branches(
        args["registry"],
        family_id="f",
        root_id=family.root_ids[0],
        protocol_sha256=sha,
        branch_protocol_sha256=canonical_digest(protocol),
        attempts=[(n, e) for n in ("wait", "recorded") for e in ("native", "scalar")],
        output_path=branches,
    )
    frozen_sources = json.loads(path.read_text())["source_files"]
    names = {
        "compare_reacting_public_branches.py",
        "prepare_prospective_branch.py",
        "select_reacting_public_root.py",
        "collect_public_development_games.py",
        "read_native_public_levels.py",
        "smoke_reference_battle.py",
    }
    sources = {
        k: v
        for k, v in frozen_sources.items()
        if k.startswith("src/clasher/") or Path(k).name in names
    }
    (branches / "provenance.json").write_text(
        json.dumps({"sources": sources, "inputs": {}})
    )
    monkeypatch.setattr(evaluator, "prepare", lambda *a: protocol)
    monkeypatch.setattr(evaluator, "verify_archives", lambda *a: None)
    monkeypatch.setattr(
        evaluator,
        "audit_capture",
        lambda *a: {
            "errors": [],
            "sources_unchanged": True,
            "paired_frames_passed": 2,
            "hidden_deck_independent_vocabulary": independent_vocabulary,
        },
    )

    def read_scores(*a, **k):
        with pytest.raises(ValueError, match="opened"):
            require_unopened_acceptance(args["registry"], "f", sha)
        return [
            {
                "candidate": n,
                "engine": e,
                "failure": None,
                "native_attestation_sha256": "e" * 64 if e == "native" else None,
                "response_seed": 1,
                "terminal": {
                    "tick": 3601,
                    "winner": 0,
                    "towers": [{"owner": 0, "hp": 200 if n == "wait" else 0}],
                },
            }
            for n in ("wait", "recorded")
            for e in ("native", "scalar")
        ]

    monkeypatch.setattr(evaluator, "read_branch_evidence", read_scores)
    index = tmp_path / "index.json"
    index.write_text(
        json.dumps(
            {
                config: {
                    "capture": str(capture),
                    "branches": [
                        {"path": str(branches), "engines": ["native", "scalar"]}
                    ],
                }
            }
        )
    )
    result = evaluator.evaluate(
        path, args["registry"], index, args["catalog"], args["workspace"]
    )
    assert result["acceptance_passed"] is independent_vocabulary
    assert result["public_failed_families"] == (0 if independent_vocabulary else 1)
    assert result["clear_improvement_families"] == (1 if independent_vocabulary else 0)
    assert not result["training_authorized"]
