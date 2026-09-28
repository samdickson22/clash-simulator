from __future__ import annotations

import torch

from scripts.fit_public_reactive_slot_probe import (
    PublicReactiveSlotScorer,
    PublicSlotExamples,
)


def _examples() -> PublicSlotExamples:
    return PublicSlotExamples(
        entity_ids=torch.tensor([[1, 2, 0], [2, 1, 0]]),
        entity_features=torch.rand(2, 3, 4),
        entity_mask=torch.tensor([[True, True, False], [True, True, False]]),
        entity_id_confidence=torch.ones(2, 3),
        entity_feature_confidence=torch.ones(2, 3, 4),
        hand_ids=torch.tensor([[1, 2, 3, 4], [1, 2, 3, 4]]),
        hand_confidence=torch.ones(2, 4),
        global_features=torch.rand(2, 3),
        global_confidence=torch.ones(2, 3),
        legal=torch.ones(2, 4, dtype=torch.bool),
        target=torch.tensor([0, 1]),
        target_card=torch.tensor([1, 2]),
        episode=torch.tensor([0, 1]).numpy(),
    )


def _model() -> PublicReactiveSlotScorer:
    torch.manual_seed(7)
    return PublicReactiveSlotScorer(
        num_tokens=5,
        card_stats=torch.rand(5, 2),
        entity_feature_size=4,
        global_feature_size=3,
        identity_size=3,
        hidden_size=8,
    )


def test_reactive_slot_scorer_is_entity_permutation_invariant() -> None:
    model = _model().eval()
    examples = _examples().select(torch.tensor([0]).numpy())
    permuted = PublicSlotExamples(
        entity_ids=examples.entity_ids[:, [1, 0, 2]],
        entity_features=examples.entity_features[:, [1, 0, 2]],
        entity_mask=examples.entity_mask[:, [1, 0, 2]],
        entity_id_confidence=examples.entity_id_confidence[:, [1, 0, 2]],
        entity_feature_confidence=examples.entity_feature_confidence[:, [1, 0, 2]],
        hand_ids=examples.hand_ids,
        hand_confidence=examples.hand_confidence,
        global_features=examples.global_features,
        global_confidence=examples.global_confidence,
        legal=examples.legal,
        target=examples.target,
        target_card=examples.target_card,
        episode=examples.episode,
    )

    torch.testing.assert_close(model(examples), model(permuted))


def test_reactive_slot_scorer_is_hand_permutation_equivariant() -> None:
    model = _model().eval()
    examples = _examples().select(torch.tensor([0]).numpy())
    order = [2, 0, 3, 1]
    permuted = PublicSlotExamples(
        entity_ids=examples.entity_ids,
        entity_features=examples.entity_features,
        entity_mask=examples.entity_mask,
        entity_id_confidence=examples.entity_id_confidence,
        entity_feature_confidence=examples.entity_feature_confidence,
        hand_ids=examples.hand_ids[:, order],
        hand_confidence=examples.hand_confidence[:, order],
        global_features=examples.global_features,
        global_confidence=examples.global_confidence,
        legal=examples.legal[:, order],
        target=examples.target,
        target_card=examples.target_card,
        episode=examples.episode,
    )

    torch.testing.assert_close(model(permuted), model(examples)[:, order])


def test_unobserved_dynamic_values_do_not_change_scores() -> None:
    model = _model().eval()
    examples = _examples().select(torch.tensor([0]).numpy())
    confidence = examples.entity_feature_confidence.clone()
    confidence[:, 0, :] = 0.0
    hidden = examples.entity_features.clone()
    hidden[:, 0, :] = 1000.0
    altered = PublicSlotExamples(
        entity_ids=examples.entity_ids,
        entity_features=hidden,
        entity_mask=examples.entity_mask,
        entity_id_confidence=examples.entity_id_confidence,
        entity_feature_confidence=confidence,
        hand_ids=examples.hand_ids,
        hand_confidence=examples.hand_confidence,
        global_features=examples.global_features,
        global_confidence=examples.global_confidence,
        legal=examples.legal,
        target=examples.target,
        target_card=examples.target_card,
        episode=examples.episode,
    )
    baseline = PublicSlotExamples(
        entity_ids=examples.entity_ids,
        entity_features=examples.entity_features,
        entity_mask=examples.entity_mask,
        entity_id_confidence=examples.entity_id_confidence,
        entity_feature_confidence=confidence,
        hand_ids=examples.hand_ids,
        hand_confidence=examples.hand_confidence,
        global_features=examples.global_features,
        global_confidence=examples.global_confidence,
        legal=examples.legal,
        target=examples.target,
        target_card=examples.target_card,
        episode=examples.episode,
    )

    torch.testing.assert_close(model(altered), model(baseline))
