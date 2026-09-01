from pathlib import Path


def test_legacy_joint_q_driver_pins_matched_bridge_contract() -> None:
    source = Path("scripts/run_hog26_legacy_joint_q_ab.sh").read_text()
    assert "set -euo pipefail" in source
    assert "--simulation-backend python" in source
    assert "--actor-workers" in source
    assert "--device mps" in source
    assert "--actor-device cpu" in source
    assert "--first-rollout-audit-json" in source
    assert "control and candidate first rollouts differ" in source
    assert "candidate initializer changed shared model tensors" in source
    assert "ratio < 0.90" in source
    assert "completed-local-bridge-pilot" in source
