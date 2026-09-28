"""Frozen input checks for prospective reference collection, never gate admission."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .calibration_decisions import DecisionCriteria
from .calibration_families import require_unopened_acceptance
from .native_match_registry import canonical_digest

Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


def collection_sources(root: Path) -> list[Path]:
    return sorted((root / "src/clasher").rglob("*.py")) + [
        root / "scripts" / name
        for name in (
            "collect_native_public_game.py",
            "read_native_public_levels.py",
            "smoke_reference_battle.py",
            "collect_public_development_games.py",
            "select_reacting_public_root.py",
            "prepare_prospective_branch.py",
            "evaluate_prospective_calibration.py",
            "run_prospective_calibration.py",
            "run_calibration_job.py",
            "audit_native_public_boundary.py",
            "compare_reacting_public_branches.py",
        )
    ]


class FrozenCollectionProtocol(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    schema_version: Literal[1] = 1
    status: Literal["frozen"]
    source_domain: Literal["pinned-native-reference"]
    game_build: Literal["15.535.86"]
    ruleset_sha256: Digest
    catalog_sha256: Digest
    native_attestation_sha256: Digest
    family_manifest_path: str = Field(min_length=1)
    reference_criteria_path: str = Field(min_length=1)
    decision_criteria_path: str = Field(min_length=1)
    family_manifest_sha256: Digest
    reference_criteria_sha256: Digest
    decision_criteria_sha256: Digest
    source_files: dict[str, Digest] = Field(min_length=1)
    families: dict[str, tuple[Digest, ...]] = Field(min_length=1)
    public_opponent_seat: Literal[0, 1]
    public_opponent_style: Literal["balanced", "pressure"]
    decision_stride: Literal[30]
    command_delay: Literal[1]
    startup_wait_ticks: Literal[90]
    max_tick: Literal[6001]
    root_start_ticks: dict[Digest, Literal[90, 900, 1800, 2700]]
    root_selection_mode: Literal["first-in-window", "seeded-play-event"] = (
        "first-in-window"
    )
    root_event_seeds: dict[Digest, Annotated[int, Field(ge=0)]] = Field(
        default_factory=dict
    )
    branch_window_ticks: Literal[300, 5910]
    branch_response_seed: int = Field(ge=0)
    branch_other_style: Literal["pressure"]
    branch_x_offsets: tuple[Literal[-1], Literal[1]]
    branch_include_delay_one: Literal[True]
    collection_only: Literal[True]

    @model_validator(mode="after")
    def disjoint_families(self):
        members = [r for roots in self.families.values() for r in roots]
        if any(not roots for roots in self.families.values()) or len(members) != len(
            set(members)
        ):
            raise ValueError("empty or duplicate prospective family membership")
        if set(self.root_start_ticks) != set(members):
            raise ValueError(
                "root windows must cover exactly all frozen configurations"
            )
        if self.root_selection_mode == "seeded-play-event":
            if (
                set(self.root_event_seeds) != set(members)
                or self.branch_window_ticks != 5910
                or any(t != 90 for t in self.root_start_ticks.values())
            ):
                raise ValueError(
                    "event sampling requires a seed for every root and the full playable window"
                )
        elif self.root_event_seeds:
            raise ValueError("window selection cannot carry unused event seeds")
        return self


class FrozenReferenceCriteria(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    status: Literal["frozen"]
    source_domain: Literal["pinned-native-reference"]
    verifier: Literal["public-reference-v1"]
    ruleset_sha256: Digest
    cards: tuple[str, ...] = Field(min_length=1)
    level: Literal[11]
    base_forms_only: Literal[True]
    metadata_version: Literal[4]
    maximum_entities: Literal[128]
    maximum_failures: Literal[0]
    camera_calibrated: Literal[False]


class FrozenDecisionCriteria(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    status: Literal["frozen"]
    criteria: DecisionCriteria
    baseline: Literal["recorded"]
    selected_tie_rule: Literal["worst-native-outcome"]
    missing_root_rule: Literal["family-failure-no-substitution"]
    maximum_bad_families: Literal[0]
    maximum_regression_families: Literal[0]


def verify_protocol_documents(protocol, directory):
    documents = {}
    for kind in ("family_manifest", "reference_criteria", "decision_criteria"):
        relative = Path(getattr(protocol, kind + "_path"))
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("protocol document must be a relative bundled path")
        encoded = (directory / relative).read_bytes()
        if hashlib.sha256(encoded).hexdigest() != getattr(protocol, kind + "_sha256"):
            raise ValueError(f"frozen {kind} changed")
        documents[kind] = encoded
    reference = FrozenReferenceCriteria.model_validate_json(
        documents["reference_criteria"]
    )
    decision = FrozenDecisionCriteria.model_validate_json(
        documents["decision_criteria"]
    )
    if reference.ruleset_sha256 != protocol.ruleset_sha256:
        raise ValueError("reference criteria ruleset differs")
    if len(reference.cards) != len(set(reference.cards)):
        raise ValueError("duplicate reference card")
    manifest = json.loads(documents["family_manifest"])
    if manifest.get("status") != "frozen":
        raise ValueError("family manifest is not frozen")
    families = {}
    for family in manifest["families"]:
        name = family["family_id"]
        if name in families:
            raise ValueError("duplicate manifest family")
        roots = []
        for item in family["configurations"]:
            config_digest = canonical_digest(item["config"])
            if item["root_id"] != "native-root-v1:" + config_digest:
                raise ValueError("manifest root identity differs from configuration")
            if any(
                card not in reference.cards for deck in item["decks"] for card in deck
            ):
                raise ValueError("manifest deck outside reference scope")
            if (
                family.get("root_selection_start_tick")
                != protocol.root_start_ticks[config_digest]
            ):
                raise ValueError("manifest root window differs from protocol")
            if (
                protocol.root_selection_mode == "seeded-play-event"
                and item.get("root_selection_seed")
                != protocol.root_event_seeds[config_digest]
            ):
                raise ValueError("manifest event seed differs from protocol")
            roots.append(config_digest)
        families[name] = tuple(roots)
    if families != protocol.families:
        raise ValueError("manifest families differ from frozen protocol")
    if len(families) < decision.criteria.minimum_families:
        raise ValueError("manifest lacks the declared family sample size")
    return reference, decision


def verify_collection_protocol(
    path: Path,
    *,
    workspace: Path,
    registry: Path,
    family_id: str,
    config: dict,
    gamedata: Path,
    catalog: Path,
    opponent_seat,
    opponent_style,
):
    """Validate before configuring native state. This does not open outcomes."""
    encoded = path.read_bytes()
    protocol = FrozenCollectionProtocol.model_validate_json(encoded)
    digest = hashlib.sha256(encoded).hexdigest()
    verify_protocol_documents(protocol, path.parent)
    expected_paths = {
        str(p.relative_to(workspace)) for p in collection_sources(workspace)
    }
    if set(protocol.source_files) != expected_paths:
        raise ValueError("frozen producer source inventory differs")
    for name, expected in protocol.source_files.items():
        if hashlib.sha256((workspace / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"frozen producer changed: {name}")
    for p, expected in (
        (gamedata, protocol.ruleset_sha256),
        (catalog, protocol.catalog_sha256),
    ):
        if hashlib.sha256(p.read_bytes()).hexdigest() != expected:
            raise ValueError("frozen ruleset or catalog changed")
    if (
        opponent_seat != protocol.public_opponent_seat
        or opponent_style != protocol.public_opponent_style
    ):
        raise ValueError("controller differs from frozen protocol")
    config_digest = canonical_digest(config)
    if config_digest not in protocol.families.get(family_id, ()):
        raise ValueError("configuration is not a frozen family member")
    family = require_unopened_acceptance(registry, family_id, digest)
    declared = tuple(
        sorted("native-root-v1:" + d for d in protocol.families[family_id])
    )
    if family.root_ids != declared:
        raise ValueError("ledger family differs from frozen protocol")
    return protocol, family, digest
