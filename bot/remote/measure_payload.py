#!/usr/bin/env python3
"""Read two existing JSONL files; emit only sizes/provenance, never row contents."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess


def measure(directory):
    frames_path = directory / "frames.jsonl"
    decisions_path = directory / "decisions.jsonl"
    frames_raw = frames_path.read_bytes()
    decisions_raw = decisions_path.read_bytes()
    frames = [(len(line), json.loads(line)) for line in frames_raw.splitlines()]
    size, frame = sorted(frames, key=lambda item: item[0])[math.ceil(.95 * len(frames)) - 1]
    frame_times = {row["n"]: row["ts_ms"] for _, row in frames}
    history = [line for line in decisions_raw.splitlines(keepends=True)
               if frame["ts_ms"] - 30000 < frame_times[json.loads(line)["n"]] <= frame["ts_ms"]]
    return {
        "label": "proxy: per-frame perception row + 30 s play history",
        "source_host": "127x05", "source_directory": str(directory),
        "measured_at_utc": subprocess.check_output(["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"], text=True).strip(),
        "frames_sha256": hashlib.sha256(frames_raw).hexdigest(),
        "decisions_sha256": hashlib.sha256(decisions_raw).hexdigest(),
        "frame_count": len(frames), "frame_p95_method": "nearest rank, raw UTF-8 row excluding newline",
        "frame_p95_bytes": size, "selected_frame_n": frame["n"],
        "selected_frame_ts_ms": frame["ts_ms"], "history_seconds": 30,
        "history_row_count": len(history), "history_bytes_including_newlines": sum(map(len, history)),
        "realistic_bytes": size + sum(map(len, history)),
        "history_method": "Join decisions.n to frames.n/ts_ms; take (selected ts_ms - 30000, selected ts_ms]. All decision telemetry rows included, not just plays.",
        "caveat": "Sizing proxy, not a serialized search request. Frame rows include HUD/units summaries and timings; decision telemetry overestimates compact play history. No original row contents are shipped.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    print(json.dumps(measure(parser.parse_args().directory), indent=2))
