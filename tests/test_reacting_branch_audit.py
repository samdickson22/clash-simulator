"""Ranking reports must retain ties and reject incomplete paired evidence."""

import importlib.util
import json
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "branch_audit",
    Path(__file__).resolve().parents[1] / "scripts/audit_reacting_public_branches.py",
)
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def branch(candidate, engine, winner, hp):
    return {
        "response_seed": 3,
        "candidate": candidate,
        "engine": engine,
        "failure": None,
        "commands": [],
        "decision_counts": [2, 2],
        "terminal": {
            "tick": 6001,
            "winner": winner,
            "towers": [{"owner": 1, "hp": hp}, {"owner": 0, "hp": 10}],
        },
    }


def fixture(tmp_path, rows):
    for name, data in {
        "protocol.json": {
            "owner": 1,
            "response_seeds": [3],
            "candidates": [{"name": "a"}, {"name": "b"}],
        },
        "complete.json": {"sources_unchanged": True},
        "results.json": rows,
    }.items():
        (tmp_path / name).write_text(json.dumps(data))


def test_win_precedes_hp_and_strict_reversal_is_reported(tmp_path):
    fixture(
        tmp_path,
        [
            branch("a", "native", 1, 0),
            branch("b", "native", 0, 9000),
            branch("a", "scalar", 0, 9000),
            branch("b", "scalar", 1, 0),
        ],
    )
    result = AUDIT.audit(tmp_path)
    assert result["pairwise_rankings"][0]["strict_reversal"]
    assert not result["acceptance_passed"]


def test_tie_disagreement_is_not_a_strict_reversal(tmp_path):
    fixture(
        tmp_path,
        [
            branch("a", "native", 0, 100),
            branch("b", "native", 0, 100),
            branch("a", "scalar", 0, 101),
            branch("b", "scalar", 0, 100),
        ],
    )
    pair = AUDIT.audit(tmp_path)["pairwise_rankings"][0]
    assert pair["tie_disagreement"]
    assert not pair["strict_reversal"]


@pytest.mark.parametrize("fault", ["missing", "duplicate", "failed", "nonterminal"])
def test_incomplete_evidence_cannot_be_scored(tmp_path, fault):
    rows = [branch(c, e, 0, 100) for c in ("a", "b") for e in ("native", "scalar")]
    if fault == "missing":
        rows.pop()
    elif fault == "duplicate":
        rows.append(rows[0])
    elif fault == "failed":
        rows[0]["failure"] = {"type": "unconfirmed_command"}
    else:
        rows[0]["terminal"] = None
    fixture(tmp_path, rows)
    with pytest.raises(ValueError):
        AUDIT.audit(tmp_path)


def test_same_winners_with_hp_reversal_remain_a_secondary_disagreement(tmp_path):
    fixture(
        tmp_path,
        [
            branch("a", "native", 1, 100),
            branch("b", "native", 1, 90),
            branch("a", "scalar", 1, 90),
            branch("b", "scalar", 1, 100),
        ],
    )
    result = AUDIT.audit(tmp_path)
    pair = result["pairwise_rankings"][0]
    assert pair["strict_reversal"]
    assert pair["hp_only_order_disagreement"]
    assert not pair["outcome_order_disagreement"]
    assert all(r["winner_matches"] for r in result["branches"])
    assert result["independent_acceptance_roots"] == 0


def test_lost_win_distinction_is_reported_even_if_hp_preserves_order(tmp_path):
    fixture(
        tmp_path,
        [
            branch("a", "native", 1, 100),
            branch("b", "native", 0, 90),
            branch("a", "scalar", 1, 100),
            branch("b", "scalar", 1, 90),
        ],
    )
    pair = AUDIT.audit(tmp_path)["pairwise_rankings"][0]
    assert pair["native"] == pair["scalar"] == 1
    assert pair["outcome_order_disagreement"]
    assert not pair["hp_only_order_disagreement"]


def test_response_magnitudes_can_reverse_mean_ranking_despite_per_seed_agreement(
    tmp_path,
):
    rows = []
    for seed, values in [
        (3, {"native": (0, 10), "scalar": (0, 30)}),
        (4, {"native": (30, 0), "scalar": (10, 0)}),
    ]:
        for engine, (a, b) in values.items():
            for name, hp in [("a", a), ("b", b)]:
                row = branch(name, engine, 1, hp)
                row["response_seed"] = seed
                rows.append(row)
    fixture(tmp_path, rows)
    protocol = json.loads((tmp_path / "protocol.json").read_text())
    protocol["response_seeds"] = [3, 4]
    (tmp_path / "protocol.json").write_text(json.dumps(protocol))
    result = AUDIT.audit(tmp_path)
    assert not any(r["strict_reversal"] for r in result["pairwise_rankings"])
    assert result["response_mean_rankings"][0]["strict_reversal"]
