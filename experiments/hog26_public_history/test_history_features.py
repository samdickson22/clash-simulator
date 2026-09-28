"""Public-prefix causality, reset refusal and exact online/offline equivalence."""

import copy

import numpy as np
import pytest
from body_features import feature_names as body_names
from history_features import (
    LAGS,
    HistoryState,
    build_game_history,
    history_names,
    make_layout,
)
from residual_features import make_layout as numeric_layout


def fixture(rows=81):
    names = (*numeric_layout(498, (0, *range(2, 10))).names, *body_names())
    layout = make_layout(names)
    base = np.random.default_rng(37).random((rows, 809), dtype=np.float32)
    base[:, layout.clock] = np.arange(rows) / 1000
    base[:, layout.clock_confidence] = 1
    base[:, layout.lag_flags] = np.arange(rows)[:, None] >= np.array(LAGS)
    return base, layout


def test_future_changes_and_truncation_cannot_change_the_past():
    base, layout = fixture()
    expected = build_game_history(base, layout)
    for count in (1, 2, 5, 6, 20, 21, 42, 80):
        np.testing.assert_array_equal(build_game_history(base[:count], layout), expected[:count])
    changed = base.copy()
    changed[31:, list(layout.columns)] *= .3
    np.testing.assert_array_equal(build_game_history(changed, layout)[:31], expected[:31])
    assert len(history_names()) == 97
    assert not expected[0].any()


def test_streaming_is_exact_and_clone_is_independent():
    base, layout = fixture()
    state = HistoryState(layout)
    actual = []
    for row in base[:30]:
        actual.append(state.step(row))
    fork = copy.deepcopy(state)
    alternative = base[30].copy()
    alternative[list(layout.columns)] *= .5
    fork.step(alternative)
    for row in base[30:]:
        actual.append(state.step(row))
    np.testing.assert_array_equal(np.stack(actual), build_game_history(base, layout))
    assert state.seen == len(base) and fork.seen == 31


def test_reset_and_unprimed_history_are_rejected():
    base, layout = fixture()
    state = HistoryState(layout)
    with pytest.raises(ValueError, match='unprimed'):
        state.step(base[25])
    for row in base[:25]:
        state.step(row)
    with pytest.raises(ValueError, match='boundary'):
        state.step(base[0])
    with pytest.raises(ValueError, match='reset'):
        build_game_history(base[25:], layout)


def test_visibility_changes_are_observed_changes_and_input_is_unchanged():
    base, layout = fixture(3)
    before = base.copy()
    output = build_game_history(base, layout)
    np.testing.assert_array_equal(base, before)
    np.testing.assert_array_equal(output[1, :24], base[1, list(layout.columns)] - base[0, list(layout.columns)])
    np.testing.assert_array_equal(output[1, 72:96], np.abs(output[1, :24]))
    assert output[1, -1] == np.float32(1 / 20)


def test_wide_magnitudes_keep_exact_streaming_order():
    base, layout = fixture(113)
    rng = np.random.default_rng(411)
    base[:, list(layout.columns)] = np.exp(rng.uniform(-50, 0, (len(base), 24))).astype(np.float32)
    state = HistoryState(layout)
    online = np.stack([state.step(row) for row in base])
    np.testing.assert_array_equal(online, build_game_history(base, layout))
