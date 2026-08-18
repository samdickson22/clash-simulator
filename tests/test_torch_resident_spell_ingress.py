from __future__ import annotations

import copy
import inspect
from collections import deque
from collections.abc import Iterator

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import AreaEffect, Projectile, SpawnProjectile, TargetType, Troop
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.spells import SPELL_REGISTRY
from clasher.torch_sim import resident_spell_ingress
from clasher.torch_sim.actions import (
    NO_OP_ACTION,
    TensorActionCatalog,
    TensorActionKernel,
    TensorActionState,
)
from clasher.torch_sim.catalog import TensorCardCatalog
from clasher.torch_sim.resident_engine import _resident_deployment_catalog_closure
from clasher.torch_sim.resident_spell_ingress import TensorResidentSpellActionIngress
from clasher.torch_sim.runtime_objects import TensorRuntimeObjectPhase
from clasher.torch_sim.runtime_state import TensorBattleRuntime


@pytest.fixture(params=("cpu", "cuda"))
def tensor_device(request: pytest.FixtureRequest) -> Iterator[str]:
    device = str(request.param)
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA is unavailable on this host")
    yield device


def _troop(
    battle: BattleState,
    entity_id: int,
    player_id: int,
    position: Position,
    *,
    hp: float = 5_000,
) -> Troop:
    stats = battle.card_loader.get_card("Knight")
    assert stats is not None
    entity = Troop(
        id=entity_id,
        position=position,
        player_id=player_id,
        card_stats=stats,
        hitpoints=hp,
        max_hitpoints=hp,
        damage=float(stats.scaled_damage or stats.damage or 0),
        range=float(stats.range or 0),
        sight_range=float(stats.sight_range or 0),
        speed=0,
        target_type=TargetType.BOTH,
    )
    entity._spawn_hook_pending = False
    entity._spawn_hook_fired = True
    entity.battle_state = battle  # type: ignore[attr-defined]
    return entity


def _spell_battle(
    spell_name: str,
    *,
    two_targets: bool = False,
) -> BattleState:
    battle = BattleState(fast_path=False)
    targets = [_troop(battle, 1, 1, Position(9.5, 14.5))]
    if two_targets:
        targets.append(_troop(battle, 2, 0, Position(8.5, 17.5)))
    battle.entities = {entity.id: entity for entity in targets}
    battle.next_entity_id = len(targets) + 1
    for entity in targets:
        entity.battle_state = battle  # type: ignore[attr-defined]
    for player in battle.players:
        player.hand = [spell_name, "Knight", None, None]
        player.deck = [spell_name, "Knight", "Archer"]
        player.cycle_queue = deque(["Archer"])
        player.elixir = 10.0
    return battle


def _owners(
    battles: list[BattleState],
    names: set[str],
    *,
    device: str,
    max_objects: int = 80,
) -> tuple[
    TensorCardCatalog,
    TensorActionKernel,
    TensorActionState,
    TensorBattleRuntime,
    TensorRuntimeObjectPhase,
    TensorResidentSpellActionIngress,
]:
    loader, closure = _resident_deployment_catalog_closure(
        battles[0].card_loader, names
    )
    cards = TensorCardCatalog.compile(loader, closure, device=device)
    action_catalog = TensorActionCatalog.compile(cards)
    kernel = TensorActionKernel(action_catalog)
    action_state = TensorActionState.from_battles(battles, action_catalog)
    runtime = TensorBattleRuntime.from_battles(
        battles,
        catalog=cards,
        device=device,
        max_entities=96,
        event_capacity=8_192,
    )
    objects = TensorRuntimeObjectPhase.from_battles(
        runtime, battles, max_objects=max_objects
    )
    ingress = TensorResidentSpellActionIngress.from_battles(
        runtime, objects, battles, cards
    )
    return cards, kernel, action_state, runtime, objects, ingress


def _cast_oracle(
    battle: BattleState,
    player_id: int,
    spell_name: str,
    position: Position,
) -> None:
    stats = battle.card_loader.get_card(spell_name)
    assert stats is not None
    assert battle.players[player_id].play_card(spell_name, stats)
    assert SPELL_REGISTRY[spell_name].cast(battle, player_id, position)


