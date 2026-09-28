"""Bounded causal encoder for the existing814 public value features."""

from collections import deque
from copy import copy

import numpy as np
from body_features import body_features
from body_features import feature_names as physical_names
from health_features import augment
from health_features import make_layout as health_layout
from residual_features import make_layout, numeric_features
from scalar_features import LAGS

PUBLIC_FIELDS = ('entity_ids', 'entity_features', 'entity_mask', 'entity_id_confidence',
                 'entity_feature_confidence', 'hand_ids', 'hand_id_confidence',
                 'global_features', 'global_feature_confidence')


class PublicFeatureState:
    """One owner per complete decision stream; static layout/table are immutable resources."""

    def __init__(self, layout, table):
        if layout != make_layout(layout.vocabulary_size, layout.hand_tokens) or len(table.vocabulary) != layout.vocabulary_size:
            raise ValueError('canonical fixed numeric layout and matching body vocabulary required')
        self._layout, self._table = layout, table
        self._health = health_layout((*layout.names, *physical_names()))
        self._global_columns = tuple(layout.names.index(f'global{i}') for i in range(18))
        self._confidence_columns = tuple(layout.names.index(f'global{i}.confidence') for i in range(18))
        self._lags = tuple((lag, tuple(layout.names.index(f'lag{lag}.global{i}.difference') for i in range(18)),
                            layout.names.index(f'lag{lag}.available')) for lag in LAGS)
        self.reset()

    @property
    def seen(self):
        return self._seen

    @property
    def history_frames(self):
        return len(self._history)

    def reset(self):
        self._history = deque(maxlen=max(LAGS))
        self._seen, self._clock = 0, None

    def clone(self):
        other = copy(self)
        other._history = deque(((g.copy(), c.copy()) for g, c in self._history), maxlen=max(LAGS))
        return other

    def step(self, frame):
        if set(frame) != set(PUBLIC_FIELDS):
            raise ValueError('exact public fields required; metadata and labels are not inputs')
        arrays = {key: np.asarray(frame[key]) for key in PUBLIC_FIELDS}
        hand, confidence = arrays['hand_ids'], arrays['hand_id_confidence']
        if hand.shape not in ((4,), (5,)) or confidence.shape != hand.shape:
            raise ValueError('four current hand slots, optionally with one ignored next-card slot, required')
        arrays['hand_ids'], arrays['hand_id_confidence'] = hand[:4], confidence[:4]
        public = {key: value[None, ...] for key, value in arrays.items()}
        numeric = numeric_features(public, self._layout)
        current = numeric[0, list(self._global_columns)].copy()
        current_confidence = numeric[0, list(self._confidence_columns)].copy()
        clock = float(current[0])
        if current_confidence[0] != 1 or clock < 0:
            raise ValueError('fully observed nonnegative public clock required')
        if self._seen == 0 and clock != 0:
            raise ValueError('complete public prefix from game reset required')
        if self._clock is not None and clock <= self._clock:
            raise ValueError('strictly increasing decision clock required; reset at game boundaries')
        for lag, columns, flag in self._lags:
            if self._seen >= lag:
                past, past_confidence = self._history[-lag]
                available = (current_confidence > 0) & (past_confidence > 0)
                numeric[0, list(columns)] = np.where(available, current - past, 0)
                numeric[0, flag] = 1
        base = np.concatenate((numeric, body_features(public, self._table)), axis=1)
        result = augment(base, self._health)[0].copy()
        if result.shape != (814,) or not np.isfinite(result).all():
            raise ValueError('finite814-column public output required')
        # Commit only after every public/static-field and health check succeeds.
        self._history.append((current, current_confidence))
        self._seen, self._clock = self._seen + 1, clock
        return result
