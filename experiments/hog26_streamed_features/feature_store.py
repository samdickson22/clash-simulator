"""Append exact float32 feature blocks to an owned file without retaining games."""

import hashlib
import mmap
from pathlib import Path

import numpy as np


def file_sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024**2), b""):
            digest.update(block)
    return digest.hexdigest()


class FeatureStore:
    def __init__(self, path, rows, columns):
        if rows <= 0 or columns <= 0:
            raise ValueError("positive feature dimensions required")
        self.path = Path(path)
        with self.path.open("xb") as stream:
            stream.truncate(rows * columns * 4)
        self.array = np.memmap(self.path, mode="r+", dtype="<f4", shape=(rows, columns))
        self.offset = 0
        self.digest = hashlib.sha256()

    def append(self, values):
        values = np.asarray(values)
        if (values.dtype != np.dtype("<f4") or values.ndim != 2
                or values.shape[1] != self.array.shape[1] or not len(values)
                or self.offset + len(values) > len(self.array) or not np.isfinite(values).all()):
            raise ValueError("invalid exact feature block")
        block = np.ascontiguousarray(values)
        self.array[self.offset:self.offset + len(block)] = block
        self.digest.update(memoryview(block).cast("B"))
        self.offset += len(block)

    def release_pages(self):
        self.array.flush()
        self.array._mmap.madvise(mmap.MADV_DONTNEED)

    def finish(self):
        if self.offset != len(self.array):
            raise ValueError("feature store is incomplete")
        shape = list(self.array.shape)
        self.release_pages()
        self.array._mmap.close()
        actual = file_sha(self.path)
        if actual != self.digest.hexdigest():
            raise ValueError("stored features differ from appended bytes")
        return {"shape": shape, "dtype": "<f4", "sha256": actual, "bytes": self.path.stat().st_size}
