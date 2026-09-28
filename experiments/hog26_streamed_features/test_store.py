import numpy as np
import pytest
from feature_store import FeatureStore, file_sha


def test_chunking_and_page_release_preserve_exact_rows(tmp_path):
    path = tmp_path / "features.f32"
    values = np.arange(40, dtype=np.float32).reshape(10, 4) / 7
    store = FeatureStore(path, 10, 4)
    store.append(values[:3])
    store.release_pages()
    store.append(values[3:])
    result = store.finish()
    assert result["sha256"] == file_sha(path)
    mapped = np.memmap(path, mode="r", dtype="<f4", shape=(10, 4))
    np.testing.assert_array_equal(mapped[[9, 0, 5, 5]], values[[9, 0, 5, 5]])
    mapped._mmap.close()
    with pytest.raises(FileExistsError):
        FeatureStore(path, 10, 4)


def test_partial_or_invalid_blocks_cannot_finish(tmp_path):
    store = FeatureStore(tmp_path / "partial.f32", 3, 4)
    store.append(np.ones((2, 4), dtype=np.float32))
    with pytest.raises(ValueError, match="incomplete"):
        store.finish()
    with pytest.raises(ValueError, match="invalid exact"):
        store.append(np.ones((1, 4), dtype=np.float64))
    with pytest.raises(ValueError, match="invalid exact"):
        store.append(np.full((1, 4), np.nan, dtype=np.float32))
    store.array._mmap.close()
