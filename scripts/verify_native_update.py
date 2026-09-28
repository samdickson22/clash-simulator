"""Verify downloaded native update files against a pinned compatibility manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath


def digest(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def verify(root: Path, manifest_path: Path, engine_path: Path) -> dict:
    root = root.resolve()
    manifest = json.loads(manifest_path.read_text())
    engine = json.loads(engine_path.read_text())
    expected = {
        name.removeprefix("runtime-update/"): value
        for name, value in manifest["source_files"].items()
        if name.startswith("runtime-update/")
    }
    if not expected:
        raise ValueError("manifest has no runtime update files")
    expected["fingerprint.json"] = engine["runtime_fingerprint_sha256"]
    rows = []
    for name, expected_hash in sorted(expected.items()):
        relative = PurePosixPath(name)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("unsafe manifest path")
        path = (root / name).resolve()
        if not path.is_relative_to(root):
            raise ValueError("manifest file escapes update root")
        actual = digest(path) if path.is_file() else None
        rows.append(
            {
                "path": name,
                "expected_sha256": expected_hash,
                "actual_sha256": actual,
                "matches": actual == expected_hash,
            }
        )
    return {
        "status": "matched" if all(r["matches"] for r in rows) else "mismatch",
        "runtime_content_version": engine["runtime_content_version"],
        "manifest_sha256": digest(manifest_path),
        "engine_pin_sha256": digest(engine_path),
        "root": str(root),
        "files": rows,
        "scope": "Pinned Null's update identity only; not official-game fidelity or replay acceptance.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--engine-pin", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.root, args.manifest, args.engine_pin)
    with args.output.open("x") as target:
        json.dump(result, target, indent=2)
        target.write("\n")
    print(result["status"], len(result["files"]), "files checked")
    raise SystemExit(0 if result["status"] == "matched" else 1)


if __name__ == "__main__":
    main()
