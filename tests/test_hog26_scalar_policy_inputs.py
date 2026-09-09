from dataclasses import fields
from types import SimpleNamespace

import numpy as np
import torch

from clasher.rl.structured_obs import ActorObservation
from scripts.hog26_scalar_policy_inputs import scalar_policy_inputs


def test_unknown_features_are_not_marked_exact_and_mask_receives_only_public_fields():
    values = np.zeros((4, 32), dtype=np.float32)
    values[0, 4] = 1
    values[1, 6] = 1
    actor = ActorObservation(
        entity_ids=np.array([2, 3, 0, 0]), entity_features=values,
        entity_mask=np.array([True, True, False, False]),
        hand_ids=np.zeros(5, dtype=np.int64), global_features=np.zeros(18, dtype=np.float32),
        opponent_history_ids=np.zeros(0, dtype=np.int64), opponent_history_ages=np.zeros(0),
        opponent_seen_card_ids=np.zeros(0, dtype=np.int64),
    )

    class PublicOnlyMask:
        def build(self, public):
            assert {f.name for f in fields(public)} == {
                "entity_ids", "entity_features", "entity_mask", "hand_ids", "global_features"}
            return SimpleNamespace(masks=torch.ones((1, 2, 2306), dtype=torch.bool))

    inputs, _ = scalar_policy_inputs([actor, actor], PublicOnlyMask(),
                                     previous_actions=[2304, 2304], episode_starts=[True, True])
    confidence = inputs.entity_feature_confidence
    assert confidence[:, :, 0, 9].all()
    assert confidence[:, :, 0, 30].all()
    assert not confidence[:, :, 0, 11:23].any()
    assert not confidence[:, :, 1, 9:].any()
    assert not confidence[:, :, 2:].any()
    assert not inputs.previous_rewards.any()
    assert all(getattr(inputs, f.name) is None for f in fields(inputs) if f.name.startswith("critic"))
    assert inputs.with_exact_actor_confidence() is inputs
