"""Scalar pilot outcome models; accepts only reviewed public observation arrays.

No collector, simulator, policy state, metadata, labels, or reward is imported.
Positions and tower-relative geometry remain in normalized actor coordinates.
Sequence lengths describe padding only; no terminal time is an input feature.
"""

from dataclasses import dataclass

import torch
from torch import Tensor, nn
from torch.nn.utils.rnn import pack_padded_sequence, pad_packed_sequence


@dataclass(frozen=True)
class PublicSequence:
    entity_ids: Tensor
    entity_features: Tensor
    entity_mask: Tensor
    entity_id_confidence: Tensor
    entity_feature_confidence: Tensor
    hand_ids: Tensor
    hand_id_confidence: Tensor
    global_features: Tensor
    global_feature_confidence: Tensor


def _available(values, confidence):
    # The where protects missing entries from NaNs and undefined padding values.
    return torch.where(confidence > 0, values * confidence, torch.zeros_like(values))


class GlobalWDL(nn.Module):
    """18 available public globals plus their 18 availability confidences."""

    def __init__(self):
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(36, 32), nn.GELU(), nn.Linear(32, 32), nn.GELU(), nn.Linear(32, 3)
        )

    def forward(self, global_features, global_feature_confidence):
        if global_features.shape != global_feature_confidence.shape or global_features.shape[-1] != 18:
            raise ValueError("expected matching 18 public globals and confidences")
        return self.network(torch.cat((
            _available(global_features, global_feature_confidence), global_feature_confidence
        ), -1))


