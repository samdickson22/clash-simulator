from __future__ import annotations

from dataclasses import dataclass

import torch
from torch import Tensor, nn

from .common import BOARD_WIDTH, NUM_HAND_SLOTS, NUM_TILES

PLACEMENT_ACTIONS = NUM_HAND_SLOTS * NUM_TILES
NO_OP_ACTION = PLACEMENT_ACTIONS
ABILITY_ACTION = PLACEMENT_ACTIONS + 1
NUM_ACTIONS = ABILITY_ACTION + 1

PLAY_DECISION = 0
WAIT_DECISION = 1
ABILITY_DECISION = 2
NUM_DECISIONS = 3
UNKNOWN_LABEL = -1


@dataclass(frozen=True)
class HierarchicalImitationConfig:
    """Weights for independently normalized trusted supervision components."""

    decision_loss_coef: float = 1.0
    card_loss_coef: float = 1.0
    tile_loss_coef: float = 1.0

    def validate(self) -> None:
        for name, value in (
            ("decision_loss_coef", self.decision_loss_coef),
            ("card_loss_coef", self.card_loss_coef),
            ("tile_loss_coef", self.tile_loss_coef),
        ):
            if value < 0.0:
                raise ValueError(f"{name} cannot be negative")


@dataclass(frozen=True)
class HierarchicalPublicMasks:
    """Label-independent public legality for each hierarchical action head."""

    decision: Tensor
    card: Tensor
    tile: Tensor


@dataclass(frozen=True)
class HierarchicalImitationLabels:
    """Targets whose trust masks state exactly which facts were observed.

    An untrusted target must be ``UNKNOWN_LABEL``. In particular, an uncertain
    play is not converted into wait, and an uncertain placement is not
    converted into tile zero.
    """

    decision_target: Tensor
    decision_trusted: Tensor
    card_target: Tensor
    card_trusted: Tensor
    tile_target: Tensor
    tile_trusted: Tensor


@dataclass(frozen=True)
class HierarchicalImitationLoss:
    total: Tensor
    decision: Tensor
    card: Tensor
    tile: Tensor
    decision_count: Tensor
    card_count: Tensor
    tile_count: Tensor


def factor_public_action_mask(action_mask: Tensor) -> HierarchicalPublicMasks:
    """Factor a public flat action mask without consulting imitation labels."""

    if action_mask.ndim != 2 or action_mask.shape[1] != NUM_ACTIONS:
        raise ValueError(f"action_mask must have shape [batch, {NUM_ACTIONS}]")
    if action_mask.dtype != torch.bool:
        raise ValueError("action_mask must be boolean")
    tile = action_mask[:, :PLACEMENT_ACTIONS].reshape(
        -1, NUM_HAND_SLOTS, NUM_TILES
    )
    card = tile.any(dim=-1)
    decision = torch.stack(
        (
            card.any(dim=-1),
            action_mask[:, NO_OP_ACTION],
            action_mask[:, ABILITY_ACTION],
        ),
        dim=-1,
    )
    return HierarchicalPublicMasks(decision=decision, card=card, tile=tile)


def labels_from_flat_actions(
    actions: Tensor,
    *,
    decision_trusted: Tensor,
    card_trusted: Tensor,
    tile_trusted: Tensor,
) -> HierarchicalImitationLabels:
    """Decode trusted parts of flat actions while preserving unknowns.

    Trust is deliberately supplied independently of the action value. This
    helper never upgrades a weak visual label merely because its encoded action
    happens to look valid.
    """

    if actions.ndim != 1 or actions.dtype != torch.long:
        raise ValueError("actions must be a one-dimensional int64 tensor")
    for name, trusted in (
        ("decision_trusted", decision_trusted),
        ("card_trusted", card_trusted),
        ("tile_trusted", tile_trusted),
    ):
        if trusted.shape != actions.shape or trusted.dtype != torch.bool:
            raise ValueError(f"{name} must be a boolean tensor shaped like actions")

    placement = (actions >= 0) & (actions < PLACEMENT_ACTIONS)
    in_range = (actions >= 0) & (actions < NUM_ACTIONS)
    if bool((decision_trusted & ~in_range).any()):
        raise ValueError("trusted decision action is outside the action space")
    if bool((card_trusted & ~placement).any()):
        raise ValueError("trusted card identity requires a placement action")
    if bool((tile_trusted & ~placement).any()):
        raise ValueError("trusted tile requires a placement action")

    decision = torch.full_like(actions, UNKNOWN_LABEL)
    decoded_decision = torch.where(
        placement,
        torch.full_like(actions, PLAY_DECISION),
        torch.where(
            actions == NO_OP_ACTION,
            torch.full_like(actions, WAIT_DECISION),
            torch.full_like(actions, ABILITY_DECISION),
        ),
    )
    decision[decision_trusted] = decoded_decision[decision_trusted]
    card = torch.full_like(actions, UNKNOWN_LABEL)
    card[card_trusted] = actions[card_trusted] // NUM_TILES
    tile = torch.full_like(actions, UNKNOWN_LABEL)
    tile[tile_trusted] = actions[tile_trusted] % NUM_TILES
    return HierarchicalImitationLabels(
        decision_target=decision,
        decision_trusted=decision_trusted,
        card_target=card,
        card_trusted=card_trusted,
        tile_target=tile,
        tile_trusted=tile_trusted,
    )


