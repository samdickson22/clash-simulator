from __future__ import annotations

import pytest
import torch

from clasher.battle import BattleState
from clasher.rl.common import BOARD_WIDTH
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.catalog import TensorCardCatalog
from clasher.torch_sim.simple_catalog import FastCardCatalog
from clasher.torch_sim.simple_outcomes import FastMatchRules, FastTowerSpec
from clasher.torch_sim.simple_runtime import SimpleGymRuntime


def _spell_runtime(spell_name: str) -> tuple[SimpleGymRuntime, int, int]:
    battle = BattleState()
    full = TensorCardCatalog.compile(
        battle.card_loader,
        [spell_name, "Knight"],
    )
    catalog = FastCardCatalog.from_tensor_catalog(full, loader=battle.card_loader)
    spell = full.name_to_id[spell_name]
    knight = full.name_to_id["Knight"]
    decks = torch.stack(
        (
            torch.full((8,), spell, dtype=torch.int64),
            torch.full((8,), knight, dtype=torch.int64),
        ),
        dim=0,
    ).unsqueeze(0)
    tower_spec = FastTowerSpec(
        card_id=torch.full((2, 3), knight, dtype=torch.int64),
        x_units=torch.tensor([[3_500, 14_500, 9_000], [3_500, 14_500, 9_000]]),
        y_units=torch.tensor([[6_500, 6_500, 2_500], [25_500, 25_500, 29_500]]),
        hitpoints=torch.tensor(
            [[2_000.0, 2_000.0, 3_000.0], [2_000.0, 2_000.0, 3_000.0]]
        ),
        damage=torch.zeros((2, 3)),
        range_units=torch.full((2, 3), 7_500),
        sight_range_units=torch.full((2, 3), 9_500),
        hit_cooldown_ticks=torch.full((2, 3), 16, dtype=torch.int32),
    )
    entity_lookup = torch.zeros((2, catalog.size), dtype=torch.int64)
    entity_lookup[0, knight] = 101
    entity_lookup[1, knight] = 201
    hand_lookup = torch.arange(catalog.size, dtype=torch.int64) + 100
    runtime = SimpleGymRuntime(
        decks,
        catalog,
        tower_spec,
        FastMatchRules(regulation_ticks=200, tiebreak_ticks=400),
        entity_token_lookup=entity_lookup,
        hand_token_lookup=hand_lookup,
        max_entities=12,
    )
    # A non-tower target in the same splash proves tower scaling is per hit.
    slot = 6
    runtime.state.active[0, slot] = True
    runtime.state.stable_id[0, slot] = 7
    runtime.state.next_stable_id[0] = 8
    runtime.state.kind[0, slot] = catalog.kind[knight]
    runtime.state.owner[0, slot] = 1
    runtime.state.card_id[0, slot] = knight
    runtime.state.x_units[0, slot] = 4_000
    runtime.state.y_units[0, slot] = 25_000
    runtime.state.hp[0, slot] = 1_000.0
    runtime.state.max_hp[0, slot] = 1_000.0
    return runtime, spell, slot


@pytest.mark.parametrize(
    ("spell_name", "damage", "tower_multiplier", "travels"),
    (
        ("Fireball", 688.0, 0.25, True),
        ("GiantSnowball", 179.0, 45.0 / 179.0, True),
        ("Rocket", 1484.0, 342.0 / 1484.0, True),
        ("Arrows", 144.0, 0.20, False),
    ),
)
def test_simple_spell_action_uses_one_effect_path_and_per_hit_tower_scale(
    spell_name: str,
    damage: float,
    tower_multiplier: float,
    travels: bool,
) -> None:
    runtime, _, troop_slot = _spell_runtime(spell_name)
    target_tile = 25 * BOARD_WIDTH + 3
    action = torch.tensor([[target_tile, NO_OP_ACTION]], dtype=torch.int64)
    tower_before = runtime.state.hp[0, 3].clone()
    troop_before = runtime.state.hp[0, troop_slot].clone()
    active_before = int(runtime.state.active.sum())

    result = runtime.step_tick(action)
    assert result.action_success.tolist() == [[True, True]]
    assert int(runtime.state.active.sum()) == active_before
    if travels:
        assert bool(runtime.effects.active[0, 0])
        assert runtime.state.hp[0, troop_slot] == troop_before
        noop = torch.full((1, 2), NO_OP_ACTION, dtype=torch.int64)
        for _ in range(160):
            runtime.step_tick(noop)
            if not bool(runtime.effects.active[0, 0]):
                break
    else:
        assert not bool(runtime.effects.active[0, 0])

    torch.testing.assert_close(
        runtime.state.hp[0, troop_slot], (troop_before - damage).clamp_min(0)
    )
    torch.testing.assert_close(
        runtime.state.hp[0, 3],
        tower_before - damage * tower_multiplier,
    )
    assert not bool(runtime.effects.active[0, 0])
