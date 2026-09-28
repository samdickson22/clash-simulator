"""Full fitting-matrix allocation and synthetic-only estimator memory check."""

import argparse
import json
import resource
import sys
import time
from pathlib import Path

import numpy as np
import torch
from cache_reader import read_complete_cache
from health_features import make_layout, materialize_fitting


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--kind', choices=('trees', 'globals'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('preserve existing probe')
    torch.set_num_threads(1)
    root = Path(__file__).resolve().parents[2]
    directory = root / 'reports/hog26_expanded_feature_cache_20260913'
    mapped, evaluation, complete, _ = read_complete_cache(directory)
    layout = make_layout(complete['feature_names'])
    shape = mapped.shape
    mapped._mmap.close()
    folds = evaluation[7]
    counts = [int(np.count_nonzero(folds != fold)) for fold in range(4)]
    largest_fold = int(np.argmax(counts))
    rows = np.flatnonzero(folds != largest_fold)
    del evaluation, folds
    started = time.time()
    if args.kind == 'trees':
        sys.path.insert(0, '/Users/sam/.cache/clasher-margin-tree-diagnostic')
        from sklearn.ensemble import (
            HistGradientBoostingClassifier,
            HistGradientBoostingRegressor,
        )

        features = materialize_fitting(directory / 'features.f32', shape, rows, layout)
        # Three synthetic classes exercise the maximum WDL allocation, without outcome labels.
        labels = (np.arange(len(rows)) % 3).astype(np.int64)
        weights = np.ones(len(rows), dtype=np.float64)
        settings = {'learning_rate': .05, 'max_iter': 2, 'max_leaf_nodes': 15, 'min_samples_leaf': 20,
                        'l2_regularization': 1., 'max_bins': 255, 'early_stopping': False, 'max_features': 1., 'random_state': 1279501}
        classifier = HistGradientBoostingClassifier(**settings).fit(features, labels, sample_weight=weights)
        regressor = HistGradientBoostingRegressor(**settings).fit(features, np.sin(np.arange(len(rows))), sample_weight=weights)
        if not np.isfinite(classifier.predict_proba(features[:512])).all() or not np.isfinite(regressor.predict(features[:512])).all():
            raise ValueError('synthetic prediction nonfinite')
        dimensions = list(features.shape)
    else:
        features = np.empty((shape[0], 36), dtype=np.float32)
        for start in range(0, shape[0], 8192):
            cache = np.memmap(directory / 'features.f32', mode='r', dtype='<f4', shape=shape)
            features[start:start + 8192] = cache[start:start + 8192, layout.globals]
            cache._mmap.close()
        model = torch.nn.Sequential(torch.nn.Linear(36, 32), torch.nn.GELU(), torch.nn.Linear(32, 32),
                                    torch.nn.GELU(), torch.nn.Linear(32, 3))
        optimizer = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=1e-4)
        tensor = torch.from_numpy(features)
        for start in range(0, len(rows), 512):
            chosen = rows[start:start + 512]
            optimizer.zero_grad(set_to_none=True)
            logits = model(tensor[chosen])
            loss = torch.nn.functional.cross_entropy(logits, torch.from_numpy(chosen % 3))
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.)
            optimizer.step()
        dimensions = list(features.shape)
    report = {'status': 'complete-synthetic-memory-probe', 'kind': args.kind, 'largest_fold': largest_fold,
              'fold_fitting_rows': counts, 'matrix_shape': dimensions, 'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
              'elapsed_seconds': time.time() - started, 'outcome_labels_used': False, 'checkpoint_saved': False,
              'fitting_allowed': False, 'scope': 'Full allocation and synthetic steps; the 100-iteration production runs still require a live memory guard.'}
    with args.output.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
