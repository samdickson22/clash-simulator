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


def corpus_matchup_clusters(metadata, corpus):
    """Use seeded deal identities only after reconstructing recorded openings."""
    from scripts.hog26_seeded_opening_audit import audit_seeded_openings

    verified = audit_seeded_openings(metadata, corpus)
    if not verified["seeded_openings_verified"]:
        return [
            episode_matchup_cluster(metadata, corpus, episode)
            for episode in range(len(corpus.episode_ordinals))
        ]
    ids = metadata["seeded_deals"]["scenario_ids_by_stream"]
    # ID includes the relative ordered deal and matchup, not seed or ordinal.
    # Paired seats and repeated deals across seeds therefore stay together.
    return [
        json.dumps(
            ["verified-seeded-deal", ids[int(stream)][int(ordinal)]],
            separators=(",", ":"),
        )
        for stream, ordinal in zip(
            corpus.episode_stream_rows, corpus.episode_ordinals, strict=True
        )
    ]
