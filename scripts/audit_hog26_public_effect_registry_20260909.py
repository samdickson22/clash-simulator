"""Inventory serialized public effect identities without authorizing visibility."""

import hashlib
import json
from collections import Counter
from pathlib import Path

from clasher.data import CardDataLoader
from clasher.rl.simple_pytorch_backend import (
    DEFAULT_SIMPLE_TOKEN_VOCABULARY,
    load_current_client_typed_vocabulary,
    load_simple_supported_decks,
)
from clasher.torch_sim.simple_catalog import (
    FAST_CARD_EFFECT_AREA,
    FAST_CARD_EFFECT_DIRECT,
    FAST_CARD_EFFECT_PROJECTILE,
)
from clasher.torch_sim.simple_standard import compile_standard_simple_setup


def declared_appearance(raw, primitive):
    """Use direct serialized appearance references, not damage/radius heuristics."""
    key = "projectileData" if primitive == FAST_CARD_EFFECT_PROJECTILE else "areaEffectObjectData"
    body = raw.get("summonCharacterData") or raw
    names = {value["name"] for parent in (raw, body)
             if isinstance(parent, dict) and isinstance(value := parent.get(key), dict)
             and isinstance(value.get("name"), str)}
    return sorted(names)


def main():
    root = Path(__file__).resolve().parents[1]
    protocol = json.loads((root / "reports/hog26_procedural_outcome_protocol_reassessed_20260908.json").read_text())
    manifest = load_simple_supported_decks(root / protocol["procedural_decks"]["path"])
    loader = CardDataLoader()
    setup = compile_standard_simple_setup(loader, manifest.public_cards, device="cpu",
                                         canonical_lane_globals=True)
    vocabulary = load_current_client_typed_vocabulary(DEFAULT_SIMPLE_TOKEN_VOCABULARY)
    catalog = setup.spawn_blueprints.fast_cards
    rows = []
    for index, name in enumerate(setup.cards.names):
        primitive = int(catalog.effect_kind[index])
        stats = loader.get_card(name)
        raw = getattr(stats, "_raw_entry", {})
        record = {"runtime_card_id": index, "runtime_card_name": name,
                  "effect_primitive": primitive,
                  "public_root": bool(setup.public_root_mask[index]),
                  "production_visibility_authorized": False}
        if index == 0:
            record.update(status="tower_numeric_override_requires_separate_mapping", candidates=[])
        elif primitive == FAST_CARD_EFFECT_DIRECT:
            record.update(status="internal_direct_hit_not_an_area_sprite", candidates=[])
        elif primitive in (FAST_CARD_EFFECT_PROJECTILE, FAST_CARD_EFFECT_AREA):
            names = declared_appearance(raw, primitive)
            namespace = "projectile" if primitive == FAST_CARD_EFFECT_PROJECTILE else "area_effect"
            candidates = [{"name": value, "namespace": namespace,
                           "token": vocabulary.resolve(value, namespace)} for value in names]
            status = ("serialized_identity_candidate" if len(candidates) == 1 and candidates[0]["token"] > 0
                      else "unresolved_or_ambiguous_identity")
            record.update(status=status, candidates=candidates)
        else:
            record.update(status="non_effect_or_unsupported", candidates=[])
        rows.append(record)
    output = root / "reports/hog26_public_effect_registry_audit_20260909.json"
    with output.open("x") as stream:
        json.dump({"status": "identity inventory only; visibility certification pending",
                   "scope": "Effect primitive does not prove rendered visibility. Direct-hit queue entries are excluded. Serialized identity candidates require scalar/native appearance traces before actor exposure. No target, damage, lifetime or future impact metadata is an actor input.",
                   "manifest_sha256": manifest.sha256,
                   "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   "status_counts": dict(Counter(row["status"] for row in rows)),
                   "entries": rows}, stream, indent=2)
        stream.write("\n")
    print(json.dumps(dict(Counter(row["status"] for row in rows))))
    for row in rows:
        if row["status"] == "unresolved_or_ambiguous_identity":
            print(json.dumps(row))


if __name__ == "__main__":
    main()
