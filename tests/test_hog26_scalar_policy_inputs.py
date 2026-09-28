from dataclasses import fields
from types import SimpleNamespace

import numpy as np
import torch

from clasher.rl.structured_obs import ActorObservation
from scripts.hog26_scalar_policy_inputs import scalar_policy_inputs


def test_unknown_features_are_not_marked_exact_and_mask_receives_only_public_fields():
    values = np.zeros((4, 32), dtype=np.float32)
    values[0, 4] = 1
    values[1, 6] = 1
    actor = ActorObservation(
        entity_ids=np.array([2, 3, 0, 0]),
        entity_features=values,
        entity_mask=np.array([True, True, False, False]),
        hand_ids=np.zeros(5, dtype=np.int64),
        global_features=np.zeros(18, dtype=np.float32),
        opponent_history_ids=np.zeros(0, dtype=np.int64),
        opponent_history_ages=np.zeros(0),
        opponent_seen_card_ids=np.zeros(0, dtype=np.int64),
    )

    class PublicOnlyMask:
        tables = SimpleNamespace(
            token_keys=("<pad>", "<unknown>", "troop_body:Knight", "projectile:Arrows")
        )

        def build(self, public):
            assert {f.name for f in fields(public)} == {
                "entity_ids",
                "entity_features",
                "entity_mask",
                "hand_ids",
                "global_features",
            }
            return SimpleNamespace(masks=torch.ones((1, 2, 2306), dtype=torch.bool))

    inputs, _ = scalar_policy_inputs(
        [actor, actor],
        PublicOnlyMask(),
        previous_actions=[2304, 2304],
        episode_starts=[True, True],
    )
    confidence = inputs.entity_feature_confidence
    assert confidence[:, :, 0, 9].all()
    assert confidence[:, :, 0, 30].all()
    assert not confidence[:, :, 0, 11].any()
    assert confidence[:, :, 0, 12].all()
    assert not confidence[:, :, 0, 13:23].any()
    assert not confidence[:, :, 1, 9:].any()
    assert not confidence[:, :, 2:].any()
    assert not inputs.previous_rewards.any()
    assert all(
        getattr(inputs, f.name) is None
        for f in fields(inputs)
        if f.name.startswith("critic")
    )
    assert inputs.with_exact_actor_confidence() is inputs


def test_declared_extra_appearance_preserved_for_outcome_and_unknown_to_frozen_policy():
    import pytest

    features = np.zeros((1, 32), dtype=np.float32)
    features[0, 6] = 1
    actor = ActorObservation(
        entity_ids=np.array([2]),
        entity_features=features,
        entity_mask=np.array([True]),
        hand_ids=np.zeros(5, dtype=np.int64),
        global_features=np.zeros(18, dtype=np.float32),
        opponent_history_ids=np.zeros(0, dtype=np.int64),
        opponent_history_ages=np.zeros(0),
        opponent_seen_card_ids=np.zeros(0, dtype=np.int64),
    )

    class Mask:
        tables = SimpleNamespace(token_keys=("<pad>", "<unknown>"))

        def build(self, public):
            assert (public.entity_ids == 1).all()
            return SimpleNamespace(masks=torch.ones((1, 2, 2306), dtype=torch.bool))

    kwargs = {"previous_actions": [2304, 2304], "episode_starts": [True, True]}
    with pytest.raises(ValueError, match="outside declared"):
        scalar_policy_inputs([actor, actor], Mask(), **kwargs)
    result, _ = scalar_policy_inputs(
        [actor, actor],
        Mask(),
        **kwargs,
        extra_public_effect_tokens=("projectile:TowerPrincessProjectile",),
    )
    assert (actor.entity_ids == 2).all()
    assert (result.entity_ids == 1).all()
    assert not result.entity_id_confidence.any()
    assert result.entity_feature_confidence[..., :9].all()


def _extra_actor(kind=7, second_kind=None):
    values = np.zeros((1, 32), dtype=np.float32)
    values[0, kind] = 1
    if second_kind is not None:
        values[0, second_kind] = 1
    return ActorObservation(
        entity_ids=np.array([2]),
        entity_features=values,
        entity_mask=np.array([True]),
        hand_ids=np.zeros(5, dtype=np.int64),
        global_features=np.zeros(18, dtype=np.float32),
        opponent_history_ids=np.zeros(0, dtype=np.int64),
        opponent_history_ages=np.zeros(0),
        opponent_seen_card_ids=np.zeros(0, dtype=np.int64),
    )


class _UnknownEffectMask:
    tables = SimpleNamespace(token_keys=("<pad>", "<unknown>"))

    def build(self, public):
        assert (public.entity_ids == 1).all()
        return SimpleNamespace(masks=torch.ones((1, 2, 2306), dtype=torch.bool))


def test_exact_chain_and_container_categories_remain_unknown_to_policy():
    for name in ("public_effect:chain_bolt", "building_body:SkeletonContainerNew"):
        actor = _extra_actor()
        before_features = actor.entity_features.copy()
        result, _ = scalar_policy_inputs(
            [actor, actor],
            _UnknownEffectMask(),
            previous_actions=[2304, 2304],
            episode_starts=[True, True],
            extra_public_effect_tokens=(name,),
        )
        assert (actor.entity_ids == 2).all()
        assert np.array_equal(actor.entity_features, before_features)
        assert (result.entity_ids == 1).all()
        assert not result.entity_id_confidence.any()
        assert result.entity_feature_confidence[..., :9].all()
        assert not result.entity_feature_confidence[..., 9:].any()


def test_category_exceptions_do_not_admit_arbitrary_namespace_members():
    import pytest

    actor = _extra_actor()
    for name in (
        "public_effect:other",
        "public_effect:chain_bolt_suffix",
        "building_body:Knight",
        "building_body:SkeletonContainerNew_suffix",
    ):
        with pytest.raises(ValueError, match="distinct declared"):
            scalar_policy_inputs(
                [actor, actor],
                _UnknownEffectMask(),
                previous_actions=[2304, 2304],
                episode_starts=[True, True],
                extra_public_effect_tokens=(name,),
            )


def test_exception_tokens_still_require_effect_only_rows():
    import pytest

    for name in ("public_effect:chain_bolt", "building_body:SkeletonContainerNew"):
        for kind, second_kind in ((4, None), (5, None), (7, 5), (6, 4)):
            actor = _extra_actor(kind, second_kind)
            with pytest.raises(ValueError, match="only effect appearances"):
                scalar_policy_inputs(
                    [actor, actor],
                    _UnknownEffectMask(),
                    previous_actions=[2304, 2304],
                    episode_starts=[True, True],
                    extra_public_effect_tokens=(name,),
                )
