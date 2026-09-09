"""Outcome-sidecar tower-shot categories from public fixed arena launch sites."""

from dataclasses import replace

import torch


def with_public_tower_shots(rules, tower_spec, policy_token_names, princess_projectile_name):
    """Extend a separate sidecar vocabulary without changing policy IDs.

    Princess appearance has a serialized projectile identity. King shots use an
    explicitly source-based public category; no unverified asset name is guessed.
    Matching requires exact fixed tower launch coordinates and affiliation.
    """
    names = list(policy_token_names)
    categories = ["projectile:" + princess_projectile_name, "public_tower_shot:king"]
    for name in categories:
        if name not in names:
            names.append(name)
    princess, king = [names.index(name) for name in categories]
    device = tower_spec.x_units.device
    xy = torch.stack((tower_spec.x_units.flatten(), tower_spec.y_units.flatten()), dim=-1)
    updated = replace(
        rules, tower_source_xy=xy,
        tower_owners=torch.tensor([0, 0, 0, 1, 1, 1], device=device),
        tower_tokens=torch.tensor([princess, princess, king, princess, princess, king], device=device),
    )
    return updated, tuple(names)
