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


def test_three_seed_driver_requires_every_child_gate() -> None:
    source = Path(
        "scripts/run_hog26_joint_action_value_cuda_three_seed.sh"
    ).read_text()
    for seed in (1244001, 1244002, 1244003, 1246001, 1246002, 1246003):
        assert str(seed) in source
    assert 'all(row["status"] == expected for row in rows)' in source
    assert "minimum_throughput_ratio" in source
    assert "at least one CUDA seed failed" in source
