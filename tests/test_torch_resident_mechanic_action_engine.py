from __future__ import annotations

import copy
from collections import deque
from typing import Any, cast

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.resident_engine import (
    ResidentUnsupportedReason,
    TensorResidentEngine,
)

ROOTS = ("BattleRam", "Golem", "NightWitch", "Tombstone", "Bandit", "Miner")


def _set_hand(battle: BattleState, root: str) -> None:
    player = battle.players[0]
    player.hand = [root, "Knight", "Cannon", "Zap"]
    player.deck = [card for card in player.hand if card is not None]
    player.cycle_queue = deque()
    player.elixir = 20.0


def _placement(engine: TensorResidentEngine) -> int:
    state = engine.deployment.action_state(engine.runtime)
    legal = engine.deployment.kernel.legal_action_mask(state)
    result = torch.nonzero(legal[0, 0, : 18 * 32], as_tuple=False)
    assert result.numel()
    return int(result[0, 0])


def _new_characters(
    engine: TensorResidentEngine,
    first_id: int,
) -> list[tuple[str, int, int, float, float]]:
    core = engine.runtime.battle
    return sorted(
        (
            core.card_names[int(core.entity_card[0, slot])],
            int(core.entity_x_units[0, slot]),
            int(core.entity_y_units[0, slot]),
            float(core.entity_hp[0, slot]),
            float(core.entity_deploy_delay[0, slot]),
        )
        for slot in range(engine.runtime.max_entities)
        if bool(engine.runtime.entity_pool.active[0, slot])
        and int(core.entity_id[0, slot]) >= first_id
        and int(core.entity_kind[0, slot]) in {0, 1}
    )


def _scalar_new_characters(
    battle: BattleState,
    first_id: int,
) -> list[tuple[str, int, int, float, float]]:
    return sorted(
        (
            str(entity.card_stats.name),
            round(entity.position.x * 1_000),
            round(entity.position.y * 1_000),
            float(entity.hitpoints),
            float(entity.deploy_delay_remaining),
        )
        for entity_id, entity in battle.entities.items()
        if entity_id >= first_id and getattr(entity, "entity_kind", 4) in {0, 1}
    )


@pytest.mark.parametrize("root", ROOTS)
@pytest.mark.parametrize(
    "device",
    (
        "cpu",
        pytest.param(
            "cuda",
            marks=pytest.mark.skipif(
                not torch.cuda.is_available(), reason="CUDA unavailable"
            ),
        ),
    ),
)
def test_mechanic_action_first_complete_tick_matches_scalar_and_owner_handoff(
    root: str,
    device: str,
) -> None:
    battle = BattleState(fast_path=False)
    _set_hand(battle, root)
    oracle = battle.clone()
    first_id = battle.next_entity_id
    engine = TensorResidentEngine.from_battles(
        [battle],
        device=device,
        max_entities=24,
        max_objects=16,
        event_capacity=256,
    )
    action = _placement(engine)
    actions = torch.tensor([[action, NO_OP_ACTION]], device=engine.device)
    action_space = DiscreteTileActionSpace(canonical_perspective=True)
    assert action_space.apply_action(oracle, 0, action)
    oracle.step_logic_ticks(1)

    preflight = engine.preflight(actions)
    result = engine.step(
        actions,
        player_order=torch.tensor([[0, 1]], device=engine.device),
    )

    assert preflight.supported.tolist() == [True]
    assert result.committed.tolist() == [True]
    assert _new_characters(engine, first_id) == _scalar_new_characters(oracle, first_id)
    owner_ids = engine.mechanic_deployment.state.owner_entity_id
    assert (owner_ids >= first_id).any()
    assert result.action_router.player_order.tolist() == [[0, 1]]


def test_unrepresented_co_mechanics_remain_preflight_fallback_and_atomic() -> None:
    battle = BattleState(fast_path=False)
    _set_hand(battle, "ElectroWizard")
    engine = TensorResidentEngine.from_battles(
        [battle], max_entities=24, max_objects=16, event_capacity=128
    )
    action = _placement(engine)
    actions = torch.tensor([[action, NO_OP_ACTION]])
    before_ids = engine.runtime.battle.entity_id.clone()
    before_elixir = engine.runtime.battle.elixir.clone()

    preflight = engine.preflight(actions)
    result = engine.step(actions)

    assert preflight.supported.tolist() == [False]
    assert preflight.reason_code.tolist() == [ResidentUnsupportedReason.ACTION_MECHANIC]
    assert result.committed.tolist() == [False]
    assert torch.equal(engine.runtime.battle.entity_id, before_ids)
    assert torch.equal(engine.runtime.battle.elixir, before_elixir)


