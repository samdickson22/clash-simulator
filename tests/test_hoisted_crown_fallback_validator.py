from __future__ import annotations

import pytest

from clasher import entities as entities_module
from clasher.rl.determinism_check import compute_rollout_digest


@pytest.mark.parametrize("engine_fast_path", ["off", "shadow", "on"])
def test_hoisted_crown_validator_preserves_fixed_seed_rollout(
    monkeypatch: pytest.MonkeyPatch,
    engine_fast_path: str,
) -> None:
    common = {
        "seed": 8983,
        "decisions": 32,
        "decks_path": "decks.json",
        "decision_interval": 8,
        "max_ticks": 2048,
        "mirror_match": False,
        "quiet_engine": True,
        "engine_fast_path": engine_fast_path,
        "reward_profile": "defense-v2",
    }

    monkeypatch.setattr(
        entities_module,
        "_USE_HOISTED_CROWN_FALLBACK_VALIDATOR",
        False,
    )
    closure = compute_rollout_digest(**common)
    monkeypatch.setattr(
        entities_module,
        "_USE_HOISTED_CROWN_FALLBACK_VALIDATOR",
        True,
    )
    hoisted = compute_rollout_digest(**common)

    assert hoisted.sha256 == closure.sha256
    assert hoisted.mask_shadow_checks == closure.mask_shadow_checks
    assert hoisted.mask_shadow_mismatches == closure.mask_shadow_mismatches == 0
