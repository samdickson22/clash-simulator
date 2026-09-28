"""Acquire a permission-gated, video-only YouTube canary as short sections.

The command intentionally accepts only a sanitized metadata manifest.  It never
asks yt-dlp to enumerate a channel or playlist, and it rejects any source that
is not explicitly classified public before starting a download.
"""

from __future__ import annotations

# mypy: disable-error-code="import-untyped"
import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from typing import Any

from clasher.rl.oracle_corpus import atomic_write_json, file_sha256

SCHEMA = "clasher.tv_royale.youtube_metadata_canary.v1"
OUTPUT_SCHEMA = "tv-royale-youtube-section-canary-v1"
PERMISSION_BASIS = "user_attested_channel_owner_approval"
PERMISSION_DATE = "2026-08-17"
MAX_VIDEOS = 10
MAX_TOTAL_BYTES = 5 * 1024**3
SECTION_SECONDS = 8.0
SECTION_FRACTIONS = (0.10, 0.50, 0.90)
PREDICTION_SAFETY_FACTOR = 1.25
FRAME_INTERVAL_SECONDS = 2.0
YOUTUBE_URL = re.compile(
    r"https://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)"
    r"([A-Za-z0-9_-]{11})(?:[&#?].*)?$"
)
DIAGNOSTIC_URL = re.compile(r"https?://\S+")


@dataclass(frozen=True)
class VideoSource:
    video_id: str
    url: str
    duration_seconds: float
    predicted_video_bitrate_bps: float
    predicted_full_bytes: float


@dataclass(frozen=True)
class Section:
    label: str
    fraction: float
    start_seconds: float
    end_seconds: float

    @property
    def duration_seconds(self) -> float:
        return self.end_seconds - self.start_seconds


CommandRunner = Callable[[Sequence[str], Path | None, Path | None, int], str]


def _required_mapping(value: object, *, field: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"{field} must be an object")
    return value


