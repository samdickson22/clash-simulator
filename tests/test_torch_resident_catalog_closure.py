from __future__ import annotations

import random
from collections import deque

import pytest
import torch

from clasher.battle import BattleState
from clasher.factory.dynamic_factory import troop_from_character_data
from clasher.spells import SPELL_REGISTRY, SpawnProjectileSpell
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.catalog import TensorCardCatalog
from clasher.torch_sim.resident_engine import TensorResidentEngine


def _battle_with_cards(names: list[str], seed: int = 910_001) -> BattleState:
    battle = BattleState(rng=random.Random(seed))
    for player in battle.players:
        player.deck = []
        player.hand = [None, None, None, None]
        player.cycle_queue = deque()
        player.elixir = 10.0
    battle.players[0].deck = list(names)
    battle.players[0].hand = [*names[:4], *([None] * (4 - len(names[:4])))]
    return battle


def _first_slot_action(engine: TensorResidentEngine) -> int:
    state = engine.deployment.action_state(engine.runtime)
    mask = engine.deployment.kernel.legal_action_mask(state)
    legal = torch.nonzero(mask[0, 0, :NO_OP_ACTION], as_tuple=False)
    assert legal.numel()
    action = int(legal[0, 0])
    assert action // (18 * 32) == 0
    return action


@pytest.mark.parametrize(
    ("card_name", "child_name", "spawned_name", "summon_count"),
    [
        ("Archers", "Archer", "Archer", 2),
        ("Bats", "Bat", "Bats", 5),
        ("RoyalHogs", "RoyalHog", "RoyalHogs", 4),
        ("Minions", "Minion", "Minions", 3),
        ("Skeletons", "Skeleton", "Skeletons", 3),
        ("SpearGoblins", "SpearGoblin", "SpearGoblins", 3),
        ("DartGoblin", "BlowdartGoblin", "BlowdartGoblin", 1),
    ],
)
def test_serialized_child_name_deployments_are_catalog_known_after_spawn(
    card_name: str,
    child_name: str,
    spawned_name: str,
    summon_count: int,
) -> None:
    battle = _battle_with_cards([card_name])
    engine = TensorResidentEngine.from_battles(
        [battle], max_entities=32, max_objects=16
    )
    assert child_name in engine.runtime.catalog.name_to_id
    action = _first_slot_action(engine)

    result = engine.step(
        torch.tensor([[action, NO_OP_ACTION]]),
        player_order=torch.tensor([[0, 1]]),
    )

    assert result.committed.tolist() == [True]
    spawned = result.deployment.deployment.allocation
    spawned_slots = spawned.slots[0][spawned.valid[0]]
    assert spawned_slots.numel() == summon_count
    core = engine.runtime.battle
    core_names = [
        core.card_names[int(core.entity_card[0, slot])]
        for slot in spawned_slots.tolist()
    ]
    assert core_names == [spawned_name] * summon_count
    catalog_ids = engine.runtime.card_catalog_index[core.entity_card[0, spawned_slots]]
    assert (catalog_ids >= 0).all()
    assert catalog_ids.unique().tolist() == [
        engine.runtime.catalog.name_to_id[spawned_name]
    ]
    next_preflight = engine.diagnose_preflight()
    assert "absent from the catalog" not in str(next_preflight.reasons[0])


def test_synthetic_child_stats_match_serialized_character_payload_exactly() -> None:
    battle = _battle_with_cards(["RoyalHogs"])
    parent = battle.card_loader.get_card("RoyalHogs")
    assert parent is not None
    payload = parent.summon_character_data
    assert isinstance(payload, dict)
    child = troop_from_character_data(
        "RoyalHog",
        payload,
        elixir=0,
        rarity=str(payload.get("rarity", "Common")),
    )
    engine = TensorResidentEngine.from_battles([battle])
    catalog = engine.runtime.catalog
    card_id = catalog.name_to_id["RoyalHog"]
    assert child.range is not None
    assert child.sight_range is not None
    assert child.speed is not None

    assert catalog.hitpoints[card_id].item() == child.scaled_hitpoints
    assert catalog.damage[card_id].item() == child.scaled_damage
    assert catalog.range_units[card_id].item() == round(float(child.range) * 1_000)
    assert catalog.sight_range_units[card_id].item() == round(
        float(child.sight_range) * 1_000
    )
    assert catalog.speed_units_per_tick[card_id].item() == round(float(child.speed))
    assert catalog.deploy_time_ms[card_id].item() == child.deploy_time


