from __future__ import annotations

import pytest

from clasher.rl import resource_guard as resource_guard_module
from clasher.rl.resource_guard import (
    ProcessRecord,
    ResourceGuardError,
    guard_training_resources,
    inspect_competing_claims,
)

DESKTOP_COMMAND = (
    "/Users/sam/Desktop/code/clasher/.venv/bin/python3 "
    "-m clasher.rl.train_recurrent --num-envs 14 --actor-workers 7 "
    "--actor-threads 1 --device mps --actor-device cpu"
)


def test_process_inspection_counts_real_production_shape_once() -> None:
    processes = (
        ProcessRecord(100, 1, f"uv run python {DESKTOP_COMMAND.split('python3 ', 1)[1]}"),
        ProcessRecord(101, 100, DESKTOP_COMMAND),
        ProcessRecord(
            102,
            101,
            "/usr/bin/python3 -c from multiprocessing.spawn import spawn_main",
        ),
    )

    claims = inspect_competing_claims(
        processes, current_pid=900, auto_uses_mps=True
    )

    assert len(claims) == 1
    assert claims[0].pid == 101
    assert claims[0].actor_workers == 7
    assert claims[0].actor_threads == 1
    assert claims[0].actor_cpu_slots == 7
    assert claims[0].mps is True


def test_process_inspection_excludes_current_process_family() -> None:
    processes = (
        ProcessRecord(200, 1, "uv run python -m clasher.rl.train_recurrent"),
        ProcessRecord(201, 200, DESKTOP_COMMAND),
        ProcessRecord(202, 201, "/usr/bin/python3 -m owned.actor"),
    )

    claims = inspect_competing_claims(
        processes, current_pid=201, auto_uses_mps=True
    )

    assert claims == ()


def test_process_inspection_does_not_exclude_clasher_sibling_of_ancestor() -> None:
    processes = (
        ProcessRecord(200, 1, "/Applications/Codex app-server"),
        ProcessRecord(201, 200, "/bin/zsh owned-command"),
        ProcessRecord(202, 201, "/usr/bin/python3 -c owned-probe"),
        ProcessRecord(203, 200, DESKTOP_COMMAND),
    )

    claims = inspect_competing_claims(
        processes, current_pid=202, auto_uses_mps=True
    )

    assert [claim.pid for claim in claims] == [203]


def test_process_inspection_parses_unified_recurrent_launcher() -> None:
    command = (
        "/usr/bin/python3 run_clasher.py train -- --actor-workers 12 "
        "--actor-threads 1 --device cpu --actor-device cpu"
    )

    claims = inspect_competing_claims(
        (ProcessRecord(250, 1, command),),
        current_pid=900,
        auto_uses_mps=True,
    )

    assert len(claims) == 1
    assert claims[0].actor_cpu_slots == 12
    assert claims[0].mps is False


def test_process_inspection_counts_dagger_workers() -> None:
    command = (
        "/usr/bin/python3 -m clasher.rl.train_dagger_oracle "
        "--num-workers=6 --device cpu"
    )

    claims = inspect_competing_claims(
        (ProcessRecord(260, 1, command),),
        current_pid=900,
        auto_uses_mps=True,
    )

    assert len(claims) == 1
    assert claims[0].actor_workers == 6
    assert claims[0].actor_threads == 1
    assert claims[0].actor_cpu_slots == 6


def test_omitted_recurrent_device_claims_default_auto_mps() -> None:
    command = (
        "/usr/bin/python3 run_clasher.py train -- "
        "--actor-workers 2 --actor-threads 1"
    )

    claims = inspect_competing_claims(
        (ProcessRecord(270, 1, command),),
        current_pid=900,
        auto_uses_mps=True,
    )

    assert len(claims) == 1
    assert claims[0].mps is True


def test_auto_actor_device_does_not_claim_mps_for_cpu_learner() -> None:
    command = (
        "/usr/bin/python3 run_clasher.py train -- "
        "--device cpu --actor-device auto"
    )

    claims = inspect_competing_claims(
        (ProcessRecord(275, 1, command),),
        current_pid=900,
        auto_uses_mps=True,
    )

    assert len(claims) == 1
    assert claims[0].mps is False


