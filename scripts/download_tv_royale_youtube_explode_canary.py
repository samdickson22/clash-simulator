"""Acquire the bounded ten-video canary through YoutubeExplode high-res streams."""

from __future__ import annotations

# mypy: disable-error-code="import-untyped"
import argparse
import json
import os
import shutil
import tempfile
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from clasher.rl.oracle_corpus import atomic_write_json, file_sha256
from scripts.download_tv_royale_youtube_canary import (
    MAX_TOTAL_BYTES,
    OUTPUT_SCHEMA,
    CommandRunner,
    _default_runner,
    _directory_bytes,
    load_sanitized_manifest,
    predicted_total_bytes,
    sections_for,
)

MAX_TRANSIENT_BYTES = 500 * 1024**2
DOTNET = Path("/Users/sam/.local/share/dotnet-clasher/dotnet")
PROJECT = Path("tools/youtube_explode_canary/YoutubeExplodeCanary.csproj")
YOUTUBE_DOWNLOADER_COMMIT = "bbcff039515a2ac985e3769f0243a58645a52b28"
YOUTUBE_EXPLODE_COMMIT = "a268db97feb1689b3f5eab18fdbc73f983a21ce5"
YOUTUBE_EXPLODE_VERSION = "6.6.1"


def _artifact(path: Path, root: Path) -> dict[str, Any]:
    return {
        "path": str(path.relative_to(root)),
        "bytes": path.stat().st_size,
        "sha256": file_sha256(path),
    }


def _run(
    command: Sequence[str],
    *,
    runner: CommandRunner,
    root: Path,
    records: list[dict[str, Any]],
) -> str:
    started = time.monotonic()
    stdout = runner(command, None, root, MAX_TOTAL_BYTES)
    records.append(
        {
            "argv": list(command),
            "elapsed_seconds": time.monotonic() - started,
            "monitored_bytes_after": _directory_bytes(root),
        }
    )
    return stdout


