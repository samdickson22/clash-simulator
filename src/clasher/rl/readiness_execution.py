"""Pinned execution inputs for the readiness-v2 development runner.

Capture files remain read-only. Fresh acceptance execution is deliberately not
implemented until its capture/exposure ownership binding is installed.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from pathlib import Path
from typing import Annotated, Any, Literal

import numpy as np
from pydantic import Field, model_validator

from .public_observation import ConfidenceAwareActorObservation
from .readiness_tier_b import TierBProtocol
from .training_readiness_v2 import (
    CONDITIONS,
    ROLES,
    SHA,
    Engine,
    Protocol,
    Record,
    Role,
)

CAPTURE_FILES = (
    "plan.json",
    "initial.json",
    "result.json",
    "native-frames.jsonl.gz",
    "gamedata.json",
)


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def packet_sha(packet: Any) -> str:
    def plain(value: Any) -> Any:
        if dataclasses.is_dataclass(value):
            return {
                field.name: plain(getattr(value, field.name))
                for field in dataclasses.fields(value)
            }
        if isinstance(value, np.ndarray):
            return {
                "dtype": str(value.dtype),
                "shape": list(value.shape),
                "values": value.tolist(),
            }
        if isinstance(value, np.generic):
            return value.item()
        if isinstance(value, dict):
            return {str(key): plain(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [plain(item) for item in value]
        return value

    return canonical_sha(plain(packet))


class CaptureBinding(Record):
    family_id: str = Field(min_length=1)
    capture_path: str = Field(min_length=1)
    root_tick: int = Field(ge=90, lt=6001)
    input_hashes: dict[str, SHA]
    config_sha256: SHA
    root_frame_sha256: SHA

    @model_validator(mode="after")
    def required_files(self) -> CaptureBinding:
        if set(self.input_hashes) != set(CAPTURE_FILES):
            raise ValueError("all capture inputs must be pinned")
        return self

    @property
    def root_sha256(self) -> str:
        return canonical_sha(
            {
                "config_sha256": self.config_sha256,
                "root_tick": self.root_tick,
                "root_frame_sha256": self.root_frame_sha256,
            }
        )

    def verify_files(self) -> None:
        capture = Path(self.capture_path)
        for relative, digest in self.input_hashes.items():
            if file_sha(capture / relative) != digest:
                raise ValueError(f"capture input changed: {relative}")
        if (
            canonical_sha(json.loads((capture / "plan.json").read_text())["config"])
            != self.config_sha256
        ):
            raise ValueError("capture config differs from root binding")


class ExecutionPlan(Record):
    schema_version: Literal["readiness-v2-execution-v1"] = "readiness-v2-execution-v1"
    # Tier A plans serialize exactly as before; Tier B plans are distinguished
    # by the protocol schema version and the ``tier_b_transfer`` purpose.
    protocol: Annotated[
        Protocol | TierBProtocol, Field(discriminator="schema_version")
    ]
    captures: tuple[CaptureBinding, ...]
    catalog_path: str
    catalog_sha256: SHA
    native_attestation_sha256: SHA | None = None
    source_pins: dict[str, SHA]
    repetitions: int = Field(default=1, ge=1, le=16)
    engines: tuple[Engine, ...] = ("scalar", "reference")
    selected_conditions: tuple[str, ...] = CONDITIONS
    selected_roles: tuple[Role, ...] = ROLES
    purpose: Literal[
        "development_coverage",
        "identical_repetition",
        "fresh_acceptance",
        "tier_b_transfer",
    ]

    @model_validator(mode="after")
    def bindings(self) -> ExecutionPlan:
        if (
            not self.selected_conditions
            or len(set(self.selected_conditions)) != len(self.selected_conditions)
            or not set(self.selected_conditions) <= set(CONDITIONS)
            or not self.selected_roles
            or len(set(self.selected_roles)) != len(self.selected_roles)
        ):
            raise ValueError(
                "selected conditions and roles must be distinct declared cases"
            )
        if self.purpose != "identical_repetition" and (
            self.selected_conditions != CONDITIONS or self.selected_roles != ROLES
        ):
            raise ValueError("coverage and acceptance require all conditions and roles")
        if not self.engines or len(set(self.engines)) != len(self.engines):
            raise ValueError("distinct declared engines required")
        if {c.family_id for c in self.captures} != {
            f.family_id for f in self.protocol.families
        } or len(self.captures) != len(self.protocol.families):
            raise ValueError("exactly one capture binding per family required")
        if not self.captures:
            raise ValueError("at least one captured root required")
        if not self.source_pins:
            raise ValueError("execution sources must be pinned")
        for binding in self.captures:
            family = next(
                f for f in self.protocol.families if f.family_id == binding.family_id
            )
            if binding.root_sha256 != family.root_sha256:
                raise ValueError("root binding differs from family declaration")
        if self.purpose == "identical_repetition" and self.repetitions < 2:
            raise ValueError("identical repetition study needs at least two executions")
        if self.purpose != "identical_repetition" and self.repetitions != 1:
            raise ValueError("only repetition studies may repeat branches")
        if (self.purpose == "tier_b_transfer") != isinstance(
            self.protocol, TierBProtocol
        ):
            raise ValueError("Tier B protocols execute only under the Tier B purpose")
        if self.purpose in ("fresh_acceptance", "tier_b_transfer"):
            if self.protocol.status != "frozen":
                raise ValueError("fresh execution requires a frozen protocol")
        elif any(f.role != "opened_development" for f in self.protocol.families):
            raise ValueError(
                "development execution requires opened-development families"
            )
        if "reference" in self.engines and self.native_attestation_sha256 is None:
            raise ValueError("native attestation must be pinned before execution")
        return self

    def verify_inputs(self) -> None:
        for path, digest in self.source_pins.items():
            if file_sha(Path(path)) != digest:
                raise ValueError(f"execution source changed: {path}")
        if file_sha(Path(self.catalog_path)) != self.catalog_sha256:
            raise ValueError("projectile catalog changed")
        for capture in self.captures:
            capture.verify_files()


class Job(Record):
    family_id: str
    condition: str
    candidate_role: Role
    engine: Engine
    repetition: int = Field(ge=0)
    execution_sha256: SHA


def jobs(plan: ExecutionPlan) -> tuple[Job, ...]:
    """Repetition index is excluded from the identical-execution identity."""
    result = []
    for family in plan.protocol.families:
        binding = next(c for c in plan.captures if c.family_id == family.family_id)
        for condition in plan.selected_conditions:
            for candidate in family.candidates:
                if candidate.role not in plan.selected_roles:
                    continue
                for engine in plan.engines:
                    identity = canonical_sha(
                        {
                            "family": family.model_dump(mode="json"),
                            "capture": binding.model_dump(mode="json"),
                            "condition": condition,
                            "candidate": candidate.model_dump(mode="json"),
                            "engine": engine,
                            "source_pins": plan.source_pins,
                            "catalog_sha256": plan.catalog_sha256,
                            "native_attestation_sha256": plan.native_attestation_sha256,
                            "decision_interval_ticks": 5,
                        }
                    )
                    for repetition in range(plan.repetitions):
                        result.append(
                            Job(
                                family_id=family.family_id,
                                condition=condition,
                                candidate_role=candidate.role,
                                engine=engine,
                                repetition=repetition,
                                execution_sha256=identity,
                            )
                        )
    return tuple(result)


def require_development_execution(plan: ExecutionPlan) -> None:
    if plan.purpose in ("fresh_acceptance", "tier_b_transfer"):
        raise ValueError(
            "fresh execution requires the future v2 capture/exposure ownership adapter; planning only"
        )
    for binding in plan.captures:
        capture = Path(binding.capture_path)
        metadata = json.loads((capture / "plan.json").read_text())
        result = json.loads((capture / "result.json").read_text())
        if metadata.get("role") != "development":
            raise ValueError(
                "opened development runner cannot consume acceptance captures"
            )
        if (
            result.get("failure") is not None
            or result.get("producer_sources_unchanged") is not True
        ):
            raise ValueError("capture producer failed or source identity changed")


def decision_ticks(root_tick: int) -> range:
    if type(root_tick) is not int or not 90 <= root_tick < 6001:
        raise ValueError("root must lie in the playable decision window")
    return range(root_tick, 6001, 5)


def condition_styles(condition: str, root_owner: int) -> tuple[str, str]:
    if (
        condition not in CONDITIONS
        or type(root_owner) is not int
        or root_owner not in (0, 1)
    ):
        raise ValueError("undeclared continuation condition or root owner")
    owner_style, other_style = condition.split("/")
    return (owner_style, other_style) if root_owner == 0 else (other_style, owner_style)


def public_v4_structure_valid(packet: ConfidenceAwareActorObservation) -> bool:
    """Unknown level values are valid when explicitly paired with zero confidence.

    Packet validation enforces shape, dtype and value/confidence consistency.
    Channel calibration and how many levels were measured are separate claims.
    """
    packet.validate()
    actor = packet.observation
    return (
        packet.schema_version == 4
        and actor.entity_levels is not None
        and actor.entity_level_confidence is not None
        and actor.hand_levels is not None
        and actor.hand_level_confidence is not None
    )
