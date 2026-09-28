from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.build_win_condition_utilization_matrix import (
    WIN_CONDITION_SPECS,
    build_matrix,
)
from scripts.evaluate_win_condition_utilization import (
    promotion_gate,
    summarize_utilization,
)
from scripts.finalize_mechanics_slot_gameplay_gate import (
    PAIRED_SPECS,
    PAIRED_WORKLOADS,
    _sha256,
)
from scripts.finalize_mechanics_slot_pfsp_pilot import finalize_pfsp_pilot


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_utilization(decisions_path: Path, games_path: Path, output: Path) -> None:
    decisions = json.loads(decisions_path.read_text(encoding="utf-8"))
    games = json.loads(games_path.read_text(encoding="utf-8"))
    report = summarize_utilization(decisions, games)
    report["gate"] = promotion_gate(
        report,
        max_zero_use_rate=0.10,
        min_window_conversion_rate=0.25,
        min_games_per_seat=5,
    )
    report.update(
        {
            "decisions": str(decisions_path.resolve()),
            "decisions_sha256": _sha256(decisions_path),
            "game_records": str(games_path.resolve()),
            "game_records_sha256": _sha256(games_path),
        }
    )
    _write(output, report)


def _write_designated_utilization(
    decisions_path: Path,
    games_path: Path,
    output: Path,
    *,
    card: str,
) -> None:
    decisions = json.loads(decisions_path.read_text(encoding="utf-8"))
    games = json.loads(games_path.read_text(encoding="utf-8"))
    report = summarize_utilization(
        decisions,
        games,
        role="designated_win_condition",
        designated_cards={card},
    )
    report["gate"] = promotion_gate(
        report,
        max_zero_use_rate=0.0,
        min_window_conversion_rate=0.25,
        min_games_per_seat=1,
    )
    report.update(
        {
            "decisions": str(decisions_path.resolve()),
            "decisions_sha256": _sha256(decisions_path),
            "game_records": str(games_path.resolve()),
            "game_records_sha256": _sha256(games_path),
        }
    )
    _write(output, report)


def _eval(
    *,
    checkpoint: Path,
    opponent: Path | None,
    decks: Path,
    games: int,
    seed: int,
    mode: str,
    strategy: str | None,
    metrics: dict,
) -> dict:
    outcome_metrics = {
        "wins": games // 2,
        "losses": games - games // 2,
        "draws": 0,
        "crown_diff_per_game": 0.0,
        "candidate_noop_when_playable": 0.75,
        **metrics,
    }
    return {
        "schema_version": 1,
        "checkpoint": str(checkpoint),
        "checkpoint_sha256": _sha256(checkpoint),
        "opponent_checkpoint": None if opponent is None else str(opponent),
        "opponent_checkpoint_sha256": (
            None if opponent is None else _sha256(opponent)
        ),
        "sampling_decks_path": str(decks),
        "sampling_decks_sha256": _sha256(decks),
        "seed": seed,
        "mirror_match": True,
        "opponent_mode": mode,
        "opponent_strategy": strategy,
        "reward_profile": "defense-v2",
        "metrics": {"games": games, **outcome_metrics},
    }


def _strategy(checkpoint: Path, decks: Path, score: float = 0.5) -> dict:
    names = (
        "bridge-pressure",
        "slow-push",
        "spell-control",
        "reactive-defense",
        "split-lane",
        "balanced",
    )
    return {
        "schema_version": 1,
        "candidate": {
            "checkpoint": str(checkpoint),
            "checkpoint_sha256": _sha256(checkpoint),
        },
        "protocol": {
            "sampling_decks_path": str(decks),
            "sampling_decks_sha256": _sha256(decks),
            "games_per_opponent": 6,
            "seed": 1056201,
            "reward_profile": "defense-v2",
            "paired_seats": True,
            "public_information_only": True,
        },
        "results": {name: {"score_rate": score} for name in names},
    }


