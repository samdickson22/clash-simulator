from __future__ import annotations

from typing import Any

import pytest

from clasher.rl.reward_model import OBJECTIVE_V1
from clasher.rl.selfplay_env import SelfPlayBattleEnv


def _reward_env(*, gamma: float | None, previous: float) -> SelfPlayBattleEnv:
    env = SelfPlayBattleEnv.__new__(SelfPlayBattleEnv)
    env.battle = object()  # type: ignore[assignment]
    env.reward_profile = OBJECTIVE_V1
    env.reward_shaping_gamma = gamma
    env._prev_reward_potential_p0 = previous
    return env


def test_legacy_reward_delta_remains_checkpoint_compatible(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "clasher.rl.selfplay_env.reward_potential_p0",
        lambda _battle, _profile: 0.6,
    )
    env = _reward_env(gamma=None, previous=0.4)

    assert env._compute_dense_rewards(done=False) == pytest.approx(
        {0: 0.2, 1: -0.2}
    )


def test_gamma_correct_reward_uses_absorbing_zero_terminal_potential(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def potential(_battle: Any, _profile: str) -> float:
        return 0.6

    monkeypatch.setattr("clasher.rl.selfplay_env.reward_potential_p0", potential)
    active = _reward_env(gamma=0.995, previous=0.4)
    terminal = _reward_env(gamma=0.995, previous=0.4)

    assert active._compute_dense_rewards(done=False) == pytest.approx(
        {0: 0.197, 1: -0.197}
    )
    assert terminal._compute_dense_rewards(done=True) == pytest.approx(
        {0: -0.4, 1: 0.4}
    )


@pytest.mark.parametrize("gamma", [0.0, -0.1, 1.01])
def test_reward_experiment_parameters_fail_closed(gamma: float) -> None:
    with pytest.raises(ValueError, match="reward_shaping_gamma"):
        SelfPlayBattleEnv(reward_shaping_gamma=gamma)
    with pytest.raises(ValueError, match="elixir_leak_penalty_scale"):
        SelfPlayBattleEnv(elixir_leak_penalty_scale=-0.01)
