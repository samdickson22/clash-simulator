import random
from dataclasses import fields

import pytest
import torch

from clasher.battle import BattleState
from clasher.torch_sim import (
    TensorBattleState,
    TensorPythonRandom,
    TorchBattleExecutor,
)
from clasher.torch_sim import executor as torch_executor


def test_python_random_state_round_trips_without_consumption() -> None:
    sources = [random.Random(17), random.Random(2**48 + 91)]
    sources[0].gauss(3.0, 2.0)
    before = [source.getstate() for source in sources]

    resident = TensorPythonRandom.from_randoms(sources)

    assert [source.getstate() for source in sources] == before
    assert [resident.python_state(row) for row in range(2)] == before

    targets = [random.Random(), random.Random()]
    resident.sync_to_randoms(targets)
    assert [target.getstate() for target in targets] == before
    assert [target.random() for target in targets] == [
        source.random() for source in sources
    ]


def test_tensor_random_matches_python_across_twists_and_masked_rows() -> None:
    oracles = [random.Random(seed) for seed in (0, 2301, 2**40 + 7)]
    resident = TensorPythonRandom.from_randoms(
        [random.Random(seed) for seed in (0, 2301, 2**40 + 7)]
    )

    for draw in range(1_000):
        active = torch.tensor(
            [draw % 2 == 0, draw % 3 != 0, draw % 5 in {1, 4}],
            dtype=torch.bool,
        )
        actual = resident.random(active).tolist()
        expected = [
            oracle.random() if bool(active[row]) else 0.0
            for row, oracle in enumerate(oracles)
        ]
        assert actual == expected

    assert [resident.python_state(row) for row in range(3)] == [
        oracle.getstate() for oracle in oracles
    ]


def test_tensor_random_matches_python_at_staggered_twist_boundaries() -> None:
    seeds = (113, 227, 331)
    source_streams = [random.Random(seed) for seed in seeds]
    oracles = [random.Random(seed) for seed in seeds]
    for word_count, source, oracle in zip(
        (622, 623, 624), source_streams, oracles
    ):
        for _ in range(word_count):
            assert source.getrandbits(32) == oracle.getrandbits(32)

    resident = TensorPythonRandom.from_randoms(source_streams)
    masks = (
        torch.tensor([True, True, False]),
        torch.tensor([False, True, True]),
        torch.tensor([True, False, True]),
        torch.tensor([True, True, True]),
    )
    for active in masks:
        actual = resident.random(active).tolist()
        expected = [
            oracle.random() if bool(active[row]) else 0.0
            for row, oracle in enumerate(oracles)
        ]
        assert actual == expected

    assert [resident.python_state(row) for row in range(3)] == [
        oracle.getstate() for oracle in oracles
    ]


def test_tensor_getrandbits_and_randrange_match_python_consumption_order() -> None:
    seeds = (3, 74, 2301, 2**39 + 11)
    resident = TensorPythonRandom.from_randoms(
        [random.Random(seed) for seed in seeds]
    )
    oracles = [random.Random(seed) for seed in seeds]

    for bit_count in (0, 1, 17, 31, 32, 33, 63):
        assert resident.getrandbits(bit_count).tolist() == [
            oracle.getrandbits(bit_count) for oracle in oracles
        ]

    bounds = torch.tensor([1, 2, 359, 2**31 + 1], dtype=torch.int64)
    for _ in range(1_000):
        assert resident.randrange(bounds).tolist() == [
            oracle.randrange(int(bound))
            for oracle, bound in zip(oracles, bounds.tolist())
        ]

    assert [resident.python_state(row) for row in range(4)] == [
        oracle.getstate() for oracle in oracles
    ]


