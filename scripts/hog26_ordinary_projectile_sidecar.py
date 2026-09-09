"""Experimental primary-pool projection with explicit unresolved-event rejection."""

from dataclasses import dataclass

import torch

from clasher.torch_sim.simple_catalog import (
    FAST_CARD_EFFECT_DIRECT,
    FAST_CARD_EFFECT_PROJECTILE,
)
from clasher.torch_sim.simple_effects import FAST_EFFECT_AREA, FAST_EFFECT_PROJECTILE
from scripts.hog26_public_effect_probe import project_visible_effects


@dataclass(frozen=True)
class OrdinaryProjectileRules:
    primitive: torch.Tensor
    appearance_token: torch.Tensor
    exclusions: tuple[str, ...]


def compile_ordinary_rules(catalog, runtime_names, inventory):
    """Allow only serialized single-flight candidates, not special topologies."""
    entries = inventory["entries"]
    if [row["runtime_card_name"] for row in entries] != list(runtime_names):
        raise ValueError("effect identity inventory does not match runtime catalog")
    tokens = torch.zeros_like(catalog.effect_kind, dtype=torch.int64)
    excluded = []
    for index, row in enumerate(entries):
        if int(catalog.effect_kind[index]) != row["effect_primitive"]:
            raise ValueError("effect primitive changed since inventory")
        reason = row["status"]
        if (index > 0 and row["effect_primitive"] == FAST_CARD_EFFECT_PROJECTILE
                and reason == "serialized_identity_candidate"):
            special = (bool(catalog.consume_source_on_impact[index])
                       or float(catalog.effect_damage[index]) <= 0
                       or bool(catalog.rolling_enabled[index])
                       or int(catalog.multi_target_count[index]) > 1
                       or int(catalog.chain_target_count[index]) > 0
                       or int(catalog.line_range_units[index]) > 0
                       or int(catalog.fan_ray_count[index]) > 0)
            if special:
                reason = "special_projectile_requires_separate_public_lifecycle"
            else:
                tokens[index] = row["candidates"][0]["token"]
                reason = "ordinary_projectile_probe_rule"
        excluded.append(reason)
    return OrdinaryProjectileRules(catalog.effect_kind.clone(), tokens, tuple(excluded))


def project_primary_effect_pool(effects, rules):
    """Read only primary attack/cast effects; reject any unhandled active event.

    This prototype must not be applied to death/travel/triggered pools. Those
    require distinct appearance rules. It is not wired into policy observations.
    """
    card = effects.source_card_id
    known = (card > 0) & (card < len(rules.primitive))
    safe = card.clamp(0, len(rules.primitive) - 1)
    token = rules.appearance_token[safe]
    flight = known & (token > 0) & (effects.kind == FAST_EFFECT_PROJECTILE)
    direct_queue = known & (rules.primitive[safe] == FAST_CARD_EFFECT_DIRECT) & (effects.kind == FAST_EFFECT_AREA)
    unresolved = effects.active & ~flight & ~direct_queue
    if unresolved.any():
        raise ValueError("active effect lacks a registered ordinary-flight probe rule; enrichment must stop")
    visible = (effects.active & flight)[:, None].expand(-1, 2, -1)
    appearance = torch.where(flight, 1, 0)
    features, mask = project_visible_effects(
        torch.stack((effects.x_units, effects.y_units), dim=-1),
        effects.source_owner, appearance, visible,
    )
    public_tokens = torch.where(mask, token[:, None], 0)
    return public_tokens, features, mask
