"""Check public routing and the boundary between separate feature stores."""

import json

import numpy as np
from combined_storage import materialize, routed_probabilities
from health_features import augment, make_layout
from value_contract import CACHE


class FixedClassifier:
    def __init__(self, classes, values):
        self.classes_ = np.asarray(classes)
        self.values = values

    def predict_proba(self, features):
        return np.tile(self.values, (len(features), 1))


def test_public_phase_routing_keeps_absent_draw_class_explicit():
    models = [FixedClassifier([0, 1, 2], [.6, .3, .1]), FixedClassifier([0, 1, 2], [.2, .5, .3]),
              FixedClassifier([0, 2], [.2, .8])]
    features = np.zeros((4, 814), dtype=np.float32)
    features[:, 7] = [0, 1 / 3, 2 / 3, .9]
    actual = routed_probabilities(models, features, 7)
    assert np.array_equal(actual, [[.6, .3, .1], [.2, .5, .3], [.2, 0, .8], [.2, 0, .8]])


def test_combined_store_boundary_preserves_feature_bytes(tmp_path, monkeypatch):
    import combined_storage

    names = json.loads((CACHE / 'complete.json').read_text())['feature_names']
    layout = make_layout(names)
    natural = np.zeros((3, 809), dtype=np.float32)
    natural[:, layout.hp] = np.array([.1, .2, .3, .4, .5, .6])
    natural[:, layout.confidence] = 1
    controls = augment(natural[:2], layout).copy()
    controls[:, 0] = [.7, .8]
    natural_dir, control_dir = tmp_path / 'natural', tmp_path / 'controls'
    natural_dir.mkdir()
    control_dir.mkdir()
    natural.tofile(natural_dir / 'features.f32')
    controls.tofile(control_dir / 'features.f32')
    monkeypatch.setattr(combined_storage, 'CACHE', natural_dir)
    monkeypatch.setattr(combined_storage, 'CONTROLS', control_dir)
    data = {'natural_rows': 3, 'rows': 5, 'natural_shape': natural.shape,
            'control': {'shape': controls.shape}, 'health': layout}
    rows = np.array([0, 2, 3, 4])
    actual = materialize(data, rows)
    expected = np.concatenate((augment(natural, layout), controls))[rows].astype(np.float64)
    assert actual.flags.f_contiguous and actual.dtype == np.float64
    assert np.array_equal(actual, expected)
