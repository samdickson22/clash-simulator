"""Public geometric threat summaries, without attack locks or cooldowns."""

import numpy as np


def corpus_tower_geometry(loaded, stats, fixture):
    parts = []
    xy = np.asarray(fixture["xy_tiles"], dtype=np.float32)
    radii = np.asarray(fixture["radii_tiles"], dtype=np.float32)
    max_hp = np.asarray(fixture["max_hp"], dtype=np.float32)
    for metadata, corpus in loaded:
        crowns = [i for i, name in enumerate(metadata["token_names"])
                  if name.startswith("tower:")]
        if not crowns:
            raise ValueError("public crown-tower tokens are missing")
        for start in range(0, corpus.row_count, 512):
            rows = slice(start, start + 512)
            parts.append(tower_geometry_features(
                corpus.arrays["entity_ids"][rows], corpus.arrays["entity_features"][rows],
                corpus.arrays["entity_mask"][rows], corpus.arrays["global_features"][rows],
                stats, xy, radii, max_hp, crowns,
            ))
    return np.concatenate(parts)


def tower_geometry_features(ids, entities, mask, public, stats, xy, radii, max_hp, crown_tokens):
    """Describe opposing visible ground attackers relative to six arena towers.

    Positions/ranges/radii are in tiles; HP and damage use public card metadata.
    Geometric reach is not a claim that an attacker is targeting or ready to hit.
    """
    visible = np.asarray(mask, dtype=bool)
    card = stats[ids]
    attackers = (visible & (entities[..., 9] > 0)
                 & ((entities[..., 4] > .5) | (entities[..., 5] > .5))
                 & (card[..., 14] > .5) & (card[..., 6] > 0)
                 & ~np.isin(ids, crown_tokens))
    opposing = (entities[..., 2, None] > .5) != (np.arange(6) < 3)
    valid = attackers[..., None] & opposing
    position = np.rint(entities[..., :2] * np.array([18000, 32000])).astype(np.int64)
    target_position = np.rint(xy * 1000).astype(np.int64)
    distance_squared = ((position[..., None, :] - target_position) ** 2).sum(axis=-1)
    reach = (np.rint(card[..., 7, None] * 12000).astype(np.int64)
             + np.rint(radii * 1000).astype(np.int64))
    gap = (np.sqrt(distance_squared) - reach) / 1000
    damage = np.expm1(card[..., 6] * 8)[..., None] / max_hp
    hp = public[:, 8:14]
    in_reach = valid & (distance_squared <= reach ** 2)
    near = valid & (distance_squared <= (reach + 3000) ** 2)
    minimum = np.where(valid, gap, 12).min(axis=1).clip(-12, 12) / 12
    max_damage = np.where(valid, damage, 0).max(axis=1)
    hit_damage = np.where(in_reach, damage, 0)
    columns = [hp, minimum, max_damage.clip(0, 4),
               hit_damage.sum(axis=1).clip(0, 4),
               hit_damage.max(axis=1).clip(0, 4),
               (hit_damage.max(axis=1) / np.maximum(hp, 1e-6)).clip(0, 4),
               in_reach.sum(axis=1) / 8,
               np.where(near, damage, 0).sum(axis=1).clip(0, 4)]
    result = np.stack(columns, axis=-1)
    result = np.where((hp > 0)[..., None], result, 0)
    return result.reshape(len(public), -1).astype(np.float32)
