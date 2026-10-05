"""The SRP shortcut must preserve the public mask's float32 boundary."""
from types import SimpleNamespace

import numpy as np
import pytest

from clasher.battle import BattleState
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.public_observation import project_council_public_observation
from clasher.rl.public_scripted_opponent import PublicScriptedOpponent, SUPPORTED_CARDS
from clasher.rl.script_rollout_planner import ScriptRolloutPlanner
from clasher.rl.structured_obs import StructuredObservationBuilder


def fixture():
    battle = BattleState()
    builder = StructuredObservationBuilder(
        card_vocab=sorted(SUPPORTED_CARDS), canonical_lane_globals=True,
        public_entity_levels=True, card_semantics_version=4,
    )
    env = SimpleNamespace(
        battle=battle, action_space=DiscreteTileActionSpace(),
        structured_obs_builder=builder, public_contract_version=4,
        get_structured_observation=lambda seat: builder.build(battle, seat),
    )
    return battle, ScriptRolloutPlanner(env, PublicScriptedOpponent(builder))


@pytest.mark.parametrize('seat', [0, 1])
@pytest.mark.parametrize('elixir', [0., .999998, .999999, 1., 2.999998, 3., 10.])
def test_unaffordable_shortcut_matches_public_script(seat, elixir):
    battle, planner = fixture()
    battle.players[seat].hand = ['Skeletons', 'Cannon', 'Knight', 'Fireball']
    battle.players[seat].elixir = elixir
    packet = project_council_public_observation(planner.env.structured_obs_builder.build_actor(battle, seat))
    expected = planner.bot.select_action(packet)
    assert planner._model_action(battle, seat, seat) == expected
    if planner._must_wait(battle, seat):
        assert expected == 2304
    if float(np.float32(elixir / 10)) * 10 + 1e-6 >= 1:
        assert not planner._must_wait(battle, seat)


def test_refill_empty_hand_skips_but_unknown_card_does_not():
    battle, planner = fixture()
    battle.players[0].hand = [None] * 4
    assert planner._must_wait(battle, 0)
    battle.players[0].hand[0] = 'unknown-card'
    assert not planner._must_wait(battle, 0)


def test_shortcut_is_scoped_to_p16_v4_and_same_builder():
    battle, planner = fixture()
    battle.players[0].elixir = 0
    battle.players[0].hand = ['Knight', 'Cannon', 'Fireball', 'Skeletons']
    assert planner._must_wait(battle, 0)
    planner.env.public_contract_version = 5
    assert not planner._must_wait(battle, 0)
    planner.env.public_contract_version = 4
    planner.fast_script = False
    assert not planner._must_wait(battle, 0)
