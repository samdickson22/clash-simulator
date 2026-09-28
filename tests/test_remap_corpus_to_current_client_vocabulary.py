from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from scripts.remap_corpus_to_current_client_vocabulary import (
    TypedVocabularyRemapper,
    _remap_entity_ids,
)

ROOT = Path(__file__).resolve().parents[1]


def _remapper() -> TypedVocabularyRemapper:
    manifest = json.loads(
        (ROOT / "reports/current_client_youtube_stable_vocabulary_v1.json").read_text()
    )
    old_tokens = tuple(manifest["retained_checkpoint_comparison"]["old_token_names"])
    return TypedVocabularyRemapper(manifest, old_tokens)


def test_contextual_remap_preserves_source_and_visible_form_authority() -> None:
    mapper = _remapper()

    assert mapper._card_key("Archers") == "card_action:Archer"
    assert mapper._entity_key("Archer", "projectile") == (
        "projectile:ArcherArrow",
        "unique_base_form_from_owner",
    )
    assert mapper._entity_key("LogProjectileRolling", "troop_body") == (
        "projectile:LogProjectileRolling",
        "exact_cross_kind_identity",
    )
    fireball, reason = mapper._entity_key("Fireball", "area_effect")
    assert fireball == "card_action:Fireball"
    assert reason.startswith("source_card_fallback_")
    assert mapper._entity_key("Tower", "building_body") == (
        "tower:Tower",
        "tower_source_identity",
    )


def test_entity_array_remap_uses_each_rows_public_kind() -> None:
    mapper = _remapper()
    tables = mapper.entity_tables()
    old = {name: index for index, name in enumerate(mapper.old_tokens)}
    ids = np.asarray([[old["Archer"], old["Fireball"], 0]], dtype=np.int64)
    features = np.zeros((1, 3, 32), dtype=np.float32)
    features[0, 0, 6] = 1.0  # projectile
    features[0, 1, 7] = 1.0  # area effect
    mask = np.asarray([[True, True, False]])

    remapped, stats = _remap_entity_ids(ids, features, mask, tables)

    assert mapper.token_names[remapped[0, 0]] == "projectile:ArcherArrow"
    assert mapper.token_names[remapped[0, 1]] == "card_action:Fireball"
    assert remapped[0, 2] == 0
    assert stats["visible_rows"] == 2
    assert stats["visible_rows_unknown_after_remap"] == 0
