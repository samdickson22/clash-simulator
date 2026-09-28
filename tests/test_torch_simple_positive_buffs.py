from __future__ import annotations

from dataclasses import fields
import inspect

import pytest
import torch

from clasher.torch_sim.simple_positive_buffs import (
    FastPositiveBuffAreaCommands,
    FastPositiveBuffState,
    advance_fast_positive_buffs_,
    apply_fast_positive_area_buffs_,
    clear_stale_fast_positive_buffs_,
    fast_positive_buff_view,
)
from clasher.torch_sim.simple_state import FastGymState


@pytest.fixture(params=("cpu", "cuda"))
def tensor_device(request: pytest.FixtureRequest) -> torch.device:
    device = torch.device(str(request.param))
    if device.type == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    return device


def _state(device: torch.device, *, batch_size: int = 1) -> FastGymState:
    state = FastGymState.empty(batch_size, max_entities=4, device=device)
    state.active[:, :3] = True
    state.stable_id[:, :3] = torch.tensor(
        [11, 12, 13], dtype=torch.int64, device=device
    )
    state.owner[:, :3] = torch.tensor([0, 0, 1], dtype=torch.int8, device=device)
    state.x_units[:, :3] = torch.tensor(
        [1_000, 7_000, 1_500], dtype=torch.int32, device=device
    )
    state.y_units[:, :3] = 2_000
    state.hp[:, :3] = 100.0
    return state


def _commands(
    device: torch.device,
    *,
    owner: tuple[int, ...] = (0,),
    center_x: tuple[int, ...] = (1_000,),
    radius: tuple[int, ...] = (3_000,),
    duration: tuple[int, ...] = (20,),
    movement: tuple[float, ...] = (1.3,),
    attack: tuple[float, ...] = (1.3,),
) -> FastPositiveBuffAreaCommands:
    shape = (1, len(owner))
    return FastPositiveBuffAreaCommands(
        active=torch.ones(shape, dtype=torch.bool, device=device),
        owner=torch.tensor([owner], dtype=torch.int8, device=device),
        center_x_units=torch.tensor([center_x], dtype=torch.int32, device=device),
        center_y_units=torch.full(shape, 2_000, dtype=torch.int32, device=device),
        radius_units=torch.tensor([radius], dtype=torch.int32, device=device),
        duration_ticks=torch.tensor([duration], dtype=torch.int32, device=device),
        movement_speed_multiplier=torch.tensor(
            [movement], dtype=torch.float32, device=device
        ),
        attack_cooldown_multiplier=torch.tensor(
            [attack], dtype=torch.float32, device=device
        ),
    )


def test_serialized_area_scan_refreshes_friendly_recipient_for_twenty_ticks(
    tensor_device: torch.device,
) -> None:
    state = _state(tensor_device)
    buffs = FastPositiveBuffState.empty(1, max_entities=4, device=tensor_device)
    applied = apply_fast_positive_area_buffs_(
        state, buffs, _commands(tensor_device)
    )

    # A 5.5-second source field lives for 110 Gym ticks, but its serialized
    # one-second recipient falloff is 20 ticks and is the value this primitive
    # stores.  The future source-area owner is responsible for repeated scans.
    assert applied.touched.tolist() == [[True, False, False, False]]
    assert buffs.remaining_ticks.tolist() == [[20, 0, 0, 0]]
    view = fast_positive_buff_view(state, buffs)
    torch.testing.assert_close(
        view.movement_speed_multiplier,
        torch.tensor([[1.3, 1.0, 1.0, 1.0]], device=tensor_device),
    )
    torch.testing.assert_close(
        view.cooldown_decrement_multiplier,
        torch.tensor([[1.3, 1.0, 1.0, 1.0]], device=tensor_device),
    )

    for _ in range(19):
        result = advance_fast_positive_buffs_(state, buffs)
        assert not bool(result.expired.any())
    assert int(buffs.remaining_ticks[0, 0]) == 1
    result = advance_fast_positive_buffs_(state, buffs)
    assert result.expired.tolist() == [[True, False, False, False]]
    assert fast_positive_buff_view(
        state, buffs
    ).movement_speed_multiplier.tolist() == [[1.0, 1.0, 1.0, 1.0]]


def test_external_110_tick_area_source_repeatedly_refreshes_then_lingers(
    tensor_device: torch.device,
) -> None:
    state = _state(tensor_device)
    buffs = FastPositiveBuffState.empty(1, max_entities=4, device=tensor_device)
    scan = _commands(tensor_device, duration=(20,))

    # The serialized source owns a 5.5-second (110 tick) lifetime and scans at
    # 300 ms (six ticks).  This recipient-only primitive accepts those scans
    # but stores only the independent one-second falloff.
    for source_tick in range(110):
        if source_tick % 6 == 5:
            apply_fast_positive_area_buffs_(state, buffs, scan)
        advance_fast_positive_buffs_(state, buffs)

    assert int(buffs.remaining_ticks[0, 0]) == 17
    assert float(
        fast_positive_buff_view(state, buffs).movement_speed_multiplier[0, 0]
    ) == pytest.approx(1.3)
    for _ in range(16):
        advance_fast_positive_buffs_(state, buffs)
    assert int(buffs.remaining_ticks[0, 0]) == 1
    advance_fast_positive_buffs_(state, buffs)
    assert not bool(fast_positive_buff_view(state, buffs).active[0, 0])


