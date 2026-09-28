from __future__ import annotations

import pytest
import torch

from scripts.audit_rl_state_dict_changes import audit_state_dict_changes


def _state() -> dict[str, torch.Tensor]:
    return {
        "actor.weight": torch.zeros(2),
        "critic.weight": torch.zeros(2),
        "frozen.weight": torch.zeros(2),
    }


def _audit(
    before: dict[str, torch.Tensor], after: dict[str, torch.Tensor]
) -> dict[str, object]:
    return audit_state_dict_changes(
        before,
        after,
        actor_prefixes=("actor.",),
        value_prefixes=("critic.",),
    )


def test_requires_actor_and_value_changes() -> None:
    before = _state()
    after = _state()
    after["actor.weight"] = torch.ones(2)
    after["critic.weight"] = torch.ones(2)

    report = _audit(before, after)

    assert report["passes"] is True
    assert report["actor_changed_parameters"] == ["actor.weight"]
    assert report["value_changed_parameters"] == ["critic.weight"]


def test_rejects_value_only_update() -> None:
    before = _state()
    after = _state()
    after["critic.weight"] = torch.ones(2)

    assert _audit(before, after)["passes"] is False


def test_rejects_unauthorized_change() -> None:
    before = _state()
    after = _state()
    after["actor.weight"] = torch.ones(2)
    after["critic.weight"] = torch.ones(2)
    after["frozen.weight"] = torch.ones(2)

    report = _audit(before, after)

    assert report["passes"] is False
    assert report["unauthorized_changes"] == ["frozen.weight"]


def test_rejects_state_schema_change() -> None:
    before = _state()
    after = _state()
    del after["frozen.weight"]

    with pytest.raises(ValueError, match="removed parameters"):
        _audit(before, after)


def test_allows_declared_zero_upgrade_parameters() -> None:
    before = _state()
    after = _state()
    after["actor.history.weight"] = torch.ones(2)
    after["critic.weight"] = torch.ones(2)

    report = audit_state_dict_changes(
        before,
        after,
        actor_prefixes=("actor.",),
        value_prefixes=("critic.",),
        allowed_added_prefixes=("actor.history.",),
    )

    assert report["passes"] is True
    assert report["added_parameters"] == ["actor.history.weight"]


def test_rejects_undeclared_added_parameters() -> None:
    before = _state()
    after = _state()
    after["actor.history.weight"] = torch.ones(2)

    with pytest.raises(ValueError, match="added unauthorized parameters"):
        _audit(before, after)
