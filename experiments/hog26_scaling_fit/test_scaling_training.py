import ast
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
import scalar_training as original
import scaling_training as scaling
import torch
from compact_public import compact_public
from test_scalar_dataset import game


def test_original_update_and_prediction_functions_unchanged():
    root = Path(__file__).resolve().parents[2]
    def functions(path):
        return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(path.read_text()).body
                if isinstance(n, ast.FunctionDef)}
    assert functions(root/'experiments/hog26_scalar_pilot/scalar_training.py') == functions(root/'experiments/hog26_scaling_fit/scaling_training.py')


@pytest.mark.parametrize('kind', ['globals', 'entity'])
def test_compact_training_updates_bit_identical_to_original(kind):
    torch.set_num_threads(1)
    games = [game(5), game(7)]
    for index, g in enumerate(games):
        count = index+1
        g.public['entity_mask'][:, :count] = True
        g.public['entity_ids'][:, :count] = 2
        g.public['entity_features'][:, :count, 2] = 1
        g.public['entity_features'][:, :count, 4] = 1
        g.public['entity_id_confidence'][:, :count] = 1
        g.public['entity_feature_confidence'][:, :count] = 1
        g.public['global_feature_confidence'][:] = 1
    games[0] = replace(games[0], target_class=0, target_margin=-.4)
    compact = [replace(g, public=compact_public(g.public)) for g in games]
    weights = [np.full(5,.5/5),np.full(7,.5/7)]
    vocabulary=('<pad>','<unknown>','troop_body:Knight','tower:Tower','tower:KingTower')
    def fit(module, values):
        if kind == 'globals':
            return module.fit_globals(values,[0,1],weights,seed=7,epochs=2,batch_rows=4)
        return module.fit_entity(values,[0,1],weights,weights,vocabulary=vocabulary,seed=7,epochs=2)
    before, after = fit(original,games),fit(scaling,compact)
    for key,value in before.state_dict().items():
        torch.testing.assert_close(value,after.state_dict()[key],rtol=0,atol=0)
