from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, cast
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

MAX_SOURCE_BYTES = 500 * 1024**2
DIRECT_CHUNK_BYTES = 10 * 1024**2
SCHEMA = "clasher.tv_royale.youtube_fullmatch_acquisition.v1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def run(command: list[str]) -> tuple[str, float]:
    started = time.perf_counter()
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    elapsed = time.perf_counter() - started
    if result.returncode != 0:
        raise RuntimeError(
            f"command failed ({result.returncode}): {command[0]}: "
            f"{result.stderr[-2000:]}"
        )
    return result.stdout, elapsed


def select_yt_dlp_format(metadata: dict[str, Any], format_id: str) -> dict[str, Any]:
    formats = metadata.get("formats")
    if not isinstance(formats, list):
        raise TypeError("yt-dlp metadata has no formats list")
    matches = [row for row in formats if str(row.get("format_id")) == format_id]
    if len(matches) != 1:
        raise ValueError(f"yt-dlp format {format_id!r} is not unique")
    selected = matches[0]
    if selected.get("acodec") != "none" or selected.get("vcodec") in {None, "none"}:
        raise ValueError("selected yt-dlp format must be video-only")
    declared = selected.get("filesize")
    if not isinstance(declared, int) or not 0 < declared <= MAX_SOURCE_BYTES:
        raise ValueError("selected yt-dlp format has no bounded exact filesize")
    return cast(dict[str, Any], selected)


def download_bounded_public_stream(selected: dict[str, Any], source: Path) -> float:
    url = str(selected.get("url", ""))
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or not parsed.hostname.endswith(".googlevideo.com")
    ):
        raise ValueError("selected media URL is not an HTTPS googlevideo host")
    declared = int(selected["filesize"])
    headers = selected.get("http_headers", {})
    if not isinstance(headers, dict):
        raise TypeError("selected format HTTP headers are not an object")
    request = Request(
        url, headers={str(key): str(value) for key, value in headers.items()}
    )
    started = time.perf_counter()
    try:
        response = urlopen(request, timeout=60)
    except HTTPError as error:
        raise RuntimeError(
            f"bounded direct media request failed with HTTP status {error.code}"
        ) from None
    with response:
        final = urlparse(response.geturl())
        if (
            final.scheme != "https"
            or not final.hostname
            or not final.hostname.endswith(".googlevideo.com")
        ):
            raise ValueError("media request redirected outside googlevideo HTTPS")
        content_length = response.headers.get("Content-Length")
        if content_length is not None and int(content_length) != declared:
            raise ValueError("media response length differs from declared stream size")
        written = 0
        with source.open("xb") as output:
            while chunk := response.read(1024 * 1024):
                written += len(chunk)
                if written > declared or written > MAX_SOURCE_BYTES:
                    raise ValueError("media response exceeded its declared bound")
                output.write(chunk)
        if written != declared:
            raise ValueError("media response ended before its declared bound")
    return time.perf_counter() - started


def download_bounded_public_stream_with_yt_dlp(
    selected: dict[str, Any],
    source: Path,
    yt_dlp: Path,
    impersonate: str | None = None,
) -> float:
    """Download one already-resolved public stream without re-extraction.

    Googlevideo throttles a single long-lived response on some cloud egress.
    yt-dlp's bounded 10 MiB range chunks preserve the exact declared stream but
    avoid that transport bottleneck.  The signed media URL is passed directly,
    so this does not perform a second YouTube watch-page/player extraction.
    """

    url = str(selected.get("url", ""))
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or not parsed.hostname.endswith(".googlevideo.com")
    ):
        raise ValueError("selected media URL is not an HTTPS googlevideo host")
    declared = selected.get("filesize")
    if not isinstance(declared, int) or not 0 < declared <= MAX_SOURCE_BYTES:
        raise ValueError("selected media stream has no bounded exact filesize")
    headers = selected.get("http_headers", {})
    if not isinstance(headers, dict):
        raise TypeError("selected format HTTP headers are not an object")
    command = [
        str(yt_dlp),
        "--http-chunk-size",
        str(DIRECT_CHUNK_BYTES),
        "--no-part",
        "--no-mtime",
        "--no-playlist",
        "--no-warnings",
        "--output",
        str(source),
    ]
    if impersonate is not None:
        command.extend(("--impersonate", impersonate))
    for key, value in sorted(headers.items()):
        command.extend(("--add-header", f"{key}:{value}"))
    command.append(url)
    _, elapsed = run(command)
    if source.stat().st_size != declared:
        raise ValueError("chunked direct download differs from declared stream size")
    return elapsed


