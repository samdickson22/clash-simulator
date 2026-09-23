from clasher.rl.determinism_check import compute_rollout_digest


def test_rollout_digest_is_reproducible_for_same_seed():
    d1 = compute_rollout_digest(
        seed=1234,
        decisions=64,
        decks_path="decks.json",
        decision_interval=8,
        max_ticks=9090,
        mirror_match=False,
        quiet_engine=True,
        engine_fast_path="off",
    )
    d2 = compute_rollout_digest(
        seed=1234,
        decisions=64,
        decks_path="decks.json",
        decision_interval=8,
        max_ticks=9090,
        mirror_match=False,
        quiet_engine=True,
        engine_fast_path="off",
    )
    assert d1.sha256 == d2.sha256
    assert len(d1.sha256) == 64


def test_rollout_digest_changes_with_different_seed():
    d1 = compute_rollout_digest(
        seed=1234,
        decisions=64,
        decks_path="decks.json",
        decision_interval=8,
        max_ticks=9090,
        mirror_match=False,
        quiet_engine=True,
        engine_fast_path="off",
    )
    d2 = compute_rollout_digest(
        seed=1235,
        decisions=64,
        decks_path="decks.json",
        decision_interval=8,
        max_ticks=9090,
        mirror_match=False,
        quiet_engine=True,
        engine_fast_path="off",
    )
    assert d1.sha256 != d2.sha256


def test_fast_path_matches_scalar_digest_and_shadow_masks():
    common = {
        "seed": 4321,
        "decisions": 64,
        "decks_path": "decks.json",
        "decision_interval": 8,
        "max_ticks": 9090,
        "mirror_match": False,
        "quiet_engine": True,
        "reward_profile": "defense-v2",
    }
    scalar = compute_rollout_digest(**common, engine_fast_path="off")
    shadow = compute_rollout_digest(**common, engine_fast_path="shadow")
    fast = compute_rollout_digest(**common, engine_fast_path="on")

    assert scalar.sha256 == shadow.sha256 == fast.sha256
    assert shadow.mask_shadow_checks > 0
    assert shadow.mask_shadow_mismatches == 0
