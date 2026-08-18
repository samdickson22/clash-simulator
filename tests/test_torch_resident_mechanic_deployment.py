from __future__ import annotations

import copy
from collections import deque
from collections.abc import Mapping, Sequence

import pytest
import torch

from clasher.battle import BattleState
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.deck_pool import load_deck_pool, unique_cards_from_decks
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.catalog import MECHANIC_OPCODE, TensorCardCatalog
from clasher.torch_sim.deployment import TensorDeploymentCatalog
from clasher.torch_sim.resident_mechanic_deployment import (
    TensorMechanicDeploymentCatalog,
    TensorResidentMechanicDeployment,
)
from clasher.torch_sim.runtime_state import TensorBattleRuntime

ROOTS = ("BattleRam", "Golem", "NightWitch", "Tombstone", "Bandit", "Miner")

OWNER_OPCODES = {
    "terminal": (MECHANIC_OPCODE["DeathSpawn"],),
    "death_payload": (
        MECHANIC_OPCODE["DeathDamage"],
        MECHANIC_OPCODE["DeathAreaEffect"],
    ),
    "periodic": (MECHANIC_OPCODE["PeriodicSpawner"],),
    "charge": (MECHANIC_OPCODE["BattleRamCharge"],),
    "combat_dispatch": (MECHANIC_OPCODE["BanditDash"],),
    "special_deployment": (
        MECHANIC_OPCODE["CrownTowerScaling"],
        MECHANIC_OPCODE["UndergroundDeployment"],
    ),
}


def _set_hand(battle: BattleState, root: str) -> None:
    player = battle.players[0]
    player.hand = [root, "Knight", "Cannon", "Zap"]
    player.deck = [name for name in player.hand if name is not None]
    player.cycle_queue = deque()
    player.elixir = 20.0


def _stack(
    battle: BattleState,
    device: str,
    *,
    owner_opcodes: Mapping[str, Sequence[int]] = OWNER_OPCODES,
) -> tuple[
    TensorBattleRuntime,
    TensorResidentMechanicDeployment,
]:
    cards = TensorCardCatalog.compile(
        battle.card_loader,
        unique_cards_from_decks(load_deck_pool()),
        device=device,
    )
    runtime = TensorBattleRuntime.from_battles(
        [battle], device=device, catalog=cards, max_entities=24, event_capacity=64
    )
    capabilities = TensorMechanicDeploymentCatalog.compile(
        cards, owner_opcodes, loader=battle.card_loader
    )
    adapter = TensorResidentMechanicDeployment(
        capabilities,
        TensorDeploymentCatalog.compile(battle.card_loader, cards),
        runtime,
    )
    return runtime, adapter


def _placement(
    adapter: TensorResidentMechanicDeployment,
    runtime: TensorBattleRuntime,
    player: int = 0,
) -> int:
    state = adapter.driver.action_state(runtime)
    legal = adapter.driver.kernel.legal_action_mask(state)
    selected = torch.nonzero(legal[0, player, : 18 * 32], as_tuple=False)
    assert selected.numel()
    return int(selected[0, 0])


def _spawned(
    runtime: TensorBattleRuntime, first_id: int
) -> list[tuple[str, int, int, float, float]]:
    core = runtime.battle
    return sorted(
        (
            core.card_names[int(core.entity_card[0, slot])],
            int(core.entity_x_units[0, slot]),
            int(core.entity_y_units[0, slot]),
            float(core.entity_hp[0, slot]),
            float(core.entity_deploy_delay[0, slot]),
        )
        for slot in range(runtime.max_entities)
        if bool(runtime.entity_pool.active[0, slot])
        and int(core.entity_id[0, slot]) >= first_id
    )


def _scalar_spawned(
    battle: BattleState, first_id: int
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
def test_represented_mechanic_action_materializes_exact_and_hands_off_owners(
    root: str,
    device: str,
) -> None:
    battle = BattleState(fast_path=False)
    _set_hand(battle, root)
    expected = copy.deepcopy(battle)
    first_id = battle.next_entity_id
    runtime, adapter = _stack(battle, device)
    action = _placement(adapter, runtime)
    actions = torch.tensor([[action, NO_OP_ACTION]], device=runtime.device)
    assert DiscreteTileActionSpace(canonical_perspective=True).apply_action(
        expected, 0, action
    )

    result = adapter.apply(
        runtime,
        actions,
        player_order=torch.tensor([[0, 1]], device=runtime.device),
    )

    assert result.committed.tolist() == [True]
    assert not result.capability_rejected.any()
    assert _spawned(runtime, first_id) == _scalar_spawned(expected, first_id)
    spawned_slots = result.spawned[0]
    assert spawned_slots.any()
    assert (result.owner_spawn_mask[:, 0, spawned_slots]).any(dim=1).any()
    assert torch.equal(
        adapter.state.owner_entity_id[:, 0, spawned_slots],
        result.owner_entity_id[:, 0, spawned_slots],
    )
    if root == "BattleRam":
        assert result.owner_mask(adapter.catalog, "charge").any()
        assert result.owner_mask(adapter.catalog, "terminal").any()
    elif root in {"NightWitch", "Tombstone"}:
        assert result.owner_mask(adapter.catalog, "periodic").any()
        assert result.owner_mask(adapter.catalog, "terminal").any()
    elif root == "Golem":
        assert result.owner_mask(adapter.catalog, "death_payload").any()
        assert result.owner_mask(adapter.catalog, "terminal").any()


def test_missing_co_owner_rolls_back_entire_mixed_row() -> None:
    battle = BattleState(fast_path=False)
    _set_hand(battle, "Golem")
    opponent = battle.players[1]
    opponent.hand = ["Knight", "Cannon", "Zap", "Fireball"]
    opponent.deck = [name for name in opponent.hand if name is not None]
    opponent.cycle_queue = deque()
    opponent.elixir = 20.0
    runtime, adapter = _stack(
        battle,
        "cpu",
        owner_opcodes={
            "death_payload": (MECHANIC_OPCODE["DeathDamage"],),
        },
    )
    action = _placement(adapter, runtime)
    opponent_action = _placement(adapter, runtime, 1)
    before_ids = runtime.battle.entity_id.clone()
    before_elixir = runtime.battle.elixir.clone()
    before_rng = runtime.battle.rng.words.clone()

    result = adapter.apply(
        runtime,
        torch.tensor([[action, opponent_action]]),
        player_order=torch.tensor([[0, 1]]),
    )

    assert result.committed.tolist() == [False]
    assert result.capability_rejected.tolist() == [True]
    assert torch.equal(runtime.battle.entity_id, before_ids)
    assert torch.equal(runtime.battle.elixir, before_elixir)
    assert torch.equal(runtime.battle.rng.words, before_rng)
    assert not adapter.state.owner_entity_id.any()


def test_state_clone_fork_and_row_reset_are_independent() -> None:
    battle = BattleState(fast_path=False)
    _set_hand(battle, "Bandit")
    runtime, adapter = _stack(battle, "cpu")
    action = _placement(adapter, runtime)
    adapter.apply(
        runtime,
        torch.tensor([[action, NO_OP_ACTION]]),
        player_order=torch.tensor([[0, 1]]),
    )
    cloned = adapter.state.clone()
    forked = adapter.state.fork([0, 0])
    assert forked.owner_entity_id.shape[1] == 2
    cloned.owner_entity_id.zero_()
    assert adapter.state.owner_entity_id.any()
    adapter.state.reset_rows_([0], cloned, [0])
    assert not adapter.state.owner_entity_id.any()