def _write_win_condition_matrix_evidence(
    *,
    root: Path,
    manifest_path: Path,
    parent: Path,
    candidate: Path,
) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for index, (entry, spec) in enumerate(
        zip(manifest["entries"], WIN_CONDITION_SPECS, strict=True)
    ):
        deck_pool = Path(entry["deck_pool"])
        cards = json.loads(deck_pool.read_text(encoding="utf-8"))["decks"][0][
            "cards"
        ]
        tag = spec.archetype.replace("-", "_")
        seed = 1_056_401 + index
        games = [
            {
                "game": game,
                "candidate_player": game,
                "candidate_deck": cards,
            }
            for game in range(2)
        ]
        decisions = [
            {
                "game": game,
                "game_decision": 0,
                "hand": cards[:4],
                "elixir": 10.0,
                "slot": 0,
                "is_no_op": False,
                "is_ability": False,
                "action_type_probabilities": [
                    1.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                ],
            }
            for game in range(2)
        ]
        for role, checkpoint in (("parent", parent), ("candidate", candidate)):
            metrics_path = root / f"{role}_{tag}2.metrics.json"
            games_path = root / f"{role}_{tag}2.games.json"
            decisions_path = root / f"{role}_{tag}2.decisions.json"
            _write(
                metrics_path,
                _eval(
                    checkpoint=checkpoint,
                    opponent=None,
                    decks=deck_pool,
                    games=2,
                    seed=seed,
                    mode="strategy",
                    strategy="balanced",
                    metrics={},
                ),
            )
            _write(games_path, games)
            _write(decisions_path, decisions)
            _write_designated_utilization(
                decisions_path,
                games_path,
                root / f"{role}_{tag}2.utilization.json",
                card=spec.card,
            )
        baseline = root / f"parent_{tag}2.games.json"
        challenger = root / f"candidate_{tag}2.games.json"
        _write(
            root / f"{tag}2.compare.json",
            {
                "schema_version": 1,
                "baseline": str(baseline),
                "baseline_sha256": _sha256(baseline),
                "candidate": str(challenger),
                "candidate_sha256": _sha256(challenger),
                "games": 2,
                "improvements": [],
                "regressions": [],
                "improvement_count": 0,
                "regression_count": 0,
                "unchanged_count": 2,
                "baseline_crown_difference": 0.0,
                "candidate_crown_difference": 0.0,
                "crown_difference_change": 0.0,
                "passes_strict_no_regression": True,
            },
        )


