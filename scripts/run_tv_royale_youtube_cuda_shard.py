from __future__ import annotations

# mypy: disable-error-code="import-not-found,import-untyped", follow-imports=skip
import argparse
import hashlib
import json
import os
import platform
import resource
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, cast

import cv2
import numpy as np
import torch
import torchvision
import ultralytics

from clasher.rl.public_action_mask import PUBLIC_ACTION_MASK_CONTRACT_VERSION

PINS_SCHEMA = "clasher.youtube.cuda_extraction_pins.v2"
SMOKE_SCHEMA = "clasher.youtube.cuda_smoke_gate.v2"
COMPLETE_SCHEMA = "clasher.youtube.cuda_video_complete.v2"
TELEMETRY_SCHEMA = "clasher.youtube.cuda_stage_telemetry.v1"
MASK_CONTRACT = "label_independent_public_action_mask_v2"
MAX_SOURCE_BYTES = 500 * 1024**2


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def absolute_executable_path(path: Path) -> Path:
    """Make an executable path absolute without dereferencing venv symlinks."""

    return path if path.is_absolute() else Path.cwd() / path


def atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
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


def deterministic_shard(video_id: str, *, seed: int, shard_count: int) -> int:
    if shard_count <= 0:
        raise ValueError("shard_count must be positive")
    digest = hashlib.sha256(f"{seed}:{video_id}".encode()).digest()
    return int.from_bytes(digest[:8], "big") % shard_count


def selected_videos(
    metadata: dict[str, Any], *, seed: int, shard_count: int, shard_index: int
) -> list[dict[str, Any]]:
    if not 0 <= shard_index < shard_count:
        raise ValueError("shard_index must be within shard_count")
    videos = metadata.get("videos")
    if not isinstance(videos, list):
        raise TypeError("metadata manifest has no videos list")
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in videos:
        if not isinstance(row, dict):
            raise TypeError("metadata video row must be an object")
        video_id = str(row.get("id", ""))
        if not video_id or video_id in seen:
            raise ValueError(f"invalid or duplicate video id: {video_id!r}")
        seen.add(video_id)
        if row.get("availability") != "public" or row.get("access_class") != "public":
            continue
        if deterministic_shard(video_id, seed=seed, shard_count=shard_count) == shard_index:
            selected.append(row)
    return sorted(selected, key=lambda row: str(row["id"]))


def _version_base(value: str) -> str:
    return value.split("+", 1)[0]


