import math

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.data import CardDataLoader
from clasher.dynamic_spells import create_spell_from_json
from clasher.rl.simple_pytorch_backend import (
    DEFAULT_SIMPLE_TOKEN_VOCABULARY,
    _typed_lookups,
    load_current_client_typed_vocabulary,
)
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.simple_standard import compile_standard_simple_setup


@pytest.mark.parametrize("device", ["cpu", "mps:0"])
@pytest.mark.parametrize("card", ["Log", "BarbLog"])
def test_rolling_origin_delay_direction_and_damage_match_scalar(card, device):
    if device == "mps:0" and not torch.backends.mps.is_available():
        pytest.skip("MPS unavailable")
    torch.set_num_threads(1)
    loader = CardDataLoader()
    setup = compile_standard_simple_setup(loader, [card, "Knight"], device=device,
                                         canonical_lane_globals=True)
    vocab = load_current_client_typed_vocabulary(DEFAULT_SIMPLE_TOKEN_VOCABULARY)
    entity, hand = _typed_lookups(setup, loader, vocab)
    runtime = setup.create_runtime([[[card] * 8, [card] * 8]] * 2,
                                  entity_token_lookup=entity, hand_token_lookup=hand,
                                  canonical_lane_globals=True, starting_elixir=10)
    scalar = []
    for owner, position in [(0, Position(3.5, 14.5)), (1, Position(14.5, 17.5))]:
        battle = BattleState()
        before = set(battle.entities)
        spell = create_spell_from_json(loader.get_card(card)._raw_entry, loader.load_card_definitions())
        assert spell.cast(battle, owner, position)
        rolling = next(value for key, value in battle.entities.items() if key not in before)
        towers = [e for e in battle.entities.values()
                  if getattr(getattr(e, "card_stats", None), "name", None) in {"Tower", "KingTower"}]
        slots = [int(torch.nonzero((runtime.state.x_units[owner] == round(e.position.x * 1000))
                                   & (runtime.state.y_units[owner] == round(e.position.y * 1000))).flatten()[0])
                 for e in towers]
        scalar.append((battle, rolling, towers, slots))
    first_move = None
    for tick in range(160):
        actions = torch.full((2, 2), NO_OP_ACTION, dtype=torch.int64, device=device)
        if tick == 0:
            actions[0, 0] = actions[1, 1] = 14 * 18 + 3
        runtime.step_tick(actions)
        for row, (battle, rolling, towers, slots) in enumerate(scalar):
            rolling.update(.05, battle)
            expected = torch.tensor([round(rolling.position.x * 1000), round(rolling.position.y * 1000)])
            actual = torch.stack((runtime.rolling_spells.x_units[row, 0], runtime.rolling_spells.y_units[row, 0])).cpu()
            assert torch.equal(actual, expected), (tick + 1, row, actual, expected)
            assert bool(runtime.rolling_spells.active[row, 0]) == rolling.is_alive
            torch.testing.assert_close(
                runtime.state.hp[row, slots].cpu(),
                torch.tensor([tower.hitpoints for tower in towers], dtype=torch.float32),
                rtol=0, atol=0,
            )
        if first_move is None and runtime.rolling_spells.distance_travelled_units.any():
            first_move = tick + 1
        if not runtime.rolling_spells.active.any():
            break
    assert first_move == math.ceil(scalar[0][1].spawn_delay / .05 - 1e-9)
    assert not runtime.rolling_spells.active.any()
    for row, (battle, _, _, _) in enumerate(scalar):
        children = [e for e in battle.entities.values()
                    if getattr(getattr(e, "card_stats", None), "name", None) == "Barbarian"]
        native_children = torch.nonzero(runtime.state.active[row] & (runtime.state.kind[row] == 0)).flatten()
        assert len(children) == len(native_children) == (1 if card == "BarbLog" else 0)
        for child, slot in zip(children, native_children, strict=True):
            assert int(runtime.state.owner[row, slot]) == child.player_id
            assert int(runtime.state.x_units[row, slot]) == round(child.position.x * 1000)
            assert int(runtime.state.y_units[row, slot]) == round(child.position.y * 1000)
