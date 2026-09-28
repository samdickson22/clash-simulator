from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import torch
from torch import Tensor, nn

from clasher.card_aliases import resolve_card_name
from clasher.spells import SPELL_REGISTRY, RollingProjectileSpell

from .common import BOARD_WIDTH, NUM_HAND_SLOTS, NUM_TILES
from .structured_obs import StructuredObservationBuilder

PLACEMENT_ACTIONS = NUM_HAND_SLOTS * NUM_TILES
NO_OP_ACTION = PLACEMENT_ACTIONS
ABILITY_ACTION = PLACEMENT_ACTIONS + 1

STRICT_KIND = 0
TROOP_KIND = 1
BUILDING_KIND = 2
SPELL_KIND = 3
KIND_NAMES = {
    TROOP_KIND: "troop",
    BUILDING_KIND: "building",
    SPELL_KIND: "spell",
}


@dataclass(frozen=True)
class SpatialImitationConfig:
    """Conservative, mechanics-derived spatial label smoothing.

    The exact expert tile always retains most of the target mass. Buildings
    remain exact because a one-tile shift changes footprint and pathing. Troop
    tolerance is limited to immediate neighboring tiles and may expand only to
    the card's serialized formation extent. Area-spell tolerance is a fraction
    of the simulator effect radius; rolling line spells remain exact.
    """

    type_loss_coef: float = 1.0
    location_loss_coef: float = 1.0
    troop_neighbor_mass: float = 0.15
    troop_radius_tiles: float = 1.0
    max_troop_radius_tiles: float = 1.5
    spell_neighbor_mass: float = 0.25
    spell_radius_fraction: float = 0.5
    max_spell_radius_tiles: float = 2.0

    def validate(self) -> None:
        if self.type_loss_coef < 0.0 or self.location_loss_coef < 0.0:
            raise ValueError("loss coefficients cannot be negative")
        for name, value in (
            ("troop_neighbor_mass", self.troop_neighbor_mass),
            ("spell_neighbor_mass", self.spell_neighbor_mass),
        ):
            if not 0.0 <= value < 1.0:
                raise ValueError(f"{name} must be in [0, 1)")
        for name, value in (
            ("troop_radius_tiles", self.troop_radius_tiles),
            ("max_troop_radius_tiles", self.max_troop_radius_tiles),
            ("spell_radius_fraction", self.spell_radius_fraction),
            ("max_spell_radius_tiles", self.max_spell_radius_tiles),
        ):
            if value < 0.0:
                raise ValueError(f"{name} cannot be negative")
        if self.max_troop_radius_tiles < self.troop_radius_tiles:
            raise ValueError(
                "max_troop_radius_tiles cannot be smaller than troop_radius_tiles"
            )


@dataclass(frozen=True)
class TokenSpatialSemantics:
    """Per-token smoothing parameters derived from immutable public mechanics."""

    radius_tiles: Tensor
    neighbor_mass: Tensor
    kind: Tensor

    def __post_init__(self) -> None:
        if not (
            self.radius_tiles.ndim
            == self.neighbor_mass.ndim
            == self.kind.ndim
            == 1
        ):
            raise ValueError("token spatial semantics must be one-dimensional")
        if not (
            self.radius_tiles.shape
            == self.neighbor_mass.shape
            == self.kind.shape
        ):
            raise ValueError("token spatial semantic shapes must match")


@dataclass(frozen=True)
class ImitationLoss:
    total: Tensor
    exact_joint: Tensor
    action_type: Tensor
    location: Tensor


def _logic_or_tile_radius(value: float | str | None) -> float:
    radius = max(0.0, float(value or 0.0))
    # Older static spell declarations retain native 1/1000-tile units, while
    # dynamically loaded mechanics are already expressed in tiles.
    return radius / 1000.0 if radius > 32.0 else radius


