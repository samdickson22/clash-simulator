from __future__ import annotations

from pathlib import Path


def test_cuda_ab_driver_pins_fail_closed_contracts() -> None:
    source = Path("scripts/run_hog26_joint_action_value_cuda_ab.sh").read_text()
    assert "set -euo pipefail" in source
    assert "--device cuda" in source
    assert "--actor-device cuda" in source
    assert '[[ ! -e "$output_root" ]]' in source
    assert 'metadata.get("execution_mode") != "cuda-graph"' in source
    assert "throughput_ratio < 0.95" in source
    assert "len(candidate_only) != 14" in source
    assert "shared_initial_mismatches" in source
