from __future__ import annotations

from scripts.finalize_hog26_behavior_reproduction import compare


def _evaluation(
    *, scores: tuple[int, int], counts: tuple[int, int], action_hash: str | None = None
) -> dict:
    rows = []
    for opponent, score, count in zip(
        ("balanced", "random"), scores, counts, strict=True
    ):
        rows.append(
            {
                "opponent": opponent,
                "games": 4,
                "wins": max(score, 0),
                "losses": max(-score, 0),
                "draws": 4 - abs(score),
                "placement_rate": 0.07,
                "card_counts": {"card_action:HogRider": count},
                "records": [
                    {
                        "decisions": 400,
                        **(
                            {"action_sha256": action_hash}
                            if action_hash is not None
                            else {}
                        ),
                    }
                    for _game in range(4)
                ],
            }
        )
    return {
        "schema": "clasher.hog26.simple-policy-evaluation.v1",
        "checkpoint_sha256": "a" * 64,
        "base_seed": 7,
        "games_per_opponent": 4,
        "chunk_steps": 64,
        "rows": rows,
    }


def test_closed_loop_comparison_passes_behavior_but_not_small_scale() -> None:
    result = compare(
        _evaluation(scores=(1, 0), counts=(12, 8)),
        _evaluation(scores=(1, 0), counts=(11, 9)),
    )
    assert result["behavior_gate_pass"] is True
    assert result["scale_gate_met"] is False
    assert result["status"] == "passed-smoke-not-promotion"


def test_closed_loop_comparison_rejects_bucket_regression_or_missing_card() -> None:
    result = compare(
        _evaluation(scores=(2, 0), counts=(12, 8)),
        _evaluation(scores=(0, 0), counts=(0, 20)),
    )
    assert result["behavior_gate_pass"] is False
    assert result["status"] == "rejected"


def test_closed_loop_comparison_reports_exact_action_hashes() -> None:
    teacher = _evaluation(scores=(0, 0), counts=(8, 8), action_hash="a" * 64)
    student = _evaluation(scores=(0, 0), counts=(8, 8), action_hash="a" * 64)
    student["rows"][1]["records"][0]["action_sha256"] = "b" * 64
    result = compare(teacher, student)
    assert result["exact_action_hash_matches"] == 7
    assert result["exact_action_hash_rows"] == 8
    assert result["exact_action_hash_match_rate"] == 7 / 8
