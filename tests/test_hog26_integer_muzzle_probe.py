import math

import numpy as np
import pytest
import torch

from scripts.hog26_integer_muzzle_probe import integer_muzzle_offsets


@pytest.mark.parametrize("device", ["cpu", "mps:0"])
def test_integer_offsets_match_exact_reference_across_board_geometry(device):
    if device == "mps:0" and not torch.backends.mps.is_available():
        pytest.skip("MPS unavailable")
    rng = np.random.default_rng(1278981)
    cases = [(0, -7040, 300), (0, 0, 300), (3000, 4000, 5000),
             (32767, 32767, 65534), (-32767, 32767, 32767)]
    cases += list(zip(rng.integers(-18000, 18001, 4096).tolist(),
                      rng.integers(-32000, 32001, 4096).tolist(),
                      rng.integers(0, 65535, 4096).tolist(), strict=True))
    expected = []
    for x, y, radius in cases:
        d2 = x * x + y * y
        if radius * radius >= d2:
            expected.append((x, y))
        else:
            expected.append(tuple((1 if c >= 0 else -1) * math.isqrt(c * c * radius * radius // d2)
                                  for c in (x, y)))
    values = torch.tensor(cases, dtype=torch.int64, device=device)
    actual = torch.stack(integer_muzzle_offsets(*values.unbind(1)), dim=1).cpu()
    assert torch.equal(actual, torch.tensor(expected))


def test_invalid_geometry_rejected():
    with pytest.raises(ValueError, match="bound"):
        integer_muzzle_offsets(torch.tensor([40000]), torch.tensor([0]), torch.tensor([300]))
