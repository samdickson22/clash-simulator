from types import SimpleNamespace

import numpy as np

from scripts.hog26_public_episode_diversity import (
    PUBLIC_TRANSCRIPT_FIELDS,
    public_episode_diversity,
)


def test_repeated_games_are_detected_despite_different_ordinals_and_labels():
    corpus = SimpleNamespace(
        arrays={
            name: np.zeros((6, 2), np.float32) for name in PUBLIC_TRANSCRIPT_FIELDS
        },
        episode_offsets=np.array([0, 2, 4, 6]),
        episode_stream_rows=np.array([0, 0, 0]),
        episode_ordinals=np.array([0, 1, 2]),
    )
    corpus.arrays["final_outcomes"] = np.array([-1, -1, 0, 0, 1, 1])
    result = public_episode_diversity(corpus)
    assert not result["all_streams_have_distinct_public_transcripts"]
    assert result["streams"][0]["distinct_public_transcripts"] == 1
    corpus.arrays["actions"][2, 0] = 1
    corpus.arrays["hand_ids"][4, 0] = 2
    assert public_episode_diversity(corpus)[
        "all_streams_have_distinct_public_transcripts"
    ]
