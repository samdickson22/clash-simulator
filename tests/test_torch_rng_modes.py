from __future__ import annotations

import inspect
import random
from dataclasses import FrozenInstanceError

import pytest
import torch

from clasher.torch_sim.rng import TensorPythonRandom
from clasher.torch_sim.rng_modes import (
    ResidentRNG,
    ResidentRNGMode,
    create_resident_rng,
)


def _randoms(seeds: list[int]) -> list[random.Random]:
    return [random.Random(seed) for seed in seeds]


def test_factory_defaults_to_exact_and_matches_masked_python_shuffle_state() -> None:
    seeds = [101, 202, 303, 404]
    references = _randoms(seeds)
    rng = create_resident_rng(_randoms(seeds))
    masks = (
        torch.tensor([True, True, True, True]),
        torch.tensor([True, False, True, False]),
        torch.tensor([False, True, False, True]),
        torch.tensor([False, False, False, False]),
    )

    assert rng.mode is ResidentRNGMode.EXACT_PYTHON
    assert rng.parity_eligible
    for mask in masks * 12:
        expected: list[list[int]] = []
        for row, source in enumerate(references):
            order = [0, 1]
            if bool(mask[row]):
                source.shuffle(order)
            expected.append(order)
        assert rng.draw_player_order(mask).tolist() == expected

    expected_state = TensorPythonRandom.from_randoms(references)
    checkpoint = rng.state_dict()
    assert torch.equal(checkpoint["words"], expected_state.words)
    assert torch.equal(checkpoint["index"], expected_state.index)


def test_native_training_is_explicit_deterministic_masked_and_non_parity() -> None:
    rows = _randoms([1, 2, 3, 4])
    first = create_resident_rng(
        rows,
        mode=ResidentRNGMode.NATIVE_TRAINING,
        native_seed=99,
    )
    second = create_resident_rng(
        rows,
        mode=ResidentRNGMode.NATIVE_TRAINING,
        native_seed=99,
    )
    active = torch.tensor([True, False, True, False])
    before = first.state_dict()["native_state"]

    first_order = first.draw_player_order(active)
    second_order = second.draw_player_order(active)

    assert torch.equal(first_order, second_order)
    assert first_order[~active].tolist() == [[0, 1], [0, 1]]
    assert torch.equal(first.state_dict()["native_state"][~active], before[~active])
    assert not first.parity_eligible
    assert first.telemetry.label.startswith("NON_PARITY")
    assert first.telemetry.native_training_opt_in
    with pytest.raises(RuntimeError, match="not eligible"):
        first.require_parity()


def test_native_mode_requires_both_mode_and_seed_opt_in() -> None:
    rows = _randoms([7, 8])
    with pytest.raises(ValueError, match="native_seed"):
        create_resident_rng(rows, native_seed=7)
    with pytest.raises(ValueError, match="explicit native_seed"):
        create_resident_rng(rows, mode=ResidentRNGMode.NATIVE_TRAINING)


@pytest.mark.parametrize("mode", list(ResidentRNGMode))
def test_clone_fork_and_state_restore_share_one_mode_safe_interface(
    mode: ResidentRNGMode,
) -> None:
    seeds = [11, 22, 33]
    rng = (
        ResidentRNG.exact_from_randoms(_randoms(seeds))
        if mode is ResidentRNGMode.EXACT_PYTHON
        else ResidentRNG.native_training_from_seed(1234, len(seeds))
    )
    rng.draw_player_order()
    checkpoint = rng.state_dict()
    cloned = rng.clone()
    forked = rng.fork([2, 0, 2])

    assert cloned.mode is mode
    assert forked.mode is mode
    for name, value in checkpoint.items():
        assert torch.equal(cloned.state_dict()[name], value)
        assert cloned.state_dict()[name].data_ptr() != value.data_ptr()
    if mode is ResidentRNGMode.EXACT_PYTHON:
        assert torch.equal(forked.state_dict()["words"], checkpoint["words"][[2, 0, 2]])
    else:
        assert torch.equal(
            forked.state_dict()["native_state"],
            checkpoint["native_state"][[2, 0, 2]],
        )

    rng.draw_player_order()
    rng.load_state_dict_(checkpoint)
    for name, value in checkpoint.items():
        assert torch.equal(rng.state_dict()[name], value)


def test_checkpoint_metadata_prevents_native_state_from_claiming_parity() -> None:
    exact = ResidentRNG.exact_from_randoms(_randoms([1, 2]))
    native = ResidentRNG.native_training_from_seed(55, 2)
    native_state = native.state_dict()

    assert int(native_state["mode"].item()) == int(ResidentRNGMode.NATIVE_TRAINING)
    assert not bool(native_state["parity_eligible"].item())
    with pytest.raises(ValueError, match="mode/parity"):
        exact.load_state_dict_(native_state)

    mislabeled = exact.state_dict()
    mislabeled["parity_eligible"] = torch.tensor(False)
    with pytest.raises(ValueError, match="mode/parity"):
        exact.load_state_dict_(mislabeled)

    with pytest.raises(TypeError, match="exact RNG mode"):
        ResidentRNG(native._source, ResidentRNGMode.EXACT_PYTHON)
    with pytest.raises(FrozenInstanceError):
        native.mode = ResidentRNGMode.EXACT_PYTHON  # type: ignore[misc]


def test_common_draw_and_checkpoint_surfaces_are_tensor_only() -> None:
    source = inspect.getsource(ResidentRNG.draw_player_order)
    assert ".item(" not in source
    assert ".tolist(" not in source
    for rng in (
        ResidentRNG.exact_from_randoms(_randoms([9, 10])),
        ResidentRNG.native_training_from_seed(42, 2),
    ):
        assert rng.draw_player_order().shape == (2, 2)
        assert all(
            isinstance(value, torch.Tensor) for value in rng.state_dict().values()
        )


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA unavailable")
def test_native_training_mode_stays_cuda_resident_across_common_operations() -> None:
    rng = ResidentRNG.native_training_from_seed(808, 4, device="cuda")
    active = torch.tensor([True, False, True, True], device="cuda")
    order = rng.draw_player_order(active)
    clone = rng.clone()
    fork = rng.fork(torch.tensor([3, 0], device="cuda"))

    assert order.device.type == "cuda"
    assert clone.device.type == "cuda"
    assert fork.device.type == "cuda"
    assert all(value.device.type == "cuda" for value in rng.state_dict().values())
