import pytest

from clasher import entities
from clasher.rl.determinism_check import compute_rollout_digest


@pytest.mark.parametrize("engine_fast_path", ["off", "shadow", "on"])
def test_small_target_scalar_path_preserves_fixed_seed_rollout(
    monkeypatch,
    engine_fast_path,
):
    common = {
        "seed": 2301,
        "decisions": 32,
        "decks_path": "decks.json",
        "decision_interval": 8,
        "max_ticks": 2048,
        "mirror_match": False,
        "quiet_engine": True,
        "engine_fast_path": engine_fast_path,
        "reward_profile": "defense-v2",
    }

    monkeypatch.setattr(entities, "_FAST_TARGET_VECTOR_MIN_SIZE", 0)
    vector = compute_rollout_digest(**common)
    monkeypatch.setattr(entities, "_FAST_TARGET_VECTOR_MIN_SIZE", 21)
    hybrid = compute_rollout_digest(**common)

    assert hybrid.sha256 == vector.sha256
    assert hybrid.mask_shadow_mismatches == vector.mask_shadow_mismatches == 0
