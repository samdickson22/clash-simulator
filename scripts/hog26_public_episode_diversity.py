"""Measure repeated complete actor-visible trajectories without using labels."""

import hashlib

import numpy as np

PUBLIC_TRANSCRIPT_FIELDS = (
    "entity_ids",
    "entity_features",
    "entity_mask",
    "hand_ids",
    "global_features",
    "actions",
)


def public_episode_diversity(corpus):
    rows = []
    for episode, (begin, end) in enumerate(
        zip(
            corpus.episode_offsets[:-1],
            corpus.episode_offsets[1:],
            strict=True,
        )
    ):
        digest = hashlib.sha256()
        for name in PUBLIC_TRANSCRIPT_FIELDS:
            value = np.ascontiguousarray(corpus.arrays[name][begin:end])
            digest.update(name.encode())
            digest.update(str(value.dtype).encode())
            digest.update(str(value.shape).encode())
            digest.update(value.tobytes())
        rows.append(
            {
                "stream": int(corpus.episode_stream_rows[episode]),
                "ordinal": int(corpus.episode_ordinals[episode]),
                "public_transcript_sha256": digest.hexdigest(),
                "decisions": int(end - begin),
            }
        )
    streams = []
    for stream in sorted({row["stream"] for row in rows}):
        selected = [row for row in rows if row["stream"] == stream]
        unique = len({row["public_transcript_sha256"] for row in selected})
        streams.append(
            {
                "stream": stream,
                "episodes": len(selected),
                "distinct_public_transcripts": unique,
            }
        )
    return {
        "schema": "clasher.public-episode-diversity.v1",
        "fields": list(PUBLIC_TRANSCRIPT_FIELDS),
        "episodes": rows,
        "streams": streams,
        "all_streams_have_distinct_public_transcripts": all(
            row["episodes"] == row["distinct_public_transcripts"] for row in streams
        ),
        "scope": "exact public trajectory diversity; not a statistical independence or model acceptance certificate",
    }
