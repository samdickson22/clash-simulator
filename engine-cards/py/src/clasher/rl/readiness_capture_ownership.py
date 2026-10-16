"""Append-only ownership for prospective readiness-v2 captures and admission.

This ledger never writes historical v7 databases. A pre-capture declaration and
post-prefix seal are distinct identities; branch claims bind both. Failed claims
cannot be retried, redirected, or removed through this API, with one exception
fixed before capture: an attempt declared with ``technical_rerun_policy=
"once_before_result"`` may re-execute, once and at a new path, a branch claim
that recorded no result because of a declared infrastructure failure (or a hard
runner kill). The ledger derives eligibility from the preserved original output
directory; it never trusts a flag. See ``claim_technical_rerun``.
"""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, model_serializer, model_validator

from .public_scripted_opponent import SUPPORTED_CARDS
from .readiness_execution import CaptureBinding, ExecutionPlan, canonical_sha, file_sha
from .training_readiness_v2 import (
    APPROVED_STRATEGY_SHA,
    CONDITIONS,
    ROLES,
    SHA,
    Branch,
    Engine,
    Family,
    MechanismReview,
    Protocol,
    Record,
    Report,
    Role,
    TechnicalRerunSummary,
    evaluate,
)


class EpisodeSpec(Record):
    family_id: str = Field(min_length=1)
    source_episode_id: str = Field(min_length=1)
    config_path: str
    config_file_sha256: SHA
    config_sha256: SHA
    root_request_sha256: SHA
    root_owner: Literal[0, 1]


class AttemptDeclaration(Record):
    attempt_id: str = Field(min_length=1)
    evidence_role: Literal["fresh_acceptance", "opened_development"]
    root_bank_sha256: SHA
    generator_sha256: SHA
    converter_manifest_sha256: SHA
    pre_protocol: Protocol
    native_attestation_sha256: SHA
    gamedata_sha256: SHA
    catalog_sha256: SHA
    workspace_gamedata_sha256: SHA
    source_pins: dict[str, SHA]
    input_pins: dict[str, SHA]
    episodes: tuple[EpisodeSpec, ...]
    historical_registries: tuple[str, ...] = ()
    # Part of the design hash, so it is fixed before capture. "none" (the
    # default) keeps append-only claims with no retries of any kind.
    technical_rerun_policy: Literal["none", "once_before_result"] = "none"

    @model_serializer(mode="wrap")
    def _omit_default_rerun_policy(self, handler: Any) -> Any:
        # Declarations without the field keep their exact serialization and
        # design hash; only an explicit opt-in changes the canonical record.
        data = handler(self)
        if self.technical_rerun_policy == "none":
            data.pop("technical_rerun_policy", None)
        return data

    @model_validator(mode="after")
    def prospective(self) -> AttemptDeclaration:
        if (
            self.pre_protocol.status != "draft"
            or self.pre_protocol.families
            or self.pre_protocol.generation_failures
        ):
            raise ValueError(
                "pre-capture protocol must be an unbound draft without discarded roots"
            )
        if self.pre_protocol.attempt_id != self.attempt_id:
            raise ValueError("attempt identity differs from pre-capture protocol")
        if self.pre_protocol.source_pins != self.source_pins:
            raise ValueError("pre-capture protocol must bind the same source pins")
        if not self.source_pins or not self.input_pins or not self.episodes:
            raise ValueError("source/input pins and episode declarations required")
        for attribute in ("family_id", "source_episode_id", "config_sha256"):
            if len({getattr(e, attribute) for e in self.episodes}) != len(
                self.episodes
            ):
                raise ValueError(f"duplicate declared {attribute}")
        if self.evidence_role == "fresh_acceptance":
            if (
                len(self.episodes) != 32
                or sum(e.root_owner == 0 for e in self.episodes) != 16
            ):
                raise ValueError(
                    "fresh Tier A requires 32 independent, seat-balanced episodes"
                )
            if not self.historical_registries:
                raise ValueError("freshness requires historical registry checks")
            if (
                self.pre_protocol.floors is None
                or self.pre_protocol.scalar_coverage_study_sha256 is None
            ):
                raise ValueError(
                    "development repetition and coverage evidence required before fresh capture"
                )
        if (
            self.gamedata_sha256 not in self.input_pins.values()
            or self.workspace_gamedata_sha256 not in self.input_pins.values()
        ):
            raise ValueError(
                "capture and workspace spell-registry data must both be pinned"
            )
        if self.converter_manifest_sha256 not in self.input_pins.values():
            raise ValueError("converter manifest must be pinned")
        return self

    @property
    def sha256(self) -> str:
        return canonical_sha(self.model_dump(mode="json"))


class EpisodeClaim(Record):
    attempt_id: str
    family_id: str
    source_episode_id: str
    design_sha256: SHA
    config_sha256: SHA
    converter_manifest_sha256: SHA
    native_attestation_sha256: SHA
    nonce: str
    output_path: str


class CaptureReceipt(Record):
    claim_nonce: str
    design_sha256: SHA
    family_id: str
    config_sha256: SHA
    native_attestation_sha256: SHA
    status: Literal["selected", "no_eligible_root", "failed"]
    prefix_complete: bool
    game_complete: Literal[False] = False
    artifact_hashes: dict[str, SHA]
    selected_family: Family | None = None
    capture_binding: CaptureBinding | None = None
    failure: str | None = None

    @model_validator(mode="after")
    def selection(self) -> CaptureReceipt:
        if self.status == "selected":
            if (
                not self.prefix_complete
                or self.selected_family is None
                or self.capture_binding is None
                or self.failure is not None
            ):
                raise ValueError(
                    "selected root requires complete prefix, bindings and no failure"
                )
        elif self.selected_family is not None or self.capture_binding is not None:
            raise ValueError("missing/failed roots cannot contain substitute bindings")
        if self.status == "failed" and (not self.failure or self.prefix_complete):
            raise ValueError(
                "failed capture requires an incomplete prefix and failure explanation"
            )
        return self


class RootSeal(Record):
    attempt_id: str
    design_sha256: SHA
    protocol: Protocol
    capture_receipt_hashes: dict[str, SHA]

    @property
    def sha256(self) -> str:
        return canonical_sha(self.model_dump(mode="json"))


class BranchClaim(Record):
    attempt_id: str
    family_id: str
    condition: str
    candidate_role: Role
    engine: Engine
    design_sha256: SHA
    root_seal_sha256: SHA
    protocol_sha256: SHA
    root_sha256: SHA
    nonce: str
    output_path: str


class RerunBranchClaim(BranchClaim):
    """The single technical rerun of an original branch claim.

    Identical job, design, seal, protocol and root; only the nonce and output
    path are new. A distinct type, so it never validates as an original claim.
    """

    original_nonce: str


class TechnicalRerun(Record):
    attempt_id: str
    policy: Literal["once_before_result"]
    original_claim: BranchClaim
    rerun_claim: RerunBranchClaim
    reason: Literal["infrastructure_failure", "runner_killed_without_outcome"]
    failure_type: str | None
    # Every file of the preserved original output directory at rerun time.
    evidence: dict[str, SHA]

    @model_validator(mode="after")
    def same_inputs(self) -> TechnicalRerun:
        original, rerun = self.original_claim, self.rerun_claim
        if (
            original.model_dump(exclude={"nonce", "output_path"})
            != rerun.model_dump(exclude={"nonce", "output_path", "original_nonce"})
            or rerun.original_nonce != original.nonce
            or rerun.nonce == original.nonce
            or rerun.output_path == original.output_path
            or original.attempt_id != self.attempt_id
        ):
            raise ValueError(
                "technical rerun must repeat the identical claimed job at a new path"
            )
        if (self.reason == "infrastructure_failure") != (self.failure_type is not None):
            raise ValueError("technical rerun reason and failure type disagree")
        return self

    @property
    def evidence_sha256(self) -> str:
        return canonical_sha(
            {
                "original_output_path": self.original_claim.output_path,
                "reason": self.reason,
                "failure_type": self.failure_type,
                "files": self.evidence,
            }
        )

    def summary(self, *, completed: bool) -> TechnicalRerunSummary:
        claim = self.original_claim
        return TechnicalRerunSummary(
            family_id=claim.family_id,
            condition=claim.condition,
            candidate_role=claim.candidate_role,
            engine=claim.engine,
            original_nonce=claim.nonce,
            rerun_nonce=self.rerun_claim.nonce,
            original_output_path=claim.output_path,
            rerun_output_path=self.rerun_claim.output_path,
            reason=self.reason,
            failure_type=self.failure_type,
            evidence_sha256=self.evidence_sha256,
            completed=completed,
        )