def _required_positive_float(value: object, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(f"{field} must be a positive number")
    result = float(value)
    if not 0.0 < result < float("inf"):
        raise ValueError(f"{field} must be a positive finite number")
    return result


def _prediction_bitrate(row: Mapping[str, Any], duration_seconds: float) -> float:
    bitrate = row.get("predicted_video_bitrate_bps")
    if bitrate is not None:
        return _required_positive_float(
            bitrate, field="predicted_video_bitrate_bps"
        )
    approximate_size = row.get("filesize_approx_bytes")
    if approximate_size is None:
        raise ValueError(
            "video requires predicted_video_bitrate_bps or filesize_approx_bytes"
        )
    return (
        _required_positive_float(approximate_size, field="filesize_approx_bytes")
        * 8.0
        / duration_seconds
    )


def _prediction_full_bytes(
    row: Mapping[str, Any], duration_seconds: float, bitrate_bps: float
) -> float:
    approximate_size = row.get("filesize_approx_bytes")
    if approximate_size is not None:
        return _required_positive_float(
            approximate_size, field="filesize_approx_bytes"
        )
    return duration_seconds * bitrate_bps / 8.0


def load_sanitized_manifest(path: Path) -> tuple[dict[str, Any], list[VideoSource]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema") != SCHEMA:
        raise ValueError(f"manifest schema must be {SCHEMA}")
    permission = _required_mapping(
        payload.get("permission_provenance"), field="permission_provenance"
    )
    if permission.get("basis") != PERMISSION_BASIS:
        raise ValueError(f"permission basis must be {PERMISSION_BASIS}")
    if permission.get("attested_on") != PERMISSION_DATE:
        raise ValueError(f"permission date must be {PERMISSION_DATE}")
    raw_videos = payload.get("videos")
    if not isinstance(raw_videos, list) or not 1 <= len(raw_videos) <= MAX_VIDEOS:
        raise ValueError(f"manifest must contain between 1 and {MAX_VIDEOS} videos")

    sources: list[VideoSource] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_videos):
        row = _required_mapping(raw, field=f"videos[{index}]")
        availability = row.get("availability")
        access_class = row.get("access_class", availability)
        if availability != "public" or access_class != "public":
            raise ValueError(
                f"videos[{index}] is not explicitly public "
                f"(availability={availability!r}, access_class={access_class!r})"
            )
        video_id = str(row.get("id", ""))
        if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
            raise ValueError(f"videos[{index}].id is not a YouTube video ID")
        if video_id in seen:
            raise ValueError(f"duplicate video ID: {video_id}")
        url = str(row.get("url", ""))
        match = YOUTUBE_URL.fullmatch(url)
        if match is None or match.group(1) != video_id:
            raise ValueError(f"videos[{index}].url does not match its public ID")
        duration = _required_positive_float(
            row.get("duration_seconds"), field=f"videos[{index}].duration_seconds"
        )
        if duration <= SECTION_SECONDS * 2.0:
            raise ValueError(
                f"video {video_id} is too short for bounded non-full sections"
            )
        bitrate = _prediction_bitrate(row, duration)
        sources.append(
            VideoSource(
                video_id=video_id,
                url=url,
                duration_seconds=duration,
                predicted_video_bitrate_bps=bitrate,
                predicted_full_bytes=_prediction_full_bytes(row, duration, bitrate),
            )
        )
        seen.add(video_id)
    return payload, sources


def sections_for(source: VideoSource) -> list[Section]:
    sections: list[Section] = []
    half = SECTION_SECONDS / 2.0
    for fraction in SECTION_FRACTIONS:
        center = source.duration_seconds * fraction
        start = min(max(0.0, center - half), source.duration_seconds - SECTION_SECONDS)
        end = start + SECTION_SECONDS
        sections.append(
            Section(
                label=f"p{round(fraction * 100):02d}",
                fraction=fraction,
                start_seconds=start,
                end_seconds=end,
            )
        )
    for left, right in pairwise(sections):
        if left.end_seconds > right.start_seconds:
            raise ValueError(f"video {source.video_id} produces overlapping sections")
    return sections


def predicted_total_bytes(sources: Sequence[VideoSource]) -> int:
    # This deliberately overestimates peak staging: it counts every transient
    # full video even though each is deleted immediately after its sections are
    # cut, plus all retained sections.
    raw = sum(source.predicted_full_bytes for source in sources) + sum(
        section.duration_seconds * source.predicted_video_bitrate_bps / 8.0
        for source in sources
        for section in sections_for(source)
    )
    return int(raw * PREDICTION_SAFETY_FACTOR + 0.999999)


def validate_predicted_quota(sources: Sequence[VideoSource]) -> int:
    predicted = predicted_total_bytes(sources)
    if predicted > MAX_TOTAL_BYTES:
        raise ValueError(
            f"predicted canary size {predicted} exceeds {MAX_TOTAL_BYTES} bytes"
        )
    return predicted


def _directory_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def _redact_diagnostics(value: str) -> str:
    """Keep expiring signed media URLs out of logs and exception messages."""
    return DIAGNOSTIC_URL.sub("[redacted-url]", value)


def _recordable_argv(command: Sequence[str]) -> list[str]:
    result: list[str] = []
    for value in command:
        if value.startswith("https://") and YOUTUBE_URL.fullmatch(value) is None:
            result.append("[redacted-signed-media-url]")
        else:
            result.append(value)
    return result


def _deno_executable() -> Path:
    discovered = shutil.which("deno")
    candidate = Path(discovered) if discovered else Path.home() / ".deno/bin/deno"
    if not candidate.is_file() or not os.access(candidate, os.X_OK):
        raise RuntimeError(
            "Deno >=2.3 is required by yt-dlp for YouTube JavaScript challenges"
        )
    return candidate.resolve()


def _default_runner(
    command: Sequence[str],
    cwd: Path | None,
    monitored_directory: Path | None,
    byte_limit: int,
) -> str:
    process = subprocess.Popen(
        list(command),
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    while process.poll() is None:
        if (
            monitored_directory is not None
            and _directory_bytes(monitored_directory) > byte_limit
        ):
            process.terminate()
            try:
                process.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                process.kill()
            raise RuntimeError("actual canary size exceeded 5 GiB during command")
        time.sleep(0.1)
    stdout, stderr = process.communicate()
    if process.returncode != 0:
        raise RuntimeError(
            f"command failed ({process.returncode}): "
            f"{' '.join(_recordable_argv(command))}\n"
            f"{_redact_diagnostics(stderr)}"
        )
    if monitored_directory is not None and _directory_bytes(monitored_directory) > byte_limit:
        raise RuntimeError("actual canary size exceeded 5 GiB")
    return stdout.strip()


def _run_recorded(
    command: Sequence[str],
    *,
    runner: CommandRunner,
    cwd: Path | None,
    monitored_directory: Path | None,
    records: list[dict[str, Any]],
) -> str:
    started = time.monotonic()
    stdout = runner(command, cwd, monitored_directory, MAX_TOTAL_BYTES)
    monitored_bytes = (
        _directory_bytes(monitored_directory)
        if monitored_directory is not None
        else None
    )
    records.append(
        {
            "argv": _recordable_argv(command),
            "cwd": str(cwd) if cwd else None,
            "stdout": _redact_diagnostics(stdout),
            "elapsed_seconds": time.monotonic() - started,
            "monitored_bytes_after": monitored_bytes,
        }
    )
    return stdout


def _single_section_path(directory: Path, prefix: str) -> Path:
    matches = [
        path
        for path in directory.glob(f"{prefix}.*")
        if path.is_file() and not path.name.endswith((".part", ".ytdl"))
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"expected exactly one completed section for {prefix}; found {matches}"
        )
    return matches[0]


def _probe_section(
    path: Path,
    *,
    runner: CommandRunner,
    root: Path,
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration,size:stream=codec_type",
        "-of",
        "json",
        str(path),
    ]
    payload = json.loads(
        _run_recorded(
            command,
            runner=runner,
            cwd=None,
            monitored_directory=root,
            records=records,
        )
    )
    stream_types = [str(row.get("codec_type")) for row in payload.get("streams", ())]
    if not stream_types or any(value != "video" for value in stream_types):
        raise RuntimeError(f"section must contain video only; streams={stream_types}")
    duration = float(payload["format"]["duration"])
    if not 0.0 < duration <= SECTION_SECONDS + 1.0:
        raise RuntimeError(f"section duration out of bounds: {duration}")
    return {"duration_seconds": duration, "stream_types": stream_types}


def _artifact(path: Path, root: Path) -> dict[str, Any]:
    return {
        "path": str(path.relative_to(root)),
        "bytes": path.stat().st_size,
        "sha256": file_sha256(path),
    }


def acquire_canary(
    *,
    metadata_manifest: Path,
    output_directory: Path,
    runner: CommandRunner = _default_runner,
) -> dict[str, Any]:
    source_sha256 = file_sha256(metadata_manifest)
    source_payload, sources = load_sanitized_manifest(metadata_manifest)
    if file_sha256(metadata_manifest) != source_sha256:
        raise RuntimeError("metadata manifest changed while it was being validated")
    predicted = validate_predicted_quota(sources)
    if output_directory.exists():
        raise FileExistsError(f"output already exists: {output_directory}")
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
        deno = _deno_executable()
        versions = {
            "yt_dlp": _run_recorded(
                ["yt-dlp", "--version"],
                runner=runner,
                cwd=None,
                monitored_directory=staging,
                records=commands,
            ),
            "ffmpeg": _run_recorded(
                ["ffmpeg", "-version"],
                runner=runner,
                cwd=None,
                monitored_directory=staging,
                records=commands,
            ).splitlines()[0],
            "ffprobe": _run_recorded(
                ["ffprobe", "-version"],
                runner=runner,
                cwd=None,
                monitored_directory=staging,
                records=commands,
            ).splitlines()[0],
            "deno": _run_recorded(
                [str(deno), "--version"],
                runner=runner,
                cwd=None,
                monitored_directory=staging,
                records=commands,
            ).splitlines()[0],
        }
        video_records: list[dict[str, Any]] = []
        for source in sources:
            source_started = time.monotonic()
            video_dir = staging / source.video_id
            video_dir.mkdir()
            full_path = video_dir / "transient_mobile_web_source.mp4"
            download_command = [
                "yt-dlp",
                "--no-playlist",
                "--force-ipv4",
                "--abort-on-error",
                "--no-continue",
                "--force-overwrites",
                "--no-progress",
                "--format",
                "18",
                "--impersonate",
                "Chrome-136:Macos-15",
                "--extractor-args",
                "youtube:player_client=mweb",
                "--js-runtimes",
                f"deno:{deno}",
                "--remote-components",
                "ejs:npm",
                "--output",
                str(full_path),
                source.url,
            ]
            _run_recorded(
                download_command,
                runner=runner,
                cwd=None,
                monitored_directory=staging,
                records=commands,
            )
            if not full_path.is_file() or full_path.stat().st_size <= 0:
                raise RuntimeError("transient mobile-web transfer produced no file")
            transient_source = _artifact(full_path, staging)
            section_records: list[dict[str, Any]] = []
            for section in sections_for(source):
                prefix = f"section_{section.label}"
                section_path = video_dir / f"{prefix}{full_path.suffix}"
                command = [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-ss",
                    f"{section.start_seconds:.3f}",
                    "-i",
                    str(full_path),
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
                _run_recorded(
                    command,
                    runner=runner,
                    cwd=None,
                    monitored_directory=staging,
                    records=commands,
                )
                probe = _probe_section(
                    section_path,
                    runner=runner,
                    root=staging,
                    records=commands,
                )
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
                    f"fps=1/{FRAME_INTERVAL_SECONDS:g}",
                    "-q:v",
                    "3",
                    str(frames_dir / "frame_%03d.jpg"),
                ]
                _run_recorded(
                    frame_command,
                    runner=runner,
                    cwd=None,
                    monitored_directory=staging,
                    records=commands,
                )
                frames = sorted(frames_dir.glob("frame_*.jpg"))
                if not frames:
                    raise RuntimeError(f"no audit frames extracted from {section_path}")
                section_records.append(
                    {
                        "label": section.label,
                        "fraction": section.fraction,
                        "requested_start_seconds": section.start_seconds,
                        "requested_end_seconds": section.end_seconds,
                        "media": _artifact(section_path, staging),
                        "probe": probe,
                        "frames": [_artifact(frame, staging) for frame in frames],
                    }
                )
            full_path.unlink()
            video_records.append(
                {
                    "id": source.video_id,
                    "url": source.url,
                    "duration_seconds": source.duration_seconds,
                    "transient_video_only_source": {
                        **transient_source,
                        "deleted_before_publication": True,
                        "reason": (
                            "remote FFmpeg section seeking returned CDN 403; "
                            "the available public mweb format was downloaded "
                            "transiently and audio was removed from every section"
                        ),
                        "format_id": "18",
                        "expected_transient_streams": ["video", "audio"],
                        "retained_section_streams": ["video"],
                        "transfer_and_cut_elapsed_seconds": (
                            time.monotonic() - source_started
                        ),
                    },
                    "sections": section_records,
                }
            )
        actual = _directory_bytes(staging)
        if actual > MAX_TOTAL_BYTES:
            raise RuntimeError("actual canary size exceeded 5 GiB before publication")
        manifest: dict[str, Any] = {
            "schema": OUTPUT_SCHEMA,
            "source_manifest": {
                "path": str(metadata_manifest.resolve()),
                "sha256": source_sha256,
                "schema": source_payload["schema"],
            },
            "permission_provenance": dict(source_payload["permission_provenance"]),
            "limits": {
                "maximum_videos": MAX_VIDEOS,
                "maximum_total_bytes": MAX_TOTAL_BYTES,
                "predicted_total_bytes_with_safety_factor": predicted,
                "actual_bytes_before_manifest": actual,
                "section_seconds": SECTION_SECONDS,
                "section_fractions": list(SECTION_FRACTIONS),
                "prediction_safety_factor": PREDICTION_SAFETY_FACTOR,
                "published_total_bytes": 0,
            },
            "coverage": {
                "requested_videos": len(sources),
                "completed_videos": len(video_records),
                "requested_sections": len(sources) * len(SECTION_FRACTIONS),
                "completed_sections": sum(
                    len(row["sections"]) for row in video_records
                ),
                "fractions": list(SECTION_FRACTIONS),
            },
            "performance": {
                "wall_seconds_before_manifest": time.monotonic() - run_started,
                "recorded_command_seconds": sum(
                    float(row["elapsed_seconds"]) for row in commands
                ),
                "peak_scratch_bytes": max(
                    (int(row["monitored_bytes_after"] or 0) for row in commands),
                    default=0,
                ),
            },
            "tools": versions,
            "commands": commands,
            "videos": video_records,
        }
        manifest_path = staging / "manifest.json"
        if file_sha256(metadata_manifest) != source_sha256:
            raise RuntimeError("metadata manifest changed before publication")
        final_bytes = 0
        for _ in range(4):
            atomic_write_json(manifest_path, manifest)
            measured = _directory_bytes(staging)
            if measured == final_bytes:
                break
            final_bytes = measured
            manifest["limits"]["published_total_bytes"] = final_bytes
        atomic_write_json(manifest_path, manifest)
        final_bytes = _directory_bytes(staging)
        if manifest["limits"]["published_total_bytes"] != final_bytes:
            raise RuntimeError("published byte count did not stabilize")
        if final_bytes > MAX_TOTAL_BYTES:
            raise RuntimeError("actual canary size exceeded 5 GiB after manifest")
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
    manifest = acquire_canary(
        metadata_manifest=args.metadata_manifest,
        output_directory=args.output_directory,
    )
    print(json.dumps(manifest, sort_keys=True))


if __name__ == "__main__":
    main()
