import importlib.util
from pathlib import Path

import pytest
import torch


def _load_script():
    path = Path("scripts/scale_dense_repair_adapter.py")
    spec = importlib.util.spec_from_file_location("scale_dense_repair_adapter", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_scale_dense_repair_payload_changes_only_output_layer() -> None:
    module = _load_script()
    payload = {
        "model_state_dict": {
            "base.weight": torch.tensor([7.0]),
            "repair_adapter.0.weight": torch.tensor([3.0]),
            "repair_adapter.0.bias": torch.tensor([2.0]),
            "repair_adapter.2.weight": torch.tensor([4.0]),
            "repair_adapter.2.bias": torch.tensor([6.0]),
        },
        "optimizer_state_dict": {"state": {}},
    }

    scaled = module.scale_dense_repair_payload(payload, alpha=0.25)

    assert torch.equal(scaled["model_state_dict"]["base.weight"], torch.tensor([7.0]))
    assert torch.equal(
        scaled["model_state_dict"]["repair_adapter.0.weight"],
        torch.tensor([3.0]),
    )
    assert torch.equal(
        scaled["model_state_dict"]["repair_adapter.2.weight"],
        torch.tensor([1.0]),
    )
    assert torch.equal(
        scaled["model_state_dict"]["repair_adapter.2.bias"],
        torch.tensor([1.5]),
    )
    assert "optimizer_state_dict" not in scaled
    assert scaled["repair_adapter_scale"]["alpha"] == 0.25


def test_scale_dense_repair_payload_rejects_invalid_input() -> None:
    module = _load_script()
    payload = {"model_state_dict": {}}

    with pytest.raises(ValueError, match="between zero and one"):
        module.scale_dense_repair_payload(payload, alpha=1.5)
    with pytest.raises(ValueError, match="expected dense repair adapter"):
        module.scale_dense_repair_payload(payload, alpha=0.5)


def test_scale_dense_repair_payload_supports_repair_stages() -> None:
    module = _load_script()
    payload = {
        "model_state_dict": {
            "repair_adapter.2.weight": torch.tensor([5.0]),
            "repair_adapter.2.bias": torch.tensor([7.0]),
            "repair_stages.0.2.weight": torch.tensor([4.0]),
            "repair_stages.0.2.bias": torch.tensor([6.0]),
        }
    }

    scaled = module.scale_dense_repair_payload(
        payload,
        alpha=0.25,
        prefix="repair_stages.0",
    )

    assert torch.equal(
        scaled["model_state_dict"]["repair_adapter.2.weight"],
        torch.tensor([5.0]),
    )
    assert torch.equal(
        scaled["model_state_dict"]["repair_stages.0.2.weight"],
        torch.tensor([1.0]),
    )
    assert scaled["repair_adapter_scale"]["prefix"] == "repair_stages.0"
