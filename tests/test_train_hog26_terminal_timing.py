from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from scripts.train_hog26_terminal_timing import (
    TimingTable,
    load_timing_table,
    timing_metrics,
)


def test_load_timing_table_preserves_terminal_targets(tmp_path: Path) -> None:
    path = tmp_path / "corpus.npz"
    np.savez_compressed(
        path,
        terminal_timing_root_rows=np.asarray([2, 5]),
        terminal_timing_targets_play=np.asarray([False, True]),
        terminal_timing_parent_play=np.asarray([True, True]),
        terminal_timing_weights=np.asarray([4.0, 1.5], dtype=np.float32),
    )

    table = load_timing_table(path)

    assert table.root_rows.tolist() == [2, 5]
    assert table.targets_play.tolist() == [False, True]
    assert table.corrective.tolist() == [True, False]
    assert table.weights.tolist() == pytest.approx([4.0, 1.5])


def test_timing_metrics_separates_corrective_safety_and_nonroot_retention() -> None:
    table = TimingTable(
        root_rows=np.asarray([1, 3]),
        targets_play=np.asarray([False, True]),
        parent_play=np.asarray([True, True]),
        weights=np.asarray([4.0, 2.0], dtype=np.float32),
    )
    expert = np.asarray([10, 20, 30, 40, 50])
    predicted = np.asarray([10, 2304, 30, 41, 51])

    metrics = timing_metrics(predicted, expert, table)

    assert metrics["corrective_roots"] == 1
    assert metrics["corrective_accuracy"] == 1.0
    assert metrics["safety_roots"] == 1
    assert metrics["safety_accuracy"] == 1.0
    assert metrics["nonroot_rows"] == 3
    assert metrics["nonroot_exact_action_accuracy"] == pytest.approx(2 / 3)
