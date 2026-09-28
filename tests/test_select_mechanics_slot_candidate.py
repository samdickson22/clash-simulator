from __future__ import annotations

from copy import deepcopy

from scripts.select_mechanics_slot_candidate import select_candidate


def _sweep(
    *,
    prefix: str,
    accuracies: tuple[float, float, float],
    accepted: bool = True,
    alpha: float = 0.2,
) -> dict:
    aggregate = {
        "alpha": alpha,
        "human_accuracy_mean": sum(accuracies) / 3.0,
        "human_accuracy_min": min(accuracies),
        "human_accuracy_max": max(accuracies),
        "validation_disagreement_max": 0.008,
        "heldout_disagreement_max": 0.009,
        "accepted": accepted,
    }
    per_probe = []
    for index, accuracy in enumerate(accuracies):
        per_probe.append(
            {
                "probe": f"/{prefix}/seed{index}.pt",
                "rows": [
                    {
                        "alpha": alpha,
                        "human": {
                            "accuracy": accuracy,
                            "base_accuracy": 0.45,
                        },
                        "validation": {"disagreement_with_base": 0.008},
                        "heldout": {"disagreement_with_base": 0.009},
                    }
                ],
            }
        )
    return {
        "schema": "mechanics-slot-normalized-blend-sweep-v1",
        "selected": aggregate if accepted else None,
        "aggregate_rows": [aggregate],
        "per_probe": per_probe,
    }


def _reports(*, promoted: tuple[bool, bool, bool]) -> list[dict]:
    return [
        {
            "source_probe": f"/source/seed{index}.pt",
            "promoted": current,
            "human_validation_source": {"mode": "external_replay_disjoint"},
        }
        for index, current in enumerate(promoted)
    ]


def test_selection_rejects_finetuned_arm_unless_every_seed_promotes() -> None:
    zero = _sweep(prefix="zero", accuracies=(0.47, 0.48, 0.49))
    tuned = _sweep(prefix="tuned", accuracies=(0.52, 0.53, 0.54))

    decision = select_candidate(
        zero_shot_sweep=zero,
        finetuned_sweep=tuned,
        finetune_reports=_reports(promoted=(True, False, True)),
    )

    assert decision["status"] == "candidate_selected"
    assert decision["selected"]["name"] == "zero_shot"
    assert decision["arms"][1] == {
        "name": "human_finetuned",
        "eligible": False,
        "reason": "not_all_finetune_seeds_promoted",
    }


def test_selection_uses_median_seed_from_validation_not_best_seed() -> None:
    zero = _sweep(prefix="zero", accuracies=(0.47, 0.48, 0.49))
    tuned = _sweep(prefix="tuned", accuracies=(0.52, 0.56, 0.54))

    decision = select_candidate(
        zero_shot_sweep=zero,
        finetuned_sweep=tuned,
        finetune_reports=_reports(promoted=(True, True, True)),
    )

    selected = decision["selected"]
    assert selected["name"] == "human_finetuned"
    assert selected["median_seed"]["probe"] == "/tuned/seed2.pt"
    assert selected["median_seed"]["human_accuracy"] == 0.54
    assert selected["base_scale"] == 0.8
    assert selected["query_scale"] == 0.2
    assert not decision["heldout_archetype_used_for_selection"]
    assert not decision["chronology_used_for_selection"]


def test_selection_rejects_when_neither_arm_has_safe_alpha() -> None:
    zero = _sweep(prefix="zero", accuracies=(0.47, 0.48, 0.49), accepted=False)
    tuned = _sweep(prefix="tuned", accuracies=(0.52, 0.53, 0.54), accepted=False)

    decision = select_candidate(
        zero_shot_sweep=zero,
        finetuned_sweep=tuned,
        finetune_reports=_reports(promoted=(True, True, True)),
    )

    assert decision["status"] == "rejected"
    assert decision["selected"] is None


def test_selection_fails_if_selected_row_was_mutated() -> None:
    zero = _sweep(prefix="zero", accuracies=(0.47, 0.48, 0.49))
    tuned = _sweep(prefix="tuned", accuracies=(0.52, 0.53, 0.54))
    tuned["selected"] = deepcopy(tuned["selected"])
    tuned["selected"]["human_accuracy_mean"] += 0.01

    try:
        select_candidate(
            zero_shot_sweep=zero,
            finetuned_sweep=tuned,
            finetune_reports=_reports(promoted=(True, True, True)),
        )
    except ValueError as error:
        assert "does not match" in str(error)
    else:
        raise AssertionError("mutated selected row was accepted")