def download_source(
    *,
    video: dict[str, Any],
    source: Path,
    backend: str,
    dotnet: Path | None,
    downloader_project: Path | None,
    yt_dlp: Path | None,
    yt_dlp_format: str | None,
    yt_dlp_impersonate: str | None = None,
) -> tuple[dict[str, Any], float, str]:
    if backend == "youtube-explode":
        if dotnet is None or downloader_project is None:
            raise ValueError("youtube-explode requires dotnet and downloader project")
        stdout, elapsed = run(
            [
                str(dotnet),
                "run",
                "--project",
                str(downloader_project),
                "--configuration",
                "Release",
                "--",
                str(video["url"]),
                str(source),
            ]
        )
        return json.loads(stdout), elapsed, "youtube-explode-public-video-only-linux-v1"
    if backend not in {"yt-dlp", "yt-dlp-direct"}:
        raise ValueError(f"unsupported acquisition backend: {backend}")
    if yt_dlp is None or not yt_dlp_format:
        raise ValueError("yt-dlp backend requires executable and exact format ID")
    version, _ = run([str(yt_dlp), "--version"])
    # The batch driver has just resolved and atomically stored the complete
    # metadata object.  Re-extracting the same watch page here doubled YouTube
    # extractor traffic and exhausted otherwise healthy cloud IPs.  The direct
    # backend consumes that fresh, bounded format URL exactly once.
    if backend == "yt-dlp-direct" and isinstance(video.get("formats"), list):
        selected = select_yt_dlp_format(video, yt_dlp_format)
    else:
        metadata_command = [
            str(yt_dlp),
            "--no-playlist",
            "--no-warnings",
            "--force-ipv4",
            "--dump-single-json",
            "--skip-download",
        ]
        if yt_dlp_impersonate is not None:
            metadata_command.extend(("--impersonate", yt_dlp_impersonate))
        metadata_command.append(str(video["url"]))
        metadata_stdout, _ = run(metadata_command)
        selected = select_yt_dlp_format(json.loads(metadata_stdout), yt_dlp_format)
    if backend == "yt-dlp-direct":
        elapsed = download_bounded_public_stream_with_yt_dlp(
            selected, source, yt_dlp, yt_dlp_impersonate
        )
        backend_name = "yt-dlp-resolved-bounded-chunked-https-v2"
    else:
        download_command = [
            str(yt_dlp),
            "--force-ipv4",
            "--no-playlist",
            "--no-warnings",
            "--no-part",
            "--no-mtime",
            "--format",
            yt_dlp_format,
            "--output",
            str(source),
        ]
        if yt_dlp_impersonate is not None:
            download_command.extend(("--impersonate", yt_dlp_impersonate))
        download_command.append(str(video["url"]))
        _, elapsed = run(download_command)
        backend_name = (
            "yt-dlp-public-exact-format-video-only-impersonated-v2"
            if yt_dlp_impersonate is not None
            else "yt-dlp-public-exact-format-video-only-v1"
        )
    declared = int(selected["filesize"])
    return (
        {
            "schema": "clasher.yt_dlp_public_stream.v1",
            "tool_version": version.strip(),
            "impersonate": yt_dlp_impersonate,
            "sourceUrl": str(video["url"]),
            "stream": {
                "formatId": yt_dlp_format,
                "container": str(selected["ext"]),
                "width": int(selected["width"]),
                "height": int(selected["height"]),
                "framesPerSecond": round(float(selected["fps"])),
                "bitrateBitsPerSecond": round(float(selected["tbr"]) * 1_000),
                "declaredBytes": declared,
                "actualBytes": source.stat().st_size,
                "videoCodec": str(selected["vcodec"]),
            },
        },
        elapsed,
        backend_name,
    )