@pytest.mark.parametrize(
    "device",
    (
        "cpu",
        pytest.param(
            "cuda",
            marks=pytest.mark.skipif(
                not torch.cuda.is_available(), reason="CUDA unavailable"
            ),
        ),
    ),
)
def test_miner_action_retains_transport_until_surface_then_rejoins_engine(
    device: str,
) -> None:
    battle = BattleState(fast_path=False)
    _set_hand(battle, "Miner")
    oracle = battle.clone()
    first_id = battle.next_entity_id
    engine = TensorResidentEngine.from_battles(
        [battle],
        device=device,
        max_entities=24,
        max_objects=16,
        event_capacity=512,
    )
    action = _placement(engine)
    action_space = DiscreteTileActionSpace(canonical_perspective=True)
    assert action_space.apply_action(oracle, 0, action)
    actions = torch.tensor([[action, NO_OP_ACTION]], device=engine.device)

    surfaced = False
    for tick in range(60):
        current = actions if tick == 0 else None
        if tick:
            assert engine.preflight().supported.tolist() == [True]
        result = engine.step(current)
        oracle.step_logic_ticks(1)

        assert result.committed.tolist() == [True]
        assert _new_characters(engine, first_id) == _scalar_new_characters(
            oracle, first_id
        )
        miner_slot = int(
            torch.nonzero(
                engine.runtime.battle.entity_id[0] == first_id,
                as_tuple=False,
            )[0, 0]
        )
        scalar_miner = oracle.entities[first_id]
        assert engine.runtime.battle.entity_placement_pending[
            0, miner_slot
        ].item() == bool(scalar_miner.placement_pending)
        assert engine.runtime.battle.entity_deploy_delay[
            0, miner_slot
        ].item() == pytest.approx(scalar_miner.deploy_delay_remaining)
        if not scalar_miner.placement_pending:
            surfaced = True
            assert result.miner is not None
            assert result.miner.surfaced[0, miner_slot].item()
            assert engine.miner.tracked_entity_id[0, miner_slot].item() == 0
            break

    assert surfaced
    assert engine.preflight().supported.tolist() == [True]
    result = engine.step()
    oracle.step_logic_ticks(1)
    assert result.committed.tolist() == [True]
    assert _new_characters(engine, first_id) == _scalar_new_characters(oracle, first_id)


@pytest.mark.parametrize(
    "device",
    (
        "cpu",
        pytest.param(
            "cuda",
            marks=pytest.mark.skipif(
                not torch.cuda.is_available(), reason="CUDA unavailable"
            ),
        ),
    ),
)
def test_terminal_golemites_inherit_death_owner_for_later_cascade(
    device: str,
) -> None:
    battle = BattleState(fast_path=False)
    battle.entities.clear()
    battle.next_entity_id = 1
    golem = battle.card_loader.get_card("Golem")
    knight = battle.card_loader.get_card("Knight")
    assert golem is not None and knight is not None
    battle._spawn_unit_at_position(
        Position(9.0, 10.0),
        0,
        golem,
        deploy_delay_override=0.0,
        snap_to_valid=False,
    )
    source = battle.entities[1]
    assert isinstance(source, Troop)
    source.placement_pending = False
    source._spawn_hook_pending = False
    source._spawn_hook_fired = True
    battle._spawn_unit_at_position(
        Position(9.0, 11.0),
        1,
        knight,
        deploy_delay_override=0.0,
        snap_to_valid=False,
    )
    target = battle.entities[2]
    assert isinstance(target, Troop)
    target.placement_pending = False
    target._spawn_hook_pending = False
    target._spawn_hook_fired = True
    target.stun_timer = 100.0
    target.attack_cooldown = 100.0
    oracle = copy.deepcopy(battle)
    oracle.entities[source.id].take_damage(source.hitpoints)
    oracle._cleanup_dead_entities()
    source.hitpoints = 0.0
    source.is_alive = False
    engine = TensorResidentEngine.from_battles(
        [battle],
        device=device,
        max_entities=16,
        max_objects=8,
        event_capacity=256,
    )

    result = engine.step()

    assert result.committed.tolist() == [True]
    scalar_children = sorted(
        entity_id
        for entity_id, entity in oracle.entities.items()
        if getattr(entity.card_stats, "name", None) == "Golemite"
    )
    assert len(scalar_children) == 2
    death_owner = engine.mechanic_deployment.catalog.owner_index("death_payload")
    for child_id in scalar_children:
        slot = int(
            torch.nonzero(
                engine.runtime.battle.entity_id[0] == child_id,
                as_tuple=False,
            )[0, 0]
        )
        catalog_id = int(
            engine.runtime.card_catalog_index[
                engine.runtime.battle.entity_card[0, slot]
            ]
        )
        assert (
            engine.mechanic_deployment.state.owner_entity_id[
                death_owner, 0, slot
            ].item()
            == child_id
        )
        assert engine.death_payloads.entity_card[0, slot].item() == (
            engine.death_payload_card_by_catalog[catalog_id].item()
        )
        assert engine.death_payloads.damage_receivable[0, slot].any()

    for child_id in scalar_children:
        scalar_child = oracle.entities[child_id]
        scalar_child.take_damage(scalar_child.hitpoints)
        oracle._cleanup_dead_entities()
        slot = int(
            torch.nonzero(
                engine.runtime.battle.entity_id[0] == child_id,
                as_tuple=False,
            )[0, 0]
        )
        engine.runtime.battle.entity_hp[0, slot] = 0.0
        engine.runtime.battle.entity_active[0, slot] = False

        assert engine.preflight().supported.tolist() == [True]
        result = engine.step()

        assert result.committed.tolist() == [True]
        target_slot = int(
            torch.nonzero(
                engine.runtime.battle.entity_id[0] == target.id,
                as_tuple=False,
            )[0, 0]
        )
        assert engine.runtime.battle.entity_hp[0, target_slot].item() == (
            oracle.entities[target.id].hitpoints
        )