def test_overlaps_use_strongest_multipliers_and_longest_refresh(
    tensor_device: torch.device,
) -> None:
    state = _state(tensor_device)
    buffs = FastPositiveBuffState.empty(1, max_entities=4, device=tensor_device)
    commands = _commands(
        tensor_device,
        owner=(0, 0, 0),
        center_x=(1_000, 1_000, 1_000),
        radius=(3_000, 3_000, 3_000),
        duration=(7, 20, 11),
        movement=(1.5, 1.2, 1.4),
        attack=(1.1, 1.3, 1.2),
    )
    first = apply_fast_positive_area_buffs_(state, buffs, commands)
    assert first.newly_applied.tolist() == [[True, False, False, False]]
    assert float(buffs.movement_speed_multiplier[0, 0]) == pytest.approx(1.5)
    assert float(buffs.attack_cooldown_multiplier[0, 0]) == pytest.approx(1.3)
    assert int(buffs.remaining_ticks[0, 0]) == 20

    for _ in range(8):
        advance_fast_positive_buffs_(state, buffs)
    refresh = apply_fast_positive_area_buffs_(
        state,
        buffs,
        _commands(
            tensor_device,
            duration=(20,),
            movement=(1.2,),
            attack=(1.1,),
        ),
    )
    assert refresh.refreshed.tolist() == [[True, False, False, False]]
    assert int(buffs.remaining_ticks[0, 0]) == 20
    assert float(buffs.movement_speed_multiplier[0, 0]) == pytest.approx(1.5)
    assert float(buffs.attack_cooldown_multiplier[0, 0]) == pytest.approx(1.3)


def test_enemy_out_of_radius_and_invalid_positive_commands_are_excluded(
    tensor_device: torch.device,
) -> None:
    state = _state(tensor_device)
    buffs = FastPositiveBuffState.empty(1, max_entities=4, device=tensor_device)
    commands = _commands(
        tensor_device,
        owner=(0, 0, 0),
        center_x=(1_000, 1_000, 1_000),
        radius=(3_000, -1, 3_000),
        duration=(20, 20, 0),
        movement=(1.3, 2.0, 2.0),
        attack=(1.3, 2.0, 2.0),
    )
    result = apply_fast_positive_area_buffs_(state, buffs, commands)

    assert result.touched.tolist() == [[True, False, False, False]]
    assert buffs.bound_stable_id.tolist() == [[11, 0, 0, 0]]


def test_death_slot_reuse_reset_rows_and_clone_replay_are_identity_safe(
    tensor_device: torch.device,
) -> None:
    state = _state(tensor_device, batch_size=2)
    commands = _commands(tensor_device)
    commands = FastPositiveBuffAreaCommands(
        **{
            descriptor.name: getattr(commands, descriptor.name).expand(2, -1).clone()
            for descriptor in fields(commands)
        }
    )
    buffs = FastPositiveBuffState.empty(2, max_entities=4, device=tensor_device)
    apply_fast_positive_area_buffs_(state, buffs, commands)
    replay = buffs.clone()

    for _ in range(4):
        advance_fast_positive_buffs_(state, buffs)
        advance_fast_positive_buffs_(state, replay)
    for descriptor in fields(buffs):
        if descriptor.name != "device":
            torch.testing.assert_close(
                getattr(buffs, descriptor.name), getattr(replay, descriptor.name)
            )

    state.active[0, 0] = False
    stale = clear_stale_fast_positive_buffs_(state, buffs)
    assert stale[0, 0]
    state.active[0, 0] = True
    state.stable_id[0, 0] = 99
    assert not fast_positive_buff_view(state, buffs).active[0, 0]
    assert float(buffs.movement_speed_multiplier[0, 0]) == 1.0
    apply_fast_positive_area_buffs_(state, buffs, commands)
    assert int(buffs.bound_stable_id[0, 0]) == 99

    buffs.reset_rows_(torch.tensor([False, True], device=tensor_device))
    assert int(buffs.remaining_ticks[0, 0]) == 20
    assert not bool(buffs.remaining_ticks[1].any())
    assert torch.equal(
        buffs.movement_speed_multiplier[1],
        torch.ones(4, dtype=torch.float32, device=tensor_device),
    )


def test_positive_buff_hot_paths_have_no_host_sync_or_card_dispatch() -> None:
    source = "\n".join(
        inspect.getsource(function)
        for function in (
            apply_fast_positive_area_buffs_,
            advance_fast_positive_buffs_,
            clear_stale_fast_positive_buffs_,
            fast_positive_buff_view,
        )
    )
    for forbidden in (".item(", ".tolist(", ".cpu(", ".nonzero("):
        assert forbidden not in source
    for card_name in ("Lumberjack", "Rage", "BarbarianRage"):
        assert card_name not in source
