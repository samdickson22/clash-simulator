from __future__ import annotations

import inspect
from copy import deepcopy
from dataclasses import fields, replace

import pytest
import torch

from clasher.data import CardDataLoader
from clasher.torch_sim.catalog import MECHANIC_OPCODE, TensorCardCatalog
from clasher.torch_sim.simple_abilities import (
    FastAbilityCatalog,
    FastAbilityState,
    activate_fast_abilities_,
    fast_ability_player_view,
    refresh_fast_abilities_,
    step_fast_abilities_,
)
from clasher.torch_sim.simple_actions import FastActionState
from clasher.torch_sim.simple_state import FAST_KIND_TROOP, FastGymState


def _device(requested: str) -> str:
    if requested == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    return requested


def _catalog(
    device: str = "cpu",
) -> tuple[CardDataLoader, TensorCardCatalog, FastAbilityCatalog]:
    loader = CardDataLoader()
    tensor = TensorCardCatalog.compile(
        loader,
        ("ArcherQueen", "Knight", "SkeletonKing"),
        device=device,
    )
    return loader, tensor, FastAbilityCatalog.compile(tensor, loader)


def _spawn(
    state: FastGymState,
    tensor: TensorCardCatalog,
    *,
    slot: int,
    stable_id: int,
    player: int,
    card_name: str = "ArcherQueen",
) -> None:
    state.active[:, slot] = True
    state.stable_id[:, slot] = stable_id
    state.kind[:, slot] = FAST_KIND_TROOP
    state.owner[:, slot] = player
    state.card_id[:, slot] = tensor.name_to_id[card_name]
    state.hp[:, slot] = 1_000.0
    state.max_hp[:, slot] = 1_000.0


def _elixir(state: FastGymState, amount: float = 10.0) -> torch.Tensor:
    return torch.full(
        (state.batch_size, 2), amount, dtype=torch.float32, device=state.device
    )


def test_serialized_archer_queen_profile_is_exact_at_50_ms() -> None:
    _, tensor, catalog = _catalog()
    queen = tensor.name_to_id["ArcherQueen"]
    skeleton_king = tensor.name_to_id["SkeletonKing"]

    assert catalog.supported.tolist() == [False, True, False, False]
    assert catalog.profile_card_id[queen].item() == queen
    assert catalog.mechanic_opcode[queen].item() == MECHANIC_OPCODE["ArcherQueenCloak"]
    assert catalog.elixir_cost[queen].item() == 1
    assert catalog.trigger_delay_ticks[queen].item() == 4
    assert catalog.cast_time_ticks[queen].item() == 19
    assert catalog.duration_ticks[queen].item() == 70
    assert catalog.cooldown_ticks[queen].item() == 340
    assert catalog.attack_speed_multiplier[queen].item() == pytest.approx(2.8)
    assert catalog.movement_speed_multiplier[queen].item() == pytest.approx(0.75)
    # A nested summon payload has an ability opcode but no dense payload
    # kernel yet.  It is diagnosed and fails closed instead of borrowing the
    # cloak profile or collapsing the typed card identity.
    assert not catalog.supported[skeleton_king].item()
    assert catalog.malformed[skeleton_king].item()
    assert catalog.profile_card_id[skeleton_king].item() == 0


@pytest.mark.parametrize("requested_device", ("cpu", "cuda"))
def test_newest_live_typed_champion_owns_each_player_button(
    requested_device: str,
) -> None:
    device = _device(requested_device)
    _, tensor, catalog = _catalog(device)
    state = FastGymState.empty(1, max_entities=5, device=device)
    abilities = FastAbilityState.empty_like(state)
    _spawn(state, tensor, slot=0, stable_id=5, player=0)
    _spawn(state, tensor, slot=1, stable_id=19, player=0)
    _spawn(state, tensor, slot=2, stable_id=7, player=1)
    _spawn(state, tensor, slot=3, stable_id=99, player=0, card_name="Knight")

    view = fast_ability_player_view(state, abilities, catalog, elixir=_elixir(state))

    assert view.owner_stable_id.tolist() == [[19, 7]]
    assert view.owner_card_id.tolist() == [
        [tensor.name_to_id["ArcherQueen"], tensor.name_to_id["ArcherQueen"]]
    ]
    assert view.legal.tolist() == [[True, True]]
    assert abilities.bound_stable_id.tolist() == [[5, 19, 7, 0, 0]]
    assert (
        abilities.bound_card_id[0, :3].tolist()
        == [tensor.name_to_id["ArcherQueen"]] * 3
    )

    # Frozen/stunned Champions retain their button under the current native
    # global, while placement, elixir, and player liveness remain hard gates.
    stunned = torch.zeros_like(state.active)
    stunned[0, 1] = True
    assert fast_ability_player_view(
        state, abilities, catalog, elixir=_elixir(state), stunned=stunned
    ).legal.tolist() == [[True, True]]
    state.deploy_ticks[0, 1] = 1
    assert fast_ability_player_view(
        state, abilities, catalog, elixir=_elixir(state), stunned=stunned
    ).legal.tolist() == [[False, True]]
    state.deploy_ticks[0, 1] = 0
    alive = torch.tensor([[True, False]], dtype=torch.bool, device=state.device)
    poor = torch.tensor([[0.0, 10.0]], device=state.device)
    assert fast_ability_player_view(
        state,
        abilities,
        catalog,
        elixir=poor,
        stunned=stunned,
        player_alive=alive,
    ).legal.tolist() == [[False, False]]


