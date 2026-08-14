from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

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
