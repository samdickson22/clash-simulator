from __future__ import annotations

import random
from collections import deque
from dataclasses import fields

import pytest
import torch

from clasher.battle import BattleState
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.deck_pool import load_deck_pool, unique_cards_from_decks
from clasher.torch_sim.actions import NO_OP_ACTION, TensorActionCatalog
from clasher.torch_sim.catalog import TensorCardCatalog
from clasher.torch_sim.deployment import (
    TensorCommandMaterializer,
    TensorDeploymentCatalog,
)
from clasher.torch_sim.runtime_deployment import TensorRuntimeDeployment
from clasher.torch_sim.runtime_state import (
    RuntimeEventOpcode,
    TensorBattleRuntime,
    TickPhase,
)


def _stack(
    battle: BattleState,
    *,
    device: str | torch.device = "cpu",
) -> tuple[TensorCardCatalog, TensorRuntimeDeployment]:
    cards = TensorCardCatalog.compile(
        battle.card_loader,
        unique_cards_from_decks(load_deck_pool()),
        device=device,
    )
    action_catalog = TensorActionCatalog.compile(cards)
    deployment = TensorDeploymentCatalog.compile(battle.card_loader, cards)
    return cards, TensorRuntimeDeployment(
        action_catalog,
        TensorCommandMaterializer(deployment),
    )


def _set_hand(battle: BattleState, player_id: int, first: str) -> None:
    fillers = [name for name in ("Knight", "Zap", "Cannon") if name != first]
    player = battle.players[player_id]
    player.hand = [first, *fillers][:4]
    while len(player.hand) < 4:
        player.hand.append("Fireball")
    player.deck = list(player.hand)
    player.cycle_queue = deque()
    player.elixir = 20.0


def _first_placement(
    driver: TensorRuntimeDeployment,
    runtime: TensorBattleRuntime,
    row: int,
    player: int,
) -> int:
    state = driver.action_state(runtime)
    mask = driver.kernel.legal_action_mask(state)
    placement = torch.nonzero(mask[row, player, : 18 * 32], as_tuple=False)
    assert placement.numel()
    return int(placement[0, 0].item())


def _row_tensors(runtime: TensorBattleRuntime, row: int) -> dict[str, torch.Tensor]:
    result: dict[str, torch.Tensor] = {}
    for owner_name, owner in (
        ("battle", runtime.battle),
        ("rng", runtime.battle.rng),
        ("pool", runtime.entity_pool),
        ("status", runtime.status),
        ("phases", runtime.phases),
        ("events", runtime.events),
    ):
        for descriptor in fields(owner):
            value = getattr(owner, descriptor.name)
            if (
                isinstance(value, torch.Tensor)
                and value.ndim > 0
                and value.shape[0] == runtime.batch_size
            ):
                result[f"{owner_name}.{descriptor.name}"] = value[row].clone()
    result["runtime.supported"] = runtime.supported[row].clone()
    result["runtime.dirty"] = runtime.dirty[row].clone()
    return result


def _assert_runtime_equal(
    left: TensorBattleRuntime, right: TensorBattleRuntime
) -> None:
    assert left.battle.card_names == right.battle.card_names
    for owner_name, left_owner, right_owner in (
        ("battle", left.battle, right.battle),
        ("rng", left.battle.rng, right.battle.rng),
        ("pool", left.entity_pool, right.entity_pool),
        ("status", left.status, right.status),
        ("phases", left.phases, right.phases),
    ):
        for descriptor in fields(left_owner):
            if owner_name == "phases" and descriptor.name == "dirty":
                continue
            left_value = getattr(left_owner, descriptor.name)
            right_value = getattr(right_owner, descriptor.name)
            if isinstance(left_value, torch.Tensor):
                assert torch.equal(left_value, right_value), (
                    owner_name,
                    descriptor.name,
                )


