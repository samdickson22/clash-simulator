from __future__ import annotations

import numpy as np

from scripts.audit_structured_corruption_sensitivity import apply_corruption


def _arrays() -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    arrays = {
        "entity_features": np.full((2, 3, 32), 0.5, dtype=np.float32),
        "entity_feature_confidence": np.ones((2, 3, 32), dtype=np.float32),
        "entity_id_confidence": np.full((2, 3), 0.85, dtype=np.float32),
        "hand_ids": np.asarray([[1, 2, 3, 4, 0], [2, 3, 4, 1, 0]]),
        "hand_id_confidence": np.asarray(
            [[1.0, 1.0, 1.0, 1.0, 0.0], [1.0, 1.0, 1.0, 1.0, 0.0]],
            dtype=np.float32,
        ),
        "global_features": np.full((2, 18), 0.5, dtype=np.float32),
        "global_feature_confidence": np.ones((2, 18), dtype=np.float32),
    }
    exact = dict(arrays)
    exact["hand_ids"] = np.asarray([[1, 2, 3, 4, 5], [2, 3, 4, 1, 6]])
    return arrays, exact


def _apply(variant: str) -> dict[str, np.ndarray]:
    arrays, exact = _arrays()
    return apply_corruption(
        arrays,
        exact_arrays=exact,
        variant=variant,
        seed=7,
        position_noise_std=0.01,
        hp_noise_std=0.05,
        elixir_noise_std=0.05,
    )


def test_zero_variants_clear_values_and_confidence_together() -> None:
    motion = _apply("motion_zero")
    assert not np.any(motion["entity_features"][..., 27:29])
    assert not np.any(motion["entity_feature_confidence"][..., 27:29])

    static = _apply("static_zero")
    for channel in (23, 24, 25, 26, 30):
        assert not np.any(static["entity_features"][..., channel])
        assert not np.any(static["entity_feature_confidence"][..., channel])


def test_next_and_confidence_variants_are_explicit() -> None:
    restored = _apply("next_exact_from_base")
    assert restored["hand_ids"][:, 4].tolist() == [5, 6]
    assert restored["hand_id_confidence"][:, 4].tolist() == [1.0, 1.0]

    binary = _apply("confidence_binary")
    assert set(np.unique(binary["entity_id_confidence"]).tolist()) == {1.0}
    assert binary["hand_id_confidence"][:, 4].tolist() == [0.0, 0.0]
