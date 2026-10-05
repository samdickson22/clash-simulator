"""Local pilot concurrency and conservative task-only compute accounting."""

from __future__ import annotations

import fcntl
import os
import signal
import subprocess
import time
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class BudgetJob(BaseModel):
    model_config = ConfigDict(
        extra="forbid", strict=True, frozen=True, allow_inf_nan=False
    )
    argv: list[str]
    started_at: float = Field(ge=0)
    cpu_cores: int = Field(gt=0)
    accelerator: bool
    pid: int | None = Field(default=None, gt=0)


class CompletedBudgetJob(BudgetJob):
    elapsed_seconds: float = Field(ge=0)
    status: Literal["completed", "failed", "compute-ceiling", "interrupted-unobserved"]


class BudgetRecord(BaseModel):
    model_config = ConfigDict(
        extra="forbid", strict=True, frozen=True, allow_inf_nan=False
    )
    schema_version: Literal["clasher.local-pilot-budget.v1"] = Field(alias="schema")
    config_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    cpu_core_hour_ceiling: float = Field(gt=0)
    accelerator_hour_ceiling: float = Field(gt=0)
    cpu_core_hours_used: float = Field(ge=0)
    accelerator_hours_used: float = Field(ge=0)
    active: BudgetJob | None
    jobs: list[CompletedBudgetJob]


class BudgetSnapshot(BaseModel):
    model_config = ConfigDict(
        extra="forbid", strict=True, frozen=True, allow_inf_nan=False
    )
    cpu_core_hours_used: float = Field(ge=0)
    accelerator_hours_used: float = Field(ge=0)
    cpu_core_hours_remaining: float = Field(ge=0)
    accelerator_hours_remaining: float = Field(ge=0)
    active_job: BudgetJob | None
    ledger_path: str
    accounting: Literal[
        "allocated task cores times elapsed wall time; no unrelated host jobs"
    ]


class PilotBudgetExceeded(RuntimeError):
    pass


def budget_snapshot(path: Path) -> dict:
    record = BudgetRecord.model_validate_json(path.read_text()).model_dump(
        by_alias=True
    )
    active = record.get("active")
    cpu = record["cpu_core_hours_used"]
    accelerator = record["accelerator_hours_used"]
    if active is not None:
        hours = max(0.0, time.time() - active["started_at"]) / 3600
        cpu += hours * active["cpu_cores"]
        accelerator += hours * int(active["accelerator"])
    return {
        "cpu_core_hours_used": cpu,
        "accelerator_hours_used": accelerator,
        "cpu_core_hours_remaining": max(0.0, record["cpu_core_hour_ceiling"] - cpu),
        "accelerator_hours_remaining": max(
            0.0, record["accelerator_hour_ceiling"] - accelerator
        ),
        "active_job": active,
        "ledger_path": str(path.resolve()),
        "accounting": "allocated task cores times elapsed wall time; no unrelated host jobs",
    }