def build_token_spatial_semantics(
    builder: StructuredObservationBuilder,
    *,
    device: torch.device | str,
    config: SpatialImitationConfig | None = None,
) -> TokenSpatialSemantics:
    """Build card-agnostic tolerance tensors from serialized mechanics."""

    config = config or SpatialImitationConfig()
    config.validate()
    count = len(builder.token_names)
    radius_tiles = torch.zeros(count, dtype=torch.float32, device=device)
    neighbor_mass = torch.zeros(count, dtype=torch.float32, device=device)
    kind = torch.zeros(count, dtype=torch.long, device=device)
    definitions = builder.loader.load_card_definitions()

    for token_id, token_name in enumerate(builder.token_names):
        if token_name.startswith("<"):
            continue
        card_name = builder.card_name_for_token_id(token_id)
        if card_name is None:
            continue
        stats = builder.loader.get_card(card_name)
        if stats is None:
            continue
        card_kind = str(getattr(stats, "card_type", "") or "").lower()
        if card_kind == "building":
            kind[token_id] = BUILDING_KIND
            continue
        if card_kind == "spell":
            kind[token_id] = SPELL_KIND
            resolved = resolve_card_name(card_name, definitions)
            spell = SPELL_REGISTRY.get(resolved)
            if spell is None or isinstance(spell, RollingProjectileSpell):
                continue
            effect_radius = _logic_or_tile_radius(getattr(spell, "radius", 0.0))
            support = min(
                config.max_spell_radius_tiles,
                effect_radius * config.spell_radius_fraction,
            )
            # Tile centers are one unit apart, so a smaller support is exact.
            if support >= 1.0:
                radius_tiles[token_id] = support
                neighbor_mass[token_id] = config.spell_neighbor_mass
            continue

        # Champions deploy through a hand slot and therefore share troop
        # placement semantics. Unknown mechanics remain strict.
        if card_kind not in {"troop", "champion"}:
            continue
        kind[token_id] = TROOP_KIND
        formation_extent = max(
            _logic_or_tile_radius(getattr(stats, "summon_radius", 0.0)),
            0.5 * _logic_or_tile_radius(getattr(stats, "summon_width", 0.0)),
        )
        support = min(
            config.max_troop_radius_tiles,
            max(config.troop_radius_tiles, formation_extent),
        )
        if support >= 1.0:
            radius_tiles[token_id] = support
            neighbor_mass[token_id] = config.troop_neighbor_mass

    return TokenSpatialSemantics(
        radius_tiles=radius_tiles,
        neighbor_mass=neighbor_mass,
        kind=kind,
    )


def _validate_batch(
    joint_logits: Tensor,
    targets: Tensor,
    action_masks: Tensor,
    hand_ids: Tensor,
    semantics: TokenSpatialSemantics,
) -> None:
    if joint_logits.ndim != 2 or joint_logits.shape[1] != ABILITY_ACTION + 1:
        raise ValueError("joint logits must have shape [batch, 2306]")
    if action_masks.shape != joint_logits.shape:
        raise ValueError("action mask shape must match joint logits")
    if targets.shape != joint_logits.shape[:1]:
        raise ValueError("targets must have shape [batch]")
    if hand_ids.ndim != 2 or hand_ids.shape[0] != targets.shape[0]:
        raise ValueError("hand IDs must have shape [batch, visible slots]")
    if hand_ids.shape[1] < NUM_HAND_SLOTS:
        raise ValueError("hand IDs must contain all playable hand slots")
    if semantics.radius_tiles.device != joint_logits.device:
        raise ValueError("token spatial semantics must be on the logits device")
    if bool(((targets < 0) | (targets > ABILITY_ACTION)).any()):
        raise ValueError("target action is outside the policy action space")
    target_legal = action_masks.gather(1, targets.unsqueeze(1)).squeeze(1)
    if not bool(target_legal.all()):
        raise ValueError("every imitation target must be legal")


def _action_types(actions: Tensor) -> Tensor:
    placement = actions < PLACEMENT_ACTIONS
    return torch.where(
        placement,
        actions // NUM_TILES,
        NUM_HAND_SLOTS + (actions == ABILITY_ACTION).long(),
    )


def _joint_and_type_log_probs(
    joint_logits: Tensor,
    action_masks: Tensor,
) -> tuple[Tensor, Tensor]:
    joint_log_probs = nn.functional.log_softmax(
        joint_logits.masked_fill(~action_masks, -torch.inf),
        dim=-1,
    )
    placement = joint_log_probs[:, :PLACEMENT_ACTIONS].reshape(
        -1, NUM_HAND_SLOTS, NUM_TILES
    )
    placement_mask = action_masks[:, :PLACEMENT_ACTIONS].reshape(
        -1, NUM_HAND_SLOTS, NUM_TILES
    )
    valid_slots = placement_mask.any(dim=-1)
    safe_placement = placement.masked_fill(
        ~valid_slots.unsqueeze(-1),
        0.0,
    )
    slot_log_probs = torch.logsumexp(safe_placement, dim=-1).masked_fill(
        ~valid_slots,
        -torch.inf,
    )
    type_log_probs = torch.cat(
        [slot_log_probs, joint_log_probs[:, PLACEMENT_ACTIONS:]],
        dim=-1,
    )
    return joint_log_probs, type_log_probs


