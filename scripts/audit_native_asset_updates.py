"""Compare decoded bundled records with downloaded native logic updates."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path

import tomllib

from clasher.native_assets import decode_logic_asset


def parse_asset(data, suffix):
    text = data.decode("utf-8-sig")
    if suffix == ".toml":
        return tomllib.loads(text)
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        raise ValueError("empty CSV logic asset")
    header = rows[0]
    if len(set(header)) != len(header):
        raise ValueError("duplicate CSV columns")
    # Some shipped tables contain unnamed trailing columns, including cells
    # in their type row. Preserve those values by position in this audit.
    width = max(map(len, rows))
    header = [*header, *(f"__unnamed_column_{i}" for i in range(len(header), width))]
    records = {}
    current_name = ""
    for row in rows[1:]:
        if not row:
            continue
        current_name = row[0] or current_name
        entries = records.setdefault(current_name, {})
        entries[str(len(entries))] = dict(
            zip(header, row + [""] * (len(header) - len(row)), strict=True)
        )
    return {"columns": header, "rows": records}


def differences(before, after, path=()):
    if isinstance(before, dict) and isinstance(after, dict):
        for key in sorted(before.keys() | after.keys()):
            if key not in before or key not in after:
                yield {
                    "path": [*path, key],
                    "before_present": key in before,
                    "after_present": key in after,
                    "before": before.get(key),
                    "after": after.get(key),
                }
            else:
                yield from differences(before[key], after[key], (*path, key))
    elif before != after:
        yield {"path": list(path), "before": before, "after": after}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundled-decoded", type=Path, required=True)
    parser.add_argument("--downloaded", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--include-csv", action="store_true")
    args = parser.parse_args()
    records = []
    updates = list(args.downloaded.rglob("*.toml"))
    if args.include_csv:
        updates.extend(args.downloaded.rglob("*.csv"))
    for update in sorted(updates):
        relative = update.relative_to(args.downloaded)
        bundled = args.bundled_decoded / relative
        compressed = update.read_bytes()
        decoded = decode_logic_asset(compressed)
        before_bytes = bundled.read_bytes() if bundled.exists() else None
        before = parse_asset(before_bytes, update.suffix) if before_bytes else {}
        after = parse_asset(decoded, update.suffix)
        records.append(
            {
                "path": str(relative),
                "bundled_present": before_bytes is not None,
                "bundled_sha256": (
                    hashlib.sha256(before_bytes).hexdigest() if before_bytes else None
                ),
                "downloaded_sha256": hashlib.sha256(compressed).hexdigest(),
                "decoded_sha256": hashlib.sha256(decoded).hexdigest(),
                "differences": list(differences(before, after)),
            }
        )
    if not records:
        parser.error("no downloaded logic assets found")
    result = {
        "scope": (
            "TOML and CSV updates; asset differences do not certify a ruleset"
            if args.include_csv
            else "TOML updates only; excludes CSV tables and does not certify a ruleset"
        ),
        "bundled_decoded": str(args.bundled_decoded.resolve()),
        "downloaded": str(args.downloaded.resolve()),
        "files_compared": len(records),
        "files_changed": sum(bool(r["differences"]) for r in records),
        "records": records,
    }
    with args.output.open("x") as output:
        json.dump(result, output, indent=2)
        output.write("\n")
    print(json.dumps({k: v for k, v in result.items() if k != "records"}))


if __name__ == "__main__":
    main()
