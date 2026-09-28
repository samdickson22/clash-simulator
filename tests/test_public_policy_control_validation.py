import numpy as np
import pytest
from clasher.battle import BattleState
from clasher.rl.structured_obs import StructuredObservationBuilder
from clasher.rl.public_policy_contract import PublicPolicySequence


def fixture():
    builder = StructuredObservationBuilder(card_vocab=['Knight'], max_entities=16)
    view = builder.build_actor(BattleState(), 0)
    seq = PublicPolicySequence.from_observations(builder, [view, view])
    controls = dict(action_mask=np.ones((2, 2306), dtype=bool), previous_actions=np.array([0,2304],dtype=np.int32), previous_rewards=[0,.25], episode_starts=[True,False])
    return seq, controls


def test_valid_controls_preserve_values():
    seq, controls = fixture()
    result = seq.policy_inputs(**controls)
    assert result.previous_actions.tolist() == [[0,2304]]
    assert result.previous_rewards.tolist() == [[0,.25]]


@pytest.mark.parametrize('field,value', [
    ('previous_actions', [-1,0]), ('previous_actions', [2306,0]),
    ('previous_actions', [0.5,0]), ('previous_actions', [True,False]),
    ('previous_actions', [[0],[1]]), ('previous_actions', 0),
    ('previous_rewards', [float('nan'),0]), ('previous_rewards', [float('inf'),0]),
    ('previous_rewards', [1e100,0]), ('previous_rewards', ['0','1']),
    ('episode_starts', [1,0]), ('episode_starts', [[True],[False]]),
    ('action_mask', np.ones((2,2306), dtype=np.float32)),
])
def test_malformed_controls_rejected(field, value):
    seq, controls = fixture()
    controls[field] = value
    with pytest.raises(ValueError):
        seq.policy_inputs(**controls)


def test_unsigned_boundary_ids_remain_valid():
    seq, controls = fixture()
    controls['previous_actions'] = np.array([0,2305], dtype=np.uint64)
    controls['previous_rewards'] = np.array([-1,1], dtype=np.int32)
    result = seq.policy_inputs(**controls)
    assert result.previous_actions.tolist() == [[0,2305]]
    assert result.previous_rewards.tolist() == [[-1,1]]


def test_previous_action_need_not_be_legal_in_current_mask():
    seq, controls = fixture()
    controls['action_mask'][:] = False
    controls['action_mask'][:,2304] = True
    controls['previous_actions'] = np.array([0,575], dtype=np.int64)
    assert seq.policy_inputs(**controls).previous_actions.tolist() == [[0,575]]