def test_action_ingress_materializes_exact_runtime_transaction() -> None:
    source = BattleState(rng=random.Random(902_441))
    _set_hand(source, 0, "Archers")
    _set_hand(source, 1, "Cannon")
    expected = source.clone()
    cards, driver = _stack(source)
    runtime = TensorBattleRuntime.from_battles(
        [source], catalog=cards, max_entities=32, event_capacity=64
    )
    driver.prepare_runtime(runtime)
    actions = torch.tensor(
        [
            [
                _first_placement(driver, runtime, 0, 0),
                _first_placement(driver, runtime, 0, 1),
            ]
        ]
    )

    action_space = DiscreteTileActionSpace(canonical_perspective=True)
    order = [0, 1]
    expected.rng.shuffle(order)
    for player in order:
        assert action_space.apply_action(expected, player, int(actions[0, player]))

    result = driver.apply(runtime, actions)
    expected_runtime = TensorBattleRuntime.from_battles(
        [expected], catalog=cards, max_entities=32, event_capacity=64
    )
    driver.prepare_runtime(expected_runtime)

    assert result.committed.tolist() == [True]
    assert result.deployment.player_order.tolist() == [order]
    assert runtime.phases.dirty[:, TickPhase.COMMANDS].tolist() == [True]
    assert runtime.events.count.tolist() == [3]
    assert runtime.events.opcode[0, :3].tolist() == [RuntimeEventOpcode.SPAWN] * 3
    spawned = runtime.entity_pool.active & (runtime.battle.entity_id >= 7)
    assert not runtime.status.stun_timer[spawned].any()
    assert (runtime.phases.target_slot[spawned] == -1).all()
    _assert_runtime_equal(runtime, expected_runtime)


def test_unsupported_row_is_atomic_including_rng_status_phase_and_events() -> None:
    sources = [
        BattleState(rng=random.Random(903_100)),
        BattleState(rng=random.Random(903_101)),
    ]
    _set_hand(sources[0], 0, "Knight")
    _set_hand(sources[1], 0, "Fireball")
    cards, driver = _stack(sources[0])
    runtime = TensorBattleRuntime.from_battles(
        sources, catalog=cards, max_entities=16, event_capacity=16
    )
    driver.prepare_runtime(runtime)
    actions = torch.tensor(
        [
            [_first_placement(driver, runtime, 0, 0), NO_OP_ACTION],
            [_first_placement(driver, runtime, 1, 0), NO_OP_ACTION],
        ]
    )
    unsupported_before = _row_tensors(runtime, 1)

    result = driver.apply(runtime, actions)

    assert result.committed.tolist() == [True, False]
    assert result.deployment.unsupported_spell.tolist() == [False, True]
    assert runtime.entity_pool.next_entity_id.tolist() == [8, 7]
    unsupported_after = _row_tensors(runtime, 1)
    assert unsupported_after.keys() == unsupported_before.keys()
    for name, expected in unsupported_before.items():
        assert torch.equal(unsupported_after[name], expected), name


def test_capacity_failure_is_row_local_and_precedes_all_mutation() -> None:
    sources = [BattleState(rng=random.Random(904_200 + row)) for row in range(2)]
    for battle in sources:
        _set_hand(battle, 0, "Archers")
    cards, driver = _stack(sources[0])
    runtime = TensorBattleRuntime.from_battles(
        sources, catalog=cards, max_entities=9, event_capacity=16
    )
    driver.prepare_runtime(runtime)
    # Row zero has only two free slots for two Archers; row one is made full.
    runtime.entity_pool.active[1, 7:] = True
    runtime.battle.entity_active[1, 7:] = True
    runtime.battle.entity_id[1, 7:] = torch.tensor([7, 8])
    runtime.entity_pool.next_entity_id[1] = 9
    runtime.assert_invariants()
    actions = torch.tensor(
        [
            [_first_placement(driver, runtime, 0, 0), NO_OP_ACTION],
            [_first_placement(driver, runtime, 1, 0), NO_OP_ACTION],
        ]
    )
    before = _row_tensors(runtime, 1)

    result = driver.apply(runtime, actions, player_order=torch.tensor([[0, 1], [0, 1]]))

    assert result.committed.tolist() == [True, False]
    assert result.unsupported_capacity.tolist() == [False, True]
    for name, expected in before.items():
        assert torch.equal(_row_tensors(runtime, 1)[name], expected), name


