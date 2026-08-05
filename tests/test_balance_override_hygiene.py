import json
from collections import defaultdict

from clasher.balance import (
    AREA_EFFECT_FIELD_OVERRIDES,
    CHARACTER_FIELD_OVERRIDES,
    CHARACTER_RUNTIME_TRAITS,
    ENTRY_PATH_OVERRIDES,
    PROJECTILE_FIELD_OVERRIDES,
)
from clasher.card_aliases import resolve_card_name
from clasher.gamedata_normalization import build_object_registry, normalize_entry
from clasher.paths import gamedata_path, project_root


_MISSING = object()


def _enabled_raw_entries():
    with gamedata_path().open() as source:
        data = json.load(source)
    with (project_root() / "decks.json").open() as source:
        decks = json.load(source)["decks"]

    entries = {
        entry["name"]: entry
        for entry in data["items"]["spells"]
        if entry.get("name")
    }
    registry = build_object_registry(data)
    enabled_names = {
        resolve_card_name(card_name, entries)
        for deck in decks
        for card_name in deck["cards"]
    }
    return {
        name: normalize_entry(entries[name], registry)
        for name in enabled_names
    }


def _path_value(value, path):
    for key in path:
        if not isinstance(value, dict) or key not in value:
            return _MISSING
        value = value[key]
    return value


def _identity_payloads(entries, identities):
    payloads = defaultdict(list)

    def walk(value):
        if isinstance(value, dict):
            name = str(value.get("name", ""))
            if name in identities:
                payloads[name].append(value)
            for key, child in value.items():
                if key in {"evolvedSpellsData", "heroData"}:
                    continue
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    for entry in entries.values():
        walk(entry)
    return payloads


def test_enabled_entry_overrides_only_correct_missing_or_stale_feed_values():
    entries = _enabled_raw_entries()
    for entry_name, patches in ENTRY_PATH_OVERRIDES.items():
        if entry_name not in entries:
            continue
        for path, override in patches.items():
            assert _path_value(entries[entry_name], path) != override, (
                f"{entry_name}.{'.'.join(path)} already equals its V5 override; "
                "remove the duplicate pin so future data updates flow through"
            )


def test_enabled_identity_overrides_do_not_repin_complete_live_payloads():
    entries = _enabled_raw_entries()
    override_tables = (
        (CHARACTER_FIELD_OVERRIDES, "characters"),
        (CHARACTER_RUNTIME_TRAITS, "characters"),
        (PROJECTILE_FIELD_OVERRIDES, "projectiles"),
        (AREA_EFFECT_FIELD_OVERRIDES, "area_effect_objects"),
    )
    identities = {
        name
        for table, _ in override_tables
        for name in table
    }
    payloads = _identity_payloads(entries, identities)

    for table, source_prefix in override_tables:
        for name, fields in table.items():
            matching_payloads = [
                payload
                for payload in payloads.get(name, ())
                if str(payload.get("source", "")).startswith(source_prefix)
            ]
            if not matching_payloads:
                continue
            for field, override in fields.items():
                raw_values = [
                    payload.get(field, _MISSING)
                    for payload in matching_payloads
                ]
                assert any(value != override for value in raw_values), (
                    f"{name}.{field} is already complete in every enabled V5 "
                    "payload; remove the duplicate override"
                )
