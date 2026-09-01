from pathlib import Path


def test_spatial_cuda_driver_pins_candidate_and_graph_gate() -> None:
    source = Path("scripts/run_hog26_spatial_teacher_cuda_gate.sh").read_text()
    assert "set -euo pipefail" in source
    assert "3b651bce56b036b8948eefa0f0b85611c19ac558cbd86e64bece399f23ae3cc5" in source
    assert "4ec5585f63fd65c30ed977b78a87cc66208ab64d7e125116f1dd32f7d120d8f4" in source
    assert "--device cuda" in source
    assert "finalize_hog26_spatial_teacher_cuda_gate.py" in source