def _validate_labels(
    labels: HierarchicalImitationLabels,
    masks: HierarchicalPublicMasks,
) -> int:
    batch_size = int(masks.decision.shape[0])
    if masks.decision.shape != (batch_size, NUM_DECISIONS):
        raise ValueError("decision mask must have shape [batch, 3]")
    if masks.card.shape != (batch_size, NUM_HAND_SLOTS):
        raise ValueError("card mask must have shape [batch, 4]")
    if masks.tile.shape != (batch_size, NUM_HAND_SLOTS, NUM_TILES):
        raise ValueError("tile mask must have shape [batch, 4, 576]")
    if not torch.equal(masks.card, masks.tile.any(dim=-1)):
        raise ValueError("card mask must equal the public tile support")
    if not torch.equal(masks.decision[:, PLAY_DECISION], masks.card.any(dim=-1)):
        raise ValueError("play mask must equal the public card support")
    for name, value in (
        ("decision mask", masks.decision),
        ("card mask", masks.card),
        ("tile mask", masks.tile),
        ("decision_trusted", labels.decision_trusted),
        ("card_trusted", labels.card_trusted),
        ("tile_trusted", labels.tile_trusted),
    ):
        if value.dtype != torch.bool:
            raise ValueError(f"{name} must be boolean")
    for name, value in (
        ("decision_target", labels.decision_target),
        ("card_target", labels.card_target),
        ("tile_target", labels.tile_target),
    ):
        if value.shape != (batch_size,) or value.dtype != torch.long:
            raise ValueError(f"{name} must be an int64 tensor shaped [batch]")
    for name, value in (
        ("decision_trusted", labels.decision_trusted),
        ("card_trusted", labels.card_trusted),
        ("tile_trusted", labels.tile_trusted),
    ):
        if value.shape != (batch_size,):
            raise ValueError(f"{name} must have shape [batch]")
    tensors = (
        masks.decision,
        masks.card,
        masks.tile,
        labels.decision_target,
        labels.decision_trusted,
        labels.card_target,
        labels.card_trusted,
        labels.tile_target,
        labels.tile_trusted,
    )
    if any(value.device != masks.decision.device for value in tensors):
        raise ValueError("hierarchical masks and labels must share one device")

    for target_name, target, trusted in (
        ("decision", labels.decision_target, labels.decision_trusted),
        ("card", labels.card_target, labels.card_trusted),
        ("tile", labels.tile_target, labels.tile_trusted),
    ):
        if bool((target[~trusted] != UNKNOWN_LABEL).any()):
            raise ValueError(f"untrusted {target_name} targets must be UNKNOWN_LABEL")
    if bool((labels.card_trusted & ~labels.decision_trusted).any()):
        raise ValueError("trusted card identity requires a trusted decision")
    if bool(
        (
            labels.card_trusted
            & (labels.decision_target != PLAY_DECISION)
        ).any()
    ):
        raise ValueError("trusted card identity requires a play decision")
    if bool((labels.tile_trusted & ~labels.card_trusted).any()):
        raise ValueError("trusted tile requires trusted card identity")
    return batch_size


