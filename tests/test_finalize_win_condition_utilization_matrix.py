from __future__ import annotations

import json
from pathlib import Path

from scripts.build_win_condition_utilization_matrix import WIN_CONDITION_SPECS
from scripts.evaluate_win_condition_utilization import (
    promotion_gate,
    summarize_utilization,
)
from scripts.finalize_mechanics_slot_gameplay_gate import _sha256
from scripts.finalize_win_condition_utilization_matrix import (
    finalize_win_condition_matrix,
)


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _metrics(
    checkpoint: Path,
    decks: Path,
    *,
    seed: int,
) -> dict:
    return {
        "schema_version": 1,
        "checkpoint": str(checkpoint),
        "checkpoint_sha256": _sha256(checkpoint),
        "opponent_checkpoint": None,
        "opponent_checkpoint_sha256": None,
        "sampling_decks_path": str(decks),
        "sampling_decks_sha256": _sha256(decks),
        "seed": seed,
        "mirror_match": True,
        "opponent_mode": "strategy",
        "opponent_strategy": "balanced",
        "reward_profile": "defense-v2",
        "metrics": {
            "games": 2,
            "wins": 1,
            "losses": 1,
            "draws": 0,
            "crown_diff_per_game": 0.0,
        },
    }


def _write_utilization(
    decisions_path: Path,
    games_path: Path,
    output: Path,
    *,
    card: str,
) -> None:
    decisions = json.loads(decisions_path.read_text(encoding="utf-8"))
    games = json.loads(games_path.read_text(encoding="utf-8"))
    payload = summarize_utilization(
        decisions,
        games,
        role="designated_win_condition",
        designated_cards={card},
    )
    payload["gate"] = promotion_gate(
        payload,
        max_zero_use_rate=0.0,
        min_window_conversion_rate=0.25,
        min_games_per_seat=1,
    )
    payload.update(
        {
            "decisions": str(decisions_path.resolve()),
            "decisions_sha256": _sha256(decisions_path),
            "game_records": str(games_path.resolve()),
            "game_records_sha256": _sha256(games_path),
        }
    )
    _write(output, payload)


