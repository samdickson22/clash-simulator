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
    )
    d2 = compute_rollout_digest(
        seed=1234,
        decisions=64,
        decks_path="decks.json",
        decision_interval=8,
        max_ticks=9090,
        mirror_match=False,
        quiet_engine=True,
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
    )
    d2 = compute_rollout_digest(
        seed=1235,
        decisions=64,
        decks_path="decks.json",
        decision_interval=8,
        max_ticks=9090,
        mirror_match=False,
        quiet_engine=True,
    )
    assert d1.sha256 != d2.sha256
