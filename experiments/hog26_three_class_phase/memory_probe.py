"""Full-width largest-phase synthetic allocation; no real fitting labels."""

import numpy as np
import torch
from three_class_contract import MEMORY, PIN, validate
from three_class_model import fit_classifier
from value_contract import publish, sha
from value_models import canonical_probabilities


def main():
    torch.set_num_threads(1)
    pin = validate()
    rows = max(max(value) for value in pin['phase_fit_rows'].values())
    features = np.empty((rows, 814), dtype=np.float64, order='F')
    rng = np.random.default_rng(1281401)
    for start in range(0, rows, 4096):
        end = min(rows, start + 4096)
        features[start:end] = rng.random((end - start, 814))
    labels = np.arange(rows) % 3
    model = fit_classifier(features, labels, np.ones(rows), 1281401, memory=True)
    probability = canonical_probabilities(model, features[:4096])
    if probability.shape != (4096, 3) or not np.array_equal(model.classes_, [0, 1, 2]):
        raise ValueError('multiclass inference proof failed')
    validate()
    publish(MEMORY, {'status': 'complete-three-class-synthetic-memory', 'pin_sha256': sha(PIN), 'rows': rows,
                     'features': 814, 'classes': [0, 1, 2], 'iterations': 2, 'real_labels_used': False,
                     'checkpoint_saved': False, 'acceptance': False})


if __name__ == '__main__':
    main()
