#!/usr/bin/env python3
"""Create a deterministic YouTube inventory excluding completed local sources."""

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _complete_ids(roots: list[Path]) -> set[str]:
    result: set[str] = set()
    for root in roots:
        if not root.exists():
            continue
        for manifest in sorted(root.glob("*/manifest.json")):
            value = json.loads(manifest.read_text(encoding="utf-8"))
            if not isinstance(value, dict):
                continue
            schema = value.get("schema")
            complete = value.get("status") == "complete" or (
                isinstance(schema, str)
                and schema.startswith("clasher.youtube.fullmatch.extraction_manifest.v")
            )
            if not complete:
                continue
            source = value.get("source")
            video_id = source.get("video_id") if isinstance(source, dict) else None
            if not isinstance(video_id, str) or video_id != manifest.parent.name:
                raise ValueError(f"source manifest video ID mismatch: {manifest}")
            result.add(video_id)
    return result


def filter_inventory(
    input_path: Path,
    exclude_roots: list[Path],
    output: Path,
    manifest_path: Path,
) -> dict[str, Any]:
    excluded = _complete_ids(exclude_roots)
    retained: list[dict[str, Any]] = []
    seen: set[str] = set()
    for line_number, line in enumerate(
        input_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict) or not isinstance(value.get("id"), str):
            raise TypeError(f"invalid inventory row {line_number}")
        video_id = value["id"]
        if video_id in seen:
            raise ValueError(f"duplicate inventory video ID: {video_id}")
        seen.add(video_id)
        if video_id not in excluded:
            retained.append(value)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.{os.getpid()}.tmp")
    temporary.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in retained),
        encoding="utf-8",
    )
    os.replace(temporary, output)
    payload = {
        "schema": "clasher.youtube.filtered_inventory.v1",
        "input": str(input_path.resolve()),
        "input_sha256": _sha256(input_path),
        "exclude_roots": [str(path.resolve()) for path in exclude_roots],
        "input_rows": len(seen),
        "excluded_complete_video_ids": len(seen & excluded),
        "retained_rows": len(retained),
        "output": str(output.resolve()),
        "output_sha256": _sha256(output),
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_manifest = manifest_path.with_name(
        f".{manifest_path.name}.{os.getpid()}.tmp"
    )
    temporary_manifest.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary_manifest, manifest_path)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--exclude-source-root", action="append", default=[], type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args()
    payload = filter_inventory(
        args.input, args.exclude_source_root, args.output, args.manifest
    )
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
