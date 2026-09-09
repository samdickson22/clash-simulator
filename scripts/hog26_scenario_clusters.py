"""Conservative episode groups until opening independence is certified."""

import json


def episode_matchup_cluster(metadata, corpus, episode):
    source = metadata.get("outcome_source", "natural-strategy-games")
    seed = int(metadata["seed"])
    ordinal = int(corpus.episode_ordinals[episode])
    if source != "natural-strategy-games":
        return json.dumps([source, seed, ordinal], separators=(",", ":"))
    style = metadata["opponents"][
        int(corpus.episode_arrays["episode_opponent_indices"][episode])
    ]
    deck = metadata["opponent_decks"][
        int(corpus.episode_arrays["episode_opponent_deck_indices"][episode])
    ]
    # Repeated deterministic games from a fixed template are one scenario,
    # including across seeds and paired seats. A declared shuffled opening is
    # not yet sufficient evidence: its independent audit must precede finer
    # grouping. Random-opponent streams already have exogenous action draws.
    if style == "random":
        identity = ["random-action-stream", seed, ordinal]
    else:
        identity = ["uncertified-opening-matchup"]
    return json.dumps([source, style, deck, identity], separators=(",", ":"))
