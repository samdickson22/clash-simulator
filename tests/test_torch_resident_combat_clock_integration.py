from __future__ import annotations

from collections import deque
from collections.abc import Iterator

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.resident_engine import TensorResidentEngine


@pytest.fixture(params=("cpu", "cuda"))
def tensor_device(request: pytest.FixtureRequest) -> Iterator[str]:
    device = str(request.param)
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    yield device


def _spawn(
    battle: BattleState,
    name: str,
    player: int,
    position: Position,
) -> Troop:
    stats = battle.card_loader.get_card(name)
    assert stats is not None
    entity = battle._spawn_entity(Troop, position, player, stats)
    assert isinstance(entity, Troop)
    entity.deploy_delay_remaining = 0.0
    entity.placement_pending = False
    entity._spawn_hook_pending = False
    entity._spawn_hook_fired = True
    return entity


def _spell_battle(
    spell_name: str,
    target_name: str,
    *,
    existing_stun: float = 0.0,
    charged: bool = False,
) -> BattleState:
    battle = BattleState(fast_path=False)
    battle.entities.clear()
    battle.next_entity_id = 1
    target = _spawn(battle, target_name, 1, Position(9.5, 14.5))
    target.speed = 0.0
    target.damage = 0.0
    target.attack_cooldown = 10.0
    target.last_attack_time = 3.0
    target.stun_timer = existing_stun
    if charged:
        target.is_charging = True
        target.has_charged = True
        target._native_charge_progress = 10_000
        target.attack_cooldown = 0.0
        target._attack_preload_blocked = True
    player = battle.players[0]
    player.hand = [spell_name, "Knight", None, None]
    player.deck = [spell_name, "Knight"]
    player.cycle_queue = deque()
    player.elixir = 10.0
    return battle


def _apply_oracle_actions(
    battles: list[BattleState], actions: torch.Tensor
) -> torch.Tensor:
    action_space = DiscreteTileActionSpace(canonical_perspective=True)
    orders: list[list[int]] = []
    for row, battle in enumerate(battles):
        order = [0, 1]
        battle.rng.shuffle(order)
        orders.append(order)
        for player in order:
            action_space.apply_action(battle, player, int(actions[row, player]))
    return torch.tensor(orders, dtype=torch.int64, device=actions.device)


def _slot(engine: TensorResidentEngine, row: int, entity_id: int) -> int:
    found = torch.where(engine.runtime.battle.entity_id[row] == entity_id)[0]
    assert found.numel() == 1
    return int(found[0].item())


def test_due_zap_interrupts_fresh_and_longer_existing_stun_exactly(
    tensor_device: str,
) -> None:
    sources = [
        _spell_battle("Zap", "Knight"),
        _spell_battle("Zap", "Knight", existing_stun=100.0),
    ]
    oracle = [battle.clone() for battle in sources]
    engine = TensorResidentEngine.from_battles(
        sources,
        device=tensor_device,
        max_entities=8,
        max_objects=4,
        event_capacity=512,
    )
    action = DiscreteTileActionSpace(canonical_perspective=True).encode_action(
        0, 9, 14, 0
    )
    for tick in range(20):
        actions = torch.tensor(
            [
                [action if tick == 0 else NO_OP_ACTION, NO_OP_ACTION],
                [action if tick == 0 else NO_OP_ACTION, NO_OP_ACTION],
            ],
            dtype=torch.int64,
            device=engine.device,
        )
        order = _apply_oracle_actions(oracle, actions)
        for battle in oracle:
            battle.step_logic_ticks(1)
        result = engine.step(actions, player_order=order)
        assert result.committed.tolist() == [True, True]

    for row, battle in enumerate(oracle):
        scalar = battle.entities[1]
        slot = _slot(engine, row, 1)
        assert engine.combat.attack_cooldown[row, slot].item() == (
            scalar.attack_cooldown
        )
        assert engine.combat.attack_windup_active[row, slot].item() is (
            scalar._attack_windup_active
        )
        assert engine.combat.has_attacked_once[row, slot].item() is (
            scalar._has_attacked_once
        )
        assert int(engine.runtime.phases.target_slot[row, slot].item()) == -1


