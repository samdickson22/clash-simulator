"""Operational partitions of a full immutable readiness execution plan."""

from __future__ import annotations

from typing import Literal

from .readiness_execution import ExecutionPlan, Job, jobs
from .training_readiness_v2 import Record

BranchKey = tuple[str, str, str, str]


class JobSelection(Record):
    full_job_count: int
    selected_indices: tuple[int, ...]
    engine_filter: Literal["both", "scalar", "reference"]
    shard_index: int
    shard_count: int
    explicit_indices: tuple[int, ...]
    unclaimed_only: bool
    skipped_claimed_indices: tuple[int, ...]


def branch_key(job: Job) -> BranchKey:
    return job.family_id, job.condition, job.candidate_role, job.engine


def select_job_indices(
    plan: ExecutionPlan,
    *,
    engine: Literal["both", "scalar", "reference"] = "both",
    shard_index: int = 0,
    shard_count: int = 1,
    explicit_indices: tuple[int, ...] = (),
    claimed_keys: frozenset[BranchKey] | None = None,
) -> JobSelection:
    declared = jobs(plan)
    if (
        engine not in ("both", "scalar", "reference")
        or type(shard_count) is not int
        or type(shard_index) is not int
        or shard_count < 1
        or not 0 <= shard_index < shard_count
    ):
        raise ValueError("invalid engine filter or shard coordinates")
    if len(set(explicit_indices)) != len(explicit_indices) or any(
        type(i) is not int or not 0 <= i < len(declared) for i in explicit_indices
    ):
        raise ValueError("explicit job indices must be unique declared indices")
    if explicit_indices and (shard_index != 0 or shard_count != 1):
        raise ValueError("use explicit indices or sharding, not both")
    if claimed_keys is not None and plan.purpose not in (
        "fresh_acceptance",
        "tier_b_transfer",
    ):
        raise ValueError(
            "unclaimed selection requires the prospective ownership ledger"
        )
    eligible = tuple(
        i for i, job in enumerate(declared) if engine == "both" or job.engine == engine
    )
    if explicit_indices:
        if not set(explicit_indices) <= set(eligible):
            raise ValueError("explicit job indices disagree with engine filter")
        selected = tuple(sorted(explicit_indices))
    else:
        # Shard the filtered order, retaining original full-plan indices. This
        # avoids empty shards caused by the interleaved scalar/reference design.
        selected = tuple(
            index
            for ordinal, index in enumerate(eligible)
            if ordinal % shard_count == shard_index
        )
    skipped = tuple(
        i
        for i in selected
        if claimed_keys is not None and branch_key(declared[i]) in claimed_keys
    )
    selected = tuple(i for i in selected if i not in skipped)
    return JobSelection(
        full_job_count=len(declared),
        selected_indices=selected,
        engine_filter=engine,
        shard_index=shard_index,
        shard_count=shard_count,
        explicit_indices=explicit_indices,
        unclaimed_only=claimed_keys is not None,
        skipped_claimed_indices=skipped,
    )
