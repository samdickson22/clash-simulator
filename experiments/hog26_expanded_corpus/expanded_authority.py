"""Verify all three complete cohorts before exposing streamed training games."""

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from expansion_protocol import COMPLETE_PATHS
from parallel_protocol import source_fingerprint as expansion_fingerprint
from parallel_protocol import validate_plan as validate_expansion
from scaling_protocol import source_fingerprint as scaling_fingerprint
from scaling_protocol import validate_pilot_plan as validate_scaling
from terminal_labels import sha

from clasher.rl.simple_pytorch_backend import (
    _compile_public_mask_v2_tables,
    _typed_lookups,
    load_current_client_typed_vocabulary,
)
from clasher.rl.structured_obs import StructuredObservationBuilder
from clasher.torch_sim.simple_public_mask import SimplePublicMaskV2Provider
from clasher.torch_sim.simple_standard import compile_standard_simple_setup
from scripts.collect_hog26_scalar_pilot import EXTRA_TOKENS
from scripts.hog26_scalar_corpus import validate_scalar_corpus
from scripts.hog26_scalar_opening_audit import audit_scalar_opening_metadata
from scripts.hog26_scalar_openings import digest
from scripts.hog26_scalar_pilot_protocol import (
    source_fingerprint as original_fingerprint,
)
from scripts.hog26_scalar_pilot_protocol import validate_pilot_plan as validate_original
from scripts.hog26_scalar_public_payload_mask import (
    ScalarPublicPayloadMaskProvider,
    ScalarPublicPayloadMaskRules,
)

PUBLIC_FIELDS = ("entity_ids", "entity_features", "entity_mask", "entity_id_confidence",
                 "entity_feature_confidence", "hand_ids", "hand_id_confidence",
                 "global_features", "global_feature_confidence")
COHORTS = (
    ("original", "hog26_scalar_birthfixed_pilot_seed1279261_20260911", "hog26_scalar_birthfixed_frozen_plan_20260911.json",
     "hog26_scalar_birthfixed_preflight_pin_20260911.json", 384),
    ("extension", "hog26_scaling_train_seed1279701_20260912", "hog26_scaling_frozen_plan_20260912.json",
     "hog26_scaling_preflight_pin_20260912.json", 1152),
    ("expanded", "hog26_training_expansion_parallel_seed1280101_20260913", "hog26_training_expansion_parallel_frozen_plan_20260913.json",
     "hog26_training_expansion_parallel_preflight_pin_20260913.json", 4608),
)


@dataclass(frozen=True)
class ScheduledGame:
    path: Path
    sha256: str
    cohort: str
    metadata: dict
    initial_hand: tuple[int, ...]
    record: dict


@dataclass(frozen=True)
class CorpusAuthority:
    games: tuple[ScheduledGame, ...]
    vocabulary: tuple[str, ...]
    resources: dict[str, str]
    cohort_rows: dict[str, int]
    learner_cards: tuple[str, ...]


def build_context(root):
    vocabulary = load_current_client_typed_vocabulary()
    builder = StructuredObservationBuilder(decks_path=root / "decks.json", token_names=vocabulary.token_names,
                                            max_entities=128, card_semantics_version=3, canonical_lane_globals=True)
    resource_paths = {"checkpoint": root / "checkpoints/hog26_direct_constant_event_seed1263001/candidate.pt",
                      "card_data": Path(builder.loader.data_file)}
    arguments = {"resource_paths": resource_paths, "vocabulary_sha256": vocabulary.sha256,
                 "card_definitions": builder.loader.load_card_definitions()}
    authorities = {"original": original_fingerprint(root, **arguments),
                   "extension": scaling_fingerprint(root, **arguments),
                   "expanded": expansion_fingerprint(root, **arguments)}
    canonical = authorities["original"]["contract"]["canonical_names"]
    if any(a["contract"]["canonical_names"] != canonical for a in authorities.values()):
        raise ValueError("cohort canonical card contracts differ")
    setup = compile_standard_simple_setup(builder.loader, canonical, device="cpu", canonical_lane_globals=True)
    lookup, _ = _typed_lookups(setup, builder.loader, vocabulary)
    base_provider = SimplePublicMaskV2Provider(_compile_public_mask_v2_tables(builder, setup, lookup))
    tokens = (*vocabulary.token_names, *EXTRA_TOKENS)
    provider = ScalarPublicPayloadMaskProvider(base_provider, ScalarPublicPayloadMaskRules.compile(
        builder.loader, policy_token_names=vocabulary.token_names, outcome_token_names=tokens))
    return vocabulary, tokens, provider.semantics_digest, authorities


