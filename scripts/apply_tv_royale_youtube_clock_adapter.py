from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, cast

ANCHOR_SCHEMA = "clasher.youtube.clock_anchor.v1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def portable_path(path: Path) -> str:
    """Keep repository-owned artifacts portable across synced checkouts."""
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return str(path)


def atomic_json(path: Path, payload: object) -> None:
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(payload, output, indent=2, sort_keys=True)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def load_anchors(path: Path, *, stride: int) -> dict[int, dict[str, Any]]:
    anchors: dict[int, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        output_pts = row.get("output_pts")
        seconds = row.get("seconds_remaining")
        confidence = row.get("confidence")
        if (
            row.get("schema") != ANCHOR_SCHEMA
            or row.get("current_frame_only") is not True
            or not isinstance(output_pts, int)
            or isinstance(output_pts, bool)
            or output_pts < 0
            or output_pts % stride
            or not isinstance(seconds, int)
            or isinstance(seconds, bool)
            or not 0 <= seconds <= 599
            or isinstance(confidence, bool)
            or not isinstance(confidence, int | float)
            or not 0.0 < float(confidence) <= 1.0
            or not isinstance(row.get("raw_text"), list)
        ):
            raise ValueError(f"invalid current-frame clock anchor: {row}")
        if output_pts in anchors:
            raise ValueError(f"duplicate clock anchor output_pts {output_pts}")
        anchors[output_pts] = row
    if not anchors:
        raise ValueError("clock adapter produced no valid anchors")
    return anchors


def apply_clock_anchors(
    *,
    input_manifest: Path,
    anchors_path: Path,
    output_dir: Path,
    provider_path: Path,
    provider_sha256: str,
) -> dict[str, Any]:
    if output_dir.exists():
        raise FileExistsError(output_dir)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(
            prefix=f".{output_dir.name}.", suffix=".partial", dir=output_dir.parent
        )
    )
    manifest = cast(
        dict[str, Any], json.loads(input_manifest.read_text(encoding="utf-8"))
    )
    neutral_source = Path(manifest["artifacts"]["neutral_sequence"]["path"])
    event_source = Path(manifest["artifacts"]["offline_play_events"]["path"])
    stride = int(
        manifest.get("models", {}).get("clock_head", {}).get("anchor_stride_frames", 5)
    )
    if stride <= 0:
        raise ValueError("clock anchor stride must be positive")
    anchors = load_anchors(anchors_path, stride=stride)
    neutral_name = "neutral_sequence_clocked.jsonl.gz"
    neutral_output = staging / neutral_name
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{neutral_output.name}.", suffix=".tmp", dir=staging
    )
    os.close(descriptor)
    rows = 0
    valid = 0
    try:
        with (
            gzip.open(neutral_source, "rt", encoding="utf-8") as source,
            gzip.open(temporary, "wt", encoding="utf-8", compresslevel=6) as sink,
        ):
            for line in source:
                if not line.strip():
                    continue
                row = json.loads(line)
                output_pts = int(row["output_pts"])
                anchor_pts = output_pts - output_pts % stride
                anchor = anchors.get(anchor_pts)
                if anchor is None:
                    row["public"]["clock"] = {
                        "value": None,
                        "valid": False,
                        "confidence": 0.0,
                        "reason": "external_clock_anchor_missing",
                        "media_elapsed_ms_label_only": row["timestamp_ms"],
                    }
                else:
                    propagated = output_pts != anchor_pts
                    row["public"]["clock"] = {
                        "value": int(anchor["seconds_remaining"]),
                        "valid": True,
                        "confidence": float(anchor["confidence"])
                        * (0.98 if propagated else 1.0),
                        "raw_text": anchor["raw_text"],
                        "evidence": (
                            "external_linux_current_clock_crop"
                            if not propagated
                            else "external_linux_anchor_within_same_stride_window"
                        ),
                        "anchor_output_pts": anchor_pts,
                        "media_elapsed_ms_label_only": row["timestamp_ms"],
                    }
                    valid += 1
                sink.write(json.dumps(row, sort_keys=True, separators=(",", ":")))
                sink.write("\n")
                rows += 1
        os.replace(temporary, neutral_output)
    finally:
        Path(temporary).unlink(missing_ok=True)

    event_output = staging / event_source.name
    event_temporary = staging / f".{event_source.name}.tmp"
    shutil.copy2(event_source, event_temporary)
    os.replace(event_temporary, event_output)
    result = copy.deepcopy(manifest)
    result["artifacts"]["neutral_sequence"] = {
        "path": portable_path(output_dir / neutral_name),
        "sha256": sha256(neutral_output),
        "rows": rows,
    }
    result["artifacts"]["actor_trajectories"] = []
    result["artifacts"]["offline_play_events"] = {
        "path": portable_path(output_dir / event_source.name),
        "sha256": sha256(event_output),
        "rows": manifest["artifacts"]["offline_play_events"]["rows"],
    }
    result["coverage"]["clock_valid_frames"] = valid
    result["models"]["clock_head"] = {
        "implementation": "pinned_external_linux_clock_adapter",
        "provider_path": str(provider_path),
        "provider_sha256": provider_sha256,
        "adapter_output_sha256": sha256(anchors_path),
        "anchor_schema": ANCHOR_SCHEMA,
        "anchor_stride_frames": stride,
        "anchors_valid": len(anchors),
    }
    result["limitations"] = [
        (
            "clock OCR uses pinned external Linux current-frame anchors with "
            "within-stride propagation; missing anchors fail closed"
            if "clock" in str(item).casefold()
            else item
        )
        for item in result.get("limitations", [])
    ]
    manifest_output = staging / "manifest.json"
    try:
        atomic_json(manifest_output, result)
        os.replace(staging, output_dir)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Apply pinned current-frame Linux clock anchors to extraction"
    )
    parser.add_argument("--input-manifest", type=Path, required=True)
    parser.add_argument("--anchors", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--provider", type=Path, required=True)
    parser.add_argument("--provider-sha256", required=True)
    args = parser.parse_args()
    output = apply_clock_anchors(
        input_manifest=args.input_manifest.resolve(),
        anchors_path=args.anchors.resolve(),
        output_dir=args.output_dir.resolve(),
        provider_path=args.provider.resolve(),
        provider_sha256=args.provider_sha256,
    )
    print(
        json.dumps(
            {
                "manifest": str(args.output_dir / "manifest.json"),
                "clock_valid_frames": output["coverage"]["clock_valid_frames"],
            }
        )
    )


if __name__ == "__main__":
    main()