class EntityHistoryOutcome(nn.Module):
    """Fixed entity pooling and full-game 64-dimensional causal recurrence.

    Token IDs are vocabulary IDs, never instance IDs. Tower token IDs are public
    vocabulary configuration, supplied once at construction. No caller-supplied
    recurrent state is accepted. Every forward call begins a new full game.
    """

    def __init__(self, vocabulary_size, *, princess_tower_token, king_tower_token):
        super().__init__()
        if vocabulary_size < 3 or len({princess_tower_token, king_tower_token}) != 2:
            raise ValueError("two distinct public tower tokens required")
        if not all(1 < t < vocabulary_size for t in (princess_tower_token, king_tower_token)):
            raise ValueError("tower token outside vocabulary")
        self.vocabulary_size = vocabulary_size
        self.princess_tower_token = princess_tower_token
        self.king_tower_token = king_tower_token
        self.embedding = nn.Embedding(vocabulary_size, 16, padding_idx=0)
        # embedding16 + idconfidence1 + features32 + confidence32 + geometry24
        self.entity_encoder = nn.Sequential(
            nn.Linear(105, 64), nn.GELU(), nn.Linear(64, 64), nn.GELU()
        )
        # 8 groups x (mean64 + max64 + count1), globals36, hand4 x (embed16+conf1).
        self.frame_projection = nn.Sequential(nn.Linear(1136, 64), nn.GELU())
        self.gru = nn.GRU(64, 64, batch_first=True)
        self.wdl = nn.Linear(64, 3)
        self.margin = nn.Linear(64, 1)

    def _validate(self, x, lengths):
        if x.entity_ids.ndim != 3:
            raise ValueError("expected batch,time,entity public arrays")
        b, t, n = x.entity_ids.shape
        expected = {
            "entity_features": (b, t, n, 32), "entity_mask": (b, t, n),
            "entity_id_confidence": (b, t, n), "entity_feature_confidence": (b, t, n, 32),
            "hand_ids": (b, t, 4), "hand_id_confidence": (b, t, 4),
            "global_features": (b, t, 18), "global_feature_confidence": (b, t, 18),
        }
        for name, shape in expected.items():
            if tuple(getattr(x, name).shape) != shape:
                raise ValueError(f"wrong public array shape: {name}")
        if lengths.shape != (b,) or lengths.dtype != torch.long:
            raise ValueError("padding lengths must be int64 per game")
        if bool(((lengths < 1) | (lengths > t)).any()):
            raise ValueError("invalid padding length")
        return b, t, n

    def _embed(self, ids, confidence):
        known = confidence > 0
        if bool((((ids < 0) | (ids >= self.vocabulary_size)) & known).any()):
            raise ValueError("observed token outside frozen vocabulary")
        safe = torch.where(known, ids, torch.zeros_like(ids))
        return self.embedding(safe) * confidence.unsqueeze(-1)

    def tower_geometry(self, ids, features, confidence, identity_confidence, mask):
        """Six current visible tower slots; permutation invariant, no hidden HP.

        Relative dx/dy = entity minus tower in normalized arena coordinates;
        distance is Euclidean in that normalized coordinate system. Slots are
        own-left,own-king,own-right,enemy-left,enemy-king,enemy-right. A single
        surviving princess retains its left/right slot by canonical x < .5.
        """
        xy_known = (confidence[..., :2] > 0).all(-1)
        body = (features[..., 5] > .5) & (confidence[..., 5] > 0)
        known = mask & xy_known & body & (identity_confidence > 0)
        geometry = []
        for side in (2, 3):
            side_mask = (features[..., side] > .5) & (confidence[..., side] > 0)
            for slot in range(3):
                token = self.king_tower_token if slot == 1 else self.princess_tower_token
                selected = known & side_mask & (ids == token)
                if slot != 1:
                    selected &= (features[..., 0] < .5) if slot == 0 else (features[..., 0] >= .5)
                count = selected.sum(-1)
                if bool((count > 1).any()):
                    raise ValueError("multiple visible towers occupy one public slot")
                tower_xy = torch.where(selected.unsqueeze(-1), features[..., :2], 0).sum(-2)
                present = (count > 0).unsqueeze(-1) & xy_known & mask
                delta = features[..., :2] - tower_xy.unsqueeze(-2)
                delta = torch.where(present.unsqueeze(-1), delta, 0)
                distance = torch.linalg.vector_norm(delta, dim=-1, keepdim=True)
                geometry.append(torch.cat((delta, distance, present.unsqueeze(-1).to(features.dtype)), -1))
        return torch.cat(geometry, -1)

    def encode_frames(self, x, lengths):
        b, t, _ = self._validate(x, lengths)
        time_mask = torch.arange(t, device=x.entity_ids.device)[None, :] < lengths.to(x.entity_ids.device)[:, None]
        mask = x.entity_mask.bool() & time_mask.unsqueeze(-1)
        confidence = torch.where(mask.unsqueeze(-1), x.entity_feature_confidence, 0)
        features = _available(x.entity_features, confidence)
        identity_confidence = torch.where(mask, x.entity_id_confidence, 0)
        encoded = self.entity_encoder(torch.cat((
            self._embed(x.entity_ids, identity_confidence), identity_confidence.unsqueeze(-1),
            features, confidence,
            self.tower_geometry(x.entity_ids, features, confidence, identity_confidence, mask),
        ), -1))
        pools = []
        for side in (2, 3):
            for kind in (4, 5, 6, 7):
                selected = mask & (features[..., side] > .5) & (features[..., kind] > .5)
                count = selected.sum(-1, keepdim=True).to(encoded.dtype)
                mean = torch.where(selected.unsqueeze(-1), encoded, 0).sum(-2) / count.clamp_min(1)
                maximum = encoded.masked_fill(~selected.unsqueeze(-1), -torch.inf).amax(-2)
                maximum = torch.where(count > 0, maximum, 0)
                pools.extend((mean, maximum, count))
        gc = torch.where(time_mask.unsqueeze(-1), x.global_feature_confidence, 0)
        hc = torch.where(time_mask.unsqueeze(-1), x.hand_id_confidence, 0)
        hand = torch.cat((self._embed(x.hand_ids, hc), hc.unsqueeze(-1)), -1).reshape(b, t, 68)
        frame = self.frame_projection(torch.cat((
            *pools, _available(x.global_features, gc), gc, hand
        ), -1))
        return frame, time_mask

    def forward(self, x, lengths):
        frames, time_mask = self.encode_frames(x, lengths)
        packed = pack_padded_sequence(frames, lengths.cpu(), batch_first=True, enforce_sorted=False)
        output, hidden = self.gru(packed)  # implicit all-zero reset; no policy state input
        output, _ = pad_packed_sequence(output, batch_first=True, total_length=frames.shape[1])
        logits = self.wdl(output).masked_fill(~time_mask.unsqueeze(-1), 0)
        margin = self.margin(output).squeeze(-1).tanh().masked_fill(~time_mask, 0)
        return logits, margin, hidden