class LocalPilotBudget(AbstractContextManager):
    def __init__(
        self,
        directory: Path,
        *,
        config_sha256: str,
        cpu_core_hour_ceiling: float = 4608.0,
        accelerator_hour_ceiling: float = 72.0,
    ):
        self.directory = directory
        self.path = directory / "resource-budget.json"
        self.config_sha256 = config_sha256
        self.cpu_limit = cpu_core_hour_ceiling
        self.accelerator_limit = accelerator_hour_ceiling
        self.lock = None
        self.record = None

    def _save(self):
        temporary = self.path.with_suffix(".tmp")
        validated = BudgetRecord.model_validate(self.record)
        temporary.write_text(validated.model_dump_json(by_alias=True, indent=2) + "\n")
        os.replace(temporary, self.path)

    def __enter__(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        self.lock = (self.directory / ".pilot.lock").open("a+")
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            self.lock.close()
            raise RuntimeError("another coordinator owns this pilot run") from error
        try:
            if self.path.exists():
                self.record = BudgetRecord.model_validate_json(
                    self.path.read_text()
                ).model_dump(by_alias=True)
                if self.record["config_sha256"] != self.config_sha256:
                    raise ValueError(
                        "pilot budget belongs to a different frozen config"
                    )
                active = self.record.get("active")
                if active is not None:
                    pid = active.get("pid")
                    if pid is not None:
                        try:
                            os.kill(pid, 0)
                        except ProcessLookupError:
                            pass
                        else:
                            raise RuntimeError(
                                "the previous pilot child is still running; reconcile its owned process before resuming"
                            )
                    self._finish(
                        max(0.0, time.time() - active["started_at"]),
                        "interrupted-unobserved",
                    )
            else:
                self.record = {
                    "schema": "clasher.local-pilot-budget.v1",
                    "config_sha256": self.config_sha256,
                    "cpu_core_hour_ceiling": self.cpu_limit,
                    "accelerator_hour_ceiling": self.accelerator_limit,
                    "cpu_core_hours_used": 0.0,
                    "accelerator_hours_used": 0.0,
                    "active": None,
                    "jobs": [],
                }
                self._save()
            if (
                self.record["cpu_core_hour_ceiling"] != self.cpu_limit
                or self.record["accelerator_hour_ceiling"] != self.accelerator_limit
            ):
                raise ValueError("pilot budget ceilings changed")
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def _finish(self, seconds: float, status: str):
        active = self.record["active"]
        self.record["cpu_core_hours_used"] += seconds * active["cpu_cores"] / 3600
        self.record["accelerator_hours_used"] += (
            seconds * int(active["accelerator"]) / 3600
        )
        self.record["jobs"].append(
            active | {"elapsed_seconds": seconds, "status": status}
        )
        self.record["active"] = None
        self._save()

    def run(self, argv, *, cwd, env, log, cpu_cores: int, accelerator: bool = False):
        if self.record is None or self.record["active"] is not None or cpu_cores < 1:
            raise ValueError("invalid pilot budget state or allocation")
        remaining_cpu = self.cpu_limit - self.record["cpu_core_hours_used"]
        remaining_accelerator = (
            self.accelerator_limit - self.record["accelerator_hours_used"]
        )
        timeout = remaining_cpu * 3600 / cpu_cores
        if accelerator:
            timeout = min(timeout, remaining_accelerator * 3600)
        if timeout <= 0:
            raise PilotBudgetExceeded(
                "pilot compute ceiling reached; report achieved experience and profiling before expansion"
            )
        self.record["active"] = {
            "argv": list(argv),
            "started_at": time.time(),
            "cpu_cores": cpu_cores,
            "accelerator": accelerator,
            "pid": None,
        }
        self._save()
        begin = time.monotonic()
        process = None
        status = "failed"
        try:
            process = subprocess.Popen(
                argv,
                cwd=cwd,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            self.record["active"]["pid"] = process.pid
            self._save()
            code = process.wait(timeout=timeout)
            if code:
                raise subprocess.CalledProcessError(code, argv)
            status = "completed"
        except subprocess.TimeoutExpired as error:
            status = "compute-ceiling"
            raise PilotBudgetExceeded(
                "pilot compute ceiling reached; partial checkpoints and usage are retained"
            ) from error
        finally:
            if process is not None and process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=10)
            self._finish(time.monotonic() - begin, status)

    def __exit__(self, exc_type, exc_value, traceback):
        if self.lock is not None and not self.lock.closed:
            fcntl.flock(self.lock, fcntl.LOCK_UN)
            self.lock.close()
        return False


def require_owned_budget(path: Path) -> dict:
    snapshot = budget_snapshot(path)
    active = snapshot["active_job"]
    if active is None or active.get("pid") != os.getpid():
        raise ValueError(
            "gameplay fitting must run as the recorded child of the pilot budget coordinator"
        )
    if snapshot["cpu_core_hours_remaining"] <= 0 or (
        active["accelerator"] and snapshot["accelerator_hours_remaining"] <= 0
    ):
        raise PilotBudgetExceeded("pilot compute ceiling is exhausted")
    return snapshot