class AdmissionReceipt(Record):
    schema_version: Literal["readiness-v2-admission-v1"] = "readiness-v2-admission-v1"
    attempt_id: str
    ledger_path: str
    source_root: str
    design_sha256: SHA
    root_seal_sha256: SHA
    protocol_sha256: SHA
    report_path: str
    report_sha256: SHA
    calibration_receipt_path: str
    calibration_receipt_sha256: SHA
    strategy_sha256: str = APPROVED_STRATEGY_SHA
    source_pins: dict[str, SHA]
    input_pins: dict[str, SHA]
    gamedata_sha256: SHA
    catalog_sha256: SHA
    workspace_gamedata_sha256: SHA
    public_contract_version: Literal[4] = 4
    supported_cards: tuple[str, ...] = tuple(sorted(SUPPORTED_CARDS))
    levels: tuple[Literal[10, 11, 12], ...] = (11,)
    level_sampling_scope: Literal["nominal", "uniform_cards", "independent_cards"] = (
        "nominal"
    )
    native_level_scope: Literal["nominal_level11", "uniform_cards_asymmetric_kings"] = (
        "nominal_level11"
    )
    parent_admission_path: str | None = None
    parent_admission_sha256: SHA | None = None
    level_extension_path: str | None = None
    level_extension_sha256: SHA | None = None
    training_scope: Literal["scalar_public_policy_only"] = "scalar_public_policy_only"
    teacher_search_admitted: Literal[False] = False
    technical_reruns: tuple[TechnicalRerunSummary, ...] = ()

    @model_serializer(mode="wrap")
    def _omit_empty_reruns(self, handler: Any) -> Any:
        # Receipts without reruns serialize byte-identically to earlier ones.
        data = handler(self)
        if not self.technical_reruns:
            data.pop("technical_reruns", None)
        return data


def _canonical(path: Path) -> str:
    return str(path.resolve())


def verify_pins(pins: dict[str, str]) -> None:
    for filename, expected in pins.items():
        if file_sha(Path(filename)) != expected:
            raise ValueError(f"pinned input or source changed: {filename}")


def required_source_pins() -> dict[str, str]:
    root = Path(__file__).resolve().parents[3]
    paths = sorted((root / "src/clasher").rglob("*.py")) + [
        root / "scripts" / name
        for name in (
            "run_readiness_v2.py",
            "collect_readiness_prefix.py",
            "read_native_public_levels.py",
            "smoke_reference_battle.py",
            "compare_reacting_public_branches.py",
            "collect_public_development_games.py",
            "prepare_prospective_branch.py",
        )
    ]
    return {str(p.resolve()): file_sha(p) for p in paths}


def _verify_declaration(declaration: AttemptDeclaration) -> None:
    if declaration.evidence_role == "fresh_acceptance":
        declared = {
            str(Path(k).resolve()): v for k, v in declaration.source_pins.items()
        }
        if any(declared.get(k) != v for k, v in required_source_pins().items()):
            raise ValueError(
                "fresh declaration omits or changes an execution source dependency"
            )
    verify_pins(declaration.source_pins)
    verify_pins(declaration.input_pins)
    workspace = Path(__file__).resolve().parents[3] / "gamedata.json"
    if file_sha(workspace) != declaration.workspace_gamedata_sha256:
        raise ValueError(
            "workspace spell-registry gamedata changed or was not declared"
        )
    for episode in declaration.episodes:
        path = Path(episode.config_path)
        if (
            file_sha(path) != episode.config_file_sha256
            or canonical_sha(json.loads(path.read_text())) != episode.config_sha256
        ):
            raise ValueError("episode config differs from pre-capture declaration")


