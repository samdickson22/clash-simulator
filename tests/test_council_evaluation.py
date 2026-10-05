"""Synthetic outcomes verify prospective statistics and result ownership only."""

import json
from pathlib import Path

import numpy as np
import pytest

from clasher.rl.council_evaluation import (
    GameRecord,
    build_protocol,
    clustered_interval,
    evaluate_recipe,
    load_protocol,
    record_completion,
    result_binding,
    roster_key,
    score_paired_games,
    validated_completion,
)
from clasher.rl.council_pilot import load_pilot_config


@pytest.fixture(scope="module")
def protocol():
    return build_protocol(load_pilot_config(Path("configs/council-pilot-local.toml")))


def pairs(protocol):
    by_family = {}
    for roster, family in protocol.family_by_roster.items():
        by_family.setdefault(family, roster.split("|"))
    families = list(by_family)
    rows = []
    for cell in protocol.cells:
        if cell.purpose != "final":
            continue
        candidate_decks = json.loads(Path(cell.candidate_decks_path).read_text())[
            "decks"
        ]
        opponent_deck = json.loads(Path(cell.opponent_decks_path).read_text())["decks"][
            0
        ]["cards"]
        for game in range(cell.games):
            cards = (
                by_family[families[(game // 2) % len(families)]]
                if cell.role == "holdout"
                else candidate_decks[0]["cards"]
            )
            own = 10 if cell.level_mode == "mixed" and game % 2 == 0 else 11
            enemy = 12 if cell.level_mode == "mixed" and game % 2 == 0 else 11
            common = {
                "game": game,
                "matchup": game // 2,
                "matchup_seed": cell.seed + (game // 2) * 1009,
                "candidate_player": game % 2,
                "terminated": True,
                "truncated": False,
                "ticks": 6001,
                "candidate_deck": cards,
                "opponent_deck": opponent_deck,
                "level_mode": cell.level_mode,
                "candidate_card_levels": {name: own for name in cards},
                "opponent_card_levels": {name: enemy for name in opponent_deck},
                "candidate_tower_level": own,
                "opponent_tower_level": enemy,
            }
            rows.append(
                (
                    cell,
                    GameRecord(**common, outcome="draw"),
                    GameRecord(**common, outcome="win"),
                )
            )
    return rows


def test_protocol_frozen_before_outcomes_has_independent_seeds_and_broad_slices(
    protocol,
):
    frozen = load_protocol(
        Path("reports/strategy_council_20260928/pilot/evaluation-protocol.json")
    )
    assert frozen == protocol
    final = [cell for cell in protocol.cells if cell.purpose == "final"]
    assert len(final) == 12 and len({cell.seed for cell in final}) == 12
    assert sum(cell.games for cell in final if cell.role == "holdout") == 516
    assert protocol.collapse_margin == 0.10
    assert len(protocol.required_slices) == 9
    final_seeds = {
        cell.seed + 1009 * m for cell in final for m in range(cell.games // 2)
    }
    diagnostic = [cell for cell in protocol.cells if cell.purpose == "diagnostic"]
    assert len(diagnostic) == 6
    assert not final_seeds & {
        cell.seed + 1009 * m for cell in diagnostic for m in range(cell.games // 2)
    }
    assert all("/m0/data/roles_v2/" in cell.opponent_decks_path for cell in protocol.cells)
    assert all(
        "/m0/data/roles_v2/" in cell.candidate_decks_path
        for cell in protocol.cells
        if cell.role == "holdout"
    )


def test_cluster_bootstrap_does_not_count_two_seats_as_independent():
    values = np.array([0, 0, 1, 1], dtype=float)
    grouped = clustered_interval(values, ["a", "a", "b", "b"], repetitions=5000, seed=1)
    independent = clustered_interval(
        np.repeat(values, 100), [str(i) for i in range(400)], repetitions=5000, seed=1
    )
    duplicated = clustered_interval(
        np.repeat(values, 100), ["a"] * 200 + ["b"] * 200, repetitions=5000, seed=1
    )
    assert grouped["ci95"] == duplicated["ci95"] == [0, 1]
    assert independent["ci95"][1] - independent["ci95"][0] < 0.2
    assert grouped["clusters"] == 2 and duplicated["clusters"] == 2


def test_gain_and_relative_slice_rules_qualify_strength_but_never_promote(protocol):
    result = score_paired_games(protocol, pairs(protocol))
    assert result["strength_qualified"]
    assert result["gain"]["mean"] == 0.5 and result["gain"]["ci95"] == [0.5, 0.5]
    assert result["gain"]["games"] == 516 and result["gain"]["clusters"] == 258
    assert result["tier_b_required"] and not result["promotion_authorized"]


def test_disadvantaged_slice_has_no_arbitrary_absolute_win_floor(protocol):
    modified = []
    for cell, initial, candidate in pairs(protocol):
        if (
            cell.role == "holdout"
            and cell.level_mode == "mixed"
            and candidate.candidate_player == 0
        ):
            initial = initial.model_copy(update={"outcome": "loss"})
            candidate = candidate.model_copy(update={"outcome": "loss"})
        modified.append((cell, initial, candidate))
    result = score_paired_games(protocol, modified)
    group = result["subgroups"]["heldout/mixed/disadvantaged"]
    assert (
        group["candidate_score"] == 0 and group["status"] == "noninferiority_supported"
    )
    assert result["strength_qualified"]


def test_heldout_family_collapse_blocks_otherwise_strong_candidate(protocol):
    target = sorted(set(protocol.family_by_roster.values()))[0]
    modified = []
    for cell, initial, candidate in pairs(protocol):
        if (
            cell.role == "holdout"
            and protocol.family_by_roster[roster_key(candidate.candidate_deck)]
            == target
        ):
            initial = initial.model_copy(update={"outcome": "win"})
            candidate = candidate.model_copy(update={"outcome": "loss"})
        modified.append((cell, initial, candidate))
    result = score_paired_games(protocol, modified)
    assert result["gain"]["mean"] > 0.05 and result["candidate_score"]["mean"] > 0.5
    assert not result["strength_qualified"]
    assert (
        result["subgroups"]["heldout/family/" + target]["status"] == "material_collapse"
    )


def test_exact_pair_identity_and_complete_matrix_are_required(protocol):
    rows = pairs(protocol)
    with pytest.raises(ValueError, match="incomplete"):
        score_paired_games(protocol, rows[:-1])
    cell, initial, candidate = rows[0]
    rows[0] = (
        cell,
        initial,
        candidate.model_copy(update={"matchup_seed": candidate.matchup_seed + 1}),
    )
    with pytest.raises(ValueError, match="exact frozen case"):
        score_paired_games(protocol, rows)


def write_cell(tmp_path, protocol):
    cell = next(
        cell
        for cell in protocol.cells
        if cell.purpose == "final"
        and cell.role == "hog26"
        and cell.level_mode == "nominal"
    )
    checkpoint = tmp_path / "candidate.pt"
    checkpoint.write_bytes(b"synthetic checkpoint identity")
    binding = result_binding(
        protocol,
        cell,
        checkpoint=checkpoint,
        seed=protocol.seeds[0],
        arm="scratch",
        policy_role="candidate",
    )
    records = [candidate for item, _, candidate in pairs(protocol) if item == cell]
    summary = {
        "checkpoint_sha256": binding["checkpoint_sha256"],
        "gamedata_sha256": protocol.gamedata_sha256,
        "checkpoint_gamedata_sha256": protocol.gamedata_sha256,
        "checkpoint_training_seed": protocol.seeds[0],
        "model_config_sha256": protocol.model_config_sha256,
        "opponent_mode": "public-script",
        "public_script_style": cell.style,
        "level_mode": cell.level_mode,
        "candidate_sampling_decks_sha256": cell.candidate_decks_sha256,
        "opponent_sampling_decks_sha256": cell.opponent_decks_sha256,
        "seed": cell.seed,
        "deterministic": False,
        "decision_interval_ticks": 5,
        "max_ticks": 6001,
        "public_contract_version": 4,
        "sampling_temperature": 1.0,
        "candidate_defense_strategy": None,
        "location_lookahead": None,
        "metrics": {"games": cell.games, "score_rate": 1.0},
    }
    summary_path = tmp_path / "candidate.json"
    games_path = tmp_path / "candidate.games.json"
    summary_path.write_text(json.dumps(summary))
    games_path.write_text(json.dumps([record.model_dump() for record in records]))
    return cell, binding, summary_path, games_path


def test_resume_skips_only_completed_exact_bound_results(tmp_path, protocol):
    cell, binding, summary, games = write_cell(tmp_path, protocol)
    with pytest.raises(ValueError, match="uncommitted"):
        validated_completion(
            protocol, cell, summary_path=summary, games_path=games, binding=binding
        )
    record_completion(
        protocol, cell, summary_path=summary, games_path=games, binding=binding
    )
    assert validated_completion(
        protocol, cell, summary_path=summary, games_path=games, binding=binding
    )
    altered = binding | {"training_seed": protocol.seeds[1]}
    with pytest.raises(ValueError, match="changed"):
        validated_completion(
            protocol, cell, summary_path=summary, games_path=games, binding=altered
        )
    data = json.loads(games.read_text())
    data[0]["outcome"] = "loss"
    games.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="changed"):
        validated_completion(
            protocol, cell, summary_path=summary, games_path=games, binding=binding
        )


def test_recipe_requires_two_of_three_distinct_declared_seeds(
    tmp_path, protocol, monkeypatch
):
    import clasher.rl.council_evaluation as module

    path = tmp_path / "protocol.json"
    path.write_text(protocol.model_dump_json())
    reports = []
    paths = []
    for index, seed in enumerate(protocol.seeds):
        report = {
            "arm": "scratch",
            "protocol_sha256": protocol.sha256,
            "evaluation_dir": str(tmp_path / f"seed-{seed}"),
            "seed": seed,
            "candidate_sha256": str(index) * 64,
            "strength_qualified": index < 2,
        }
        reports.append(report)
        target = tmp_path / f"{seed}.json"
        target.write_text(json.dumps(report))
        paths.append(target)
    monkeypatch.setattr(
        module,
        "evaluate_seed",
        lambda protocol_path, evaluation_dir, seed, arm: reports[
            protocol.seeds.index(seed)
        ],
    )
    result = evaluate_recipe(path, paths, arm="scratch")
    assert result["qualified_seeds"] == 2 and result["reproducible_strength"]
    assert result["tier_b_required"] and not result["promotion_authorized"]
    with pytest.raises(ValueError, match="exactly all three"):
        evaluate_recipe(path, paths[:2], arm="scratch")
    reports[1]["candidate_sha256"] = reports[0]["candidate_sha256"]
    paths[1].write_text(json.dumps(reports[1]))
    with pytest.raises(ValueError, match="independent training"):
        evaluate_recipe(path, paths, arm="scratch")


# --- Negative rules: every non-pass path must block qualification. ---


def _holdout_clusters(rows):
    order = {}
    for cell, _, candidate in rows:
        if cell.role == "holdout":
            order.setdefault(candidate.matchup_seed, len(order))
    return order


def _set(rows, predicate, initial_outcome, candidate_outcome):
    modified = []
    for cell, initial, candidate in rows:
        if predicate(cell, candidate):
            initial = initial.model_copy(update={"outcome": initial_outcome})
            candidate = candidate.model_copy(update={"outcome": candidate_outcome})
        modified.append((cell, initial, candidate))
    return modified


def _flatten_mixed_levels(rows, keep):
    """Equalize mixed levels except for ``keep`` disadvantaged holdout games."""
    modified, kept = [], 0
    for cell, initial, candidate in rows:
        disadvantaged = (
            cell.role == "holdout"
            and cell.level_mode == "mixed"
            and candidate.candidate_tower_level == 10
        )
        if disadvantaged and kept < keep and candidate.matchup % 2 == 0:
            kept += 1
        elif cell.level_mode == "mixed":
            update = {
                "candidate_card_levels": {k: 11 for k in candidate.candidate_deck},
                "opponent_card_levels": {k: 11 for k in candidate.opponent_deck},
                "candidate_tower_level": 11,
                "opponent_tower_level": 11,
            }
            initial = initial.model_copy(update=update)
            candidate = candidate.model_copy(update=update)
        modified.append((cell, initial, candidate))
    return modified, kept


@pytest.mark.parametrize("keep", [0, 19])
def test_insufficient_subgroup_samples_block_instead_of_passing(protocol, keep):
    rows, kept = _flatten_mixed_levels(pairs(protocol), keep)
    assert kept == keep
    result = score_paired_games(protocol, rows)
    group = result["subgroups"]["heldout/mixed/disadvantaged"]
    assert group["status"] == "insufficient_coverage"
    assert group["games"] == keep and group["games"] < protocol.minimum_slice_games
    # Everything else is overwhelmingly positive; coverage alone must block.
    assert result["improved_over_initialization"] and result["beats_fixed_script_pool"]
    assert not result["subgroups_clear"] and not result["strength_qualified"]
    assert result["status"] == "strength_not_qualified"


def test_family_slice_below_cluster_minimum_is_insufficient(protocol):
    # Nineteen paired matchups (38 seat games) sit just below both minimums.
    rows = pairs(protocol)
    target = sorted(set(protocol.family_by_roster.values()))[0]
    by_cluster = {}
    trimmed = []
    for cell, initial, candidate in rows:
        family = (
            protocol.family_by_roster[roster_key(candidate.candidate_deck)]
            if cell.role == "holdout"
            else None
        )
        if family == target:
            by_cluster.setdefault(candidate.matchup_seed, len(by_cluster))
            if by_cluster[candidate.matchup_seed] >= 19:
                # Reassign surplus games to another family's roster.
                other = next(
                    r.split("|")
                    for r, f in protocol.family_by_roster.items()
                    if f != target
                )
                initial = initial.model_copy(update={"candidate_deck": other,
                    "candidate_card_levels": {k: initial.candidate_tower_level for k in other}})
                candidate = candidate.model_copy(update={"candidate_deck": other,
                    "candidate_card_levels": {k: candidate.candidate_tower_level for k in other}})
        trimmed.append((cell, initial, candidate))
    group = score_paired_games(protocol, trimmed)["subgroups"][
        "heldout/family/" + target
    ]
    assert group["status"] == "insufficient_coverage"
    assert group["clusters"] == 19 and group["games"] == 38


def test_inconclusive_subgroup_blocks_strength(protocol):
    rows = pairs(protocol)
    target = sorted(set(protocol.family_by_roster.values()))[1]
    clusters = {}
    modified = []
    for cell, initial, candidate in rows:
        if (
            cell.role == "holdout"
            and protocol.family_by_roster[roster_key(candidate.candidate_deck)]
            == target
        ):
            index = clusters.setdefault(candidate.matchup_seed, len(clusters))
            good = index % 2 == 0
            initial = initial.model_copy(update={"outcome": "loss" if good else "win"})
            candidate = candidate.model_copy(
                update={"outcome": "win" if good else "loss"}
            )
        modified.append((cell, initial, candidate))
    result = score_paired_games(protocol, modified)
    group = result["subgroups"]["heldout/family/" + target]
    assert group["status"] == "inconclusive"
    assert group["ci95"][0] <= -protocol.collapse_margin < group["mean"]
    assert result["improved_over_initialization"] and not result["strength_qualified"]


def test_overall_score_must_exceed_half_against_scripts(protocol):
    rows = _set(
        pairs(protocol), lambda cell, _: cell.role == "holdout", "loss", "draw"
    )
    result = score_paired_games(protocol, rows)
    assert result["gain"]["mean"] == 0.5 and result["improved_over_initialization"]
    assert result["candidate_score"]["mean"] == 0.5
    assert not result["beats_fixed_script_pool"] and not result["strength_qualified"]


def test_gain_below_five_points_blocks_even_with_positive_interval(protocol):
    rows = pairs(protocol)
    order = _holdout_clusters(rows)
    rows = _set(rows, lambda cell, c: cell.role == "holdout", "win", "win")
    rows = _set(
        rows,
        lambda cell, c: cell.role == "holdout" and order[c.matchup_seed] % 25 == 0,
        "draw",
        "win",
    )
    result = score_paired_games(protocol, rows)
    assert 0 < result["gain"]["mean"] < protocol.minimum_gain
    assert result["gain"]["ci95"][0] > 0
    assert result["subgroups_clear"] and result["beats_fixed_script_pool"]
    assert not result["improved_over_initialization"]
    assert not result["strength_qualified"]


def test_gain_interval_touching_zero_blocks_even_when_mean_exceeds_minimum(protocol):
    rows = pairs(protocol)
    order = _holdout_clusters(rows)
    rows = _set(
        rows,
        lambda cell, c: cell.role == "holdout" and order[c.matchup_seed] % 20 < 11,
        "loss",
        "win",
    )
    rows = _set(
        rows,
        lambda cell, c: cell.role == "holdout" and order[c.matchup_seed] % 20 >= 11,
        "win",
        "loss",
    )
    result = score_paired_games(protocol, rows)
    assert result["gain"]["mean"] >= protocol.minimum_gain
    assert result["gain"]["ci95"][0] <= 0
    assert not result["improved_over_initialization"]
    assert not result["strength_qualified"]


def test_protocol_cannot_be_weakened_by_editing_structure(protocol):
    from pydantic import ValidationError

    from clasher.rl.council_evaluation import EvaluationProtocol

    base = protocol.model_dump(mode="json")

    def rejected(update, match):
        with pytest.raises(ValidationError, match=match):
            EvaluationProtocol.model_validate(base | update)

    final_holdout = [
        i
        for i, cell in enumerate(base["cells"])
        if cell["purpose"] == "final" and cell["role"] == "holdout"
    ]
    shrunk = [dict(cell) for cell in base["cells"]]
    shrunk[final_holdout[0]]["games"] -= 6
    rejected({"cells": shrunk}, "fewer than 512")
    rejected(
        {"required_slices": [s for s in base["required_slices"] if "disadvantaged" not in s]},
        "subgroup",
    )
    rejected({"seeds": [2901, 2901, 2903]}, "distinct seeds")
    overlapping = [dict(cell) for cell in base["cells"]]
    overlapping[final_holdout[1]]["seed"] = overlapping[final_holdout[0]]["seed"] + 1009
    rejected({"cells": overlapping}, "share matchup seeds")
    # Any diagnostic cell replaying a final matchup seed is rejected, even when
    # only one matchup overlaps and the decks differ.
    for diagnostic in (
        i for i, cell in enumerate(base["cells"]) if cell["purpose"] == "diagnostic"
    ):
        for target in final_holdout[:1] + [
            i
            for i, cell in enumerate(base["cells"])
            if cell["purpose"] == "final" and cell["role"] == "hog26"
        ][:1]:
            leaked = [dict(cell) for cell in base["cells"]]
            leaked[diagnostic]["seed"] = leaked[target]["seed"] + 1009 * (
                leaked[target]["games"] // 2 - 1
            )
            rejected({"cells": leaked}, "diagnostic cells reuse final")
    for field, value in (
        ("minimum_gain", 0.01),
        ("collapse_margin", 0.2),
        ("minimum_slice_games", 10),
        ("tier_b_required", False),
        ("recipe_successes_required", 1),
    ):
        rejected({field: value}, field)


def test_truncated_dropped_or_renumbered_games_are_never_silently_scored(
    tmp_path, protocol
):
    from clasher.rl.council_evaluation import validate_result

    cell, binding, summary, games = write_cell(tmp_path, protocol)
    original = json.loads(games.read_text())

    def check(rows, match, metrics=None):
        games.write_text(json.dumps(rows))
        if metrics is not None:
            data = json.loads(summary.read_text())
            data["metrics"] = metrics
            summary.write_text(json.dumps(data))
        with pytest.raises(ValueError, match=match):
            validate_result(
                protocol, cell, summary_path=summary, games_path=games, binding=binding
            )

    truncated = [dict(row) for row in original]
    truncated[5] |= {"terminated": False, "truncated": True}
    check(truncated, "terminated|truncated")
    # Dropping the unfinished game and shrinking the declared count still fails.
    check(original[:5] + original[6:], "missing declared completed games",
          {"games": cell.games - 1, "score_rate": 1.0})
    renumbered = [dict(row) | {"game": i} for i, row in enumerate(original[:5] + original[6:])]
    renumbered.append(dict(original[-1]) | {"game": cell.games - 1})
    check(renumbered, "seed schedule|dropped or duplicated",
          {"games": cell.games, "score_rate": 1.0})
    check(original, "summary score/count", {"games": cell.games, "score_rate": 0.9})


def _summary(protocol, cell, binding, score):
    return {
        "checkpoint_sha256": binding["checkpoint_sha256"],
        "gamedata_sha256": protocol.gamedata_sha256,
        "checkpoint_gamedata_sha256": protocol.gamedata_sha256,
        "checkpoint_training_seed": binding["training_seed"],
        "model_config_sha256": protocol.model_config_sha256,
        "opponent_mode": "public-script",
        "public_script_style": cell.style,
        "level_mode": cell.level_mode,
        "candidate_sampling_decks_sha256": cell.candidate_decks_sha256,
        "opponent_sampling_decks_sha256": cell.opponent_decks_sha256,
        "seed": cell.seed,
        "deterministic": False,
        "decision_interval_ticks": 5,
        "max_ticks": 6001,
        "public_contract_version": 4,
        "sampling_temperature": 1.0,
        "candidate_defense_strategy": None,
        "location_lookahead": None,
        "metrics": {"games": cell.games, "score_rate": score},
    }


def _write_seed_block(directory, protocol, *, seed, arm):
    directory.mkdir(parents=True)
    checkpoints = {}
    for role in ("initialization", "candidate"):
        checkpoints[role] = directory / f"{role}.pt"
        checkpoints[role].write_bytes(f"synthetic {role} {seed} {arm}".encode())
    by_cell = {}
    for cell, initial, candidate in pairs(protocol):
        by_cell.setdefault(cell.cell_id, (cell, [], []))
        by_cell[cell.cell_id][1].append(initial)
        by_cell[cell.cell_id][2].append(candidate)
    for cell_id, (cell, initial_rows, candidate_rows) in by_cell.items():
        for role, rows in (("initialization", initial_rows), ("candidate", candidate_rows)):
            binding = result_binding(
                protocol, cell, checkpoint=checkpoints[role], seed=seed, arm=arm,
                policy_role=role,
            )
            stem = directory / f"{role}-{cell_id.replace('/', '-')}"
            summary_path = stem.with_suffix(".json")
            games_path = stem.with_suffix(".games.json")
            score = float(np.mean([row.score for row in rows]))
            summary_path.write_text(json.dumps(_summary(protocol, cell, binding, score)))
            games_path.write_text(json.dumps([row.model_dump() for row in rows]))
            record_completion(protocol, cell, summary_path=summary_path,
                              games_path=games_path, binding=binding)
    return checkpoints


def _strings(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from _strings(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _strings(item)
    else:
        yield str(value)


def test_seed_and_recipe_reports_from_bound_files_never_claim_viability(
    tmp_path, protocol
):
    from clasher.rl.council_evaluation import evaluate_seed

    path = tmp_path / "protocol.json"
    path.write_text(protocol.model_dump_json())
    seed_paths = []
    for seed in protocol.seeds:
        directory = tmp_path / f"seed-{seed}"
        _write_seed_block(directory, protocol, seed=seed, arm="scratch")
        report = evaluate_seed(path, directory, seed=seed, arm="scratch")
        assert report["strength_qualified"]
        assert report["status"] == "strength_qualified_tier_b_pending"
        assert report["tier_b_required"] and report["promotion_authorized"] is False
        target = tmp_path / f"report-{seed}.json"
        target.write_text(json.dumps(report))
        seed_paths.append(target)
    recipe = evaluate_recipe(path, seed_paths, arm="scratch")
    assert recipe["qualified_seeds"] == 3
    assert recipe["status"] == "replicated_strength_tier_b_pending"
    assert recipe["promotion_authorized"] is False
    for text in _strings(recipe):
        assert "viable" not in text.lower() and "promot" not in text.lower() or text == "promotion_authorized"

    # Remove one bound cell: the seed can no longer be graded at all.
    directory = tmp_path / f"seed-{protocol.seeds[0]}"
    next(directory.glob("candidate-final-holdout-mixed-*.complete.json")).unlink()
    with pytest.raises(ValueError, match="missing cells"):
        evaluate_seed(path, directory, seed=protocol.seeds[0], arm="scratch")


def test_recipe_with_one_of_three_seeds_is_not_reproducible(
    tmp_path, protocol, monkeypatch
):
    import clasher.rl.council_evaluation as module

    path = tmp_path / "protocol.json"
    path.write_text(protocol.model_dump_json())
    reports, paths = [], []
    for index, seed in enumerate(protocol.seeds):
        report = {
            "arm": "scripted",
            "protocol_sha256": protocol.sha256,
            "evaluation_dir": str(tmp_path / f"seed-{seed}"),
            "seed": seed,
            "candidate_sha256": str(index) * 64,
            "strength_qualified": index == 0,
        }
        reports.append(report)
        target = tmp_path / f"{seed}.json"
        target.write_text(json.dumps(report))
        paths.append(target)
    monkeypatch.setattr(
        module,
        "evaluate_seed",
        lambda protocol_path, evaluation_dir, seed, arm: reports[
            protocol.seeds.index(seed)
        ],
    )
    result = evaluate_recipe(path, paths, arm="scripted")
    assert result["qualified_seeds"] == 1 and not result["reproducible_strength"]
    assert result["status"] == "recipe_strength_not_qualified"
    # A missing (e.g. crashed) seed cannot be dropped to reach two of two.
    with pytest.raises(ValueError, match="exactly all three"):
        evaluate_recipe(path, [paths[0], paths[0], paths[1]], arm="scripted")
