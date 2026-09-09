from types import SimpleNamespace

import numpy as np

from scripts.hog26_scenario_clusters import episode_matchup_cluster


def fixture(style="balanced", seed=1):
    metadata = {
        "seed": seed,
        "outcome_source": "natural-strategy-games",
        "opponents": [style],
        "opponent_decks": ["Giant"],
    }
    corpus = SimpleNamespace(
        episode_ordinals=np.array([0, 0, 1, 1]),
        episode_arrays={
            "episode_opponent_indices": np.zeros(4, int),
            "episode_opponent_deck_indices": np.zeros(4, int),
        },
    )
    return metadata, corpus


def test_deterministic_repeats_do_not_gain_clusters_from_ordinals_or_seeds():
    first, corpus = fixture()
    second, _ = fixture(seed=2)
    clusters = {
        episode_matchup_cluster(meta, corpus, ep)
        for meta in (first, second)
        for ep in range(4)
    }
    assert len(clusters) == 1


def test_random_opponent_retains_draw_identity_and_pairs_seats():
    metadata, corpus = fixture("random")
    clusters = [episode_matchup_cluster(metadata, corpus, ep) for ep in range(4)]
    assert clusters[0] == clusters[1]
    assert clusters[2] == clusters[3]
    assert clusters[0] != clusters[2]


def test_claimed_seeded_openings_cannot_bypass_independence_audit():
    metadata, corpus = fixture()
    metadata["opening_schedule"] = "seeded-ordered-decks-v1"
    metadata["seeded_deals"] = {"scenario_ids_by_stream": [["invented", "different"]]}
    assert episode_matchup_cluster(metadata, corpus, 0) == episode_matchup_cluster(
        metadata, corpus, 2
    )
