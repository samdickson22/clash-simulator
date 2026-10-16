from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


def visible_enemy_pressure_mask(
    entity_features: np.ndarray,
    entity_mask: np.ndarray,
    *,
    maximum_canonical_y: float = 0.25,
) -> NDArray[np.bool_]:
    """Return rows with a visible enemy troop/building near the defended side.

    Canonical y=0 is the observing player's side. Spells, projectiles, and
    Crown Towers are excluded. This is deliberately a public visual context,
    not a simulator target/aggro or exact-DPS label.
    """
    if entity_features.ndim != 3 or entity_features.shape[2] < 32:
        raise ValueError("entity_features must have shape [samples, entities, >=32]")
    if entity_mask.shape != entity_features.shape[:2]:
        raise ValueError("entity_mask shape must match entity features")
    if not 0.0 <= maximum_canonical_y <= 1.0:
        raise ValueError("maximum_canonical_y must be between zero and one")
    features = entity_features.astype(np.float32, copy=False)
    enemy = features[:, :, 3] > 0.5
    troop_or_building = (features[:, :, 4] > 0.5) | (
        features[:, :, 5] > 0.5
    )
    crown_tower = features[:, :, 31] > 0.5
    near = features[:, :, 1] <= maximum_canonical_y
    return np.asarray(
        np.any(
            entity_mask & enemy & troop_or_building & ~crown_tower & near,
            axis=1,
        ),
        dtype=np.bool_,
    )
