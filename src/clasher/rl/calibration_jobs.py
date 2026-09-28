"""Durable sequential job receipts; a missing observation never authorizes a retry."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class JobSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    command: tuple[str, ...] = Field(min_length=1)
    cwd: str = Field(min_length=1)
    native: bool
    protocol_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


def atomic_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as f:
        json.dump(value, f, indent=2)
        f.write("\n")
        temporary = f.name
    os.replace(temporary, path)


def process_identity(pid: int) -> str | None:
    result = subprocess.run(
        ["ps", "-p", str(pid), "-o", "lstart=", "-o", "command="],
        capture_output=True,
        text=True,
        check=False,
    )
    value = result.stdout.strip()
    return value if result.returncode == 0 and value else None


def job_status(directory: Path, spec: JobSpec):
    request = JobSpec.model_validate_json((directory / "request.json").read_bytes())
    if request != spec:
        raise ValueError("job request changed; cannot reuse evidence")
    terminal = directory / "complete.json"
    if terminal.exists():
        result = json.loads(terminal.read_text())
        if (
            result["request"] != spec.model_dump(mode="json")
            or type(result["exit_code"]) is not int
        ):
            raise ValueError("job terminal receipt does not match request")
        # Terminal receipt is written only after wait() reaps the actual child.
        return "complete", result["exit_code"]
    for filename in ("running.json", "launch.json"):
        path = directory / filename
        if path.exists():
            state = json.loads(path.read_text())
            pid = state["pid"]
            identity = state["identity"]
            if type(pid) is int and identity and process_identity(pid) == identity:
                return "running", None
    return "unresolved", None
