"""Externally pinned scalar pilot schedule. Building a draft grants no run permission."""

import copy
import hashlib
import json
import platform
from pathlib import Path

import numpy as np
import torch

from clasher.card_aliases import resolve_card_name
from scripts.hog26_scalar_opening_audit import audit_scalar_opening_metadata
from scripts.hog26_scalar_openings import CanonicalOpeningSchedule, digest

MANIFEST = "training_decks/hog26_procedural_supported_seed1278401.json"
PROTOCOL = "reports/hog26_procedural_outcome_protocol_reassessed_20260908.json"
LEARNER = ("HogRider", "Musketeer", "IceGolem", "Skeletons", "IceSpirits", "Cannon", "Fireball", "Log")
CAMPAIGNS = ((1279261, ("balanced", "random")),
             (1279262, ("bridge-pressure", "reactive-defense")),
             (1279263, ("slow-push", "spell-control")))
INHERITED = ("gates", "generalization_evaluation", "opponent_generalization")


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _requirements(protocol):
    result = {key: copy.deepcopy(protocol[key]) for key in INHERITED}
    result["replication"] = {key: protocol["replication"][key] for key in ("rule", "counterfactual_rule")}
    # Preserve role budgets and seeds; historical corpus paths are never run permissions.
    def role(value):
        return {key: copy.deepcopy(value[key]) for key in (
            "family_ids", "expected_games", "episodes_per_seat", "opponents", "seed", "deck",
            "battles", "physical_games", "actor_views", "episodes_per_battle", "scope",
        ) if key in value}
    result["reserved_roles"] = {
        "selection": role(protocol["development_selection"]),
        "calibration": role(protocol["probability_calibration"]),
        "final_generated": role(protocol["final_holdout"]["generated"]),
        "final_original": role(protocol["final_holdout"]["reserved_original"]),
        "final_draw": role(protocol["final_holdout"]["controlled_draw"]),
        "training_draw": role(protocol["corrected_draw_controls"]["training"]),
        "validation_draw": role(protocol["corrected_draw_controls"]["validation"]),
    }
    result["reserved_collection_allowed"] = False
    result["draw_scope"] = "Controlled symmetry only; never substitute for natural draw calibration."
    return result


def source_fingerprint(root, *, resource_paths, vocabulary_sha256, card_definitions):
    """Call independently before and after a run; never reconstruct pins from run output.

    Required resources: checkpoint and card_data. Manifest and inherited protocol
    are fixed workspace paths. All Python under src/clasher and scripts is included,
    including untracked files. Adding, removing or changing any file invalidates it.
    """
    root = Path(root).resolve()
    resources = dict(resource_paths)
    if not {"checkpoint", "card_data"} <= resources.keys():
        raise ValueError("checkpoint and card_data resources are required")
    resources = {key: Path(path) if Path(path).is_absolute() else root / path
                 for key, path in resources.items()}
    resources.update(manifest=root / MANIFEST, inherited_protocol=root / PROTOCOL)
    if torch.get_num_threads() != 1:
        raise ValueError("scalar pilot requires actual torch thread count one")
    paths = sorted(p for directory in (root / "src/clasher", root / "scripts")
                   for p in directory.rglob("*.py") if p.is_file())
    if not paths:
        raise ValueError("empty source inventory")
    manifest = json.loads((root / MANIFEST).read_text())
    protocol = json.loads((root / PROTOCOL).read_text())
    def canonical(cards):
        values = [resolve_card_name(c, card_definitions) for c in cards]
        if any(c not in card_definitions for c in values):
            raise ValueError("manifest has unresolved canonical card names")
        return values

    decks = [{"name": d["name"], "family_id": d.get("family_id"), "split": d.get("split"),
              "cards": canonical(d["cards"])} for d in manifest["decks"]]
    return {
        "schema": "clasher.scalar-pilot-source.v1",
        "sources": {str(p.relative_to(root)): _sha(p) for p in paths},
        "resources": {key: {"path": str(Path(path).resolve()), "sha256": _sha(path)}
                      for key, path in sorted(resources.items())},
        "vocabulary_sha256": vocabulary_sha256,
        "runtime": {"python": platform.python_version(), "numpy": np.__version__,
                    "torch": torch.__version__, "device": "cpu", "torch_threads": 1},
        "contract": {"decks": decks, "learner_template": canonical(LEARNER),
                     "canonical_names": sorted({c for d in decks for c in d["cards"]} | set(canonical(LEARNER))),
                     "requirements": _requirements(protocol)},
    }


