"""Opened diagnostic inputs, accessible only after a verified evaluation pin."""

import json

import numpy as np
from body_features import augmented_features
from body_stats import compile_body_table
from evaluation_authority import validate_pin
from health_features import augment, make_layout
from residual_features import make_layout as numeric_layout
from semantic_contract import FrozenPlan
from semantic_data import layout_hash
from value_contract import CACHE, ROOT


def load_diagnostic(*, verified_pin):
    validate_pin(verified_pin)
    from transfer_dataset import load_complete_pilot

    games, vocabulary, audit = load_complete_pilot(
        ROOT / 'datasets/derived/hog26_seed_transfer_seed1279601_20260911',
        plan_path=ROOT / 'reports/hog26_seed_transfer_frozen_plan_20260911.json',
        preflight_path=ROOT / 'reports/hog26_seed_transfer_preflight_pin_20260911.json')
    reference = json.loads((ROOT / 'reports/hog26_scaling_seed_transfer_evaluation_20260912/evaluation_manifest.json').read_text())
    feature_plan = FrozenPlan.model_validate_json((ROOT / 'reports/hog26_semantic_margin_frozen_plan_20260912.json').read_text())
    if audit != reference['data_audit'] or tuple(vocabulary) != feature_plan.data.vocabulary or len(games) != 384:
        raise ValueError('opened diagnostic identity differs')
    numeric = numeric_layout(len(vocabulary), feature_plan.data.hand_tokens)
    if layout_hash(numeric) != feature_plan.data.feature_layout_sha256:
        raise ValueError('numeric feature definition changed')
    names = json.loads((CACHE / 'complete.json').read_text())['feature_names']
    layout = make_layout(names)
    table = compile_body_table(vocabulary)
    base = np.concatenate([augmented_features(game.public, numeric, table) for game in games])
    lengths = [len(game.public['global_features']) for game in games]
    ids = np.repeat(np.arange(384), lengths)
    progress = np.concatenate([game.public['global_features'][:, 0] for game in games])
    labels, target, seats, styles, families, clusters = [np.repeat([getattr(game, key) for game in games], lengths)
                                                       for key in ('target_class', 'target_margin', 'seat', 'style', 'family', 'cluster')]
    current = np.concatenate([(game.public['global_features'][:, 8:11].sum(1)
                              - game.public['global_features'][:, 11:14].sum(1)) / 3 for game in games])
    features = augment(base, layout)
    if (len(ids) != 155496 or not np.array_equal(features[:, -1], current)
            or not np.array_equal(base[:, names.index('global0')], progress)):
        raise ValueError('diagnostic public baseline, progress or row count differs')
    folds = np.array([int(family[-3:]) // 2 for family in families], dtype=np.int8)
    evaluation = (ids, progress, labels, target, current, seats, styles, folds, clusters, families)
    globals_x = np.ascontiguousarray(base[:, layout.globals])
    return features, globals_x, np.r_[0, np.cumsum(lengths)], evaluation, audit
