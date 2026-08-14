from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import run_interaction_shard as shard_runner

SCRIPT = Path(__file__).parents[1] / "scripts" / "run_interaction_shard.py"


def _run(tmp_path: Path, *extra: str) -> dict[str, object]:
    summary = tmp_path / "summary.json"
    command = [
        sys.executable,
        str(SCRIPT),
        "--kind",
        "1v1",
        "--shard-index",
        "0",
        "--shard-count",
        "8464",
        "--ticks",
        "1",
        "--limit",
        "1",
        "--json-out",
        str(summary),
        *extra,
    ]
    subprocess.run(command, check=True, capture_output=True, text=True)
    return json.loads(summary.read_text())


def test_completed_journal_resumes_without_duplicate_cases(tmp_path: Path) -> None:
    first = _run(tmp_path)
    second = _run(tmp_path, "--resume")
    records = (tmp_path / "summary.jsonl").read_text().splitlines()

    assert first["cases_run"] == second["cases_run"] == 1
    assert second["completed_this_run"] == 0
    assert second["resume_from_count"] == 1
    assert len(records) == 2
    assert first["candidate"] == "python-self"
    assert first["journal_path"] == "summary.jsonl"
    assert first["semantic_event_tracing"] == "deferred"
    assert first["event_counts_scope"] == "scenario-setup-only"
    record = json.loads(records[1])
    assert record["capability_accepted"] is True
    assert record["expected_state_sha256"] == record["actual_state_sha256"]
    assert record["state_sha256"] == record["expected_state_sha256"]
    assert record["parity_checks"] == record["ticks_compared"] == 1
    assert record["parity_mismatches"] == 0
    assert record["shadow_checks"] == record["shadow_mismatches"] == 0


def test_resume_discards_truncated_tail(tmp_path: Path) -> None:
    expected = _run(tmp_path)
    journal = tmp_path / "summary.jsonl"
    with journal.open("ab") as target:
        target.write(b'{"type":"case"')

    resumed = _run(tmp_path, "--resume")

    assert resumed["sha256_chain"] == expected["sha256_chain"]
    assert journal.read_bytes().endswith(b"\n")


def test_resume_rejects_fingerprint_change(tmp_path: Path) -> None:
    _run(tmp_path)
    summary = tmp_path / "summary.json"
    command = [
        sys.executable,
        str(SCRIPT),
        "--kind",
        "1v1",
        "--shard-index",
        "0",
        "--shard-count",
        "8464",
        "--ticks",
        "2",
        "--limit",
        "1",
        "--json-out",
        str(summary),
        "--resume",
    ]

    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert "fingerprint mismatch" in completed.stderr


def test_resume_rejects_noncontiguous_case_index(tmp_path: Path) -> None:
    _run(tmp_path)
    journal = tmp_path / "summary.jsonl"
    lines = journal.read_text().splitlines()
    record = json.loads(lines[1])
    record["index"] = 99
    journal.write_text(lines[0] + "\n" + json.dumps(record) + "\n")

    with pytest.raises(subprocess.CalledProcessError):
        subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--kind",
                "1v1",
                "--shard-index",
                "0",
                "--shard-count",
                "8464",
                "--ticks",
                "1",
                "--limit",
                "1",
                "--json-out",
                str(tmp_path / "summary.json"),
                "--resume",
            ],
            check=True,
            capture_output=True,
            text=True,
        )


def test_rust_candidate_capability_failure_precedes_case_record(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = SimpleNamespace(case_id="unsupported-case")

    def reject(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise RuntimeError("resident core cannot execute the complete tick")

    monkeypatch.setattr(shard_runner, "run_rust_interaction_case", reject)

    with pytest.raises(RuntimeError, match="cannot execute the complete tick"):
        shard_runner._run_candidate_case(
            "resident-rust-shadow",
            case,
            ticks=1,
            seed=1,
            dump_directory=None,
        )


def test_rust_candidate_record_has_exact_zero_mismatch_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = SimpleNamespace(case_id="supported-case")
    setup = SimpleNamespace()
    result = SimpleNamespace(
        ticks_compared=3,
        expected_sha256="ab" * 32,
        actual_sha256="ab" * 32,
    )
    monkeypatch.setattr(
        shard_runner,
        "run_rust_interaction_case",
        lambda *args, **kwargs: (setup, result),
    )
    monkeypatch.setattr(
        shard_runner,
        "interaction_case_summary",
        lambda value: {"index": 9, "event_family": "ordinary", "event_applied": True},
    )

    actual_setup, actual_result = shard_runner._run_candidate_case(
        "resident-rust-shadow",
        case,
        ticks=3,
        seed=1,
        dump_directory=None,
    )
    record = shard_runner._case_record(
        "resident-rust-shadow",
        actual_setup,
        actual_result,
    )

    assert record["capability_accepted"] is True
    assert record["state_sha256"] == "ab" * 32
    assert record["shadow_checks"] == 3
    assert record["shadow_mismatches"] == 0


def test_rust_candidate_provenance_hashes_native_binary() -> None:
    artifact = shard_runner._preflight_candidate("resident-rust-shadow")

    assert artifact is not None
    assert artifact["path_name"].endswith((".so", ".dylib", ".pyd"))
    assert len(artifact["sha256"]) == 64