def _fixture(tmp_path: Path) -> dict:
    root = tmp_path / "pilot"
    initializer = tmp_path / "initializer"
    root.mkdir()
    initializer.mkdir()
    parent = tmp_path / "parent.pt"
    candidate = tmp_path / "candidate.pt"
    parent.write_bytes(b"parent")
    candidate.write_bytes(b"candidate")
    validation = tmp_path / "validation.json"
    heldout = tmp_path / "heldout.json"
    hog = tmp_path / "hog.json"
    pfsp_decks = tmp_path / "pfsp.json"
    source_decks: dict[str, list[dict[str, object]]] = {
        "validation": [],
        "heldout": [],
    }
    for spec in WIN_CONDITION_SPECS:
        source_decks[spec.source].append(
            {
                "name": f"{spec.archetype}-source",
                "source": "project-base",
                "substitutions": 0,
                "archetype": spec.archetype,
                "cards": [
                    spec.card,
                    "Musketeer",
                    "Skeletons",
                    "IceSpirit",
                    "Fireball",
                    "Log",
                    "Cannon",
                    "Knight",
                ],
            }
        )
    _write(validation, {"decks": source_decks["validation"]})
    _write(heldout, {"decks": source_decks["heldout"]})
    for path in (hog, pfsp_decks):
        path.write_text("[]\n", encoding="utf-8")
    win_condition_manifest = tmp_path / "matrix_pools" / "manifest.json"
    build_matrix(
        validation_path=validation,
        heldout_path=heldout,
        output_dir=win_condition_manifest.parent,
    )
    _write(
        initializer / "summary.json",
        {
            "rl_initializer_eligible": True,
            "candidate_checkpoint": str(parent),
            "candidate_checkpoint_sha256": _sha256(parent),
        },
    )

    unbalanced = tmp_path / "unbalanced.json"
    train = tmp_path / "balanced.json"
    unbalanced.write_text("unbalanced\n", encoding="utf-8")
    train.write_text("balanced\n", encoding="utf-8")
    exclusion = tmp_path / "exclusion.json"
    balance = tmp_path / "balance.json"
    _write(
        exclusion,
        {
            "output": str(unbalanced),
            "output_sha256": _sha256(unbalanced),
            "retained_exclusion_overlap": 0,
            "retained_decks": 1720,
        },
    )
    _write(
        balance,
        {
            "source": str(unbalanced),
            "source_sha256": _sha256(unbalanced),
            "output": str(train),
            "output_sha256": _sha256(train),
            "decks": 1720,
            "signature_changes": 0,
            "before": {"maximum_to_minimum_ratio": 20.0},
            "after": {"maximum_to_minimum_ratio": 5.0},
        },
    )

    _write(root / "parent_strategy.json", _strategy(parent, pfsp_decks))
    _write(root / "candidate_strategy.json", _strategy(candidate, pfsp_decks))
    pfsp_exclusion = tmp_path / "pfsp_exclusion.json"
    _write(
        pfsp_exclusion,
        {
            "output": str(pfsp_decks),
            "output_sha256": _sha256(pfsp_decks),
            "retained_exclusion_overlap": 0,
            "retained_decks": 308,
        },
    )
    _write(
        root / "training_stability.json",
        {
            "passes": True,
            "start_update": 1,
            "end_update": 4,
            "updates": 4,
            "transition_delta": 16_384,
            "parent": str(parent),
        },
    )
    _write(
        root / "state_dict_audit.json",
        {
            "passes": True,
            "actor_changed_parameter_count": 1,
            "value_changed_parameter_count": 1,
            "unauthorized_changes": [],
            "actor_prefixes": [
                "action_type_head.",
                "mechanics_slot_choice_query.",
            ],
            "value_prefixes": ["critic_encoder.", "value_head."],
            "before": str(parent),
            "after": str(candidate),
        },
    )
    for split, decks, seed in (
        ("validation", validation, 1056301),
        ("heldout", heldout, 1056302),
    ):
        _write(
            root / f"direct_{split}12.metrics.json",
            _eval(
                checkpoint=candidate,
                opponent=parent,
                decks=decks,
                games=12,
                seed=seed,
                mode="policy",
                strategy=None,
                metrics={"wins": 7, "losses": 5, "crown_diff_per_game": 0.1},
            ),
        )
        _write(root / f"direct_{split}12.games.json", {"games": []})

    defense_parent = {
        "games": 12,
        "defense_event_success_rate": 0.4,
        "defense_event_mean_outcome": -0.05,
        "defense_events_resolved": 20,
        "candidate_noop_when_playable": 0.75,
    }
    defense_candidate = {
        **defense_parent,
        "defense_event_success_rate": 0.43,
        "defense_event_mean_outcome": -0.045,
    }
    hog_game_records = [
        {
            "game": game,
            "candidate_player": game % 2,
            "candidate_deck": [
                "HogRider",
                "IceSpirit",
                "Skeletons",
                "Fireball",
                "Musketeer",
                "Log",
                "Cannon",
                "IceGolem",
            ],
        }
        for game in range(12)
    ]
    hog_decision_records = []
    for game in range(12):
        for slot in range(4):
            hand = ["IceSpirit", "Skeletons", "Fireball", "Musketeer"]
            hand[slot] = "HogRider"
            probabilities = [0.0] * 6
            probabilities[slot] = 1.0
            hog_decision_records.append(
                {
                    "game": game,
                    "game_decision": slot,
                    "hand": hand,
                    "elixir": 10.0,
                    "action_type_probabilities": probabilities,
                    "is_no_op": False,
                    "is_ability": False,
                    "slot": slot,
                }
            )
    for name in PAIRED_WORKLOADS:
        games, seed, mode, strategy, deck_group = PAIRED_SPECS[name]
        decks = hog if deck_group == "hog" else heldout
        baseline_games = initializer / f"candidate_{name}.games.json"
        candidate_games = root / f"candidate_{name}.games.json"
        game_payload: object = hog_game_records if name == "hog12" else {"games": []}
        _write(baseline_games, game_payload)
        _write(candidate_games, game_payload)
        _write(
            initializer / f"candidate_{name}.metrics.json",
            {
                "metrics": defense_parent
                if name in {"balanced12", "reactive12"}
                else {"games": games, "candidate_noop_when_playable": 0.75}
            },
        )
        _write(
            root / f"candidate_{name}.metrics.json",
            _eval(
                checkpoint=candidate,
                opponent=None,
                decks=decks,
                games=games,
                seed=seed,
                mode=mode,
                strategy=strategy,
                metrics=(
                    defense_candidate if name in {"balanced12", "reactive12"} else {}
                ),
            ),
        )
        _write(
            root / f"{name}.compare.json",
            {
                "schema_version": 1,
                "baseline": str(baseline_games),
                "baseline_sha256": _sha256(baseline_games),
                "candidate": str(candidate_games),
                "candidate_sha256": _sha256(candidate_games),
                "games": games,
                "improvements": [],
                "regressions": [],
                "improvement_count": 0,
                "regression_count": 0,
                "unchanged_count": games,
                "baseline_crown_difference": 0.0,
                "candidate_crown_difference": 0.0,
                "passes_strict_no_regression": True,
                "crown_difference_change": 0.0,
            },
        )
    parent_decisions = initializer / "candidate_hog12.decisions.json"
    parent_games = initializer / "candidate_hog12.games.json"
    candidate_decisions = root / "candidate_hog12.decisions.json"
    candidate_games = root / "candidate_hog12.games.json"
    _write(parent_decisions, hog_decision_records)
    _write(candidate_decisions, hog_decision_records)
    _write_utilization(
        parent_decisions,
        parent_games,
        initializer / "candidate_hog12.utilization.json",
    )
    _write_utilization(
        candidate_decisions,
        candidate_games,
        root / "candidate_hog12.utilization.json",
    )
    win_condition_root = root / "win_condition_matrix"
    _write_win_condition_matrix_evidence(
        root=win_condition_root,
        manifest_path=win_condition_manifest,
        parent=parent,
        candidate=candidate,
    )

    human_splits = {}
    for name in ("validation", "archetype", "chronology"):
        corpus = tmp_path / f"human_{name}.npz"
        sidecar = tmp_path / f"human_{name}_sidecar.npz"
        corpus.write_bytes(name.encode())
        sidecar.write_bytes(f"{name}-sidecar".encode())
        human_splits[name] = (corpus, sidecar)
        common = {
            "action_type_improvements_vs_first": 0,
            "action_type_regressions_vs_first": 0,
            "exact_improvements_vs_first": 0,
            "exact_regressions_vs_first": 0,
        }
        _write(
            root / f"human_{name}.json",
            {
                "schema_version": 1,
                "corpus": str(corpus),
                "corpus_sha256": _sha256(corpus),
                "public_observation_sidecar": str(sidecar),
                "public_observation_sidecar_sha256": _sha256(sidecar),
                "results": [
                    {
                        "checkpoint": str(parent),
                        "checkpoint_sha256": _sha256(parent),
                        **common,
                    },
                    {
                        "checkpoint": str(candidate),
                        "checkpoint_sha256": _sha256(candidate),
                        **common,
                    },
                ],
            },
        )
    initializer_summary = json.loads(
        (initializer / "summary.json").read_text(encoding="utf-8")
    )
    initializer_summary["evidence_sha256"] = {
        str(path.resolve()): _sha256(path)
        for path in initializer.iterdir()
        if path.is_file() and path.name != "summary.json"
    }
    _write(initializer / "summary.json", initializer_summary)
    return {
        "root": root,
        "initializer_root": initializer,
        "parent": parent,
        "candidate": candidate,
        "train_pool": train,
        "balance_report": balance,
        "exclusion_manifest": exclusion,
        "pfsp_sampling_decks": pfsp_decks,
        "pfsp_exclusion_manifest": pfsp_exclusion,
        "validation_decks": validation,
        "heldout_decks": heldout,
        "hog_decks": hog,
        "win_condition_root": win_condition_root,
        "win_condition_manifest": win_condition_manifest,
        "human_splits": human_splits,
    }