def _assert_player_transition(
    oracle: BattleState,
    runtime: TensorBattleRuntime,
    player_id: int,
) -> None:
    expected_hand = [
        runtime.battle.card_to_id.get(name or "", 0)
        for name in oracle.players[player_id].hand
    ]
    expected_cycle = [
        runtime.battle.card_to_id[name]
        for name in oracle.players[player_id].cycle_queue
    ]
    assert runtime.battle.hand[0, player_id].tolist() == expected_hand
    assert runtime.battle.cycle_queue_length[0, player_id].item() == len(expected_cycle)
    assert (
        runtime.battle.cycle_queue[0, player_id, : len(expected_cycle)].tolist()
        == expected_cycle
    )
    assert runtime.battle.elixir[0, player_id].item() == (
        oracle.players[player_id].elixir
    )


@pytest.mark.parametrize(
    "spell_name",
    ("Zap", "Fireball", "Arrows", "GoblinBarrel", "GlobalLightning"),
)
def test_spell_ingress_exact_immediate_materialization_matches_python(
    tensor_device: str,
    spell_name: str,
) -> None:
    battle = _spell_battle(spell_name)
    oracle = copy.deepcopy(battle)
    _, kernel, state, runtime, objects, driver = _owners(
        [battle],
        {spell_name, "Knight", "Archer"},
        device=tensor_device,
    )
    action_space = DiscreteTileActionSpace(canonical_perspective=True)
    action_id = action_space.encode_action(0, 9, 14, 0)
    tensor_ingress = kernel.ingress(
        state,
        torch.tensor([[action_id, NO_OP_ACTION]], device=runtime.device),
    )
    result = driver.apply(
        tensor_ingress,
        player_order=torch.tensor([[0, 1]], device=runtime.device),
    )
    _cast_oracle(oracle, 0, spell_name, Position(9.5, 14.5))

    assert result.committed.tolist() == [True]
    assert result.action_success.tolist() == [[True, True]]
    assert result.unsupported_reasons == (None,)
    _assert_player_transition(oracle, runtime, 0)
    assert runtime.battle.rng.python_state(0) == oracle.rng.getstate()
    assert runtime.battle.entity_hp[0, 0].item() == oracle.entities[1].hitpoints
    assert runtime.status.stun_timer[0, 0].item() == oracle.entities[1].stun_timer

    python_objects = [
        entity
        for entity in oracle.entities.values()
        if isinstance(entity, (AreaEffect, Projectile, SpawnProjectile))
    ]
    live = objects.objects.allocated[0]
    assert int(live.sum().item()) == len(python_objects)
    if python_objects:
        assert objects.objects.object_id[0, live].tolist() == [
            entity.id for entity in python_objects
        ]
        assert objects.objects.target_x_units[0, live].tolist() == [
            round(getattr(entity, "target_position", entity.position).x * 1_000)
            for entity in python_objects
        ]
        assert objects.objects.target_y_units[0, live].tolist() == [
            round(getattr(entity, "target_position", entity.position).y * 1_000)
            for entity in python_objects
        ]
        assert objects.objects.launch_delay_ms[0, live].tolist() == [
            round(float(getattr(entity, "launch_delay", 0.0)) * 1_000)
            for entity in python_objects
        ]


def test_simultaneous_players_consume_shuffle_rng_and_execute_in_oracle_order(
    tensor_device: str,
) -> None:
    battle = _spell_battle("Zap", two_targets=True)
    oracle = copy.deepcopy(battle)
    _, kernel, state, runtime, _, driver = _owners(
        [battle], {"Zap", "Knight", "Archer"}, device=tensor_device
    )
    action_space = DiscreteTileActionSpace(canonical_perspective=True)
    actions = torch.tensor(
        [
            [
                action_space.encode_action(0, 9, 14, 0),
                action_space.encode_action(0, 8, 17, 1),
            ]
        ],
        device=runtime.device,
    )
    tensor_ingress = kernel.ingress(state, actions)
    result = driver.apply(tensor_ingress)

    order = [0, 1]
    oracle.rng.shuffle(order)
    for player_id in order:
        target = Position(9.5, 14.5) if player_id == 0 else Position(8.5, 17.5)
        _cast_oracle(oracle, player_id, "Zap", target)

    assert result.committed.tolist() == [True]
    assert result.player_order[0].tolist() == order
    assert runtime.battle.rng.python_state(0) == oracle.rng.getstate()
    for player_id in (0, 1):
        _assert_player_transition(oracle, runtime, player_id)
    assert runtime.battle.entity_hp[0, :2].tolist() == [
        oracle.entities[1].hitpoints,
        oracle.entities[2].hitpoints,
    ]


