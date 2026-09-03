"""Actor-visible complete-outcome prediction heads and calibrated metrics."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
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


def outcome_state_sha256(state: Mapping[str, Tensor]) -> str:
    """Hash an outcome head state independently of checkpoint serialization."""

    digest = hashlib.sha256()
    for name in sorted(state):
        tensor = state[name].detach().cpu().contiguous()
        descriptor = json.dumps(
            (name, str(tensor.dtype), list(tensor.shape)), separators=(",", ":")
        ).encode()
        digest.update(len(descriptor).to_bytes(8, "big"))
        digest.update(descriptor)
        payload = tensor.numpy().tobytes(order="C")
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


class ActorOutcomeHead(nn.Module):
    """Predict terminal results from frozen actor-visible policy state."""

    def __init__(
        self,
        state_size: int,
        hidden_size: int = 128,
        *,
        separate_draw_trunk: bool = False,
        structured_residual_scale: float = 0.0,
        margin_residual_scale: float = 0.0,
    ) -> None:
        super().__init__()
        if state_size < 18 or hidden_size < 1:
            raise ValueError("outcome head dimensions must be positive")
        if structured_residual_scale < 0.0:
            raise ValueError("structured residual scale must be nonnegative")
        if structured_residual_scale > 0.0 and state_size == 18:
            raise ValueError("structured residual needs context before public globals")
        if margin_residual_scale < 0.0:
            raise ValueError("margin residual scale must be nonnegative")
        self.state_size = int(state_size)
        self.hidden_size = int(hidden_size)
        self.separate_draw_trunk = bool(separate_draw_trunk)
        self.structured_residual_scale = float(structured_residual_scale)
        self.margin_residual_scale = float(margin_residual_scale)
        self.register_buffer("draw_logit_calibration", torch.zeros(()))
        self.register_buffer("decisive_logit_calibration", torch.zeros(()))
        self.register_buffer("outcome_probability_prior", torch.full((3,), 1.0 / 3.0))
        self.register_buffer("probability_shrinkage", torch.ones(()))
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
            nn.Linear(hidden_size, 1) if self.structured_residual_scale > 0.0 else None
        )
        if self.structured_decisive is not None:
            nn.init.zeros_(self.structured_decisive.weight)
            nn.init.zeros_(self.structured_decisive.bias)
        self.margin_trunk = (
            nn.Sequential(
                nn.Linear(18, hidden_size),
                nn.GELU(),
                nn.Linear(hidden_size, 1),
            )
            if self.margin_residual_scale > 0.0
            else None
        )
        if self.margin_trunk is not None:
            final_margin = self.margin_trunk[-1]
            assert isinstance(final_margin, nn.Linear)
            nn.init.zeros_(final_margin.weight)
            nn.init.zeros_(final_margin.bias)
        nn.init.constant_(self.draw.bias, -2.1972245773362196)

    @torch.no_grad()
    def set_prior_calibration(
        self, empirical_prior: Tensor, target_mass: Tensor
    ) -> None:
        """Correct factorized logits from training mass to empirical game prior."""

        empirical = empirical_prior.to(
            device=self.draw_logit_calibration.device,
            dtype=self.draw_logit_calibration.dtype,
        )
        target = target_mass.to(device=empirical.device, dtype=empirical.dtype)
        if empirical.shape != (3,) or target.shape != (3,):
            raise ValueError("outcome calibration needs loss/draw/win vectors")
        if not bool(torch.isfinite(empirical).all()) or not bool(
            torch.isfinite(target).all()
        ):
            raise ValueError("outcome calibration masses must be finite")
        if bool((empirical <= 0).any()) or bool((target <= 0).any()):
            raise ValueError("outcome calibration masses must be positive")
        empirical = empirical / empirical.sum()
        target = target / target.sum()
        self.outcome_probability_prior.copy_(empirical)

        def log_odds(probability: Tensor) -> Tensor:
            return probability.log() - (1.0 - probability).log()

        self.draw_logit_calibration.copy_(log_odds(empirical[1]) - log_odds(target[1]))
        empirical_win_given_decisive = empirical[2] / (empirical[0] + empirical[2])
        target_win_given_decisive = target[2] / (target[0] + target[2])
        self.decisive_logit_calibration.copy_(
            log_odds(empirical_win_given_decisive) - log_odds(target_win_given_decisive)
        )

    @torch.no_grad()
    def set_probability_shrinkage(self, shrinkage: float) -> None:
        """Set held-out shrinkage toward the empirical complete-game prior."""

        if not math.isfinite(shrinkage) or not 0.0 <= shrinkage <= 1.0:
            raise ValueError("probability shrinkage must be in [0, 1]")
        self.probability_shrinkage.fill_(shrinkage)

    def forward(
        self, state: Tensor, *, calibrated: bool = True
    ) -> ActorOutcomePrediction:
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
        if calibrated:
            draw_logit = draw_logit + self.draw_logit_calibration
            decisive_win_logit = decisive_win_logit + self.decisive_logit_calibration
        log_draw = -F.softplus(-draw_logit)
        log_decisive = -F.softplus(draw_logit)
        log_win_given_decisive = -F.softplus(-decisive_win_logit)
        log_loss_given_decisive = -F.softplus(decisive_win_logit)
        current_margin = (
            public_globals[..., 8:11].sum(dim=-1)
            - public_globals[..., 11:14].sum(dim=-1)
        ) / 3.0
        terminal_margin = current_margin
        if self.margin_trunk is not None:
            terminal_margin = (
                current_margin
                + self.margin_residual_scale
                * self.margin_trunk(public_globals).squeeze(-1).tanh()
            ).clamp(-1.0, 1.0)
        outcome_logits = torch.stack(
            (
                log_decisive + log_loss_given_decisive,
                log_draw,
                log_decisive + log_win_given_decisive,
            ),
            dim=-1,
        )
        if calibrated:
            probabilities = (
                self.probability_shrinkage * outcome_logits.exp()
                + (1.0 - self.probability_shrinkage) * self.outcome_probability_prior
            )
            outcome_logits = probabilities.log()
        return ActorOutcomePrediction(
            outcome_logits=outcome_logits,
            terminal_tower_margin=terminal_margin,
        )


def actor_outcome_loss(
    prediction: ActorOutcomePrediction,
    final_outcomes: Tensor,
    terminal_tower_margins: Tensor,
    *,
    margin_coefficient: float = 0.25,
    sample_weights: Tensor | None = None,
    margin_sample_weights: Tensor | None = None,
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
    if margin_sample_weights is not None:
        if margin_sample_weights.shape != final_outcomes.shape:
            raise ValueError("margin sample weights do not match outcome rows")
        if not bool(torch.isfinite(margin_sample_weights).all()) or bool(
            (margin_sample_weights < 0).any()
        ):
            raise ValueError("margin sample weights must be finite and nonnegative")
        if not bool(margin_sample_weights.sum() > 0):
            raise ValueError("margin sample weights must have positive mass")
    targets = final_outcomes.to(torch.long) + 1
    outcome_rows = F.cross_entropy(prediction.outcome_logits, targets, reduction="none")
    margin_rows = F.smooth_l1_loss(
        prediction.terminal_tower_margin,
        terminal_tower_margins.to(prediction.terminal_tower_margin.dtype),
        reduction="none",
    )
    if sample_weights is None:
        outcome_nll = outcome_rows.mean()
    else:
        weights = sample_weights.to(
            device=prediction.outcome_logits.device,
            dtype=prediction.outcome_logits.dtype,
        )
        outcome_nll = (outcome_rows * weights).mean()
    effective_margin_weights = (
        margin_sample_weights if margin_sample_weights is not None else sample_weights
    )
    if effective_margin_weights is None:
        margin = margin_rows.mean()
    else:
        margin_weights = effective_margin_weights.to(
            device=prediction.outcome_logits.device,
            dtype=prediction.outcome_logits.dtype,
        )
        margin = (margin_rows * margin_weights).mean()
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
