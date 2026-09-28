"""Check copied numerical rules and preserve refusal for unsupported outcomes."""

import inspect
import json
from pathlib import Path

import numpy as np
import pytest
import torch
from supported_slices import evaluate_slices

from scripts.hog26_public_slice_gates import evaluate_slices as native


def arguments(outcomes):
    protocol = json.loads(Path('reports/hog26_procedural_outcome_protocol_reassessed_20260908.json').read_text())
    n = len(outcomes)
    return {'probabilities': np.tile([.6, .1, .3], (n, 1)), 'predicted_margin': np.zeros(n),
                'target_margin': np.asarray(outcomes) * .2, 'current_margin': np.zeros(n), 'outcomes': np.asarray(outcomes),
                'phases': np.resize(['early', 'middle', 'late'], n), 'seats': np.arange(n) % 2,
                'styles': np.repeat('balanced', n), 'clusters': np.arange(n), 'expected_styles': ['balanced'],
                'gates': protocol['gates'], 'design': protocol['generalization_evaluation'], 'seed': 42}


def test_source_diff_is_only_declared_prior_domain():
    expected = inspect.getsource(native).replace('(prior <= 0).any()', '(prior < 0).any() or not np.isfinite(prior).all()')
    expected = expected.replace('    label_ids = y.astype(int) + 1',
        '    label_ids = y.astype(int) + 1\n    if np.any(prior[label_ids] <= 0):\n        raise ValueError("observed label has no training prior support")')
    assert inspect.getsource(evaluate_slices) == expected


def test_positive_prior_full_report_identity():
    torch.set_num_threads(1)
    args = arguments([-1, 0, 1] * 8)
    assert evaluate_slices(**args, prior=[.6, .1, .3]) == native(**args, prior=[.6, .1, .3])


def test_zero_draw_is_diagnostic_only_and_observed_zero_refused():
    torch.set_num_threads(1)
    args = arguments([-1, 1] * 12)
    with pytest.raises(ValueError, match='invalid training-only prior'):
        native(**args, prior=[.7, 0, .3])
    report = evaluate_slices(**args, prior=[.7, 0, .3])
    assert np.isfinite(report['slices']['overall']['prior_nll'])
    with pytest.raises(ValueError, match='observed label'):
        evaluate_slices(**arguments([-1, 0, 1]), prior=[.7, 0, .3])
