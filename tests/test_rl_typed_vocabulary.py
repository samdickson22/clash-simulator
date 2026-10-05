from __future__ import annotations

import numpy as np

from clasher.rl.imitation_objective import (
    BUILDING_KIND,
    TROOP_KIND,
    build_token_spatial_semantics,
)
from clasher.rl.public_action_mask import PublicActionMaskBuilder, PublicActionMaskInput
from clasher.rl.structured_live_adapter import StructuredLiveInferenceAdapter
from clasher.rl.structured_obs import (
    ACTOR_GLOBAL_SIZE,
    ENTITY_FEATURE_SIZE,
    StructuredObservationBuilder,
)


def _builder() -> StructuredObservationBuilder:
    return StructuredObservationBuilder(
        token_names=(
            "<pad>",
            "<unknown>",
            "card_action:Knight",
            "troop_body:Knight",
            "tower:Tower",
            "projectile:MusketeerProjectile",
        ),
        max_entities=2,
    )


def test_typed_vocabulary_resolves_context_without_role_collisions() -> None:
    builder = _builder()

    assert builder.token_id("Knight") == 2
    assert builder.token_id("Knight", namespace="card_action") == 2
    assert builder.token_id("Knight", namespace="troop_body") == 3
    assert builder.token_id("Tower", namespace="tower") == 4
    assert builder.token_id("MusketeerProjectile", namespace="projectile") == 5
    assert builder.token_id("Knight", namespace="projectile") == 1
    assert builder.card_name_for_token_id(2) == "Knight"
    assert builder.card_name_for_token_id(3) is None
    assert builder.card_stat_features[2, 0] > 0.0


def test_typed_vocabulary_resolves_deck_aliases_to_card_actions() -> None:
    builder = StructuredObservationBuilder(
        token_names=(
            "<pad>",
            "<unknown>",
            "card_action:IceSpirits",
            "card_action:IceGolemite",
            "card_action:BarbLog",
        ),
        max_entities=2,
        card_semantics_version=3,
    )

    assert builder.token_id("IceSpirit") == 2
    assert builder.token_id("IceGolem") == 3
    assert builder.token_id("BarbarianBarrel") == 4
    assert builder.token_id("IceSpirit", namespace="troop_body") == 1


def test_public_mask_accepts_typed_card_action_but_not_body_token() -> None:
    builder = _builder()
    masks = PublicActionMaskBuilder(builder)
    globals_ = np.zeros((ACTOR_GLOBAL_SIZE,), dtype=np.float32)
    globals_[5] = 1.0
    global_confidence = np.zeros_like(globals_)
    global_confidence[5] = 1.0

    def observation(token: int) -> PublicActionMaskInput:
        return PublicActionMaskInput(
            entity_ids=np.zeros((2,), dtype=np.int64),
            entity_features=np.zeros((2, ENTITY_FEATURE_SIZE), dtype=np.float32),
            entity_mask=np.zeros((2,), dtype=np.bool_),
            hand_ids=np.asarray([token, 0, 0, 0, 0], dtype=np.int64),
            global_features=globals_,
            entity_id_confidence=np.zeros((2,), dtype=np.float32),
            hand_id_confidence=np.ones((5,), dtype=np.float32),
            global_feature_confidence=global_confidence,
            # PublicActionMaskBuilder now fails closed on unknown match status
            # (terminal=None -> no-op only; public_action_mask.py "Unknown
            # match status cannot authorize a game command"). Real structured
            # observations always carry terminal=bool(battle.game_over).
            terminal=False,
        )

    assert masks.build(observation(2)).sum() > 1
    assert np.flatnonzero(masks.build(observation(3))).tolist() == [
        masks.no_op_action
    ]


def test_typed_card_actions_retain_spatial_mechanics_classes() -> None:
    builder = StructuredObservationBuilder(
        token_names=(
            "<pad>",
            "<unknown>",
            "card_action:Knight",
            "card_action:Cannon",
            "troop_body:Knight",
        ),
        max_entities=2,
    )
    semantics = build_token_spatial_semantics(builder, device="cpu")

    assert int(semantics.kind[2]) == TROOP_KIND
    assert int(semantics.kind[3]) == BUILDING_KIND
    assert int(semantics.kind[4]) == 0


def test_live_adapter_uses_the_same_contextual_typed_resolver() -> None:
    builder = _builder()
    adapter = StructuredLiveInferenceAdapter.__new__(StructuredLiveInferenceAdapter)
    adapter.public_action_mask_builder = PublicActionMaskBuilder(builder)

    assert adapter._token_id("Knight") == 2
    assert adapter._token_id("Knight", namespace="troop_body") == 3
    assert adapter._token_id("Knight", namespace="projectile") == 1