def test_tensor_battle_fork_isolates_all_mutable_planes_and_rng_rows() -> None:
    parents = [
        BattleState(rng=random.Random(101)),
        BattleState(rng=random.Random(202)),
    ]
    parent_states = [battle.rng.getstate() for battle in parents]
    resident = TensorBattleState.from_battles(parents, max_entities=16)

    children = resident.fork([1, 0, 1])

    assert children.card_names is resident.card_names
    assert children.card_to_id is resident.card_to_id
    for state_field in fields(resident):
        if state_field.name in {"device", "card_names", "card_to_id", "rng"}:
            continue
        parent_tensor = getattr(resident, state_field.name)
        child_tensor = getattr(children, state_field.name)
        assert child_tensor.data_ptr() != parent_tensor.data_ptr()

    children.time[0] += 1.0
    children.entity_hp[1, 0] -= 17.0
    active = torch.tensor([True, False, True])
    actual_draws = children.rng.random(active).tolist()

    child_oracles = [random.Random(), random.Random(), random.Random()]
    for target, state in zip(
        child_oracles,
        (parent_states[1], parent_states[0], parent_states[1]),
    ):
        target.setstate(state)
    expected_draws = [child_oracles[0].random(), 0.0, child_oracles[2].random()]
    assert actual_draws == expected_draws

    child_battles = [parents[1].clone(), parents[0].clone(), parents[1].clone()]
    children.sync_to_battles(child_battles)
    assert [battle.rng.getstate() for battle in child_battles] == [
        oracle.getstate() for oracle in child_oracles
    ]
    assert [battle.rng.random() for battle in child_battles] == [
        oracle.random() for oracle in child_oracles
    ]

    assert float(resident.time[1].item()) != float(children.time[0].item())
    assert [resident.rng.python_state(row) for row in range(2)] == parent_states
    assert [battle.rng.getstate() for battle in parents] == parent_states
    assert children.rng.words.data_ptr() != resident.rng.words.data_ptr()


def test_resident_rng_sync_preserves_python_next_draw_continuity() -> None:
    actual = BattleState(rng=random.Random(9013))
    expected = actual.clone()
    resident = TensorBattleState.from_battles([actual], max_entities=16)

    assert resident.rng.random().item() == expected.rng.random()
    assert resident.rng.randrange(359).item() == expected.rng.randrange(359)
    assert resident.rng.randrange(1).item() == expected.rng.randrange(1)

    resident.sync_to_battles([actual])

    assert actual.rng.getstate() == expected.rng.getstate()
    assert [actual.rng.random() for _ in range(8)] == [
        expected.rng.random() for _ in range(8)
    ]


def test_python_rng_draw_invalidates_retained_tensor_state() -> None:
    actual = BattleState(rng=random.Random(7301))
    expected = actual.clone()
    executor = TorchBattleExecutor("pytorch")

    assert executor.step_logic_ticks(actual, 0) == 0
    assert actual.rng.random() == expected.rng.random()

    # Clocks and entities are unchanged, so only the RNG comparison can force
    # a reload of the retained tensor row rather than publishing stale state.
    assert executor.step_logic_ticks(actual, 0) == 0
    assert actual.rng.getstate() == expected.rng.getstate()
    assert actual.rng.random() == expected.rng.random()


def test_tensor_rng_sync_precedes_same_call_python_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actual = BattleState(rng=random.Random(11939))
    expected = actual.clone()
    tensor_draw = expected.rng.random()
    fallback_draw = expected.rng.random()
    observed: dict[str, float] = {}

    def consume_tensor_rng(
        state: TensorBattleState,
        ticks: int,
    ) -> torch.Tensor:
        del ticks
        observed["tensor"] = float(state.rng.random().item())
        return torch.zeros(
            (state.batch_size,), dtype=torch.int64, device=state.device
        )

    def consume_python_rng(self: BattleState, ticks: int = 1) -> int:
        observed["fallback"] = self.rng.random()
        return max(0, int(ticks))

    monkeypatch.setattr(torch_executor, "step_idle_tensor_ticks", consume_tensor_rng)
    monkeypatch.setattr(BattleState, "step_logic_ticks", consume_python_rng)

    executor = TorchBattleExecutor("pytorch")
    assert executor.step_logic_ticks(actual, 1) == 1
    assert observed == {"tensor": tensor_draw, "fallback": fallback_draw}
    assert actual.rng.getstate() == expected.rng.getstate()
    assert executor.metrics_dict()["unsupported_fallbacks"] == 1
