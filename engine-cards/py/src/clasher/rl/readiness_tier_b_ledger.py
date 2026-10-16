"""Append-only Tier B ownership in the readiness-v2 ledger, beside Tier A.

Tier B attempts use their own ``tier_b_*`` tables in the same readiness-v2
database, so no Tier A table ever holds a record of a different shape and no
Tier A invariant (32 seat-balanced families, admission receipts) is relaxed.
Freshness is shared: Tier B episode identities are inserted into the common
``fresh_identities`` table and checked against Tier A attempts, v7 native
roots and earlier Tier B attempts. Tier B never issues an admission receipt;
it records a report receipt whose status gates promotion.

Unlike Tier A, a Tier B seal retains missing or ineligible roots as declared
failures (they remain in accounting and prevent a pass) instead of making the
attempt unsealable, so blocking evidence from the captured roots is not lost.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, model_validator

from .readiness_capture_ownership import (
    LEDGER_BUSY_TIMEOUT_SECONDS,
    BranchClaim,
    CaptureReceipt,
    EpisodeClaim,
    _artifacts,
    _canonical,
    _checked_calibration,
    _historically_known,
    _require_calibration_scope,
    _transaction,
    _verify_branch_files,
    _verify_declaration,
    required_source_pins,
)
from .readiness_execution import canonical_sha, file_sha
from .readiness_tier_b import (
    SHA,
    BlockKind,
    OpponentKind,
    Phase,
    PolicyRootRecord,
    ProbeKind,
    TierBProtocol,
    TierBReport,
    TierBRootBank,
    evaluate_tier_b,
)
from .training_readiness_v2 import (
    CONDITIONS,
    ROLES,
    Branch,
    Engine,
    MechanismReview,
    Record,
    Role,
)

TIER_B_SCRIPTS = (
    "tier_b_readiness.py",
    "collect_tier_b_prefix.py",
)


class TierBEpisodeSpec(Record):
    family_id: str = Field(min_length=1)
    source_episode_id: str = Field(min_length=1)
    config_path: str
    config_file_sha256: SHA
    config_sha256: SHA
    root_request_sha256: SHA
    root_owner: Literal[0, 1]
    deck_id: str = Field(min_length=1)
    phase: Phase
    opponent: OpponentKind
    probe_kind: ProbeKind | None = None


class TierBDeclaration(Record):
    schema_version: Literal["readiness-v2-tier-b-declaration-v1"] = (
        "readiness-v2-tier-b-declaration-v1"
    )
    attempt_id: str = Field(min_length=1)
    evidence_role: Literal["tier_b_transfer"] = "tier_b_transfer"
    block_kind: BlockKind
    root_bank_sha256: SHA
    generator_sha256: SHA
    converter_manifest_sha256: SHA
    checkpoint_path: str
    checkpoint_sha256: SHA
    tier_a_admission_path: str
    tier_a_admission_sha256: SHA
    pre_protocol: TierBProtocol
    native_attestation_sha256: SHA
    gamedata_sha256: SHA
    catalog_sha256: SHA
    workspace_gamedata_sha256: SHA
    source_pins: dict[str, SHA]
    input_pins: dict[str, SHA]
    episodes: tuple[TierBEpisodeSpec, ...]
    historical_registries: tuple[str, ...]

    @model_validator(mode="after")
    def prospective(self) -> TierBDeclaration:
        p = self.pre_protocol
        if p.status != "draft" or p.families or p.policy_roots or p.generation_failures:
            raise ValueError("pre-capture protocol must be an unbound draft")
        if p.attempt_id != self.attempt_id or p.block_kind != self.block_kind:
            raise ValueError("attempt identity or block differs from pre-capture protocol")
        if p.source_pins != self.source_pins or not self.source_pins:
            raise ValueError("pre-capture protocol must bind the same source pins")
        if p.checkpoint_sha256 != self.checkpoint_sha256:
            raise ValueError("pre-capture protocol binds a different checkpoint")
        if (
            p.floors is None
            or p.config_sha256 is None
            or p.generator_sha256 != self.generator_sha256
            or p.tier_a_protocol_sha256 is None
        ):
            raise ValueError("floors, config/generator pins and Tier A reference required")
        if not self.historical_registries or not self.episodes:
            raise ValueError("historical registries and episode declarations required")
        for attribute in ("family_id", "source_episode_id", "config_sha256"):
            if len({getattr(e, attribute) for e in self.episodes}) != len(self.episodes):
                raise ValueError(f"duplicate declared {attribute}")
        strata = {s.family_id: s for s in p.strata}
        if len(self.episodes) != p.family_count or set(strata) != {
            e.family_id for e in self.episodes
        }:
            raise ValueError("episodes must equal the declared strata")
        for episode in self.episodes:
            stratum = strata[episode.family_id]
            if (
                stratum.root_owner,
                stratum.deck_id,
                stratum.phase,
                stratum.opponent,
                stratum.probe_kind,
            ) != (
                episode.root_owner,
                episode.deck_id,
                episode.phase,
                episode.opponent,
                episode.probe_kind,
            ):
                raise ValueError("episode differs from its declared stratum")
        pinned = set(self.input_pins.values())
        for digest, what in (
            (self.gamedata_sha256, "capture gamedata"),
            (self.workspace_gamedata_sha256, "workspace gamedata"),
            (self.converter_manifest_sha256, "converter manifest"),
            (self.checkpoint_sha256, "frozen checkpoint"),
            (self.tier_a_admission_sha256, "Tier A admission receipt"),
            (self.catalog_sha256, "projectile catalog"),
        ):
            if digest not in pinned:
                raise ValueError(f"{what} must be pinned")
        if self.input_pins.get(str(Path(self.checkpoint_path).resolve())) != (
            self.checkpoint_sha256
        ):
            raise ValueError("checkpoint path must be pinned with its digest")
        return self

    @property
    def sha256(self) -> str:
        return canonical_sha(self.model_dump(mode="json"))


class TierBRootSeal(Record):
    attempt_id: str
    design_sha256: SHA
    protocol: TierBProtocol
    capture_receipt_hashes: dict[str, SHA]

    @property
    def sha256(self) -> str:
        return canonical_sha(self.model_dump(mode="json"))


class TierBReportReceipt(Record):
    schema_version: Literal["readiness-v2-tier-b-report-receipt-v1"] = (
        "readiness-v2-tier-b-report-receipt-v1"
    )
    attempt_id: str
    block_kind: BlockKind
    status: Literal["passed", "blocked", "inconclusive", "no_block_found"]
    ledger_path: str
    design_sha256: SHA
    root_seal_sha256: SHA
    protocol_sha256: SHA
    checkpoint_sha256: SHA
    report_path: str
    report_sha256: SHA
    calibration_receipt_sha256: SHA
    # Tier B gates promotion; it grants no new training or search scope.
    grants_scope: Literal[False] = False


def required_tier_b_source_pins() -> dict[str, str]:
    root = Path(__file__).resolve().parents[3]
    extra = [root / "scripts" / name for name in TIER_B_SCRIPTS]
    return {
        **required_source_pins(),
        **{str(p.resolve()): file_sha(p) for p in extra if p.exists()},
    }


def _create_tables(db: sqlite3.Connection) -> None:
    db.execute(
        "CREATE TABLE IF NOT EXISTS tier_b_attempts (attempt_id TEXT PRIMARY KEY, design_sha TEXT NOT NULL UNIQUE, record TEXT NOT NULL)"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS tier_b_episode_claims (attempt_id TEXT NOT NULL, family_id TEXT NOT NULL, nonce TEXT NOT NULL UNIQUE, output_path TEXT NOT NULL UNIQUE, record TEXT NOT NULL, PRIMARY KEY(attempt_id,family_id))"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS tier_b_captures (attempt_id TEXT NOT NULL, family_id TEXT NOT NULL, record TEXT NOT NULL, policy_record TEXT, PRIMARY KEY(attempt_id,family_id))"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS tier_b_root_seals (attempt_id TEXT PRIMARY KEY, seal_sha TEXT NOT NULL UNIQUE, record TEXT NOT NULL)"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS tier_b_branch_claims (attempt_id TEXT NOT NULL, family_id TEXT NOT NULL, condition TEXT NOT NULL, role TEXT NOT NULL, engine TEXT NOT NULL, output_path TEXT NOT NULL UNIQUE, nonce TEXT NOT NULL UNIQUE, record TEXT NOT NULL, PRIMARY KEY(attempt_id,family_id,condition,role,engine))"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS tier_b_branch_results (nonce TEXT PRIMARY KEY, branch TEXT NOT NULL, artifacts TEXT NOT NULL)"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS tier_b_exposures (event_id INTEGER PRIMARY KEY, attempt_id TEXT NOT NULL, family_id TEXT, purpose TEXT NOT NULL, evidence_sha TEXT NOT NULL)"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS tier_b_reports (attempt_id TEXT PRIMARY KEY, receipt_path TEXT NOT NULL UNIQUE, record TEXT NOT NULL)"
    )


@contextmanager
def _tx(path: Path) -> Iterator[sqlite3.Connection]:
    with _transaction(path) as db:
        _create_tables(db)
        yield db


def _read(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(
        path.resolve(strict=True).as_uri() + "?mode=ro",
        uri=True,
        timeout=LEDGER_BUSY_TIMEOUT_SECONDS,
    )


def _attempt(db: sqlite3.Connection, attempt_id: str) -> TierBDeclaration:
    try:
        row = db.execute(
            "SELECT record FROM tier_b_attempts WHERE attempt_id=?", (attempt_id,)
        ).fetchone()
    except sqlite3.OperationalError:
        row = None
    if row is None:
        raise ValueError("undeclared Tier B attempt")
    return TierBDeclaration.model_validate_json(row[0])


def get_tier_b_attempt(path: Path, attempt_id: str) -> TierBDeclaration:
    with _read(path) as db:
        return _attempt(db, attempt_id)


def _verify(declaration: TierBDeclaration) -> None:
    declared = {str(Path(k).resolve()): v for k, v in declaration.source_pins.items()}
    if any(declared.get(k) != v for k, v in required_tier_b_source_pins().items()):
        raise ValueError("Tier B declaration omits or changes an execution source")
    # Shared pin/config checks; Tier A's fresh-only branch is not taken here.
    _verify_declaration(declaration)  # type: ignore[arg-type]


def _opened(db: sqlite3.Connection, attempt_id: str) -> bool:
    return bool(
        db.execute(
            "SELECT 1 FROM tier_b_exposures WHERE attempt_id=?", (attempt_id,)
        ).fetchone()
    )


def _tier_b_known(db: sqlite3.Connection, episode: TierBEpisodeSpec) -> bool:
    for (raw,) in db.execute("SELECT record FROM tier_b_attempts"):
        for prior in json.loads(raw)["episodes"]:
            if (
                prior["config_sha256"] == episode.config_sha256
                or prior["source_episode_id"] == episode.source_episode_id
            ):
                return True
    return False


def declare_tier_b_attempt(
    path: Path,
    declaration: TierBDeclaration,
    *,
    tier_a_ledger: Path | None,
    require_tier_a: bool = True,
) -> str:
    """Record the prospective Tier B design; roots must be fresh everywhere."""
    if require_tier_a:
        from .readiness_capture_ownership import require_admission

        if tier_a_ledger is None:
            raise ValueError("Tier B requires the Tier A admission ledger")
        receipt = require_admission(tier_a_ledger, Path(declaration.tier_a_admission_path))
        if receipt.protocol_sha256 != declaration.pre_protocol.tier_a_protocol_sha256:
            raise ValueError("Tier B floors must come from the admitted Tier A protocol")
    if file_sha(Path(declaration.tier_a_admission_path)) != declaration.tier_a_admission_sha256:
        raise ValueError("Tier A admission receipt differs from declaration")
    _verify(declaration)
    with _tx(path) as db:
        for episode in declaration.episodes:
            if _tier_b_known(db, episode):
                raise ValueError("Tier B episode already declared in an earlier attempt")
            prior = db.execute(
                "SELECT 1 FROM fresh_identities WHERE config_sha=? OR episode_id=?",
                (episode.config_sha256, episode.source_episode_id),
            ).fetchone()
            if prior is not None:
                raise ValueError("episode identity already used by a readiness attempt")
            for (raw,) in db.execute("SELECT record FROM attempts"):
                for other in json.loads(raw)["episodes"]:
                    if (
                        other["config_sha256"] == episode.config_sha256
                        or other["source_episode_id"] == episode.source_episode_id
                    ):
                        raise ValueError("episode already declared in a Tier A attempt")
            # Requires both a v7 native-root and a readiness-v2 registry.
            if _historically_known(
                episode,  # type: ignore[arg-type]
                declaration.historical_registries,
                ledger=path,
                attempt_id=declaration.attempt_id,
            ):
                raise ValueError("episode already occurs in a historical registry")
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
            "INSERT INTO tier_b_attempts VALUES (?,?,?)",
            (declaration.attempt_id, declaration.sha256, declaration.model_dump_json()),
        )
    return declaration.sha256


def claim_tier_b_episode(
    path: Path,
    *,
    attempt_id: str,
    family_id: str,
    output_path: Path,
    native_attestation_sha256: str,
) -> EpisodeClaim:
    if output_path.exists():
        raise ValueError("capture output already exists; no retries or redirection")
    with _tx(path) as db:
        declaration = _attempt(db, attempt_id)
        _verify(declaration)
        if _opened(db, attempt_id):
            raise ValueError("opened attempt cannot claim more capture work")
        episode = next((e for e in declaration.episodes if e.family_id == family_id), None)
        if episode is None or native_attestation_sha256 != declaration.native_attestation_sha256:
            raise ValueError("undeclared family or native runtime")
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
            "INSERT INTO tier_b_episode_claims VALUES (?,?,?,?,?)",
            (attempt_id, family_id, claim.nonce, claim.output_path, claim.model_dump_json()),
        )
    return claim


def _policy_record(directory: Path, declaration: TierBDeclaration) -> dict[str, Any]:
    payload = json.loads((directory / "policy-root.json").read_text())
    if payload.get("checkpoint_sha256") != declaration.checkpoint_sha256:
        raise ValueError("capture policy used a different checkpoint")
    return payload


def record_tier_b_capture(path: Path, claim: EpisodeClaim, receipt: CaptureReceipt) -> None:
    with _tx(path) as db:
        row = db.execute(
            "SELECT record FROM tier_b_episode_claims WHERE nonce=?", (claim.nonce,)
        ).fetchone()
        if row is None or EpisodeClaim.model_validate_json(row[0]) != claim:
            raise ValueError("capture claim identity or canonical path mismatch")
        declaration = _attempt(db, claim.attempt_id)
        if receipt.status != "failed":
            _verify(declaration)
        if (
            receipt.claim_nonce != claim.nonce
            or receipt.design_sha256 != claim.design_sha256
            or receipt.family_id != claim.family_id
            or receipt.config_sha256 != claim.config_sha256
            or receipt.native_attestation_sha256 != claim.native_attestation_sha256
        ):
            raise ValueError("capture receipt differs from its prospective claim")
        directory = Path(claim.output_path)
        _artifacts(directory, receipt.artifact_hashes)
        policy_json = None
        episode = next(e for e in declaration.episodes if e.family_id == claim.family_id)
        if receipt.status == "selected":
            family, binding = receipt.selected_family, receipt.capture_binding
            assert family is not None and binding is not None
            if (
                family.family_id != claim.family_id
                or family.independence_id != claim.source_episode_id
                or family.role != "fresh_acceptance"
                or family.root_owner != episode.root_owner
                or binding.family_id != claim.family_id
                or binding.config_sha256 != claim.config_sha256
                or _canonical(Path(binding.capture_path)) != claim.output_path
                or binding.root_sha256 != family.root_sha256
            ):
                raise ValueError("selected root was substituted or reassigned")
            plan = json.loads((directory / "plan.json").read_text())
            if canonical_sha(plan["root_request"]) != episode.root_request_sha256:
                raise ValueError("captured root request differs from declaration")
            binding.verify_files()
            if binding.input_hashes["gamedata.json"] != declaration.gamedata_sha256:
                raise ValueError("capture ruleset differs from declaration")
            if "policy-root.json" not in receipt.artifact_hashes:
                raise ValueError("selected Tier B root lacks its policy ranking record")
            payload = _policy_record(directory, declaration)
            record = PolicyRootRecord.model_validate(payload["record"])
            if (
                record.family_id != family.family_id
                or record.public_packet_sha256 != family.public_packet_sha256
                or record.candidate_actions != {c.role: c.action_id for c in family.candidates}
                or record.original_recommendation != family.original_recommendation
                or record.root_tick != binding.root_tick
                or record.probe_kind != episode.probe_kind
                or payload.get("root_request_sha256") != episode.root_request_sha256
            ):
                raise ValueError("policy ranking record differs from captured family")
            policy_json = record.model_dump_json()
        target = directory / "capture-receipt.json"
        with target.open("x") as stream:
            stream.write(receipt.model_dump_json(indent=2) + "\n")
        db.execute(
            "INSERT INTO tier_b_captures VALUES (?,?,?,?)",
            (claim.attempt_id, claim.family_id, receipt.model_dump_json(), policy_json),
        )


def _captures(db: sqlite3.Connection, attempt_id: str) -> list[tuple[str, CaptureReceipt, str | None, EpisodeClaim]]:
    rows = db.execute(
        "SELECT c.family_id,c.record,c.policy_record,e.record FROM tier_b_captures c JOIN tier_b_episode_claims e ON c.attempt_id=e.attempt_id AND c.family_id=e.family_id WHERE c.attempt_id=? ORDER BY c.family_id",
        (attempt_id,),
    ).fetchall()
    return [
        (
            family_id,
            CaptureReceipt.model_validate_json(raw),
            policy,
            EpisodeClaim.model_validate_json(claim),
        )
        for family_id, raw, policy, claim in rows
    ]


def expected_generation_failures(receipts: list[CaptureReceipt]) -> tuple[str, ...]:
    return tuple(
        f"{r.family_id}: {r.status}" + (f" ({r.failure})" if r.failure else "")
        for r in sorted(receipts, key=lambda r: r.family_id)
        if r.status != "selected"
    )


def seal_tier_b_roots(path: Path, *, attempt_id: str, protocol: TierBProtocol) -> TierBRootSeal:
    """Freeze roots, candidates and policy rankings before any branch outcome."""
    with _tx(path) as db:
        declaration = _attempt(db, attempt_id)
        _verify(declaration)
        if _opened(db, attempt_id):
            raise ValueError("opened attempts cannot be resealed")
        if protocol.status != "frozen":
            raise ValueError("Tier B root seal requires a frozen protocol")
        ignore = {"status", "families", "policy_roots", "generation_failures"}
        if protocol.model_dump(exclude=ignore) != declaration.pre_protocol.model_dump(
            exclude=ignore
        ):
            raise ValueError("criteria, strata or pins changed after declaration")
        rows = _captures(db, attempt_id)
        if {r[0] for r in rows} != {e.family_id for e in declaration.episodes}:
            raise ValueError("every declared root needs a recorded capture outcome")
        hashes, families, records = {}, {}, {}
        for family_id, receipt, policy_json, claim in rows:
            _artifacts(Path(claim.output_path), receipt.artifact_hashes)
            saved = Path(claim.output_path) / "capture-receipt.json"
            if CaptureReceipt.model_validate_json(saved.read_text()) != receipt:
                raise ValueError("capture receipt changed")
            hashes[family_id] = file_sha(saved)
            if receipt.status == "selected":
                assert policy_json is not None
                families[family_id] = receipt.selected_family
                records[family_id] = PolicyRootRecord.model_validate_json(policy_json)
        if {f.family_id: f for f in protocol.families} != families:
            raise ValueError("protocol roots/candidates differ from captured bindings")
        if {p.family_id: p for p in protocol.policy_roots} != records:
            raise ValueError("protocol policy rankings differ from captured records")
        if protocol.generation_failures != expected_generation_failures(
            [r[1] for r in rows]
        ):
            raise ValueError("every uncaptured root must remain as a declared failure")
        seal = TierBRootSeal(
            attempt_id=attempt_id,
            design_sha256=declaration.sha256,
            protocol=protocol,
            capture_receipt_hashes=hashes,
        )
        db.execute(
            "INSERT INTO tier_b_root_seals VALUES (?,?,?)",
            (attempt_id, seal.sha256, seal.model_dump_json()),
        )
    return seal


def get_tier_b_root_seal(path: Path, attempt_id: str) -> TierBRootSeal:
    with _read(path) as db:
        row = db.execute(
            "SELECT record FROM tier_b_root_seals WHERE attempt_id=?", (attempt_id,)
        ).fetchone()
    if row is None:
        raise ValueError("Tier B attempt has no root seal")
    return TierBRootSeal.model_validate_json(row[0])


def _verify_sealed(path: Path, declaration: TierBDeclaration, seal: TierBRootSeal) -> None:
    with _read(path) as db:
        rows = _captures(db, declaration.attempt_id)
    if len(rows) != len(declaration.episodes):
        raise ValueError("Tier B seal lost a declared capture")
    expected = {f.family_id: f for f in seal.protocol.families}
    for family_id, receipt, _policy, claim in rows:
        if claim.design_sha256 != declaration.sha256:
            raise ValueError("capture canonical ownership changed")
        directory = Path(claim.output_path)
        _artifacts(directory, receipt.artifact_hashes)
        if file_sha(directory / "capture-receipt.json") != seal.capture_receipt_hashes.get(
            family_id
        ):
            raise ValueError("sealed capture receipt changed")
        if receipt.status == "selected":
            binding = receipt.capture_binding
            assert binding is not None
            if receipt.selected_family != expected.get(family_id):
                raise ValueError("captured root differs from its seal")
            binding.verify_files()


def require_tier_b_execution_plan(path: Path, plan: Any, *, attempt_id: str) -> TierBDeclaration:
    declaration = get_tier_b_attempt(path, attempt_id)
    seal = get_tier_b_root_seal(path, attempt_id)
    _verify(declaration)
    _verify_sealed(path, declaration, seal)
    if (
        plan.purpose != "tier_b_transfer"
        or plan.protocol != seal.protocol
        or plan.source_pins != declaration.source_pins
    ):
        raise ValueError("execution plan differs from the sealed Tier B protocol")
    if (
        set(plan.engines) != {"scalar", "reference"}
        or plan.repetitions != 1
        or plan.selected_conditions != CONDITIONS
        or plan.selected_roles != ROLES
    ):
        raise ValueError("Tier B execution requires the entire branch design")
    if (
        plan.catalog_sha256 != declaration.catalog_sha256
        or plan.native_attestation_sha256 != declaration.native_attestation_sha256
    ):
        raise ValueError("execution catalog or runtime differs from declaration")
    with _read(path) as db:
        bindings = {
            r.family_id: r.capture_binding
            for _, r, _, _ in _captures(db, attempt_id)
            if r.status == "selected"
        }
    if {c.family_id: c for c in plan.captures} != bindings:
        raise ValueError("execution capture bindings differ from the Tier B seal")
    plan.verify_inputs()
    return declaration


def claim_tier_b_branch(
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
    with _tx(path) as db:
        declaration = _attempt(db, attempt_id)
        _verify(declaration)
        raw = db.execute(
            "SELECT record FROM tier_b_root_seals WHERE attempt_id=?", (attempt_id,)
        ).fetchone()
        if raw is None:
            raise ValueError("branch execution requires a Tier B root seal")
        if _opened(db, attempt_id):
            raise ValueError("opened attempts cannot claim new branches")
        seal = TierBRootSeal.model_validate_json(raw[0])
        family = next((f for f in seal.protocol.families if f.family_id == family_id), None)
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
            "INSERT INTO tier_b_branch_claims VALUES (?,?,?,?,?,?,?,?)",
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


def _check_branch(
    db: sqlite3.Connection,
    claim: BranchClaim,
    branch: Branch,
    artifact_hashes: dict[str, str],
    *,
    audit_transport: bool,
) -> None:
    stored = db.execute(
        "SELECT record FROM tier_b_branch_claims WHERE nonce=?", (claim.nonce,)
    ).fetchone()
    if stored is None or BranchClaim.model_validate_json(stored[0]) != claim:
        raise ValueError("unclaimed Tier B branch result or changed output path")
    declaration = _attempt(db, claim.attempt_id)
    _verify(declaration)
    seal = TierBRootSeal.model_validate_json(
        db.execute(
            "SELECT record FROM tier_b_root_seals WHERE attempt_id=?", (claim.attempt_id,)
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
            "SELECT record FROM tier_b_captures WHERE attempt_id=? AND family_id=?",
            (claim.attempt_id, claim.family_id),
        ).fetchone()[0]
    )
    binding = capture.capture_binding
    assert binding is not None
    if (
        _canonical(Path(result["capture_path"])) != _canonical(Path(binding.capture_path))
        or result["root_tick"] != binding.root_tick
        or result["root_owner"] != family.root_owner
        or result.get("calibration_receipt_sha256") not in declaration.input_pins.values()
        or result["gamedata_sha256"] != declaration.gamedata_sha256
        or result["catalog_sha256"] != declaration.catalog_sha256
        or result["native_attestation_sha256"] != declaration.native_attestation_sha256
    ):
        raise ValueError("branch source, perspective or runtime differs from declaration")
    _verify_branch_files(claim, branch, artifact_hashes, audit_transport=audit_transport)


def record_tier_b_branch_result(
    path: Path, claim: BranchClaim, branch: Branch, *, artifact_hashes: dict[str, str]
) -> None:
    with _read(path) as snapshot:
        _check_branch(snapshot, claim, branch, artifact_hashes, audit_transport=True)
    with _tx(path) as db:
        _check_branch(db, claim, branch, artifact_hashes, audit_transport=False)
        db.execute(
            "INSERT INTO tier_b_branch_results VALUES (?,?,?)",
            (claim.nonce, branch.model_dump_json(), json.dumps(artifact_hashes, sort_keys=True)),
        )


def tier_b_claimed_branch_keys(
    path: Path, *, attempt_id: str
) -> frozenset[tuple[str, str, str, str]]:
    with _read(path) as db:
        _attempt(db, attempt_id)
        return frozenset(
            tuple(row)
            for row in db.execute(
                "SELECT family_id,condition,role,engine FROM tier_b_branch_claims WHERE attempt_id=?",
                (attempt_id,),
            )
        )


def record_tier_b_exposure(
    path: Path,
    *,
    attempt_id: str,
    purpose: Literal["evaluation", "inspection", "repair", "training"],
    evidence_sha256: str,
    family_id: str | None = None,
) -> None:
    with _tx(path) as db:
        declaration = _attempt(db, attempt_id)
        if family_id is not None and family_id not in {
            e.family_id for e in declaration.episodes
        }:
            raise ValueError("undeclared exposure family")
        if purpose == "training":
            raise ValueError("Tier B roots can never enter training")
        db.execute(
            "INSERT INTO tier_b_exposures(attempt_id,family_id,purpose,evidence_sha) VALUES (?,?,?,?)",
            (attempt_id, family_id, purpose, evidence_sha256),
        )


def evaluate_tier_b_attempt(
    path: Path,
    *,
    attempt_id: str,
    calibration_receipt_path: Path,
    report_path: Path,
    receipt_path: Path,
    reviews: tuple[MechanismReview, ...] = (),
    calibration_checker: Any = None,
) -> tuple[TierBReport, TierBReportReceipt]:
    """Open all Tier B outcomes once; every root stays in accounting."""
    declaration = get_tier_b_attempt(path, attempt_id)
    seal = get_tier_b_root_seal(path, attempt_id)
    _verify(declaration)
    _verify_sealed(path, declaration, seal)
    calibration = (calibration_checker or _checked_calibration)(calibration_receipt_path)
    _require_calibration_scope(calibration, declaration)  # type: ignore[arg-type]
    calibration_sha = file_sha(calibration_receipt_path)
    if declaration.input_pins.get(str(calibration_receipt_path.resolve())) != calibration_sha:
        raise ValueError("calibration evidence differs from pre-capture input pins")
    record_tier_b_exposure(
        path,
        attempt_id=attempt_id,
        purpose="evaluation",
        evidence_sha256=canonical_sha(
            {"calibration": str(calibration_receipt_path.resolve()), "report": str(report_path.resolve())}
        ),
    )
    with _read(path) as db:
        rows = db.execute(
            "SELECT c.record,r.branch,r.artifacts FROM tier_b_branch_claims c JOIN tier_b_branch_results r ON c.nonce=r.nonce WHERE c.attempt_id=?",
            (attempt_id,),
        ).fetchall()
    branches = []
    for raw_claim, raw_branch, raw_artifacts in rows:
        claim = BranchClaim.model_validate_json(raw_claim)
        branch = Branch.model_validate_json(raw_branch)
        _verify_branch_files(claim, branch, json.loads(raw_artifacts), audit_transport=True)
        result = json.loads((Path(claim.output_path) / "result.json").read_text())
        if result.get("calibration_receipt_sha256") != calibration_sha:
            raise ValueError("branch used a different calibration receipt")
        branches.append(branch)
    report = evaluate_tier_b(seal.protocol, tuple(branches), reviews)
    with report_path.open("x") as stream:
        stream.write(report.model_dump_json(indent=2) + "\n")
    receipt = TierBReportReceipt(
        attempt_id=attempt_id,
        block_kind=declaration.block_kind,
        status=report.status,
        ledger_path=_canonical(path),
        design_sha256=declaration.sha256,
        root_seal_sha256=seal.sha256,
        protocol_sha256=seal.protocol.sha256,
        checkpoint_sha256=declaration.checkpoint_sha256,
        report_path=_canonical(report_path),
        report_sha256=file_sha(report_path),
        calibration_receipt_sha256=calibration_sha,
    )
    with _tx(path) as db:
        with receipt_path.open("x") as stream:
            stream.write(receipt.model_dump_json(indent=2) + "\n")
        db.execute(
            "INSERT INTO tier_b_reports VALUES (?,?,?)",
            (attempt_id, _canonical(receipt_path), receipt.model_dump_json()),
        )
    return report, receipt


# ---------------------------------------------------------------------------
# Declaration inputs and the frozen protocol, built from pinned files only.


class TierBConfigEntry(Record):
    family_id: str
    source_episode_id: str
    root_request_sha256: SHA
    config_path: str
    config_file_sha256: SHA
    config_sha256: SHA


class TierBConfigManifest(Record):
    schema_version: Literal["readiness-v2-tier-b-native-configs-v1"] = (
        "readiness-v2-tier-b-native-configs-v1"
    )
    root_bank_sha256: SHA
    root_bank_file_sha256: SHA
    template_config_sha256: SHA
    gamedata_sha256: SHA
    gamedata_path: str
    episodes: tuple[TierBConfigEntry, ...]


def materialize_tier_b_configs(
    bank: TierBRootBank,
    *,
    template_capture: Path,
    expected_template_plan_sha256: str,
    gamedata: Path,
    expected_gamedata_sha256: str,
    output: Path,
) -> TierBConfigManifest:
    """Reuse the Tier A config converter; any unsupported request fails loudly."""
    from clasher.data import CardDataLoader

    from .readiness_native_config import config_for_request, load_verified_template

    if file_sha(gamedata) != expected_gamedata_sha256:
        raise ValueError("declared gamedata hash changed")
    template = load_verified_template(template_capture, expected_template_plan_sha256)
    loader = CardDataLoader(gamedata)
    template_loader = CardDataLoader(template_capture / "gamedata.json")
    output.mkdir(parents=True, exist_ok=False)
    (output / "configs").mkdir()
    bank_path = output / "root-bank.json"
    bank_path.write_text(bank.model_dump_json(indent=2) + "\n")
    entries = []
    for index, request in enumerate(bank.requests):
        config = config_for_request(request, template, loader, template_loader)  # type: ignore[arg-type]
        path = output / "configs" / f"episode-{index:02d}.json"
        path.write_text(json.dumps(config, indent=2) + "\n")
        entries.append(
            TierBConfigEntry(
                family_id=request.family_id,
                source_episode_id=request.source_episode_id,
                root_request_sha256=canonical_sha(request.model_dump(mode="json")),
                config_path=str(path.resolve()),
                config_file_sha256=file_sha(path),
                config_sha256=canonical_sha(config),
            )
        )
    manifest = TierBConfigManifest(
        root_bank_sha256=canonical_sha(bank.model_dump(mode="json")),
        root_bank_file_sha256=file_sha(bank_path),
        template_config_sha256=canonical_sha(template),
        gamedata_sha256=file_sha(gamedata),
        gamedata_path=str(gamedata.resolve()),
        episodes=tuple(entries),
    )
    (output / "manifest.json").write_text(manifest.model_dump_json(indent=2) + "\n")
    return manifest


def tier_b_declaration_from_bank(
    *,
    attempt_id: str,
    bank: TierBRootBank,
    manifest_path: Path,
    checkpoint_path: Path,
    tier_a_admission_path: Path,
    tier_a_protocol: Any,
    generator_path: Path,
    native_attestation_sha256: str,
    catalog_path: Path,
    calibration_path: Path,
    historical_registries: tuple[Path, ...],
    decks_path: Path | None = None,
    source_pins: dict[str, str] | None = None,
) -> TierBDeclaration:
    """Assemble the prospective declaration; floors come from admitted Tier A."""
    manifest = TierBConfigManifest.model_validate_json(manifest_path.read_text())
    if manifest.root_bank_sha256 != canonical_sha(bank.model_dump(mode="json")):
        raise ValueError("config manifest was built from another root bank")
    entries = {e.family_id: e for e in manifest.episodes}
    workspace = Path(__file__).resolve().parents[3] / "gamedata.json"
    pins = source_pins if source_pins is not None else required_tier_b_source_pins()
    inputs = {
        str(p.resolve()): file_sha(p)
        for p in (
            Path(manifest.gamedata_path),
            workspace,
            manifest_path,
            checkpoint_path,
            tier_a_admission_path,
            catalog_path,
            calibration_path,
            *(() if decks_path is None else (decks_path,)),
        )
    }
    protocol = bank.protocol_draft(
        attempt_id,
        source_pins=pins,
        config_sha256=canonical_sha([e.config_sha256 for e in manifest.episodes]),
        generator_sha256=file_sha(generator_path),
        floors=tier_a_protocol.floors,
        tier_a_protocol_sha256=tier_a_protocol.sha256,
    )
    episodes = []
    for request in bank.requests:
        entry = entries[request.family_id]
        if entry.root_request_sha256 != canonical_sha(request.model_dump(mode="json")):
            raise ValueError("config entry differs from its root request")
        episodes.append(
            TierBEpisodeSpec(
                family_id=request.family_id,
                source_episode_id=request.source_episode_id,
                config_path=entry.config_path,
                config_file_sha256=entry.config_file_sha256,
                config_sha256=entry.config_sha256,
                root_request_sha256=entry.root_request_sha256,
                root_owner=request.root_owner,
                deck_id=request.deck_id,
                phase=request.phase,
                opponent=request.opponent,
                probe_kind=request.probe_kind,
            )
        )
    return TierBDeclaration(
        attempt_id=attempt_id,
        block_kind=bank.block_kind,
        root_bank_sha256=manifest.root_bank_sha256,
        generator_sha256=file_sha(generator_path),
        converter_manifest_sha256=file_sha(manifest_path),
        checkpoint_path=str(checkpoint_path.resolve()),
        checkpoint_sha256=file_sha(checkpoint_path),
        tier_a_admission_path=str(tier_a_admission_path.resolve()),
        tier_a_admission_sha256=file_sha(tier_a_admission_path),
        pre_protocol=protocol,
        native_attestation_sha256=native_attestation_sha256,
        gamedata_sha256=manifest.gamedata_sha256,
        catalog_sha256=file_sha(catalog_path),
        workspace_gamedata_sha256=file_sha(workspace),
        source_pins=pins,
        input_pins=inputs,
        episodes=tuple(episodes),
        historical_registries=tuple(_canonical(p) for p in historical_registries),
    )


def build_frozen_tier_b_protocol(path: Path, *, attempt_id: str) -> TierBProtocol:
    """Freeze the declared design with every recorded capture outcome."""
    declaration = get_tier_b_attempt(path, attempt_id)
    with _read(path) as db:
        rows = _captures(db, attempt_id)
    if {r[0] for r in rows} != {e.family_id for e in declaration.episodes}:
        raise ValueError("every declared root needs a recorded capture outcome")
    families, records = [], []
    for _family_id, receipt, policy_json, _claim in rows:
        if receipt.status == "selected":
            assert receipt.selected_family is not None and policy_json is not None
            families.append(receipt.selected_family)
            records.append(PolicyRootRecord.model_validate_json(policy_json))
    return TierBProtocol.model_validate(
        {
            **declaration.pre_protocol.model_dump(),
            "status": "frozen",
            "families": [f.model_dump() for f in families],
            "policy_roots": [r.model_dump() for r in records],
            "generation_failures": expected_generation_failures([r[1] for r in rows]),
        },
        strict=False,
    )
