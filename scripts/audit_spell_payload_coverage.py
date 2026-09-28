"""Record spell payload gaps and affected curated decks; never certify support."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from clasher.balance import BALANCE_VERSION, apply_entry_overrides
from clasher.card_aliases import resolve_card_name
from clasher.dynamic_spells import create_spell_from_json
from clasher.gamedata_normalization import build_object_registry
from clasher.paths import decks_path, gamedata_path
from clasher.spells import AreaEffectSpell, DirectDamageSpell


def referenced_spawns(value, path=""):
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else key
            if key in {
                "spawnData",
                "spawnCharacter",
                "deathSpawnCharacter",
            } and isinstance(child, str):
                yield child_path, child
            yield from referenced_spawns(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from referenced_spawns(child, f"{path}[{index}]")


def audit():
    feed_bytes = gamedata_path().read_bytes()
    deck_bytes = decks_path("decks.json", must_exist=True).read_bytes()
    feed = json.loads(feed_bytes)
    decks = json.loads(deck_bytes)["decks"]
    registry = build_object_registry(feed)
    rows = []
    for raw in feed["items"]["spells"]:
        if raw.get("tidType") != "TID_CARD_TYPE_SPELL":
            continue
        entry = apply_entry_overrides(raw, registry)
        spell = create_spell_from_json(entry, registry)
        area = entry.get("areaEffectObjectData") or {}
        flags = []
        if type(spell) is AreaEffectSpell and area.get("onStartingActionData"):
            flags.append("generic_area_does_not_execute_starting_action_tree")
        if type(spell) is DirectDamageSpell and not spell.damage:
            flags.append("zero_damage_direct_spell_requires_payload_review")
        if (
            type(spell) is AreaEffectSpell
            and not spell.hits_air
            and not spell.hits_ground
        ):
            flags.append("area_has_no_damage_target_plane")
        missing = sorted(
            {name for _, name in referenced_spawns(entry) if name not in registry}
        )
        if missing:
            flags.append("unresolved_named_spawn_reference_requires_review")
        rows.append(
            {
                "name": spell.name,
                "runtime_type": type(spell).__name__,
                "review_flags": flags,
                "unresolved_spawn_names": missing,
                "affected_curated_decks": [
                    d["name"]
                    for d in decks
                    if spell.name in {resolve_card_name(c) for c in d["cards"]}
                ],
            }
        )
    return {
        "status": "diagnostic_inventory_not_training_admission",
        "declared_balance_version": BALANCE_VERSION,
        "gamedata_sha256": hashlib.sha256(feed_bytes).hexdigest(),
        "decks_sha256": hashlib.sha256(deck_bytes).hexdigest(),
        "curated_deck_provenance": "local named deck collection; professional usage not independently established",
        "spells": rows,
        "limitations": [
            "No flags does not prove correct behavior.",
            "Missing references may be resolved by other engine mechanisms; flags require review.",
            "Troop abilities, modern forms, and interaction fidelity need separate coverage.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit()
    with args.output.open("x") as output:
        json.dump(result, output, indent=2)
        output.write("\n")


if __name__ == "__main__":
    main()
