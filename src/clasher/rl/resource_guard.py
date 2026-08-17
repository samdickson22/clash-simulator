"""Fail-closed resource admission for simulator training processes.

The recurrent trainer uses CPU actor processes and may use the single Apple
MPS device for PPO updates.  Starting a second production-shaped command can
otherwise silently oversubscribe the actors or contend for MPS.  This module
inspects already-running Clasher Python commands before any workers are
created; it never signals or otherwise mutates those processes.
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProcessRecord:
    pid: int
    ppid: int
    command: str


@dataclass(frozen=True)
class ResourceClaim:
    pid: int
    command: str
    actor_workers: int
    actor_threads: int
    actor_cpu_slots: int
    mps: bool


@dataclass(frozen=True)
class ResourceAllocation:
    guard_enabled: bool
    logical_cpus: int
    reserved_cpus: int
    requested_actor_cpu_slots: int
    competing_actor_cpu_slots: int
    available_actor_cpu_slots: int
    competing_claims: tuple[ResourceClaim, ...]

    def summary(self) -> str:
        status = "on" if self.guard_enabled else "off"
        return (
            f"resource_guard={status} logical_cpus={self.logical_cpus} "
            f"reserved_cpus={self.reserved_cpus} "
            f"actor_cpu_slots={self.requested_actor_cpu_slots} "
            f"competing_actor_cpu_slots={self.competing_actor_cpu_slots} "
            f"available_actor_cpu_slots={self.available_actor_cpu_slots}"
        )


class ResourceGuardError(RuntimeError):
    """Raised before training when resource ownership is not safe."""


_PROCESS_LINE = re.compile(r"^\s*(\d+)\s+(\d+)\s+(.*)$")
_MPS_OPTIONS = (
    "--device",
    "--learner-device",
    "--actor-device",
    "--simulation-device",
)


def _read_processes() -> tuple[ProcessRecord, ...]:
    try:
        completed = subprocess.run(
            ["ps", "-axo", "pid=,ppid=,command="],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise ResourceGuardError(
            "resource guard could not inspect running processes"
        ) from error

    records: list[ProcessRecord] = []
    for line in completed.stdout.splitlines():
        match = _PROCESS_LINE.match(line)
        if match is None:
            continue
        records.append(
            ProcessRecord(
                pid=int(match.group(1)),
                ppid=int(match.group(2)),
                command=match.group(3),
            )
        )
    if not records:
        raise ResourceGuardError("resource guard process inspection returned no rows")
    return tuple(records)


def _argument_value(
    arguments: Sequence[str], option: str, default: str | None = None
) -> str | None:
    prefix = f"{option}="
    for index, argument in enumerate(arguments):
        if argument.startswith(prefix):
            return argument[len(prefix) :]
        if argument == option and index + 1 < len(arguments):
            return arguments[index + 1]
    return default


def _positive_int_argument(
    arguments: Sequence[str], option: str, default: int
) -> int:
    raw_value = _argument_value(arguments, option, str(default))
    try:
        value = int(raw_value) if raw_value is not None else default
    except ValueError as error:
        raise ResourceGuardError(
            f"running Clasher process has invalid {option}={raw_value!r}"
        ) from error
    if value <= 0:
        raise ResourceGuardError(
            f"running Clasher process has non-positive {option}={value}"
        )
    return value


def _python_arguments(command: str) -> tuple[str, ...] | None:
    try:
        arguments = tuple(shlex.split(command))
    except ValueError as error:
        raise ResourceGuardError(
            f"could not parse running process command: {command!r}"
        ) from error
    if not arguments:
        return None
    # Ignore wrappers such as `uv run python ...`. The actual Python child is
    # present in the same process snapshot, and counting both would double the
    # live resource claim.
    if not Path(arguments[0]).name.startswith("python"):
        return None
    return arguments


def _uses_mps(arguments: Sequence[str], *, auto_uses_mps: bool) -> bool:
    for option in _MPS_OPTIONS:
        value = _argument_value(arguments, option)
        if value == "mps" or (
            option != "--actor-device"
            and value == "auto"
            and auto_uses_mps
        ):
            return True
    return False


def _training_kind(arguments: Sequence[str]) -> str | None:
    direct_modules = {
        "clasher.rl.train_recurrent": "recurrent",
        "clasher.rl.train_dagger_oracle": "dagger",
        "clasher.rl.train_selfplay": "legacy",
        "clasher.rl.train_selfplay_async": "async",
    }
    for module, kind in direct_modules.items():
        if module in arguments:
            return kind

    cli_commands = {
        "train": "recurrent",
        "train-dagger": "dagger",
        "train-legacy": "legacy",
        "train-async": "async",
    }
    for index, argument in enumerate(arguments[:-1]):
        if Path(argument).name == "run_clasher.py" or argument == "clasher.cli":
            return cli_commands.get(arguments[index + 1])
    return None


def _resource_claim(
    process: ProcessRecord, *, auto_uses_mps: bool
) -> ResourceClaim | None:
    arguments = _python_arguments(process.command)
    if arguments is None or not any("clasher" in argument for argument in arguments):
        return None

    training_kind = _training_kind(arguments)
    if training_kind == "recurrent":
        actor_workers = _positive_int_argument(arguments, "--actor-workers", 1)
        actor_threads = _positive_int_argument(arguments, "--actor-threads", 2)
    elif training_kind in {"dagger", "legacy"}:
        actor_workers = _positive_int_argument(arguments, "--num-workers", 1)
        actor_threads = 1
    elif training_kind == "async":
        if "--actors-auto" in arguments:
            raise ResourceGuardError(
                "running async Clasher process uses --actors-auto; "
                "resource guard cannot infer its live CPU claim"
            )
        actor_workers = _positive_int_argument(arguments, "--num-actors", 8)
        actor_threads = 1
    else:
        # A Clasher Python benchmark, audit, evaluation, or test process still
        # occupies at least one CPU execution slot even without actor flags.
        actor_workers = 1
        actor_threads = 1

    mps = _uses_mps(arguments, auto_uses_mps=auto_uses_mps)
    if (
        training_kind is not None
        and _argument_value(arguments, "--device") is None
        and auto_uses_mps
    ):
        # Training entry points declare `auto` as their default learner device.
        # Treat an omitted flag as an accelerator claim conservatively.
        mps = True
    return ResourceClaim(
        pid=process.pid,
        command=process.command,
        actor_workers=actor_workers,
        actor_threads=actor_threads,
        actor_cpu_slots=actor_workers * actor_threads,
        mps=mps,
    )


def _process_family_pids(
    processes: Sequence[ProcessRecord], current_pid: int
) -> set[int]:
    parent_by_pid = {process.pid: process.ppid for process in processes}
    ancestors = {current_pid}
    pid = current_pid
    while pid in parent_by_pid:
        parent = parent_by_pid[pid]
        if parent <= 1 or parent in ancestors:
            break
        ancestors.add(parent)
        pid = parent

    # Include descendants of this process (such as its actor pool), but not
    # siblings that merely share a uv/Codex/app-server ancestor.
    descendants = {current_pid}
    changed = True
    while changed:
        changed = False
        for process in processes:
            if process.ppid in descendants and process.pid not in descendants:
                descendants.add(process.pid)
                changed = True
    return ancestors | descendants


def inspect_competing_claims(
    processes: Iterable[ProcessRecord] | None = None,
    *,
    current_pid: int | None = None,
    auto_uses_mps: bool,
) -> tuple[ResourceClaim, ...]:
    snapshot = tuple(processes) if processes is not None else _read_processes()
    own_family = _process_family_pids(snapshot, current_pid or os.getpid())
    claims: list[ResourceClaim] = []
    for process in snapshot:
        if process.pid in own_family:
            continue
        claim = _resource_claim(process, auto_uses_mps=auto_uses_mps)
        if claim is not None and (claim.actor_cpu_slots or claim.mps):
            claims.append(claim)
    return tuple(sorted(claims, key=lambda claim: claim.pid))


def guard_training_resources(
    *,
    learner_device: str,
    actor_device: str,
    actor_workers: int,
    actor_threads: int,
    enabled: bool = True,
    reserve_cpus: int = 0,
    logical_cpus: int | None = None,
    processes: Iterable[ProcessRecord] | None = None,
    current_pid: int | None = None,
    auto_uses_mps: bool = True,
) -> ResourceAllocation:
    """Validate device partitioning and admit a CPU/MPS training allocation."""

    if actor_workers <= 0 or actor_threads <= 0:
        raise ValueError("actor_workers and actor_threads must be positive")
    if reserve_cpus < 0:
        raise ValueError("reserve_cpus must be non-negative")
    cpu_count = logical_cpus if logical_cpus is not None else os.cpu_count()
    if cpu_count is None or cpu_count <= 0:
        raise ResourceGuardError("resource guard could not determine logical CPU count")

    requested_actor_slots = (
        actor_workers * actor_threads if actor_device == "cpu" else 0
    )
    if actor_workers > 1 and actor_device != "cpu":
        raise ResourceGuardError(
            "parallel rollout workers must use CPU; select --actor-device cpu"
        )
    if learner_device == "mps" and actor_device != "cpu":
        raise ResourceGuardError(
            "MPS is reserved for learner batches; select --actor-device cpu"
        )

    if not enabled:
        available = max(0, cpu_count - reserve_cpus)
        return ResourceAllocation(
            guard_enabled=False,
            logical_cpus=cpu_count,
            reserved_cpus=reserve_cpus,
            requested_actor_cpu_slots=requested_actor_slots,
            competing_actor_cpu_slots=0,
            available_actor_cpu_slots=available,
            competing_claims=(),
        )

    claims = inspect_competing_claims(
        processes,
        current_pid=current_pid,
        auto_uses_mps=auto_uses_mps,
    )
    competing_actor_slots = sum(claim.actor_cpu_slots for claim in claims)
    available_actor_slots = max(
        0, cpu_count - reserve_cpus - competing_actor_slots
    )

    if learner_device == "mps":
        mps_claims = tuple(claim for claim in claims if claim.mps)
        if mps_claims:
            pids = ",".join(str(claim.pid) for claim in mps_claims)
            raise ResourceGuardError(
                "MPS is already claimed by a competing Clasher process "
                f"(pid={pids}); refusing accelerator contention"
            )
    if requested_actor_slots > available_actor_slots:
        competing_pids = ",".join(
            str(claim.pid) for claim in claims if claim.actor_cpu_slots
        ) or "none"
        raise ResourceGuardError(
            "CPU actor allocation exceeds the fail-closed budget: "
            f"requested={requested_actor_slots} "
            f"available={available_actor_slots} logical={cpu_count} "
            f"reserved={reserve_cpus} competing={competing_actor_slots} "
            f"competing_pids={competing_pids}"
        )

    return ResourceAllocation(
        guard_enabled=True,
        logical_cpus=cpu_count,
        reserved_cpus=reserve_cpus,
        requested_actor_cpu_slots=requested_actor_slots,
        competing_actor_cpu_slots=competing_actor_slots,
        available_actor_cpu_slots=available_actor_slots,
        competing_claims=claims,
    )
