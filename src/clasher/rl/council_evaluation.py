"""Prospective paired-seat strength evaluation; never a promotion authority."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator


class EvaluationCell(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    cell_id: str
    purpose: Literal["diagnostic", "final"]
    role: Literal["holdout", "hog26"]
    style: Literal["balanced", "pressure", "defense"]
    level_mode: Literal["nominal", "mixed"]
    games: int = Field(ge=2)
    seed: int
    candidate_decks_path: str
    candidate_decks_sha256: str
    opponent_decks_path: str
    opponent_decks_sha256: str

    @model_validator(mode="after")
    def complete_pairs(self):
        if self.games % 2:
            raise ValueError("evaluation cells require complete seat pairs")
        return self


class EvaluationProtocol(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["council-strength-v1"] = "council-strength-v1"
    strategy_sha256: str
    gamedata_sha256: str
    model_config_sha256: str
    seeds: tuple[int, int, int]
    arms: tuple[str, str]
    cells: tuple[EvaluationCell, ...]
    family_by_roster: dict[str, str]
    required_slices: tuple[str, ...]
    min_final_heldout_games: Literal[512] = 512
    minimum_gain: Literal[0.05] = 0.05
    collapse_margin: Literal[0.10] = 0.10
    minimum_slice_games: Literal[40] = 40
    minimum_slice_clusters: Literal[20] = 20
    confidence: Literal[0.95] = 0.95
    bootstrap_replicates: Literal[20000] = 20000
    bootstrap_seed: Literal[9428] = 9428
    # Levels are compared only against the matched initializer in the same case.
    disadvantage_level_gap: Literal[0.25] = 0.25
    tier_b_required: Literal[True] = True
    recipe_successes_required: Literal[2] = 2
    decoder: Literal["stochastic-temperature-one"] = "stochastic-temperature-one"

    @model_validator(mode="after")
    def prospective_rules_are_structurally_enforceable(self):
        # A hand-edited protocol must not weaken the predeclared rules while
        # keeping the Literal thresholds: seeds, sample size, slices, clusters.
        if len(set(self.seeds)) != 3 or len(set(self.arms)) != 2:
            raise ValueError("protocol needs three distinct seeds and two arms")
        if len({cell.cell_id for cell in self.cells}) != len(self.cells):
            raise ValueError("duplicate evaluation cell")
        final = [cell for cell in self.cells if cell.purpose == "final"]
        if (
            sum(cell.games for cell in final if cell.role == "holdout")
            < self.min_final_heldout_games
        ):
            raise ValueError("final held-out matrix declares fewer than 512 games")
        families = sorted(set(self.family_by_roster.values()))
        mandatory = {
            "heldout/nominal",
            "heldout/mixed",
            "heldout/mixed/disadvantaged",
            "hog26/nominal",
            "hog26/mixed",
            *("heldout/family/" + name for name in families),
        }
        if not families or set(self.required_slices) != mandatory:
            raise ValueError("protocol omits or invents predeclared subgroup slices")
        if len(set(self.required_slices)) != len(self.required_slices):
            raise ValueError("duplicate subgroup slice")
        # Clusters are keyed by matchup seed; overlapping final schedules would
        # silently merge independent cells or reuse the same games.
        def schedule(cell):
            return {cell.seed + matchup * 1009 for matchup in range(cell.games // 2)}

        scheduled = set()
        for cell in final:
            seeds = schedule(cell)
            if scheduled & seeds:
                raise ValueError("final evaluation cells share matchup seeds")
            scheduled |= seeds
        # Diagnostic games inform humans mid-run; they must never replay a final
        # matchup, even with other decks, so final results stay prospective.
        for cell in self.cells:
            if cell.purpose == "diagnostic" and schedule(cell) & scheduled:
                raise ValueError("diagnostic cells reuse final matchup seeds")
        return self

    @property
    def sha256(self):
        return canonical_sha(self.model_dump(mode="json"))


class GameRecord(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True, frozen=True)
    game: int = Field(ge=0)
    matchup: int = Field(ge=0)
    matchup_seed: int
    candidate_player: Literal[0, 1]
    outcome: Literal["win", "draw", "loss"]
    terminated: Literal[True]
    truncated: Literal[False]
    ticks: int = Field(gt=0, le=6001)
    candidate_deck: list[str] = Field(min_length=8, max_length=8)
    opponent_deck: list[str] = Field(min_length=8, max_length=8)
    candidate_card_levels: dict[str, int]
    opponent_card_levels: dict[str, int]
    candidate_tower_level: int
    opponent_tower_level: int
    level_mode: Literal["nominal", "mixed"]

    @model_validator(mode="after")
    def levels_match_cards(self):
        for prefix in ("candidate", "opponent"):
            cards = getattr(self, f"{prefix}_deck")
            levels = getattr(self, f"{prefix}_card_levels")
            if len(set(cards)) != 8 or set(levels) != set(cards):
                raise ValueError("every declared deck card needs its actual level")
            values = [*levels.values(), getattr(self, f"{prefix}_tower_level")]
            if any(
                type(value) is not int or value not in (10, 11, 12) for value in values
            ):
                raise ValueError("evaluation contains an unsupported level")
            if self.level_mode == "nominal" and any(value != 11 for value in values):
                raise ValueError("nominal evaluation contains a non-nominal level")
        return self

    @property
    def score(self):
        return {"win": 1.0, "draw": 0.5, "loss": 0.0}[self.outcome]

    def case_identity(self):
        return {
            name: getattr(self, name)
            for name in (
                "game",
                "matchup",
                "matchup_seed",
                "candidate_player",
                "candidate_deck",
                "opponent_deck",
                "candidate_card_levels",
                "opponent_card_levels",
                "candidate_tower_level",
                "opponent_tower_level",
                "level_mode",
            )
        }


def canonical_sha(value) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def roster_key(cards) -> str:
    return "|".join(sorted(cards))


def build_protocol(config) -> EvaluationProtocol:
    from clasher.data import CardDataLoader

    from .council_pilot import build_council_model_config, evaluation_commands
    from .structured_obs import StructuredObservationBuilder

    builder = StructuredObservationBuilder(
        card_loader=CardDataLoader(config.gamedata_path),
        decks_path=config.training_decks_path,
        max_entities=128,
        card_semantics_version=4,
        canonical_lane_globals=True,
        public_history_slots=4,
        public_seen_card_slots=8,
        public_entity_levels=True,
        public_hand_levels=True,
    )
    cells = []
    for final in (False, True):
        purpose = "final" if final else "diagnostic"
        for command in evaluation_commands(
            config, checkpoint=Path("candidate.pt"), output=Path("out"), final=final
        ):

            def arg(name, args=command):
                return args[args.index("--" + name) + 1]

            role = (
                "hog26"
                if arg("candidate-sampling-decks-path") == config.deployment_decks_path
                else "holdout"
            )
            style, mode = arg("public-script-style"), arg("level-mode")
            cells.append(
                EvaluationCell(
                    cell_id=f"{purpose}/{role}/{mode}/{style}",
                    purpose=purpose,
                    role=role,
                    style=style,
                    level_mode=mode,
                    games=int(arg("games")),
                    seed=int(arg("seed")),
                    candidate_decks_path=arg("candidate-sampling-decks-path"),
                    candidate_decks_sha256=file_sha(
                        Path(arg("candidate-sampling-decks-path"))
                    ),
                    opponent_decks_path=arg("opponent-sampling-decks-path"),
                    opponent_decks_sha256=file_sha(
                        Path(arg("opponent-sampling-decks-path"))
                    ),
                )
            )
    payload = json.loads(Path(config.acceptance_decks_path).read_text())
    by_name = {row["name"]: row for row in payload["decks"]}
    family_by_roster = {}
    for row in payload["decks"]:
        parent = row
        seen = set()
        while parent.get("parent"):
            if parent["name"] in seen or parent["parent"] not in by_name:
                raise ValueError("invalid evaluation family graph")
            seen.add(parent["name"])
            parent = by_name[parent["parent"]]
        key = roster_key(row["cards"])
        if key in family_by_roster and family_by_roster[key] != parent["name"]:
            raise ValueError("ambiguous evaluation roster")
        family_by_roster[key] = parent["name"]
    slices = [
        "heldout/nominal",
        "heldout/mixed",
        "heldout/mixed/disadvantaged",
        "hog26/nominal",
        "hog26/mixed",
    ]
    slices += [
        "heldout/family/" + name for name in sorted(set(family_by_roster.values()))
    ]
    return EvaluationProtocol(
        strategy_sha256=config.strategy_sha256,
        gamedata_sha256=config.gamedata_sha256,
        model_config_sha256=canonical_sha(
            build_council_model_config(builder).to_dict()
        ),
        seeds=config.seeds,
        arms=config.arms,
        cells=tuple(cells),
        family_by_roster=family_by_roster,
        required_slices=tuple(slices),
    )


def load_protocol(path: Path) -> EvaluationProtocol:
    return EvaluationProtocol.model_validate_json(path.read_text())


def freeze_protocol(config) -> EvaluationProtocol:
    protocol = build_protocol(config)
    path = Path(config.evaluation_protocol_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if load_protocol(path) != protocol:
            raise ValueError("evaluation protocol already frozen with different rules")
    else:
        with path.open("x") as stream:
            stream.write(protocol.model_dump_json(indent=2) + "\n")
    return protocol


def cell_for_command(
    protocol: EvaluationProtocol, command: list[str], *, final: bool
) -> EvaluationCell:
    def arg(name):
        return command[command.index("--" + name) + 1]

    purpose = "final" if final else "diagnostic"
    matches = [
        cell
        for cell in protocol.cells
        if cell.purpose == purpose
        and cell.style == arg("public-script-style")
        and cell.level_mode == arg("level-mode")
        and cell.candidate_decks_path == arg("candidate-sampling-decks-path")
    ]
    if len(matches) != 1:
        raise ValueError("evaluation command is outside the frozen matrix")
    cell = matches[0]
    if (
        int(arg("seed")) != cell.seed
        or int(arg("games")) != cell.games
        or "--stochastic" not in command
    ):
        raise ValueError("evaluation command changed frozen seeds, size or decoder")
    return cell


def result_binding(
    protocol: EvaluationProtocol,
    cell: EvaluationCell,
    *,
    checkpoint: Path,
    seed: int,
    arm: str,
    policy_role: str,
) -> dict:
    if (
        seed not in protocol.seeds
        or arm not in protocol.arms
        or policy_role not in {"initialization", "candidate"}
    ):
        raise ValueError("undeclared policy role or training seed")
    return {
        "protocol_sha256": protocol.sha256,
        "cell_id": cell.cell_id,
        "checkpoint": str(checkpoint.resolve()),
        "checkpoint_sha256": file_sha(checkpoint),
        "training_seed": seed,
        "arm": arm,
        "policy_role": policy_role,
    }


def validate_result(
    protocol: EvaluationProtocol,
    cell: EvaluationCell,
    *,
    summary_path: Path,
    games_path: Path,
    binding: dict,
) -> list[GameRecord]:
    summary = json.loads(summary_path.read_text())
    required = {
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
    }
    if any(summary.get(key) != value for key, value in required.items()):
        raise ValueError("evaluation metadata differs from frozen binding")
    if file_sha(Path(binding["checkpoint"])) != binding["checkpoint_sha256"]:
        raise ValueError("evaluated checkpoint changed")
    for path, digest in (
        (cell.candidate_decks_path, cell.candidate_decks_sha256),
        (cell.opponent_decks_path, cell.opponent_decks_sha256),
    ):
        if file_sha(Path(path)) != digest:
            raise ValueError("evaluation deck role changed")
    games = [
        GameRecord.model_validate(row) for row in json.loads(games_path.read_text())
    ]
    if len(games) != cell.games or {row.game for row in games} != set(
        range(cell.games)
    ):
        raise ValueError("evaluation is missing declared completed games")
    candidate_rosters = {
        roster_key(row["cards"])
        for row in json.loads(Path(cell.candidate_decks_path).read_text())["decks"]
    }
    opponent_rosters = {
        roster_key(row["cards"])
        for row in json.loads(Path(cell.opponent_decks_path).read_text())["decks"]
    }
    groups = defaultdict(list)
    for row in games:
        if (
            roster_key(row.candidate_deck) not in candidate_rosters
            or roster_key(row.opponent_deck) not in opponent_rosters
        ):
            raise ValueError("evaluation game used a deck outside its frozen role")
        if (
            row.matchup != row.game // 2
            or row.candidate_player != row.game % 2
            or row.matchup_seed != cell.seed + row.matchup * 1009
            or row.level_mode != cell.level_mode
        ):
            raise ValueError(
                "evaluation pair identity does not match the declared seed schedule"
            )
        groups[row.matchup].append(row)
    for pair in groups.values():
        if len(pair) != 2 or {row.candidate_player for row in pair} != {0, 1}:
            raise ValueError("evaluation dropped or duplicated a seat")
        if roster_key(pair[0].candidate_deck) != roster_key(
            pair[1].candidate_deck
        ) or roster_key(pair[0].opponent_deck) != roster_key(pair[1].opponent_deck):
            raise ValueError("paired seats changed the deck matchup")
    score = float(np.mean([row.score for row in games]))
    metrics = summary["metrics"]
    if int(metrics["games"]) != cell.games or not np.isclose(
        metrics["score_rate"], score, atol=1e-12
    ):
        raise ValueError("summary score/count disagree with completed game records")
    return sorted(games, key=lambda row: row.game)


def completion_path(summary_path: Path) -> Path:
    return summary_path.with_suffix(".complete.json")


def validated_completion(protocol, cell, *, summary_path, games_path, binding) -> bool:
    marker = completion_path(summary_path)
    if not marker.exists():
        if summary_path.exists() or games_path.exists():
            raise ValueError(
                "uncommitted evaluation artifacts exist; retain them and reconcile instead of silently rerunning"
            )
        return False
    record = json.loads(marker.read_text())
    if (
        record["binding"] != binding
        or record["summary_sha256"] != file_sha(summary_path)
        or record["games_sha256"] != file_sha(games_path)
    ):
        raise ValueError("completed evaluation binding or artifacts changed")
    validate_result(
        protocol,
        cell,
        summary_path=summary_path,
        games_path=games_path,
        binding=binding,
    )
    return True


def record_completion(protocol, cell, *, summary_path, games_path, binding):
    validate_result(
        protocol,
        cell,
        summary_path=summary_path,
        games_path=games_path,
        binding=binding,
    )
    record = {
        "schema": "council-evaluation-completion-v1",
        "binding": binding,
        "summary_path": str(summary_path.resolve()),
        "games_path": str(games_path.resolve()),
        "summary_sha256": file_sha(summary_path),
        "games_sha256": file_sha(games_path),
    }
    with completion_path(summary_path).open("x") as stream:
        json.dump(record, stream, indent=2)
        stream.write("\n")


def clustered_interval(values, clusters, *, repetitions=20000, seed=9428):
    values = np.asarray(values, dtype=np.float64)
    if (
        values.ndim != 1
        or len(values) != len(clusters)
        or not len(values)
        or not np.isfinite(values).all()
    ):
        raise ValueError("invalid finite clustered observations")
    groups = defaultdict(list)
    for value, cluster in zip(values, clusters):
        groups[cluster].append(value)
    names = sorted(groups)
    sums = np.asarray([sum(groups[name]) for name in names])
    counts = np.asarray([len(groups[name]) for name in names])
    if len(names) < 2:
        raise ValueError(
            "clustered uncertainty needs at least two independent clusters"
        )
    rng = np.random.default_rng(seed)
    estimates = []
    # Ratio-of-sums preserves game weighting in subgroups containing one seat.
    for start in range(0, repetitions, 1000):
        chosen = rng.integers(
            0, len(names), size=(min(1000, repetitions - start), len(names))
        )
        estimates.extend((sums[chosen].sum(1) / counts[chosen].sum(1)).tolist())
    low, high = np.quantile(estimates, [0.025, 0.975])
    return {
        "mean": float(values.mean()),
        "ci95": [float(low), float(high)],
        "games": len(values),
        "clusters": len(names),
    }


def _slice_names(protocol, cell, game):
    names = [f"{'heldout' if cell.role == 'holdout' else 'hog26'}/{cell.level_mode}"]
    if cell.role == "holdout":
        family = protocol.family_by_roster.get(roster_key(game.candidate_deck))
        if family is None:
            raise ValueError("held-out game uses an undeclared family roster")
        names.append("heldout/family/" + family)
        own = np.mean(
            [*game.candidate_card_levels.values(), game.candidate_tower_level]
        )
        other = np.mean(
            [*game.opponent_card_levels.values(), game.opponent_tower_level]
        )
        if (
            cell.level_mode == "mixed"
            and own - other <= -protocol.disadvantage_level_gap
        ):
            names.append("heldout/mixed/disadvantaged")
    return names


def score_paired_games(
    protocol: EvaluationProtocol,
    pairs: list[tuple[EvaluationCell, GameRecord, GameRecord]],
) -> dict:
    primary = []
    slices = defaultdict(list)
    seen = set()
    for cell, initial, candidate in pairs:
        if (
            cell.purpose != "final"
            or initial.case_identity() != candidate.case_identity()
        ):
            raise ValueError(
                "candidate and initializer do not share the exact frozen case"
            )
        key = (cell.cell_id, candidate.game)
        if key in seen:
            raise ValueError("duplicate policy case")
        seen.add(key)
        # Matrix seeds are disjoint; repeated conditions cannot invent clusters.
        cluster = str(candidate.matchup_seed)
        record = (candidate.score - initial.score, candidate.score, cluster)
        if cell.role == "holdout":
            primary.append(record)
        for name in _slice_names(protocol, cell, candidate):
            slices[name].append(record)
    expected = {
        (cell.cell_id, game)
        for cell in protocol.cells
        if cell.purpose == "final"
        for game in range(cell.games)
    }
    if seen != expected:
        raise ValueError("final evaluation matrix is incomplete")
    if len(primary) < protocol.min_final_heldout_games:
        raise ValueError("fewer than 512 held-out completed games")
    gain = clustered_interval(
        [r[0] for r in primary],
        [r[2] for r in primary],
        repetitions=protocol.bootstrap_replicates,
        seed=protocol.bootstrap_seed,
    )
    score = clustered_interval(
        [r[1] for r in primary],
        [r[2] for r in primary],
        repetitions=protocol.bootstrap_replicates,
        seed=protocol.bootstrap_seed,
    )
    reports = {}
    for name in protocol.required_slices:
        rows = slices[name]
        clusters = {row[2] for row in rows}
        if (
            len(rows) < protocol.minimum_slice_games
            or len(clusters) < protocol.minimum_slice_clusters
        ):
            reports[name] = {
                "status": "insufficient_coverage",
                "games": len(rows),
                "clusters": len(clusters),
            }
            continue
        stats = clustered_interval(
            [r[0] for r in rows],
            [r[2] for r in rows],
            repetitions=protocol.bootstrap_replicates,
            seed=protocol.bootstrap_seed,
        )
        if stats["mean"] <= -protocol.collapse_margin and stats["ci95"][1] < 0:
            status = "material_collapse"
        elif stats["ci95"][0] > -protocol.collapse_margin:
            status = "noninferiority_supported"
        else:
            status = "inconclusive"
        reports[name] = stats | {
            "status": status,
            "candidate_score": float(np.mean([r[1] for r in rows])),
        }
    improved = gain["mean"] >= protocol.minimum_gain and gain["ci95"][0] > 0
    beats_pool = score["mean"] > 0.5
    subgroup_clear = all(
        value["status"] == "noninferiority_supported" for value in reports.values()
    )
    qualified = improved and beats_pool and subgroup_clear
    return {
        "status": "strength_qualified_tier_b_pending"
        if qualified
        else "strength_not_qualified",
        "strength_qualified": qualified,
        "gain": gain,
        "candidate_score": score,
        "improved_over_initialization": improved,
        "beats_fixed_script_pool": beats_pool,
        "subgroups_clear": subgroup_clear,
        "subgroups": reports,
        "tier_b_required": True,
        "promotion_authorized": False,
        "uncertainty": "two-sided 95% paired cluster percentile bootstrap; independent seed clusters; no per-cell win-rate floor",
    }


def evaluate_seed(
    protocol_path: Path, evaluation_dir: Path, *, seed: int, arm: str
) -> dict:
    protocol = load_protocol(protocol_path)
    if seed not in protocol.seeds or arm not in protocol.arms:
        raise ValueError("undeclared training replica")
    records = {}
    artifacts = []
    checkpoint_hashes = defaultdict(set)
    cells = {cell.cell_id: cell for cell in protocol.cells if cell.purpose == "final"}
    for marker in sorted(evaluation_dir.glob("*.complete.json")):
        record = json.loads(marker.read_text())
        binding = record["binding"]
        if binding.get("training_seed") != seed or binding.get("arm") != arm:
            raise ValueError("evaluation directory mixes replicas")
        if (
            binding.get("protocol_sha256") != protocol.sha256
            or binding["cell_id"] not in cells
        ):
            raise ValueError("evaluation uses another protocol/purpose")
        key = (binding["cell_id"], binding["policy_role"])
        if key in records:
            raise ValueError("duplicate completed evaluation cell")
        cell = cells[binding["cell_id"]]
        summary_path, games_path = (
            Path(record["summary_path"]),
            Path(record["games_path"]),
        )
        validated_completion(
            protocol,
            cell,
            summary_path=summary_path,
            games_path=games_path,
            binding=binding,
        )
        records[key] = validate_result(
            protocol,
            cell,
            summary_path=summary_path,
            games_path=games_path,
            binding=binding,
        )
        checkpoint_hashes[binding["policy_role"]].add(binding["checkpoint_sha256"])
        artifacts.append({"path": str(marker.resolve()), "sha256": file_sha(marker)})
    expected = {
        (cell_id, role) for cell_id in cells for role in ("initialization", "candidate")
    }
    if set(records) != expected or any(
        len(checkpoint_hashes[role]) != 1 for role in ("initialization", "candidate")
    ):
        raise ValueError("missing cells or checkpoint changed within final block")
    pairs = [
        (cell, initial, candidate)
        for key, cell in cells.items()
        for initial, candidate in zip(
            records[(key, "initialization")], records[(key, "candidate")]
        )
    ]
    result = score_paired_games(protocol, pairs)
    return result | {
        "schema": "council-seed-strength-v1",
        "protocol_path": str(protocol_path.resolve()),
        "protocol_sha256": protocol.sha256,
        "evaluation_dir": str(evaluation_dir.resolve()),
        "seed": seed,
        "arm": arm,
        "candidate_sha256": next(iter(checkpoint_hashes["candidate"])),
        "initialization_sha256": next(iter(checkpoint_hashes["initialization"])),
        "artifacts": artifacts,
    }


def evaluate_recipe(
    protocol_path: Path, seed_report_paths: list[Path], *, arm: str
) -> dict:
    protocol = load_protocol(protocol_path)
    reports = []
    for path in seed_report_paths:
        saved = json.loads(path.read_text())
        if saved["arm"] != arm or saved["protocol_sha256"] != protocol.sha256:
            raise ValueError("recipe reports mix arms/protocols")
        current = evaluate_seed(
            protocol_path, Path(saved["evaluation_dir"]), seed=saved["seed"], arm=arm
        )
        if current != saved:
            raise ValueError("seed report or its bound results changed")
        reports.append(current)
    if len(reports) != 3 or {report["seed"] for report in reports} != set(
        protocol.seeds
    ):
        raise ValueError("recipe requires exactly all three declared seeds")
    if len({report["candidate_sha256"] for report in reports}) != 3:
        raise ValueError(
            "three reports reused candidate weights instead of independent training seeds"
        )
    successes = sum(report["strength_qualified"] for report in reports)
    return {
        "schema": "council-recipe-strength-v1",
        "protocol_sha256": protocol.sha256,
        "arm": arm,
        "seeds": list(protocol.seeds),
        "qualified_seeds": successes,
        "reproducible_strength": successes >= protocol.recipe_successes_required,
        "status": "replicated_strength_tier_b_pending"
        if successes >= protocol.recipe_successes_required
        else "recipe_strength_not_qualified",
        "tier_b_required": True,
        "promotion_authorized": False,
    }