def test_pfsp_finalizer_accepts_complete_improving_evidence(tmp_path: Path) -> None:
    inputs = _fixture(tmp_path)

    result = finalize_pfsp_pilot(**inputs)

    assert result["development_candidate_eligible"]
    assert all(result["gates"].values())
    assert result["direct"]["games"] == 24
    assert "not a champion" in result["claim_scope"]


def test_pfsp_finalizer_accepts_four_updates_from_nonzero_parent(
    tmp_path: Path,
) -> None:
    inputs = _fixture(tmp_path)
    stability_path = inputs["root"] / "training_stability.json"
    stability = json.loads(stability_path.read_text(encoding="utf-8"))
    stability.update({"start_update": 29, "end_update": 32, "updates": 4})
    _write(stability_path, stability)

    result = finalize_pfsp_pilot(
        **inputs,
        start_update=28,
        end_update=32,
    )

    assert result["development_candidate_eligible"]
    assert result["training_interval"] == {
        "parent_update": 28,
        "candidate_update": 32,
        "updates": 4,
        "expected_transitions": 16_384,
        "actor_prefixes": [
            "action_type_head.",
            "mechanics_slot_choice_query.",
        ],
    }


def test_pfsp_finalizer_accepts_mechanics_only_actor_changes(tmp_path: Path) -> None:
    inputs = _fixture(tmp_path)
    audit_path = inputs["root"] / "state_dict_audit.json"
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    audit["actor_prefixes"] = ["mechanics_slot_choice_query."]
    _write(audit_path, audit)

    result = finalize_pfsp_pilot(
        **inputs,
        expected_actor_prefixes=("mechanics_slot_choice_query.",),
    )

    assert result["development_candidate_eligible"]
    assert result["training_interval"]["actor_prefixes"] == [
        "mechanics_slot_choice_query."
    ]


