from pathlib import Path
from typing import Any

import pytest

from scripts.acquire_tv_royale_youtube_fullmatch import (
    download_bounded_public_stream,
    download_bounded_public_stream_with_yt_dlp,
    download_source,
    parse_framehash,
    select_yt_dlp_format,
)


def test_parse_framehash_requires_contiguous_pts(tmp_path: Path) -> None:
    path = tmp_path / "index.framehash"
    path.write_text(
        "#format: frame checksums\n"
        "#version: 2\n"
        "#tb 0: 1/10\n"
        "0, 0, 0, 1, 6, aaa\n"
        "0, 1, 1, 1, 6, bbb\n",
        encoding="utf-8",
    )
    assert parse_framehash(path) == {
        "sample_count": 2,
        "first_output_pts": 0,
        "last_output_pts": 1,
        "output_time_base": "1/10",
        "all_output_pts_contiguous": True,
        "all_frame_hashes_unique": True,
    }

    path.write_text(
        "#tb 0: 1/10\n0, 0, 0, 1, 6, aaa\n0, 2, 2, 1, 6, bbb\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="not contiguous"):
        parse_framehash(path)


def test_yt_dlp_selection_requires_exact_bounded_video_only_format() -> None:
    metadata = {
        "formats": [
            {
                "format_id": "308",
                "ext": "webm",
                "width": 1182,
                "height": 2560,
                "fps": 60,
                "vcodec": "vp9",
                "acodec": "none",
                "filesize": 138_690_318,
                "tbr": 5207.485,
            }
        ]
    }
    assert select_yt_dlp_format(metadata, "308")["filesize"] == 138_690_318

    metadata["formats"][0]["acodec"] = "opus"
    with pytest.raises(ValueError, match="video-only"):
        select_yt_dlp_format(metadata, "308")

    metadata["formats"][0]["acodec"] = "none"
    metadata["formats"][0]["filesize"] = None
    with pytest.raises(ValueError, match="bounded exact filesize"):
        select_yt_dlp_format(metadata, "308")


def test_direct_stream_rejects_non_googlevideo_url_before_network(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="googlevideo"):
        download_bounded_public_stream(
            {
                "url": "https://example.com/video.webm",
                "filesize": 10,
                "http_headers": {},
            },
            tmp_path / "source.webm",
        )

    with pytest.raises(ValueError, match="googlevideo"):
        download_bounded_public_stream_with_yt_dlp(
            {
                "url": "https://example.com/video.webm",
                "filesize": 10,
                "http_headers": {},
            },
            tmp_path / "chunked.webm",
            Path("yt-dlp"),
        )


def test_direct_backend_reuses_fresh_metadata_without_second_extraction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    commands: list[list[str]] = []

    def fake_run(command: list[str]) -> tuple[str, float]:
        commands.append(command)
        assert command[-1] == "--version"
        return "2026.08.19\n", 0.01

    def fake_download(
        selected: dict[str, Any],
        source: Path,
        yt_dlp: Path,
        impersonate: str | None,
    ) -> float:
        assert yt_dlp == Path("yt-dlp")
        assert impersonate == "Chrome-136:Macos-15"
        source.write_bytes(b"x" * int(selected["filesize"]))
        return 0.02

    monkeypatch.setattr("scripts.acquire_tv_royale_youtube_fullmatch.run", fake_run)
    monkeypatch.setattr(
        "scripts.acquire_tv_royale_youtube_fullmatch.download_bounded_public_stream_with_yt_dlp",
        fake_download,
    )
    video = {
        "url": "https://www.youtube.com/watch?v=public",
        "formats": [
            {
                "format_id": "308",
                "url": "https://example.googlevideo.com/videoplayback",
                "ext": "webm",
                "width": 1182,
                "height": 2560,
                "fps": 60,
                "vcodec": "vp9",
                "acodec": "none",
                "filesize": 8,
                "tbr": 5207.485,
                "http_headers": {},
            }
        ],
    }
    source = tmp_path / "source.webm"

    _, _, backend = download_source(
        video=video,
        source=source,
        backend="yt-dlp-direct",
        dotnet=None,
        downloader_project=None,
        yt_dlp=Path("yt-dlp"),
        yt_dlp_format="308",
        yt_dlp_impersonate="Chrome-136:Macos-15",
    )

    assert backend == "yt-dlp-resolved-bounded-chunked-https-v2"
    assert len(commands) == 1
    assert source.read_bytes() == b"x" * 8