def factorized_spatial_imitation_loss(
    joint_logits: Tensor,
    targets: Tensor,
    action_masks: Tensor,
    hand_ids: Tensor,
    semantics: TokenSpatialSemantics,
    *,
    config: SpatialImitationConfig | None = None,
    reduction: Literal["none", "mean", "sum"] = "mean",
) -> ImitationLoss:
    """Return exact-type plus mechanics-aware conditional-location loss.

    With zero neighbor mass and unit coefficients this is algebraically equal
    to exact 2,306-action cross entropy. Only the supervised target changes;
    the exact joint distribution used by inference and PPO is untouched.
    """

    config = config or SpatialImitationConfig()
    config.validate()
    _validate_batch(joint_logits, targets, action_masks, hand_ids, semantics)
    joint_log_probs, type_log_probs = _joint_and_type_log_probs(
        joint_logits, action_masks
    )
    target_types = _action_types(targets)
    type_nll = -type_log_probs.gather(1, target_types.unsqueeze(1)).squeeze(1)
    exact_nll = -joint_log_probs.gather(1, targets.unsqueeze(1)).squeeze(1)
    location_nll = torch.zeros_like(type_nll)

    placement_rows = torch.nonzero(
        targets < PLACEMENT_ACTIONS,
        as_tuple=False,
    ).flatten()
    if placement_rows.numel() > 0:
        placement_targets = targets.index_select(0, placement_rows)
        target_slots = placement_targets // NUM_TILES
        target_tiles = placement_targets % NUM_TILES
        row_logits = joint_log_probs.index_select(0, placement_rows)[
            :, :PLACEMENT_ACTIONS
        ].reshape(-1, NUM_HAND_SLOTS, NUM_TILES)
        row_masks = action_masks.index_select(0, placement_rows)[
            :, :PLACEMENT_ACTIONS
        ].reshape(-1, NUM_HAND_SLOTS, NUM_TILES)
        row_index = torch.arange(placement_rows.numel(), device=joint_logits.device)
        slot_joint_log_probs = row_logits[row_index, target_slots]
        slot_legal = row_masks[row_index, target_slots]
        conditional_log_probs = slot_joint_log_probs - torch.logsumexp(
            slot_joint_log_probs, dim=-1, keepdim=True
        )
        exact_location_nll = -conditional_log_probs.gather(
            1, target_tiles.unsqueeze(1)
        ).squeeze(1)

        target_hand_ids = hand_ids.index_select(0, placement_rows)[
            row_index, target_slots
        ]
        radii = semantics.radius_tiles[target_hand_ids]
        neighbor_mass = semantics.neighbor_mass[target_hand_ids]
        tile_ids = torch.arange(NUM_TILES, device=joint_logits.device)
        tile_x = tile_ids.remainder(BOARD_WIDTH).to(joint_logits.dtype)
        tile_y = torch.div(
            tile_ids,
            BOARD_WIDTH,
            rounding_mode="floor",
        ).to(joint_logits.dtype)
        target_x = target_tiles.remainder(BOARD_WIDTH).to(joint_logits.dtype)
        target_y = torch.div(
            target_tiles,
            BOARD_WIDTH,
            rounding_mode="floor",
        ).to(joint_logits.dtype)
        distance_sq = (tile_x.unsqueeze(0) - target_x.unsqueeze(1)).square()
        distance_sq += (tile_y.unsqueeze(0) - target_y.unsqueeze(1)).square()
        neighbor_mask = (
            slot_legal
            & (distance_sq > 0.0)
            & (distance_sq <= radii.unsqueeze(1).square())
        )
        sigma = torch.clamp(0.5 * radii, min=0.5)
        neighbor_weights = torch.exp(
            -distance_sq / (2.0 * sigma.unsqueeze(1).square())
        ) * neighbor_mask.to(joint_logits.dtype)
        weight_sum = neighbor_weights.sum(dim=-1)
        has_neighbors = weight_sum > 0.0
        effective_mass = neighbor_mass * has_neighbors.to(neighbor_mass.dtype)
        normalized_weight = weight_sum.clamp_min(1e-12).unsqueeze(1)
        neighbor_distribution = neighbor_weights / normalized_weight
        neighbor_nll = -(
            neighbor_distribution
            * conditional_log_probs.masked_fill(~neighbor_mask, 0.0)
        ).sum(dim=-1)
        placement_location_nll = (
            (1.0 - effective_mass) * exact_location_nll
            + effective_mass * neighbor_nll
        )
        location_nll[placement_rows] = placement_location_nll

    total = (
        config.type_loss_coef * type_nll
        + config.location_loss_coef * location_nll
    )

    def reduce(values: Tensor) -> Tensor:
        if reduction == "none":
            return values
        if reduction == "sum":
            return values.sum()
        if reduction == "mean":
            return values.mean()
        raise ValueError(f"unsupported reduction {reduction!r}")

    return ImitationLoss(
        total=reduce(total),
        exact_joint=reduce(exact_nll),
        action_type=reduce(type_nll),
        location=reduce(location_nll),
    )


