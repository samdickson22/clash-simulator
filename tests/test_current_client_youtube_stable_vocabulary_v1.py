from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import torch

from clasher.card_aliases import CARD_NAME_ALIASES
from clasher.data import CardDataLoader
from clasher.rl.structured_obs import StructuredObservationBuilder

ROOT = Path(__file__).resolve().parents[1]
GAMEDATA = ROOT / "gamedata.json"
DECKS = ROOT / "decks.json"
CHECKPOINT = (
    ROOT / "checkpoints/fresh_structured_causal_v1_seed1062701/"
    "resource_belief_gated_seed1063602/resource_u10_gate0.pt"
)
CANARY = ROOT / "reports/tv_royale_youtube_neutral_readiness_20260817/manifest.json"
MANIFEST = ROOT / "reports/current_client_youtube_stable_vocabulary_v1.json"

EXPECTED_GAMEDATA_SHA256 = (
    "3d99987c19cb94a0c8a6795e943829771078e564859e34c1411e221e5d57486a"
)
EXPECTED_DECKS_SHA256 = (
    "39fd5d5fe36cc7cfa69cf049de3ea2e7e00bc143ec71b14f33ead300fb4b2944"
)
EXPECTED_CHECKPOINT_SHA256 = (
    "3353615954fdcfdb24f2ba570f1888cd6130242238391a9bcf98dcedbcfc5b88"
)

