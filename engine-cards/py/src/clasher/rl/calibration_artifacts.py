"""Completion receipts for prospective evidence files, without acceptance claims."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Kind = Literal["native_capture", "paired_branches"]


class ArtifactReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    schema_version: Literal[1] = 1
    kind: Kind
    role: Literal["development", "acceptance"]
    collection_protocol_sha256: Digest | None
    files: dict[str, Digest] = Field(min_length=1)

    @model_validator(mode="after")
    def acceptance_requires_protocol(self):
        if self.role == "acceptance" and self.collection_protocol_sha256 is None:
            raise ValueError("acceptance artifacts require a frozen protocol identity")
        return self


def artifact_digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def _artifact_path(directory: Path, name: str) -> Path:
    relative = Path(name)
    candidate = directory / relative
    if (
        relative.is_absolute()
        or ".." in relative.parts
        or not candidate.resolve().is_relative_to(directory.resolve())
    ):
        raise ValueError("artifact path leaves its evidence directory")
    if name == "artifact-receipt.json":
        raise ValueError("artifact receipt cannot hash itself")
    return candidate


def seal_artifacts(
    directory: Path,
    *,
    kind: Kind,
    role: str,
    protocol_sha256: str | None,
    paths: set[str],
) -> ArtifactReceipt:
    receipt = ArtifactReceipt(
        kind=kind,
        role=role,
        collection_protocol_sha256=protocol_sha256,
        files={
            name: artifact_digest(_artifact_path(directory, name))
            for name in sorted(paths)
        },
    )
    with (directory / "artifact-receipt.json").open("x") as f:
        f.write(receipt.model_dump_json(indent=2) + "\n")
    return receipt


def verify_artifacts(
    directory: Path,
    *,
    kind: Kind,
    role: str,
    protocol_sha256: str | None,
    required_paths: set[str],
) -> ArtifactReceipt:
    receipt = ArtifactReceipt.model_validate_json(
        (directory / "artifact-receipt.json").read_bytes()
    )
    if (
        receipt.kind != kind
        or receipt.role != role
        or receipt.collection_protocol_sha256 != protocol_sha256
    ):
        raise ValueError("artifact role/kind/protocol binding differs")
    if set(receipt.files) != required_paths:
        raise ValueError("artifact inventory is incomplete or unexpected")
    for name, expected in receipt.files.items():
        if artifact_digest(_artifact_path(directory, name)) != expected:
            raise ValueError(f"completed evidence file changed: {name}")
    return receipt


def capture_artifact_paths(*, family: bool, prospective: bool) -> set[str]:
    result = {
        "plan.json",
        "gamedata.json",
        "initial.json",
        "native-attestation.json",
        "result.json",
        "root-identity.json",
        "producer-source.zip",
        "native-frames.jsonl.gz",
    }
    result.update(
        f"seat{owner}/{name}"
        for owner in (0, 1)
        for name in ("decisions.json", "masks.npy", "observations.npz", "receipt.json")
    )
    if family:
        result.add("family-identity.json")
    if prospective:
        result.add("collection-protocol.json")
    return result


def branch_artifact_paths(protocol: dict, engines: tuple[str, ...]) -> set[str]:
    result = {
        "protocol.json",
        "provenance.json",
        "producer-source.zip",
        "results.json",
        "complete.json",
    }
    for seed in protocol["response_seeds"]:
        for candidate in protocol["candidates"]:
            for engine in engines:
                prefix = f"{seed}-{candidate['name']}-{engine}"
                result.update(
                    f"{prefix}/{name}" for name in ("result.json", "decisions.jsonl.gz")
                )
    return result


def read_branch_evidence(
    directory: Path, *, protocol: dict, engines: tuple[str, ...], protocol_sha256: str
) -> list[dict]:
    """Read a sealed complete branch batch; full campaign provenance is checked upstream."""
    import json

    if (
        protocol.get("role") != "acceptance"
        or protocol.get("collection_protocol_sha256") != protocol_sha256
    ):
        raise ValueError("expected branch protocol is not bound acceptance evidence")
    if (
        not engines
        or len(set(engines)) != len(engines)
        or any(e not in ("native", "scalar") for e in engines)
    ):
        raise ValueError("invalid branch engine inventory")
    verify_artifacts(
        directory,
        kind="paired_branches",
        role="acceptance",
        protocol_sha256=protocol_sha256,
        required_paths=branch_artifact_paths(protocol, engines),
    )
    if json.loads((directory / "protocol.json").read_text()) != protocol:
        raise ValueError("saved branch protocol differs from expected candidates")
    complete = json.loads((directory / "complete.json").read_text())
    if (
        complete.get("role") != "acceptance"
        or complete.get("sources_unchanged") is not True
        or complete.get("collection_protocol_sha256") != protocol_sha256
    ):
        raise ValueError("branch completion receipt is not valid acceptance evidence")
    results = json.loads((directory / "results.json").read_text())
    expected = {
        (seed, c["name"], engine)
        for seed in protocol["response_seeds"]
        for c in protocol["candidates"]
        for engine in engines
    }
    indexed = {(r["response_seed"], r["candidate"], r["engine"]): r for r in results}
    if (
        len(indexed) != len(results)
        or set(indexed) != expected
        or complete.get("branches") != len(expected)
    ):
        raise ValueError("missing or duplicate declared branch results")
    for (seed, candidate, engine), result in indexed.items():
        if result["failure"] is not None or result["terminal"] is None:
            raise ValueError("incomplete branch cannot receive an outcome score")
        parent = directory / f"{seed}-{candidate}-{engine}" / "result.json"
        if json.loads(parent.read_text()) != result:
            raise ValueError("aggregate branch result differs from individual result")
    return results