def test_surfaced_miner_rejoins_combat_with_exact_crown_scaling() -> None:
    battle = BattleState(fast_path=False)
    tower = next(
        entity
        for entity in battle.entities.values()
        if entity.player_id == 1 and getattr(entity.card_stats, "name", None) == "Tower"
    )
    miner_stats = battle.card_loader.get_card("Miner")
    assert miner_stats is not None
    battle._spawn_unit_at_position(
        Position(tower.position.x, tower.position.y - 1.0),
        0,
        miner_stats,
        deploy_delay_override=0.0,
        snap_to_valid=False,
    )
    miner = battle.entities[battle.next_entity_id - 1]
    assert isinstance(miner, Troop)
    miner.placement_pending = False
    miner._spawn_hook_pending = False
    miner._spawn_hook_fired = True
    cast(Any, miner)._underground_deployment = False
    miner._special_move_active = False
    miner.position = Position(tower.position.x, tower.position.y - 1.0)
    miner.deploy_delay_remaining = 0.0
    miner.placement_delay_total = 0.0
    miner.attack_cooldown = 0.0
    miner.target_id = tower.id
    miner._movement_target_id = tower.id
    tower.stun_timer = 100.0
    tower.attack_cooldown = 100.0
    oracle = copy.deepcopy(battle)
    engine = TensorResidentEngine.from_battles(
        [battle], max_entities=16, max_objects=8, event_capacity=128
    )
    tower_slot = int(
        torch.nonzero(
            engine.runtime.battle.entity_id[0] == tower.id,
            as_tuple=False,
        )[0, 0]
    )
    hp_before = float(engine.runtime.battle.entity_hp[0, tower_slot])

    assert engine.preflight().supported.tolist() == [True]
    result = engine.step()
    oracle.step_logic_ticks(1)

    assert result.committed.tolist() == [True]
    assert hp_before - engine.runtime.battle.entity_hp[0, tower_slot].item() == 39
    assert engine.runtime.battle.entity_hp[0, tower_slot].item() == (
        oracle.entities[tower.id].hitpoints
    )


def test_inflight_scalar_miner_without_retained_handoff_fails_closed() -> None:
    battle = BattleState(fast_path=False)
    miner_stats = battle.card_loader.get_card("Miner")
    assert miner_stats is not None
    battle._spawn_unit_at_position(
        Position(9.0, 20.0),
        0,
        miner_stats,
        snap_to_valid=False,
    )
    engine = TensorResidentEngine.from_battles(
        [battle], max_entities=16, max_objects=8, event_capacity=128
    )

    preflight = engine.preflight()
    result = engine.step()

    assert preflight.supported.tolist() == [False]
    assert preflight.reason_code.tolist() == [ResidentUnsupportedReason.ACTIVE_MECHANIC]
    assert result.committed.tolist() == [False]


def test_no_death_spawn_catalog_constructs_and_admits_miner_action() -> None:
    miner_battle = BattleState(fast_path=False)
    control_battle = BattleState(fast_path=False)
    for battle, root in (
        (miner_battle, "Miner"),
        (control_battle, "Fireball"),
    ):
        for player_id, player in enumerate(battle.players):
            first = root if player_id == 0 else "Fireball"
            player.hand = [first, "Knight", "Cannon", "Zap"]
            player.deck = [first, "Knight", "Cannon", "Zap"]
            player.cycle_queue = deque()
            player.elixir = 20.0
    engine = TensorResidentEngine.from_battles(
        [miner_battle, control_battle],
        max_entities=24,
        max_objects=8,
        event_capacity=128,
    )
    assert engine.terminal_pipeline.catalog.terminal.direct_supported.numel() == 0
    action = _placement(engine)
    actions = torch.tensor(
        [
            [action, NO_OP_ACTION],
            [NO_OP_ACTION, NO_OP_ACTION],
        ]
    )

    preflight = engine.preflight(actions)
    result = engine.step(actions)

    assert preflight.supported.tolist() == [True, True]
    assert result.committed.tolist() == [True, True]
    assert engine.miner.underground_active[0].any()