@pytest.mark.parametrize(
    ("spell_name", "target_name", "charged"),
    (
        ("Fireball", "Knight", False),
        ("GiantSnowball", "Knight", False),
        ("Rocket", "Knight", False),
        ("Fireball", "Bowler", False),
        ("Fireball", "HogRider", False),
        ("Fireball", "Prince", True),
        ("Fireball", "RoyalHogs", False),
    ),
)
def test_projectile_knockback_combat_clocks_match_multi_tick(
    tensor_device: str,
    spell_name: str,
    target_name: str,
    charged: bool,
) -> None:
    source = _spell_battle(spell_name, target_name, charged=charged)
    oracle = source.clone()
    engine = TensorResidentEngine.from_battles(
        [source],
        device=tensor_device,
        max_entities=16,
        max_objects=32,
        event_capacity=2_048,
    )
    action = DiscreteTileActionSpace(canonical_perspective=True).encode_action(
        0, 9, 14, 0
    )
    saw_knockback = False
    for tick in range(70):
        actions = torch.tensor(
            [[action if tick == 0 else NO_OP_ACTION, NO_OP_ACTION]],
            dtype=torch.int64,
            device=engine.device,
        )
        order = _apply_oracle_actions([oracle], actions)
        oracle.step_logic_ticks(1)
        result = engine.step(actions, player_order=order)
        assert result.committed.tolist() == [True]
        scalar = oracle.entities.get(1)
        if scalar is None:
            break
        slot = _slot(engine, 0, 1)
        assert engine.combat.attack_cooldown[0, slot].item() == (scalar.attack_cooldown)
        assert engine.runtime.battle.entity_last_attack_time[0, slot].item() == (
            scalar.last_attack_time
        )
        assert engine.runtime.battle.entity_x_units[0, slot].item() == round(
            scalar.position.x * 1_000
        )
        assert engine.runtime.battle.entity_y_units[0, slot].item() == round(
            scalar.position.y * 1_000
        )
        scalar_knockback = scalar._knockback_target is not None
        tensor_knockback = bool(
            engine.projectile_bridge.knockback_active[0, slot].item()
        )
        assert tensor_knockback is scalar_knockback
        saw_knockback |= scalar_knockback
        if saw_knockback and not scalar_knockback:
            break

    if target_name in {"Bowler", "Prince"}:
        assert not saw_knockback
    else:
        assert saw_knockback


def test_goblin_barrel_children_publish_birth_clock_and_deploy_tick(
    tensor_device: str,
) -> None:
    source = _spell_battle("GoblinBarrel", "Knight")
    oracle = source.clone()
    engine = TensorResidentEngine.from_battles(
        [source],
        device=tensor_device,
        max_entities=16,
        max_objects=4,
        event_capacity=1_024,
    )
    action = DiscreteTileActionSpace(canonical_perspective=True).encode_action(
        0, 9, 14, 0
    )
    for tick in range(60):
        actions = torch.tensor(
            [[action if tick == 0 else NO_OP_ACTION, NO_OP_ACTION]],
            dtype=torch.int64,
            device=engine.device,
        )
        order = _apply_oracle_actions([oracle], actions)
        oracle.step_logic_ticks(1)
        result = engine.step(actions, player_order=order)
        assert result.committed.tolist() == [True]
        children = [
            entity
            for entity in oracle.entities.values()
            if getattr(entity.card_stats, "name", None) == "Goblin"
        ]
        if not children:
            continue
        for child in children:
            slot = _slot(engine, 0, child.id)
            assert engine.combat.attack_cooldown[0, slot].item() == (
                child.attack_cooldown
            )
            assert engine.runtime.battle.entity_deploy_delay[0, slot].item() == (
                child.deploy_delay_remaining
            )
        return
    raise AssertionError("Goblin Barrel did not materialize children")


def test_positive_direct_combat_damage_changes_integer_hp_scalar_kind() -> None:
    battle = BattleState(fast_path=False)
    battle.entities.clear()
    battle.next_entity_id = 1
    attacker = _spawn(battle, "Knight", 0, Position(9.0, 10.0))
    target = _spawn(battle, "Knight", 1, Position(9.0, 11.0))
    attacker.target_id = target.id
    attacker.attack_cooldown = 0.0
    target.stun_timer = 100.0
    assert type(target.hitpoints) is int
    oracle = battle.clone()
    engine = TensorResidentEngine.from_battles(
        [battle], max_entities=8, max_objects=4, event_capacity=64
    )

    oracle.step_logic_ticks(1)
    result = engine.step(player_order=torch.tensor([[0, 1]]))

    assert result.committed.tolist() == [True]
    assert type(oracle.entities[target.id].hitpoints) is float
    slot = _slot(engine, 0, target.id)
    assert not engine.runtime.battle.entity_hp_integer_kind[0, slot].item()