def parse_framehash(path: Path) -> dict[str, Any]:
    rows: list[tuple[int, int, str]] = []
    time_base: str | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#tb "):
            parts = line.split()
            if len(parts) >= 3 and parts[1] == "0:":
                time_base = parts[2]
            continue
        if not line or line.startswith("#"):
            continue
        parts = [value.strip() for value in line.split(",")]
        if len(parts) < 6:
            raise ValueError(f"malformed framehash row: {line}")
        rows.append((int(parts[0]), int(parts[2]), parts[-1]))
    if not rows or time_base is None:
        raise ValueError("framehash has no stream time base or data rows")
    pts = [row[1] for row in rows]
    if [row[0] for row in rows] != [0] * len(rows):
        raise ValueError("framehash contains an unexpected stream")
    if pts != list(range(len(rows))):
        raise ValueError("framehash output PTS are not contiguous from zero")
    return {
        "sample_count": len(rows),
        "first_output_pts": pts[0],
        "last_output_pts": pts[-1],
        "output_time_base": time_base,
        "all_output_pts_contiguous": True,
        "all_frame_hashes_unique": len({row[2] for row in rows}) == len(rows),
    }


def acquire(
    *,
    video: dict[str, Any],
    output_dir: Path,
    backend: str,
    dotnet: Path | None,
    downloader_project: Path | None,
    yt_dlp: Path | None,
    yt_dlp_format: str | None,
    yt_dlp_impersonate: str | None,
    sample_hz: int,
) -> dict[str, Any]:
    if output_dir.exists():
        raise FileExistsError(output_dir)
    if video.get("availability") != "public" or video.get("access_class") != "public":
        raise ValueError("full-match acquisition accepts only explicitly public videos")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(
            prefix=f".{output_dir.name}.", suffix=".partial", dir=output_dir.parent
        )
    )
    try:
        source = staging / "source.webm"
        download, download_seconds, acquisition_backend = download_source(
            video=video,
            source=source,
            backend=backend,
            dotnet=dotnet,
            downloader_project=downloader_project,
            yt_dlp=yt_dlp,
            yt_dlp_format=yt_dlp_format,
            yt_dlp_impersonate=yt_dlp_impersonate,
        )
        actual_bytes = source.stat().st_size
        if not 0 < actual_bytes <= MAX_SOURCE_BYTES:
            raise ValueError("downloaded source violated the 500 MiB bound")
        declared_bytes = int(download["stream"]["declaredBytes"])
        if declared_bytes != actual_bytes:
            raise ValueError("downloaded source size differs from declared stream size")

        probe_stdout, _ = run(
            [
                "ffprobe",
                "-v",
                "error",
                "-count_packets",
                "-show_entries",
                (
                    "format=format_name,start_time,duration,size,bit_rate:"
                    "stream=codec_name,profile,codec_type,width,height,r_frame_rate,"
                    "avg_frame_rate,time_base,start_pts,start_time,nb_read_packets"
                ),
                "-of",
                "json",
                str(source),
            ]
        )
        probe = json.loads(probe_stdout)
        streams = probe.get("streams", [])
        if len(streams) != 1 or streams[0].get("codec_type") != "video":
            raise ValueError("source must contain exactly one video stream")
        stream = streams[0]
        frame_index = staging / f"frame_index_{sample_hz}fps.framehash"
        _, decode_seconds = run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(source),
                "-map",
                "0:v:0",
                "-an",
                "-vf",
                f"fps={sample_hz}",
                "-fps_mode",
                "passthrough",
                "-f",
                "framehash",
                "-hash",
                "sha256",
                str(frame_index),
            ]
        )
        framehash = parse_framehash(frame_index)
        duration = float(probe["format"]["duration"])
        manifest = {
            "schema": SCHEMA,
            "source": {
                "video_id": video["id"],
                "watch_url": video["url"],
                "availability": "public",
                "access_class": "public",
                "upload_date": video.get("upload_date"),
            },
            "permission_provenance": {
                "basis": "user_attested_channel_owner_approval",
                "attested_on": "2026-08-17",
                "public_cc_license_claimed": False,
                "cookies_used": False,
                "account_used": False,
            },
            "limits": {
                "maximum_source_bytes": MAX_SOURCE_BYTES,
                "declared_bytes": declared_bytes,
                "actual_bytes": actual_bytes,
            },
            "acquisition": {
                "backend": acquisition_backend,
                "tool_version": download.get("tool_version"),
                "performance": {
                    "wall_seconds": download_seconds,
                    "media_payload_megabytes_per_second": actual_bytes
                    / download_seconds
                    / 1e6,
                },
            },
            "source_media": {
                "path": str(output_dir / "source.webm"),
                "bytes": actual_bytes,
                "sha256": sha256(source),
                "container": download["stream"]["container"],
                "video_only": True,
                "codec": stream["codec_name"],
                "codec_profile": stream.get("profile"),
                "width": int(stream["width"]),
                "height": int(stream["height"]),
                "nominal_frames_per_second": int(download["stream"]["framesPerSecond"]),
                "average_frame_rate": stream["avg_frame_rate"],
                "real_frame_rate": stream["r_frame_rate"],
                "source_time_base": stream["time_base"],
                "start_pts": int(stream.get("start_pts", 0)),
                "start_time_seconds": float(stream.get("start_time", 0.0)),
                "probed_duration_seconds": duration,
                "video_packet_count": int(stream["nb_read_packets"]),
                "full_decode_passed": True,
            },
            "decode": {
                "purpose": "current-frame semantic extraction source cadence",
                "cadence_hz": sample_hz,
                **framehash,
                "first_target_source_time_seconds": 0.0,
                "last_target_source_time_seconds": (framehash["sample_count"] - 1)
                / sample_hz,
                "remaining_source_tail_seconds": duration
                - (framehash["sample_count"] - 1) / sample_hz,
                "index": {
                    "path": str(output_dir / frame_index.name),
                    "schema": "FFmpeg framehash v2",
                    "bytes": frame_index.stat().st_size,
                    "sha256": sha256(frame_index),
                },
                "performance": {
                    "wall_seconds": decode_seconds,
                    "sampled_output_frames_per_second": framehash["sample_count"]
                    / decode_seconds,
                    "source_realtime_factor": duration / decode_seconds,
                },
            },
            "status": "complete",
        }
        manifest_path = staging / "manifest.json"
        atomic_json(manifest_path, manifest)
        os.replace(staging, output_dir)
        return manifest
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video-json", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--backend",
        choices=("youtube-explode", "yt-dlp", "yt-dlp-direct"),
        default="youtube-explode",
    )
    parser.add_argument("--dotnet", type=Path)
    parser.add_argument("--downloader-project", type=Path)
    parser.add_argument("--yt-dlp", type=Path)
    parser.add_argument("--yt-dlp-format")
    parser.add_argument("--yt-dlp-impersonate")
    parser.add_argument("--sample-hz", type=int, default=10)
    args = parser.parse_args()
    if args.sample_hz <= 0:
        raise ValueError("sample-hz must be positive")
    video = json.loads(args.video_json.read_text(encoding="utf-8"))
    manifest = acquire(
        video=video,
        output_dir=args.output_dir.resolve(),
        backend=args.backend,
        dotnet=None if args.dotnet is None else args.dotnet.resolve(),
        downloader_project=(
            None
            if args.downloader_project is None
            else args.downloader_project.resolve()
        ),
        yt_dlp=None if args.yt_dlp is None else args.yt_dlp.resolve(),
        yt_dlp_format=args.yt_dlp_format,
        yt_dlp_impersonate=args.yt_dlp_impersonate,
        sample_hz=args.sample_hz,
    )
    print(
        json.dumps(
            {
                "manifest": str(args.output_dir / "manifest.json"),
                "status": manifest["status"],
            }
        )
    )


if __name__ == "__main__":
    main()
