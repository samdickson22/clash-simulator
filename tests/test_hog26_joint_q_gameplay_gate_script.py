from pathlib import Path


def test_gameplay_gate_driver_is_fail_closed() -> None:
    source = Path("scripts/run_hog26_joint_q_gameplay_gate.sh").read_text()
    assert "set -euo pipefail" in source
    assert "PILOT_ROOT" in source
    assert '[[ -f "$pilot_root/COMPLETE" ]]' in source
    assert '[[ ! -e "$output_root" ]]' in source
    assert "policy_v2_update_" in source
    for opponent in (
        "balanced",
        "bridge-pressure",
        "reactive-defense",
        "spell-control",
        "slow-push",
        "split-lane",
        "random",
    ):
        assert opponent in source