def metadata_for(authority, plan, schedule, scenario, seat, tokens, policy_tokens, mask_digest,
                 *, source_digest=None, plan_digest=None):
    return {"schema": "clasher.scalar-pilot-game-metadata.v1", "mode": "collect",
            "source_authority_sha256": source_digest or digest(authority), "plan_sha256": plan_digest or digest(plan),
            "opening_metadata": schedule["metadata"], "opening_authority": schedule["external_authority"],
            "scenario_id": scenario.scenario_id, "cluster_id": scenario.cluster_id,
            "ordinal": scenario.ordinal, "learner_seat": seat, "family_id": schedule["family_id"],
            "style": schedule["external_authority"]["opponent_style"],
            "outcome_token_names": list(tokens), "policy_token_names": list(policy_tokens),
            "mask_semantics_digest": mask_digest,
            "retention": "all predecision learner rows through first actual terminal; no filtering by success/outcome"}


def load_authority(root):
    root = Path(root)
    # This gate precedes model setup, older cohort arrays and any feature access.
    expanded_complete = root / "datasets/derived" / COHORTS[2][1] / "complete.json"
    if not expanded_complete.is_file():
        raise ValueError("expanded collection incomplete; no combined training access")
    newest = json.loads(expanded_complete.read_text())
    if newest.get("status") != "complete-audited" or newest.get("game_count") != 4608:
        raise ValueError("expanded collection incomplete; no combined training access")
    parity_path = root / "reports/hog26_training_expansion_sequential_prefix_parity_20260913.json"
    if not parity_path.is_file():
        raise ValueError("retired sequential prefix parity required before combined training access")
    parity = json.loads(parity_path.read_text())
    prefix_path = root / "reports/hog26_training_expansion_sequential_retired_prefix_20260913.json"
    prefix = json.loads(prefix_path.read_text())
    if (parity.get("status") != "retired-prefix-array-parity-passed"
            or not parity.get("all_arrays_exact_except_provenance_metadata")
            or parity.get("parallel_complete_sha256") != sha(expanded_complete)
            or parity.get("prefix_manifest_sha256") != sha(prefix_path)
            or prefix.get("status") != "audited-retired-sequential-prefix"
            or parity.get("games") != prefix.get("games") or prefix.get("games") != len(prefix.get("input_games", []))
            or prefix.get("games", 0) <= 0 or len(parity.get("comparisons", [])) != prefix["games"]
            or prefix.get("source_plan_sha256") != sha(root / "reports/hog26_training_expansion_frozen_plan_20260913.json")
            or parity.get("source_sha256") != sha(root / "experiments/hog26_parallel_expansion/prefix_audit.py")
            or {row["path"] for row in parity.get("comparisons", [])} != {Path(row["path"]).name for row in prefix["input_games"]}
            or any(not row.get("exact") for row in parity.get("comparisons", []))):
        raise ValueError("retired sequential prefix parity differs from completed expansion")
    vocabulary, tokens, mask_digest, authorities = build_context(root)
    resources, games, cohort_rows = {str(parity_path): sha(parity_path), str(prefix_path): sha(prefix_path)}, [], {}
    all_clusters, excluded_clusters = set(), set()
    diagnostic_plan = root / "reports/hog26_seed_transfer_frozen_plan_20260911.json"
    diagnostic = json.loads(diagnostic_plan.read_text())
    resources[str(diagnostic_plan)] = sha(diagnostic_plan)
    for schedule in diagnostic["schedules"]:
        excluded_clusters.update(s.cluster_id for s in audit_scalar_opening_metadata(
            schedule["metadata"], expected_authority=schedule["external_authority"]))
    expansion_pin = root / "reports/hog26_training_expansion_parallel_preflight_pin_20260913.json"
    excluded_clusters.update(json.loads(expansion_pin.read_text())["preflight_clusters"])
    for relative in COMPLETE_PATHS:
        if "preflight" in relative:
            excluded_clusters.update(row["cluster_id"] for row in json.loads((root / relative).read_text())["games"])
    for kind, directory_name, plan_name, pin_name, count in COHORTS:
        directory = root / "datasets/derived" / directory_name
        plan_path, pin_path = root / "reports" / plan_name, root / "reports" / pin_name
        plan, pin = json.loads(plan_path.read_text()), json.loads(pin_path.read_text())
        complete_path, run_plan_path = directory / "complete.json", directory / "run_plan.json"
        complete = json.loads(complete_path.read_text())
        if kind == "expanded":
            validate_expansion(plan, authorities[kind], preflight=pin)
        else:
            validator = validate_original if kind == "original" else validate_scaling
            validator(plan, authorities[kind], expected_preflight=pin)
        if (not plan["collection_allowed"] or not plan["frozen"] or plan["expected_natural_games"] != count
                or complete.get("status") != "complete-audited" or complete.get("mode") != "collect"
                or complete.get("game_count") != count or len(complete.get("games", [])) != count
                or complete["source_authority_sha256"] != digest(authorities[kind])
                or complete["plan_sha256"] != digest(plan) or json.loads(run_plan_path.read_text()) != plan):
            raise ValueError("complete cohort differs from frozen external authority")
        for path in (plan_path, pin_path, complete_path, run_plan_path):
            resources[str(path)] = sha(path)
        records = {row["path"]: row for row in complete["games"]}
        if len(records) != count or set(records) != {p.name for p in directory.glob("game-*.npz")}:
            raise ValueError("cohort file inventory differs")
        ordered, local_clusters = [], set()
        source_digest, plan_digest = digest(authorities[kind]), digest(plan)
        for index, schedule in enumerate(plan["schedules"]):
            for scenario in audit_scalar_opening_metadata(schedule["metadata"], expected_authority=schedule["external_authority"]):
                if scenario.cluster_id in all_clusters | local_clusters | excluded_clusters:
                    raise ValueError("combined training relative-deal overlap")
                local_clusters.add(scenario.cluster_id)
                for seat in schedule["learner_seats"]:
                    name = f"game-{index:03d}-{scenario.ordinal:03d}-{seat}.npz"
                    record = records[name]
                    metadata = metadata_for(authorities[kind], plan, schedule, scenario, seat,
                                            tokens, vocabulary.token_names, mask_digest,
                                            source_digest=source_digest, plan_digest=plan_digest)
                    hand = tuple(vocabulary.resolve(card, "card_action") for card in scenario.relative_decks[0][:5])
                    if any(token <= 1 for token in hand):
                        raise ValueError("unresolved expected opening hand")
                    ordered.append(ScheduledGame(directory / name, record["sha256"], kind, metadata, hand, record))
        if ([g.path.name for g in ordered] != [row["path"] for row in complete["games"]]
                or len(ordered) != count or len(local_clusters) != count // 2
                or sum(row["rows"] for row in complete["games"]) != complete["rows"]):
            raise ValueError("cohort ordering, count or rows differ")
        if any(sum(g.metadata["family_id"] == f"family-{f:03d}" for g in ordered) != count // 8 for f in range(8)):
            raise ValueError("cohort family quota differs")
        games.extend(ordered)
        all_clusters.update(local_clusters)
        cohort_rows[kind] = complete["rows"]
    if len(games) != 6144 or len(all_clusters) != 3072:
        raise ValueError("combined training quota differs")
    reference_path = root / "reports/hog26_scaling_globals_comparison_20260912/fitting_manifest.json"
    reference = json.loads(reference_path.read_text())
    original_records = [{"path": str((root / row["path"]).resolve()), "sha256": row["sha256"]}
                        for row in reference["input_games"]]
    if [{"path": str(g.path.resolve()), "sha256": g.sha256} for g in games[:1536]] != original_records:
        raise ValueError("original training prefix differs from reviewed model corpus")
    resources[str(reference_path)] = sha(reference_path)
    resources[str(root / "decks.json")] = sha(root / "decks.json")
    for authority in authorities.values():
        resources.update({str(root / relative): value for relative, value in authority["sources"].items()})
        resources.update({item["path"]: item["sha256"] for item in authority["resources"].values()})
    return CorpusAuthority(tuple(games), tuple(tokens), resources, cohort_rows,
                           tuple(authorities["original"]["contract"]["learner_template"]))


def read_game(game):
    if sha(game.path) != game.sha256:
        raise ValueError("combined game bytes differ from completed manifest")
    audit = validate_scalar_corpus(game.path, expected_metadata=game.metadata)
    audit.pop("metadata")
    expected = {"path": game.path.name, "sha256": game.sha256,
                **{key: game.metadata[key] for key in ("family_id", "style", "learner_seat", "scenario_id", "cluster_id")}, **audit}
    if expected != game.record or json.loads(game.path.with_suffix(".audit.json").read_text()) != game.record:
        raise ValueError("combined per-game audit does not reproduce")
    if any(audit[key] for key in ("rejected_card_actions", "noop_false_results", "failed_ability_actions")):
        raise ValueError("combined training contains rejected or failed actions")
    with np.load(game.path, allow_pickle=False) as archive:
        if (not bool(archive["actual_terminal"]) or archive["entity_ids"].shape[1] != 128
                or not np.array_equal(archive["hand_ids"][0], game.initial_hand)):
            raise ValueError("combined game terminal, capacity or initial hand differs")
        public = {key: archive[key] for key in PUBLIC_FIELDS}
        label = 2 - int(np.argmax(archive["outcome_wdl"]))
        margin = float(archive["terminal_tower_margin"])
    for key in ("hand_ids", "hand_id_confidence"):
        public[key] = public[key][:, :4]
    return public, label, margin
