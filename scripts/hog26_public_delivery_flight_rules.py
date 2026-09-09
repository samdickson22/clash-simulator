"""Public flight-only rules for serialized spawn-projectile spell bodies."""

from dataclasses import replace

from clasher.dynamic_spells import create_spell_from_json
from clasher.spells import SpawnProjectileSpell
from clasher.torch_sim.simple_catalog import FAST_CARD_EFFECT_PROJECTILE


def with_public_delivery_flights(rules, catalog, loader, inventory):
    """Recognize a visible carrier, never its queued payload or landing target."""
    tokens = rules.appearance_token.clone()
    reasons = list(rules.exclusions)
    registered = []
    for row in inventory["entries"]:
        index = row["runtime_card_id"]
        if (not row["public_root"] or row["status"] != "serialized_identity_candidate"
                or row["effect_primitive"] != FAST_CARD_EFFECT_PROJECTILE
                or float(catalog.effect_damage[index]) != 0):
            continue
        card = loader.get_card(row["runtime_card_name"])
        raw = getattr(card, "_raw_entry", {})
        payload = raw.get("projectileData", {})
        if not payload.get("spawnCharacterData"):
            continue
        spell = create_spell_from_json(raw, loader.load_card_definitions())
        candidate = row["candidates"][0]
        if (not isinstance(spell, SpawnProjectileSpell)
                or payload.get("name") != candidate["name"]
                or int(catalog.effect_kind[index]) != FAST_CARD_EFFECT_PROJECTILE
                or candidate["token"] <= 0):
            raise ValueError("delivery appearance/lifecycle definition mismatch")
        tokens[index] = candidate["token"]
        reasons[index] = "serialized_spawn_projectile_flight_only"
        registered.append(row["runtime_card_name"])
    return replace(rules, appearance_token=tokens, exclusions=tuple(reasons)), registered
