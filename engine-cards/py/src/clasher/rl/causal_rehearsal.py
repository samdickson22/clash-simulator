from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
from torch import Tensor

from .hierarchical_imitation import (
    PLACEMENT_ACTIONS,
    PLAY_DECISION,
    HierarchicalImitationConfig,
    factor_public_action_mask,
    hierarchical_masked_imitation_loss,
    labels_from_flat_actions,
)
from .model import ClasherPolicy, PolicyInputs, PolicyOutput
from .public_action_mask import PUBLIC_ACTION_MASK_CONTRACT_VERSION
from .public_observation import (
    PUBLIC_OBSERVATION_SCHEMA_VERSION,
    REAL_PLAY_FEATURE_CONTRACT_VERSION,
)


@dataclass
class CausalDecisionRehearsal:
    """Trusted public-frame cadence supervision sampled during outcome PPO.

    The component deliberately supervises only play/wait/ability. Card identity,
    placement, and gameplay value remain PPO responsibilities. Uncertain or
    public-mask-incompatible labels stay recurrent context and contribute zero
    supervised loss.
    """

    corpus: Path
    sidecar: Path
    arrays: dict[str, np.ndarray]
    chunks: np.ndarray
    rng: np.random.Generator

    @classmethod
    def load(
        cls,
        corpus: Path,
        sidecar: Path,
        *,
        token_names: tuple[str, ...],
        max_entities: int,
        sequence_length: int,
        seed: int,
    ) -> CausalDecisionRehearsal:
        if sequence_length <= 0:
            raise ValueError("causal rehearsal sequence length must be positive")
        base_names = (
            "entity_ids",
            "entity_features",
            "entity_mask",
            "hand_ids",
            "global_features",
            "action_masks",
            "previous_actions",
            "previous_rewards",
            "episode_starts",
            "expert_actions",
            "expert_action_supervision_valid",
            "episode_ids",
            "source_frames",
        )
        with np.load(corpus, allow_pickle=False) as payload:
            missing = [name for name in base_names if name not in payload]
            if missing:
                raise ValueError(f"causal rehearsal corpus is missing arrays: {missing}")
            metadata = json.loads(str(payload["metadata_json"].item()))
            base = {name: payload[name].copy() for name in base_names}
            optional_supervision = {
                name: payload[name].copy()
                for name in (
                    "expert_card_supervision_valid",
                    "expert_tile_supervision_valid",
                )
                if name in payload
            }
        if tuple(metadata["token_names"]) != token_names:
            raise ValueError("causal rehearsal token vocabulary differs")
        if int(metadata["max_entities"]) != max_entities:
            raise ValueError("causal rehearsal max_entities differs")

        sidecar_names = (
            "entity_ids",
            "entity_features",
            "entity_mask",
            "entity_id_confidence",
            "entity_feature_confidence",
            "hand_ids",
            "hand_id_confidence",
            "global_features",
            "global_feature_confidence",
            "action_masks",
            "expert_action_masked",
            "expert_actions",
            "episode_ids",
            "source_frames",
        )
        with np.load(sidecar, allow_pickle=False) as payload:
            for name, expected in (
                ("schema_version", PUBLIC_OBSERVATION_SCHEMA_VERSION),
                ("feature_contract_version", REAL_PLAY_FEATURE_CONTRACT_VERSION),
                (
                    "action_mask_contract_version",
                    PUBLIC_ACTION_MASK_CONTRACT_VERSION,
                ),
            ):
                if name not in payload or int(payload[name].item()) != expected:
                    raise ValueError(f"unsupported causal rehearsal {name}")
            missing = [name for name in sidecar_names if name not in payload]
            if missing:
                raise ValueError(f"causal rehearsal sidecar is missing arrays: {missing}")
            public = {name: payload[name].copy() for name in sidecar_names}

        samples = int(base["expert_actions"].shape[0])
        if any(values.shape[0] != samples for values in base.values()):
            raise ValueError("causal rehearsal corpus arrays have different lengths")
        if any(values.shape[0] != samples for values in public.values()):
            raise ValueError("causal rehearsal sidecar arrays have different lengths")
        for name in ("expert_actions", "episode_ids", "source_frames"):
            if not np.array_equal(base[name], public[name]):
                raise ValueError(f"causal rehearsal sidecar {name} is not aligned")
        for name in ("entity_ids", "entity_features", "entity_mask", "hand_ids", "global_features", "action_masks"):
            if public[name].shape != base[name].shape:
                raise ValueError(f"causal rehearsal sidecar {name} shape differs")

        confidence_pairs = (
            ("entity_ids", "entity_id_confidence"),
            ("entity_features", "entity_feature_confidence"),
            ("hand_ids", "hand_id_confidence"),
            ("global_features", "global_feature_confidence"),
        )
        for value_name, confidence_name in confidence_pairs:
            confidence = public[confidence_name]
            if confidence.shape != public[value_name].shape:
                raise ValueError(f"causal rehearsal {confidence_name} shape differs")
            if not np.isfinite(confidence).all() or np.any(
                (confidence < 0.0) | (confidence > 1.0)
            ):
                raise ValueError(
                    f"causal rehearsal {confidence_name} must be finite in [0, 1]"
                )
            if np.any(public[value_name][confidence <= 0.0] != 0):
                raise ValueError(
                    f"causal rehearsal {value_name} fabricates unknown values"
                )

        action_masks = public["action_masks"].astype(np.bool_, copy=False)
        actions = base["expert_actions"].astype(np.int64, copy=False)
        masked = ~action_masks[np.arange(samples), actions]
        if not np.array_equal(masked, public["expert_action_masked"]):
            raise ValueError("causal rehearsal expert_action_masked is inconsistent")
        supervised = base["expert_action_supervision_valid"].astype(
            np.bool_, copy=False
        )
        if np.any(supervised & masked):
            raise ValueError("causal rehearsal contains a supervised masked action")

        arrays = dict(base)
        placement = actions < PLACEMENT_ACTIONS
        card_supervised = np.asarray(
            optional_supervision.get(
                "expert_card_supervision_valid",
                supervised & placement,
            ),
            dtype=np.bool_,
        )
        tile_supervised = np.asarray(
            optional_supervision.get(
                "expert_tile_supervision_valid",
                np.zeros_like(supervised),
            ),
            dtype=np.bool_,
        )
        if card_supervised.shape != supervised.shape or tile_supervised.shape != supervised.shape:
            raise ValueError("causal rehearsal component supervision shape differs")
        if np.any(card_supervised & (~supervised | ~placement)):
            raise ValueError("causal rehearsal card supervision is not trusted placement")
        if np.any(tile_supervised & ~card_supervised):
            raise ValueError("causal rehearsal tile supervision requires trusted card")
        arrays.update(public)
        arrays["expert_action_supervision_valid"] = supervised & ~masked
        arrays["expert_card_supervision_valid"] = card_supervised & ~masked
        arrays["expert_tile_supervision_valid"] = tile_supervised & ~masked
        arrays["previous_rewards"] = np.zeros_like(
            base["previous_rewards"], dtype=np.float32
        )

        chunks: list[np.ndarray] = []
        episode_ids = arrays["episode_ids"]
        start = 0
        while start < samples:
            end = start + 1
            while end < samples and episode_ids[end] == episode_ids[start]:
                end += 1
            for chunk_start in range(start, end - sequence_length + 1, sequence_length):
                chunk = np.arange(
                    chunk_start, chunk_start + sequence_length, dtype=np.int64
                )
                if np.any(arrays["expert_action_supervision_valid"][chunk]):
                    chunks.append(chunk)
            start = end
        if not chunks:
            raise ValueError("causal rehearsal has no supervised sequence chunks")
        return cls(
            corpus=corpus,
            sidecar=sidecar,
            arrays=arrays,
            chunks=np.stack(chunks),
            rng=np.random.default_rng(seed),
        )

    def loss(
        self,
        model: ClasherPolicy,
        *,
        device: torch.device,
        batch_sequences: int,
        decision_loss_coef: float = 1.0,
        decision_positive_weight: float | None = None,
        card_loss_coef: float = 0.0,
        tile_loss_coef: float = 0.0,
    ) -> Tensor:
        if batch_sequences <= 0:
            raise ValueError("causal rehearsal batch size must be positive")
        if decision_loss_coef < 0.0:
            raise ValueError(
                "causal rehearsal decision loss coefficient cannot be negative"
            )
        if decision_positive_weight is not None and decision_positive_weight <= 0.0:
            raise ValueError(
                "causal rehearsal decision positive weight must be positive"
            )
        if card_loss_coef < 0.0:
            raise ValueError("causal rehearsal card loss coefficient cannot be negative")
        if tile_loss_coef < 0.0:
            raise ValueError("causal rehearsal tile loss coefficient cannot be negative")
        selected = self.chunks[
            self.rng.integers(0, len(self.chunks), size=batch_sequences)
        ]

        def tensor(name: str, dtype: torch.dtype) -> Tensor:
            return torch.as_tensor(
                self.arrays[name][selected], dtype=dtype, device=device
            )

        inputs = PolicyInputs(
            entity_ids=tensor("entity_ids", torch.long),
            entity_features=tensor("entity_features", torch.float32),
            entity_mask=tensor("entity_mask", torch.bool),
            hand_ids=tensor("hand_ids", torch.long),
            global_features=tensor("global_features", torch.float32),
            action_mask=tensor("action_masks", torch.bool),
            previous_actions=tensor("previous_actions", torch.long),
            previous_rewards=tensor("previous_rewards", torch.float32),
            episode_starts=tensor("episode_starts", torch.bool),
            entity_id_confidence=tensor("entity_id_confidence", torch.float32),
            entity_feature_confidence=tensor(
                "entity_feature_confidence", torch.float32
            ),
            hand_id_confidence=tensor("hand_id_confidence", torch.float32),
            global_feature_confidence=tensor(
                "global_feature_confidence", torch.float32
            ),
        )
        targets = tensor("expert_actions", torch.long).reshape(-1)
        trusted = tensor("expert_action_supervision_valid", torch.bool).reshape(-1)
        card_trusted = tensor(
            "expert_card_supervision_valid", torch.bool
        ).reshape(-1)
        tile_trusted = tensor(
            "expert_tile_supervision_valid", torch.bool
        ).reshape(-1)
        output: PolicyOutput = model(inputs)
        action_type_logits = output.action_type_logits.reshape(-1, 6)
        decision_logits = torch.cat(
            (
                torch.logsumexp(action_type_logits[:, :4], dim=-1, keepdim=True),
                action_type_logits[:, 4:],
            ),
            dim=-1,
        )
        public_masks = factor_public_action_mask(
            inputs.action_mask.reshape(-1, inputs.action_mask.shape[-1])
        )
        labels = labels_from_flat_actions(
            targets,
            decision_trusted=trusted,
            card_trusted=(card_trusted if card_loss_coef > 0.0 else torch.zeros_like(card_trusted)),
            tile_trusted=(tile_trusted if tile_loss_coef > 0.0 else torch.zeros_like(tile_trusted)),
        )
        if output.play_hazard_logits is not None:
            hazard_trusted = trusted & public_masks.decision[:, PLAY_DECISION]
            if not bool(hazard_trusted.any()):
                return output.play_hazard_logits.sum() * 0.0
            hazard_targets = (targets < PLACEMENT_ACTIONS).to(torch.float32)
            hazard_logits = output.play_hazard_logits.reshape(-1)
            effective_positive_weight = (
                model.config.play_hazard_positive_weight
                if decision_positive_weight is None
                else decision_positive_weight
            )
            loss_logits = hazard_logits
            if decision_positive_weight is not None:
                # Inference consumes raw_logit - log(model_positive_weight).
                # Preserve that calibrated probability while allowing this
                # corpus to use a different BCE sampling weight.
                loss_logits = (
                    hazard_logits
                    - math.log(model.config.play_hazard_positive_weight)
                    + math.log(effective_positive_weight)
                )
            per_row = torch.nn.functional.binary_cross_entropy_with_logits(
                loss_logits[hazard_trusted],
                hazard_targets[hazard_trusted],
                pos_weight=torch.tensor(
                    effective_positive_weight,
                    dtype=hazard_logits.dtype,
                    device=hazard_logits.device,
                ),
                reduction="none",
            )
            decision_loss = per_row.mean()
            if card_loss_coef == 0.0 and tile_loss_coef == 0.0:
                return decision_loss_coef * decision_loss
        decision_loss_logits = decision_logits
        if output.play_hazard_logits is None and decision_positive_weight is not None:
            # Weighted cross entropy shifts the optimal play log-odds by
            # log(weight). Add that offset only inside the loss so the model's
            # emitted/direct-decoding logits remain calibrated at inference.
            decision_loss_logits = torch.cat(
                (
                    decision_logits[:, :1] + math.log(decision_positive_weight),
                    decision_logits[:, 1:],
                ),
                dim=-1,
            )
        breakdown = hierarchical_masked_imitation_loss(
            decision_loss_logits,
            action_type_logits[:, :4],
            output.location_logits.reshape(-1, 4, 576),
            public_masks,
            labels,
            config=HierarchicalImitationConfig(
                decision_loss_coef=1.0,
                card_loss_coef=1.0,
                tile_loss_coef=1.0,
            ),
            decision_sample_weights=(
                None
                if output.play_hazard_logits is not None
                or decision_positive_weight is None
                else torch.where(
                    labels.decision_target == PLAY_DECISION,
                    torch.full_like(
                        labels.decision_target,
                        decision_positive_weight,
                        dtype=decision_logits.dtype,
                    ),
                    torch.ones_like(
                        labels.decision_target,
                        dtype=decision_logits.dtype,
                    ),
                )
            ),
        )
        if output.play_hazard_logits is None:
            decision_loss = breakdown.decision
        return (
            decision_loss_coef * decision_loss
            + card_loss_coef * breakdown.card
            + tile_loss_coef * breakdown.tile
        )
