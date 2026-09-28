"""Synthetic negative control for binning versus loss sample weights."""

import json
from pathlib import Path

import numpy as np
import torch
from value_contract import ROOT, publish, sha
from value_models import new_trees


def main():
    torch.set_num_threads(1)
    x = np.asfortranarray(np.column_stack((np.linspace(0, 1, 8192), np.cos(np.arange(8192) / 13))))
    y = np.where(x[:, 0] < .5, -.5, .5)
    predictions, thresholds = [], []
    for left_weight, right_weight in ((100., 1.), (1., 100.)):
        _, model = new_trees(1280701, probe_iterations=2)
        weights = np.where(x[:, 0] < .5, left_weight, right_weight)
        weights /= weights.mean()
        model.fit(x, y, sample_weight=weights)
        predictions.append(model.predict(x))
        thresholds.append(model._bin_mapper.bin_thresholds_)
    identical = all(a.dtype == b.dtype and a.shape == b.shape and a.tobytes() == b.tobytes()
                    for a, b in zip(*thresholds, strict=True))
    changed = not np.array_equal(*predictions)
    if not identical or not changed:
        raise ValueError('synthetic binning/loss negative control differs')
    base = Path('/Users/sam/.cache/clasher-margin-tree-diagnostic/sklearn/ensemble/_hist_gradient_boosting')
    resources = {str(base / name): sha(base / name) for name in ('gradient_boosting.py', 'binning.py')}
    result = {'status': 'complete-synthetic-binning-weight-control', 'source_sha256': sha(__file__), 'resources': resources,
              'rows': 8192, 'features': 2, 'opposite_weight_ratios': [[100, 1], [1, 100]],
              'all_binning_threshold_bytes_identical': identical, 'prediction_arrays_differ': changed,
              'maximum_prediction_difference': float(np.max(np.abs(predictions[0] - predictions[1]))),
              'source_observation': 'BaseHistGradientBoosting._bin_data calls _bin_mapper.fit_transform(X) without sample_weight; _BinMapper selects a uniform row subsample above200000 and computes unweighted quantiles.',
              'scope': 'Synthetic implementation control only. Different phase/representative fitting populations can change bins even if loss weights emphasize the same positions. This does not establish the cause of any observed outcome-model error.',
              'real_game_targets_used': False, 'checkpoint_saved': False, 'acceptance': False}
    publish(ROOT / 'reports/hog26_binning_weight_synthetic_control_20260913.json', result)
    print(json.dumps({key: result[key] for key in ('status', 'all_binning_threshold_bytes_identical', 'prediction_arrays_differ', 'maximum_prediction_difference')}), flush=True)


if __name__ == '__main__':
    main()
