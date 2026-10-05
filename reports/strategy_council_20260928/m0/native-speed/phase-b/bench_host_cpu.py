"""Offline host-CPU benchmark: cumulative vs delta rich transfer (no device).

Rebuilds full native frames from saved Phase A evidence (fast-snapshot-i2
job-00049: the stored compact records keep every envelope; omitted events are
re-synthesized with their recorded counts and real per-ring event templates),
then times the host work per decision for:

  full : json.loads(observe-rich bytes) + compact_native_frame(frame)
  delta: json.loads(observe-rich-since bytes) + accumulator.apply
         + compact_native_frame(frame, event_cache=...)

The delta response carries the measured mean number of new events per
decision. The reconstructed rich object and the compact record must equal the
full-path ones byte for byte, or the benchmark aborts.

Usage: .venv/bin/python -B bench_host_cpu.py --output bench-host-cpu.json
"""

from __future__ import annotations

import argparse
import copy
import gzip
import json
import platform
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "src"))

from clasher.rl import native_frame_storage as storage
from clasher.rl.native_rich_delta import (
    DELTA_KEYS,
    TRACE_ORDER,
    TRANSMIT_FIELD_TRACES,
    NativeRichTraceAccumulator,
)

JOB = ROOT / "reports/strategy_council_20260928/m0/native-speed/equivalence/fast-snapshot-i2/job-00049"
# Mean new events per decision over the 723 decisions of job-00049 (rounded up).
NEW_EVENTS = {"combatEvents": 2, "phaseRuntime": 12, "remainingRuntime": 1}


def load_frames(indices):
    with gzip.open(JOB / "first-decision-full-frame.json.gz", "rt") as stream:
        first = json.load(stream)
    templates = {f: first["rich"][f]["events"] for f in TRACE_ORDER}
    wanted, frames = set(indices), {}
    with gzip.open(JOB / "decisions.jsonl.gz", "rt") as stream:
        for index, line in enumerate(stream):
            if index in wanted:
                frames[index] = json.loads(line)["native_frame"]
            last = index
    frames.setdefault(last, None)
    return templates, frames, last


def synthesize(frame, templates):
    frame = copy.deepcopy(frame)
    stored = frame.pop("storage_provenance")
    for field in TRACE_ORDER:
        env = frame["rich"][field]
        count = stored["omitted_events"].get(field, {"count": 0})["count"]
        env["events"] = [event(templates[field], field, env["nextSequence"] - count + i) for i in range(count)]
    return frame, stored


def event(template, field, sequence):
    base = copy.deepcopy(template[sequence % len(template)]) if template else {"kind": field}
    base["sequence"] = sequence
    return base


def with_delta(env, since, transmit, events):
    out = {}
    for key, value in env.items():
        if key == "events":
            out[DELTA_KEYS[0]], out[DELTA_KEYS[1]] = since, transmit
            out["events"] = events
        elif key == "transmitFromSequence":
            out[key] = transmit
        else:
            out[key] = value
    return out


def delta_pair(rich, templates):
    """(prior full-retransmit delta, current delta) around the given frame."""
    prior, current = dict(rich), dict(rich)
    for field in TRACE_ORDER:
        env = rich[field]
        nxt, oldest, first, cap = (env[k] for k in ("nextSequence", "oldestRetainedSequence",
                                                     "epochFirstSequence", "capacity"))
        k = min(NEW_EVENTS.get(field, 0), len(env["events"]))
        prior_next = nxt - k
        prior_oldest = prior_next - cap if prior_next > first + cap else first
        older = [event(templates[field], field, s) for s in range(prior_oldest, oldest)]
        by_seq = {e["sequence"]: e for e in env["events"]}
        prior_events = older + [by_seq[s] for s in range(oldest, prior_next)]
        penv = with_delta(env, 0, prior_oldest, prior_events)
        penv.update(nextSequence=prior_next, oldestRetainedSequence=prior_oldest)
        if field in TRANSMIT_FIELD_TRACES:
            penv["transmitFromSequence"] = prior_oldest
        prior[field] = penv
        current[field] = with_delta(env, prior_next, prior_next, [by_seq[s] for s in range(prior_next, nxt)])
    return prior, current


def best(fn, repeats):
    times = []
    for _ in range(repeats):
        start = time.perf_counter()
        fn()
        times.append(time.perf_counter() - start)
    return min(times), sorted(times)[len(times) // 2]


def measure(frame, templates, repeats):
    full_bytes = storage._json_bytes(frame["rich"])
    prior, current = delta_pair(frame["rich"], templates)
    delta_bytes = storage._json_bytes(current)
    prior_bytes = storage._json_bytes(prior)

    def full_path():
        rich = json.loads(full_bytes)
        return storage.compact_native_frame({**frame, "rich": rich})

    def delta_path():
        accumulator = NativeRichTraceAccumulator()
        accumulator.apply(json.loads(prior_bytes))  # previous decision (not timed below)
        start = time.perf_counter()
        rich = accumulator.apply(json.loads(delta_bytes))
        record = storage.compact_native_frame({**frame, "rich": rich},
                                              event_cache=accumulator.event_cache(rich))
        return rich, record, time.perf_counter() - start

    reference = full_path()
    rich, record, _ = delta_path()
    if storage._json_bytes(rich) != full_bytes or storage._json_bytes(record) != storage._json_bytes(reference):
        raise SystemExit("delta reconstruction or cached compaction differs from the full path")
    full_min, full_median = best(full_path, repeats)
    delta_times = sorted(delta_path()[2] for _ in range(repeats))
    parse_full = best(lambda: json.loads(full_bytes), repeats)[0]
    compact_full = best(lambda: storage.compact_native_frame(frame), repeats)[0]
    return {
        "full_rich_bytes": len(full_bytes),
        "delta_rich_bytes": len(delta_bytes),
        "retained_events": sum(len(frame["rich"][f]["events"]) for f in TRACE_ORDER),
        "new_events": sum(len(current[f]["events"]) for f in TRACE_ORDER),
        "full_ms": {"min": round(full_min * 1e3, 2), "median": round(full_median * 1e3, 2),
                    "parse_min": round(parse_full * 1e3, 2), "compact_min": round(compact_full * 1e3, 2)},
        "delta_ms": {"min": round(delta_times[0] * 1e3, 2),
                     "median": round(delta_times[len(delta_times) // 2] * 1e3, 2)},
        "identical_output": True,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=7)
    args = parser.parse_args()
    templates, frames, last = load_frames([0, 180, 361, 540])
    _, tail, _ = load_frames([last])
    frames[last] = tail[last]
    results = {}
    for index in sorted(frames):
        frame, stored = synthesize(frames[index], templates)
        result = measure(frame, templates, args.repeats)
        result["recorded_full_frame_json_bytes"] = stored["full_frame_json_bytes"]
        results[f"decision-{index}"] = result
        print(index, json.dumps(result), flush=True)
    receipt = {
        "schema": "native-speed-phase-b-host-cpu-bench.v1",
        "source": str(JOB.relative_to(ROOT)),
        "new_events_per_decision": NEW_EVENTS,
        "python": platform.python_version(),
        "machine": platform.machine(),
        "note": "host CPU only (parse + reconstruction + compaction); device transfer not included",
        "results": results,
    }
    args.output.write_text(json.dumps(receipt, indent=2) + "\n")


if __name__ == "__main__":
    main()
