"""Gradient-boosted trees without a runtime dependency: a LightGBM model (dump_model JSON) exported to flat arrays and
evaluated with numpy, every tree in lock-step (one gather per depth level). Training needs lightgbm; inference here
needs only numpy (the Mac live player).

Model file (JSON): {format, names, feature, threshold, left, right, value, depth, base, sha}. Node arrays are
[trees, nodes]; a child index < 0 is a leaf: leaf ~child. Decisions are `x[feature] <= threshold` -> left (numeric
splits only; features are never NaN)."""
import hashlib
import json

import numpy as np

FORMAT = 'clasher.playdet.trees.v1'


def from_lightgbm(dump, names):
    """lightgbm Booster.dump_model() -> model dict (binary objective: raw score = sum of leaves, P = sigmoid)."""
    assert dump.get('objective', '').startswith('binary'), dump.get('objective')
    assert list(dump['feature_names']) == list(names), 'feature names differ from features.NAMES'
    trees = dump['tree_info']
    inner = max(1, max(_count(t['tree_structure'])[0] for t in trees))
    leaves = max(_count(t['tree_structure'])[1] for t in trees)
    T = len(trees)
    feat = np.zeros((T, inner), np.int32)
    thr = np.zeros((T, inner), np.float64)
    left = np.full((T, inner), -1, np.int32)
    right = np.full((T, inner), -1, np.int32)
    value = np.zeros((T, leaves), np.float64)
    depth = 0
    for i, t in enumerate(trees):
        root = t['tree_structure']
        if 'split_index' not in root:            # a single-leaf tree: route every row to leaf 0
            value[i, 0] = root['leaf_value']
            left[i, 0] = right[i, 0] = ~0
            thr[i, 0] = np.inf
            continue
        depth = max(depth, _walk(root, i, feat, thr, left, right, value, 1))
    m = dict(format=FORMAT, names=list(names), feature=feat.tolist(), threshold=thr.tolist(), left=left.tolist(),
             right=right.tolist(), value=value.tolist(), depth=depth, base=0.)
    m['sha'] = hashlib.sha256(json.dumps(m, sort_keys=True).encode()).hexdigest()
    return m


def _count(node):
    if 'split_index' not in node:
        return 0, 1
    a, b = _count(node['left_child']), _count(node['right_child'])
    return 1 + a[0] + b[0], a[1] + b[1]


def _walk(node, i, feat, thr, left, right, value, d):
    k = node['split_index']
    assert node.get('decision_type', '<=') == '<=', node.get('decision_type')
    feat[i, k], thr[i, k] = node['split_feature'], node['threshold']
    deepest = d
    for side, arr in (('left_child', left), ('right_child', right)):
        ch = node[side]
        if 'split_index' in ch:
            arr[i, k] = ch['split_index']
            deepest = max(deepest, _walk(ch, i, feat, thr, left, right, value, d + 1))
        else:
            arr[i, k] = ~ch['leaf_index']
            value[i, ch['leaf_index']] = ch['leaf_value']
    return deepest


class Trees:
    def __init__(self, model):
        if isinstance(model, (str, bytes)) or hasattr(model, 'read_text'):
            model = json.loads(open(model).read())
        assert model['format'] == FORMAT
        self.model, self.names = model, model['names']
        self.feature = np.asarray(model['feature'], np.int64)
        self.threshold = np.asarray(model['threshold'], np.float64)
        self.left = np.asarray(model['left'], np.int64)
        self.right = np.asarray(model['right'], np.int64)
        self.value = np.asarray(model['value'], np.float64)
        self.depth, self.base = int(model['depth']), float(model['base'])
        self.rows = np.arange(len(self.feature))

    def raw(self, x):
        """Raw score of one feature vector (sum of the leaves)."""
        x = np.asarray(x, np.float64)
        node = np.zeros(len(self.rows), np.int64)
        for _ in range(self.depth):
            live = node >= 0
            if not live.any():
                break
            n = np.where(live, node, 0)
            go = x[self.feature[self.rows, n]] <= self.threshold[self.rows, n]
            nxt = np.where(go, self.left[self.rows, n], self.right[self.rows, n])
            node = np.where(live, nxt, node)
        return self.base + float(self.value[self.rows, ~node].sum())

    def prob(self, x):
        return 1./(1. + np.exp(-self.raw(x)))

    def raw_batch(self, X):
        """Raw scores of a batch of feature vectors [n, features] (every tree and row in lock-step)."""
        X = np.asarray(X, np.float64)
        if X.ndim != 2 or not len(X):
            return np.zeros(len(X))
        n, T = len(X), len(self.rows)
        node = np.zeros((n, T), np.int64)
        rows = np.broadcast_to(self.rows, (n, T))
        cols = np.arange(n)[:, None]
        for _ in range(self.depth):
            live = node >= 0
            if not live.any():
                break
            k = np.where(live, node, 0)
            go = X[cols, self.feature[rows, k]] <= self.threshold[rows, k]
            nxt = np.where(go, self.left[rows, k], self.right[rows, k])
            node = np.where(live, nxt, node)
        return self.base + self.value[rows, ~node].sum(1)

    def prob_batch(self, X):
        return 1./(1. + np.exp(-self.raw_batch(X)))