def acquire_highres_canary(
    *,
    metadata_manifest: Path,
    output_directory: Path,
    runner: CommandRunner = _default_runner,
    dotnet: Path = DOTNET,
    project: Path = PROJECT,
) -> dict[str, Any]:
    source_sha = file_sha256(metadata_manifest)
    source_payload, sources = load_sanitized_manifest(metadata_manifest)
    if file_sha256(metadata_manifest) != source_sha:
        raise RuntimeError("metadata manifest changed during validation")
    predicted = predicted_total_bytes(sources)
    if predicted > MAX_TOTAL_BYTES:
        raise ValueError("predicted total exceeds 5 GiB")
    if source_payload["permission_provenance"].get("public_cc_license_claimed") is not False:
        raise ValueError("public_cc_license_claimed must be explicitly false")
    if output_directory.exists():
        raise FileExistsError(output_directory)
    output_directory.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(
            prefix=f".{output_directory.name}.",
            suffix=".partial",
            dir=output_directory.parent,
        )
    )
    commands: list[dict[str, Any]] = []
    run_started = time.monotonic()
    try:
        build = [
            str(dotnet),
            "build",
            str(project),
            "--configuration",
            "Release",
            "--nologo",
        ]
        _run(build, runner=runner, root=staging, records=commands)
        videos: list[dict[str, Any]] = []
        for source in sources:
            source_started = time.monotonic()
            video_dir = staging / source.video_id
            video_dir.mkdir()
            transient = video_dir / "transient_original.stream"
            download = [
                str(dotnet),
                "run",
                "--project",
                str(project),
                "--configuration",
                "Release",
                "--no-build",
                "--",
                source.url,
                str(transient),
            ]
            metadata = json.loads(
                _run(download, runner=runner, root=staging, records=commands)
            )
            stream = metadata["stream"]
            declared = int(stream["declaredBytes"])
            actual = transient.stat().st_size
            if declared != actual or not 0 < actual <= MAX_TRANSIENT_BYTES:
                raise RuntimeError(
                    f"{source.video_id} declared/actual transient bound mismatch"
                )
            if int(stream["width"]) < 1000 or int(stream["height"]) < 1900:
                raise RuntimeError(f"{source.video_id} did not resolve high resolution")
            transient_record = {
                **_artifact(transient, staging),
                **stream,
                "deleted_before_publication": True,
            }
            section_records: list[dict[str, Any]] = []
            for section in sections_for(source):
                section_path = video_dir / f"section_{section.label}.mp4"
                ffmpeg = [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-ss",
                    f"{section.start_seconds:.3f}",
                    "-i",
                    str(transient),
                    "-t",
                    f"{section.duration_seconds:.3f}",
                    "-map",
                    "0:v:0",
                    "-an",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "18",
                    "-pix_fmt",
                    "yuv420p",
                    "-movflags",
                    "+faststart",
                    str(section_path),
                ]
                _run(ffmpeg, runner=runner, root=staging, records=commands)
                probe_command = [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration,size:stream=codec_type,width,height,avg_frame_rate,codec_name",
                    "-of",
                    "json",
                    str(section_path),
                ]
                probe = json.loads(
                    _run(probe_command, runner=runner, root=staging, records=commands)
                )
                if any(row.get("codec_type") != "video" for row in probe["streams"]):
                    raise RuntimeError("retained section contains a non-video stream")
                duration = float(probe["format"]["duration"])
                if not 7.9 <= duration <= 8.1:
                    raise RuntimeError(f"section duration out of bounds: {duration}")
                frames_dir = video_dir / f"frames_{section.label}"
                frames_dir.mkdir()
                frame_command = [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-i",
                    str(section_path),
                    "-an",
                    "-vf",
                    "fps=1/2",
                    "-q:v",
                    "3",
                    str(frames_dir / "frame_%03d.jpg"),
                ]
                _run(frame_command, runner=runner, root=staging, records=commands)
                decode = [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-i",
                    str(section_path),
                    "-f",
                    "null",
                    "-",
                ]
                _run(decode, runner=runner, root=staging, records=commands)
                frame_paths = sorted(frames_dir.glob("frame_*.jpg"))
                if not frame_paths:
                    raise RuntimeError("section produced no audit frames")
                section_records.append(
                    {
                        "label": section.label,
                        "fraction": section.fraction,
                        "requested_start_seconds": section.start_seconds,
                        "requested_end_seconds": section.end_seconds,
                        "media": _artifact(section_path, staging),
                        "probe": probe,
                        "frames": [_artifact(path, staging) for path in frame_paths],
                        "full_decode_passed": True,
                    }
                )
            transient.unlink()
            videos.append(
                {
                    "id": source.video_id,
                    "url": source.url,
                    "duration_seconds": source.duration_seconds,
                    "transient_video_only_source": transient_record,
                    "elapsed_seconds": time.monotonic() - source_started,
                    "sections": section_records,
                }
            )
        actual = _directory_bytes(staging)
        manifest: dict[str, Any] = {
            "schema": OUTPUT_SCHEMA,
            "backend": "youtube-downloader-core-youtube-explode-highres-v1",
            "source_manifest": {
                "path": str(metadata_manifest.resolve()),
                "sha256": source_sha,
                "schema": source_payload["schema"],
            },
            "permission_provenance": dict(source_payload["permission_provenance"]),
            "tools": {
                "youtube_downloader_commit": YOUTUBE_DOWNLOADER_COMMIT,
                "youtube_explode_commit": YOUTUBE_EXPLODE_COMMIT,
                "youtube_explode_version": YOUTUBE_EXPLODE_VERSION,
                "dotnet_sdk": "10.0.100",
                "dotnet_runtime": "10.0.0",
            },
            "limits": {
                "maximum_videos": 10,
                "maximum_total_bytes": MAX_TOTAL_BYTES,
                "maximum_transient_bytes": MAX_TRANSIENT_BYTES,
                "predicted_total_bytes_with_safety_factor": predicted,
                "actual_bytes_before_manifest": actual,
                "published_total_bytes": 0,
                "cookies_used": False,
                "account_used": False,
                "po_token_used": False,
            },
            "coverage": {
                "requested_videos": len(sources),
                "completed_videos": len(videos),
                "requested_sections": len(sources) * 3,
                "completed_sections": sum(len(row["sections"]) for row in videos),
                "fractions": [0.1, 0.5, 0.9],
            },
            "performance": {
                "wall_seconds_before_manifest": time.monotonic() - run_started,
                "recorded_command_seconds": sum(
                    float(row["elapsed_seconds"]) for row in commands
                ),
                "peak_scratch_bytes": max(
                    (int(row["monitored_bytes_after"]) for row in commands),
                    default=0,
                ),
            },
            "commands": commands,
            "videos": videos,
        }
        manifest_path = staging / "manifest.json"
        for _ in range(4):
            atomic_write_json(manifest_path, manifest)
            measured = _directory_bytes(staging)
            if manifest["limits"]["published_total_bytes"] == measured:
                break
            manifest["limits"]["published_total_bytes"] = measured
        atomic_write_json(manifest_path, manifest)
        if _directory_bytes(staging) != manifest["limits"]["published_total_bytes"]:
            raise RuntimeError("published byte count did not stabilize")
        if _directory_bytes(staging) > MAX_TOTAL_BYTES:
            raise RuntimeError("published canary exceeds 5 GiB")
        if file_sha256(metadata_manifest) != source_sha:
            raise RuntimeError("metadata manifest changed before publication")
        os.replace(staging, output_directory)
        return manifest
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metadata-manifest", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    args = parser.parse_args()
    result = acquire_highres_canary(
        metadata_manifest=args.metadata_manifest,
        output_directory=args.output_directory,
    )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
