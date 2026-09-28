import json

import numpy as np
import pytest
from cache_reader import cluster_codes, read_complete_cache


def test_compact_cluster_codes_preserve_bootstrap_group_order():
    names = np.array(["z", "a", "q", "z", "b", "a"])
    vocabulary, codes = cluster_codes(names)
    assert vocabulary == ("a", "b", "q", "z")
    for selected in (np.arange(6), np.array([0, 1, 3, 5]), np.array([2, 4])):
        np.testing.assert_array_equal(np.unique(names[selected], return_inverse=True)[1],
                                      np.unique(codes[selected], return_inverse=True)[1])


def test_partial_cache_refuses_before_feature_bytes(tmp_path, monkeypatch):
    import cache_reader

    (tmp_path / "complete.json").write_text(json.dumps({"status": "partial"}))

    def forbidden(path):
        raise AssertionError("partial cache reached feature bytes")

    monkeypatch.setattr(cache_reader, "file_sha", forbidden)
    with pytest.raises(ValueError, match="complete expanded cache audit"):
        read_complete_cache(tmp_path)
