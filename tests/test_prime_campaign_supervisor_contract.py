from pathlib import Path


def test_supervisor_terminates_early_only_after_marker_and_worker_exit() -> None:
    script = Path("scripts/supervise_prime_tv_royale_campaign.sh").read_text(
        encoding="utf-8"
    )
    assert "CLASHER_REMOTE_COMPLETION_MARKER" in script
    marker = script.index("test -f '$remote_repo/$remote_completion_marker'")
    workers = script.index("! pgrep -f", marker)
    terminate = script.index('prime --plain pods terminate "$pod_id" --yes')
    assert marker < workers < terminate
