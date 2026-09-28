"""Compact the existing public numeric summaries without discarding information."""

from dataclasses import dataclass

import numpy as np
from scalar_features import build_game_features, feature_names


@dataclass(frozen=True)
class FeatureLayout:
    vocabulary_size: int
    hand_tokens: tuple[int, ...]
    columns: tuple[int, ...]
    names: tuple[str, ...]
    scales: tuple[float, ...]


def make_layout(vocabulary_size, hand_tokens):
    tokens = tuple(sorted(set(hand_tokens)))
    if (len(tokens) != 9 or tokens[0] != 0 or tokens[1] <= 1
            or tokens[-1] >= vocabulary_size):
        raise ValueError("expected empty hand plus eight known learner card identities")
    original = feature_names(vocabulary_size)
    columns = tuple(i for i, name in enumerate(original)
                    if not name.startswith("hand") or int(name.split(".token")[1]) in tokens)
    names = tuple(original[i] for i in columns)
    scales = tuple(128.0 if name.endswith(".count") else 1.0 for name in names)
    if len(names) != 425:
        raise ValueError("numeric feature contract must contain 425 columns")
    return FeatureLayout(vocabulary_size, tokens, columns, names, scales)


def numeric_features(public, layout):
    hand = np.asarray(public["hand_ids"])
    confidence = np.asarray(public["hand_id_confidence"])
    if hand.shape != confidence.shape or hand.ndim != 2 or hand.shape[1] != 4:
        raise ValueError("expected four visible hand slots and matching confidence")
    if not np.isin(hand[confidence > 0], layout.hand_tokens).all():
        raise ValueError("visible hand contains a card outside the frozen learner deck")
    original = build_game_features(**public, vocabulary_size=layout.vocabulary_size)
    values = np.ascontiguousarray(original[:, layout.columns])
    values /= np.asarray(layout.scales, dtype=np.float32)
    return values


def build_feature_matrix(games, layout):
    lengths = [len(game.public["global_features"]) for game in games]
    values = np.empty((sum(lengths), len(layout.columns)), dtype=np.float32)
    offset = 0
    for game, length in zip(games, lengths, strict=True):
        block = numeric_features(game.public, layout)
        if len(block) != length:
            raise ValueError("game feature length changed")
        values[offset:offset + length] = block
        offset += length
    return values
