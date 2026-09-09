"""Training-only tree probe of public margin representation and fitting capacity."""

import numpy as np
import sklearn
from sklearn.ensemble import HistGradientBoostingRegressor


def fit_tree_margin(features, target, weights, fit_rows, *, seed, config):
    if sklearn.__version__ != config["sklearn_version"]:
        raise ValueError("tree diagnostic sklearn version drifted")
    public = features[:, -18:]
    current = (public[:, 8:11].sum(1) - public[:, 11:14].sum(1)) / 3
    model = HistGradientBoostingRegressor(
        loss="absolute_error", learning_rate=config["learning_rate"],
        max_iter=config["max_iter"], max_leaf_nodes=config["max_leaf_nodes"],
        min_samples_leaf=config["min_samples_leaf"],
        l2_regularization=config["l2_regularization"],
        max_bins=config["max_bins"], early_stopping=False, random_state=seed,
    )
    model.fit(features[fit_rows], (target - current)[fit_rows],
              sample_weight=weights[fit_rows])
    # Only final margin is bounded. No time-based suppression or overtime rule.
    return np.clip(current + model.predict(features), -1, 1).astype(np.float32)
