#!/usr/bin/env python3
"""TIERS Amendment 4, B.5: assemble the Mac states.pkl and its expected fingerprint.

Order: T1's published 1,200 (END order), golden125 (END order), then the extra
agreement/packet rows by (TIERS index, seed, tick), taken from the SHA-verified
captures. Speed rows always come from the published file. The first 1,325
canonical digests must equal the committed END index (c09142b9). The list is
written once with pickle.dump(..., protocol=5) to a new file; identity is the
ordered canonical fingerprint, never the pickle SHA (Amendment 3).
"""
import argparse
import json
import os
from pathlib import Path
import pickle
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import macreg_io as io


def load_pinned_pickle(path, expected):
    if io.file_sha(path) != expected:
        raise ValueError("Pin mismatch: " + str(path))
    with Path(path).open("rb") as stream:  # executes only after the SHA matched
        return pickle.load(stream)


def end_prefix(rows, end, canonical_digest):
    """B.5: the END part of the fixture equals the reviewed c09142b9 index, entry by entry."""
    entries = [dict(id=str(r["id"]), canonical_sha256=canonical_digest(r)) for r in rows]
    if entries != end:
        bad = next((i for i, (x, y) in enumerate(zip(entries, end)) if x != y), min(len(entries), len(end)))
        raise ValueError("END prefix differs from c09142b9 at entry %d" % bad)
    return entries


def extra_rows(plan, files, validate_row, canonical_digest, log=print):
    """The plan's extra rows, read from their SHA-verified captures, validated again."""
    wanted = {}
    for identity in plan["extra_ids"]:
        wanted.setdefault(plan["extra_sources"][identity], set()).add(identity)
    found = {}
    for entry in files:
        ids = wanted.pop(entry["relative"], None)
        if not ids:
            continue
        capture = io.load_capture(entry)
        for row in io.capture_rows(capture):
            if row["id"] in ids:
                io.row_identity(row, entry)
                validate_row(row, entry["tier"])
                found[row["id"]] = row
        del capture
        log("extra rows from %s: %d" % (entry["relative"], len(ids)))
    if wanted or set(found) != set(plan["extra_ids"]):
        raise ValueError("Extra rows missing from their captures")
    rows = [found[i] for i in plan["extra_ids"]]
    return rows, [dict(id=str(r["id"]), canonical_sha256=canonical_digest(r)) for r in rows]


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    io.runtime_arguments(p)
    p.add_argument("--corpora", type=Path, required=True)
    p.add_argument("--end-digests", type=Path, required=True)
    p.add_argument("--end-digests-sha256", required=True)
    p.add_argument("--captures", type=Path, required=True)
    p.add_argument("--public", type=Path, required=True, help="T1 published states.pkl (282b0877)")
    p.add_argument("--golden", type=Path, required=True, help="golden125 states.pkl (8b188918)")
    p.add_argument("--selection", type=Path, required=True, help="build_sets output directory")
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args(argv)
    io.require_low_priority()
    a.output.mkdir(parents=True)
    pins, runtime = io.setup_runtime(a)
    stage_sha = io.file_sha(a.selection / "selection-stage.json")
    stage = json.loads((a.selection / "selection-stage.json").read_text())
    io.verify_artifacts({a.selection / "pool.json": stage["output_sha256"]["pool"],
                         a.selection / "mac-sets.json": stage["output_sha256"]["sets"]})
    plan = io.read_pinned_json(a.selection / "fixture-plan.json", stage["output_sha256"]["plan"])
    corpora = io.read_pinned_json(a.corpora, io.CORPORA_SHA256)
    end = io.end_digests(a.end_digests, a.end_digests_sha256)
    if plan["fixture_ids"][:io.END_ROWS] != [e["id"] for e in end] or plan["fixture_ids"][io.END_ROWS:] != plan["extra_ids"]:
        raise ValueError("Fixture plan is not END + extra rows")
    from convert_states import canonical_digest, fingerprint
    from corpus_contract import validate_row
    started = io.utc()
    public = load_pinned_pickle(a.public, io.PUBLIC_SHA256)
    golden = load_pinned_pickle(a.golden, io.GOLDEN_SHA256)
    rows = public + golden  # T1 END order
    del public, golden
    entries = end_prefix(rows, end, canonical_digest)
    print("END prefix: %d entries equal c09142b9" % len(entries), flush=True)
    extra, extra_entries = extra_rows(plan, io.capture_inventory(corpora, a.captures), validate_row, canonical_digest)
    rows.extend(extra)
    entries.extend(extra_entries)
    if [e["id"] for e in entries] != plan["fixture_ids"] or len({e["id"] for e in entries}) != len(entries):
        raise ValueError("Assembled order differs from the fixture plan")
    target = a.output / "states.pkl"
    with target.open("xb") as stream:
        pickle.dump(rows, stream, protocol=5)
        stream.flush()
        os.fsync(stream.fileno())
    states_sha, states_bytes = io.file_sha(target), target.stat().st_size
    expected = fingerprint(entries)
    index_sha = io.write_json(a.output / "fixture-digests.json", dict(rows=entries, fixture_canonical_fingerprint=expected))
    receipt = dict(schema="clasher.tiers-a4.assembly.v1", utc_start=started, utc_end=io.utc(), **io.process_identity(),
                   e4v3_pins=pins, runtime=runtime, versions=io.runtime_versions(),
                   selection_stage_sha256=stage_sha, sets_sha256=stage["sets_sha256"], script_sha256={n: io.file_sha(io.HERE / n) for n in ("assemble_states.py", "macreg_io.py")},
                   inputs=dict(public=io.PUBLIC_SHA256, golden=io.GOLDEN_SHA256, corpora=io.CORPORA_SHA256,
                               end_digests=a.end_digests_sha256, fixture_plan=stage["output_sha256"]["plan"]),
                   end_prefix=dict(entries=io.END_ROWS, equal=True, end_fingerprint=io.END_FINGERPRINT),
                   rows=len(rows), extra_rows=len(extra),
                   states=dict(file="states.pkl", sha256=states_sha, bytes=states_bytes,
                               note="process-specific bytes (torch storage keys); identity is the fingerprint"),
                   fixture_digests_sha256=index_sha, expected_fingerprint=expected,
                   outcomes_read=False, games_read=False, timing=False)
    io.write_json(a.output / "assembly.json", receipt)
    print(json.dumps(dict(rows=len(rows), states_sha256=states_sha, expected_fingerprint=expected)), flush=True)


if __name__ == "__main__":
    main()
