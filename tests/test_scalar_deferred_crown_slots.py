from __future__ import annotations

import pytest

from clasher import entities as entities_module
from clasher.rl.determinism_check import compute_rollout_digest


@pytest.mark.parametrize("engine_fast_path", ["off", "shadow", "on"])
def test_scalar_crown_slots_preserve_fixed_seed_rollout(
    monkeypatch: pytest.MonkeyPatch,
    engine_fast_path: str,
) -> None:
    common = {
        "seed": 8991,
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
        "_USE_SCALAR_DEFERRED_CROWN_SLOTS",
        False,
    )
    listed = compute_rollout_digest(**common)
    monkeypatch.setattr(
        entities_module,
        "_USE_SCALAR_DEFERRED_CROWN_SLOTS",
        True,
    )
    scalar = compute_rollout_digest(**common)

    assert scalar.sha256 == listed.sha256
    assert scalar.mask_shadow_checks == listed.mask_shadow_checks
    assert scalar.mask_shadow_mismatches == listed.mask_shadow_mismatches == 0
