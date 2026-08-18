from __future__ import annotations

import inspect
import random
from collections import deque
from collections.abc import Iterator

import pytest
import torch

from clasher.battle import BattleState
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.resident_selfplay import TensorResidentSelfPlay


@pytest.fixture(params=("cpu", "cuda"))
def tensor_device(request: pytest.FixtureRequest) -> Iterator[str]:
    device = str(request.param)
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA is unavailable on this host")
    yield device


def _mixed_battle(seed: int, character: str) -> BattleState:
    battle = BattleState(fast_path=False, rng=random.Random(seed))
    battle.players[0].hand = [character, None, None, None]
    battle.players[0].deck = [character]
    battle.players[0].cycle_queue = deque()
    battle.players[0].elixir = 10.0
    battle.players[1].hand = ["Zap", None, None, None]
    battle.players[1].deck = ["Zap"]
    battle.players[1].cycle_queue = deque()
    battle.players[1].elixir = 10.0
    return battle


def _safe_empty(seed: int) -> BattleState:
    battle = BattleState(fast_path=False, rng=random.Random(seed))
    for player in battle.players:
        player.hand = [None, None, None, None]
        player.deck = []
        player.cycle_queue = deque()
        player.elixir = 5.0
    return battle


def _actions(device: torch.device | str, rows: int = 2) -> torch.Tensor:
    space = DiscreteTileActionSpace(canonical_perspective=True)
    mixed = [
        space.encode_action(0, 9, 10, 0),
        space.encode_action(0, 9, 10, 1),
    ]
    values = [mixed for _ in range(rows)]
    return torch.tensor(values, dtype=torch.int64, device=device)


def _slot_for_id(bridge: TensorResidentSelfPlay, row: int, entity_id: int) -> int:
    slots = torch.where(bridge.engine.runtime.battle.entity_id[row] == entity_id)[0]
    assert slots.numel() == 1
    return int(slots[0].item())


def test_episode_admission_accepts_safe_mixed_spell_rows() -> None:
    bridge = TensorResidentSelfPlay.from_battles(
        [_mixed_battle(81_001, "Knight"), _mixed_battle(81_002, "Cannon")],
        decision_interval_ticks=1,
        max_ticks=20,
        max_entities=24,
        max_objects=8,
    )

    assert bridge._episode_resident.tolist() == [True, True]
    assert bridge._episode_route_reasons == [None, None]


