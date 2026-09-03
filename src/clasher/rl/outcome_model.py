"""Actor-visible complete-outcome prediction heads and calibrated metrics."""

from __future__ import annotations

from dataclasses import dataclass

import torch
from torch import Tensor, nn
from torch.nn import functional as F


@dataclass(frozen=True)
class ActorOutcomePrediction:
    outcome_logits: Tensor
    terminal_tower_margin: Tensor


@dataclass(frozen=True)
class ActorOutcomeLoss:
    total: Tensor
    outcome_nll: Tensor
    tower_margin_huber: Tensor


class ActorOutcomeHead(nn.Module):
    """Predict terminal results from frozen actor-visible policy state."""

    def __init__(
        self,
        state_size: int,
        hidden_size: int = 128,
        *,
        separate_draw_trunk: bool = False,
        structured_residual_scale: float = 0.0,
    ) -> None:
        super().__init__()
        if state_size < 18 or hidden_size < 1:
            raise ValueError("outcome head dimensions must be positive")
        if structured_residual_scale < 0.0:
            raise ValueError("structured residual scale must be nonnegative")
        if structured_residual_scale > 0.0 and state_size == 18:
            raise ValueError("structured residual needs context before public globals")
        self.state_size = int(state_size)
        self.hidden_size = int(hidden_size)
        self.separate_draw_trunk = bool(separate_draw_trunk)
        self.structured_residual_scale = float(structured_residual_scale)
        trunk_size = 18 if self.structured_residual_scale > 0.0 else state_size
        self.trunk = nn.Sequential(
            nn.LayerNorm(trunk_size),
            nn.Linear(trunk_size, hidden_size),
            nn.GELU(),
            nn.Linear(hidden_size, hidden_size),
            nn.GELU(),
        )
        self.draw = nn.Linear(hidden_size, 1)
        self.decisive_win = nn.Linear(hidden_size, 1)
        self.draw_trunk = (
            nn.Sequential(
                nn.LayerNorm(18),
                nn.Linear(18, hidden_size),
                nn.GELU(),
                nn.Linear(hidden_size, hidden_size),
                nn.GELU(),
            )
            if self.separate_draw_trunk
            else None
        )
        self.structured_trunk = (
            nn.Sequential(
                nn.Linear(state_size - 18, hidden_size),
                nn.GELU(),
                nn.Linear(hidden_size, hidden_size),
                nn.GELU(),
            )
            if self.structured_residual_scale > 0.0
            else None
        )
        self.structured_decisive = (
            nn.Linear(hidden_size, 1)
            if self.structured_residual_scale > 0.0
            else None
        )
        if self.structured_decisive is not None:
            nn.init.zeros_(self.structured_decisive.weight)
            nn.init.zeros_(self.structured_decisive.bias)
        nn.init.constant_(self.draw.bias, -2.1972245773362196)

    def forward(self, state: Tensor) -> ActorOutcomePrediction:
        if state.shape[-1] != self.state_size:
            raise ValueError("actor outcome state width changed")
        public_globals = state[..., -18:]
        hidden = self.trunk(
            public_globals if self.structured_trunk is not None else state
        )
        draw_hidden = (
            hidden if self.draw_trunk is None else self.draw_trunk(public_globals)
        )
        draw_logit = self.draw(draw_hidden).squeeze(-1)
        decisive_win_logit = self.decisive_win(hidden).squeeze(-1)
        if self.structured_trunk is not None:
            assert self.structured_decisive is not None
            structured = self.structured_trunk(state[..., :-18])
            decisive_win_logit = decisive_win_logit + (
                self.structured_residual_scale
                * self.structured_decisive(structured).squeeze(-1).tanh()
            )
        log_draw = -F.softplus(-draw_logit)
        log_decisive = -F.softplus(draw_logit)
        log_win_given_decisive = -F.softplus(-decisive_win_logit)
        log_loss_given_decisive = -F.softplus(decisive_win_logit)
        return ActorOutcomePrediction(
            outcome_logits=torch.stack(
                (
                    log_decisive + log_loss_given_decisive,
                    log_draw,
                    log_decisive + log_win_given_decisive,
                ),
                dim=-1,
            ),
            terminal_tower_margin=(
                state[..., -10:-7].sum(dim=-1) - state[..., -7:-4].sum(dim=-1)
            )
            / 3.0,
        )


def actor_outcome_loss(
    prediction: ActorOutcomePrediction,
    final_outcomes: Tensor,
    terminal_tower_margins: Tensor,
    *,
    margin_coefficient: float = 0.25,
    sample_weights: Tensor | None = None,
) -> ActorOutcomeLoss:
    """Train undiscounted W/D/L first, with public terminal margin auxiliary."""

    if prediction.outcome_logits.shape[:-1] != final_outcomes.shape:
        raise ValueError("outcome labels do not match prediction rows")
    if prediction.outcome_logits.shape[-1] != 3:
        raise ValueError("outcome logits must contain loss/draw/win")
    if terminal_tower_margins.shape != final_outcomes.shape:
        raise ValueError("tower-margin labels do not match outcome rows")
    if not 0.0 <= margin_coefficient <= 1.0:
        raise ValueError("margin coefficient must be in [0, 1]")
    if not bool(
        torch.isin(
            final_outcomes, torch.tensor([-1, 0, 1], device=final_outcomes.device)
        ).all()
    ):
        raise ValueError("outcome labels must be -1, 0, or 1")
    if not bool(torch.isfinite(terminal_tower_margins).all()):
        raise ValueError("tower-margin labels must be finite")
    if sample_weights is not None:
        if sample_weights.shape != final_outcomes.shape:
            raise ValueError("sample weights do not match outcome rows")
        if not bool(torch.isfinite(sample_weights).all()) or bool(
            (sample_weights < 0).any()
        ):
            raise ValueError("sample weights must be finite and nonnegative")
        if not bool(sample_weights.sum() > 0):
            raise ValueError("sample weights must have positive mass")
    targets = final_outcomes.to(torch.long) + 1
    outcome_rows = F.cross_entropy(
        prediction.outcome_logits, targets, reduction="none"
    )
    margin_rows = F.smooth_l1_loss(
        prediction.terminal_tower_margin,
        terminal_tower_margins.to(prediction.terminal_tower_margin.dtype),
        reduction="none",
    )
    if sample_weights is None:
        outcome_nll = outcome_rows.mean()
        margin = margin_rows.mean()
    else:
        weights = sample_weights.to(
            device=prediction.outcome_logits.device,
            dtype=prediction.outcome_logits.dtype,
        )
        outcome_nll = (outcome_rows * weights).mean()
        margin = (margin_rows * weights).mean()
    return ActorOutcomeLoss(
        total=outcome_nll + margin_coefficient * margin,
        outcome_nll=outcome_nll,
        tower_margin_huber=margin,
    )


__all__ = [
    "ActorOutcomeHead",
    "ActorOutcomeLoss",
    "ActorOutcomePrediction",
    "actor_outcome_loss",
]
