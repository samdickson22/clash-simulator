"""Experimental public rolling-body projection, separate from hit ledgers."""

import torch

from clasher.dynamic_spells import create_spell_from_json
from clasher.spells import RollingProjectileSpell
from scripts.hog26_public_effect_probe import project_visible_effects


def compile_public_rolling_tokens(catalog, runtime_names, loader, vocabulary):
    tokens = torch.zeros_like(catalog.effect_kind, dtype=torch.int64)
    for index, name in enumerate(runtime_names):
        if not bool(catalog.rolling_enabled[index]):
            continue
        raw = getattr(loader.get_card(name), "_raw_entry", {})
        child = raw.get("projectileData", {}).get("spawnProjectileData", {})
        identity = child.get("name")
        spell = create_spell_from_json(raw, loader.load_card_definitions())
        token = vocabulary.resolve(identity, "projectile") if identity else 0
        if not isinstance(spell, RollingProjectileSpell) or token <= 0:
            raise ValueError("rolling body lacks a matched serialized public identity")
        tokens[index] = token
    return tokens


def project_public_rollers(rollers, appearance_tokens):
    card = rollers.source_card_id
    known = (card > 0) & (card < len(appearance_tokens))
    token = appearance_tokens[card.clamp(0, len(appearance_tokens) - 1)]
    if (rollers.active & (~known | (token <= 0))).any():
        raise ValueError("active rolling body has no public appearance rule")
    visible = (rollers.active & (rollers.spawn_delay_ticks == 0))[:, None].expand(-1, 2, -1)
    features, mask = project_visible_effects(
        torch.stack((rollers.x_units, rollers.y_units), dim=-1), rollers.owner,
        torch.ones_like(card), visible,
    )
    return torch.where(mask, token[:, None], 0), features, mask
