from __future__ import annotations

import numpy as np
import pytest
import torch

from clasher.rl.model import PolicyInputs
from scripts.perf.benchmark_trimmed_entity_padding import (
    sequence_batch_inputs_trimmed_numpy,
    trim_entity_padding,
)


def _inputs(mask: torch.Tensor) -> PolicyInputs:
    batch, sequence, entities = mask.shape
    return PolicyInputs(
        entity_ids=torch.arange(entities).expand(batch, sequence, -1),
        entity_features=torch.zeros((batch, sequence, entities, 32)),
        entity_mask=mask,
        hand_ids=torch.ones((batch, sequence, 5), dtype=torch.long),
        global_features=torch.zeros((batch, sequence, 18)),
        action_mask=torch.ones((batch, sequence, 2306), dtype=torch.bool),
        previous_actions=torch.zeros((batch, sequence), dtype=torch.long),
        previous_rewards=torch.zeros((batch, sequence)),
        episode_starts=torch.zeros((batch, sequence), dtype=torch.bool),
    )


def test_trim_entity_padding_keeps_batch_maximum_packed_width() -> None:
    mask = torch.tensor(
        [
            [[True, True, False, False], [True, False, False, False]],
            [[True, True, True, False], [False, False, False, False]],
        ]
    )

    trimmed = trim_entity_padding(_inputs(mask))

    assert trimmed.entity_ids.shape == (2, 2, 3)
    assert trimmed.entity_features.shape == (2, 2, 3, 32)
    assert trimmed.entity_mask.equal(mask[..., :3])


def test_trim_entity_padding_rejects_internal_holes() -> None:
    mask = torch.tensor([[[True, False, True, False]]])

    with pytest.raises(ValueError, match="pack valid rows"):
        trim_entity_padding(_inputs(mask))


def test_numpy_pretransfer_trim_keeps_only_packed_batch_width() -> None:
    mask = np.asarray(
        [[[True, True, False, False], [True, False, False, False]]],
        dtype=np.bool_,
    )
    arrays = {
        "entity_ids": np.arange(8, dtype=np.int64).reshape(2, 4),
        "entity_features": np.zeros((2, 4, 32), dtype=np.float32),
        "entity_mask": mask.reshape(2, 4),
        "hand_ids": np.ones((2, 5), dtype=np.int64),
        "global_features": np.zeros((2, 18), dtype=np.float32),
        "action_masks": np.ones((2, 2306), dtype=np.bool_),
        "previous_actions": np.zeros(2, dtype=np.int64),
        "previous_rewards": np.zeros(2, dtype=np.float32),
        "episode_starts": np.zeros(2, dtype=np.bool_),
    }
    inputs = sequence_batch_inputs_trimmed_numpy(
        arrays, np.asarray([[0, 1]], dtype=np.int64), torch.device("cpu")
    )
    assert inputs.entity_ids.shape == (1, 2, 2)
    assert inputs.entity_features.shape == (1, 2, 2, 32)
    assert inputs.entity_mask.equal(torch.as_tensor(mask[..., :2]))
