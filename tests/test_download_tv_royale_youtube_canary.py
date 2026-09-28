from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.download_tv_royale_youtube_canary import (
    MAX_TOTAL_BYTES,
    OUTPUT_SCHEMA,
    PERMISSION_BASIS,
    PERMISSION_DATE,
    SCHEMA,
    acquire_canary,
    load_sanitized_manifest,
    predicted_total_bytes,
    sections_for,
)


def _row(index: int = 0, **updates: object) -> dict[str, object]:
    video_id = f"v{index:010d}"
    row: dict[str, object] = {
        "id": video_id,
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "availability": "public",
        "access_class": "public",
        "duration_seconds": 200.0,
        "predicted_video_bitrate_bps": 2_000_000.0,
    }
    row.update(updates)
    return row


def _manifest(videos: list[dict[str, object]]) -> dict[str, object]:
    return {
        "schema": SCHEMA,
        "permission_provenance": {
            "basis": PERMISSION_BASIS,
            "attested_on": PERMISSION_DATE,
        },
        "videos": videos,
    }


def _write(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_validates_public_permission_gated_ten_video_bound(tmp_path: Path) -> None:
    path = tmp_path / "metadata.json"
    _write(path, _manifest([_row(index) for index in range(10)]))

    _, sources = load_sanitized_manifest(path)

    assert len(sources) == 10
    assert predicted_total_bytes(sources) == 700_000_000
    assert [section.label for section in sections_for(sources[0])] == [
        "p10",
        "p50",
        "p90",
    ]
    assert all(section.duration_seconds == 8.0 for section in sections_for(sources[0]))


@pytest.mark.parametrize("availability", ["subscriber_only", "private", None])
def test_rejects_nonpublic_or_unknown_access(
    tmp_path: Path, availability: object
) -> None:
    path = tmp_path / "metadata.json"
    _write(
        path,
        _manifest(
            [_row(availability=availability, access_class=availability)]
        ),
    )

    with pytest.raises(ValueError, match="not explicitly public"):
        load_sanitized_manifest(path)


def test_rejects_more_than_ten_or_duplicate_videos(tmp_path: Path) -> None:
    too_many = tmp_path / "many.json"
    _write(too_many, _manifest([_row(index) for index in range(11)]))
    with pytest.raises(ValueError, match="between 1 and 10"):
        load_sanitized_manifest(too_many)

    duplicate = tmp_path / "duplicate.json"
    _write(duplicate, _manifest([_row(), _row()]))
    with pytest.raises(ValueError, match="duplicate video ID"):
        load_sanitized_manifest(duplicate)


@pytest.mark.parametrize(
    ("basis", "attested_on", "message"),
    [
        ("license_metadata", PERMISSION_DATE, "permission basis"),
        (PERMISSION_BASIS, "2026-08-16", "permission date"),
    ],
)
def test_rejects_wrong_permission_provenance(
    tmp_path: Path, basis: str, attested_on: str, message: str
) -> None:
    payload = _manifest([_row()])
    permission = payload["permission_provenance"]
    assert isinstance(permission, dict)
    permission.update({"basis": basis, "attested_on": attested_on})
    path = tmp_path / "metadata.json"
    _write(path, payload)

    with pytest.raises(ValueError, match=message):
        load_sanitized_manifest(path)


def test_rejects_missing_prediction_or_five_gib_prediction(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"
    row = _row()
    row.pop("predicted_video_bitrate_bps")
    _write(missing, _manifest([row]))
    with pytest.raises(ValueError, match="requires predicted"):
        load_sanitized_manifest(missing)

    huge = tmp_path / "huge.json"
    _write(
        huge,
        _manifest(
            [_row(predicted_video_bitrate_bps=MAX_TOTAL_BYTES * 8.0)]
        ),
    )
    _, sources = load_sanitized_manifest(huge)
    assert predicted_total_bytes(sources) > MAX_TOTAL_BYTES


class _FakeRunner:
    def __init__(self, *, fail_on_frame: bool = False) -> None:
        self.commands: list[list[str]] = []
        self.fail_on_frame = fail_on_frame

    def __call__(
        self,
        command: list[str] | tuple[str, ...],
        cwd: Path | None,
        monitored_directory: Path | None,
        byte_limit: int,
    ) -> str:
        del cwd, monitored_directory, byte_limit
        argv = list(command)
        self.commands.append(argv)
        if argv[:2] == ["yt-dlp", "--version"]:
            return "2026.08.17"
        if argv[:2] == ["ffmpeg", "-version"]:
            return "ffmpeg version test\nrest"
        if argv[:2] == ["ffprobe", "-version"]:
            return "ffprobe version test\nrest"
        if argv[-1:] == ["--version"] and "deno" in Path(argv[0]).name:
            return "deno 2.3.0\nrest"
        if argv[0] == "yt-dlp":
            target = Path(argv[argv.index("--output") + 1])
            target.write_bytes(b"mobile-web-source")
            return "downloaded"
        if argv[0] == "ffprobe":
            return json.dumps(
                {
                    "streams": [{"codec_type": "video"}],
                    "format": {"duration": "8.0", "size": "13"},
                }
            )
        if argv[0] == "ffmpeg":
            if self.fail_on_frame:
                raise RuntimeError("synthetic frame failure")
            template = Path(argv[-1])
            if "%03d" in str(template):
                for index in range(1, 3):
                    Path(str(template).replace("%03d", f"{index:03d}")).write_bytes(
                        f"frame-{index}".encode()
                    )
            else:
                template.write_bytes(b"video-section")
            return ""
        raise AssertionError(argv)


def test_acquires_only_short_video_sections_and_hashes_every_artifact(
    tmp_path: Path,
) -> None:
    metadata = tmp_path / "metadata.json"
    output = tmp_path / "canary"
    _write(metadata, _manifest([_row()]))
    runner = _FakeRunner()

    manifest = acquire_canary(
        metadata_manifest=metadata,
        output_directory=output,
        runner=runner,
    )

    assert manifest["schema"] == OUTPUT_SCHEMA
    assert (output / "manifest.json").is_file()
    assert len(manifest["videos"][0]["sections"]) == 3
    assert manifest["coverage"]["completed_sections"] == 3
    assert manifest["limits"]["published_total_bytes"] > 0
    assert manifest["performance"]["peak_scratch_bytes"] > 0
    for section in manifest["videos"][0]["sections"]:
        assert len(section["media"]["sha256"]) == 64
        assert len(section["frames"]) == 2
        assert all(len(frame["sha256"]) == 64 for frame in section["frames"])
        assert section["probe"]["stream_types"] == ["video"]
    download_commands = [
        row
        for row in manifest["commands"]
        if row["argv"] and row["argv"][0] == "yt-dlp" and "--output" in row["argv"]
    ]
    assert len(download_commands) == 1
    assert all("--no-playlist" in row["argv"] for row in download_commands)
    assert all("--force-ipv4" in row["argv"] for row in download_commands)
    assert all("--js-runtimes" in row["argv"] for row in download_commands)
    assert all("ejs:npm" in row["argv"] for row in download_commands)
    assert all(
        row["argv"][row["argv"].index("--format") + 1] == "18"
        for row in download_commands
    )
    assert download_commands[0]["argv"][
        download_commands[0]["argv"].index("--extractor-args") + 1
    ] == "youtube:player_client=mweb"
    transient = manifest["videos"][0]["transient_video_only_source"]
    assert transient["deleted_before_publication"] is True
    assert not (output / transient["path"]).exists()


def test_failure_removes_owned_partial_directory(tmp_path: Path) -> None:
    metadata = tmp_path / "metadata.json"
    output = tmp_path / "canary"
    _write(metadata, _manifest([_row()]))

    with pytest.raises(RuntimeError, match="synthetic frame failure"):
        acquire_canary(
            metadata_manifest=metadata,
            output_directory=output,
            runner=_FakeRunner(fail_on_frame=True),
        )

    assert not output.exists()
    assert not list(tmp_path.glob(".canary.*.partial"))