def test_batched_mixed_decision_card_timeline_and_delayed_visible_effect(
    tensor_device: str,
) -> None:
    sources = [
        _mixed_battle(82_001, "Knight"),
        _mixed_battle(82_002, "Cannon"),
        BattleState(fast_path=False, rng=random.Random(82_003)),
    ]
    bridge = TensorResidentSelfPlay.from_battles(
        sources,
        device=tensor_device,
        decision_interval_ticks=1,
        max_ticks=20,
        max_entities=32,
        max_objects=8,
        event_capacity=256,
        include_privileged_critic=True,
    )
    assert bridge._episode_resident.tolist() == [True, True, False]
    fallback_ids = bridge.engine.runtime.battle.entity_id[2].clone()
    fallback_rng = bridge.engine.runtime.battle.rng.python_state(2)
    expected_rng = [random.Random(), random.Random()]
    for row, rng in enumerate(expected_rng):
        rng.setstate(sources[row].rng.getstate())
    expected_order: list[list[int]] = []
    for rng in expected_rng:
        order = [0, 1]
        rng.shuffle(order)
        expected_order.append(order)

    actions = torch.cat(
        (
            _actions(bridge.device),
            torch.full(
                (1, 2),
                NO_OP_ACTION,
                dtype=torch.int64,
                device=bridge.device,
            ),
        ),
        dim=0,
    )
    first = bridge.step(actions)

    assert first.observation_valid.tolist() == [True, True, False]
    assert first.fallback.mask.tolist() == [False, False, True]
    assert first.fallback.row_indices.tolist() == [2]
    assert first.ticks_advanced.tolist() == [1, 1, 0]
    assert first.action_success.tolist() == [
        [True, True],
        [True, True],
        [False, False],
    ]
    assert first.player_order[:2].tolist() == expected_order
    assert first.public.events.valid[:2, :, :2].all().item()
    assert first.public.events.play_time_seconds[:2, :, :2].tolist() == [
        [[0.05, 0.05], [0.05, 0.05]],
        [[0.05, 0.05], [0.05, 0.05]],
    ]
    assert first.privileged_critic is not None
    assert not hasattr(first.public.structured, "critic_card_ids")
    assert first.privileged_critic.card_ids.shape[:2] == (3, 2)
    assert torch.isfinite(first.rewards).all()
    assert torch.equal(first.rewards[:, 0], -first.rewards[:, 1])
    assert not first.dones.any()
    assert first.action_masks[:2, :, NO_OP_ACTION].all().item()
    assert first.action_masks[:2, :, :NO_OP_ACTION].any(dim=2).all().item()
    assert bridge.engine.runtime.battle.tick[2].item() == 0
    assert torch.equal(bridge.engine.runtime.battle.entity_id[2], fallback_ids)
    assert bridge.engine.runtime.battle.rng.python_state(2) == fallback_rng

    core = bridge.engine.runtime.battle
    deployed_ids = [7, 7]
    deployed_slots = [
        _slot_for_id(bridge, row, entity_id)
        for row, entity_id in enumerate(deployed_ids)
    ]
    initial_hp = [
        core.entity_hp[row, slot].item() for row, slot in enumerate(deployed_slots)
    ]
    initial_features = first.public.structured.entity_features[:2].clone()
    assert bridge.engine.pending_spells.active[:2].sum(dim=1).tolist() == [1, 1]

    last = first
    noops = torch.full_like(actions, NO_OP_ACTION)
    for _ in range(19):
        next_orders: list[list[int]] = []
        for rng in expected_rng:
            order = [0, 1]
            rng.shuffle(order)
            next_orders.append(order)
        last = bridge.step(noops)
        assert last.player_order[:2].tolist() == next_orders

    assert bridge.engine.pending_spells.active[:2].sum(dim=1).tolist() == [0, 0]
    for row, slot in enumerate(deployed_slots):
        assert core.entity_hp[row, slot].item() < initial_hp[row]
        assert bridge.engine.runtime.status.stun_timer[row, slot].item() > 0.0
        assert bridge.engine.runtime.battle.rng.python_state(row) == (
            expected_rng[row].getstate()
        )
    assert not last.public.events.valid.any()
    assert last.rewards[2].tolist() == [0.0, 0.0]
    assert bridge.engine.runtime.battle.tick[2].item() == 0
    assert torch.equal(bridge.engine.runtime.battle.entity_id[2], fallback_ids)
    assert bridge.engine.runtime.battle.rng.python_state(2) == fallback_rng
    assert not torch.equal(last.public.structured.entity_features[:2], initial_features)


def test_selective_reset_clears_only_selected_pending_spell_row(
    tensor_device: str,
) -> None:
    sources = [
        _mixed_battle(83_001, "Knight"),
        _mixed_battle(83_002, "Cannon"),
    ]
    bridge = TensorResidentSelfPlay.from_battles(
        sources,
        device=tensor_device,
        decision_interval_ticks=1,
        max_ticks=20,
        max_entities=24,
        max_objects=8,
        event_capacity=128,
        include_privileged_critic=True,
    )
    assert bridge._episode_resident.tolist() == [True, True]
    first = bridge.step(_actions(bridge.device))
    assert first.action_success.tolist() == [[True, True], [True, True]]
    assert bridge.engine.pending_spells.active.sum(dim=1).tolist() == [1, 1]
    row_one_ids = bridge.engine.runtime.battle.entity_id[1].clone()
    row_one_rng = bridge.engine.runtime.battle.rng.python_state(1)

    fresh = _safe_empty(83_101)
    ignored = _safe_empty(83_102)
    public, critic, masks = bridge.reset_rows(
        [fresh, ignored],
        torch.tensor([True, False], device=bridge.device),
    )

    assert bridge.engine.pending_spells.active.sum(dim=1).tolist() == [0, 1]
    assert torch.equal(bridge.engine.runtime.battle.entity_id[1], row_one_ids)
    assert bridge.engine.runtime.battle.rng.python_state(1) == row_one_rng
    assert bridge.engine.runtime.battle.tick.tolist() == [0, 1]
    assert public.structured.entity_ids.shape[:2] == (2, 2)
    assert critic is not None
    assert masks[:, :, NO_OP_ACTION].all().item()


def test_selfplay_step_reuses_masks_and_defers_host_diagnostics() -> None:
    source = inspect.getsource(TensorResidentSelfPlay.step)
    loop = source[source.index("for logic_tick") : source.index("if bool(failed_any")]
    assert ".item(" not in loop
    assert ".tolist(" not in loop
    assert "first_legal = self.engine.deployment" not in source
    assert "action_masks = post_mask" in source