def test_activation_returns_atomic_spend_intent_without_rotating_hand() -> None:
    _, tensor, catalog = _catalog()
    state = FastGymState.empty(1, max_entities=3)
    abilities = FastAbilityState.empty_like(state)
    _spawn(state, tensor, slot=1, stable_id=41, player=0)
    decks = torch.tensor(
        [
            [
                [1, 2, 3, 4, 5, 6, 7, 8],
                [8, 7, 6, 5, 4, 3, 2, 1],
            ]
        ],
        dtype=torch.int64,
    )
    action_state = FastActionState.from_decks(decks)
    before = action_state.clone()

    result = activate_fast_abilities_(
        state,
        abilities,
        catalog,
        torch.tensor([[True, True]]),
        elixir=action_state.elixir,
    )

    assert result.activated.tolist() == [[True, False]]
    assert result.elixir_delta.tolist() == [[-1.0, 0.0]]
    assert result.owner_stable_id.tolist() == [[41, 0]]
    assert result.owner_card_id.tolist() == [[tensor.name_to_id["ArcherQueen"], 0]]
    assert torch.equal(action_state.hand_ids, before.hand_ids)
    assert torch.equal(action_state.cycle_ids, before.cycle_ids)
    assert torch.equal(action_state.cycle_head, before.cycle_head)
    assert torch.equal(action_state.elixir, before.elixir)
    assert "hand" not in inspect.signature(activate_fast_abilities_).parameters
    assert "cycle" not in inspect.signature(activate_fast_abilities_).parameters


@pytest.mark.parametrize("requested_device", ("cpu", "cuda"))
def test_trigger_cast_duration_and_cooldown_boundaries(
    requested_device: str,
) -> None:
    device = _device(requested_device)
    _, tensor, catalog = _catalog(device)
    state = FastGymState.empty(1, max_entities=2, device=device)
    abilities = FastAbilityState.empty_like(state)
    _spawn(state, tensor, slot=0, stable_id=11, player=0)
    elixir = _elixir(state, 6.0)
    activation = activate_fast_abilities_(
        state,
        abilities,
        catalog,
        torch.tensor([[True, False]], device=state.device),
        elixir=elixir,
    )
    elixir.add_(activation.elixir_delta)

    expected = {
        # tick: pending, cast lock, effect, attack, move, legal, cd, duration
        0: (True, True, False, 1.0, 1.0, False, 1.0, 0.0),
        3: (True, True, False, 1.0, 1.0, False, 1.0, 0.0),
        4: (False, True, True, 2.8, 0.75, False, 1.0, 1.0),
        18: (False, True, True, 2.8, 0.75, False, 1.0, 56 / 70),
        19: (False, False, True, 2.8, 0.75, False, 1.0, 55 / 70),
        73: (False, False, True, 2.8, 0.75, False, 1.0, 1 / 70),
        74: (False, False, False, 1.0, 1.0, False, 1.0, 0.0),
        413: (False, False, False, 1.0, 1.0, False, 1 / 340, 0.0),
        414: (False, False, False, 1.0, 1.0, True, 0.0, 0.0),
    }
    for tick, values in expected.items():
        state.tick.fill_(tick)
        result = step_fast_abilities_(state, abilities, catalog, elixir=elixir)
        pending, locked, active, attack, move, legal, cooldown, duration = values
        assert result.pending[0, 0].item() is pending
        assert result.cast_locked[0, 0].item() is locked
        assert result.effect_active[0, 0].item() is active
        assert result.attack_speed_multiplier[0, 0].item() == pytest.approx(attack)
        assert result.movement_speed_multiplier[0, 0].item() == pytest.approx(move)
        assert result.player.legal[0, 0].item() is legal
        assert result.player.cooldown_fraction[0, 0].item() == pytest.approx(cooldown)
        assert result.player.duration_fraction[0, 0].item() == pytest.approx(duration)


