import copy

import numpy as np
import torch
from scalar_training import fit_entity, fit_globals
from test_scalar_dataset import game


def test_excluded_game_cannot_change_fitted_models():
    torch.set_num_threads(1)
    games=[game(3),game(3),game(3)]
    altered=copy.deepcopy(games)
    altered[2].public['global_features'][:]=np.nan
    object.__setattr__(altered[2],'target_class',0)
    object.__setattr__(altered[2],'target_margin',-.9)
    weights=[np.full(3,1/6),np.full(3,1/6),np.zeros(3)]
    vocabulary=('<pad>','<unknown>','troop_body:Knight','tower:Tower','tower:KingTower')
    for kind in ('globals','entity'):
        def fit(values, kind=kind):
            if kind=='globals':return fit_globals(values,[0,1],weights,seed=7,epochs=1)
            return fit_entity(values,[0,1],weights,weights,vocabulary=vocabulary,seed=7,epochs=1)
        a,b=fit(games),fit(altered)
        for key,value in a.state_dict().items():
            torch.testing.assert_close(value,b.state_dict()[key],rtol=0,atol=0)
            assert torch.isfinite(value).all()
