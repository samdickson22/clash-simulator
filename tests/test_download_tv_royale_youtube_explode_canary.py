from __future__ import annotations

import json
from pathlib import Path

from scripts.download_tv_royale_youtube_canary import (
    PERMISSION_BASIS,
    PERMISSION_DATE,
    SCHEMA,
)
from scripts.download_tv_royale_youtube_explode_canary import acquire_highres_canary


def _metadata(path: Path) -> None:
    video_id = "v0000000000"
    path.write_text(
        json.dumps(
            {
                "schema": SCHEMA,
                "permission_provenance": {
                    "basis": PERMISSION_BASIS,
                    "attested_on": PERMISSION_DATE,
                    "public_cc_license_claimed": False,
                },
                "videos": [
                    {
                        "id": video_id,
                        "url": f"https://www.youtube.com/watch?v={video_id}",
                        "availability": "public",
                        "access_class": "public",
                        "duration_seconds": 200,
                        "predicted_video_bitrate_bps": 2_000_000,
                        "filesize_approx_bytes": 50_000_000,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


class _Runner:
    def __call__(
        self,
        command: list[str] | tuple[str, ...],
        cwd: Path | None,
        monitored_directory: Path | None,
        byte_limit: int,
    ) -> str:
        del cwd, monitored_directory, byte_limit
        argv = list(command)
        if "build" in argv:
            return "build passed"
        if "run" in argv:
            output = Path(argv[-1])
            output.write_bytes(b"x" * 64)
            return json.dumps(
                {
                    "stream": {
                        "container": "webm",
                        "width": 1182,
                        "height": 2560,
                        "framesPerSecond": 60,
                        "bitrateBitsPerSecond": 2_000_000,
                        "declaredBytes": 64,
                        "actualBytes": 64,
                        "videoCodec": "vp9",
                    }
                }
            )
        if argv[0] == "ffprobe":
            return json.dumps(
                {
                    "streams": [
                        {
                            "codec_type": "video",
                            "width": 1182,
                            "height": 2560,
                        }
                    ],
                    "format": {"duration": "8.0", "size": "7"},
                }
            )
        if argv[0] == "ffmpeg" and "%03d" in argv[-1]:
            for index in range(1, 3):
                Path(argv[-1].replace("%03d", f"{index:03d}")).write_bytes(b"frame")
            return ""
        if argv[0] == "ffmpeg" and argv[-1] != "-":
            Path(argv[-1]).write_bytes(b"section")
            return ""
        if argv[0] == "ffmpeg" and argv[-1] == "-":
            return ""
        raise AssertionError(argv)


def test_publishes_highres_video_only_sections_and_deletes_transient(
    tmp_path: Path,
) -> None:
    metadata = tmp_path / "metadata.json"
    output = tmp_path / "output"
    _metadata(metadata)

    manifest = acquire_highres_canary(
        metadata_manifest=metadata,
        output_directory=output,
        runner=_Runner(),
        dotnet=Path("dotnet"),
        project=Path("canary.csproj"),
    )

    assert manifest["coverage"]["completed_videos"] == 1
    assert manifest["coverage"]["completed_sections"] == 3
    assert manifest["permission_provenance"]["public_cc_license_claimed"] is False
    source = manifest["videos"][0]["transient_video_only_source"]
    assert source["width"] == 1182
    assert source["height"] == 2560
    assert source["deleted_before_publication"] is True
    assert not (output / source["path"]).exists()
    for section in manifest["videos"][0]["sections"]:
        assert section["probe"]["streams"][0]["codec_type"] == "video"
        assert section["full_decode_passed"] is True
        assert len(section["frames"]) == 2
