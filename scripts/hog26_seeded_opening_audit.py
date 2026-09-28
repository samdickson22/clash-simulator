"""Reconstruct seeded opening provenance from the pinned public deck authority."""

import json
from pathlib import Path

import numpy as np
import torch

from clasher.data import CardDataLoader
from clasher.rl.seeded_deals import SeededDealSchedule
from clasher.rl.simple_pytorch_backend import (
    DEFAULT_SIMPLE_TOKEN_VOCABULARY,
    _learner_deck_rows,
    _typed_lookups,
    load_current_client_typed_vocabulary,
    load_simple_supported_decks,
)
from clasher.torch_sim.simple_standard import (
    _ordered_deck_ids,
    compile_standard_simple_setup,
)


def reconstruct_openings(metadata):
    artifact = load_simple_supported_decks(Path(metadata["supported_decks_path"]))
    if artifact.sha256 != metadata["supported_decks_sha256"]:
        raise ValueError("seeded opening deck authority changed")
    vocabulary = load_current_client_typed_vocabulary(DEFAULT_SIMPLE_TOKEN_VOCABULARY)
    if list(vocabulary.token_names) != metadata["token_names"]:
        raise ValueError("seeded opening public token authority changed")
    styles = metadata["row_opponents"]
    decks = tuple(metadata["row_opponent_decks"])
    rows, seats, actual_decks = _learner_deck_rows(
        artifact,
        batch_size=len(styles),
        learner_deck_name="Hog 2.6 Cycle",
        opponent_deck_name_by_row=decks,
    )
    if actual_decks != decks:
        raise ValueError("seeded opening opponent rows changed")
    loader = CardDataLoader()
    setup = compile_standard_simple_setup(
        loader,
        artifact.public_cards,
        device=torch.device("cpu"),
        canonical_lane_globals=True,
    )
    _, hand_lookup = _typed_lookups(setup, loader, vocabulary)
    keys = [
        json.dumps([style, deck], separators=(",", ":"))
        for style, deck in zip(styles, decks, strict=True)
    ]
    schedule = SeededDealSchedule(
        _ordered_deck_ids(setup, rows),
        torch.tensor(seats),
        keys,
        seed=int(metadata["seed"]),
        episodes=int(metadata["episodes_per_seat"]),
    )
    own_cards = schedule.table[:, torch.arange(len(styles)), torch.tensor(seats), :5]
    expected = schedule.metadata()
    expected["initial_actor_hand_tokens_by_stream"] = (
        hand_lookup[own_cards].permute(1, 0, 2).tolist()
    )
    return expected


def audit_seeded_openings(metadata, corpus):
    mode = metadata.get("opening_schedule", "fixed-template")
    if mode == "fixed-template":
        if metadata.get("seeded_deals") is not None:
            raise ValueError("fixed openings cannot declare seeded deal evidence")
        return {"opening_schedule": mode, "seeded_openings_verified": False}
    if mode != "seeded-ordered-decks-v1":
        raise ValueError("unknown opening schedule")
    expected = reconstruct_openings(metadata)
    if metadata.get("seeded_deals") != expected:
        raise ValueError("seeded opening metadata does not reconstruct from authority")
    streams = np.asarray(corpus.episode_stream_rows)
    ordinals = np.asarray(corpus.episode_ordinals)
    seats = np.asarray(corpus.episode_arrays["episode_learner_players"])
    if not np.array_equal(seats, streams % 2):
        raise ValueError("seeded opening learner seats disagree with collection rows")
    if (
        streams.shape != ordinals.shape
        or (streams < 0).any()
        or (streams >= len(metadata["row_opponents"])).any()
        or (ordinals < 0).any()
        or (ordinals >= metadata["episodes_per_seat"]).any()
    ):
        raise ValueError("seeded opening episode indices are invalid")
    for episode, stream in enumerate(streams):
        style = metadata["opponents"][
            int(corpus.episode_arrays["episode_opponent_indices"][episode])
        ]
        deck = metadata["opponent_decks"][
            int(corpus.episode_arrays["episode_opponent_deck_indices"][episode])
        ]
        if (
            style != metadata["row_opponents"][stream]
            or deck != metadata["row_opponent_decks"][stream]
        ):
            raise ValueError("seeded opening matchup disagrees with collection row")
    planned_hands = np.asarray(expected["initial_actor_hand_tokens_by_stream"])
    actual_hands = np.asarray(corpus.arrays["hand_ids"])[corpus.episode_offsets[:-1]]
    if not np.array_equal(actual_hands, planned_hands[streams, ordinals]):
        raise ValueError("recorded public opening hands disagree with seeded schedule")
    ids = np.asarray(expected["scenario_ids_by_stream"])[streams, ordinals]
    return {
        "opening_schedule": mode,
        "seeded_openings_verified": True,
        "distinct_planned_matchup_deals": len(set(ids.tolist())),
        "verified_initial_actor_hands": len(streams),
        "scope": "schedule reconstruction and recorded learner opening; full-game diversity audited separately",
    }