def test_pfsp_finalizer_rejects_hog_slot_collapse_hidden_by_aggregate(
    tmp_path: Path,
) -> None:
    inputs = _fixture(tmp_path)
    decisions_path = inputs["root"] / "candidate_hog12.decisions.json"
    decisions = json.loads(decisions_path.read_text(encoding="utf-8"))
    for row in decisions:
        if row["hand"][0] == "HogRider":
            row["slot"] = 1
            row["action_type_probabilities"] = [0.0, 1.0, 0.0, 0.0, 0.0, 0.0]
    _write(decisions_path, decisions)
    _write_utilization(
        decisions_path,
        inputs["root"] / "candidate_hog12.games.json",
        inputs["root"] / "candidate_hog12.utilization.json",
    )

    result = finalize_pfsp_pilot(**inputs)

    assert not result["development_candidate_eligible"]
    assert not result["gates"]["hog_each_slot_coverage"]
    assert result["gates"]["hog_absolute_gate"]


def test_pfsp_finalizer_rejects_edited_hog_utilization_arithmetic(
    tmp_path: Path,
) -> None:
    inputs = _fixture(tmp_path)
    utilization_path = inputs["root"] / "candidate_hog12.utilization.json"
    utilization = json.loads(utilization_path.read_text(encoding="utf-8"))
    utilization["window_conversion_rate"] = 0.99
    _write(utilization_path, utilization)

    with pytest.raises(ValueError, match="does not match its decision records"):
        finalize_pfsp_pilot(**inputs)


def test_pfsp_finalizer_rejects_one_win_condition_collapse(
    tmp_path: Path,
) -> None:
    inputs = _fixture(tmp_path)
    root = inputs["win_condition_root"]
    decisions_path = root / "candidate_balloon2.decisions.json"
    decisions = json.loads(decisions_path.read_text(encoding="utf-8"))
    for row in decisions:
        row["slot"] = None
        row["is_no_op"] = True
        row["action_type_probabilities"] = [0.0, 0.0, 0.0, 0.0, 1.0, 0.0]
    _write(decisions_path, decisions)
    _write_designated_utilization(
        decisions_path,
        root / "candidate_balloon2.games.json",
        root / "candidate_balloon2.utilization.json",
        card="Balloon",
    )

    result = finalize_pfsp_pilot(**inputs)

    assert not result["development_candidate_eligible"]
    assert not result["gates"]["win_condition_matrix"]
    assert not result["win_condition_matrix"]["archetypes"]["balloon"]["passes"]