def test_death_cancels_owner_and_returning_older_copy_resets_cooldown() -> None:
    _, tensor, catalog = _catalog()
    state = FastGymState.empty(1, max_entities=3)
    abilities = FastAbilityState.empty_like(state)
    _spawn(state, tensor, slot=0, stable_id=5, player=0)
    elixir = _elixir(state)
    activate_fast_abilities_(
        state,
        abilities,
        catalog,
        torch.tensor([[True, False]]),
        elixir=elixir,
    )

    state.tick.fill_(4)
    _spawn(state, tensor, slot=1, stable_id=9, player=0)
    newest = step_fast_abilities_(state, abilities, catalog, elixir=elixir)
    assert newest.player.owner_stable_id.tolist() == [[9, 0]]
    assert newest.player.legal.tolist() == [[True, False]]
    # Ownership transfer does not strip the running effect from the old troop.
    assert newest.effect_active.tolist() == [[True, False, False]]

    activate_fast_abilities_(
        state,
        abilities,
        catalog,
        torch.tensor([[True, False]]),
        elixir=elixir,
    )
    assert abilities.cooldown_armed[0, 1].item()
    state.tick.fill_(5)
    state.hp[0, 1] = 0
    state.active[0, 1] = False
    returned = step_fast_abilities_(state, abilities, catalog, elixir=elixir)
    assert returned.player.owner_stable_id.tolist() == [[5, 0]]
    assert not abilities.cooldown_armed[0, 0].item()
    assert abilities.bound_stable_id[0, 1].item() == 0
    assert abilities.duration_end_tick[0, 1].item() == 0
    assert not returned.player.legal[0, 0].item()  # old effect still active
    assert returned.player.cooldown_fraction[0, 0].item() == 0.0

    state.tick.fill_(74)
    ready = step_fast_abilities_(state, abilities, catalog, elixir=elixir)
    assert ready.player.legal.tolist() == [[True, False]]


def test_slot_reuse_row_reset_and_seeded_replay_clear_all_stale_state() -> None:
    _, tensor, catalog = _catalog()

    def trace() -> tuple[torch.Tensor, ...]:
        state = FastGymState.empty(2, max_entities=2)
        abilities = FastAbilityState.empty_like(state)
        _spawn(state, tensor, slot=0, stable_id=3, player=0)
        activate_fast_abilities_(
            state,
            abilities,
            catalog,
            torch.tensor([[True, False], [True, False]]),
            elixir=_elixir(state),
        )
        state.tick[:] = torch.tensor([9, 17])
        first = step_fast_abilities_(state, abilities, catalog, elixir=_elixir(state))
        abilities.reset_rows_(torch.tensor([False, True]))
        state.stable_id[0, 0] = 77
        rebound = refresh_fast_abilities_(state, abilities, catalog)
        return (
            first.effect_active.clone(),
            first.cast_locked.clone(),
            abilities.bound_stable_id.clone(),
            abilities.bound_card_id.clone(),
            abilities.trigger_tick.clone(),
            abilities.cast_end_tick.clone(),
            abilities.duration_end_tick.clone(),
            abilities.cooldown_end_tick.clone(),
            abilities.cooldown_armed.clone(),
            abilities.newest_owner_stable_id.clone(),
            rebound.rebound.clone(),
        )

    first = trace()
    second = trace()
    assert all(
        torch.equal(left, right) for left, right in zip(first, second, strict=True)
    )
    # Row zero's physical slot was reused and rebound without inherited
    # deadlines; row one was reset wholesale for a fresh episode.
    assert first[2].tolist() == [[77, 0], [3, 0]]
    for value in first[4:9]:
        assert not value.any().item()
    assert first[9].tolist() == [[77, 0], [3, 0]]
    assert first[10].tolist() == [[True, False], [True, False]]


