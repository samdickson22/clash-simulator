"""Fixed unfiltered complete-game expansion; reserved roles stay unchanged."""

import copy
import json
from pathlib import Path

from scripts.hog26_scalar_opening_audit import audit_scalar_opening_metadata
from scripts.hog26_scalar_openings import CanonicalOpeningSchedule, digest
from scripts.hog26_scalar_pilot_protocol import assert_source_unchanged
from scripts.hog26_scalar_pilot_protocol import build_pilot_plan as original_plan
from scripts.hog26_scalar_pilot_protocol import (
    source_fingerprint as original_fingerprint,
)

ROLE = "train-scalar-expanded-support"
SEEDS = (1280101, 1280102, 1280103)
PLAN_PATHS = (
    "reports/hog26_scalar_birthfixed_frozen_plan_20260911.json",
    "reports/hog26_scaling_frozen_plan_20260912.json",
    "reports/hog26_seed_transfer_frozen_plan_20260911.json",
)
COMPLETE_PATHS = (
    "datasets/derived/hog26_scalar_birthfixed_pilot_seed1279261_20260911/complete.json",
    "datasets/derived/hog26_scaling_train_seed1279701_20260912/complete.json",
    "datasets/derived/hog26_seed_transfer_seed1279601_20260911/complete.json",
    "datasets/derived/hog26_scaling_preflight_20260912/complete.json",
    "datasets/derived/hog26_scalar_preflight_20260911/complete.json",
    "datasets/derived/hog26_scalar_preflight_final_20260911/complete.json",
    "datasets/derived/hog26_scalar_birthfixed_preflight_20260911/complete.json",
    "datasets/derived/hog26_seed_transfer_preflight_20260911/complete.json",
    "datasets/derived/hog26_scalar_handfixed_preflight_20260911/complete.json",
)


def source_fingerprint(root, *, resource_paths, vocabulary_sha256, card_definitions):
    root = Path(root)
    paths = dict(resource_paths)
    for relative in (*PLAN_PATHS, *COMPLETE_PATHS,
                     "reports/hog26_training_expansion_draft_20260913.json"):
        paths[relative] = root / relative
    for directory in ("hog26_training_expansion", "hog26_scalar_pilot"):
        for path in (root / "experiments" / directory).glob("*.py"):
            paths[str(path.relative_to(root))] = path
    return original_fingerprint(root, resource_paths=paths, vocabulary_sha256=vocabulary_sha256,
                                card_definitions=card_definitions)


def build_pilot_plan(*, authority, preflight=None):
    result = original_plan(authority=authority, preflight=preflight)
    previous = [json.loads(Path(authority["resources"][path]["path"]).read_text()) for path in PLAN_PATHS]
    old_clusters = set()
    for plan in previous:
        for schedule in plan["schedules"]:
            old_clusters.update(s.cluster_id for s in audit_scalar_opening_metadata(
                schedule["metadata"], expected_authority=schedule["external_authority"]))
    for relative in COMPLETE_PATHS:
        complete = json.loads(Path(authority["resources"][relative]["path"]).read_text())
        old_clusters.update(row["cluster_id"] for row in complete["games"])
    if preflight is not None:
        clusters = preflight.get("preflight_clusters", [])
        if len(clusters) != 6 or len(set(clusters)) != 6:
            raise ValueError("six independently audited excluded preflight clusters required")
        old_clusters.update(clusters)
    new_clusters = set()
    for index, schedule in enumerate(result["schedules"]):
        pin = copy.deepcopy(schedule["external_authority"])
        pin.update(role=ROLE, episodes=12, campaign_seed=str(SEEDS[index // 64]))
        metadata = CanonicalOpeningSchedule(
            campaign_seed=int(pin["campaign_seed"]), role=ROLE, deck_name=pin["deck_name"],
            opponent_style=pin["opponent_style"], learner_template=pin["relative_templates"][0],
            opponent_template=pin["relative_templates"][1], canonical_names=pin["canonical_names"], episodes=12).metadata()
        for scenario in audit_scalar_opening_metadata(metadata, expected_authority=pin):
            if scenario.cluster_id in old_clusters | new_clusters:
                raise ValueError("expanded training repeats an earlier relative deal")
            new_clusters.add(scenario.cluster_id)
        schedule.update(external_authority=pin, metadata=metadata)
    if len(new_clusters) != 2304 or result["requirements"] != previous[0]["requirements"]:
        raise ValueError("expansion quota or preserved requirements changed")
    result.update(expected_natural_games=4608, independent_paired_scenarios=2304,
                  existing_training_games=1536, combined_training_games=6144,
                  extension_scope="Unfiltered complete training games only; no automatic fitting or promotion.",
                  previous_training_plan_sha256=[digest(previous[0]), digest(previous[1])])
    return result


def validate_pilot_plan(plan, current_authority, *, expected_preflight=None):
    assert_source_unchanged(plan.get("source_authority"), current_authority)
    if plan != build_pilot_plan(authority=current_authority, preflight=expected_preflight):
        raise ValueError("training expansion differs from fixed external contract")
    return {"status": "valid-frozen" if expected_preflight else "valid-draft", "natural_games": 4608,
            "collection_allowed": expected_preflight is not None}


def preflight_schedules(plan):
    result = []
    for style_index, deck_index in enumerate((0, 13, 20, 8, 24, 28)):
        selected = plan["schedules"][style_index * 32 + deck_index]
        pin = dict(selected["external_authority"])
        pin.update(role="diagnostic-training-expansion-preflight", campaign_seed=str(1280141 + style_index), episodes=1)
        metadata = CanonicalOpeningSchedule(
            campaign_seed=int(pin["campaign_seed"]), role=pin["role"], deck_name=pin["deck_name"],
            opponent_style=pin["opponent_style"], learner_template=pin["relative_templates"][0],
            opponent_template=pin["relative_templates"][1], canonical_names=pin["canonical_names"], episodes=1).metadata()
        result.append({**selected, "external_authority": pin, "metadata": metadata})
    return result