def _masked_cross_entropy(
    logits: Tensor,
    targets: Tensor,
    valid: Tensor,
    trusted: Tensor,
    *,
    component: str,
    sample_weights: Tensor | None = None,
) -> tuple[Tensor, Tensor]:
    rows = torch.nonzero(trusted, as_tuple=False).flatten()
    count = trusted.sum()
    if rows.numel() == 0:
        # Retain a differentiable, exactly-zero connection to this head.
        finite_logits = torch.where(torch.isfinite(logits), logits, 0.0)
        return finite_logits.sum() * 0.0, count
    selected_logits = logits.index_select(0, rows)
    selected_targets = targets.index_select(0, rows)
    selected_valid = valid.index_select(0, rows)
    if bool(((selected_targets < 0) | (selected_targets >= logits.shape[1])).any()):
        raise ValueError(f"trusted {component} target is outside its head")
    if not bool(selected_valid.any(dim=-1).all()):
        raise ValueError(f"trusted {component} row has no public legal choice")
    target_legal = selected_valid.gather(1, selected_targets.unsqueeze(1)).squeeze(1)
    if not bool(target_legal.all()):
        raise ValueError(f"trusted {component} target is not public-legal")
    per_row = nn.functional.cross_entropy(
        selected_logits.masked_fill(~selected_valid, -1e9),
        selected_targets,
        reduction="none",
    )
    if sample_weights is None:
        loss = per_row.mean()
    else:
        if sample_weights.shape != targets.shape:
            raise ValueError("sample weights must match target shape")
        if not bool(torch.isfinite(sample_weights).all()) or bool(
            (sample_weights < 0.0).any()
        ):
            raise ValueError("sample weights must be finite and non-negative")
        selected_weights = sample_weights.index_select(0, rows).to(per_row.dtype)
        loss = (per_row * selected_weights).sum() / selected_weights.sum().clamp_min(
            torch.finfo(per_row.dtype).tiny
        )
    return loss, count


def hierarchical_masked_imitation_loss(
    decision_logits: Tensor,
    card_logits: Tensor,
    tile_logits: Tensor,
    public_masks: HierarchicalPublicMasks,
    labels: HierarchicalImitationLabels,
    *,
    config: HierarchicalImitationConfig | None = None,
    decision_sample_weights: Tensor | None = None,
    card_sample_weights: Tensor | None = None,
    tile_sample_weights: Tensor | None = None,
) -> HierarchicalImitationLoss:
    """Compute independent trusted-label means for timing, card, and tile.

    The three denominators are deliberately independent. Missing card or tile
    labels cannot dilute the decision objective, and a batch with no trusted
    labels for one component contributes a finite differentiable zero.
    """

    config = config or HierarchicalImitationConfig()
    config.validate()
    batch_size = _validate_labels(labels, public_masks)
    if decision_logits.shape != (batch_size, NUM_DECISIONS):
        raise ValueError("decision logits must have shape [batch, 3]")
    if card_logits.shape != (batch_size, NUM_HAND_SLOTS):
        raise ValueError("card logits must have shape [batch, 4]")
    if tile_logits.shape != (batch_size, NUM_HAND_SLOTS, NUM_TILES):
        raise ValueError("tile logits must have shape [batch, 4, 576]")

    decision_loss, decision_count = _masked_cross_entropy(
        decision_logits,
        labels.decision_target,
        public_masks.decision,
        labels.decision_trusted,
        component="decision",
        sample_weights=decision_sample_weights,
    )
    card_loss, card_count = _masked_cross_entropy(
        card_logits,
        labels.card_target,
        public_masks.card,
        labels.card_trusted,
        component="card",
        sample_weights=card_sample_weights,
    )

    tile_rows = torch.nonzero(labels.tile_trusted, as_tuple=False).flatten()
    if tile_rows.numel() == 0:
        finite_tiles = torch.where(torch.isfinite(tile_logits), tile_logits, 0.0)
        tile_loss = finite_tiles.sum() * 0.0
        tile_count = labels.tile_trusted.sum()
    else:
        target_cards = labels.card_target.index_select(0, tile_rows)
        row_indices = torch.arange(tile_rows.numel(), device=tile_logits.device)
        selected_logits = tile_logits.index_select(0, tile_rows)[
            row_indices, target_cards
        ]
        selected_valid = public_masks.tile.index_select(0, tile_rows)[
            row_indices, target_cards
        ]
        tile_loss, tile_count = _masked_cross_entropy(
            selected_logits,
            labels.tile_target.index_select(0, tile_rows),
            selected_valid,
            torch.ones(tile_rows.numel(), dtype=torch.bool, device=tile_rows.device),
            component="tile",
            sample_weights=(
                None
                if tile_sample_weights is None
                else tile_sample_weights.index_select(0, tile_rows)
            ),
        )

    total = (
        config.decision_loss_coef * decision_loss
        + config.card_loss_coef * card_loss
        + config.tile_loss_coef * tile_loss
    )
    return HierarchicalImitationLoss(
        total=total,
        decision=decision_loss,
        card=card_loss,
        tile=tile_loss,
        decision_count=decision_count,
        card_count=card_count,
        tile_count=tile_count,
    )


