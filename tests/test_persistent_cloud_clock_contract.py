from pathlib import Path


def test_persistent_cloud_pipeline_publishes_clock_before_semantics() -> None:
    script = Path("scripts/run_tv_royale_persistent_l40_batch.sh").read_text(
        encoding="utf-8"
    )
    assert "CLASHER_CLOCK_PROVIDER_MODE:-pinned-linux" in script
    assert "unsupported_portable_clock_layout" in script
    assert "recognize_public_clock.py" in script
    assert "apply_tv_royale_youtube_clock_adapter.py" in script
    assert '.venv/bin/python "$clock_adapter"' in script
    assert "portable clock published zero valid frames" in script
    assert "CLOCK_COMPLETE" in script
    assert script.index("--clock-provider-mode deferred") < script.index(
        "pinned_linux_clock_complete_v1"
    )
