"""Immutable calibration families and irreversible exposure records.

Related configurations must be declared together before collection. This ledger
prevents reassignment of known members; it cannot discover undeclared match
dependencies and is not an acceptance evaluator.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .native_match_registry import NativeRootRecord, Role, canonical_digest


class CalibrationFamily(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    family_id: str = Field(min_length=1)
    role: Role
    protocol_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    root_ids: tuple[
        Annotated[str, Field(pattern=r"^native-root-v1:[0-9a-f]{64}$")], ...
    ] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_roots(self):
        if len(set(self.root_ids)) != len(self.root_ids):
            raise ValueError("duplicate family member")
        return self


def _schema(db):
    db.execute(
        "CREATE TABLE IF NOT EXISTS native_roots (group_id TEXT PRIMARY KEY, record TEXT NOT NULL)"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS calibration_families (family_id TEXT PRIMARY KEY, record TEXT NOT NULL)"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS calibration_members (root_id TEXT PRIMARY KEY, family_id TEXT NOT NULL)"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS calibration_exposures (event_id INTEGER PRIMARY KEY, family_id TEXT NOT NULL, purpose TEXT NOT NULL, evidence_sha256 TEXT NOT NULL)"
    )


def register_family(
    path: Path,
    configs: list[dict],
    *,
    family_id: str,
    role: Role,
    protocol_sha256: str,
) -> CalibrationFamily:
    """Atomically freeze a declared family and all exact-root roles.

    Only development may adopt roots that predate family registration. A caller
    cannot turn an old untracked root into a fresh acceptance family. Existing
    family membership is immutable, even if only another seat changes.
    """
    roots = []
    for config in configs:
        if type(config.get("rndSeed")) is not int or not isinstance(
            config.get("battle"), dict
        ):
            raise ValueError("explicit native seed and battle configuration required")
        digest = canonical_digest(config)
        roots.append(
            NativeRootRecord(
                duplicate_group_id=f"native-root-v1:{digest}",
                config_sha256=digest,
                role=role,
            )
        )
    family = CalibrationFamily(
        family_id=family_id,
        role=role,
        protocol_sha256=protocol_sha256,
        root_ids=tuple(sorted(r.duplicate_group_id for r in roots)),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path, timeout=30) as db:
        _schema(db)
        db.execute("BEGIN IMMEDIATE")
        prior = db.execute(
            "SELECT record FROM calibration_families WHERE family_id=?", (family_id,)
        ).fetchone()
        if prior:
            if CalibrationFamily.model_validate_json(prior[0]) != family:
                raise ValueError("family assignment is immutable")
            return family
        for root in roots:
            member = db.execute(
                "SELECT family_id FROM calibration_members WHERE root_id=?",
                (root.duplicate_group_id,),
            ).fetchone()
            if member:
                raise ValueError(f"root already belongs to family {member[0]}")
            old = db.execute(
                "SELECT record FROM native_roots WHERE group_id=?",
                (root.duplicate_group_id,),
            ).fetchone()
            if old:
                if NativeRootRecord.model_validate_json(old[0]) != root:
                    raise ValueError("root already assigned to a different role")
                if role != "development":
                    raise ValueError(
                        "previously registered root lacks prospective family provenance"
                    )
            else:
                db.execute(
                    "INSERT INTO native_roots VALUES (?, ?)",
                    (root.duplicate_group_id, root.model_dump_json()),
                )
            db.execute(
                "INSERT INTO calibration_members VALUES (?, ?)",
                (root.duplicate_group_id, family_id),
            )
        db.execute(
            "INSERT INTO calibration_families VALUES (?, ?)",
            (family_id, family.model_dump_json()),
        )
    return family


class FamilyExposure(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    family_id: str = Field(min_length=1)
    purpose: Literal["evaluation", "repair", "selection", "training"]
    evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


def record_exposure(path: Path, exposure: FamilyExposure) -> None:
    """Record opening labels before inspection; never erase or reset exposure.

    Evaluation consumes freshness too. Its frozen result may subsequently be
    assessed, but the family cannot be presented as a new unopened holdout.
    Acceptance families remain excluded from training even after a failed test.
    """
    with sqlite3.connect(path, timeout=30) as db:
        _schema(db)
        db.execute("BEGIN IMMEDIATE")
        row = db.execute(
            "SELECT record FROM calibration_families WHERE family_id=?",
            (exposure.family_id,),
        ).fetchone()
        if row is None:
            raise ValueError("unregistered family")
        family = CalibrationFamily.model_validate_json(row[0])
        if family.role == "acceptance" and exposure.purpose == "training":
            raise ValueError("acceptance families cannot enter training")
        db.execute(
            "INSERT INTO calibration_exposures (family_id, purpose, evidence_sha256) VALUES (?, ?, ?)",
            (exposure.family_id, exposure.purpose, exposure.evidence_sha256),
        )


def require_unopened_acceptance(
    path: Path, family_id: str, protocol_sha256: str
) -> CalibrationFamily:
    """Check provenance only; this does not pass calibration or permit training."""
    with sqlite3.connect(path, timeout=30) as db:
        _schema(db)
        row = db.execute(
            "SELECT record FROM calibration_families WHERE family_id=?", (family_id,)
        ).fetchone()
        if row is None:
            raise ValueError("unregistered family")
        family = CalibrationFamily.model_validate_json(row[0])
        if family.role != "acceptance" or family.protocol_sha256 != protocol_sha256:
            raise ValueError("acceptance role and frozen protocol must match")
        if db.execute(
            "SELECT 1 FROM calibration_exposures WHERE family_id=? LIMIT 1",
            (family_id,),
        ).fetchone():
            raise ValueError(
                "opened family is permanently ineligible as fresh acceptance"
            )
        return family


def require_development_member(
    path: Path, family_id: str, root_id: str
) -> CalibrationFamily:
    """Validate the ledger assignment used by an opened development report."""
    with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True) as db:
        row = db.execute(
            "SELECT record FROM calibration_families WHERE family_id=?", (family_id,)
        ).fetchone()
        if row is None:
            raise ValueError("unregistered development family")
        family = CalibrationFamily.model_validate_json(row[0])
        if family.role != "development" or root_id not in family.root_ids:
            raise ValueError("root is not a declared development member")
        member = db.execute(
            "SELECT family_id FROM calibration_members WHERE root_id=?", (root_id,)
        ).fetchone()
        if member is None or member[0] != family_id:
            raise ValueError("family membership ledger is inconsistent")
        return family


def claim_acceptance_collection(
    path: Path, *, family_id: str, root_id: str, protocol_sha256: str, output_path: Path
) -> None:
    """Reserve exactly one attempt per root, including failed/partial attempts."""
    with sqlite3.connect(path, timeout=30) as db:
        _schema(db)
        db.execute(
            "CREATE TABLE IF NOT EXISTS calibration_collections (root_id TEXT PRIMARY KEY, family_id TEXT NOT NULL, protocol_sha256 TEXT NOT NULL, output_path TEXT NOT NULL)"
        )
        db.execute("BEGIN IMMEDIATE")
        row = db.execute(
            "SELECT record FROM calibration_families WHERE family_id=?", (family_id,)
        ).fetchone()
        if row is None:
            raise ValueError("unregistered acceptance family")
        family = CalibrationFamily.model_validate_json(row[0])
        if (
            family.role != "acceptance"
            or family.protocol_sha256 != protocol_sha256
            or root_id not in family.root_ids
        ):
            raise ValueError("acceptance collection assignment mismatch")
        if db.execute(
            "SELECT 1 FROM calibration_exposures WHERE family_id=? LIMIT 1",
            (family_id,),
        ).fetchone():
            raise ValueError("opened family cannot start acceptance collection")
        if db.execute(
            "SELECT 1 FROM calibration_collections WHERE root_id=?", (root_id,)
        ).fetchone():
            raise ValueError(
                "acceptance root already attempted; do not silently recollect"
            )
        db.execute(
            "INSERT INTO calibration_collections VALUES (?, ?, ?, ?)",
            (root_id, family_id, protocol_sha256, str(output_path.resolve())),
        )


def require_collection_claim(
    path: Path,
    *,
    family_id: str,
    root_id: str,
    protocol_sha256: str,
    capture_path: Path,
) -> None:
    """Reject relabeled or copied input paths without their original reservation."""
    with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True) as db:
        row = db.execute(
            "SELECT family_id, protocol_sha256, output_path FROM calibration_collections WHERE root_id=?",
            (root_id,),
        ).fetchone()
        expected = (family_id, protocol_sha256, str(capture_path.resolve()))
        if row != expected:
            raise ValueError("capture does not match its acceptance collection claim")


def claim_acceptance_branches(
    path: Path,
    *,
    family_id: str,
    root_id: str,
    protocol_sha256: str,
    branch_protocol_sha256: str,
    attempts: list[tuple[str, str]],
    output_path: Path,
) -> None:
    """Reserve the full declared branch batch atomically, including failed work."""
    if (
        not attempts
        or len(set(attempts)) != len(attempts)
        or any(
            not name or engine not in ("native", "scalar") for name, engine in attempts
        )
    ):
        raise ValueError("invalid or duplicate branch attempt")
    with sqlite3.connect(path, timeout=30) as db:
        _schema(db)
        db.execute(
            "CREATE TABLE IF NOT EXISTS calibration_branches (root_id TEXT NOT NULL, candidate TEXT NOT NULL, engine TEXT NOT NULL, family_id TEXT NOT NULL, protocol_sha256 TEXT NOT NULL, branch_protocol_sha256 TEXT NOT NULL, output_path TEXT NOT NULL, PRIMARY KEY(root_id,candidate,engine))"
        )
        db.execute("BEGIN IMMEDIATE")
        row = db.execute(
            "SELECT record FROM calibration_families WHERE family_id=?", (family_id,)
        ).fetchone()
        if row is None:
            raise ValueError("unregistered branch family")
        family = CalibrationFamily.model_validate_json(row[0])
        if (
            family.role != "acceptance"
            or family.protocol_sha256 != protocol_sha256
            or root_id not in family.root_ids
        ):
            raise ValueError("branch family assignment mismatch")
        if db.execute(
            "SELECT 1 FROM calibration_exposures WHERE family_id=? LIMIT 1",
            (family_id,),
        ).fetchone():
            raise ValueError("opened family cannot start acceptance branches")
        collection = db.execute(
            "SELECT family_id,protocol_sha256 FROM calibration_collections WHERE root_id=?",
            (root_id,),
        ).fetchone()
        if collection != (family_id, protocol_sha256):
            raise ValueError("acceptance source was not collected under this protocol")
        prior = db.execute(
            "SELECT DISTINCT branch_protocol_sha256 FROM calibration_branches WHERE root_id=?",
            (root_id,),
        ).fetchall()
        if any(row[0] != branch_protocol_sha256 for row in prior):
            raise ValueError("branch protocol changed between engine attempts")
        for candidate, engine in attempts:
            if db.execute(
                "SELECT 1 FROM calibration_branches WHERE root_id=? AND candidate=? AND engine=?",
                (root_id, candidate, engine),
            ).fetchone():
                raise ValueError(
                    "branch already attempted; do not silently replace results"
                )
            db.execute(
                "INSERT INTO calibration_branches VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    root_id,
                    candidate,
                    engine,
                    family_id,
                    protocol_sha256,
                    branch_protocol_sha256,
                    str(output_path.resolve()),
                ),
            )


def claim_acceptance_evaluation(
    path: Path,
    *,
    families: dict[str, tuple[str, ...]],
    protocol_sha256: str,
    evidence_sha256: str,
) -> None:
    """Atomically mark the complete declared cohort opened before reading utilities."""
    if not families:
        raise ValueError("evaluation requires the complete declared cohort")
    exposure = FamilyExposure(
        family_id=next(iter(families)),
        purpose="evaluation",
        evidence_sha256=evidence_sha256,
    )
    with sqlite3.connect(path, timeout=30) as db:
        _schema(db)
        db.execute("BEGIN IMMEDIATE")
        for family_id, roots in families.items():
            row = db.execute(
                "SELECT record FROM calibration_families WHERE family_id=?",
                (family_id,),
            ).fetchone()
            if row is None:
                raise ValueError("evaluation family was not registered")
            family = CalibrationFamily.model_validate_json(row[0])
            if (
                family.role != "acceptance"
                or family.protocol_sha256 != protocol_sha256
                or family.root_ids != tuple(sorted(roots))
            ):
                raise ValueError("evaluation cohort differs from frozen registration")
            if db.execute(
                "SELECT 1 FROM calibration_exposures WHERE family_id=? LIMIT 1",
                (family_id,),
            ).fetchone():
                raise ValueError("evaluation cohort has already been opened")
        for family_id in families:
            db.execute(
                "INSERT INTO calibration_exposures (family_id,purpose,evidence_sha256) VALUES (?, ?, ?)",
                (family_id, "evaluation", exposure.evidence_sha256),
            )


def require_branch_claims(
    path: Path,
    *,
    family_id: str,
    root_id: str,
    protocol_sha256: str,
    branch_protocol_sha256: str,
    attempts: list[tuple[str, str]],
    output_path: Path,
) -> None:
    """Read completed-attempt bindings after the cohort has been opened for evaluation."""
    with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True) as db:
        expected = (
            family_id,
            protocol_sha256,
            branch_protocol_sha256,
            str(output_path.resolve()),
        )
        for candidate, engine in attempts:
            row = db.execute(
                "SELECT family_id,protocol_sha256,branch_protocol_sha256,output_path FROM calibration_branches WHERE root_id=? AND candidate=? AND engine=?",
                (root_id, candidate, engine),
            ).fetchone()
            if row != expected:
                raise ValueError(
                    "branch artifacts do not match their reserved attempts"
                )