def assert_source_unchanged(expected, current):
    if expected != current:
        raise ValueError("scalar pilot source/resource/runtime authority changed")


def build_pilot_plan(*, authority, preflight=None):
    """Return a draft dictionary; caller must separately complete and pin preflight."""
    if preflight is not None and (
        type(preflight) is not dict or preflight.get("status") != "passed"
        or preflight.get("source_authority_sha256") != digest(authority)
        or not preflight.get("evidence")
    ):
        raise ValueError("preflight must pin reviewed evidence and the exact source authority")
    contract = authority["contract"]
    decks = [d for d in contract["decks"] if d["split"] == "train"]
    families = {f"family-{i:03d}" for i in range(8)}
    if (len(decks) != 32 or {d["family_id"] for d in decks} != families
            or any(sum(d["family_id"] == f for d in decks) != 4 for f in families)
            or len({d["name"] for d in decks}) != 32):
        raise ValueError("pilot requires all 32 original training-family decks")
    schedules = []
    for seed, styles in CAMPAIGNS:
        for style in styles:
            for deck in decks:
                pin = {"version": "clasher.scalar-canonical-opening.v1", "campaign_seed": str(seed),
                       "role": "train", "deck_name": deck["name"], "opponent_style": style,
                       "relative_templates": [contract["learner_template"], deck["cards"]],
                       "episodes": 1, "canonical_names": contract["canonical_names"]}
                metadata = CanonicalOpeningSchedule(
                    campaign_seed=seed, role="train", deck_name=deck["name"], opponent_style=style,
                    learner_template=pin["relative_templates"][0], opponent_template=deck["cards"],
                    canonical_names=pin["canonical_names"], episodes=1,
                ).metadata()
                audit_scalar_opening_metadata(metadata, expected_authority=pin)
                schedules.append({"family_id": deck["family_id"], "external_authority": pin,
                                  "metadata": metadata, "learner_seats": [0, 1]})
    return {"schema": "clasher.scalar-outcome-pilot.v1", "source_authority": copy.deepcopy(authority),
            "source_authority_sha256": digest(authority),
            "readiness": "draft" if preflight is None else "frozen",
            "frozen": preflight is not None,
            "collection_allowed": preflight is not None, "fitting_allowed": False,
            "policy_updates_allowed": False, "search_allowed": False,
            "expected_natural_games": 384, "independent_paired_scenarios": 192,
            "schedules": schedules, "requirements": copy.deepcopy(contract["requirements"]),
            "historical_corpus_use": "diagnostics only; excluded from scalar fitting",
            "labels": "undiscounted terminal W/D/L and terminal tower margin; complete games only",
            "margin_definition": "mean(own_three_tower_remaining_hp / own_three_tower_initial_hp) - "
                                 "mean(enemy_three_tower_remaining_hp / enemy_three_tower_initial_hp)",
            "actor_contract": "public observations only; critic inputs and outcome labels excluded",
            "preflight": copy.deepcopy(preflight)}


def validate_pilot_plan(plan, current_authority, *, expected_preflight=None):
    """Fail closed against separately constructed current pins, not self-reported hashes."""
    assert_source_unchanged(plan.get("source_authority"), current_authority)
    expected = build_pilot_plan(authority=current_authority, preflight=expected_preflight)
    if plan != expected:
        raise ValueError("pilot plan differs from externally pinned draft contract")
    return {"status": "valid-draft" if expected_preflight is None else "valid-frozen",
            "natural_games": 384, "collection_allowed": expected_preflight is not None}
