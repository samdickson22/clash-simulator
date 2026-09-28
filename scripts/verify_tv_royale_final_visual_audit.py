"""Verify that a manual TV Royale audit binds every final rendered source."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object: {path}")
    return payload


def verify_final_visual_audit(
    *,
    audit_path: Path,
    contact_manifest_path: Path,
    run_manifest_path: Path,
    expected_games: int = 1_000,
) -> dict[str, Any]:
    audit = _object(audit_path)
    contact = _object(contact_manifest_path)
    if audit.get("schema") != "tv-royale-public-v2-visual-audit-v1":
        raise ValueError("unsupported final visual-audit schema")
    if audit.get("accepted") is not True:
        raise ValueError("final contact sheets have not passed visual inspection")
    if audit.get("contact_manifest_sha256") != _sha256(contact_manifest_path):
        raise ValueError("visual audit does not bind the final contact manifest")
    if contact.get("schema") != "tv-royale-public-arena-contact-sheets-v1":
        raise ValueError("unsupported final contact-sheet manifest")
    if int(contact.get("completed_games_at_render", -1)) != expected_games:
        raise ValueError("visual audit is not based on the final game count")
    if Path(str(contact.get("run_manifest", ""))).resolve() != run_manifest_path.resolve():
        raise ValueError("contact sheets identify another collection run")
    if contact.get("run_manifest_sha256") != _sha256(run_manifest_path):
        raise ValueError("collection manifest changed after contact-sheet rendering")
    arenas = [f"arena_{number}" for number in range(12, 32)]
    if contact.get("arenas") != arenas or int(contact.get("quantiles", -1)) != 4:
        raise ValueError("final contact-sheet arena or chronology coverage is incomplete")
    sheets = contact.get("sheets")
    if not isinstance(sheets, list) or len(sheets) != 8:
        raise ValueError("final contact-sheet count is incomplete")
    expected_pairs = {(quantile, phase) for quantile in range(4) for phase in ("early", "late")}
    observed_pairs: set[tuple[int, str]] = set()
    expected_outputs: set[str] = set()
    expected_sources: set[str] = set()
    for row in sheets:
        if not isinstance(row, dict):
            raise TypeError("contact sheet row must be an object")
        pair = (int(row.get("quantile", -1)), str(row.get("phase", "")))
        observed_pairs.add(pair)
        output = Path(str(row.get("output", ""))).resolve()
        if not output.is_file() or row.get("output_sha256") != _sha256(output):
            raise ValueError(f"contact sheet is missing or changed: {output}")
        if str(output) in expected_outputs:
            raise ValueError(f"duplicate contact-sheet output: {output}")
        expected_outputs.add(str(output))
        sources = row.get("sources")
        if not isinstance(sources, list) or len(sources) != len(arenas):
            raise ValueError(f"contact sheet lacks one source per arena: {output}")
        source_arenas: list[str] = []
        for source_row in sources:
            if not isinstance(source_row, dict):
                raise TypeError("contact-sheet source must be an object")
            source = Path(str(source_row.get("source", ""))).resolve()
            if not source.is_file() or source_row.get("source_sha256") != _sha256(source):
                raise ValueError(f"contact-sheet source is missing or changed: {source}")
            if str(source) in expected_sources:
                raise ValueError(f"duplicate contact-sheet source: {source}")
            expected_sources.add(str(source))
            source_arenas.append(str(source_row.get("arena", "")))
        if source_arenas != arenas:
            raise ValueError(f"contact-sheet source arena order is incomplete: {output}")
    if observed_pairs != expected_pairs:
        raise ValueError("contact-sheet quantile/phase coverage is incomplete")
    reviewed_rows = audit.get("reviewed_sheets")
    if not isinstance(reviewed_rows, list) or len(reviewed_rows) != len(sheets):
        raise ValueError("visual audit did not review every final contact sheet")
    reviewed = {str(Path(str(path)).resolve()) for path in reviewed_rows}
    if len(reviewed) != len(reviewed_rows):
        raise ValueError("visual audit contains duplicate reviewed sheets")
    if reviewed != expected_outputs:
        raise ValueError("visual audit did not review every final contact sheet")
    return {
        "schema": "tv-royale-final-visual-audit-verification-v1",
        "status": "final_visual_audit_verified",
        "games": expected_games,
        "arenas": len(arenas),
        "sheets": len(sheets),
        "source_frames": len(expected_sources),
        "audit": str(audit_path.resolve()),
        "audit_sha256": _sha256(audit_path),
        "contact_manifest": str(contact_manifest_path.resolve()),
        "contact_manifest_sha256": _sha256(contact_manifest_path),
        "run_manifest": str(run_manifest_path.resolve()),
        "run_manifest_sha256": _sha256(run_manifest_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", required=True, type=Path)
    parser.add_argument("--contact-manifest", required=True, type=Path)
    parser.add_argument("--run-manifest", required=True, type=Path)
    parser.add_argument("--expected-games", type=int, default=1_000)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    payload = verify_final_visual_audit(
        audit_path=args.audit,
        contact_manifest_path=args.contact_manifest,
        run_manifest_path=args.run_manifest,
        expected_games=args.expected_games,
    )
    if args.output.exists():
        if _object(args.output) != payload:
            raise SystemExit(
                f"existing verification output is stale or inconsistent: {args.output}"
            )
        print(json.dumps(payload, sort_keys=True))
        return
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
