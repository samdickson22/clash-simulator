"""Synthetic targets with the actual tree loss, weights, and storage path."""

import json
import resource
import time
from pathlib import Path

import numpy as np
import torch
from cache_reader import read_complete_cache
from fast_weights import fitting_weights
from health_features import make_layout
from value_models import canonical_probabilities, new_trees
from value_storage import materialize_fitting, predict_trees


def main():
    torch.set_num_threads(1)
    root = Path(__file__).resolve().parents[2]
    output = root / 'reports/hog26_expanded_value_actual_memory_20260913.json'
    if output.exists():
        raise ValueError('preserve previous memory proof')
    directory = root / 'reports/hog26_expanded_feature_cache_20260913'
    mapped, evaluation, complete, _ = read_complete_cache(directory)
    shape = mapped.shape
    mapped._mmap.close()
    layout = make_layout(complete['feature_names'])
    ids, progress, folds = evaluation[0], evaluation[1], evaluation[7]
    counts = [int((folds != fold).sum()) for fold in range(4)]
    fold = int(np.argmax(counts))
    fit = folds != fold
    wdl, margin = fitting_weights(ids, progress, fit)
    rows = np.flatnonzero(fit)
    wdl, margin = wdl[fit] * len(rows), margin[fit] * len(rows)
    del evaluation, ids, progress, folds, fit, complete
    started = time.time()
    features = materialize_fitting(directory / 'features.f32', shape, rows, layout)
    classifier, regressor = new_trees(1279501 + fold, probe_iterations=2)
    classifier.fit(features, np.arange(len(rows)) % 3, sample_weight=wdl)
    regressor.fit(features, np.sin(np.arange(len(rows))), sample_weight=margin)
    if not np.isfinite(canonical_probabilities(classifier, features[:512])).all():
        raise ValueError('nonfinite synthetic classifier')
    del features, wdl, margin, rows
    probabilities, predicted = predict_trees(classifier, regressor, directory / 'features.f32', shape, layout)
    if not np.isfinite(probabilities).all() or not np.isfinite(predicted).all():
        raise ValueError('nonfinite full synthetic inference')
    result = {'status': 'complete-actual-loss-synthetic-memory', 'fold': fold, 'fitting_rows': counts[fold],
              'feature_count': 814, 'classifier_classes': classifier.classes_.tolist(),
              'regressor_loss': regressor.loss, 'iterations': 2,
              'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
              'elapsed_seconds': time.time() - started, 'full_inference_rows': len(predicted),
              'outcome_labels_used': False, 'checkpoint_saved': False, 'fitting_allowed': False}
    with output.open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