SOURCE_NAMESPACES = {
    "characters": "troop_body",
    "characters_evo": "troop_body",
    "buildings": "building_body",
    "buildings_evo": "building_body",
    "projectiles": "projectile",
    "projectiles_evo": "projectile",
    "area_effect_objects": "area_effect",
    "area_effect_objects_evo": "area_effect",
    "character_buffs": "buff",
    "character_buffs_evo": "buff",
    "character_abilities": "ability",
    "actions": "action_helper",
    "spells_characters": "card_action",
    "spells_buildings": "card_action",
    "spells_other": "card_action",
    "spells_evolved": "card_action",
}
RUNTIME_NAMESPACES = {
    "troop_body",
    "building_body",
    "projectile",
    "area_effect",
    "tower",
}
HELPER_NAMESPACES = {"buff", "ability", "action_helper", "metadata_node"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_sha256(value: Any) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _normalize_label(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"[^a-z0-9]+", "", normalized)


def _walk_named(
    value: Any,
    *,
    path: tuple[str, ...] = (),
) -> Iterator[tuple[tuple[str, ...], dict[str, Any]]]:
    if isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_named(child, path=(*path, str(index)))
        return
    if not isinstance(value, dict):
        return
    if isinstance(value.get("name"), str) and value["name"]:
        yield path, value
    for key, child in value.items():
        yield from _walk_named(child, path=(*path, key))


def _namespace_for(payload: dict[str, Any], path: tuple[str, ...]) -> str:
    source = str(payload.get("source", "") or "")
    if source in SOURCE_NAMESPACES:
        return SOURCE_NAMESPACES[source]
    if path == () or path == ("evolvedSpellsData",) or path == ("heroData",):
        return "card_action"
    if source == "ext":
        joined = ".".join(path).casefold()
        if "building" in joined or "cage" in payload.get("name", "").casefold():
            return "building_body"
        if "character" in joined or "deathspawn" in joined:
            return "troop_body"
    joined = ".".join(path).casefold()
    if "areaeffect" in joined or "aoe" in payload.get("name", "").casefold():
        return "area_effect"
    return "metadata_node"


def _variant_for(path: tuple[str, ...], payload: dict[str, Any]) -> str:
    if "evolvedSpellsData" in path:
        return "evolution"
    if "heroData" in path:
        return "hero"
    name = str(payload.get("name", ""))
    if any(fragment in name.casefold() for fragment in ("_form", "egg", "norespawn")):
        return "form"
    if payload.get("notVisible"):
        return "event_or_internal"
    return "base"


def _source_path(root_name: str, path: tuple[str, ...]) -> str:
    suffix = "" if not path else "." + ".".join(path)
    return f"items.spells[{root_name!r}]{suffix}"


def _stable_key(namespace: str, name: str) -> str:
    return f"{namespace}:{name}"


def _stable_id(namespace: str, name: str) -> str:
    material = f"clasher-current-client-v1\0{namespace}\0{name}".encode()
    return "sha256:" + hashlib.sha256(material).hexdigest()


def build_manifest() -> dict[str, Any]:
    data = json.loads(GAMEDATA.read_text())
    raw_roots = [
        entry
        for entry in data["items"]["spells"]
        if entry.get("name")
        and not str(entry["name"]).startswith("King_")
        and "manaCost" in entry
    ]
    canonical_names = {str(entry["name"]) for entry in raw_roots}
    loader = CardDataLoader(GAMEDATA)
    loaded = loader.load_card_definitions()
    canonical_loaded = {name for name in loaded if name in canonical_names}

    occurrences: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    root_metadata: dict[str, dict[str, Any]] = {}
    evolution_pairs: list[dict[str, str]] = []
    hero_pairs: list[dict[str, str]] = []
    for root in raw_roots:
        root_name = str(root["name"])
        root_metadata[root_name] = {
            "supercell_id": root.get("id"),
            "english_name": root.get("englishName"),
            "mana_cost": root.get("manaCost"),
            "not_visible": bool(root.get("notVisible", False)),
            "rarity": root.get("rarity"),
            "source": root.get("source"),
        }
        evolved = root.get("evolvedSpellsData")
        if isinstance(evolved, dict) and evolved.get("name"):
            evolution_pairs.append({"base": root_name, "variant": str(evolved["name"])})
        hero = root.get("heroData")
        if isinstance(hero, dict) and hero.get("name"):
            hero_pairs.append({"base": root_name, "variant": str(hero["name"])})
        for path, payload in _walk_named(root):
            name = str(payload["name"])
            namespace = _namespace_for(payload, path)
            occurrences[(namespace, name)].append(
                {
                    "owner_root_card": root_name,
                    "path": _source_path(root_name, path),
                    "raw_subtree_sha256": _json_sha256(payload),
                    "source": payload.get("source"),
                    "variant": _variant_for(path, payload),
                    "not_visible": bool(payload.get("notVisible", False)),
                }
            )

    for tower_name in ("Tower", "KingTower"):
        occurrences[("tower", tower_name)].append(
            {
                "owner_root_card": None,
                "path": "simulator.synthetic_tower_identity",
                "raw_subtree_sha256": None,
                "source": "simulator",
                "variant": "base",
                "not_visible": False,
            }
        )

    checkpoint = torch.load(CHECKPOINT, map_location="cpu", weights_only=False)
    old_tokens = tuple(checkpoint["token_names"])
    old_by_name: dict[str, list[int]] = defaultdict(list)
    for token_id, token_name in enumerate(old_tokens):
        old_by_name[str(token_name)].append(token_id)

    rows: list[dict[str, Any]] = []
    for namespace, name in sorted(occurrences):
        refs = occurrences[(namespace, name)]
        owners = sorted(
            {str(ref["owner_root_card"]) for ref in refs if ref["owner_root_card"]}
        )
        sources = sorted({str(ref["source"]) for ref in refs if ref["source"]})
        variants = sorted({str(ref["variant"]) for ref in refs})
        not_visible = all(bool(ref["not_visible"]) for ref in refs)
        card_action_visible = namespace == "card_action" and not not_visible
        runtime_visible = namespace in RUNTIME_NAMESPACES and not not_visible
        eligible = card_action_visible or runtime_visible
        if namespace == "card_action" and name in canonical_names:
            support = "definition_loader_supported_exact_mechanics_not_proven"
        elif "evolution" in variants:
            support = "typed_representation_only_evolution_not_exposed_by_loader"
        elif "hero" in variants:
            support = "typed_representation_only_hero_not_exposed_by_loader"
        elif namespace in HELPER_NAMESPACES:
            support = "graph_only_not_a_standalone_actor_entity"
        else:
            support = "reachable_payload_representation_exact_mechanics_not_proven"
        root_info = root_metadata.get(name, {})
        rows.append(
            {
                "actor_token_id": None,
                "canonical_name": name,
                "namespace": namespace,
                "stable_id": _stable_id(namespace, name),
                "stable_key": _stable_key(namespace, name),
                "policy_token_eligible": eligible,
                "runtime_observable": runtime_visible,
                "not_visible": not_visible,
                "variant_kinds": variants,
                "sources": sources,
                "owner_root_cards": owners,
                "graph_paths": sorted({str(ref["path"]) for ref in refs}),
                "raw_subtree_sha256s": sorted(
                    {
                        str(ref["raw_subtree_sha256"])
                        for ref in refs
                        if ref["raw_subtree_sha256"]
                    }
                ),
                "supercell_root_card_id": root_info.get("supercell_id"),
                "english_name": root_info.get("english_name"),
                "mana_cost": root_info.get("mana_cost"),
                "rarity": root_info.get("rarity"),
                "loader_definition": name in canonical_loaded,
                "simulation_support_state": support,
                "old_checkpoint_token_ids": old_by_name.get(name, []),
            }
        )

    next_token = 2
    for row in rows:
        if row["policy_token_eligible"]:
            row["actor_token_id"] = next_token
            next_token += 1

    aliases: list[dict[str, Any]] = []
    normalized_targets: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        if row["namespace"] != "card_action":
            continue
        labels = {row["canonical_name"]}
        if row["english_name"]:
            labels.add(str(row["english_name"]))
        for alias, target in CARD_NAME_ALIASES.items():
            if target == row["canonical_name"]:
                labels.add(alias)
        for label in sorted(labels):
            normalized_targets[_normalize_label(label)].add(row["stable_key"])
            aliases.append(
                {
                    "context": "card_action",
                    "label": label,
                    "normalized_label": _normalize_label(label),
                    "target_stable_key": row["stable_key"],
                }
            )
    alias_collisions = [
        {"normalized_label": label, "targets": sorted(targets)}
        for label, targets in sorted(normalized_targets.items())
        if len(targets) > 1
    ]

    canary = json.loads(CANARY.read_text())
    decoded_snapshot_count = int(
        canary["counts"]["neutral_structured_snapshots_decoded"]
    )
    canary_gate = {
        "source_manifest": str(CANARY.relative_to(ROOT)),
        "source_manifest_sha256": _sha256(CANARY),
        "decoded_structured_snapshots": decoded_snapshot_count,
        "decoded_card_identities": [],
        "unknown_identities": [],
        "status": (
            "blocked_no_structured_identities_decoded"
            if decoded_snapshot_count == 0
            else "requires_identity_inventory_refresh"
        ),
        "claim": (
            "No non-unknown coverage claim is made until the neutral extractor "
            "publishes stable current-client card identities."
        ),
    }

    old_canonical = sorted(canonical_names.intersection(old_by_name))
    missing_canonical = sorted(canonical_names.difference(old_by_name))
    royal_keys = [
        "card_action:RoyalGiant",
        "troop_body:RoyalGiant",
        "projectile:RoyalGiantProjectile",
        "card_action:RoyalGiant_EV1",
        "projectile:RoyalGiantProjectile_EV1",
        "area_effect:EvoRoyalGiantPush_EV1",
    ]
    by_key = {row["stable_key"]: row for row in rows}
    royal_new = {
        key: by_key[key]["actor_token_id"] for key in royal_keys if key in by_key
    }

    namespace_counts = Counter(row["namespace"] for row in rows)
    support_counts = Counter(row["simulation_support_state"] for row in rows)
    variant_counts = Counter(
        variant for row in rows for variant in row["variant_kinds"]
    )
    return {
        "schema": "clasher.current_client.youtube_stable_vocabulary.v1",
        "authority": {
            "client_version": "15.546.41",
            "gamedata": {
                "path": "gamedata.json",
                "size_bytes": GAMEDATA.stat().st_size,
                "sha256": _sha256(GAMEDATA),
                "fingerprint": data["meta"]["fingerprint"],
            },
            "loader_sources": [
                "src/clasher/data.py",
                "src/clasher/card_aliases.py",
                "src/clasher/gamedata_normalization.py",
                "src/clasher/rl/structured_obs.py",
            ],
            "decks": {
                "path": "decks.json",
                "sha256": _sha256(DECKS),
                "configured_decks": len(json.loads(DECKS.read_text())["decks"]),
                "unique_deck_labels": len(
                    {
                        card
                        for deck in json.loads(DECKS.read_text())["decks"]
                        for card in deck["cards"]
                    }
                ),
            },
            "retained_checkpoint": {
                "path": str(CHECKPOINT.relative_to(ROOT)),
                "sha256": _sha256(CHECKPOINT),
                "token_count": len(old_tokens),
            },
        },
        "assignment_policy": {
            "reserved_tokens": {"<pad>": 0, "<unknown>": 1},
            "stable_id_material": "clasher-current-client-v1\\0{namespace}\\0{canonical_name}",
            "stable_id_algorithm": "sha256",
            "initial_numeric_assignment": "eligible rows sorted by namespace then canonical_name",
            "future_numeric_assignment": "append-only; additions require an explicit migration manifest",
            "bare_names_are_not_keys": True,
            "aliases_are_contextual_labels_only": True,
        },
        "counts": {
            "raw_spells": len(data["items"]["spells"]),
            "canonical_loader_roots": len(canonical_names),
            "loader_alias_keys": len(loaded) - len(canonical_loaded),
            "loader_total_keys": len(loaded),
            "typed_graph_entries": len(rows),
            "unique_bare_names": len({row["canonical_name"] for row in rows}),
            "actor_tokens_including_reserved": next_token,
            "policy_token_eligible_entries": sum(
                bool(row["policy_token_eligible"]) for row in rows
            ),
            "namespace_counts": dict(sorted(namespace_counts.items())),
            "variant_membership_counts": dict(sorted(variant_counts.items())),
            "simulation_support_counts": dict(sorted(support_counts.items())),
            "evolution_roots": len(evolution_pairs),
            "hero_roots": len(hero_pairs),
        },
        "evolution_variants": sorted(evolution_pairs, key=lambda row: row["base"]),
        "hero_variants": sorted(hero_pairs, key=lambda row: row["base"]),
        "entries": rows,
        "aliases": aliases,
        "ambiguous_normalized_card_labels": alias_collisions,
        "retained_checkpoint_comparison": {
            "old_token_names": list(old_tokens),
            "canonical_root_names_represented_exactly": old_canonical,
            "canonical_root_names_missing": missing_canonical,
            "missing_canonical_root_count": len(missing_canonical),
            "old_unknown_token_id": 1,
        },
        "royal_giant_gate": {
            "old_checkpoint_token_id": StructuredObservationBuilder().token_id(
                "RoyalGiant"
            ),
            "old_surface_label_token_ids": {
                label: StructuredObservationBuilder().token_id(label)
                for label in ("Royal Giant", "royal-giant", "royal_giant")
            },
            "new_typed_actor_token_ids": royal_new,
            "normalized_card_label": _normalize_label("Royal Giant"),
            "status": (
                "pass"
                if royal_new and all(value is not None for value in royal_new.values())
                else "fail"
            ),
        },
        "youtube_canary_identity_gate": canary_gate,
        "unsupported_or_unproven_simulator_mechanics": {
            "policy": (
                "Representation coverage is independent of exact mechanics support. "
                "No graph node is omitted because its simulator mechanic is unsupported."
            ),
            "evolution_card_actions": sorted(
                row["stable_key"]
                for row in rows
                if "evolution" in row["variant_kinds"]
                and row["namespace"] == "card_action"
            ),
            "hero_card_actions": sorted(
                row["stable_key"]
                for row in rows
                if "hero" in row["variant_kinds"] and row["namespace"] == "card_action"
            ),
            "abilities_not_standalone_actor_tokens": sorted(
                row["stable_key"] for row in rows if row["namespace"] == "ability"
            ),
            "action_helpers_not_standalone_actor_tokens": sorted(
                row["stable_key"] for row in rows if row["namespace"] == "action_helper"
            ),
            "buff_nodes_not_standalone_actor_tokens": sorted(
                row["stable_key"] for row in rows if row["namespace"] == "buff"
            ),
        },
    }


def test_frozen_manifest_matches_current_authorities() -> None:
    manifest = json.loads(MANIFEST.read_text())
    assert manifest == build_manifest()
    assert manifest["authority"]["gamedata"]["sha256"] == EXPECTED_GAMEDATA_SHA256
    assert manifest["authority"]["decks"]["sha256"] == EXPECTED_DECKS_SHA256
    assert (
        manifest["authority"]["retained_checkpoint"]["sha256"]
        == EXPECTED_CHECKPOINT_SHA256
    )
    assert manifest["counts"]["canonical_loader_roots"] == 144
    assert manifest["counts"]["loader_alias_keys"] == 27
    assert manifest["counts"]["loader_total_keys"] == 171
    assert manifest["counts"]["evolution_roots"] == 41
    assert manifest["counts"]["hero_roots"] == 14


def test_stable_ids_are_typed_unique_and_actor_ids_are_contiguous() -> None:
    manifest = build_manifest()
    entries = manifest["entries"]
    assert len({row["stable_id"] for row in entries}) == len(entries)
    assert len({row["stable_key"] for row in entries}) == len(entries)
    actor_ids = [
        row["actor_token_id"] for row in entries if row["actor_token_id"] is not None
    ]
    assert actor_ids == list(range(2, 2 + len(actor_ids)))
    typed = {(row["namespace"], row["canonical_name"]) for row in entries}
    assert ("card_action", "Freeze") in typed
    assert ("area_effect", "Freeze") in typed
    assert ("buff", "Freeze") in typed
    assert ("card_action", "SkeletonKing") in typed
    assert ("troop_body", "SkeletonKing") in typed
    assert ("ability", "SkeletonKing") in typed


def test_royal_giant_is_no_longer_unknown_and_aliases_are_contextual() -> None:
    manifest = build_manifest()
    gate = manifest["royal_giant_gate"]
    assert gate["old_checkpoint_token_id"] == 1
    assert set(gate["old_surface_label_token_ids"].values()) == {1}
    assert gate["status"] == "pass"
    assert len(gate["new_typed_actor_token_ids"]) == 6
    assert all(value >= 2 for value in gate["new_typed_actor_token_ids"].values())
    royal_aliases = {
        row["normalized_label"]
        for row in manifest["aliases"]
        if row["target_stable_key"] == "card_action:RoyalGiant"
    }
    assert _normalize_label("Royal Giant") in royal_aliases
    assert _normalize_label("royal-giant") in royal_aliases


def test_helpers_and_unproven_mechanics_are_not_silently_actor_tokenized() -> None:
    manifest = build_manifest()
    entries = manifest["entries"]
    for row in entries:
        if row["namespace"] in HELPER_NAMESPACES:
            assert row["policy_token_eligible"] is False
            assert row["actor_token_id"] is None
    unsupported = manifest["unsupported_or_unproven_simulator_mechanics"]
    assert len(unsupported["evolution_card_actions"]) == 41
    assert len(unsupported["hero_card_actions"]) == 14
    assert unsupported["abilities_not_standalone_actor_tokens"]
    assert unsupported["action_helpers_not_standalone_actor_tokens"]
    assert unsupported["buff_nodes_not_standalone_actor_tokens"]


def test_youtube_canary_gate_fails_closed_without_decoded_identities() -> None:
    gate = build_manifest()["youtube_canary_identity_gate"]
    assert gate["decoded_structured_snapshots"] == 0
    assert gate["decoded_card_identities"] == []
    assert gate["unknown_identities"] == []
    assert gate["status"] == "blocked_no_structured_identities_decoded"
