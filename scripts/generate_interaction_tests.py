#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from clasher.interaction_matrix import matrix_manifest

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / "tests" / "generated_interactions"


def _existing_test_inventory() -> dict[str, object]:
    files: list[dict[str, Any]] = []
    total_functions = 0
    for path in sorted((REPO_ROOT / "tests").glob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        functions: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
                node.name.startswith("test_")
            ):
                functions.append(node.name)
        functions.sort()
        total_functions += len(functions)
        files.append(
            {
                "path": str(path.relative_to(REPO_ROOT)),
                "static_test_functions": functions,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    return {
        "schema_version": 1,
        "test_file_count": len(files),
        "static_test_function_count": total_functions,
        "note": (
            "Static inventory only; pytest parameter expansion is intentionally "
            "reported separately by collection commands in the evidence report."
        ),
        "files": files,
    }


def _render_files(
    *,
    one_v_one_shards: int,
    two_v_two_shards: int,
) -> dict[str, str]:
    manifest = matrix_manifest(
        one_v_one_shards=one_v_one_shards,
        two_v_two_shards=two_v_two_shards,
    )
    return {
        "interaction_manifest.json": json.dumps(
            manifest,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        "existing_test_inventory.json": json.dumps(
            _existing_test_inventory(),
            indent=2,
            sort_keys=True,
        )
        + "\n",
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate deterministic simulator interaction test manifests"
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--one-v-one-shards", type=int, default=32)
    parser.add_argument("--two-v-two-shards", type=int, default=256)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.one_v_one_shards <= 0 or args.two_v_two_shards <= 0:
        raise ValueError("shard counts must be positive")
    rendered = _render_files(
        one_v_one_shards=args.one_v_one_shards,
        two_v_two_shards=args.two_v_two_shards,
    )
    output = args.output.resolve()
    mismatches: list[str] = []
    if args.check:
        for name, content in rendered.items():
            target = output / name
            if not target.exists() or target.read_text(encoding="utf-8") != content:
                mismatches.append(str(target))
        if mismatches:
            print("generated interaction manifests are stale:", file=sys.stderr)
            for mismatch in mismatches:
                print(f"  {mismatch}", file=sys.stderr)
            raise SystemExit(1)
        print(f"generated interaction manifests are current: {output}")
        return

    output.mkdir(parents=True, exist_ok=True)
    for name, content in rendered.items():
        target = output / name
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(target)
        print(f"wrote {target}")


if __name__ == "__main__":
    main()
