from __future__ import annotations

import inspect

import pytest
import torch

from clasher.torch_sim.native_rng import NativeTrainingRNG


def test_cpu_fallback_is_deterministic_and_rows_are_independently_seeded() -> None:
    first = NativeTrainingRNG.from_seeds([0, 1, 2, 2])
    second = NativeTrainingRNG.from_seeds([0, 1, 2, 2])
    actual = first.random((4, 7), dtype=torch.float64)
    expected = second.random((4, 7), dtype=torch.float64)

    assert actual.device.type == "cpu"
    assert torch.equal(actual, expected)
    assert not torch.equal(actual[0], actual[1])
    assert torch.equal(actual[2], actual[3])
    assert torch.all((actual >= 0.0) & (actual < 1.0))


def test_block_draw_matches_repeated_draws_and_counter_advance() -> None:
    blocked = NativeTrainingRNG.from_seeds([11, 22, 33])
    repeated = blocked.clone()
    skipped = blocked.clone()

    block = blocked.random(9, dtype=torch.float64)
    scalar = torch.stack(
        [repeated.random(dtype=torch.float64) for _ in range(9)], dim=1
    )
    skipped.advance(9)

    assert torch.equal(block, scalar)
    assert torch.equal(blocked.state, repeated.state)
    assert torch.equal(blocked.state, skipped.state)


def test_masked_rows_publish_zero_and_do_not_advance() -> None:
    rng = NativeTrainingRNG.from_seeds([5, 6, 7, 8])
    before = rng.state.clone()
    active = torch.tensor([True, False, True, False])
    samples = rng.random((3, 2), active=active)

    assert torch.count_nonzero(samples[~active]) == 0
    assert torch.equal(rng.state[~active], before[~active])
    assert torch.all(rng.state[active] != before[active])

    references = NativeTrainingRNG.from_seeds([5, 7])
    assert torch.equal(samples[active], references.random((3, 2)))


def test_clone_fork_and_state_restore_never_alias_mutable_storage() -> None:
    parent = NativeTrainingRNG.from_seeds([101, 202, 303])
    parent.random(3)
    cloned = parent.clone()
    forked = parent.fork([2, 0, 2])
    checkpoint = parent.state_dict()

    assert parent.state.data_ptr() != cloned.state.data_ptr()
    assert parent.state.data_ptr() != forked.state.data_ptr()
    assert torch.equal(forked.state, parent.state[[2, 0, 2]])
    cloned.random()
    forked.random(2)
    assert torch.equal(parent.state, checkpoint["state"])

    parent.random(5)
    parent.load_state_dict_(checkpoint)
    assert torch.equal(parent.state, checkpoint["state"])


def test_signed_and_unsigned_seed_spellings_select_the_same_stream() -> None:
    unsigned = 0xFFFFFFFFFFFFFFFF
    signed = -1
    left = NativeTrainingRNG.from_seed(unsigned, 2)
    right = NativeTrainingRNG.from_seed(signed, 2)
    assert torch.equal(left.state, right.state)
    assert torch.equal(left.random(20), right.random(20))
    assert not torch.equal(left.state[0], left.state[1])


def test_uniform_distribution_mean_variance_and_deciles() -> None:
    rng = NativeTrainingRNG.from_seeds([19, 23, 29, 31])
    samples = rng.random(65_536, dtype=torch.float64).flatten()
    assert abs(float(samples.mean()) - 0.5) < 0.003
    assert abs(float(samples.var(unbiased=False)) - 1.0 / 12.0) < 0.001
    bins = torch.histc(samples, bins=10, min=0.0, max=1.0)
    expected = samples.numel() / 10
    assert torch.all(torch.abs(bins - expected) < expected * 0.025)


def test_empty_shape_and_validation_do_not_consume_state() -> None:
    rng = NativeTrainingRNG.from_seed(9, 2)
    before = rng.state.clone()
    assert rng.random((3, 0, 4)).shape == (2, 3, 0, 4)
    assert torch.equal(rng.state, before)
    with pytest.raises(ValueError, match="negative"):
        rng.random((-1,))
    with pytest.raises(TypeError, match="floating"):
        rng.random(dtype=torch.int64)
    with pytest.raises(ValueError, match="active mask"):
        rng.random(active=torch.ones(3, dtype=torch.bool))
    assert torch.equal(rng.state, before)


def test_draw_path_has_no_item_or_tolist_host_synchronization() -> None:
    source = inspect.getsource(NativeTrainingRNG.random)
    assert ".item(" not in source
    assert ".tolist(" not in source
    rng = NativeTrainingRNG.from_seeds([1, 2, 3])
    rng.random((32, 8))


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA unavailable")
def test_cuda_streams_are_resident_and_match_cpu_bits() -> None:
    seeds = [7, 13, 29, 101]
    cpu = NativeTrainingRNG.from_seeds(seeds)
    cuda = NativeTrainingRNG.from_seeds(seeds, device="cuda")
    active_cpu = torch.tensor([True, False, True, True])
    active_cuda = active_cpu.to("cuda")

    cpu_values = cpu.random((257, 3), active=active_cpu, dtype=torch.float64)
    cuda_values = cuda.random((257, 3), active=active_cuda, dtype=torch.float64)
    assert cuda_values.device.type == "cuda"
    assert cuda.state.device.type == "cuda"
    assert torch.equal(cuda_values.cpu(), cpu_values)
    assert torch.equal(cuda.state.cpu(), cpu.state)
