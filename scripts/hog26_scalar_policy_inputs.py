"""Actor-only scalar inference boundary with explicit feature availability."""

from dataclasses import fields

import numpy as np
import torch

from clasher.rl.model import PolicyInputs
from clasher.torch_sim.resident_outputs import TensorPublicStructuredObservation


def scalar_policy_inputs(actors, mask_provider, *, previous_actions, episode_starts):
    """Build public-mask-v2 inputs for both seats, without reward/critic access.

    Body features absent from the current reference projection remain unknown,
    not confidently observed zeros. Static body metadata retains its declared
    projection semantics; this does not assert native-input equivalence.
    """
    if len(actors) != 2:
        raise ValueError("one battle requires two actor views")
    public = TensorPublicStructuredObservation(**{
        field.name: torch.from_numpy(np.stack([getattr(a, field.name) for a in actors]))[None]
        for field in fields(TensorPublicStructuredObservation)
    })
    masks = mask_provider.build(public)
    inputs = {field.name: getattr(public, field.name).reshape(
        2, 1, *getattr(public, field.name).shape[2:]) for field in fields(public)}
    features = inputs["entity_features"]
    present = inputs["entity_mask"]
    bodies = present & ((features[..., 4] == 1) | (features[..., 5] == 1))
    availability = torch.zeros_like(features)
    availability[..., :9] = present[..., None]
    for index in (9, 10, 23, 24, 25, 26, 30):
        availability[..., index] = bodies
    previous = torch.as_tensor(previous_actions, dtype=torch.int64)
    starts = torch.as_tensor(episode_starts, dtype=torch.bool)
    if previous.shape != (2,) or starts.shape != (2,):
        raise ValueError("previous actions and episode starts must each have two seats")
    return PolicyInputs(
        **inputs,
        action_mask=masks.masks.reshape(2, 1, -1),
        previous_actions=previous[:, None],
        previous_rewards=torch.zeros((2, 1), dtype=torch.float32),
        episode_starts=starts[:, None],
        entity_id_confidence=present.float(),
        entity_feature_confidence=availability,
        hand_id_confidence=torch.ones_like(inputs["hand_ids"], dtype=torch.float32),
        global_feature_confidence=torch.ones_like(inputs["global_features"]),
    ), masks
