"""Exact fixed phase inference, paired with unchanged globals probabilities."""

import json
import pickle

import numpy as np
import torch
from health_features import make_layout
from phase_contract import REFERENCES
from phase_eval_contract import MODELS, OLD_DIAGNOSTIC
from phase_storage import routed_predict
from scalar_models import GlobalWDL
from value_contract import CACHE
from value_storage import predict_globals


def infer(seed, fold, features, globals_x, offsets):
    directory = MODELS / f'seed{seed}-fold{fold}'
    models = []
    for phase in range(3):
        with (directory / f'phase{phase}.pkl').open('rb') as stream:
            model = pickle.load(stream)
        if model.random_state != seed + fold:
            raise ValueError('fixed phase model seed differs')
        models.append(model)
    layout = make_layout(json.loads((CACHE / 'complete.json').read_text())['feature_names'])
    margin = np.empty(len(features), dtype=np.float64)
    for start in range(0, len(features), 4096):
        block = features[start:start + 4096]
        margin[start:start + len(block)] = routed_predict(models, block, layout.globals[0])
    global_model = GlobalWDL()
    global_model.load_state_dict(torch.load(REFERENCES / 'globals' / f'seed{seed}-fold{fold}' / 'model.pt', weights_only=True, map_location='cpu'))
    probability = predict_globals(global_model.eval(), globals_x, offsets)
    with np.load(OLD_DIAGNOSTIC / 'globals' / f'seed{seed}-fold{fold}-predictions.npz', allow_pickle=False) as saved:
        expected = saved['probabilities']
        if probability.shape != expected.shape or probability.dtype != expected.dtype or probability.tobytes() != expected.tobytes():
            raise ValueError('unchanged diagnostic globals prediction bytes differ')
    prior = np.asarray(json.loads((directory / 'manifest.json').read_text())['prior'])
    return probability, margin, prior
