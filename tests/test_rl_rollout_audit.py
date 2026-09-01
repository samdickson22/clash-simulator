from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest

from clasher.rl.rollout_audit import build_rollout_audit, write_rollout_audit


@dataclass
class _TinyRollout:
    actions: np.ndarray
    rewards: np.ndarray
    optional: np.ndarray | None
    episodes_finished: int

    @property
    def transitions(self) -> int:
        return int(self.actions.size)


def _rollout() -> _TinyRollout:
    return _TinyRollout(
        actions=np.array([[1, 2], [3, 4]], dtype=np.int64),
        rewards=np.array([[0.0, -0.0], [1.25, -2.5]], dtype=np.float32),
        optional=None,
        episodes_finished=1,
    )


def test_rollout_audit_is_exact_and_field_attributed() -> None:
    first = build_rollout_audit(_rollout(), update=1, seed=17)
    second = build_rollout_audit(_rollout(), update=1, seed=17)
    assert first == second
    assert first["transitions"] == 4
    assert first["fields"]["actions"]["dtype"] == "<i8"

    changed = _rollout()
    changed.rewards[0, 1] = 0.0
    third = build_rollout_audit(changed, update=1, seed=17)
    assert first["rollout_sha256"] != third["rollout_sha256"]
    assert first["fields"]["actions"] == third["fields"]["actions"]
    assert first["fields"]["rewards"] != third["fields"]["rewards"]


def test_rollout_audit_refuses_to_overwrite(tmp_path: Path) -> None:
    path = tmp_path / "rollout.json"
    payload = write_rollout_audit(path, _rollout(), update=1, seed=23)
    assert path.is_file()
    assert len(payload["rollout_sha256"]) == 64
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        write_rollout_audit(path, _rollout(), update=1, seed=23)