def test_mixed_nonspell_row_falls_back_without_any_partial_mutation() -> None:
    spell = _spell_battle("Zap")
    nonspell = _spell_battle("Knight")
    _, kernel, state, runtime, objects, driver = _owners(
        [spell, nonspell],
        {"Zap", "Knight", "Archer"},
        device="cpu",
    )
    action_space = DiscreteTileActionSpace(canonical_perspective=True)
    actions = torch.tensor(
        [
            [action_space.encode_action(0, 9, 14, 0), NO_OP_ACTION],
            [action_space.encode_action(0, 9, 10, 0), NO_OP_ACTION],
        ]
    )
    tensor_ingress = kernel.ingress(state, actions)
    before_hand = runtime.battle.hand[1].clone()
    before_cycle = runtime.battle.cycle_queue[1].clone()
    before_elixir = runtime.battle.elixir[1].clone()
    before_rng = runtime.battle.rng.python_state(1)
    before_ids = runtime.battle.entity_id[1].clone()
    before_objects = objects.objects.allocated[1].clone()

    result = driver.apply(tensor_ingress)

    assert result.committed.tolist() == [True, False]
    assert result.action_success.tolist() == [[True, True], [False, False]]
    assert result.unsupported_reasons[1] == (
        "non-spell command requires another ingress"
    )
    assert torch.equal(runtime.battle.hand[1], before_hand)
    assert torch.equal(runtime.battle.cycle_queue[1], before_cycle)
    assert torch.equal(runtime.battle.elixir[1], before_elixir)
    assert runtime.battle.rng.python_state(1) == before_rng
    assert torch.equal(runtime.battle.entity_id[1], before_ids)
    assert torch.equal(objects.objects.allocated[1], before_objects)
    assert runtime.battle.entity_hp[0, 0].item() < spell.entities[1].hitpoints


def test_second_player_unsupported_spell_rolls_back_first_direct_spell() -> None:
    battle = _spell_battle("Zap", two_targets=True)
    battle.players[1].hand[0] = "Freeze"
    battle.players[1].deck[0] = "Freeze"
    _, kernel, state, runtime, objects, driver = _owners(
        [battle],
        {"Zap", "Freeze", "Knight", "Archer"},
        device="cpu",
    )
    action_space = DiscreteTileActionSpace(canonical_perspective=True)
    actions = torch.tensor(
        [
            [
                action_space.encode_action(0, 9, 14, 0),
                action_space.encode_action(0, 8, 17, 1),
            ]
        ]
    )
    tensor_ingress = kernel.ingress(state, actions)
    before_hand = runtime.battle.hand.clone()
    before_cycle = runtime.battle.cycle_queue.clone()
    before_elixir = runtime.battle.elixir.clone()
    before_rng = runtime.battle.rng.python_state(0)
    before_hp = runtime.battle.entity_hp.clone()
    before_status = runtime.status.stun_timer.clone()
    before_events = runtime.events.count.clone()
    before_objects = objects.objects.allocated.clone()

    result = driver.apply(
        tensor_ingress,
        player_order=torch.tensor([[0, 1]]),
    )

    assert result.committed.tolist() == [False]
    assert result.action_success.tolist() == [[False, False]]
    assert result.unsupported_reasons[0] == (
        "continuous freeze/slow area is not retained"
    )
    assert torch.equal(runtime.battle.hand, before_hand)
    assert torch.equal(runtime.battle.cycle_queue, before_cycle)
    assert torch.equal(runtime.battle.elixir, before_elixir)
    assert runtime.battle.rng.python_state(0) == before_rng
    assert torch.equal(runtime.battle.entity_hp, before_hp)
    assert torch.equal(runtime.status.stun_timer, before_status)
    assert torch.equal(runtime.events.count, before_events)
    assert torch.equal(objects.objects.allocated, before_objects)


