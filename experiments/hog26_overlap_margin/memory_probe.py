"""Exercise each largest overlapping expert with public inputs and synthetic targets."""

import gc
import resource

import numpy as np
import torch
from fast_weights import fitting_weights
from overlap_contract import MEMORY, PLAN, training_data, validate
from overlap_storage import overlap_weights, predict_cache
from phase_model import fit_model
from phase_storage import normalized_phase_weights
from value_contract import CACHE, publish, sha
from value_storage import materialize_fitting


def main():
    torch.set_num_threads(1)
    plan = validate()
    evaluation, _, _, shape, layout = training_data()
    ids, progress, folds = evaluation[0], evaluation[1], evaluation[7]
    gates = overlap_weights(progress)
    models, largest = [], []
    counts = np.asarray(list(plan['expert_rows_by_fold'].values()))
    for expert in range(3):
        fold = int(counts[:, expert].argmax())
        fit = folds != fold
        _, weights = fitting_weights(ids, progress, fit)
        rows = np.flatnonzero(fit & (gates[:, expert] > 0))
        if len(rows) != counts[fold, expert]:
            raise ValueError('largest overlap fitting shape differs')
        features = materialize_fitting(CACHE / 'features.f32', shape, rows, layout)
        models.append(fit_model(features, np.sin(np.arange(len(rows))), normalized_phase_weights(weights * gates[:, expert], rows),
                                1280800 + expert, memory=True))
        largest.append(len(rows))
        del features, weights
        gc.collect()
    prediction = predict_cache(models, CACHE / 'features.f32', shape, layout)
    publish(MEMORY, {'status': 'complete-overlap-margin-synthetic-memory', 'plan_sha256': sha(PLAN),
                     'largest_expert_rows': largest, 'full_inference_rows': len(prediction),
                     'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                     'real_targets_used': False, 'checkpoint_saved': False})


if __name__ == '__main__':
    main()