def test_pfsp_finalizer_rejects_missing_defense_improvement(tmp_path: Path) -> None:
    inputs = _fixture(tmp_path)
    path = inputs["root"] / "candidate_balanced12.metrics.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["metrics"]["defense_event_success_rate"] = 0.4
    _write(path, payload)
    path = inputs["root"] / "candidate_reactive12.metrics.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["metrics"]["defense_event_success_rate"] = 0.4
    _write(path, payload)

    result = finalize_pfsp_pilot(**inputs)

    assert not result["development_candidate_eligible"]
    assert not result["gates"]["defense_success_improvement"]


def test_pfsp_finalizer_rejects_game_records_changed_after_comparison(
    tmp_path: Path,
) -> None:
    inputs = _fixture(tmp_path)
    (inputs["root"] / "candidate_balanced12.games.json").write_text(
        '{"games":[{"outcome":"loss"}]}', encoding="utf-8"
    )

    with pytest.raises(ValueError, match="candidate_sha256"):
        finalize_pfsp_pilot(**inputs)


def test_pfsp_finalizer_rejects_heldout_direct_collapse_hidden_by_aggregate(
    tmp_path: Path,
) -> None:
    inputs = _fixture(tmp_path)
    validation_path = inputs["root"] / "direct_validation12.metrics.json"
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    validation["metrics"].update(
        {"wins": 12, "losses": 0, "draws": 0, "crown_diff_per_game": 1.0}
    )
    _write(validation_path, validation)
    heldout_path = inputs["root"] / "direct_heldout12.metrics.json"
    heldout = json.loads(heldout_path.read_text(encoding="utf-8"))
    heldout["metrics"].update(
        {"wins": 1, "losses": 11, "draws": 0, "crown_diff_per_game": -1.0}
    )
    _write(heldout_path, heldout)

    result = finalize_pfsp_pilot(**inputs)

    assert result["gates"]["direct_parent_improvement"]
    assert not result["gates"]["direct_each_split_no_regression"]
    assert not result["development_candidate_eligible"]


def test_pfsp_finalizer_rejects_one_strategy_regression_hidden_by_aggregates(
    tmp_path: Path,
) -> None:
    inputs = _fixture(tmp_path)
    parent_path = inputs["root"] / "parent_strategy.json"
    parent = json.loads(parent_path.read_text(encoding="utf-8"))
    parent["results"]["balanced"]["score_rate"] = 0.8
    parent["results"]["bridge-pressure"]["score_rate"] = 0.2
    _write(parent_path, parent)
    candidate_path = inputs["root"] / "candidate_strategy.json"
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    candidate["results"]["balanced"]["score_rate"] = 0.7
    candidate["results"]["bridge-pressure"]["score_rate"] = 0.3
    _write(candidate_path, candidate)

    result = finalize_pfsp_pilot(**inputs)

    assert result["gates"]["strategy_mean_no_regression"]
    assert result["gates"]["strategy_worst_no_regression"]
    assert not result["gates"]["strategy_each_no_regression"]
    assert not result["development_candidate_eligible"]


def test_pfsp_finalizer_rejects_passivity_regression_in_one_workload(
    tmp_path: Path,
) -> None:
    inputs = _fixture(tmp_path)
    path = inputs["root"] / "candidate_spell6.metrics.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["metrics"]["candidate_noop_when_playable"] = 0.78
    _write(path, payload)

    result = finalize_pfsp_pilot(**inputs)

    assert result["gates"]["passivity_no_regression"]
    assert not result["gates"]["passivity_each_workload_no_regression"]
    assert not result["development_candidate_eligible"]
