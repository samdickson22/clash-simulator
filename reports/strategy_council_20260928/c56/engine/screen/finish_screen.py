"""Finish the existing baseline screen with two disjoint resumable workers.

prepare is read/write only and requires the original screen process stopped.
worker must be launched with baseline-src on PYTHONPATH and nice -n 10.
merge verifies exact tag coverage and preserves existing result lines.
"""

from __future__ import annotations

import argparse
import contextlib
import gzip
import hashlib
import io
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCAN = HERE.parents[2] / "m0/human-prior-scan"
OUTPUT = HERE / "resim_screen.jsonl"
PLAN = HERE / "completion_plan.json"


def inputs():
    seen = set()
    for pool in ("s120", "g66"):
        with gzip.open(SCAN / f"payloads_{pool}_tier_a.jsonl.gz", "rt") as stream:
            for line in stream:
                record = json.loads(line)
                if record["tag"] in seen or record["payload"]["battle"][
                    "result"
                ] not in ("victory", "defeat", "draw"):
                    continue
                seen.add(record["tag"])
                yield pool, record


def read_rows(path):
    return (
        [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
        if path.exists()
        else []
    )


def prepare():
    previous = read_rows(OUTPUT)
    done = {r["tag"] for r in previous}
    assert len(done) == len(previous)
    pending = [r["tag"] for _, r in inputs() if r["tag"] not in done]
    plan = {
        "existing_sha256": hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
        "existing_count": len(done),
        "expected_tags": [r["tag"] for _, r in inputs()],
        "workers": [pending[::2], pending[1::2]],
    }
    with PLAN.open("x") as stream:
        json.dump(plan, stream, indent=2)
    print(
        json.dumps(
            {
                "existing": len(done),
                "pending": len(pending),
                "workers": [len(w) for w in plan["workers"]],
            }
        )
    )


def worker(index):
    # The original runner imports resim_pilot from this same source location.
    sys.path.insert(0, str(SCAN))
    import resim_pilot

    import clasher

    assert "baseline-src" in str(Path(clasher.__file__).resolve()), (
        "baseline source is required"
    )
    plan = json.loads(PLAN.read_text())
    assigned = set(plan["workers"][index])
    path = HERE / f"completion-{index}.jsonl"
    done = {r["tag"] for r in read_rows(path)}
    assert done <= assigned
    with path.open("a") as stream:
        for pool, record in inputs():
            if record["tag"] not in assigned or record["tag"] in done:
                continue
            started = time.time()
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    result = resim_pilot.run_match(record)
            except Exception as exc:  # noqa: BLE001 - retain every failed match like the original screen
                result = {"tag": record["tag"], "error": f"{type(exc).__name__}: {exc}"}
            result.update(pool=pool, seconds=round(time.time() - started, 2))
            stream.write(json.dumps(result) + "\n")
            stream.flush()
            done.add(record["tag"])
    assert done == assigned
    print("done", index, len(done), flush=True)


def merge():
    plan = json.loads(PLAN.read_text())
    assert hashlib.sha256(OUTPUT.read_bytes()).hexdigest() == plan["existing_sha256"], (
        "original output changed"
    )
    original = read_rows(OUTPUT)
    extra = []
    for index, tags in enumerate(plan["workers"]):
        rows = read_rows(HERE / f"completion-{index}.jsonl")
        assert len(rows) == len(tags) and {r["tag"] for r in rows} == set(tags)
        extra.extend(rows)
    merged = {r["tag"]: r for r in original + extra}
    assert len(merged) == len(original) + len(extra) == len(plan["expected_tags"])
    assert set(merged) == set(plan["expected_tags"])
    # Keep every original byte and append completed rows in the declared input order.
    pending = {r["tag"]: r for r in extra}
    with OUTPUT.open("a") as stream:
        for tag in plan["expected_tags"]:
            if tag in pending:
                stream.write(json.dumps(pending[tag]) + "\n")
    print("merged", len(merged))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["prepare", "worker", "merge"])
    parser.add_argument("--index", type=int, choices=[0, 1])
    args = parser.parse_args()
    if args.mode == "worker":
        if args.index is None:
            parser.error("--index required")
        worker(args.index)
    elif args.mode == "prepare":
        prepare()
    else:
        merge()


if __name__ == "__main__":
    main()
