import pytest

from clasher import battle
from clasher.rl.determinism_check import compute_rollout_digest


@pytest.mark.parametrize("engine_fast_path", ["off", "shadow", "on"])
def test_dense_entity_buckets_preserve_fixed_seed_rollout(
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

    monkeypatch.setattr(battle, "_USE_DENSE_ENTITY_BUCKETS", False)
    mapping = compute_rollout_digest(**common)
    monkeypatch.setattr(battle, "_USE_DENSE_ENTITY_BUCKETS", True)
    dense = compute_rollout_digest(**common)

    assert dense.sha256 == mapping.sha256
    assert dense.mask_shadow_mismatches == mapping.mask_shadow_mismatches == 0