def test_malformed_and_duplicate_serialized_profiles_fail_closed() -> None:
    loader, tensor, _ = _catalog()
    queen = tensor.name_to_id["ArcherQueen"]
    stats = loader.get_card("ArcherQueen")
    assert stats is not None
    stats._raw_entry = deepcopy(stats._raw_entry)
    stats._raw_entry["summonCharacterData"]["abilityData"]["buffData"][
        "hitSpeedMultiplier"
    ] = "fast"
    malformed = FastAbilityCatalog.compile(tensor, loader)
    assert malformed.malformed[queen].item()
    assert not malformed.supported[queen].item()
    assert malformed.elixir_cost[queen].item() == 0
    assert malformed.attack_speed_multiplier[queen].item() == 1.0

    opcode = torch.cat(
        (tensor.mechanic_opcode, torch.zeros_like(tensor.mechanic_opcode[:, :1])),
        dim=1,
    )
    opcode[queen, 1] = MECHANIC_OPCODE["ArcherQueenCloak"]
    parameters = torch.cat(
        (
            tensor.mechanic_parameters,
            torch.full_like(tensor.mechanic_parameters[:, :1], torch.nan),
        ),
        dim=1,
    )
    parameters[queen, 1] = tensor.mechanic_parameters[queen, 0]
    nested = torch.cat(
        (
            tensor.mechanic_nested_payload,
            torch.zeros_like(tensor.mechanic_nested_payload[:, :1]),
        ),
        dim=1,
    )
    duplicate_tensor = replace(
        tensor,
        mechanic_opcode=opcode,
        mechanic_parameters=parameters,
        mechanic_nested_payload=nested,
    )
    duplicate = FastAbilityCatalog.compile(duplicate_tensor, CardDataLoader())
    assert duplicate.duplicate[queen].item()
    assert duplicate.malformed[queen].item()
    assert not duplicate.supported[queen].item()
    assert duplicate.profile_card_id[queen].item() == 0


def test_ability_hot_paths_are_tensor_only_and_card_name_free() -> None:
    hot_paths = (
        refresh_fast_abilities_,
        fast_ability_player_view,
        activate_fast_abilities_,
        step_fast_abilities_,
    )
    for function in hot_paths:
        source = inspect.getsource(function)
        for forbidden in (".item(", ".tolist(", ".cpu(", ".nonzero("):
            assert forbidden not in source
        for card_name in ("ArcherQueen", "SkeletonKing"):
            assert card_name not in source


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA unavailable")
def test_step_is_cuda_graph_capturable() -> None:
    _, tensor, catalog = _catalog("cuda")
    state = FastGymState.empty(1, max_entities=2, device="cuda")
    abilities = FastAbilityState.empty_like(state)
    _spawn(state, tensor, slot=0, stable_id=17, player=0)
    elixir = _elixir(state)
    stunned = torch.zeros_like(state.active)
    alive = torch.ones((1, 2), dtype=torch.bool, device=state.device)
    activate_fast_abilities_(
        state,
        abilities,
        catalog,
        torch.tensor([[True, False]], device=state.device),
        elixir=elixir,
        stunned=stunned,
        player_alive=alive,
    )
    state.tick.fill_(4)

    stream = torch.cuda.Stream()
    stream.wait_stream(torch.cuda.current_stream())
    with torch.cuda.stream(stream):
        for _ in range(3):
            step_fast_abilities_(
                state,
                abilities,
                catalog,
                elixir=elixir,
                stunned=stunned,
                player_alive=alive,
            )
    torch.cuda.current_stream().wait_stream(stream)
    graph = torch.cuda.CUDAGraph()
    with torch.cuda.graph(graph):
        captured = step_fast_abilities_(
            state,
            abilities,
            catalog,
            elixir=elixir,
            stunned=stunned,
            player_alive=alive,
        )
    graph.replay()
    assert captured.effect_active[0, 0].item()
    assert captured.attack_speed_multiplier[0, 0].item() == pytest.approx(2.8)


def test_state_contract_is_fixed_entity_and_player_shaped() -> None:
    state = FastGymState.empty(3, max_entities=7)
    abilities = FastAbilityState.empty_like(state)
    for descriptor in fields(abilities):
        if descriptor.name == "device":
            continue
        expected = (3, 2) if descriptor.name == "newest_owner_stable_id" else (3, 7)
        assert getattr(abilities, descriptor.name).shape == expected
