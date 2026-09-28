from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest

from clasher.rl.public_observation import PublicObservationDegradationProfile


def _module():
    path = Path("scripts/build_public_observation_sidecar.py")
    spec = importlib.util.spec_from_file_location(
        "build_public_observation_sidecar", path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _arrays() -> dict[str, np.ndarray]:
    features = np.zeros((2, 3, 32), dtype=np.float32)
    features[:, 0, 4] = 1.0
    features[:, 0, 9] = (0.4, 0.7)
    features[:, 0, 27] = 1.0
    features[:, 1, 6] = 1.0
    return {
        "entity_ids": np.asarray([[4, 5, 0], [4, 5, 0]], dtype=np.int64),
        "entity_features": features,
        "entity_mask": np.asarray([[True, True, False]] * 2, dtype=np.bool_),
        "hand_ids": np.asarray([[1, 2, 3, 4, 5]] * 2, dtype=np.int64),
        "global_features": np.ones((2, 18), dtype=np.float32),
        "expert_actions": np.asarray([10, 11], dtype=np.int64),
        "source_frames": np.asarray([100, 101], dtype=np.int64),
    }


def test_build_public_sidecar_is_aligned_deterministic_and_fail_closed() -> None:
    module = _module()
    profile = PublicObservationDegradationProfile(
        hp_keep_probability=1.0,
        motion_keep_probability=1.0,
        tower_hp_keep_probability=1.0,
    )

    first, statistics = module.build_public_sidecar(
        arrays=_arrays(), profile=profile, seed=77, max_samples=None
    )
    second, _ = module.build_public_sidecar(
        arrays=_arrays(), profile=profile, seed=77, max_samples=None
    )

    assert first["schema_version"].item() == 2
    assert first["feature_contract_version"].item() == 2
    assert first["source_frames"].tolist() == [100, 101]
    assert first["expert_actions"].tolist() == [10, 11]
    assert first["action_masks"].shape == (2, 2306)
    assert first["action_masks"].dtype == np.bool_
    assert first["expert_action_masked"].shape == (2,)
    assert np.array_equal(first["entity_features"], second["entity_features"])
    assert first["entity_mask"].tolist() == [
        [True, True, False],
        [True, True, False],
    ]
    # The local Next card is displayed on the public HUD and remains a valid
    # fifth actor card token. Only cards beyond it are hidden.
    assert first["hand_ids"][:, 4].tolist() == [5, 5]
    assert statistics["samples"] == 2
    assert statistics["entity_hp_coverage"] == 0.5
    assert statistics["motion_coverage"] == 0.5
    assert statistics["feature_contract_version"] == 2
    assert statistics["expert_mask_recoveries"] == 0
    assert statistics["label_conditioned_mask_mutations"] == 0

    changed = _arrays()
    changed["expert_actions"] = np.asarray([2304, 2304], dtype=np.int64)
    counterfactual, _ = module.build_public_sidecar(
        arrays=changed, profile=profile, seed=77, max_samples=None
    )
    assert np.array_equal(first["action_masks"], counterfactual["action_masks"])


def test_build_public_sidecar_rejects_missing_required_array() -> None:
    module = _module()
    arrays = _arrays()
    del arrays["entity_mask"]

    with pytest.raises(ValueError, match="missing arrays"):
        module.build_public_sidecar(
            arrays=arrays,
            profile=PublicObservationDegradationProfile(),
            seed=1,
            max_samples=None,
        )
