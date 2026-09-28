import numpy as np
import pytest
from parallel_engine import compare_arrays


def test_only_provenance_metadata_may_differ(tmp_path):
    original, replay = tmp_path / "original.npz", tmp_path / "replay.npz"
    np.savez(original, metadata_json="old", feature=np.array([0., -0., 1.], dtype=np.float32))
    np.savez(replay, metadata_json="new", feature=np.array([0., -0., 1.], dtype=np.float32))
    assert compare_arrays(original, replay) == ["feature"]
    np.savez(replay, metadata_json="new", feature=np.array([0., 0., 1.], dtype=np.float32))
    with pytest.raises(ValueError, match="array differs"):
        compare_arrays(original, replay)