def _historically_known(
    episode: EpisodeSpec,
    registries: tuple[str, ...],
    *,
    ledger: Path,
    attempt_id: str,
) -> bool:
    """Check v7 native-root and readiness-v2 registries; both kinds are required.

    Only the current attempt's own rows in the ledger being written are
    excluded. Any other readiness-v2 declaration, including opened development,
    makes an episode non-fresh.
    """
    kinds, known = set(), False
    own_ledger = ledger.resolve()
    for filename in registries:
        path = Path(filename).resolve(strict=True)
        own = path == own_ledger
        with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as db:
            db.execute("PRAGMA query_only=ON")
            tables = {
                row[0]
                for row in db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            v2_tables = {"readiness_v2_meta", "attempts", "fresh_identities"}
            if "native_roots" not in tables and not v2_tables <= tables:
                raise ValueError(
                    "historical registry lacks native root or readiness-v2 identities"
                )
            if "native_roots" in tables:
                kinds.add("native_roots")
                for (record,) in db.execute("SELECT record FROM native_roots"):
                    if json.loads(record).get("config_sha256") == episode.config_sha256:
                        known = True
            if v2_tables <= tables:
                kinds.add("readiness_v2")
                for prior_id, record in db.execute(
                    "SELECT attempt_id,record FROM attempts"
                ):
                    if own and prior_id == attempt_id:
                        continue
                    for prior in json.loads(record)["episodes"]:
                        if (
                            prior["config_sha256"] == episode.config_sha256
                            or prior["source_episode_id"] == episode.source_episode_id
                        ):
                            known = True
                for config, episode_id, prior_id in db.execute(
                    "SELECT config_sha,episode_id,attempt_id FROM fresh_identities"
                ):
                    if own and prior_id == attempt_id:
                        continue
                    if (
                        config == episode.config_sha256
                        or episode_id == episode.source_episode_id
                    ):
                        known = True
    if kinds != {"native_roots", "readiness_v2"}:
        raise ValueError(
            "freshness requires both historical v7 native-root and readiness-v2 registries"
        )
    return known


# Many concurrent runners share one ledger; a waiting writer must never fail a
# completed branch. Expensive audits run before the write lock (see
# record_branch_result), so lock hold times stay short.
LEDGER_BUSY_TIMEOUT_SECONDS = 900


@contextmanager
def _transaction(path: Path) -> Iterator[sqlite3.Connection]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path, timeout=LEDGER_BUSY_TIMEOUT_SECONDS) as db:
        tables = {
            row[0]
            for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        if tables and "readiness_v2_meta" not in tables:
            raise ValueError("refusing to write a non-readiness-v2 database")
        db.execute("BEGIN IMMEDIATE")
        db.execute(
            "CREATE TABLE IF NOT EXISTS readiness_v2_meta (version INTEGER PRIMARY KEY CHECK(version=1))"
        )
        db.execute("INSERT OR IGNORE INTO readiness_v2_meta VALUES (1)")
        db.execute(
            "CREATE TABLE IF NOT EXISTS attempts (attempt_id TEXT PRIMARY KEY, design_sha TEXT NOT NULL UNIQUE, record TEXT NOT NULL)"
        )
        db.execute(
            "CREATE TABLE IF NOT EXISTS fresh_identities (config_sha TEXT PRIMARY KEY, episode_id TEXT NOT NULL UNIQUE, attempt_id TEXT NOT NULL, family_id TEXT NOT NULL)"
        )
        db.execute(
            "CREATE TABLE IF NOT EXISTS episode_claims (attempt_id TEXT NOT NULL, family_id TEXT NOT NULL, nonce TEXT NOT NULL UNIQUE, output_path TEXT NOT NULL UNIQUE, record TEXT NOT NULL, PRIMARY KEY(attempt_id,family_id))"
        )
        db.execute(
            "CREATE TABLE IF NOT EXISTS captures (attempt_id TEXT NOT NULL, family_id TEXT NOT NULL, record TEXT NOT NULL, PRIMARY KEY(attempt_id,family_id))"
        )
        db.execute(
            "CREATE TABLE IF NOT EXISTS root_seals (attempt_id TEXT PRIMARY KEY, seal_sha TEXT NOT NULL UNIQUE, record TEXT NOT NULL)"
        )
        db.execute(
            "CREATE TABLE IF NOT EXISTS branch_claims (attempt_id TEXT NOT NULL, family_id TEXT NOT NULL, condition TEXT NOT NULL, role TEXT NOT NULL, engine TEXT NOT NULL, output_path TEXT NOT NULL UNIQUE, nonce TEXT NOT NULL UNIQUE, record TEXT NOT NULL, PRIMARY KEY(attempt_id,family_id,condition,role,engine))"
        )
        db.execute(
            "CREATE TABLE IF NOT EXISTS branch_results (nonce TEXT PRIMARY KEY, branch TEXT NOT NULL, artifacts TEXT NOT NULL)"
        )
        # At most one technical rerun per original claim, always at a new path.
        db.execute(
            "CREATE TABLE IF NOT EXISTS branch_reruns (original_nonce TEXT PRIMARY KEY, rerun_nonce TEXT NOT NULL UNIQUE, output_path TEXT NOT NULL UNIQUE, reason TEXT NOT NULL, evidence_sha TEXT NOT NULL, record TEXT NOT NULL)"
        )
        db.execute(
            "CREATE TABLE IF NOT EXISTS exposures (event_id INTEGER PRIMARY KEY, attempt_id TEXT NOT NULL, family_id TEXT, purpose TEXT NOT NULL, evidence_sha TEXT NOT NULL)"
        )
        db.execute(
            "CREATE TABLE IF NOT EXISTS admission_extensions (receipt_path TEXT PRIMARY KEY, record TEXT NOT NULL)"
        )
        db.execute(
            "CREATE TABLE IF NOT EXISTS admissions (attempt_id TEXT PRIMARY KEY, receipt_path TEXT NOT NULL UNIQUE, record TEXT NOT NULL)"
        )
        yield db


def _attempt(db: sqlite3.Connection, attempt_id: str) -> AttemptDeclaration:
    row = db.execute(
        "SELECT record FROM attempts WHERE attempt_id=?", (attempt_id,)
    ).fetchone()
    if row is None:
        raise ValueError("undeclared readiness attempt")
    return AttemptDeclaration.model_validate_json(row[0])


def get_attempt(path: Path, attempt_id: str) -> AttemptDeclaration:
    with sqlite3.connect(
        path.resolve(strict=True).as_uri() + "?mode=ro", uri=True
    ) as db:
        return _attempt(db, attempt_id)


def declare_attempt(
    path: Path,
    declaration: AttemptDeclaration,
    *,
    historical_registries: tuple[Path, ...] | None = None,
) -> str:
    if (
        historical_registries is not None
        and tuple(_canonical(p) for p in historical_registries)
        != declaration.historical_registries
    ):
        raise ValueError("historical registries differ from declaration")
    _verify_declaration(declaration)
    with _transaction(path) as db:
        if declaration.evidence_role == "fresh_acceptance":
            prior = [
                AttemptDeclaration.model_validate_json(row[0])
                for row in db.execute("SELECT record FROM attempts")
            ]
            prior_configs = {e.config_sha256 for d in prior for e in d.episodes}
            prior_episodes = {e.source_episode_id for d in prior for e in d.episodes}
            for episode in declaration.episodes:
                if (
                    episode.config_sha256 in prior_configs
                    or episode.source_episode_id in prior_episodes
                ):
                    raise ValueError(
                        "fresh episode already declared in a prior development or acceptance attempt"
                    )
                if _historically_known(
                    episode,
                    declaration.historical_registries,
                    ledger=path,
                    attempt_id=declaration.attempt_id,
                ):
                    raise ValueError(
                        "fresh episode already occurs in a historical registry"
                    )
                db.execute(
                    "INSERT INTO fresh_identities VALUES (?,?,?,?)",
                    (
                        episode.config_sha256,
                        episode.source_episode_id,
                        declaration.attempt_id,
                        episode.family_id,
                    ),
                )
        db.execute(
            "INSERT INTO attempts VALUES (?,?,?)",
            (declaration.attempt_id, declaration.sha256, declaration.model_dump_json()),
        )
    return declaration.sha256


def claim_episode(
    path: Path,
    *,
    attempt_id: str,
    family_id: str,
    output_path: Path,
    native_attestation_sha256: str,
) -> EpisodeClaim:
    if output_path.exists():
        raise ValueError(
            "capture output already exists; no retries or redirected replacement"
        )
    with _transaction(path) as db:
        declaration = _attempt(db, attempt_id)
        _verify_declaration(declaration)
        if db.execute(
            "SELECT 1 FROM exposures WHERE attempt_id=?", (attempt_id,)
        ).fetchone():
            raise ValueError("opened attempt cannot claim more capture work")
        episode = next(
            (e for e in declaration.episodes if e.family_id == family_id), None
        )
        if (
            episode is None
            or native_attestation_sha256 != declaration.native_attestation_sha256
        ):
            raise ValueError("undeclared family or native runtime")
        if declaration.evidence_role == "fresh_acceptance" and _historically_known(
            episode,
            declaration.historical_registries,
            ledger=path,
            attempt_id=attempt_id,
        ):
            raise ValueError("freshness changed before capture claim")
        claim = EpisodeClaim(
            attempt_id=attempt_id,
            family_id=family_id,
            source_episode_id=episode.source_episode_id,
            design_sha256=declaration.sha256,
            config_sha256=episode.config_sha256,
            converter_manifest_sha256=declaration.converter_manifest_sha256,
            native_attestation_sha256=native_attestation_sha256,
            nonce=str(uuid.uuid4()),
            output_path=_canonical(output_path),
        )
        db.execute(
            "INSERT INTO episode_claims VALUES (?,?,?,?,?)",
            (
                attempt_id,
                family_id,
                claim.nonce,
                claim.output_path,
                claim.model_dump_json(),
            ),
        )
    return claim


def _artifacts(directory: Path, pins: dict[str, str]) -> None:
    if not directory.is_dir() or not pins:
        raise ValueError("existing claimed directory and artifact pins required")
    for relative, expected in pins.items():
        target = (directory / relative).resolve()
        if Path(relative).is_absolute() or not target.is_relative_to(
            directory.resolve()
        ):
            raise ValueError("artifact escapes claimed output directory")
        if file_sha(target) != expected:
            raise ValueError(f"capture/branch artifact changed: {relative}")


def record_capture(path: Path, claim: EpisodeClaim, receipt: CaptureReceipt) -> None:
    with _transaction(path) as db:
        row = db.execute(
            "SELECT record FROM episode_claims WHERE nonce=?", (claim.nonce,)
        ).fetchone()
        if row is None or EpisodeClaim.model_validate_json(row[0]) != claim:
            raise ValueError("capture claim identity or canonical path mismatch")
        declaration = _attempt(db, claim.attempt_id)
        # Preserve failures even when the reason is source/input drift.
        if receipt.status != "failed":
            _verify_declaration(declaration)
        if (
            receipt.claim_nonce != claim.nonce
            or receipt.design_sha256 != claim.design_sha256
            or receipt.family_id != claim.family_id
            or receipt.config_sha256 != claim.config_sha256
            or receipt.native_attestation_sha256 != claim.native_attestation_sha256
        ):
            raise ValueError("capture receipt differs from its prospective claim")
        _artifacts(Path(claim.output_path), receipt.artifact_hashes)
        if receipt.status == "selected":
            family, binding = receipt.selected_family, receipt.capture_binding
            assert family is not None and binding is not None
            if (
                family.family_id != claim.family_id
                or family.independence_id != claim.source_episode_id
                or family.role != declaration.evidence_role
                or binding.family_id != claim.family_id
                or binding.config_sha256 != claim.config_sha256
                or _canonical(Path(binding.capture_path)) != claim.output_path
                or binding.root_sha256 != family.root_sha256
            ):
                raise ValueError(
                    "selected root was substituted or assigned another role/path"
                )
            episode = next(
                e for e in declaration.episodes if e.family_id == claim.family_id
            )
            plan = json.loads((Path(claim.output_path) / "plan.json").read_text())
            if (
                family.root_owner != episode.root_owner
                or canonical_sha(plan["root_request"]) != episode.root_request_sha256
            ):
                raise ValueError(
                    "captured root request or owner differs from declaration"
                )
            binding.verify_files()
            if binding.input_hashes["gamedata.json"] != declaration.gamedata_sha256:
                raise ValueError("capture ruleset differs from declaration")
            if not set(binding.input_hashes) <= receipt.artifact_hashes.keys():
                raise ValueError("root inputs missing from capture artifact receipt")
        target = Path(claim.output_path) / "capture-receipt.json"
        with target.open("x") as stream:
            stream.write(receipt.model_dump_json(indent=2) + "\n")
        db.execute(
            "INSERT INTO captures VALUES (?,?,?)",
            (claim.attempt_id, claim.family_id, receipt.model_dump_json()),
        )


def seal_roots(path: Path, *, attempt_id: str, protocol: Protocol) -> RootSeal:
    with _transaction(path) as db:
        declaration = _attempt(db, attempt_id)
        _verify_declaration(declaration)
        if db.execute(
            "SELECT 1 FROM exposures WHERE attempt_id=?", (attempt_id,)
        ).fetchone():
            raise ValueError("opened attempts cannot be resealed")
        if (
            declaration.evidence_role != "fresh_acceptance"
            or protocol.status != "frozen"
        ):
            raise ValueError("admission root seal requires a fresh frozen protocol")
        ignore = {"status", "families", "generation_failures"}
        if protocol.model_dump(exclude=ignore) != declaration.pre_protocol.model_dump(
            exclude=ignore
        ):
            raise ValueError(
                "criteria or source/config pins changed after pre-capture declaration"
            )
        rows = db.execute(
            "SELECT family_id,record FROM captures WHERE attempt_id=?", (attempt_id,)
        ).fetchall()
        if {r[0] for r in rows} != {e.family_id for e in declaration.episodes}:
            raise ValueError("missing declared captures; no replacement or subset seal")
        hashes, families = {}, {}
        for family_id, raw in rows:
            receipt = CaptureReceipt.model_validate_json(raw)
            if receipt.status != "selected":
                raise ValueError(
                    "missing/ineligible/failed root remains in the attempt"
                )
            claim = EpisodeClaim.model_validate_json(
                db.execute(
                    "SELECT record FROM episode_claims WHERE attempt_id=? AND family_id=?",
                    (attempt_id, family_id),
                ).fetchone()[0]
            )
            _artifacts(Path(claim.output_path), receipt.artifact_hashes)
            saved = Path(claim.output_path) / "capture-receipt.json"
            if CaptureReceipt.model_validate_json(saved.read_text()) != receipt:
                raise ValueError("capture receipt changed")
            hashes[family_id] = file_sha(saved)
            families[family_id] = receipt.selected_family
        if {f.family_id: f for f in protocol.families} != families:
            raise ValueError("protocol roots/candidates differ from captured bindings")
        seal = RootSeal(
            attempt_id=attempt_id,
            design_sha256=declaration.sha256,
            protocol=protocol,
            capture_receipt_hashes=hashes,
        )
        db.execute(
            "INSERT INTO root_seals VALUES (?,?,?)",
            (attempt_id, seal.sha256, seal.model_dump_json()),
        )
    return seal


def get_root_seal(path: Path, attempt_id: str) -> RootSeal:
    with sqlite3.connect(
        path.resolve(strict=True).as_uri() + "?mode=ro", uri=True
    ) as db:
        row = db.execute(
            "SELECT record FROM root_seals WHERE attempt_id=?", (attempt_id,)
        ).fetchone()
        if row is None:
            raise ValueError("attempt has no post-prefix root seal")
        return RootSeal.model_validate_json(row[0])


def claim_branch(
    path: Path,
    *,
    attempt_id: str,
    family_id: str,
    condition: str,
    candidate_role: Role,
    engine: Engine,
    output_path: Path,
) -> BranchClaim:
    if output_path.exists():
        raise ValueError("branch output already exists; no retries")
    with _transaction(path) as db:
        declaration = _attempt(db, attempt_id)
        _verify_declaration(declaration)
        raw = db.execute(
            "SELECT record FROM root_seals WHERE attempt_id=?", (attempt_id,)
        ).fetchone()
        if raw is None:
            raise ValueError("branch execution requires a post-prefix root seal")
        if db.execute(
            "SELECT 1 FROM exposures WHERE attempt_id=?", (attempt_id,)
        ).fetchone():
            raise ValueError("opened attempts cannot claim new branches")
        seal = RootSeal.model_validate_json(raw[0])
        family = next(
            (f for f in seal.protocol.families if f.family_id == family_id), None
        )
        if (
            family is None
            or condition not in CONDITIONS
            or candidate_role not in ROLES
            or engine not in ("scalar", "reference")
        ):
            raise ValueError("undeclared branch case")
        claim = BranchClaim(
            attempt_id=attempt_id,
            family_id=family_id,
            condition=condition,
            candidate_role=candidate_role,
            engine=engine,
            design_sha256=declaration.sha256,
            root_seal_sha256=seal.sha256,
            protocol_sha256=seal.protocol.sha256,
            root_sha256=family.root_sha256,
            nonce=str(uuid.uuid4()),
            output_path=_canonical(output_path),
        )
        db.execute(
            "INSERT INTO branch_claims VALUES (?,?,?,?,?,?,?,?)",
            (
                attempt_id,
                family_id,
                condition,
                candidate_role,
                engine,
                claim.output_path,
                claim.nonce,
                claim.model_dump_json(),
            ),
        )
    return claim


# Declared infrastructure failures (failure.json "type", as the runner writes
# it). Anything else, including NativePublicProjectionError and every
# validation ValueError, is never eligible for a technical rerun.
TECHNICAL_RERUN_TRANSPORT_TYPES = frozenset(
    {
        "ConnectionRefusedError",
        "ConnectionResetError",
        "BrokenPipeError",
        # socket.timeout is TimeoutError on Python >= 3.10 ("timeout" before).
        "TimeoutError",
        "timeout",
        # Link-recovery budget exhausted / adb link failure (native_probe_transport).
        "NativeLinkLost",
        "AdbLinkTransient",
    }
)
# The runner's own wall-time budget also raises TimeoutError; it is not a
# transport failure and stays ineligible.
TECHNICAL_RERUN_EXCLUDED_TIMEOUT = "declared execution wall-time budget exhausted"
# RunInvalidatedError messages for device/app session or identity loss only;
# pin drift, ledger integrity and attestation-at-start mismatches are excluded.
TECHNICAL_RERUN_DEVICE_LOSS_PREFIXES = (
    "native device link lost:",
    "native read session could not open:",
    "native read session did not close with verified identity",
    "native session attestation failed:",
)
_MISSING_FILE = re.compile(r"No such file or directory: '(?P<path>[^']+)'$")


def _runner_internal_missing_file(message: str) -> bool:
    match = _MISSING_FILE.search(message)
    if match is None:
        return False
    root = Path(__file__).resolve().parents[3]
    target = Path(match["path"])
    target = (target if target.is_absolute() else root / target).resolve()
    return any(target.is_relative_to(root / part) for part in ("scripts", "src"))


def is_infrastructure_failure(kind: str, message: str) -> bool:
    """Whether a recorded failure type/message is a declared infrastructure failure."""
    if kind in TECHNICAL_RERUN_TRANSPORT_TYPES:
        return message != TECHNICAL_RERUN_EXCLUDED_TIMEOUT
    if kind == "RunInvalidatedError":
        return message.startswith(TECHNICAL_RERUN_DEVICE_LOSS_PREFIXES)
    if kind == "OperationalError":
        return "database is locked" in message
    if kind == "RunnerTerminated":
        return True
    if kind == "FileNotFoundError":
        return _runner_internal_missing_file(message)
    return False


def technical_rerun_eligibility(
    claim: BranchClaim,
) -> tuple[
    Literal["infrastructure_failure", "runner_killed_without_outcome"],
    str | None,
    dict[str, str],
]:
    """Derive eligibility from the preserved original output directory.

    Returns (reason, failure type, file hashes) or raises ValueError. Eligible:
    no result.json and either a failure.json with a declared infrastructure
    type, or no failure.json at all (runner killed hard).
    """
    directory = Path(claim.output_path)
    ownership = directory / "ownership-claim.json"
    if not directory.is_dir() or not ownership.is_file():
        raise ValueError("original claim has no owned output directory to rerun")
    if BranchClaim.model_validate_json(ownership.read_text()) != claim:
        raise ValueError("original ownership file differs from its ledger claim")
    if (directory / "result.json").exists() or (directory / "branch.json").exists():
        raise ValueError(
            "a failure after result.json is never eligible for technical rerun"
        )
    evidence = {
        str(p.relative_to(directory)): file_sha(p)
        for p in sorted(directory.rglob("*"))
        if p.is_file()
    }
    failure_path = directory / "failure.json"
    if not failure_path.exists():
        return "runner_killed_without_outcome", None, evidence
    failure = json.loads(failure_path.read_text())
    kind = failure.get("type") if isinstance(failure, dict) else None
    message = failure.get("message") if isinstance(failure, dict) else None
    if (
        not isinstance(kind, str)
        or not isinstance(message, str)
        or not is_infrastructure_failure(kind, message)
    ):
        raise ValueError(
            f"failure type {kind!r} is not a declared infrastructure failure"
        )
    return "infrastructure_failure", kind, evidence


def _has_table(db: sqlite3.Connection, name: str) -> bool:
    return (
        db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone()
        is not None
    )


def _stored_reruns(
    db: sqlite3.Connection, attempt_id: str
) -> list[tuple[TechnicalRerun, str | None, str | None]]:
    """Every technical rerun of the attempt with its result row, if any."""
    if not _has_table(db, "branch_reruns"):
        return []  # ledger last written before technical reruns existed
    rows = db.execute(
        "SELECT x.record,r.branch,r.artifacts FROM branch_reruns x JOIN branch_claims c ON x.original_nonce=c.nonce LEFT JOIN branch_results r ON x.rerun_nonce=r.nonce WHERE c.attempt_id=? ORDER BY c.family_id,c.condition,c.role,c.engine",
        (attempt_id,),
    ).fetchall()
    return [(TechnicalRerun.model_validate_json(r[0]), r[1], r[2]) for r in rows]


def _verify_technical_rerun(
    db: sqlite3.Connection, declaration: AttemptDeclaration, rerun: TechnicalRerun
) -> None:
    """Re-derive a stored rerun's eligibility from the untouched original."""
    if (
        declaration.technical_rerun_policy != "once_before_result"
        or rerun.policy != declaration.technical_rerun_policy
    ):
        raise ValueError("attempt did not pre-declare technical reruns")
    original = rerun.original_claim
    row = db.execute(
        "SELECT record FROM branch_claims WHERE nonce=? AND attempt_id=?",
        (original.nonce, declaration.attempt_id),
    ).fetchone()
    stored = db.execute(
        "SELECT rerun_nonce,output_path,reason,evidence_sha FROM branch_reruns WHERE original_nonce=?",
        (original.nonce,),
    ).fetchone()
    if (
        row is None
        or BranchClaim.model_validate_json(row[0]) != original
        or stored
        != (
            rerun.rerun_claim.nonce,
            rerun.rerun_claim.output_path,
            rerun.reason,
            rerun.evidence_sha256,
        )
    ):
        raise ValueError("technical rerun record differs from its original claim")
    if db.execute(
        "SELECT 1 FROM branch_results WHERE nonce=?", (original.nonce,)
    ).fetchone():
        raise ValueError("a claim with a result can never have a technical rerun")
    if technical_rerun_eligibility(original) != (
        rerun.reason,
        rerun.failure_type,
        rerun.evidence,
    ):
        raise ValueError("original evidence of a technical rerun changed")


def claim_technical_rerun(
    path: Path,
    *,
    attempt_id: str,
    original_nonce: str,
    output_path: Path,
) -> RerunBranchClaim:
    """Claim the single technical rerun of an eligible failed branch claim."""
    if output_path.exists():
        raise ValueError(
            "technical rerun output already exists; a new path is required"
        )
    with _transaction(path) as db:
        declaration = _attempt(db, attempt_id)
        _verify_declaration(declaration)
        if declaration.technical_rerun_policy != "once_before_result":
            raise ValueError("attempt did not pre-declare technical reruns")
        raw = db.execute(
            "SELECT record FROM root_seals WHERE attempt_id=?", (attempt_id,)
        ).fetchone()
        if raw is None:
            raise ValueError("branch execution requires a post-prefix root seal")
        if db.execute(
            "SELECT 1 FROM exposures WHERE attempt_id=?", (attempt_id,)
        ).fetchone():
            raise ValueError("opened attempts cannot claim technical reruns")
        seal = RootSeal.model_validate_json(raw[0])
        row = db.execute(
            "SELECT record FROM branch_claims WHERE nonce=? AND attempt_id=?",
            (original_nonce, attempt_id),
        ).fetchone()
        if row is None:
            raise ValueError(
                "technical reruns apply only to an original branch claim of this attempt"
            )
        original = BranchClaim.model_validate_json(row[0])
        if db.execute(
            "SELECT 1 FROM branch_results WHERE nonce=?", (original_nonce,)
        ).fetchone():
            raise ValueError("a claim with a result can never have a technical rerun")
        if db.execute(
            "SELECT 1 FROM branch_reruns WHERE original_nonce=?", (original_nonce,)
        ).fetchone():
            raise ValueError("claim was already re-run once; no further reruns")
        if (
            original.design_sha256 != declaration.sha256
            or original.root_seal_sha256 != seal.sha256
            or original.protocol_sha256 != seal.protocol.sha256
        ):
            raise ValueError("original claim differs from the current seals")
        canonical = _canonical(output_path)
        if (
            canonical == original.output_path
            or db.execute(
                "SELECT 1 FROM branch_claims WHERE output_path=? UNION SELECT 1 FROM branch_reruns WHERE output_path=?",
                (canonical, canonical),
            ).fetchone()
        ):
            raise ValueError("technical rerun requires a new, unclaimed output path")
        reason, failure_type, evidence = technical_rerun_eligibility(original)
        rerun = TechnicalRerun(
            attempt_id=attempt_id,
            policy="once_before_result",
            original_claim=original,
            rerun_claim=RerunBranchClaim(
                **original.model_dump(exclude={"nonce", "output_path"}),
                nonce=str(uuid.uuid4()),
                output_path=canonical,
                original_nonce=original.nonce,
            ),
            reason=reason,
            failure_type=failure_type,
            evidence=evidence,
        )
        db.execute(
            "INSERT INTO branch_reruns VALUES (?,?,?,?,?,?)",
            (
                original.nonce,
                rerun.rerun_claim.nonce,
                canonical,
                reason,
                rerun.evidence_sha256,
                rerun.model_dump_json(),
            ),
        )
    return rerun.rerun_claim


def technical_rerun_candidates(
    path: Path, *, attempt_id: str
) -> dict[tuple[str, str, str, str], tuple[BranchClaim, str, str | None]]:
    """Eligible original claims (no result, no rerun yet) keyed by branch case."""
    with sqlite3.connect(
        path.resolve(strict=True).as_uri() + "?mode=ro", uri=True
    ) as db:
        declaration = _attempt(db, attempt_id)
        if declaration.technical_rerun_policy != "once_before_result":
            raise ValueError("attempt did not pre-declare technical reruns")
        rerun_filter = (
            " AND c.nonce NOT IN (SELECT original_nonce FROM branch_reruns)"
            if _has_table(db, "branch_reruns")
            else ""
        )
        rows = db.execute(
            "SELECT c.record FROM branch_claims c LEFT JOIN branch_results r ON c.nonce=r.nonce WHERE c.attempt_id=? AND r.nonce IS NULL"
            + rerun_filter,
            (attempt_id,),
        ).fetchall()
    candidates = {}
    for (raw,) in rows:
        claim = BranchClaim.model_validate_json(raw)
        try:
            reason, failure_type, _ = technical_rerun_eligibility(claim)
        except ValueError:
            continue
        key = (claim.family_id, claim.condition, claim.candidate_role, claim.engine)
        candidates[key] = (claim, reason, failure_type)
    return candidates


def record_exposure(
    path: Path,
    *,
    attempt_id: str,
    purpose: Literal["evaluation", "inspection", "repair", "training"],
    evidence_sha256: str,
    family_id: str | None = None,
) -> None:
    with _transaction(path) as db:
        declaration = _attempt(db, attempt_id)
        if family_id is not None and family_id not in {
            e.family_id for e in declaration.episodes
        }:
            raise ValueError("undeclared exposure family")
        if purpose == "training" and declaration.evidence_role == "fresh_acceptance":
            raise ValueError("acceptance families can never enter training")
        db.execute(
            "INSERT INTO exposures(attempt_id,family_id,purpose,evidence_sha) VALUES (?,?,?,?)",
            (attempt_id, family_id, purpose, evidence_sha256),
        )


def _verify_captured_roots(
    path: Path, declaration: AttemptDeclaration, seal: RootSeal
) -> tuple[CaptureReceipt, ...]:
    with sqlite3.connect(
        path.resolve(strict=True).as_uri() + "?mode=ro", uri=True
    ) as db:
        rows = db.execute(
            "SELECT c.record,e.record FROM captures c JOIN episode_claims e ON c.attempt_id=e.attempt_id AND c.family_id=e.family_id WHERE c.attempt_id=?",
            (declaration.attempt_id,),
        ).fetchall()
    receipts = []
    expected = {f.family_id: f for f in seal.protocol.families}
    if len(rows) != len(expected):
        raise ValueError("post-prefix seal lost a declared capture")
    for raw_receipt, raw_claim in rows:
        receipt, claim = (
            CaptureReceipt.model_validate_json(raw_receipt),
            EpisodeClaim.model_validate_json(raw_claim),
        )
        binding = receipt.capture_binding
        if (
            receipt.status != "selected"
            or binding is None
            or receipt.selected_family != expected.get(receipt.family_id)
        ):
            raise ValueError("captured root differs from its post-prefix seal")
        directory = Path(binding.capture_path)
        if (
            _canonical(directory) != claim.output_path
            or claim.design_sha256 != declaration.sha256
        ):
            raise ValueError("capture canonical ownership changed")
        _artifacts(directory, receipt.artifact_hashes)
        binding.verify_files()
        if file_sha(
            directory / "capture-receipt.json"
        ) != seal.capture_receipt_hashes.get(receipt.family_id):
            raise ValueError("post-prefix capture receipt changed")
        receipts.append(receipt)
    return tuple(receipts)


def require_execution_plan(
    path: Path, plan: Any, *, attempt_id: str
) -> AttemptDeclaration:
    """Bind the executable fresh plan to both immutable ledger seals."""
    declaration = get_attempt(path, attempt_id)
    seal = get_root_seal(path, attempt_id)
    _verify_declaration(declaration)
    _verify_captured_roots(path, declaration, seal)
    if (
        plan.purpose != "fresh_acceptance"
        or plan.protocol != seal.protocol
        or plan.source_pins != declaration.source_pins
    ):
        raise ValueError("execution plan differs from sealed prospective protocol")
    if (
        set(plan.engines) != {"scalar", "reference"}
        or plan.repetitions != 1
        or plan.selected_conditions != CONDITIONS
        or plan.selected_roles != ROLES
    ):
        raise ValueError(
            "fresh execution requires the entire condition/candidate/engine design"
        )
    if plan.catalog_sha256 != declaration.catalog_sha256:
        raise ValueError("execution projectile catalog differs from declaration")
    if plan.native_attestation_sha256 != declaration.native_attestation_sha256:
        raise ValueError("runtime differs from pre-capture declaration")
    with sqlite3.connect(
        path.resolve(strict=True).as_uri() + "?mode=ro", uri=True
    ) as db:
        captures = tuple(
            CaptureReceipt.model_validate_json(r[0])
            for r in db.execute(
                "SELECT record FROM captures WHERE attempt_id=?", (attempt_id,)
            )
        )
    expected = {r.family_id: r.capture_binding for r in captures}
    if {c.family_id: c for c in plan.captures} != expected:
        raise ValueError("execution capture bindings differ from post-prefix seal")
    for receipt in captures:
        binding = receipt.capture_binding
        assert binding is not None
        _artifacts(Path(binding.capture_path), receipt.artifact_hashes)
        saved = Path(binding.capture_path) / "capture-receipt.json"
        if file_sha(saved) != seal.capture_receipt_hashes[receipt.family_id]:
            raise ValueError("post-prefix capture receipt changed")
    plan.verify_inputs()
    return declaration


def _verify_branch_files(
    claim: BranchClaim,
    branch: Branch,
    artifact_hashes: dict[str, str],
    *,
    audit_transport: bool,
) -> None:
    from clasher.data import CardDataLoader

    from .readiness_transport import (
        audit_native_transport_files,
        audit_scalar_decisions,
    )

    directory = Path(claim.output_path)
    _artifacts(directory, artifact_hashes)
    required = {
        "claim.json",
        "ownership-claim.json",
        "result.json",
        "branch.json",
        "decisions.jsonl.gz",
        "transport.jsonl.gz",
        "terminal.json",
    }
    if not required <= artifact_hashes.keys():
        raise ValueError("branch evidence is incomplete")
    if (
        type(claim).model_validate_json(
            (directory / "ownership-claim.json").read_text()
        )
        != claim
    ):
        raise ValueError("branch ownership file changed")
    if Branch.model_validate_json((directory / "branch.json").read_text()) != branch:
        raise ValueError("branch value file changed")
    result = json.loads((directory / "result.json").read_text())
    terminal = json.loads((directory / "terminal.json").read_text())
    if result["terminal_sha256"] != artifact_hashes["terminal.json"]:
        raise ValueError("terminal evidence digest mismatch")
    if claim.engine == "reference":
        playable, final = terminal["playable"], terminal["final"]
        if not final["finalized"] or not (
            playable["ended"] or playable["tick"] == 6001
        ):
            raise ValueError("native terminal evidence is incomplete")
        winner = final["winner"]
        towers = [
            {"owner": t["owner"], "hp": t["hp"]}
            for t in playable["objects"]
            if t["cardId"] == -1 and t["hp"] is not None
        ]
    else:
        if terminal["game_over"] is not True:
            raise ValueError("scalar terminal evidence is incomplete")
        winner, towers = terminal["winner"], terminal["towers"]
    owner = result["root_owner"]
    if type(owner) is not int or owner not in (0, 1) or winner not in (None, -1, 0, 1):
        raise ValueError("invalid terminal perspective or winner")
    score = 0.5 if winner in (None, -1) else float(winner == owner)
    hp = [
        sum(max(0, tower["hp"]) for tower in towers if tower["owner"] == seat)
        for seat in (0, 1)
    ]
    if (
        score != branch.score
        or hp[owner] != branch.own_remaining_hp
        or hp[1 - owner] != branch.enemy_remaining_hp
    ):
        raise ValueError("branch utility differs from retained terminal evidence")
    if branch.artifact_sha256 != file_sha(directory / "result.json"):
        raise ValueError("branch result digest mismatch")
    fields = ("family_id", "condition", "candidate_role", "engine")
    if any(result["job"][name] != getattr(claim, name) for name in fields):
        raise ValueError("result job identity differs from branch claim")
    if any(
        getattr(branch, name) != getattr(claim, name)
        for name in (*fields, "protocol_sha256", "root_sha256")
    ):
        raise ValueError("branch value differs from prospective claim")
    if (
        result["decisions_sha256"] != artifact_hashes["decisions.jsonl.gz"]
        or result["transport_sha256"] != artifact_hashes["transport.jsonl.gz"]
    ):
        raise ValueError("decision or transport digest mismatch")
    for name in (
        "score",
        "own_remaining_hp",
        "enemy_remaining_hp",
        "public_packet_sha256",
        "protocol_sha256",
        "root_sha256",
    ):
        if result[name] != getattr(branch, name):
            raise ValueError("result values differ from branch receipt")
    if (
        result.get("public_contract_valid") is not True
        or result.get("public_calibration_established") is not True
        or result.get("legal_transport_valid") is not True
    ):
        raise ValueError("result lacks checked public/transport contracts")
    if result.get("gamedata_path") is None or result.get("gamedata_sha256") != file_sha(
        Path(result["gamedata_path"])
    ):
        raise ValueError("branch ruleset path bytes differ from claimed ruleset")
    if claim.engine == "reference" and audit_transport:
        if (
            "native-session.json" not in artifact_hashes
            or result.get("native_session_sha256")
            != artifact_hashes["native-session.json"]
        ):
            raise ValueError("native branch lacks verified session artifact")
        if json.loads((directory / "native-session.json").read_text()) != result.get(
            "native_read_session"
        ):
            raise ValueError("native session artifact differs from result")
        audit_native_transport_files(
            directory,
            CardDataLoader(Path(result["gamedata_path"])),
            provenance={**result, "root_action_id": branch.action_id},
        )
    elif claim.engine == "scalar" and audit_transport:
        audit_scalar_decisions(
            directory,
            CardDataLoader(Path(result["gamedata_path"])),
            provenance={**result, "root_action_id": branch.action_id},
        )


def record_branch_result(
    path: Path, claim: BranchClaim, branch: Branch, *, artifact_hashes: dict[str, str]
) -> None:
    # Full validation including the transport audit (seconds per native branch)
    # runs on a read-only connection first. The write transaction then repeats
    # every check except the transport audit; artifact hashes are still
    # re-verified under the lock, so the audited bytes are the recorded bytes.
    with sqlite3.connect(
        path.resolve(strict=True).as_uri() + "?mode=ro",
        uri=True,
        timeout=LEDGER_BUSY_TIMEOUT_SECONDS,
    ) as snapshot:
        _check_branch_result(
            snapshot, claim, branch, artifact_hashes, audit_transport=True
        )
    with _transaction(path) as db:
        _check_branch_result(db, claim, branch, artifact_hashes, audit_transport=False)
        db.execute(
            "INSERT INTO branch_results VALUES (?,?,?)",
            (
                claim.nonce,
                branch.model_dump_json(),
                json.dumps(artifact_hashes, sort_keys=True),
            ),
        )


def _check_branch_result(
    db: sqlite3.Connection,
    claim: BranchClaim,
    branch: Branch,
    artifact_hashes: dict[str, str],
    *,
    audit_transport: bool,
) -> None:
    rerun = None
    if isinstance(claim, RerunBranchClaim):
        stored = (
            db.execute(
                "SELECT record FROM branch_reruns WHERE rerun_nonce=?", (claim.nonce,)
            ).fetchone()
            if _has_table(db, "branch_reruns")
            else None
        )
        if stored is None:
            raise ValueError("unclaimed technical rerun result")
        rerun = TechnicalRerun.model_validate_json(stored[0])
        if rerun.rerun_claim != claim:
            raise ValueError("unclaimed branch result or changed output path")
    else:
        stored = db.execute(
            "SELECT record FROM branch_claims WHERE nonce=?", (claim.nonce,)
        ).fetchone()
        if stored is None or BranchClaim.model_validate_json(stored[0]) != claim:
            raise ValueError("unclaimed branch result or changed output path")
        if (
            _has_table(db, "branch_reruns")
            and db.execute(
                "SELECT 1 FROM branch_reruns WHERE original_nonce=?", (claim.nonce,)
            ).fetchone()
        ):
            raise ValueError("claim was superseded by its technical rerun")
    declaration = _attempt(db, claim.attempt_id)
    if rerun is not None:
        # Policy, untouched original evidence and "original has no result".
        _verify_technical_rerun(db, declaration, rerun)
    _verify_declaration(declaration)
    seal = RootSeal.model_validate_json(
        db.execute(
            "SELECT record FROM root_seals WHERE attempt_id=?", (claim.attempt_id,)
        ).fetchone()[0]
    )
    family = next(f for f in seal.protocol.families if f.family_id == claim.family_id)
    candidate = next(c for c in family.candidates if c.role == claim.candidate_role)
    if (
        branch.action_id != candidate.action_id
        or branch.public_packet_sha256 != family.public_packet_sha256
    ):
        raise ValueError("branch root action/public packet differs from seal")
    result = json.loads((Path(claim.output_path) / "result.json").read_text())
    capture = CaptureReceipt.model_validate_json(
        db.execute(
            "SELECT record FROM captures WHERE attempt_id=? AND family_id=?",
            (claim.attempt_id, claim.family_id),
        ).fetchone()[0]
    )
    binding = capture.capture_binding
    assert binding is not None
    if (
        _canonical(Path(result["capture_path"]))
        != _canonical(Path(binding.capture_path))
        or result["root_tick"] != binding.root_tick
    ):
        raise ValueError("branch replay source differs from sealed root capture")
    if result["catalog_sha256"] != file_sha(Path(result["catalog_path"])):
        raise ValueError("branch projectile catalog bytes differ from claim")
    if (
        result["root_owner"] != family.root_owner
        or result.get("calibration_receipt_sha256")
        not in declaration.input_pins.values()
    ):
        raise ValueError(
            "result perspective/calibration differs from admitted declarations"
        )
    if (
        result["gamedata_sha256"] != declaration.gamedata_sha256
        or result["catalog_sha256"] != declaration.catalog_sha256
        or result["native_attestation_sha256"] != declaration.native_attestation_sha256
    ):
        raise ValueError("branch data/runtime differs from declaration")
    if claim.engine == "reference":
        storage_pins = [
            h
            for p, h in declaration.source_pins.items()
            if p.endswith("/src/clasher/rl/native_frame_storage.py")
        ]
        if (
            len(storage_pins) != 1
            or result.get("native_frame_storage_sha256") != storage_pins[0]
        ):
            raise ValueError(
                "native compact frame producer was not pinned before capture"
            )
    _verify_branch_files(
        claim, branch, artifact_hashes, audit_transport=audit_transport
    )


def _checked_calibration(path: Path) -> Any:
    from .native_public_calibration import verify_calibration_receipt

    receipt = verify_calibration_receipt(path)
    if (
        receipt.scope != "native-exact-public-v4"
        or not receipt.structural_validity_established
        or not receipt.measured_native_known_channels_valid
        or not receipt.coordinate_transport_roundtrip_valid
    ):
        raise ValueError("native exact-public calibration scope was not established")
    return receipt


def _require_calibration_scope(
    calibration: Any, declaration: AttemptDeclaration
) -> None:
    if (
        declaration.gamedata_sha256 not in calibration.ruleset_sha256
        or declaration.catalog_sha256 != calibration.catalog_sha256
    ):
        raise ValueError(
            "verified calibration covers a different ruleset or projectile catalog"
        )


def evaluate_attempt(
    path: Path,
    *,
    attempt_id: str,
    calibration_receipt_path: Path,
    report_path: Path,
    admission_path: Path,
    reviews: tuple[MechanismReview, ...] = (),
) -> tuple[Report, AdmissionReceipt | None]:
    """Open all declared outcomes once, evaluate them, and issue admission only on pass."""
    declaration = get_attempt(path, attempt_id)
    seal = get_root_seal(path, attempt_id)
    _verify_declaration(declaration)
    _verify_captured_roots(path, declaration, seal)
    calibration = _checked_calibration(calibration_receipt_path)
    _require_calibration_scope(calibration, declaration)
    calibration_sha = file_sha(calibration_receipt_path)
    if (
        declaration.input_pins.get(str(calibration_receipt_path.resolve()))
        != calibration_sha
    ):
        raise ValueError("calibration evidence differs from pre-capture input pins")
    # Opening is irreversible even if a later audit fails or cases are missing.
    record_exposure(
        path,
        attempt_id=attempt_id,
        purpose="evaluation",
        evidence_sha256=canonical_sha(
            {
                "calibration": str(calibration_receipt_path.resolve()),
                "report": str(report_path.resolve()),
            }
        ),
    )
    with sqlite3.connect(
        path.resolve(strict=True).as_uri() + "?mode=ro", uri=True
    ) as db:
        rows = [
            (BranchClaim.model_validate_json(r[0]), r[1], r[2])
            for r in db.execute(
                "SELECT c.record,r.branch,r.artifacts FROM branch_claims c JOIN branch_results r ON c.nonce=r.nonce WHERE c.attempt_id=?",
                (attempt_id,),
            )
        ]
        # An original claim is complete through its single rerun's result; a
        # rerun without a result leaves the case missing.
        reruns = _stored_reruns(db, attempt_id)
        for rerun, raw_branch, raw_artifacts in reruns:
            _verify_technical_rerun(db, declaration, rerun)
            if raw_branch is not None:
                rows.append((rerun.rerun_claim, raw_branch, raw_artifacts))
    branches = []
    for claim, raw_branch, raw_artifacts in rows:
        branch = Branch.model_validate_json(raw_branch)
        _verify_branch_files(
            claim, branch, json.loads(raw_artifacts), audit_transport=True
        )
        if (
            json.loads((Path(claim.output_path) / "result.json").read_text()).get(
                "calibration_receipt_sha256"
            )
            != calibration_sha
        ):
            raise ValueError("branch used a different calibration receipt")
        branches.append(branch)
    report = evaluate(seal.protocol, tuple(branches), reviews)
    summaries = tuple(r.summary(completed=b is not None) for r, b, _ in reruns)
    if summaries:
        report = report.model_copy(update={"technical_reruns": summaries})
    with report_path.open("x") as stream:
        stream.write(report.model_dump_json(indent=2) + "\n")
    if report.status != "passed":
        return report, None
    admission = AdmissionReceipt(
        attempt_id=attempt_id,
        ledger_path=_canonical(path),
        source_root=str(Path(__file__).resolve().parents[3]),
        design_sha256=declaration.sha256,
        root_seal_sha256=seal.sha256,
        protocol_sha256=seal.protocol.sha256,
        report_path=_canonical(report_path),
        report_sha256=file_sha(report_path),
        calibration_receipt_path=_canonical(calibration_receipt_path),
        calibration_receipt_sha256=calibration_sha,
        source_pins=declaration.source_pins,
        input_pins=declaration.input_pins,
        gamedata_sha256=declaration.gamedata_sha256,
        catalog_sha256=declaration.catalog_sha256,
        workspace_gamedata_sha256=declaration.workspace_gamedata_sha256,
        levels=tuple(
            sorted(
                {
                    level
                    for family in seal.protocol.families
                    for level in family.tower_levels
                }
            )
        ),
        technical_reruns=summaries,
    )
    with _transaction(path) as db:
        with admission_path.open("x") as stream:
            stream.write(admission.model_dump_json(indent=2) + "\n")
        db.execute(
            "INSERT INTO admissions VALUES (?,?,?)",
            (attempt_id, _canonical(admission_path), admission.model_dump_json()),
        )
    return report, admission


def require_admission(
    ledger_path: Path,
    receipt_path: Path,
    *,
    expected_source_pins: dict[str, str] | None = None,
    expected_input_pins: dict[str, str] | None = None,
    expected_gamedata_sha256: str | None = None,
    expected_gamedata_path: Path | None = None,
    expected_source_root: Path | None = None,
) -> AdmissionReceipt:
    """Validate ledger-issued admission; a hand-authored JSON success is insufficient."""
    receipt = AdmissionReceipt.model_validate_json(receipt_path.read_text())
    if receipt.parent_admission_path is not None:
        return _require_extended_admission(
            ledger_path,
            receipt_path,
            receipt,
            expected_source_pins=expected_source_pins,
            expected_input_pins=expected_input_pins,
            expected_gamedata_sha256=expected_gamedata_sha256,
            expected_gamedata_path=expected_gamedata_path,
            expected_source_root=expected_source_root,
        )
    if any(
        value is not None
        for value in (
            receipt.parent_admission_sha256,
            receipt.level_extension_path,
            receipt.level_extension_sha256,
        )
    ):
        raise ValueError("incomplete admission extension lineage")
    if receipt.ledger_path != _canonical(ledger_path):
        raise ValueError("admission ledger path differs")
    with sqlite3.connect(
        ledger_path.resolve(strict=True).as_uri() + "?mode=ro", uri=True
    ) as db:
        stored = db.execute(
            "SELECT receipt_path,record FROM admissions WHERE attempt_id=?",
            (receipt.attempt_id,),
        ).fetchone()
        if (
            stored is None
            or stored[0] != _canonical(receipt_path)
            or AdmissionReceipt.model_validate_json(stored[1]) != receipt
        ):
            raise ValueError("admission was not issued by the readiness evaluator")
        declaration = _attempt(db, receipt.attempt_id)
        seal = RootSeal.model_validate_json(
            db.execute(
                "SELECT record FROM root_seals WHERE attempt_id=?",
                (receipt.attempt_id,),
            ).fetchone()[0]
        )
        branch_rows = [
            (BranchClaim.model_validate_json(r[0]), r[1], r[2])
            for r in db.execute(
                "SELECT c.record,r.branch,r.artifacts FROM branch_claims c JOIN branch_results r ON c.nonce=r.nonce WHERE c.attempt_id=?",
                (receipt.attempt_id,),
            )
        ]
        reruns = _stored_reruns(db, receipt.attempt_id)
        for rerun, raw_branch, raw_artifacts in reruns:
            _verify_technical_rerun(db, declaration, rerun)
            if raw_branch is not None:
                branch_rows.append((rerun.rerun_claim, raw_branch, raw_artifacts))
    if receipt.technical_reruns != tuple(
        r.summary(completed=b is not None) for r, b, _ in reruns
    ):
        raise ValueError("admission technical reruns differ from the ledger")
    if (
        receipt.design_sha256 != declaration.sha256
        or receipt.root_seal_sha256 != seal.sha256
        or receipt.protocol_sha256 != seal.protocol.sha256
    ):
        raise ValueError("admission seal changed")
    _verify_declaration(declaration)
    _verify_captured_roots(ledger_path, declaration, seal)
    if (
        file_sha(Path(receipt.report_path)) != receipt.report_sha256
        or Report.model_validate_json(Path(receipt.report_path).read_text()).status
        != "passed"
    ):
        raise ValueError("admission evaluation changed or did not pass")
    if len(branch_rows) != 32 * 4 * 4 * 2:
        raise ValueError("admission lacks the complete declared branch matrix")
    for claim, raw_branch, artifacts in branch_rows:
        _verify_branch_files(
            claim,
            Branch.model_validate_json(raw_branch),
            json.loads(artifacts),
            audit_transport=False,
        )
    if (
        file_sha(Path(receipt.calibration_receipt_path))
        != receipt.calibration_receipt_sha256
    ):
        raise ValueError("calibration receipt changed")
    calibration = _checked_calibration(Path(receipt.calibration_receipt_path))
    _require_calibration_scope(calibration, declaration)
    if expected_source_pins is not None:
        verify_pins(expected_source_pins)
        admitted = {str(Path(p).resolve()): h for p, h in receipt.source_pins.items()}
        for filename, digest in expected_source_pins.items():
            requested = Path(filename).resolve()
            if expected_source_root is not None:
                relative = requested.relative_to(expected_source_root.resolve())
                original = str((Path(receipt.source_root) / relative).resolve())
            else:
                original = str(requested)
            if admitted.get(original) != digest:
                raise ValueError(
                    "requested source path/role differs from admitted module"
                )
    if expected_input_pins is not None:
        verify_pins(expected_input_pins)
        admitted = {str(Path(p).resolve()): h for p, h in receipt.input_pins.items()}
        if any(
            admitted.get(str(Path(p).resolve())) != h
            for p, h in expected_input_pins.items()
        ):
            raise ValueError("requested input path/role differs from admitted input")
    if (
        expected_gamedata_sha256 is not None
        and receipt.gamedata_sha256 != expected_gamedata_sha256
    ):
        raise ValueError("requested game data differs from admitted ruleset")
    if (
        expected_gamedata_path is not None
        and file_sha(expected_gamedata_path) != receipt.gamedata_sha256
    ):
        raise ValueError("staged game data differs from admitted ruleset")
    return receipt


def execution_plan_for_attempt(
    path: Path, *, attempt_id: str, catalog_path: Path
) -> ExecutionPlan:
    declaration = get_attempt(path, attempt_id)
    seal = get_root_seal(path, attempt_id)
    catalog_sha = file_sha(catalog_path)
    if (
        declaration.catalog_sha256 != catalog_sha
        or declaration.input_pins.get(str(catalog_path.resolve())) != catalog_sha
    ):
        raise ValueError("projectile catalog was not pinned before capture")
    with sqlite3.connect(
        path.resolve(strict=True).as_uri() + "?mode=ro", uri=True
    ) as db:
        captures = [
            CaptureReceipt.model_validate_json(row[0])
            for row in db.execute(
                "SELECT record FROM captures WHERE attempt_id=? ORDER BY family_id",
                (attempt_id,),
            )
        ]
    bindings = tuple(
        c.capture_binding for c in captures if c.capture_binding is not None
    )
    plan = ExecutionPlan(
        protocol=seal.protocol,
        captures=bindings,
        catalog_path=str(catalog_path.resolve()),
        catalog_sha256=catalog_sha,
        native_attestation_sha256=declaration.native_attestation_sha256,
        source_pins=declaration.source_pins,
        purpose="fresh_acceptance",
    )
    require_execution_plan(path, plan, attempt_id=attempt_id)
    return plan


def _verified_level_extension(path: Path, *, parent_sha256: str) -> Any:
    from .readiness_level_extension import verify_level_extension_receipt

    return verify_level_extension_receipt(path, base_admission_sha256=parent_sha256)


def _require_extension_scope(
    ledger_path: Path, base: AdmissionReceipt, evidence: Any
) -> None:
    declaration = get_attempt(ledger_path, base.attempt_id)
    extension = evidence.declaration.payload()
    if (
        extension["native_attestation_sha256"] != declaration.native_attestation_sha256
        or extension["gamedata_sha256"] != base.gamedata_sha256
    ):
        raise ValueError("level extension runtime/ruleset differs from admitted base")


def extend_admission(
    ledger_path: Path,
    *,
    base_receipt_path: Path,
    extension_receipt_path: Path,
    output_path: Path,
) -> AdmissionReceipt:
    """Extend only with independently verified level evidence, never a requested list."""
    base = require_admission(ledger_path, base_receipt_path)
    if base.parent_admission_path is not None:
        raise ValueError(
            "level extensions bind the original nominal admission directly"
        )
    parent_sha = file_sha(base_receipt_path)
    evidence = _verified_level_extension(
        extension_receipt_path, parent_sha256=parent_sha
    )
    _require_extension_scope(ledger_path, base, evidence)
    levels = tuple(sorted(set(base.levels) | set(evidence.verified_levels)))
    if not evidence.verified_levels or not set(levels) <= {10, 11, 12}:
        raise ValueError("level extension has no verified supported scope")
    receipt = AdmissionReceipt.model_validate(
        {
            **base.model_dump(),
            "levels": levels,
            "level_sampling_scope": evidence.level_sampling_scope,
            "native_level_scope": evidence.native_level_scope,
            "parent_admission_path": _canonical(base_receipt_path),
            "parent_admission_sha256": parent_sha,
            "level_extension_path": _canonical(extension_receipt_path),
            "level_extension_sha256": file_sha(extension_receipt_path),
        }
    )
    with _transaction(ledger_path) as db:
        with output_path.open("x") as stream:
            stream.write(receipt.model_dump_json(indent=2) + "\n")
        db.execute(
            "INSERT INTO admission_extensions VALUES (?,?)",
            (_canonical(output_path), receipt.model_dump_json()),
        )
    return receipt


def _require_extended_admission(
    ledger_path: Path, receipt_path: Path, receipt: AdmissionReceipt, **expected: Any
) -> AdmissionReceipt:
    if any(
        value is None
        for value in (
            receipt.parent_admission_sha256,
            receipt.level_extension_path,
            receipt.level_extension_sha256,
        )
    ):
        raise ValueError("incomplete admission extension lineage")
    with sqlite3.connect(
        ledger_path.resolve(strict=True).as_uri() + "?mode=ro", uri=True
    ) as db:
        row = db.execute(
            "SELECT record FROM admission_extensions WHERE receipt_path=?",
            (_canonical(receipt_path),),
        ).fetchone()
        if row is None or AdmissionReceipt.model_validate_json(row[0]) != receipt:
            raise ValueError("level extension was not issued by the readiness ledger")
    assert receipt.parent_admission_path is not None
    assert receipt.parent_admission_sha256 is not None
    assert receipt.level_extension_path is not None
    assert receipt.level_extension_sha256 is not None
    parent = Path(receipt.parent_admission_path)
    evidence_path = Path(receipt.level_extension_path)
    if (
        file_sha(parent) != receipt.parent_admission_sha256
        or file_sha(evidence_path) != receipt.level_extension_sha256
    ):
        raise ValueError("level extension lineage evidence changed")
    base = require_admission(ledger_path, parent, **expected)
    if base.parent_admission_path is not None:
        raise ValueError("nested or cyclic admission extension")
    evidence = _verified_level_extension(
        evidence_path, parent_sha256=receipt.parent_admission_sha256
    )
    _require_extension_scope(ledger_path, base, evidence)
    derived = AdmissionReceipt.model_validate(
        {
            **base.model_dump(),
            "levels": tuple(sorted(set(base.levels) | set(evidence.verified_levels))),
            "level_sampling_scope": evidence.level_sampling_scope,
            "native_level_scope": evidence.native_level_scope,
            "parent_admission_path": _canonical(parent),
            "parent_admission_sha256": receipt.parent_admission_sha256,
            "level_extension_path": _canonical(evidence_path),
            "level_extension_sha256": receipt.level_extension_sha256,
        }
    )
    if derived != receipt:
        raise ValueError("extension scope differs from verified evidence")
    return receipt


def claimed_branch_keys(
    path: Path, *, attempt_id: str
) -> frozenset[tuple[str, str, str, str]]:
    """Read claimed cases, including failed/incomplete claims; never make retries."""
    with sqlite3.connect(
        path.resolve(strict=True).as_uri() + "?mode=ro", uri=True
    ) as db:
        _attempt(db, attempt_id)
        return frozenset(
            tuple(row)
            for row in db.execute(
                "SELECT family_id,condition,role,engine FROM branch_claims WHERE attempt_id=?",
                (attempt_id,),
            )
        )