@pytest.mark.parametrize("spell_name", ("Rocket", "GiantSnowball"))
def test_long_knockback_projectile_spell_is_episode_supported_after_geometry_proof(
    tensor_device: str,
    spell_name: str,
) -> None:
    battle = _spell_battle(spell_name)
    _, kernel, state, runtime, objects, driver = _owners(
        [battle],
        {spell_name, "Knight", "Archer"},
        device=tensor_device,
    )
    action = DiscreteTileActionSpace(canonical_perspective=True).encode_action(
        0, 9, 14, 0
    )
    ingress = kernel.ingress(
        state,
        torch.tensor([[action, NO_OP_ACTION]], device=runtime.device),
    )
    core_card = runtime.battle.card_to_id[spell_name]
    assert driver.bridge.catalog.knockback_units[core_card].item() > 1_000

    preflight = driver.preflight(ingress)
    result = driver.apply(
        ingress,
        player_order=torch.tensor([[0, 1]], device=runtime.device),
    )

    assert driver.episode_supported_core[core_card].item() is True
    assert preflight.command_supported.tolist() == [True]
    assert preflight.row_supported.tolist() == [True]
    assert result.committed.tolist() == [True]
    assert objects.objects.allocated[0].sum().item() == 1


def test_retained_transaction_workspace_reuses_all_speculative_planes(
    tensor_device: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    battle = _spell_battle("Zap")
    _, kernel, state, runtime, _, driver = _owners(
        [battle], {"Zap", "Knight", "Archer"}, device=tensor_device
    )
    ingress = kernel.ingress(
        state,
        torch.tensor(
            [[NO_OP_ACTION, NO_OP_ACTION]],
            dtype=torch.int64,
            device=runtime.device,
        ),
    )
    order = torch.tensor([[0, 1]], device=runtime.device)
    assert driver.apply(ingress, player_order=order).committed.tolist() == [True]
    workspace = driver._transaction_workspace
    assert workspace.runtime is not None
    assert workspace.objects is not None
    assert workspace.bridge is not None
    pointers = (
        workspace.runtime.battle.time.data_ptr(),
        workspace.runtime.battle.rng.words.data_ptr(),
        workspace.objects.objects.allocated.data_ptr(),
        workspace.objects.blueprint_kind.data_ptr(),
        workspace.bridge.blueprint_actual_damage.data_ptr(),
    )

    def forbidden_clone(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("resident spell ingress reconstructed its transaction")

    monkeypatch.setattr(TensorBattleRuntime, "clone", forbidden_clone)
    monkeypatch.setattr(
        resident_spell_ingress,
        "_clone_object_phase",
        forbidden_clone,
    )
    monkeypatch.setattr(
        resident_spell_ingress,
        "_clone_tensor_owner",
        forbidden_clone,
    )
    assert driver.apply(ingress, player_order=order).committed.tolist() == [True]
    assert workspace.runtime is not None
    assert workspace.objects is not None
    assert workspace.bridge is not None
    assert pointers == (
        workspace.runtime.battle.time.data_ptr(),
        workspace.runtime.battle.rng.words.data_ptr(),
        workspace.objects.objects.allocated.data_ptr(),
        workspace.objects.blueprint_kind.data_ptr(),
        workspace.bridge.blueprint_actual_damage.data_ptr(),
    )


def test_production_apply_source_has_no_clone_or_host_diagnostic_conversion() -> None:
    source = inspect.getsource(TensorResidentSpellActionIngress.apply)
    for forbidden in (
        "runtime.clone",
        "_clone_object_phase",
        ".item(",
        ".tolist(",
    ):
        assert forbidden not in source
