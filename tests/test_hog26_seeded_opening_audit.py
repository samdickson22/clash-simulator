from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from clasher.rl.simple_pytorch_backend import (
    DEFAULT_SIMPLE_TOKEN_VOCABULARY,
    load_current_client_typed_vocabulary,
    load_simple_supported_decks,
)
from scripts.hog26_seeded_opening_audit import (
    audit_seeded_openings,
    reconstruct_openings,
)


@pytest.fixture(scope="module")
def opening_fixture():
    path = (
        Path(__file__).parents[1]
        / "training_decks/hog26_procedural_supported_seed1278401.json"
    )
    artifact = load_simple_supported_decks(path)
    deck = next(name for name in artifact.deck_names if name != "Hog 2.6 Cycle")
    metadata = {
        "supported_decks_path": str(path),
        "supported_decks_sha256": artifact.sha256,
        "token_names": list(
            load_current_client_typed_vocabulary(
                DEFAULT_SIMPLE_TOKEN_VOCABULARY
            ).token_names
        ),
        "row_opponents": ["balanced", "balanced"],
        "row_opponent_decks": [deck, deck],
        "opponents": ["balanced"],
        "opponent_decks": [deck],
        "seed": 1278951,
        "episodes_per_seat": 4,
        "opening_schedule": "seeded-ordered-decks-v1",
    }
    metadata["seeded_deals"] = reconstruct_openings(metadata)
    hands = np.asarray(metadata["seeded_deals"]["initial_actor_hand_tokens_by_stream"])
    corpus = SimpleNamespace(
        episode_stream_rows=np.repeat([0, 1], 4),
        episode_ordinals=np.tile(np.arange(4), 2),
        episode_offsets=np.arange(9),
        arrays={"hand_ids": hands.reshape(8, 5)},
        episode_arrays={
            "episode_learner_players": np.repeat([0, 1], 4),
            "episode_opponent_indices": np.zeros(8, int),
            "episode_opponent_deck_indices": np.zeros(8, int),
        },
    )
    return metadata, corpus


def test_reconstructs_real_deck_and_public_token_authorities(opening_fixture):
    metadata, corpus = opening_fixture
    result = audit_seeded_openings(metadata, corpus)
    assert result["seeded_openings_verified"]
    assert result["distinct_planned_matchup_deals"] == 4
    assert result["verified_initial_actor_hands"] == 8


@pytest.mark.parametrize(
    "corruption", ["id", "seed", "hand", "ordinal", "authority", "seat"]
)
def test_rejects_opening_provenance_corruption(opening_fixture, corruption):
    metadata, corpus = deepcopy(opening_fixture)
    if corruption == "id":
        metadata["seeded_deals"]["scenario_ids_by_stream"][0][0] = "fabricated"
    elif corruption == "seed":
        metadata["seed"] += 1
    elif corruption == "hand":
        corpus.arrays["hand_ids"][0, 0] = 0
    elif corruption == "ordinal":
        corpus.episode_ordinals[0] = -1
    elif corruption == "authority":
        metadata["supported_decks_sha256"] = "changed"
    else:
        corpus.episode_arrays["episode_learner_players"][0] = 1
    with pytest.raises(ValueError):
        audit_seeded_openings(metadata, corpus)