def _masked_correct_counts(
    logits: Tensor,
    targets: Tensor,
    valid: Tensor,
    trusted: Tensor,
) -> tuple[Tensor, Tensor]:
    rows = torch.nonzero(trusted, as_tuple=False).flatten()
    if rows.numel() == 0:
        zero = torch.zeros((), dtype=torch.long, device=logits.device)
        return zero, zero
    predictions = logits.index_select(0, rows).masked_fill(
        ~valid.index_select(0, rows), -1e9
    ).argmax(dim=-1)
    expected = targets.index_select(0, rows)
    return (predictions == expected).sum(), trusted.sum()


@torch.no_grad()
def hierarchical_imitation_metric_sums(
    decision_logits: Tensor,
    card_logits: Tensor,
    tile_logits: Tensor,
    public_masks: HierarchicalPublicMasks,
    labels: HierarchicalImitationLabels,
) -> dict[str, Tensor]:
    """Return additive metrics with explicit trusted-label denominators."""

    batch_size = _validate_labels(labels, public_masks)
    if decision_logits.shape != (batch_size, NUM_DECISIONS):
        raise ValueError("decision logits must have shape [batch, 3]")
    if card_logits.shape != (batch_size, NUM_HAND_SLOTS):
        raise ValueError("card logits must have shape [batch, 4]")
    if tile_logits.shape != (batch_size, NUM_HAND_SLOTS, NUM_TILES):
        raise ValueError("tile logits must have shape [batch, 4, 576]")

    result: dict[str, Tensor] = {}
    correct, count = _masked_correct_counts(
        decision_logits,
        labels.decision_target,
        public_masks.decision,
        labels.decision_trusted,
    )
    result["decision_correct"] = correct
    result["decision_count"] = count
    for target_value, name in (
        (PLAY_DECISION, "play"),
        (WAIT_DECISION, "wait"),
        (ABILITY_DECISION, "ability"),
    ):
        trusted = labels.decision_trusted & (
            labels.decision_target == target_value
        )
        correct, count = _masked_correct_counts(
            decision_logits,
            labels.decision_target,
            public_masks.decision,
            trusted,
        )
        result[f"{name}_correct"] = correct
        result[f"{name}_count"] = count

    correct, count = _masked_correct_counts(
        card_logits,
        labels.card_target,
        public_masks.card,
        labels.card_trusted,
    )
    result["card_correct"] = correct
    result["card_count"] = count

    tile_rows = torch.nonzero(labels.tile_trusted, as_tuple=False).flatten()
    if tile_rows.numel() == 0:
        zero = torch.zeros((), dtype=torch.long, device=tile_logits.device)
        result["tile_exact_correct"] = zero
        result["tile_within_one_correct"] = zero
        result["tile_count"] = zero
        return result
    target_cards = labels.card_target.index_select(0, tile_rows)
    row_indices = torch.arange(tile_rows.numel(), device=tile_logits.device)
    selected_logits = tile_logits.index_select(0, tile_rows)[
        row_indices, target_cards
    ]
    selected_valid = public_masks.tile.index_select(0, tile_rows)[
        row_indices, target_cards
    ]
    predicted_tiles = selected_logits.masked_fill(~selected_valid, -1e9).argmax(
        dim=-1
    )
    expected_tiles = labels.tile_target.index_select(0, tile_rows)
    predicted_x = predicted_tiles.remainder(BOARD_WIDTH)
    predicted_y = torch.div(predicted_tiles, BOARD_WIDTH, rounding_mode="floor")
    expected_x = expected_tiles.remainder(BOARD_WIDTH)
    expected_y = torch.div(expected_tiles, BOARD_WIDTH, rounding_mode="floor")
    result["tile_exact_correct"] = (predicted_tiles == expected_tiles).sum()
    result["tile_within_one_correct"] = (
        (predicted_x - expected_x).abs().maximum((predicted_y - expected_y).abs())
        <= 1
    ).sum()
    result["tile_count"] = labels.tile_trusted.sum()
    return result
