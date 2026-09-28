"""Evidence completion requires the exact files, role and immutable contents."""

import pytest

from clasher.rl.calibration_artifacts import seal_artifacts, verify_artifacts


def sealed(tmp_path):
    (tmp_path / "result.json").write_text('{"winner":0}')
    (tmp_path / "trace.gz").write_bytes(b"compressed trace bytes")
    args = {
        "kind": "paired_branches",
        "role": "acceptance",
        "protocol_sha256": "a" * 64,
    }
    paths = {"result.json", "trace.gz"}
    seal_artifacts(tmp_path, **args, paths=paths)
    return args, paths


def test_completed_evidence_can_be_verified_but_not_resealed(tmp_path):
    args, paths = sealed(tmp_path)
    assert len(verify_artifacts(tmp_path, **args, required_paths=paths).files) == 2
    with pytest.raises(FileExistsError):
        seal_artifacts(tmp_path, **args, paths=paths)


@pytest.mark.parametrize(
    "fault", ["result", "trace", "missing", "inventory", "role", "protocol"]
)
def test_changed_or_incomplete_evidence_is_rejected(tmp_path, fault):
    args, paths = sealed(tmp_path)
    if fault == "result":
        (tmp_path / "result.json").write_text('{"winner":1}')
    elif fault == "trace":
        (tmp_path / "trace.gz").write_bytes(b"different")
    elif fault == "missing":
        (tmp_path / "trace.gz").unlink()
    elif fault == "inventory":
        paths.add("missing.json")
    elif fault == "role":
        args["role"] = "development"
    else:
        args["protocol_sha256"] = "b" * 64
    with pytest.raises((ValueError, FileNotFoundError)):
        verify_artifacts(tmp_path, **args, required_paths=paths)


def test_receipt_cannot_claim_an_external_file(tmp_path):
    with pytest.raises(ValueError, match="leaves"):
        seal_artifacts(
            tmp_path,
            kind="native_capture",
            role="development",
            protocol_sha256=None,
            paths={"../outside"},
        )


def test_acceptance_receipt_requires_protocol(tmp_path):
    (tmp_path / "result").write_text("data")
    with pytest.raises(ValueError, match="frozen protocol"):
        seal_artifacts(
            tmp_path,
            kind="native_capture",
            role="acceptance",
            protocol_sha256=None,
            paths={"result"},
        )
    assert not (tmp_path / "artifact-receipt.json").exists()


@pytest.mark.parametrize(
    "fault", [None, "incomplete", "aggregate", "duplicate", "role"]
)
def test_branch_reader_checks_semantics_after_receipt_verification(tmp_path, fault):
    import json

    from clasher.rl.calibration_artifacts import (
        branch_artifact_paths,
        read_branch_evidence,
    )

    protocol = {
        "role": "acceptance",
        "collection_protocol_sha256": "a" * 64,
        "response_seeds": [1],
        "candidates": [{"name": "wait"}, {"name": "recorded"}],
    }
    rows = []
    for candidate in ("wait", "recorded"):
        row = {
            "response_seed": 1,
            "candidate": candidate,
            "engine": "native",
            "failure": None,
            "terminal": {"tick": 3601, "winner": 0, "towers": []},
        }
        if fault == "incomplete" and candidate == "wait":
            row["terminal"] = None
        sub = tmp_path / f"1-{candidate}-native"
        sub.mkdir()
        (sub / "result.json").write_text(json.dumps(row))
        (sub / "decisions.jsonl.gz").write_bytes(b"fixture trace")
        rows.append(row)
    if fault == "aggregate":
        rows[0]["terminal"]["winner"] = 1
    if fault == "duplicate":
        rows.append(rows[0])
    complete = {
        "role": "development" if fault == "role" else "acceptance",
        "sources_unchanged": True,
        "collection_protocol_sha256": "a" * 64,
        "branches": 2,
    }
    for name, value in [
        ("protocol.json", protocol),
        ("results.json", rows),
        ("complete.json", complete),
        ("provenance.json", {}),
    ]:
        (tmp_path / name).write_text(json.dumps(value))
    (tmp_path / "producer-source.zip").write_bytes(b"fixture producer")
    seal_artifacts(
        tmp_path,
        kind="paired_branches",
        role="acceptance",
        protocol_sha256="a" * 64,
        paths=branch_artifact_paths(protocol, ("native",)),
    )
    if fault is None:
        assert (
            len(
                read_branch_evidence(
                    tmp_path,
                    protocol=protocol,
                    engines=("native",),
                    protocol_sha256="a" * 64,
                )
            )
            == 2
        )
    else:
        with pytest.raises(ValueError):
            read_branch_evidence(
                tmp_path,
                protocol=protocol,
                engines=("native",),
                protocol_sha256="a" * 64,
            )
