"""Compare two executions of the same readiness branch, decision by decision.

Primary gate (must be identical): decision ticks, selected actions, public
packet hashes of both seats at every decision, accepted command stream
(command strings, selections, schedule acknowledgement fields other than the
process-global sequence counter and allocation epochs), terminal tick, winner,
finalization and every tower's HP.

Secondary evidence: full native frames. Allocation identities (generation,
stateEpoch, verified-session IDs, process identity) legitimately differ
between runs; every other differing path is listed exactly.
"""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

ALLOCATION_KEYS = {"generation", "stateEpoch", "snapshotHandles"}
SESSION_KEYS = {"verified_session", "session_id"}
STORAGE_KEY = "storage_provenance"


def rows(path):
    with gzip.open(path, "rt") as stream:
        return [json.loads(line) for line in stream]


def strip(value, drop):
    if isinstance(value, dict):
        return {k: strip(v, drop) for k, v in value.items() if k not in drop}
    if isinstance(value, list):
        return [strip(v, drop) for v in value]
    return value


def diff_paths(a, b, path="", limit=200, out=None):
    out = [] if out is None else out
    if len(out) >= limit:
        return out
    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(set(a) | set(b), key=str):
            if key not in a or key not in b:
                out.append(f"{path}/{key} (present only in {'A' if key in a else 'B'})")
            else:
                diff_paths(a[key], b[key], f"{path}/{key}", limit, out)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append(f"{path} (list length {len(a)} vs {len(b)})")
        for index, (x, y) in enumerate(zip(a, b)):
            diff_paths(x, y, f"{path}[{index}]", limit, out)
    elif a != b:
        out.append(f"{path} ({json.dumps(a)[:80]} vs {json.dumps(b)[:80]})")
    return out


def generalize(paths):
    """Collapse list indices so repeated per-object differences summarize."""
    import re

    counts = {}
    for path in paths:
        key = re.sub(r"\[\d+\]", "[*]", path.split(" (")[0])
        counts[key] = counts.get(key, 0) + 1
    return counts


TRACE_FIELDS = (
    "combatEvents", "phaseRuntime", "specialMovementRuntime", "actionMovementRuntime",
    "characterStateRuntime", "visibilityRuntime", "remainingRuntime",
)


def telemetry(path):
    """Probe hook-telemetry: trace envelopes and per-object last-step records."""
    return any(path.startswith(f"/rich/{name}/") for name in TRACE_FIELDS) or (
        path.startswith("/rich/objects[*]/phaseRuntime/")
    )


def command_stream(transport_rows):
    stream = []
    for row in transport_rows:
        stream.append(
            {
                "tick": row["tick"],
                "selected": row["selected"],
                "commands": row["commands"],
                "receipts": strip(row["receipts"], ALLOCATION_KEYS | {"sequence"}),
                "before": strip(row["before"], ALLOCATION_KEYS),
                "after": strip(row["after"], ALLOCATION_KEYS),
            }
        )
    return stream


def towers(ordinary):
    return sorted(
        (o["owner"], o["nativeObjectId"], o["hp"])
        for o in ordinary["objects"]
        if o["cardId"] == -1
    )


