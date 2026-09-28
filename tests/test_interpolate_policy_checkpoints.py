import importlib.util
from pathlib import Path

import pytest
import torch


def _load_script():
    path = Path("scripts/interpolate_policy_checkpoints.py")
    spec = importlib.util.spec_from_file_location("interpolate_policy_checkpoints", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_interpolate_policy_payloads_is_exact_and_drops_optimizer() -> None:
    module = _load_script()
    parent = {
        "format_version": 2,
        "model_config": {"width": 2},
        "token_names": ("a", "b"),
        "update": 28,
        "model_state_dict": {"weight": torch.tensor([0.0, 2.0])},
        "optimizer_state_dict": {"state": {}},
    }
    candidate = {
        **parent,
        "update": 29,
        "model_state_dict": {"weight": torch.tensor([2.0, 6.0])},
    }

    mixed = module.interpolate_policy_payloads(parent, candidate, alpha=0.25)

    assert torch.equal(mixed["model_state_dict"]["weight"], torch.tensor([0.5, 3.0]))
    assert "optimizer_state_dict" not in mixed
    assert mixed["interpolation"]["alpha"] == 0.25


def test_interpolate_policy_payloads_rejects_incompatible_configs() -> None:
    module = _load_script()
    parent = {
        "format_version": 2,
        "model_config": {"width": 2},
        "token_names": ("a",),
        "model_state_dict": {},
    }
    candidate = {**parent, "model_config": {"width": 3}}

    with pytest.raises(ValueError, match="model_config"):
        module.interpolate_policy_payloads(parent, candidate, alpha=0.5)


def test_interpolate_policy_payloads_requires_explicit_extrapolation() -> None:
    module = _load_script()
    parent = {
        "format_version": 2,
        "model_config": {"width": 2},
        "token_names": ("a",),
        "model_state_dict": {"weight": torch.tensor([1.0])},
    }
    candidate = {
        **parent,
        "model_state_dict": {"weight": torch.tensor([2.0])},
    }

    with pytest.raises(ValueError, match="extrapolation"):
        module.interpolate_policy_payloads(parent, candidate, alpha=4.0)
    scaled = module.interpolate_policy_payloads(
        parent,
        candidate,
        alpha=4.0,
        allow_extrapolation=True,
    )

    assert torch.equal(scaled["model_state_dict"]["weight"], torch.tensor([5.0]))


def test_interpolate_accepts_legacy_and_explicit_equivalent_configs() -> None:
    module = _load_script()
    legacy = {
        "num_tokens": 8,
        "max_entities": 4,
        "entity_feature_size": 32,
        "actor_global_size": 18,
        "critic_global_size": 20,
        "d_model": 16,
        "num_heads": 4,
        "actor_layers": 1,
        "critic_layers": 1,
        "memory_size": 16,
        "dropout": 0.0,
    }
    explicit = {
        **legacy,
        "encoder_kind": "attention",
        "decoder_kind": "attention",
        "memory_kind": "lstm",
        "card_input_mode": "hybrid",
        "card_semantics_version": 1,
    }
    parent = {
        "format_version": 2,
        "model_config": legacy,
        "token_names": ("a",),
        "model_state_dict": {"weight": torch.tensor([0.0])},
    }
    candidate = {
        **parent,
        "model_config": explicit,
        "model_state_dict": {"weight": torch.tensor([1.0])},
    }

    mixed = module.interpolate_policy_payloads(parent, candidate, alpha=0.5)

    assert torch.equal(mixed["model_state_dict"]["weight"], torch.tensor([0.5]))
