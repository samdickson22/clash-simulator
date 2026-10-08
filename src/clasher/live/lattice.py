"""Optional dependency-free Rust loop; NumPy is the exact portable fallback."""
import ctypes
import os
from pathlib import Path
import sys
import numpy as np

LIBRARY = Path(__file__).with_name('_lattice.dylib' if sys.platform == 'darwin' else '_lattice.so')
_kernel = None
if LIBRARY.exists() and not os.environ.get('CLASHER_TRACKER_NUMPY'):
    _library = ctypes.CDLL(str(LIBRARY))
    _kernel = _library.clasher_lattice_mix_v1
    _kernel.restype = None
    _kernel.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
                       ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
                       ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_double]


def mix(p, components, left, right, decay=1., uniform=0.):
    if _kernel is None:
        return None
    # The tracker owns contiguous native float64 arrays; never expose arbitrary
    # buffers or evaluator state to the C ABI.
    assert p.dtype == np.float64 and p.ndim == 1 and p.flags.c_contiguous
    n = len(p)
    shifts = np.array([s for s, _ in components], dtype=np.int64)
    weights = np.array([w for _, w in components], dtype=np.float64)
    caps = np.empty(len(components), dtype=np.float64)
    for i, (s, _) in enumerate(components):
        if abs(s) >= n-1:
            caps[i] = p.sum()
        elif s < 0:
            k = -s
            caps[i] = p[k]+p[:k].sum()
        elif s > 0:
            caps[i] = p[-s-1]+p[-s:].sum()
        else:
            caps[i] = 0.
    out = np.empty_like(p)
    _kernel(p.ctypes.data, out.ctypes.data, n, shifts.ctypes.data, weights.ctypes.data,
            caps.ctypes.data, len(components), left, right, decay, uniform)
    return out