def compare(a: Path, b: Path) -> dict:
    report = {"a": str(a), "b": str(b)}
    for side, folder in (("a", a), ("b", b)):
        if (folder / "failure.json").exists():
            report[f"{side}_failure"] = json.loads((folder / "failure.json").read_text())
    if any(k.endswith("_failure") for k in report):
        report["identical"] = False
        return report
    da, db = rows(a / "decisions.jsonl.gz"), rows(b / "decisions.jsonl.gz")
    report["decisions"] = [len(da), len(db)]
    first = None
    packets_equal = 0
    frame_gameplay_mismatch = []
    census = {}
    nontelemetry_decisions = 0
    for index, (x, y) in enumerate(zip(da, db)):
        same = (
            x["tick"] == y["tick"]
            and x["actions"] == y["actions"]
            and x["public_sha256"] == y["public_sha256"]
        )
        packets_equal += same
        if not same and first is None:
            first = {"index": index, "a": {k: x[k] for k in ("tick", "actions", "public_sha256")},
                     "b": {k: y[k] for k in ("tick", "actions", "public_sha256")}}
        fa = strip(x["native_frame"], ALLOCATION_KEYS | SESSION_KEYS | {STORAGE_KEY})
        fb = strip(y["native_frame"], ALLOCATION_KEYS | SESSION_KEYS | {STORAGE_KEY})
        if fa != fb:
            paths = generalize(diff_paths(fa, fb, limit=100000))
            for path in paths:
                census[path] = census.get(path, 0) + 1
            if any(not telemetry(path) for path in paths):
                nontelemetry_decisions += 1
            if len(frame_gameplay_mismatch) < 3:
                frame_gameplay_mismatch.append(
                    {"index": index, "tick": x["tick"], "paths": paths}
                )
    report["decision_rows_identical"] = packets_equal
    report["first_decision_mismatch"] = first
    report["compact_frame_differences_first3"] = frame_gameplay_mismatch
    report["compact_frame_difference_census"] = census
    report["compact_frame_decisions_with_nontelemetry_differences"] = nontelemetry_decisions
    ta, tb = rows(a / "transport.jsonl.gz"), rows(b / "transport.jsonl.gz")
    sa, sb = command_stream(ta), command_stream(tb)
    report["transport_rows"] = [len(sa), len(sb)]
    report["commands_submitted"] = [
        sum(len(r["commands"]) for r in sa), sum(len(r["commands"]) for r in sb)
    ]
    report["command_stream_identical"] = sa == sb
    if sa != sb:
        mismatch = next(
            (i for i, (x, y) in enumerate(zip(sa, sb)) if x != y), min(len(sa), len(sb))
        )
        report["first_command_mismatch"] = {
            "index": mismatch,
            "paths": diff_paths(sa[mismatch], sb[mismatch]) if mismatch < min(len(sa), len(sb)) else "length",
        }
    terminal_a = json.loads((a / "terminal.json").read_text())
    terminal_b = json.loads((b / "terminal.json").read_text())
    summary = {}
    for side, terminal in (("a", terminal_a), ("b", terminal_b)):
        playable, final = terminal["playable"], terminal["final"]
        summary[side] = {
            "playable_tick": playable["tick"], "final_tick": final["tick"],
            "ended": final["ended"], "finalized": final["finalized"],
            "winner": final["winner"], "towers_playable": towers(playable),
            "towers_final": towers(final),
        }
    report["terminal"] = summary
    report["terminal_identical"] = summary["a"] == summary["b"]
    report["terminal_ordinary_identical"] = strip(terminal_a, ALLOCATION_KEYS) == strip(
        terminal_b, ALLOCATION_KEYS
    )
    ra = json.loads((a / "result.json").read_text())
    rb = json.loads((b / "result.json").read_text())
    keys = ("score", "own_remaining_hp", "enemy_remaining_hp", "winner", "level_coverage")
    report["result"] = {"a": {k: ra[k] for k in keys}, "b": {k: rb[k] for k in keys}}
    report["result_identical"] = report["result"]["a"] == report["result"]["b"]
    report["identical"] = bool(
        len(da) == len(db)
        and packets_equal == len(da)
        and report["command_stream_identical"]
        and report["terminal_identical"]
        and report["terminal_ordinary_identical"]
        and report["result_identical"]
    )
    fa, fb = a / "first-decision-full-frame.json.gz", b / "first-decision-full-frame.json.gz"
    if fa.exists() and fb.exists():
        with gzip.open(fa, "rt") as s1, gzip.open(fb, "rt") as s2:
            full_a, full_b = json.load(s1), json.load(s2)
        raw_paths = diff_paths(full_a, full_b, limit=100000)
        stripped = diff_paths(
            strip(full_a, ALLOCATION_KEYS | SESSION_KEYS),
            strip(full_b, ALLOCATION_KEYS | SESSION_KEYS),
            limit=100000,
        )
        report["first_frame"] = {
            "raw_identical": not raw_paths,
            "raw_differing_paths": generalize(raw_paths),
            "identical_excluding_allocation_and_session_ids": not stripped,
            "differing_paths_excluding_allocation_and_session_ids": generalize(stripped),
            "nontelemetry_differing_paths": sorted(
                p for p in generalize(stripped)
                if not telemetry(p) and not p.startswith("/level_source/verified_session")
            ),
            "ordinary_identical_excluding_allocation": strip(full_a["ordinary"], ALLOCATION_KEYS)
            == strip(full_b["ordinary"], ALLOCATION_KEYS),
            "levels_identical": full_a["level_source"]["levels"] == full_b["level_source"]["levels"],
        }
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pair", nargs=3, action="append", metavar=("LABEL", "A", "B"),
                        required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    reports = {label: compare(Path(a), Path(b)) for label, a, b in args.pair}
    summary = {
        "pairs": len(reports),
        "identical_pairs": sum(r["identical"] for r in reports.values()),
        "reports": reports,
    }
    args.output.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({k: {"identical": r["identical"], "decisions": r.get("decisions"),
                          "commands": r.get("commands_submitted")}
                      for k, r in reports.items()}, indent=1))


if __name__ == "__main__":
    main()
