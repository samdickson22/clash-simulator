"""Audit existing complete training games and prepare deterministic numeric inputs."""

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from body_features import augmented_features
from body_stats import compile_body_table
from residual_features import FeatureLayout, make_layout
from scalar_evaluation import fitting_weights, fold_masks
from scaling_dataset import load_combined_training

from clasher.rl.simple_pytorch_backend import load_current_client_typed_vocabulary


@dataclass(frozen=True)
class FoldRows:
    fold: int
    mask: np.ndarray
    indices: np.ndarray
    margin_weights: np.ndarray


@dataclass(frozen=True)
class PreparedData:
    features: np.ndarray
    evaluation: tuple
    folds: tuple[FoldRows, ...]
    layout: FeatureLayout
    audit: dict
    input_games: list
    feature_sha256: str


def layout_hash(layout):
    return hashlib.sha256(json.dumps(asdict(layout), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def learner_hand_tokens(vocabulary, learner_cards):
    base = load_current_client_typed_vocabulary()
    if tuple(vocabulary[:len(base.token_names)]) != tuple(base.token_names):
        raise ValueError("public vocabulary prefix changed")
    resolved = tuple(sorted({0, *(base.resolve(card, "card_action") for card in learner_cards)}))
    if len(resolved) != 9 or resolved[1] <= 1:
        raise ValueError("learner hand identities did not resolve")
    return resolved


def prepare_data(plan):
    reference = json.loads((Path(plan.data.globals_directory) / "fitting_manifest.json").read_text())
    games, vocabulary, audit = load_combined_training(
        Path(plan.data.directory), extension_plan=Path(plan.data.collection_plan),
        extension_preflight=Path(plan.data.preflight),
    )
    actual_games = [{"path": str(Path(g.path).resolve()), "sha256": g.sha256} for g in games]
    reference_games = [{"path": str(Path(g["path"]).resolve()), "sha256": g["sha256"]}
                       for g in reference["input_games"]]
    if (audit != plan.data.expected_audit or audit != reference["data_audit"]
            or actual_games != reference_games or tuple(vocabulary) != plan.data.vocabulary):
        raise ValueError("residual corpus differs from reviewed globals training authority")
    tokens = learner_hand_tokens(vocabulary, plan.data.learner_cards)
    if tokens != plan.data.hand_tokens:
        raise ValueError("learner hand contract changed")
    layout = make_layout(len(vocabulary), tokens)
    if layout_hash(layout) != plan.data.feature_layout_sha256:
        raise ValueError("numeric feature layout changed")
    for game in games:
        if not np.all(game.public["global_feature_confidence"][:, 8:14] == 1):
            raise ValueError("baseline requires reviewed fully available tower-health globals")
    table = compile_body_table(vocabulary)
    features = np.empty((plan.data.rows, 809), dtype=np.float32)
    offset = 0
    for game in games:
        block = augmented_features(game.public, layout, table)
        features[offset:offset + len(block)] = block
        offset += len(block)
    if offset != plan.data.rows:
        raise ValueError("semantic row total differs")
    lengths = [len(g.public["global_features"]) for g in games]
    ids = np.repeat(np.arange(len(games)), lengths)
    progress = np.concatenate([g.public["global_features"][:, 0] for g in games])
    labels = np.repeat([g.target_class for g in games], lengths)
    target = np.repeat([g.target_margin for g in games], lengths)
    current = np.concatenate([(g.public["global_features"][:, 8:11].sum(1)
                               - g.public["global_features"][:, 11:14].sum(1)) / 3 for g in games])
    seats = np.repeat([g.seat for g in games], lengths)
    styles = np.repeat([g.style for g in games], lengths)
    families = np.repeat([g.family for g in games], lengths)
    clusters = np.repeat([g.cluster for g in games], lengths)
    fold_ids = np.array([int(f[-3:]) // 2 for f in families])
    evaluation = (ids, progress, labels, target, current, seats, styles, fold_ids, clusters, families)
    folds = []
    for fold in range(4):
        fitting, excluded = fold_masks(ids, families, fold)
        if len(np.unique(ids[fitting])) != 1152 or len(np.unique(ids[excluded])) != 384:
            raise ValueError("residual family-fold counts changed")
        _, margin_weights = fitting_weights(ids, progress, fitting)
        folds.append(FoldRows(fold, fitting, np.flatnonzero(fitting), margin_weights))
    if features.shape != (plan.data.rows, plan.model.inputs):
        raise ValueError("residual feature matrix shape differs")
    feature_sha = hashlib.sha256(memoryview(features).cast("B")).hexdigest()
    if feature_sha != plan.features.matrix_sha256:
        raise ValueError("semantic features differ from public-only audit")
    return PreparedData(features, evaluation, tuple(folds), layout, audit,
                        reference["input_games"], feature_sha)
