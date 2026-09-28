"""Exercise each largest phase with actual public inputs and synthetic targets."""

import gc
import resource

import numpy as np
import torch
from fast_weights import fitting_weights
from phase_contract import MEMORY, PLAN, training_data, validate
from phase_model import fit_model
from phase_storage import normalized_phase_weights, predict_cache
from scalar_evaluation import phase_ids
from value_contract import CACHE, publish, sha
from value_storage import materialize_fitting


def main():
    torch.set_num_threads(1)
    plan = validate()
    evaluation, _, _, shape, layout = training_data()
    ids, progress, folds = evaluation[0], evaluation[1], evaluation[7]
    phases = phase_ids(progress)
    models, largest = [], []
    counts = np.asarray(list(plan['phase_rows_by_fold'].values()))
    for phase in range(3):
        fold = int(counts[:, phase].argmax())
        fit = folds != fold
        _, weights = fitting_weights(ids, progress, fit)
        rows = np.flatnonzero(fit & (phases == phase))
        if len(rows) != counts[fold, phase]:
            raise ValueError('largest phase fitting shape differs')
        features = materialize_fitting(CACHE / 'features.f32', shape, rows, layout)
        models.append(fit_model(features, np.sin(np.arange(len(rows))), normalized_phase_weights(weights, rows),
                                1280600 + phase, memory=True))
        largest.append(len(rows))
        del features, weights
        gc.collect()
    prediction = predict_cache(models, CACHE / 'features.f32', shape, layout)
    publish(MEMORY, {'status': 'complete-phase-margin-synthetic-memory', 'plan_sha256': sha(PLAN),
                     'largest_phase_rows': largest, 'full_inference_rows': len(prediction),
                     'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                     'real_targets_used': False, 'checkpoint_saved': False})


if __name__ == '__main__':
    main()