def validate_pins(pins_path: Path, *, repository: Path) -> dict[str, Any]:
    pins = cast(
        dict[str, Any], json.loads(pins_path.read_text(encoding="utf-8"))
    )
    if pins.get("schema") != PINS_SCHEMA:
        raise ValueError(f"pins schema must be {PINS_SCHEMA}")
    contract = int(pins.get("mask_contract_version", -1))
    if contract != 2 or contract != PUBLIC_ACTION_MASK_CONTRACT_VERSION:
        raise ValueError("CUDA shards require public action-mask contract v2 exactly")
    runtime = pins.get("runtime", {})
    observed = {
        "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "torch": _version_base(torch.__version__),
        "torchvision": _version_base(torchvision.__version__),
        "numpy": np.__version__,
        "opencv": cv2.__version__,
        "ultralytics": ultralytics.__version__,
    }
    mismatches = {
        key: {"expected": runtime.get(key), "observed": value}
        for key, value in observed.items()
        if runtime.get(key) != value
    }
    if mismatches:
        raise ValueError(f"runtime dependency pins differ: {mismatches}")
    for role, item in pins.get("files", {}).items():
        path = (repository / str(item["path"])).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"pinned {role} is missing: {path}")
        actual = sha256(path)
        if actual != item.get("sha256"):
            raise ValueError(f"pinned {role} hash mismatch: {actual}")
    for role, item in pins.get("directories", {}).items():
        path = (repository / str(item["path"])).resolve()
        if not path.is_dir():
            raise FileNotFoundError(f"pinned {role} directory is missing: {path}")
        revision = item.get("git_revision")
        if revision:
            observed_revision = subprocess.run(
                ["git", "-C", str(path), "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            if observed_revision != revision:
                raise ValueError(f"pinned {role} git revision mismatch")
    return pins


def validate_clock_adapter(pins: dict[str, Any], executable: Path) -> None:
    adapter = pins.get("clock_adapter", {})
    expected = str(adapter.get("sha256", ""))
    if not expected or expected.startswith("PENDING"):
        raise RuntimeError("Linux clock adapter pin is pending; full smoke is blocked")
    if adapter.get("schema") != "clasher.youtube.clock_adapter.v1":
        raise ValueError("unsupported clock adapter schema")
    if not executable.is_file() or not os.access(executable, os.X_OK):
        raise FileNotFoundError(f"clock adapter is not executable: {executable}")
    if sha256(executable) != expected:
        raise ValueError("clock adapter executable hash differs from its pin")


def validate_external_tools(pins: dict[str, Any], *, dotnet: Path) -> dict[str, str]:
    expected = pins.get("external_tools", {})
    commands = {
        "dotnet": [str(dotnet), "--version"],
        "ffmpeg": ["ffmpeg", "-version"],
        "ffprobe": ["ffprobe", "-version"],
    }
    observed: dict[str, str] = {}
    for name, command in commands.items():
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        first_line = result.stdout.splitlines()[0]
        version = first_line if name == "dotnet" else first_line.split()[2]
        observed[name] = version
        if expected.get(name) != version:
            raise ValueError(
                f"external tool {name} differs: expected {expected.get(name)!r}, "
                f"observed {version!r}"
            )
    return observed


def validate_cuda(*, allowed_device_classes: tuple[str, ...]) -> dict[str, Any]:
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable")
    device_name = torch.cuda.get_device_name(0)
    matched_class = next(
        (value for value in allowed_device_classes if value in device_name.upper()), None
    )
    if matched_class is None:
        raise RuntimeError(
            f"CUDA device {device_name!r} is outside allowed classes "
            f"{allowed_device_classes}"
        )
    return {
        "device_name": device_name,
        "device_class": matched_class,
        "device_count": torch.cuda.device_count(),
        "torch_cuda": torch.version.cuda,
        "cudnn": torch.backends.cudnn.version(),
        "platform": platform.platform(),
    }


def normalize_max_rss_bytes(raw_value: float, *, system: str) -> int:
    value = int(raw_value)
    return value if system == "Darwin" else value * 1024


class StageRunner:
    def __init__(self, telemetry_path: Path) -> None:
        self.telemetry_path = telemetry_path
        self.rows: list[dict[str, Any]] = []

    def run(self, name: str, command: list[str], *, cwd: Path) -> str:
        before = resource.getrusage(resource.RUSAGE_CHILDREN)
        started = time.time()
        monotonic = time.perf_counter()
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        max_rss_bytes = normalize_max_rss_bytes(
            after.ru_maxrss, system=platform.system()
        )
        row = {
            "schema": TELEMETRY_SCHEMA,
            "stage": name,
            "started_unix": started,
            "wall_seconds": time.perf_counter() - monotonic,
            "user_cpu_seconds": after.ru_utime - before.ru_utime,
            "system_cpu_seconds": after.ru_stime - before.ru_stime,
            "child_max_rss_bytes": max_rss_bytes,
            "returncode": result.returncode,
            "argv": command,
            "stdout_tail": result.stdout[-4000:],
            "stderr_tail": result.stderr[-4000:],
        }
        self.rows.append(row)
        atomic_json(self.telemetry_path, {"schema": TELEMETRY_SCHEMA, "stages": self.rows})
        if result.returncode != 0:
            raise RuntimeError(
                f"stage {name} failed ({result.returncode}): {result.stderr[-2000:]}"
            )
        return result.stdout


def _pinned_path(pins: dict[str, Any], repository: Path, role: str) -> Path:
    item = pins.get("files", {}).get(role) or pins.get("directories", {}).get(role)
    if not isinstance(item, dict):
        raise KeyError(f"pins have no path role {role!r}")
    return (repository / str(item["path"])).resolve()


def _valid_complete(path: Path) -> bool:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        manifest = Path(payload["manifest"])
        report = Path(payload["verifier_report"])
        if not manifest.is_absolute():
            manifest = path.parent / manifest
        if not report.is_absolute():
            report = path.parent / report
        return bool(
            payload.get("schema") == COMPLETE_SCHEMA
            and payload.get("mask_contract_version") == 2
            and payload.get("mask_contract") == MASK_CONTRACT
            and manifest.is_file()
            and report.is_file()
            and sha256(manifest) == payload.get("manifest_sha256")
            and sha256(report) == payload.get("verifier_report_sha256")
            and json.loads(report.read_text()).get("failed_gates") == []
        )
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
        return False


def _verify_v2_manifest(manifest_path: Path) -> dict[str, Any]:
    manifest = cast(
        dict[str, Any], json.loads(manifest_path.read_text(encoding="utf-8"))
    )
    public_mask = manifest.get("public_mask_v3", {})
    if (
        manifest.get("schema") != "clasher.youtube.fullmatch.extraction_manifest.v3"
        or public_mask.get("contract_version") != 2
        or public_mask.get("contract") != MASK_CONTRACT
    ):
        raise ValueError("published shard is not public action-mask contract v2")
    return manifest


def _copy_acquisition_without_video(source: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=False)
    for path in source.iterdir():
        if path.name == "source.webm":
            continue
        if path.is_file():
            shutil.copy2(path, destination / path.name)


def _rebase_publication_manifest(manifest_path: Path) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    artifacts = manifest["artifacts"]
    for key in ("neutral_sequence", "offline_play_events", "offline_actor_targets"):
        item = artifacts.get(key)
        if isinstance(item, dict) and item.get("path"):
            item["path"] = Path(item["path"]).name
    for item in artifacts.get("actor_trajectories", []):
        item["path"] = Path(item["path"]).name
    manifest["source"]["acquisition_manifest"] = "acquisition/manifest.json"
    atomic_json(manifest_path, manifest)


def process_video(
    *,
    video: dict[str, Any],
    repository: Path,
    pins: dict[str, Any],
    pins_path: Path,
    scratch_root: Path,
    output_root: Path,
    clock_adapter: Path,
    python: Path,
    dotnet: Path,
    batch_size: int,
    card_preprocess_workers: int,
    benchmark_repetitions: int,
    cuda_info: dict[str, Any],
) -> dict[str, Any]:
    video_id = str(video["id"])
    final_dir = output_root / video_id
    complete_path = final_dir / "COMPLETE.json"
    if complete_path.is_file():
        if not _valid_complete(complete_path):
            raise RuntimeError(f"existing completion marker is invalid: {complete_path}")
        return cast(
            dict[str, Any], json.loads(complete_path.read_text(encoding="utf-8"))
        )
    final_dir.mkdir(parents=True, exist_ok=True)
    job_marker = final_dir / "JOB.json"
    expected_job = {
        "schema": "clasher.youtube.cuda_video_job.v2",
        "video_id": video_id,
        "pins_sha256": sha256(pins_path),
        "mask_contract_version": 2,
    }
    if job_marker.is_file():
        if json.loads(job_marker.read_text(encoding="utf-8")) != expected_job:
            raise RuntimeError(f"resume job marker differs: {job_marker}")
    elif any(final_dir.iterdir()):
        raise RuntimeError(f"refusing unowned nonempty output directory: {final_dir}")
    else:
        atomic_json(job_marker, expected_job)
    job_scratch = scratch_root / video_id
    job_scratch.mkdir(parents=True, exist_ok=True)
    scratch_marker = job_scratch / "SCRATCH_JOB.json"
    if scratch_marker.is_file():
        if json.loads(scratch_marker.read_text(encoding="utf-8")) != expected_job:
            raise RuntimeError(f"resume scratch marker differs: {scratch_marker}")
    elif any(job_scratch.iterdir()):
        raise RuntimeError(f"refusing unowned nonempty scratch: {job_scratch}")
    else:
        atomic_json(scratch_marker, expected_job)
    telemetry = final_dir / "stage_telemetry.json"
    runner = StageRunner(telemetry)
    video_json = job_scratch / "video.json"
    atomic_json(video_json, video)
    acquisition_dir = job_scratch / "acquisition"
    if not (acquisition_dir / "manifest.json").is_file():
        runner.run(
            "bounded_download_and_index",
            [
                str(python),
                str(_pinned_path(pins, repository, "acquisition_script")),
                "--video-json",
                str(video_json),
                "--output-dir",
                str(acquisition_dir),
                "--dotnet",
                str(dotnet),
                "--downloader-project",
                str(_pinned_path(pins, repository, "downloader_project")),
                "--sample-hz",
                "10",
            ],
            cwd=repository,
        )
    acquisition_manifest = acquisition_dir / "manifest.json"
    acquisition = json.loads(acquisition_manifest.read_text(encoding="utf-8"))
    source = acquisition_dir / "source.webm"
    if (
        not source.is_file()
        or source.stat().st_size > MAX_SOURCE_BYTES
        or sha256(source) != acquisition["source_media"]["sha256"]
    ):
        raise RuntimeError("resumed acquisition source failed size/hash validation")

    benchmark = final_dir / "detector_benchmark.json"
    if not benchmark.is_file():
        runner.run(
            "exact_cuda_detector_benchmark",
            [
                str(python),
                str(_pinned_path(pins, repository, "detector_benchmark")),
                "--input-video",
                str(source),
                "--source-manifest",
                str(acquisition_manifest),
                "--detector-weight",
                str(_pinned_path(pins, repository, "detector_weight_1")),
                "--detector-weight",
                str(_pinned_path(pins, repository, "detector_weight_2")),
                "--katacr-root",
                str(_pinned_path(pins, repository, "katacr_root")),
                "--device",
                "cuda",
                "--batch-size",
                str(batch_size),
                "--repetitions",
                str(benchmark_repetitions),
                "--output",
                str(benchmark),
            ],
            cwd=repository,
        )
    benchmark_payload = json.loads(benchmark.read_text(encoding="utf-8"))
    if (
        benchmark_payload.get("frames_per_repetition")
        != acquisition["decode"]["sample_count"]
        or benchmark_payload.get("stable_repetition_digest") is not True
    ):
        raise RuntimeError("exact CUDA detector benchmark did not pass stability gate")

    raw_dir = job_scratch / "semantic_raw"
    if not (raw_dir / "manifest.json").is_file():
        runner.run(
            "cuda_semantic_extraction_clock_deferred",
            [
                str(python),
                str(_pinned_path(pins, repository, "extractor")),
                "--input-video",
                str(source),
                "--source-manifest",
                str(acquisition_manifest),
                "--output-dir",
                str(raw_dir),
                "--vocabulary-manifest",
                str(_pinned_path(pins, repository, "vocabulary")),
                "--template-root",
                str(_pinned_path(pins, repository, "hud_template_root")),
                "--card-embedding-weight",
                str(_pinned_path(pins, repository, "mobilenet_weights")),
                "--katacr-root",
                str(_pinned_path(pins, repository, "katacr_root")),
                "--detector-weight",
                str(_pinned_path(pins, repository, "detector_weight_1")),
                "--detector-weight",
                str(_pinned_path(pins, repository, "detector_weight_2")),
                "--device",
                "cuda",
                "--batch-size",
                str(batch_size),
                "--sample-hz",
                "10",
                "--actor-hz",
                "5",
                "--clock-provider-mode",
                "deferred",
                "--card-preprocess-backend",
                "pil-batched",
                "--card-preprocess-workers",
                str(card_preprocess_workers),
                "--raw-actor-mode",
                "deferred",
            ],
            cwd=repository,
        )

    clock_adapter_dir = job_scratch / "clock_adapter"
    clock_adapter_dir.mkdir(parents=True, exist_ok=True)
    clock_anchors = clock_adapter_dir / "clock_anchors.jsonl"
    if not clock_anchors.is_file():
        runner.run(
            "linux_clock_adapter",
            [
                str(clock_adapter),
                "--source-video",
                str(source),
                "--source-manifest",
                str(acquisition_manifest),
                "--output-jsonl",
                str(clock_anchors),
                "--sample-hz",
                "10",
                "--anchor-stride-frames",
                "5",
            ],
            cwd=repository,
        )
    if not clock_anchors.is_file():
        raise RuntimeError("clock adapter did not publish clock_anchors.jsonl")

    clocked_dir = job_scratch / "semantic_clocked"
    clocked_manifest = clocked_dir / "manifest.json"
    if not clocked_manifest.is_file():
        runner.run(
            "apply_linux_clock_anchors",
            [
                str(python),
                str(_pinned_path(pins, repository, "clock_merger")),
                "--input-manifest",
                str(raw_dir / "manifest.json"),
                "--anchors",
                str(clock_anchors),
                "--output-dir",
                str(clocked_dir),
                "--provider",
                str(clock_adapter),
                "--provider-sha256",
                pins["clock_adapter"]["sha256"],
            ],
            cwd=repository,
        )
    if not clocked_manifest.is_file():
        raise RuntimeError("clock merger did not publish semantic_clocked/manifest.json")

    masks_manifest = clocked_dir / "manifest_masks_v3.json"
    if not masks_manifest.is_file():
        runner.run(
            "public_mask_contract_v2",
            [
                str(python),
                str(_pinned_path(pins, repository, "mask_builder")),
                "--manifest",
                str(clocked_manifest),
                "--vocabulary",
                str(_pinned_path(pins, repository, "vocabulary")),
                "--output-manifest",
                str(masks_manifest),
                "--actor-storage",
                "compact",
            ],
            cwd=repository,
        )
    _verify_v2_manifest(masks_manifest)

    publication = final_dir / "publication"
    publication_partial = final_dir / ".publication.partial"
    if publication_partial.exists():
        shutil.rmtree(publication_partial)
    if not publication.exists():
        shutil.copytree(clocked_dir, publication_partial)
        _copy_acquisition_without_video(
            acquisition_dir, publication_partial / "acquisition"
        )
        os.replace(publication_partial, publication)
    published_manifest = publication / masks_manifest.name
    _rebase_publication_manifest(published_manifest)
    published_report = publication / "contract_report.json"
    runner.run(
        "independent_contract_verifier",
        [
            str(python),
            str(_pinned_path(pins, repository, "verifier")),
            "--extraction-dir",
            str(publication),
            "--source-manifest",
            str(publication / "acquisition" / "manifest.json"),
            "--extraction-manifest",
            str(published_manifest),
            "--report-out",
            str(published_report),
        ],
        cwd=repository,
    )
    report = json.loads(published_report.read_text(encoding="utf-8"))
    if report.get("failed_gates") != [] or report.get("status") != "passed":
        raise RuntimeError("semantic contract verifier did not pass")
    completion = {
        "schema": COMPLETE_SCHEMA,
        "video_id": video_id,
        "shard_contract": "deterministic_sha256_seed_modulo_v1",
        "pins_sha256": sha256(pins_path),
        "mask_contract": MASK_CONTRACT,
        "mask_contract_version": 2,
        "manifest": str(Path("publication") / published_manifest.name),
        "manifest_sha256": sha256(published_manifest),
        "verifier_report": str(Path("publication") / published_report.name),
        "verifier_report_sha256": sha256(published_report),
        "detector_benchmark": benchmark.name,
        "detector_benchmark_sha256": sha256(benchmark),
        "telemetry": telemetry.name,
        "telemetry_sha256": sha256(telemetry),
        "cuda": cuda_info,
        "throughput_claimed": False,
        "throughput_note": "measurement recorded; no H100 rate claimed before this run",
        "status": "complete",
    }
    atomic_json(complete_path, completion)
    shutil.rmtree(job_scratch)
    return completion


def validate_smoke_gate(
    path: Path, *, pins_path: Path, expected_video_id: str | None = None
) -> dict[str, Any]:
    payload = cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
    if (
        payload.get("schema") != SMOKE_SCHEMA
        or payload.get("status") != "passed"
        or payload.get("mask_contract_version") != 2
        or payload.get("pins_sha256") != sha256(pins_path)
    ):
        raise ValueError("smoke gate is stale or did not pass contract v2")
    if expected_video_id is not None and payload.get("video_id") != expected_video_id:
        raise ValueError("smoke gate video differs from requested smoke video")
    completion_path = Path(str(payload.get("completion", "")))
    if (
        not completion_path.is_file()
        or sha256(completion_path) != payload.get("completion_sha256")
        or not _valid_complete(completion_path)
    ):
        raise ValueError("smoke gate completion marker is missing or invalid")
    return payload


def validate_bulk_gate(pins: dict[str, Any]) -> None:
    gate = pins.get("bulk_gate", {})
    if (
        gate.get("replay_disjoint_clock_validation") != "passed"
        or not isinstance(gate.get("report_sha256"), str)
        or len(gate["report_sha256"]) != 64
    ):
        raise RuntimeError(
            "bulk run is blocked pending replay-disjoint portable-clock validation"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Deterministic resumable CUDA YouTube extraction shard launcher"
    )
    parser.add_argument("--metadata-manifest", type=Path, required=True)
    parser.add_argument("--pins", type=Path, required=True)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--scratch-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--clock-adapter", type=Path, required=True)
    parser.add_argument("--dotnet", type=Path, required=True)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--seed", type=int, default=1_064_201)
    parser.add_argument("--shard-count", type=int, required=True)
    parser.add_argument("--shard-index", type=int, required=True)
    parser.add_argument("--mode", choices=("smoke", "run"), required=True)
    parser.add_argument(
        "--smoke-video-id",
        help="required in smoke mode so the exact canary is selected explicitly",
    )
    parser.add_argument("--smoke-gate", type=Path)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--card-preprocess-workers", type=int, default=8)
    parser.add_argument("--benchmark-repetitions", type=int, default=3)
    parser.add_argument("--max-download-queue", type=int, default=1)
    parser.add_argument("--minimum-scratch-free-gib", type=float, default=20.0)
    parser.add_argument(
        "--allowed-device-class",
        action="append",
        choices=("H100", "H200", "L40S"),
        help=(
            "repeat to allow multiple classes; defaults to H100 and H200. "
            "L40S must be opted into explicitly."
        ),
    )
    args = parser.parse_args()

    if args.max_download_queue != 1:
        raise ValueError("v1 launcher intentionally bounds the downloader queue to one")
    if (
        args.batch_size <= 0
        or args.card_preprocess_workers <= 0
        or args.benchmark_repetitions < 2
    ):
        raise ValueError("batch size must be positive and benchmark repetitions >= 2")
    repository = args.repository.resolve()
    scratch_root = args.scratch_root.resolve()
    output_root = args.output_root.resolve()
    scratch_root.mkdir(parents=True, exist_ok=True)
    output_root.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(scratch_root).free
    required = int(args.minimum_scratch_free_gib * 1024**3)
    if free < required:
        raise RuntimeError(f"scratch has {free} bytes free; requires {required}")

    pins_path = args.pins.resolve()
    pins = validate_pins(pins_path, repository=repository)
    metadata_path = args.metadata_manifest.resolve()
    if sha256(metadata_path) != pins.get("metadata_manifest_sha256"):
        raise ValueError("metadata manifest hash differs from pins")
    validate_clock_adapter(pins, args.clock_adapter.resolve())
    external_tools = validate_external_tools(pins, dotnet=args.dotnet.resolve())
    allowed_device_classes = tuple(args.allowed_device_class or ("H100", "H200"))
    cuda_info = validate_cuda(allowed_device_classes=allowed_device_classes)
    cuda_info["external_tools"] = external_tools
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    videos = selected_videos(
        metadata,
        seed=args.seed,
        shard_count=args.shard_count,
        shard_index=args.shard_index,
    )
    if not videos:
        raise ValueError("selected shard has no public videos")

    shard_root = output_root / f"shard-{args.shard_index:05d}-of-{args.shard_count:05d}"
    shard_scratch = scratch_root / f"shard-{args.shard_index:05d}-of-{args.shard_count:05d}"
    shard_root.mkdir(parents=True, exist_ok=True)
    shard_scratch.mkdir(parents=True, exist_ok=True)
    if args.mode == "smoke":
        if not args.smoke_video_id:
            raise ValueError("smoke mode requires --smoke-video-id")
        videos = [row for row in videos if row["id"] == args.smoke_video_id]
        if len(videos) != 1:
            raise ValueError("smoke video is absent from the selected deterministic shard")
    else:
        if args.smoke_gate is None:
            raise ValueError("run mode requires --smoke-gate")
        validate_smoke_gate(args.smoke_gate.resolve(), pins_path=pins_path)
        validate_bulk_gate(pins)

    completions = []
    for video in videos:
        completions.append(
            process_video(
                video=video,
                repository=repository,
                pins=pins,
                pins_path=pins_path,
                scratch_root=shard_scratch,
                output_root=shard_root,
                clock_adapter=args.clock_adapter.resolve(),
                # Do not resolve the interpreter path: resolving a virtualenv
                # symlink silently replaces it with the base interpreter and
                # drops the environment's site-packages.
                python=absolute_executable_path(args.python),
                dotnet=args.dotnet.resolve(),
                batch_size=args.batch_size,
                card_preprocess_workers=args.card_preprocess_workers,
                benchmark_repetitions=args.benchmark_repetitions,
                cuda_info=cuda_info,
            )
        )

    shard_manifest = {
        "schema": "clasher.youtube.cuda_shard_result.v2",
        "shard_index": args.shard_index,
        "shard_count": args.shard_count,
        "seed": args.seed,
        "mode": args.mode,
        "pins_sha256": sha256(pins_path),
        "mask_contract_version": 2,
        "videos": completions,
        "throughput_claimed": False,
    }
    atomic_json(shard_root / "shard_manifest.json", shard_manifest)
    if args.mode == "smoke":
        completion = completions[0]
        smoke = {
            "schema": SMOKE_SCHEMA,
            "video_id": completion["video_id"],
            "pins_sha256": sha256(pins_path),
            "mask_contract_version": 2,
            "completion": str(
                shard_root / completion["video_id"] / "COMPLETE.json"
            ),
            "completion_sha256": sha256(
                shard_root / completion["video_id"] / "COMPLETE.json"
            ),
            "status": "passed",
            "scale_requires_explicit_run_mode": True,
            "throughput_claimed": False,
        }
        atomic_json(shard_root / "SMOKE_GATE.json", smoke)
    print(json.dumps(shard_manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