def test_supported_path_never_calls_python_deploy_card(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = BattleState(rng=random.Random(905_300))
    _set_hand(source, 0, "Knight")
    cards, driver = _stack(source)
    runtime = TensorBattleRuntime.from_battles([source], catalog=cards, max_entities=16)
    action = _first_placement(driver, runtime, 0, 0)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Python deploy_card entered tensor deployment")

    monkeypatch.setattr(BattleState, "deploy_card", forbidden)
    result = driver.apply(runtime, torch.tensor([[action, NO_OP_ACTION]]))

    assert result.committed.tolist() == [True]


@pytest.mark.parametrize(
    "device",
    [
        "cpu",
        pytest.param(
            "cuda",
            marks=pytest.mark.skipif(
                not torch.cuda.is_available(), reason="CUDA unavailable"
            ),
        ),
    ],
)
def test_repeated_transactions_reuse_speculative_planes_and_remain_exact(
    device: str,
) -> None:
    source = BattleState(rng=random.Random(905_700))
    _set_hand(source, 0, "Archers")
    _set_hand(source, 1, "Knight")
    expected = source.clone()
    cards, driver = _stack(source, device=device)
    runtime = TensorBattleRuntime.from_battles(
        [source],
        device=device,
        catalog=cards,
        max_entities=32,
        event_capacity=64,
    )
    action_space = DiscreteTileActionSpace(canonical_perspective=True)
    allocation_pointers: tuple[int, ...] | None = None

    for iteration in range(2):
        action = (
            _first_placement(driver, runtime, 0, 0) if iteration == 0 else NO_OP_ACTION
        )
        actions = torch.tensor([[action, NO_OP_ACTION]], device=device)
        order = [0, 1]
        expected.rng.shuffle(order)
        for player_id in order:
            assert action_space.apply_action(
                expected, player_id, int(actions[0, player_id].item())
            )

        result = driver.apply(runtime, actions)
        assert result.committed.tolist() == [True]
        speculative = driver._speculative_runtime
        assert speculative is not None
        current_pointers = (
            speculative.battle.entity_id.data_ptr(),
            speculative.battle.rng.words.data_ptr(),
            speculative.events.opcode.data_ptr(),
            speculative.status.stun_timer.data_ptr(),
        )
        if allocation_pointers is None:
            allocation_pointers = current_pointers
        else:
            assert current_pointers == allocation_pointers

    expected_runtime = TensorBattleRuntime.from_battles(
        [expected],
        device=device,
        catalog=cards,
        max_entities=32,
        event_capacity=64,
    )
    driver.prepare_runtime(expected_runtime)
    _assert_runtime_equal(runtime, expected_runtime)
    assert runtime.events.count.tolist() == [2]


def test_internal_transaction_bypasses_redundant_checked_boundaries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = BattleState(rng=random.Random(905_800))
    _set_hand(source, 0, "Knight")
    cards, driver = _stack(source)
    runtime = TensorBattleRuntime.from_battles(
        [source], catalog=cards, max_entities=16, event_capacity=16
    )
    no_op = torch.tensor([[NO_OP_ACTION, NO_OP_ACTION]])
    assert driver.apply(runtime, no_op).committed.tolist() == [True]
    speculative = driver._speculative_runtime
    assert speculative is not None

    def forbidden(*_args, **_kwargs):
        raise AssertionError("checked/allocation boundary entered retained fast path")

    monkeypatch.setattr(runtime, "clone", forbidden)
    monkeypatch.setattr(runtime, "assert_invariants", forbidden)
    monkeypatch.setattr(speculative, "assert_invariants", forbidden)
    monkeypatch.setattr(driver.materializer, "_validate_commands", forbidden)
    monkeypatch.setattr(speculative.entity_pool, "allocate", forbidden)
    monkeypatch.setattr(speculative.events, "append", forbidden)

    result = driver.apply(runtime, no_op)

    assert result.committed.tolist() == [True]
    assert driver._speculative_runtime is speculative


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA unavailable")
def test_cuda_runtime_ingress_materialization_stays_on_device(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = BattleState(rng=random.Random(906_400))
    _set_hand(source, 0, "Archers")
    cards, driver = _stack(source, device="cuda")
    runtime = TensorBattleRuntime.from_battles(
        [source], device="cuda", catalog=cards, max_entities=32
    )
    action = _first_placement(driver, runtime, 0, 0)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Python deploy_card entered CUDA deployment")

    monkeypatch.setattr(BattleState, "deploy_card", forbidden)
    result = driver.apply(
        runtime,
        torch.tensor([[action, NO_OP_ACTION]], device="cuda"),
    )

    assert result.committed.is_cuda
    assert result.legal_mask.is_cuda
    assert result.ingress.commands.card_id.is_cuda
    assert result.deployment.allocation.entity_ids.is_cuda
    assert runtime.battle.entity_id.is_cuda
    assert result.committed.tolist() == [True]