@pytest.mark.parametrize("command", ["train-dagger", "train-legacy", "train-async"])
def test_omitted_unified_training_device_claims_default_auto_mps(
    command: str,
) -> None:
    process_command = f"/usr/bin/python3 run_clasher.py {command} --"

    claims = inspect_competing_claims(
        (ProcessRecord(280, 1, process_command),),
        current_pid=900,
        auto_uses_mps=True,
    )

    assert len(claims) == 1
    assert claims[0].mps is True


def test_non_training_clasher_python_process_reserves_one_cpu_slot() -> None:
    command = (
        "/repo/clasher/.venv/bin/python3 scripts/perf/benchmark_rollout.py"
    )

    claims = inspect_competing_claims(
        (ProcessRecord(290, 1, command),),
        current_pid=900,
        auto_uses_mps=True,
    )

    assert len(claims) == 1
    assert claims[0].actor_cpu_slots == 1
    assert claims[0].mps is False


def test_guard_rejects_competing_mps_learner() -> None:
    with pytest.raises(ResourceGuardError, match=r"MPS.*pid=301"):
        guard_training_resources(
            learner_device="mps",
            actor_device="cpu",
            actor_workers=4,
            actor_threads=1,
            logical_cpus=12,
            processes=(ProcessRecord(301, 1, DESKTOP_COMMAND),),
            current_pid=900,
        )


def test_guard_rejects_cpu_actor_oversubscription() -> None:
    with pytest.raises(
        ResourceGuardError,
        match=(
            r"requested=6 available=4 logical=12 reserved=1 "
            r"competing=7 competing_pids=401"
        ),
    ):
        guard_training_resources(
            learner_device="cpu",
            actor_device="cpu",
            actor_workers=6,
            actor_threads=1,
            reserve_cpus=1,
            logical_cpus=12,
            processes=(ProcessRecord(401, 1, DESKTOP_COMMAND),),
            current_pid=900,
        )


def test_guard_admits_cpu_actors_within_remaining_budget() -> None:
    allocation = guard_training_resources(
        learner_device="cpu",
        actor_device="cpu",
        actor_workers=4,
        actor_threads=1,
        reserve_cpus=1,
        logical_cpus=12,
        processes=(ProcessRecord(501, 1, DESKTOP_COMMAND),),
        current_pid=900,
    )

    assert allocation.requested_actor_cpu_slots == 4
    assert allocation.competing_actor_cpu_slots == 7
    assert allocation.available_actor_cpu_slots == 4
    assert "resource_guard=on" in allocation.summary()


def test_guard_requires_cpu_partition_for_parallel_actors() -> None:
    with pytest.raises(ResourceGuardError, match="parallel rollout workers"):
        guard_training_resources(
            learner_device="mps",
            actor_device="mps",
            actor_workers=2,
            actor_threads=1,
            logical_cpus=12,
            processes=(),
        )


def test_disabled_guard_skips_process_inspection() -> None:
    allocation = guard_training_resources(
        learner_device="cpu",
        actor_device="cpu",
        actor_workers=12,
        actor_threads=1,
        enabled=False,
        logical_cpus=12,
    )

    assert allocation.guard_enabled is False
    assert allocation.requested_actor_cpu_slots == 12
    assert allocation.available_actor_cpu_slots == 12


def test_disabled_guard_still_enforces_device_partition() -> None:
    with pytest.raises(ResourceGuardError, match="parallel rollout workers"):
        guard_training_resources(
            learner_device="mps",
            actor_device="mps",
            actor_workers=2,
            actor_threads=1,
            enabled=False,
            logical_cpus=12,
        )


def test_process_inspection_failure_is_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable(*_args: object, **_kwargs: object) -> None:
        raise OSError("ps unavailable")

    monkeypatch.setattr(resource_guard_module.subprocess, "run", unavailable)

    with pytest.raises(ResourceGuardError, match="could not inspect"):
        guard_training_resources(
            learner_device="cpu",
            actor_device="cpu",
            actor_workers=1,
            actor_threads=1,
            logical_cpus=12,
        )
