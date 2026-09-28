from __future__ import annotations

import pytest
import torch

from scripts.add_mechanics_slot_choice_adapter import (
    add_mechanics_slot_choice_adapter,
)
from scripts.verify_zero_mechanics_slot_initializer import (
    verify_checkpoint_structure,
)
from tests.test_add_mechanics_slot_choice_adapter import _payload


def test_zero_adapter_structure_accepts_exact_upgrade() -> None:
    source, card_stats = _payload()
    candidate = add_mechanics_slot_choice_adapter(
        source,
        card_stat_features=card_stats,
    )

    result = verify_checkpoint_structure(source, candidate)

    assert result["query_nonzero_count"] == 0
    assert result["inherited_tensor_count"] == len(source["model_state_dict"])


def test_zero_adapter_structure_rejects_changed_inherited_tensor() -> None:
    source, card_stats = _payload()
    candidate = add_mechanics_slot_choice_adapter(
        source,
        card_stat_features=card_stats,
    )
    changed_name = next(
        name
        for name, tensor in source["model_state_dict"].items()
        if tensor.is_floating_point()
    )
    candidate["model_state_dict"][changed_name] = (
        candidate["model_state_dict"][changed_name].clone() + 1.0
    )

    with pytest.raises(ValueError, match=f"{changed_name} tensor values changed"):
        verify_checkpoint_structure(source, candidate)


def test_zero_adapter_structure_rejects_nonzero_query() -> None:
    source, card_stats = _payload()
    candidate = add_mechanics_slot_choice_adapter(
        source,
        card_stat_features=card_stats,
    )
    candidate["model_state_dict"]["mechanics_slot_choice_query.weight"] = (
        torch.ones_like(
            candidate["model_state_dict"]["mechanics_slot_choice_query.weight"]
        )
    )

    with pytest.raises(ValueError, match="query is not exactly zero"):
        verify_checkpoint_structure(source, candidate)
