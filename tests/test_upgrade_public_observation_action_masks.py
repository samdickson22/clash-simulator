from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np

from clasher.rl.structured_obs import StructuredObservationBuilder


def _module():
    path = Path("scripts/upgrade_public_observation_action_masks.py")
    spec = importlib.util.spec_from_file_location(
        "upgrade_public_observation_action_masks", path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_upgrade_uses_public_state_without_legalizing_the_expert_action() -> None:
    builder = StructuredObservationBuilder(max_entities=3)
    base = {
        "expert_actions": np.asarray([7], dtype=np.int64),
        "metadata_json": np.asarray(
            json.dumps({"token_names": list(builder.token_names)})
        ),
    }
    sidecar = {
        "entity_ids": np.zeros((1, 3), dtype=np.int64),
        "entity_features": np.zeros((1, 3, 32), dtype=np.float32),
        "entity_mask": np.zeros((1, 3), dtype=np.bool_),
        "entity_id_confidence": np.zeros((1, 3), dtype=np.float16),
        "entity_feature_confidence": np.zeros(
            (1, 3, 32), dtype=np.float16
        ),
        "hand_ids": np.zeros((1, 5), dtype=np.int64),
        "hand_id_confidence": np.zeros((1, 5), dtype=np.float16),
        "global_features": np.zeros((1, 18), dtype=np.float32),
        "global_feature_confidence": np.zeros((1, 18), dtype=np.float16),
        "schema_version": np.asarray(2),
    }

    payload, statistics = _module().upgrade_action_masks(
        base=base, sidecar=sidecar
    )

    assert np.flatnonzero(payload["action_masks"][0]).tolist() == [2304]
    assert payload["expert_actions"].tolist() == [7]
    assert payload["expert_action_masked"].tolist() == [True]
    assert payload["feature_contract_version"].item() == 2
    assert statistics["expert_mask_recoveries"] == 0
    assert statistics["expert_actions_masked_by_public_state"] == 1
    assert statistics["label_conditioned_mask_mutations"] == 0

    counterfactual_base = dict(base)
    counterfactual_base["expert_actions"] = np.asarray([8], dtype=np.int64)
    counterfactual, _ = _module().upgrade_action_masks(
        base=counterfactual_base, sidecar=sidecar
    )
    assert np.array_equal(payload["action_masks"], counterfactual["action_masks"])
