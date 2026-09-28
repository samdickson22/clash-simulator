from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest
import torch
import torchvision
import ultralytics

from scripts.run_tv_royale_youtube_cuda_shard import (
    PINS_SCHEMA,
    _verify_v2_manifest,
    absolute_executable_path,
    deterministic_shard,
    normalize_max_rss_bytes,
    selected_videos,
    validate_bulk_gate,
    validate_clock_adapter,
    validate_cuda,
    validate_pins,
    validate_smoke_gate,
)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _pins(file: Path) -> dict[str, object]:
    return {
        "schema": PINS_SCHEMA,
        "mask_contract_version": 2,
        "runtime": {
            "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "torch": torch.__version__.split("+", 1)[0],
            "torchvision": torchvision.__version__.split("+", 1)[0],
            "numpy": np.__version__,
            "opencv": cv2.__version__,
            "ultralytics": ultralytics.__version__,
        },
        "files": {"fixture": {"path": file.name, "sha256": _digest(file)}},
        "directories": {},
    }


def test_sharding_is_deterministic_disjoint_and_sorted() -> None:
    metadata = {
        "videos": [
            {"id": "b", "availability": "public", "access_class": "public"},
            {"id": "a", "availability": "public", "access_class": "public"},
            {"id": "private", "availability": "private", "access_class": "private"},
        ]
    }
    assigned = []
    for shard in range(3):
        rows = selected_videos(metadata, seed=17, shard_count=3, shard_index=shard)
        assert [row["id"] for row in rows] == sorted(row["id"] for row in rows)
        assigned.extend(row["id"] for row in rows)
    assert sorted(assigned) == ["a", "b"]
    assert deterministic_shard("a", seed=17, shard_count=3) == deterministic_shard(
        "a", seed=17, shard_count=3
    )


def test_python_executable_path_preserves_virtualenv_symlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executable = tmp_path / "venv-python"
    executable.symlink_to(sys.executable)
    monkeypatch.chdir(tmp_path)

    selected = absolute_executable_path(Path("venv-python"))

    assert selected == executable
    assert selected.is_symlink()


def test_pins_require_contract_v2_and_exact_files(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture.bin"
    fixture.write_bytes(b"fixed")
    pins = _pins(fixture)
    pins_path = tmp_path / "pins.json"
    pins_path.write_text(json.dumps(pins), encoding="utf-8")
    assert validate_pins(pins_path, repository=tmp_path)["mask_contract_version"] == 2

    pins["mask_contract_version"] = 1
    pins_path.write_text(json.dumps(pins), encoding="utf-8")
    with pytest.raises(ValueError, match="contract v2"):
        validate_pins(pins_path, repository=tmp_path)


def test_clock_pin_pending_and_v1_shards_fail_closed(tmp_path: Path) -> None:
    adapter = tmp_path / "clock"
    adapter.write_bytes(b"clock")
    adapter.chmod(0o755)
    with pytest.raises(RuntimeError, match="pending"):
        validate_clock_adapter(
            {
                "clock_adapter": {
                    "schema": "clasher.youtube.clock_adapter.v1",
                    "sha256": "PENDING_LINUX_CLOCK_ADAPTER",
                }
            },
            adapter,
        )

    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema": "clasher.youtube.fullmatch.extraction_manifest.v3",
                "public_mask_v3": {
                    "contract": "label_independent_public_action_mask_v1",
                    "contract_version": 1,
                },
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="contract v2"):
        _verify_v2_manifest(manifest)

    smoke = tmp_path / "smoke.json"
    smoke.write_text(
        json.dumps(
            {
                "schema": "clasher.youtube.cuda_smoke_gate.v1",
                "status": "passed",
                "mask_contract_version": 1,
            }
        ),
        encoding="utf-8",
    )
    pins_path = tmp_path / "pins-empty.json"
    pins_path.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="contract v2"):
        validate_smoke_gate(smoke, pins_path=pins_path)


def test_ru_maxrss_is_normalized_by_platform() -> None:
    assert normalize_max_rss_bytes(123, system="Darwin") == 123
    assert normalize_max_rss_bytes(123, system="Linux") == 123 * 1024


def test_cuda_allowlist_is_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(torch.cuda, "get_device_name", lambda _index: "NVIDIA H200")
    monkeypatch.setattr(torch.cuda, "device_count", lambda: 1)
    monkeypatch.setattr(torch.backends.cudnn, "version", lambda: 90100)
    assert validate_cuda(allowed_device_classes=("H100", "H200"))["device_class"] == "H200"

    monkeypatch.setattr(torch.cuda, "get_device_name", lambda _index: "NVIDIA B200")
    with pytest.raises(RuntimeError, match="outside allowed classes"):
        validate_cuda(allowed_device_classes=("H100", "H200"))

    monkeypatch.setattr(torch.cuda, "get_device_name", lambda _index: "NVIDIA L40S")
    monkeypatch.setattr(torch.cuda, "device_count", lambda: 4)
    observed = validate_cuda(allowed_device_classes=("L40S",))
    assert observed["device_class"] == "L40S"
    assert observed["device_count"] == 4


def test_bulk_requires_replay_disjoint_clock_gate() -> None:
    with pytest.raises(RuntimeError, match="replay-disjoint"):
        validate_bulk_gate(
            {"bulk_gate": {"replay_disjoint_clock_validation": "pending"}}
        )
    validate_bulk_gate(
        {
            "bulk_gate": {
                "replay_disjoint_clock_validation": "passed",
                "report_sha256": "a" * 64,
            }
        }
    )
