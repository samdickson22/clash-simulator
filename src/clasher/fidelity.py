"""Compare declared game observations with a pinned simulator trace.

Passing means agreement with the supplied observations, not proof of their
authenticity, complete mechanic coverage, or policy strength.
"""

from __future__ import annotations

import hashlib
import json
import math
from itertools import pairwise
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Scalar = bool | int | float | str | None
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Name = Annotated[str, Field(min_length=1)]


class StrictRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class Exact(StrictRecord):
    kind: Literal["exact"]
    value: Scalar


class Interval(StrictRecord):
    kind: Literal["interval"]
    lower: float
    upper: float

    @model_validator(mode="after")
    def ordered(self) -> Interval:
        if self.lower > self.upper:
            raise ValueError("reversed measurement interval")
        return self


Expectation = Annotated[Exact | Interval, Field(discriminator="kind")]


class Observation(StrictRecord):
    earliest_tick: Annotated[int, Field(ge=0)]
    latest_tick: Annotated[int, Field(ge=0)]
    facts: Annotated[dict[Name, Expectation], Field(min_length=1)]

    @model_validator(mode="after")
    def ordered(self) -> Observation:
        if self.earliest_tick > self.latest_tick:
            raise ValueError("reversed observation time window")
        return self


class Evidence(StrictRecord):
    kind: Literal["external_game_reference", "simulator_control"]
    artifact: Name
    artifact_sha256: Digest
    source: Name
    game_build: Name | None
    annotation_method: Name
    timing_method: Name


class ReferenceCase(StrictRecord):
    schema_version: Literal[1]
    case_id: Name
    ruleset_id: Name
    tick_ms: Annotated[int, Field(gt=0)]
    evidence: Evidence
    observations: Annotated[list[Observation], Field(min_length=1)]

    @model_validator(mode="after")
    def chronological(self) -> ReferenceCase:
        starts = [row.earliest_tick for row in self.observations]
        if any(b <= a for a, b in pairwise(starts)):
            raise ValueError("observations must have strictly increasing start ticks")
        return self


class TraceFrame(StrictRecord):
    tick: Annotated[int, Field(ge=0)]
    facts: Annotated[dict[Name, Scalar], Field(min_length=1)]


class CandidateTrace(StrictRecord):
    schema_version: Literal[1]
    case_id: Name
    ruleset_id: Name
    tick_ms: Annotated[int, Field(gt=0)]
    game_build: Name | None
    backend: Literal["scalar_reference", "tensor_backend"]
    source_sha256: Digest
    frames: Annotated[list[TraceFrame], Field(min_length=1)]

    @model_validator(mode="after")
    def continuous(self) -> CandidateTrace:
        ticks = [row.tick for row in self.frames]
        if any(b != a + 1 for a, b in pairwise(ticks)):
            raise ValueError("candidate frames must be consecutive and unique")
        return self


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _matches(expectation: Exact | Interval, actual: Scalar) -> bool:
    if isinstance(expectation, Interval):
        return (
            type(actual) in (int, float)
            and math.isfinite(actual)
            and expectation.lower <= actual <= expectation.upper
        )
    expected = expectation.value
    # JSON numbers may differ in integer/float representation, but bool is
    # not numeric evidence. Python's True == 1 must not certify a hit count.
    if type(expected) in (int, float) and type(actual) in (int, float):
        return expected == actual
    return type(expected) is type(actual) and expected == actual


def compare(case: ReferenceCase, trace: CandidateTrace) -> dict:
    for field in ("case_id", "ruleset_id", "tick_ms"):
        if getattr(case, field) != getattr(trace, field):
            raise ValueError(f"incompatible {field}")
    if case.evidence.kind == "external_game_reference":
        if case.evidence.game_build is None or trace.game_build is None:
            raise ValueError("external comparison requires declared game builds")
        if case.evidence.game_build != trace.game_build:
            raise ValueError("incompatible game_build")

    frames = {frame.tick: frame.facts for frame in trace.frames}
    rows = []
    last_match = -1
    for observation in case.observations:
        first, last = observation.earliest_tick, observation.latest_tick
        if first < trace.frames[0].tick or last > trace.frames[-1].tick:
            raise ValueError("candidate does not cover the full observation window")
        attempts = []
        matched_tick = None
        for tick in range(first, last + 1):
            if tick <= last_match:
                continue
            actual = frames[tick]
            differences = {
                key: {
                    "expected": expected.model_dump(),
                    "present": key in actual,
                    "actual": actual.get(key),
                }
                for key, expected in observation.facts.items()
                if key not in actual or not _matches(expected, actual[key])
            }
            attempts.append({"tick": tick, "differences": differences})
            if not differences:
                matched_tick = tick
                break
        if matched_tick is not None:
            # Earliest joint match leaves the most room for later windows.
            last_match = matched_tick
        rows.append(
            {
                "earliest_tick": first,
                "latest_tick": last,
                "matched_tick": matched_tick,
                "passed": matched_tick is not None,
                "attempts": attempts,
            }
        )
    passed = all(row["passed"] for row in rows)
    return {
        "schema": "clasher.fidelity-comparison.v1",
        "case_id": case.case_id,
        "ruleset_id": case.ruleset_id,
        "status": "comparison-passed" if passed else "comparison-failed",
        "evidence_kind": case.evidence.kind,
        "candidate_backend": trace.backend,
        "source_sha256": trace.source_sha256,
        "evidence_artifact_verified": False,
        "observations": rows,
        "first_divergence": next(
            (i for i, row in enumerate(rows) if not row["passed"]), None
        ),
        "fidelity_acceptance": False,
        "scope": "Agreement with declared observations only; no independent source authentication or mechanic coverage certification.",
    }


def compare_files(case_path: Path, trace_path: Path) -> dict:
    case_bytes = case_path.read_bytes()
    trace_bytes = trace_path.read_bytes()
    case = ReferenceCase.model_validate_json(case_bytes)
    trace = CandidateTrace.model_validate_json(trace_bytes)
    root = case_path.resolve().parent
    artifact = (root / case.evidence.artifact).resolve()
    if not artifact.is_relative_to(root):
        raise ValueError("evidence artifact must be inside the case directory")
    if sha256(artifact) != case.evidence.artifact_sha256:
        raise ValueError("evidence artifact digest mismatch")
    report = compare(case, trace)
    report["evidence_artifact_verified"] = True
    report["inputs"] = {
        "case_sha256": hashlib.sha256(case_bytes).hexdigest(),
        "trace_sha256": hashlib.sha256(trace_bytes).hexdigest(),
        "evidence_sha256": case.evidence.artifact_sha256,
    }
    return report


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", type=Path)
    parser.add_argument("trace", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = compare_files(args.case, args.trace)
    with args.output.open("x") as output:
        json.dump(report, output, indent=2, allow_nan=False)
        output.write("\n")
    if report["status"] != "comparison-passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
