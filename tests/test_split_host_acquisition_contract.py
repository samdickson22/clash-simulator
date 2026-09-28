from pathlib import Path


def test_split_host_acquisition_uses_single_resolved_impersonated_stream() -> None:
    script = Path("scripts/run_tv_royale_split_host_acquisition.zsh").read_text(
        encoding="utf-8"
    )
    assert "Chrome-136:Macos-15" in script
    assert "--dump-single-json" in script
    assert "--backend yt-dlp-direct" in script
    assert "--yt-dlp-impersonate" in script
    assert "--yt-dlp-format 308" in script
    assert "rsync -az --partial" in script
    assert "ACQUISITION_COMPLETE" in script
