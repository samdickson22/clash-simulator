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
    assert "EXPECTED_INITIALIZER_SHA256" in source
    assert "--first-rollout-audit-json" in source
    assert "pre_optimization_rollout_sha256" in source
    assert "pre-optimization rollout mismatch" in source


def test_three_seed_driver_requires_every_child_gate() -> None:
    source = Path(
        "scripts/run_hog26_joint_action_value_cuda_three_seed.sh"
    ).read_text()
    for seed in (1244001, 1244002, 1244003, 1246001, 1246002, 1246003):
        assert str(seed) in source
    assert 'all(row["status"] == expected for row in rows)' in source
    assert "minimum_throughput_ratio" in source
    assert "at least one CUDA seed failed" in source
    for digest in (
        "3b651bce56b036b8948eefa0f0b85611c19ac558cbd86e64bece399f23ae3cc5",
        "6be554863e9cf2254e7503e3cebccdc25fb8b29682825142e0bcfd4c948788e6",
        "1c8323ce6fef49ef8d6420aeb4c2c400b896223a69568e4d86a137f628235776",
    ):
        assert digest in source