def test_catalog_child_ids_are_stable_across_parent_order_and_existing_closure() -> (
    None
):
    left = _battle_with_cards(["Archers", "Bats", "RoyalHogs"])
    right = _battle_with_cards(["RoyalHogs", "Bats", "Archers"])
    left_engine = TensorResidentEngine.from_battles([left])
    right_engine = TensorResidentEngine.from_battles([right])
    assert left_engine.runtime.catalog.names == right_engine.runtime.catalog.names
    assert left_engine.runtime.catalog.name_to_id == (
        right_engine.runtime.catalog.name_to_id
    )

    incomplete = TensorCardCatalog.compile(left.card_loader, ["Archers"])
    assert "Archer" not in incomplete.name_to_id
    rebuilt = TensorResidentEngine.from_battles([left], catalog=incomplete)
    assert rebuilt.runtime.catalog is not incomplete
    assert "Archer" in rebuilt.runtime.catalog.name_to_id


def test_mixed_secondary_payload_closure_is_present_but_transaction_stays_atomic() -> (
    None
):
    battle = _battle_with_cards(["GoblinGang"])
    engine = TensorResidentEngine.from_battles(
        [battle], max_entities=32, max_objects=16
    )
    assert {"Goblin_Stab", "SpearGoblin"} <= set(engine.runtime.catalog.names)
    action = _first_slot_action(engine)
    actions = torch.tensor([[action, NO_OP_ACTION]])
    diagnostics = engine.diagnose_preflight(actions)
    assert diagnostics.supported == (False,)
    assert diagnostics.reasons == ("mixed deployment payload is unsupported",)
    before_ids = engine.runtime.battle.entity_id.clone()
    before_hand = engine.runtime.battle.hand.clone()
    before_elixir = engine.runtime.battle.elixir.clone()
    before_rng = engine.runtime.battle.rng.python_state(0)

    result = engine.step(actions)

    assert result.committed.tolist() == [False]
    assert torch.equal(engine.runtime.battle.entity_id, before_ids)
    assert torch.equal(engine.runtime.battle.hand, before_hand)
    assert torch.equal(engine.runtime.battle.elixir, before_elixir)
    assert engine.runtime.battle.rng.python_state(0) == before_rng


def test_spawn_projectile_child_uses_the_shared_resident_catalog() -> None:
    battle = _battle_with_cards(["GoblinBarrel"])
    spell = SPELL_REGISTRY["GoblinBarrel"]
    assert isinstance(spell, SpawnProjectileSpell)
    child_name = str(spell.spawn_character)

    engine = TensorResidentEngine.from_battles([battle])

    assert child_name in engine.runtime.catalog.name_to_id
    assert engine.runtime.catalog is engine.deployment.catalog.cards


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA unavailable")
def test_archers_child_closure_and_first_tick_match_cpu_on_cuda() -> None:
    cpu_battle = _battle_with_cards(["Archers"], seed=920_001)
    cuda_battle = cpu_battle.clone()
    cpu = TensorResidentEngine.from_battles(
        [cpu_battle], device="cpu", max_entities=16, max_objects=16
    )
    cuda = TensorResidentEngine.from_battles(
        [cuda_battle], device="cuda", max_entities=16, max_objects=16
    )
    cpu_action = _first_slot_action(cpu)
    cuda_action = _first_slot_action(cuda)
    assert cpu_action == cuda_action

    cpu_result = cpu.step(
        torch.tensor([[cpu_action, NO_OP_ACTION]]),
        player_order=torch.tensor([[0, 1]]),
    )
    cuda_result = cuda.step(
        torch.tensor([[cuda_action, NO_OP_ACTION]], device="cuda"),
        player_order=torch.tensor([[0, 1]], device="cuda"),
    )

    assert cpu_result.committed.tolist() == cuda_result.committed.tolist() == [True]
    for name in (
        "entity_id",
        "entity_card",
        "entity_x_units",
        "entity_y_units",
        "entity_hp",
        "entity_deploy_delay",
    ):
        assert torch.equal(
            getattr(cuda.runtime.battle, name).cpu(),
            getattr(cpu.runtime.battle, name),
        ), name
