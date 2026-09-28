"""Real child processes prove durable terminal receipts and no silent reruns."""

import importlib
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from clasher.rl.calibration_jobs import (
    JobSpec,
    atomic_json,
    job_status,
    process_identity,
)


@pytest.fixture
def supervisor(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    return importlib.import_module("run_prospective_calibration")


def spec(command):
    return JobSpec(
        command=tuple(command),
        cwd=str(Path(__file__).resolve().parents[1]),
        native=False,
        protocol_sha256="a" * 64,
    )


def test_completed_job_is_not_executed_twice(supervisor, tmp_path):
    marker = tmp_path / "count"
    job = spec(
        [
            sys.executable,
            "-c",
            f"from pathlib import Path; p=Path({str(marker)!r}); p.write_text(p.read_text()+'x' if p.exists() else 'x')",
        ]
    )
    directory = tmp_path / "job"
    assert supervisor.run_job(directory, job, tmp_path / "native.lock") == 0
    assert supervisor.run_job(directory, job, tmp_path / "native.lock") == 0
    assert marker.read_text() == "x"
    assert job_status(directory, job) == ("complete", 0)


def test_nonzero_terminal_exit_is_preserved(supervisor, tmp_path):
    job = spec([sys.executable, "-c", "raise SystemExit(7)"])
    assert supervisor.run_job(tmp_path / "job", job, tmp_path / "native.lock") == 7
    assert supervisor.run_job(tmp_path / "job", job, tmp_path / "native.lock") == 7


def test_pid_file_requires_current_matching_process_identity(tmp_path):
    job = spec([sys.executable, "-c", "pass"])
    atomic_json(tmp_path / "request.json", job.model_dump(mode="json"))
    atomic_json(
        tmp_path / "running.json",
        {"pid": os.getpid(), "identity": "stale pid identity"},
    )
    assert job_status(tmp_path, job) == ("unresolved", None)
    atomic_json(
        tmp_path / "running.json",
        {"pid": os.getpid(), "identity": process_identity(os.getpid())},
    )
    assert job_status(tmp_path, job) == ("running", None)


def test_changed_command_cannot_reuse_completion(supervisor, tmp_path):
    job = spec([sys.executable, "-c", "pass"])
    directory = tmp_path / "job"
    assert supervisor.run_job(directory, job, tmp_path / "native.lock") == 0
    changed = spec([sys.executable, "-c", "raise SystemExit(1)"])
    with pytest.raises(ValueError, match="request changed"):
        supervisor.run_job(directory, changed, tmp_path / "native.lock")


@pytest.mark.parametrize("failed_stage", ["capture", "prepare", "native", "scalar", "evaluation", None])
def test_campaign_stops_at_failed_collection_job(supervisor, tmp_path, monkeypatch, failed_stage):
    monkeypatch.chdir(tmp_path)
    digest = "a" * 64
    configurations = ["b" * 64, "c" * 64]
    frozen = SimpleNamespace(
        source_files={}, ruleset_sha256=digest, catalog_sha256=digest,
        family_manifest_path="families.json", families={"family": configurations},
        public_opponent_seat=1, public_opponent_style="pressure",
    )
    (tmp_path / "protocol.json").write_text("{}")
    atomic_json(tmp_path / "families.json", {"families": [{
        "family_id": "family", "configurations": [
            {"root_id": f"native-root-v1:{config}", "config": {"rndSeed": i}, "decks": []}
            for i, config in enumerate(configurations)
        ],
    }]})
    monkeypatch.setattr(supervisor, "FrozenCollectionProtocol", SimpleNamespace(
        model_validate_json=lambda _: frozen,
    ))
    monkeypatch.setattr(supervisor, "verify_protocol_documents", lambda *_: None)
    monkeypatch.setattr(supervisor, "collection_sources", lambda _: [])
    monkeypatch.setattr(supervisor, "artifact_digest", lambda _: digest)
    monkeypatch.setattr(supervisor, "register_family", lambda *args, **kwargs: None)
    calls = []

    def run_job(directory, spec, native_lock):
        calls.append(directory.name)
        return 7 if directory.name.split("-")[-1] == failed_stage else 0

    monkeypatch.setattr(supervisor, "run_job", run_job)
    arguments = ["supervisor"]
    for option in ("protocol", "registry", "campaign", "gamedata", "catalog", "adb"):
        arguments.extend([f"--{option}", str(tmp_path / ("protocol.json" if option == "protocol" else option))])
    monkeypatch.setattr(sys, "argv", arguments)
    if failed_stage is None:
        supervisor.main()
    else:
        with pytest.raises(SystemExit) as stopped:
            supervisor.main()
        assert stopped.value.code == 7
    campaign = tmp_path / "campaign"
    stages = ["capture", "prepare", "native", "scalar"]
    if failed_stage in stages:
        expected = [f"{configurations[0]}-{stage}" for stage in stages[:stages.index(failed_stage) + 1]]
        assert calls == expected
        assert json.loads((campaign / "failure.json").read_text()) == {
            "protocol_sha256": digest, "job": expected[-1], "exit_code": 7,
            "configurations_started": 1,
        }
        assert list(json.loads((campaign / "execution-index.json").read_text())) == configurations[:1]
        assert not (campaign / "complete.json").exists()
    else:
        assert calls == [f"{config}-{stage}" for config in configurations for stage in stages] + ["evaluation"]
        assert not (campaign / "failure.json").exists()
        assert json.loads((campaign / "complete.json").read_text())["evaluation_exit_code"] == (7 if failed_stage else 0)