@torch.no_grad()
def imitation_metric_sums(
    joint_logits: Tensor,
    targets: Tensor,
    action_masks: Tensor,
    hand_ids: Tensor,
    semantics: TokenSpatialSemantics,
) -> dict[str, Tensor]:
    """Return additive exact, hierarchical, spatial, and mechanic metrics."""

    _validate_batch(joint_logits, targets, action_masks, hand_ids, semantics)
    joint_log_probs, type_log_probs = _joint_and_type_log_probs(
        joint_logits, action_masks
    )
    predicted_types = type_log_probs.argmax(dim=-1)
    placement_log_probs = joint_log_probs[:, :PLACEMENT_ACTIONS].reshape(
        -1, NUM_HAND_SLOTS, NUM_TILES
    )
    best_tiles = placement_log_probs.argmax(dim=-1)
    selected_slots = predicted_types.clamp(max=NUM_HAND_SLOTS - 1)
    selected_tiles = best_tiles.gather(
        1, selected_slots.unsqueeze(1)
    ).squeeze(1)
    placement_predictions = predicted_types * NUM_TILES + selected_tiles
    special_predictions = PLACEMENT_ACTIONS + (
        predicted_types - NUM_HAND_SLOTS
    )
    predictions = torch.where(
        predicted_types < NUM_HAND_SLOTS,
        placement_predictions,
        special_predictions,
    )
    target_types = _action_types(targets)
    exact = predictions == targets
    type_correct = predicted_types == target_types
    target_placement = targets < PLACEMENT_ACTIONS
    predicted_placement = predictions < PLACEMENT_ACTIONS
    correct_slot = target_placement & predicted_placement & type_correct
    safe_target_tiles = (targets % NUM_TILES).masked_fill(~target_placement, 0)
    safe_predicted_tiles = (predictions % NUM_TILES).masked_fill(
        ~predicted_placement, 0
    )
    dx = (
        safe_target_tiles.remainder(BOARD_WIDTH)
        - safe_predicted_tiles.remainder(BOARD_WIDTH)
    ).to(joint_logits.dtype)
    dy = (
        torch.div(safe_target_tiles, BOARD_WIDTH, rounding_mode="floor")
        - torch.div(safe_predicted_tiles, BOARD_WIDTH, rounding_mode="floor")
    ).to(joint_logits.dtype)
    distance = torch.sqrt(dx.square() + dy.square())

    safe_slots = (targets // NUM_TILES).clamp(0, NUM_HAND_SLOTS - 1)
    row_index = torch.arange(targets.shape[0], device=targets.device)
    target_hand_ids = hand_ids[row_index, safe_slots]
    tolerance = semantics.radius_tiles[target_hand_ids]
    target_kind = semantics.kind[target_hand_ids]
    tolerant = exact | (correct_slot & (distance <= tolerance))

    one = torch.ones_like(targets, dtype=torch.long)
    sums: dict[str, Tensor] = {
        "samples": one.sum(),
        "exact_correct": exact.long().sum(),
        "type_correct": type_correct.long().sum(),
        "placement_samples": target_placement.long().sum(),
        "correct_slot": correct_slot.long().sum(),
        "within_1_tile": (correct_slot & (distance <= 1.0)).long().sum(),
        "within_2_tiles": (correct_slot & (distance <= 2.0)).long().sum(),
        "mechanic_tolerant_correct": tolerant.long().sum(),
        "correct_slot_distance_sum": distance.masked_fill(~correct_slot, 0.0).sum(),
        "correct_slot_distance_count": correct_slot.long().sum(),
    }
    for kind_id, kind_name in KIND_NAMES.items():
        selected = target_placement & (target_kind == kind_id)
        sums[f"{kind_name}_samples"] = selected.long().sum()
        sums[f"{kind_name}_exact_correct"] = (selected & exact).long().sum()
        sums[f"{kind_name}_type_correct"] = (selected & type_correct).long().sum()
        sums[f"{kind_name}_tolerant_correct"] = (selected & tolerant).long().sum()
    return sums