def _fixture(tmp_path: Path) -> dict:
    validation = tmp_path / "validation.json"
    heldout = tmp_path / "heldout.json"
    parent = tmp_path / "parent.pt"
    candidate = tmp_path / "candidate.pt"
    root = tmp_path / "evidence"
    parent.write_bytes(b"parent")
    candidate.write_bytes(b"candidate")
    source_decks: dict[str, list[dict[str, object]]] = {
        "validation": [],
        "heldout": [],
    }
    entries = []
    for index, spec in enumerate(WIN_CONDITION_SPECS):
        cards = [
            spec.card,
            "Musketeer",
            "Skeletons",
            "IceSpirit",
            "Fireball",
            "Log",
            "Cannon",
            "Knight",
        ]
        selected = {
            "name": f"{spec.archetype}-source",
            "source": "project-base",
            "substitutions": 0,
            "archetype": spec.archetype,
            "cards": cards,
        }
        source_decks[spec.source].append(selected)
        pool = tmp_path / "matrix" / f"{spec.archetype.replace('-', '_')}.json"
        _write(
            pool,
            {
                "schema_version": 1,
                "metadata": {
                    "purpose": "win_condition_utilization_evaluation",
                    "archetype": spec.archetype,
                    "designated_card": spec.card,
                    "source_pool": spec.source,
                },
                "decks": [{**selected, "sampling_weight": 1.0}],
            },
        )
        entries.append(
            {
                "archetype": spec.archetype,
                "designated_card": spec.card,
                "source_pool": spec.source,
                "source_deck": selected["name"],
                "signature": sorted(cards),
                "deck_pool": str(pool),
                "deck_pool_sha256": _sha256(pool),
            }
        )
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
                "action_type_probabilities": [1.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            }
            for game in range(2)
        ]
        for role, checkpoint in (("parent", parent), ("candidate", candidate)):
            metrics_path = root / f"{role}_{tag}2.metrics.json"
            games_path = root / f"{role}_{tag}2.games.json"
            decisions_path = root / f"{role}_{tag}2.decisions.json"
            _write(metrics_path, _metrics(checkpoint, pool, seed=seed))
            _write(games_path, games)
            _write(decisions_path, decisions)
            _write_utilization(
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
    _write(validation, {"decks": source_decks["validation"]})
    _write(heldout, {"decks": source_decks["heldout"]})
    manifest = tmp_path / "matrix" / "manifest.json"
    _write(
        manifest,
        {
            "schema": "clasher-win-condition-utilization-matrix-v1",
            "validation_pool": str(validation),
            "validation_pool_sha256": _sha256(validation),
            "heldout_pool": str(heldout),
            "heldout_pool_sha256": _sha256(heldout),
            "entries": entries,
        },
    )
    return {
        "root": root,
        "manifest_path": manifest,
        "validation_pool": validation,
        "heldout_pool": heldout,
        "parent": parent,
        "candidate": candidate,
    }


def test_matrix_finalizer_accepts_every_designated_card(tmp_path: Path) -> None:
    inputs = _fixture(tmp_path)

    result = finalize_win_condition_matrix(**inputs)

    assert result["passes"]
    assert len(result["archetypes"]) == 12
    assert all(row["passes"] for row in result["archetypes"].values())


def test_matrix_finalizer_rejects_one_card_hidden_by_other_archetypes(
    tmp_path: Path,
) -> None:
    inputs = _fixture(tmp_path)
    root = inputs["root"]
    decisions_path = root / "candidate_balloon2.decisions.json"
    decisions = json.loads(decisions_path.read_text(encoding="utf-8"))
    for row in decisions:
        row["slot"] = None
        row["is_no_op"] = True
        row["action_type_probabilities"] = [0.0, 0.0, 0.0, 0.0, 1.0, 0.0]
    _write(decisions_path, decisions)
    _write_utilization(
        decisions_path,
        root / "candidate_balloon2.games.json",
        root / "candidate_balloon2.utilization.json",
        card="Balloon",
    )

    result = finalize_win_condition_matrix(**inputs)

    assert not result["passes"]
    assert not result["archetypes"]["balloon"]["passes"]
    assert all(
        row["passes"]
        for name, row in result["archetypes"].items()
        if name != "balloon"
    )


def test_matrix_finalizer_accepts_candidate_use_when_parent_has_no_windows(
    tmp_path: Path,
) -> None:
    inputs = _fixture(tmp_path)
    root = inputs["root"]
    decisions_path = root / "parent_balloon2.decisions.json"
    decisions = json.loads(decisions_path.read_text(encoding="utf-8"))
    for row in decisions:
        row["elixir"] = 0.0
        row["slot"] = None
        row["is_no_op"] = True
        row["action_type_probabilities"] = [0.0, 0.0, 0.0, 0.0, 1.0, 0.0]
    _write(decisions_path, decisions)
    _write_utilization(
        decisions_path,
        root / "parent_balloon2.games.json",
        root / "parent_balloon2.utilization.json",
        card="Balloon",
    )

    result = finalize_win_condition_matrix(**inputs)

    assert result["passes"]
    assert result["archetypes"]["balloon"]["gates"]["conversion_no_regression"]
    assert result["archetypes"]["balloon"]["gates"]["probability_no_regression"]


def test_matrix_finalizer_rejects_edited_utilization_summary(tmp_path: Path) -> None:
    inputs = _fixture(tmp_path)
    path = inputs["root"] / "candidate_x_bow2.utilization.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["plays"] = 99
    _write(path, payload)

    try:
        finalize_win_condition_matrix(**inputs)
    except ValueError as error:
        assert "does not match its decision records" in str(error)
    else:
        raise AssertionError("edited utilization summary was accepted")


def test_matrix_finalizer_rejects_easier_deck_substituted_after_selection(
    tmp_path: Path,
) -> None:
    inputs = _fixture(tmp_path)
    manifest = json.loads(inputs["manifest_path"].read_text(encoding="utf-8"))
    entry = manifest["entries"][0]
    deck_pool = Path(entry["deck_pool"])
    pool = json.loads(deck_pool.read_text(encoding="utf-8"))
    pool["decks"][0]["cards"][-1] = "Archers"
    _write(deck_pool, pool)
    entry["signature"] = sorted(pool["decks"][0]["cards"])
    entry["deck_pool_sha256"] = _sha256(deck_pool)
    _write(inputs["manifest_path"], manifest)

    try:
        finalize_win_condition_matrix(**inputs)
    except ValueError as error:
        assert "deck provenance changed" in str(error)
    else:
        raise AssertionError("substituted matrix deck was accepted")
