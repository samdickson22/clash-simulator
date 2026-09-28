"""Persistent role assignments for deterministic native reference roots."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Role = Literal["development", "training", "selection", "acceptance"]


class NativeRootRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    schema_version: Literal[1] = 1
    duplicate_group_id: str = Field(pattern=r"^native-root-v1:[0-9a-f]{64}$")
    config_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    role: Role


def canonical_digest(value) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def register_native_root(path: Path, config: dict, *, role: Role) -> NativeRootRecord:
    """Bind a root before collection; repeats cannot change its data role.

    The config includes native seed, decks, level caps and match settings.
    Paths, collector versions and the approximate scalar ruleset are excluded:
    repairing or copying a capture must not create a fresh acceptance root.
    Seat-swapped or otherwise transformed configs need an explicit shared family
    assignment before acceptance; this exact-config registry cannot infer those.
    """
    if not isinstance(config, dict) or type(config.get("rndSeed")) is not int:
        raise ValueError("native root needs an explicit integer seed")
    if not isinstance(config.get("battle"), dict):
        raise TypeError("native root needs a battle configuration")
    digest = canonical_digest(config)
    record = NativeRootRecord(
        duplicate_group_id=f"native-root-v1:{digest}", config_sha256=digest, role=role
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path, timeout=30) as db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS native_roots (group_id TEXT PRIMARY KEY, record TEXT NOT NULL)"
        )
        db.execute("BEGIN IMMEDIATE")
        existing = db.execute(
            "SELECT record FROM native_roots WHERE group_id=?",
            (record.duplicate_group_id,),
        ).fetchone()
        if existing:
            prior = NativeRootRecord.model_validate_json(existing[0])
            if prior != record:
                raise ValueError(f"native root already assigned to {prior.role}")
            return prior
        db.execute(
            "INSERT INTO native_roots VALUES (?, ?)",
            (record.duplicate_group_id, record.model_dump_json()),
        )
    return record


def native_match_id(root: NativeRootRecord, commands: list[dict]) -> str:
    """Identify an executed command sequence, independent of capture receipts.

    Each command must use native card IDs and integer world coordinates. The
    caller supplies only execution semantics, excluding process-specific IDs.
    """
    keys = {"owner", "card_id", "x", "y", "submitted_tick", "execution_tick"}
    for command in commands:
        if set(command) != keys or any(type(v) is not int for v in command.values()):
            raise ValueError("canonical native command fields must be exact integers")
        if (
            command["owner"] not in (0, 1)
            or command["execution_tick"] != command["submitted_tick"] + 1
        ):
            raise ValueError("invalid owner or unverified execution boundary")
    return "native-match-v1:" + canonical_digest(
        {"root": root.duplicate_group_id, "commands": commands}
    )
