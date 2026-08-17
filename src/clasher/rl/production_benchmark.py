"""Fail-closed evidence helpers for production simulator benchmarks.

This module deliberately keeps measurement policy separate from the simulator:
timings are not valid evidence unless the paired outputs match exactly and the
candidate reports fully tensor-resident execution with no fallback or shadow
mismatch.  The CLI driver lives in ``scripts/perf``.
"""

from __future__ import annotations

import fcntl
import hashlib
import inspect
import json
import os
import shlex
import subprocess
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO

import numpy as np
from typing_extensions import Self

REFERENCE_BACKEND = "python"
CANDIDATE_BACKEND = "pytorch"
REQUIRED_BACKEND_METRICS = (
    "tensor_ticks",
    "python_ticks",
    "shadow_checks",
    "shadow_mismatches",
    "unsupported_fallbacks",
)


@dataclass(frozen=True)
class CompetingProcess:
    """Sanitized identity for a process that blocks benchmark admission."""

    pid: int
    category: str
    executable: str


@dataclass(frozen=True)
class CapabilityCheck:
    available: bool
    reason: str | None = None


class BenchmarkLeaseError(RuntimeError):
    """Raised when the single production benchmark lease is unavailable."""


class BenchmarkLease:
    """Atomic nonblocking host-local lease held for a complete benchmark."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser().resolve()
        self._handle: TextIO | None = None

    def acquire(self) -> None:
        if self._handle is not None:
            raise BenchmarkLeaseError("benchmark lease is already held by this object")
        handle: TextIO | None = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            handle = self.path.open("a+", encoding="utf-8")
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            if handle is not None:
                handle.close()
            raise BenchmarkLeaseError(
                f"production benchmark lease is unavailable: {self.path}"
            ) from error
        assert handle is not None
        self._handle = handle

    def release(self) -> None:
        handle = self._handle
        self._handle = None
        if handle is None:
            return
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()

    def __enter__(self) -> Self:
        self.acquire()
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.release()


def paired_order(repetition: int) -> tuple[str, str]:
    """Alternate AB/BA order to reduce monotonic host-drift bias."""

    if repetition < 0:
        raise ValueError("repetition must be non-negative")
    if repetition % 2 == 0:
        return REFERENCE_BACKEND, CANDIDATE_BACKEND
    return CANDIDATE_BACKEND, REFERENCE_BACKEND


def canonical_digest(parts: Iterable[tuple[str, Any]]) -> str:
    """Hash named evidence values without lossy float/string coercion."""

    hasher = hashlib.sha256()
    for name, value in parts:
        hasher.update(name.encode("utf-8"))
        hasher.update(b"\0")
        if isinstance(value, np.ndarray):
            contiguous = np.ascontiguousarray(value)
            hasher.update(contiguous.dtype.str.encode("ascii"))
            hasher.update(repr(contiguous.shape).encode("ascii"))
            hasher.update(contiguous.tobytes())
        else:
            hasher.update(repr(value).encode("utf-8"))
        hasher.update(b"\0")
    return hasher.hexdigest()


def semantic_rollout_digest(
    fields: Mapping[str, Any], battle_snapshots: Sequence[Any]
) -> str:
    """Hash rollout semantics while excluding backend evidence counters."""

    parts = [
        (name, value) for name, value in fields.items() if name != "simulator_metrics"
    ]
    parts.extend(
        (f"battle[{index}]", snapshot)
        for index, snapshot in enumerate(battle_snapshots)
    )
    return canonical_digest(parts)


def aggregate_backend_metrics(
    metrics: Iterable[Mapping[str, int | float]],
) -> dict[str, int]:
    """Sum required executor counters and reject incomplete evidence."""

    rows = tuple(metrics)
    if not rows:
        raise ValueError("at least one backend metric row is required")
    missing = sorted(
        {name for row in rows for name in REQUIRED_BACKEND_METRICS if name not in row}
    )
    if missing:
        raise ValueError(f"backend metrics missing required counters: {missing}")
    return {
        name: sum(int(row[name]) for row in rows) for name in REQUIRED_BACKEND_METRICS
    }


def candidate_residency_failures(
    metrics: Mapping[str, int | float],
) -> tuple[str, ...]:
    """Return reasons a candidate timing cannot support a speed claim."""

    missing = [name for name in REQUIRED_BACKEND_METRICS if name not in metrics]
    if missing:
        return (f"missing backend metrics: {','.join(missing)}",)

    failures: list[str] = []
    if int(metrics["tensor_ticks"]) <= 0:
        failures.append("candidate executed zero tensor ticks")
    if int(metrics["python_ticks"]) != 0:
        failures.append("candidate executed Python ticks")
    if int(metrics["unsupported_fallbacks"]) != 0:
        failures.append("candidate used unsupported Python fallback")
    if int(metrics["shadow_mismatches"]) != 0:
        failures.append("candidate reported shadow mismatches")
    return tuple(failures)


def validate_paired_rows(
    reference: Mapping[str, Any],
    candidate: Mapping[str, Any],
) -> tuple[str, ...]:
    """Validate exact parity and candidate residency for one workload pair."""

    failures: list[str] = []
    if reference.get("backend") != REFERENCE_BACKEND:
        failures.append("reference row is not the Python backend")
    if candidate.get("backend") != CANDIDATE_BACKEND:
        failures.append("candidate row is not the PyTorch backend")
    if reference.get("sha256") != candidate.get("sha256"):
        failures.append("exact evidence digests differ")
    reference_metrics = reference.get("backend_metrics")
    candidate_metrics = candidate.get("backend_metrics")
    if not isinstance(reference_metrics, Mapping):
        failures.append("reference backend metrics are unavailable")
    if not isinstance(candidate_metrics, Mapping):
        failures.append("candidate backend metrics are unavailable")
    else:
        failures.extend(candidate_residency_failures(candidate_metrics))
    if isinstance(reference_metrics, Mapping) and isinstance(
        candidate_metrics, Mapping
    ):
        if "python_ticks" not in reference_metrics:
            failures.append("reference python tick counter is unavailable")
        elif "tensor_ticks" not in candidate_metrics:
            failures.append("candidate tensor tick counter is unavailable")
        elif int(reference_metrics["python_ticks"]) != int(
            candidate_metrics["tensor_ticks"]
        ):
            failures.append(
                "candidate tensor ticks do not match reference Python ticks"
            )
    return tuple(failures)


def paired_bootstrap_summary(
    rows: Sequence[Mapping[str, Any]],
    *,
    bootstrap_seed: int = 0,
    bootstrap_samples: int = 20_000,
) -> dict[str, Any]:
    """Summarize paired wall times with a deterministic percentile interval."""

    if bootstrap_samples <= 0:
        raise ValueError("bootstrap_samples must be positive")
    repetitions = sorted({int(row["repetition"]) for row in rows})
    if not repetitions:
        raise ValueError("at least one paired repetition is required")

    gains: list[float] = []
    validation_failures: list[str] = []
    for repetition in repetitions:
        pair_rows = [row for row in rows if int(row["repetition"]) == repetition]
        if len(pair_rows) != 2:
            raise ValueError(f"repetition {repetition} must contain exactly two rows")
        by_backend = {str(row["backend"]): row for row in pair_rows}
        if set(by_backend) != {REFERENCE_BACKEND, CANDIDATE_BACKEND}:
            raise ValueError(
                f"repetition {repetition} does not contain exactly one backend pair"
            )
        reference = by_backend[REFERENCE_BACKEND]
        candidate = by_backend[CANDIDATE_BACKEND]
        reference_seconds = float(reference["seconds"])
        candidate_seconds = float(candidate["seconds"])
        if reference_seconds <= 0.0 or candidate_seconds <= 0.0:
            raise ValueError("paired seconds must be positive")
        gains.append(100.0 * (reference_seconds / candidate_seconds - 1.0))
        validation_failures.extend(
            f"repetition {repetition}: {failure}"
            for failure in validate_paired_rows(reference, candidate)
        )

    samples = np.asarray(gains, dtype=np.float64)
    rng = np.random.default_rng(bootstrap_seed)
    bootstrap_means = np.mean(
        rng.choice(
            samples,
            size=(bootstrap_samples, samples.size),
            replace=True,
        ),
        axis=1,
    )
    interval = [
        float(np.quantile(bootstrap_means, 0.025)),
        float(np.quantile(bootstrap_means, 0.975)),
    ]
    valid = not validation_failures
    return {
        "paired_speedup_percent": gains,
        "mean_speedup_percent": float(samples.mean()),
        "median_speedup_percent": float(np.median(samples)),
        "positive_pairs": int(np.count_nonzero(samples > 0.0)),
        "pairs": int(samples.size),
        "mean_speedup_95_percentile_bootstrap_ci": interval,
        "validation_failures": validation_failures,
        "valid_for_speed_claim": valid,
        # A 2x throughput claim means reference/candidate >= 2, or >=100%
        # speedup. Require the lower confidence bound, not the point estimate.
        "meets_2x_with_95_percent_confidence": valid and interval[0] >= 100.0,
    }


def oracle_backend_capability(planner_type: type[Any]) -> CapabilityCheck:
    """Require explicit backend ingress before any oracle candidate timing."""

    try:
        parameters = inspect.signature(planner_type).parameters
    except (TypeError, ValueError) as error:
        return CapabilityCheck(False, f"cannot inspect oracle constructor: {error}")
    if "simulation_backend" not in parameters:
        return CapabilityCheck(
            False,
            "oracle planner has no simulation_backend ingress; refusing "
            "Python-vs-Python timing",
        )
    if not callable(getattr(planner_type, "simulator_backend_metrics", None)):
        return CapabilityCheck(
            False,
            "oracle planner does not expose simulator_backend_metrics; "
            "refusing uncounted candidate timing",
        )
    return CapabilityCheck(True)


def _process_rows() -> tuple[tuple[int, int, str], ...]:
    try:
        completed = subprocess.run(
            ["ps", "-axo", "pid=,ppid=,command="],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise RuntimeError(
            "benchmark resource guard could not inspect processes"
        ) from error
    rows: list[tuple[int, int, str]] = []
    for line in completed.stdout.splitlines():
        fields = line.strip().split(maxsplit=2)
        if len(fields) != 3:
            continue
        try:
            rows.append((int(fields[0]), int(fields[1]), fields[2]))
        except ValueError:
            continue
    if not rows:
        raise RuntimeError("benchmark resource guard received an empty process table")
    return tuple(rows)


def _owned_process_family(
    rows: Sequence[tuple[int, int, str]], current_pid: int
) -> set[int]:
    parent_by_pid = {pid: ppid for pid, ppid, _command in rows}
    ancestors = {current_pid}
    cursor = current_pid
    while cursor in parent_by_pid:
        parent = parent_by_pid[cursor]
        if parent <= 1 or parent in ancestors:
            break
        ancestors.add(parent)
        cursor = parent
    # Include descendants of the benchmark itself (such as its actor pool),
    # but not siblings that merely share a Codex/app-server ancestor.
    descendants = {current_pid}
    changed = True
    while changed:
        changed = False
        for pid, ppid, _command in rows:
            if ppid in descendants and pid not in descendants:
                descendants.add(pid)
                changed = True
    return ancestors | descendants


def competing_benchmark_processes(
    rows: Sequence[tuple[int, int, str]] | None = None,
    *,
    current_pid: int | None = None,
) -> tuple[CompetingProcess, ...]:
    """Find live Clasher/Rust/RoadForge compute without recording full argv."""

    snapshot = tuple(rows) if rows is not None else _process_rows()
    owned = _owned_process_family(snapshot, current_pid or os.getpid())
    blockers: list[CompetingProcess] = []
    for pid, _ppid, command in snapshot:
        if pid in owned:
            continue
        try:
            arguments = tuple(shlex.split(command))
        except ValueError:
            # An unparseable potentially relevant command is unsafe to ignore.
            if "clasher" in command.casefold() or "roadforgessd" in command.casefold():
                blockers.append(CompetingProcess(pid, "unparseable", "unknown"))
            continue
        if not arguments:
            continue
        executable = Path(arguments[0]).name
        executable_path = arguments[0].casefold()
        lowered = tuple(argument.casefold() for argument in arguments)
        joined = " ".join(lowered)
        is_clasher_command = "clasher" in joined
        category: str | None = None
        if (
            executable.startswith("python")
            and is_clasher_command
            and any(
                marker in joined
                for marker in (
                    "clasher.rl.train_",
                    "run_clasher.py train",
                    "run_clasher.py benchmark",
                    "clasher.cli benchmark",
                    "clasher.rl.benchmark",
                    "/scripts/perf/",
                    "benchmark_",
                )
            )
        ):
            category = "clasher-compute"
        if executable in {"pytest", "mypy", "pyright", "ruff"} and (
            is_clasher_command or "clasher" in executable_path
        ):
            category = "clasher-validation"
        if (
            executable.startswith("python")
            and is_clasher_command
            and any(
                marker in lowered for marker in ("pytest", "mypy", "pyright", "ruff")
            )
        ):
            category = "clasher-validation"
        # Cargo and rustc do not publish cwd in `ps`, so a generic compiler
        # process cannot be safely proven unrelated. Be conservative.
        if executable in {"cargo", "rustc", "nextest"}:
            category = "clasher-rust"
        if "rust-clasher" in executable or "rust_clasher" in executable:
            category = "clasher-rust"
        if "roadforgessd" in joined and executable.startswith(
            ("python", "cargo", "rustc")
        ):
            category = "roadforge-compute"
        if category is not None:
            blockers.append(CompetingProcess(pid, category, executable))
    return tuple(sorted(blockers, key=lambda blocker: blocker.pid))


def sanitized_process_evidence(
    blockers: Sequence[CompetingProcess],
) -> list[dict[str, str | int]]:
    """Serialize blocker evidence without leaking command arguments."""

    return [
        {
            "pid": blocker.pid,
            "category": blocker.category,
            "executable": blocker.executable,
        }
        for blocker in blockers
    ]


def write_json_report(path: str | Path, payload: Mapping[str, Any]) -> Path:
    """Write a stable JSON evidence artifact."""

    output = Path(path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output
