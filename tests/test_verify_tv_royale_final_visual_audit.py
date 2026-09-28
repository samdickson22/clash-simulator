from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.verify_tv_royale_final_visual_audit import verify_final_visual_audit


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    run = tmp_path / "run.json"
    contact = tmp_path / "contact.json"
    audit = tmp_path / "audit.json"
    _write(run, {"completed_games": 10})
    arenas = [f"arena_{number}" for number in range(12, 32)]
    sheets = []
    for quantile in range(4):
        for phase in ("early", "late"):
            sources = []
            for arena in arenas:
                source = tmp_path / f"{quantile}-{phase}-{arena}.jpg"
                source.write_bytes(f"source:{quantile}:{phase}:{arena}".encode())
                sources.append(
                    {
                        "arena": arena,
                        "source": str(source),
                        "source_sha256": _sha256(source),
                    }
                )
            output = tmp_path / f"q{quantile:02d}_{phase}.jpg"
            output.write_bytes(f"sheet:{quantile}:{phase}".encode())
            sheets.append(
                {
                    "quantile": quantile,
                    "phase": phase,
                    "output": str(output),
                    "output_sha256": _sha256(output),
                    "sources": sources,
                }
            )
    _write(
        contact,
        {
            "schema": "tv-royale-public-arena-contact-sheets-v1",
            "run_manifest": str(run),
            "run_manifest_sha256": _sha256(run),
            "completed_games_at_render": 10,
            "arenas": arenas,
            "quantiles": 4,
            "sheets": sheets,
        },
    )
    _write(
        audit,
        {
            "schema": "tv-royale-public-v2-visual-audit-v1",
            "accepted": True,
            "contact_manifest_sha256": _sha256(contact),
            "reviewed_sheets": [row["output"] for row in sheets],
        },
    )
    return run, contact, audit


def _rebind_audit(contact: Path, audit: Path) -> None:
    payload = json.loads(audit.read_text(encoding="utf-8"))
    payload["contact_manifest_sha256"] = _sha256(contact)
    _write(audit, payload)


def test_visual_audit_verifier_binds_all_sheets_and_sources(tmp_path: Path) -> None:
    run, contact, audit = _fixture(tmp_path)

    result = verify_final_visual_audit(
        audit_path=audit,
        contact_manifest_path=contact,
        run_manifest_path=run,
        expected_games=10,
    )

    assert result["status"] == "final_visual_audit_verified"
    assert result["sheets"] == 8
    assert result["source_frames"] == 160


def test_visual_audit_verifier_rejects_changed_source_frame(tmp_path: Path) -> None:
    run, contact, audit = _fixture(tmp_path)
    payload = json.loads(contact.read_text(encoding="utf-8"))
    source = Path(payload["sheets"][0]["sources"][0]["source"])
    source.write_bytes(b"changed")

    with pytest.raises(ValueError, match="source is missing or changed"):
        verify_final_visual_audit(
            audit_path=audit,
            contact_manifest_path=contact,
            run_manifest_path=run,
            expected_games=10,
        )


def test_visual_audit_verifier_rejects_unreviewed_sheet(tmp_path: Path) -> None:
    run, contact, audit = _fixture(tmp_path)
    payload = json.loads(audit.read_text(encoding="utf-8"))
    payload["reviewed_sheets"].pop()
    _write(audit, payload)

    with pytest.raises(ValueError, match="did not review every"):
        verify_final_visual_audit(
            audit_path=audit,
            contact_manifest_path=contact,
            run_manifest_path=run,
            expected_games=10,
        )


def test_visual_audit_verifier_rejects_duplicate_sheet_output(tmp_path: Path) -> None:
    run, contact, audit = _fixture(tmp_path)
    payload = json.loads(contact.read_text(encoding="utf-8"))
    payload["sheets"][1]["output"] = payload["sheets"][0]["output"]
    payload["sheets"][1]["output_sha256"] = payload["sheets"][0]["output_sha256"]
    _write(contact, payload)
    _rebind_audit(contact, audit)

    with pytest.raises(ValueError, match="duplicate contact-sheet output"):
        verify_final_visual_audit(
            audit_path=audit,
            contact_manifest_path=contact,
            run_manifest_path=run,
            expected_games=10,
        )


def test_visual_audit_verifier_rejects_duplicate_source_frame(tmp_path: Path) -> None:
    run, contact, audit = _fixture(tmp_path)
    payload = json.loads(contact.read_text(encoding="utf-8"))
    payload["sheets"][1]["sources"][0]["source"] = payload["sheets"][0][
        "sources"
    ][0]["source"]
    payload["sheets"][1]["sources"][0]["source_sha256"] = payload["sheets"][0][
        "sources"
    ][0]["source_sha256"]
    _write(contact, payload)
    _rebind_audit(contact, audit)

    with pytest.raises(ValueError, match="duplicate contact-sheet source"):
        verify_final_visual_audit(
            audit_path=audit,
            contact_manifest_path=contact,
            run_manifest_path=run,
            expected_games=10,
        )


def test_visual_audit_verifier_rejects_duplicate_review_entry(tmp_path: Path) -> None:
    run, contact, audit = _fixture(tmp_path)
    payload = json.loads(audit.read_text(encoding="utf-8"))
    payload["reviewed_sheets"][-1] = payload["reviewed_sheets"][0]
    _write(audit, payload)

    with pytest.raises(ValueError, match="duplicate reviewed sheets"):
        verify_final_visual_audit(
            audit_path=audit,
            contact_manifest_path=contact,
            run_manifest_path=run,
            expected_games=10,
        )
