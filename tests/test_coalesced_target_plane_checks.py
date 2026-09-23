from __future__ import annotations

import pytest

from clasher import entities as entities_module
from clasher.rl.determinism_check import compute_rollout_digest


@pytest.mark.parametrize("engine_fast_path", ["off", "shadow", "on"])
def test_coalesced_target_plane_checks_preserve_fixed_seed_rollout(
    monkeypatch,
    engine_fast_path: str,
):
    common = {
        "seed": 8823,
        "decisions": 32,
        "decks_path": "decks.json",
        "decision_interval": 8,
        "max_ticks": 2048,
        "mirror_match": False,
        "quiet_engine": True,
        "engine_fast_path": engine_fast_path,
        "reward_profile": "defense-v2",
    }

    monkeypatch.setattr(entities_module, "_COALESCE_TARGET_PLANE_CHECKS", False)
    reference = compute_rollout_digest(**common)
    monkeypatch.setattr(entities_module, "_COALESCE_TARGET_PLANE_CHECKS", True)
    coalesced = compute_rollout_digest(**common)

    assert coalesced.sha256 == reference.sha256
    assert coalesced.decisions == reference.decisions
    assert coalesced.episodes_finished == reference.episodes_finished
    assert coalesced.mask_shadow_checks == reference.mask_shadow_checks
    assert coalesced.mask_shadow_mismatches == reference.mask_shadow_mismatches == 0
