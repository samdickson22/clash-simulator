"""Causal actor-visible temporal prediction of terminal tower margin."""

from __future__ import annotations

import math

import torch
from torch import Tensor, nn


class ActorTemporalMarginHead(nn.Module):
    """Predict remaining tower-margin change from model-owned public memory."""

    def __init__(
        self,
        input_size: int,
        *,
        projection_size: int = 32,
        memory_size: int = 16,
        residual_scale: float = 0.5,
        progress_power: float = 6.0,
    ) -> None:
        super().__init__()
        if input_size < 18 or min(projection_size, memory_size) < 1:
            raise ValueError("temporal margin dimensions must be positive")
        if not math.isfinite(residual_scale) or residual_scale < 0.0:
            raise ValueError("temporal margin residual scale must be nonnegative")
        if not math.isfinite(progress_power) or progress_power < 0.0:
            raise ValueError("temporal margin progress power must be nonnegative")
        self.input_size = int(input_size)
        self.projection_size = int(projection_size)
        self.memory_size = int(memory_size)
        self.residual_scale = float(residual_scale)
        self.progress_power = float(progress_power)
        self.input_projection = nn.Sequential(
            nn.LayerNorm(input_size),
            nn.Linear(input_size, projection_size),
            nn.GELU(),
        )
        self.memory = nn.GRU(projection_size, memory_size, batch_first=True)
        self.residual = nn.Linear(memory_size, 1)
        nn.init.zeros_(self.residual.weight)
        nn.init.zeros_(self.residual.bias)

    def initial_state(
        self, batch_size: int, *, device: torch.device | str
    ) -> Tensor:
        return torch.zeros(1, batch_size, self.memory_size, device=device)

    def forward(
        self, state: Tensor, memory: Tensor | None = None
    ) -> tuple[Tensor, Tensor]:
        if state.ndim != 3 or state.shape[-1] != self.input_size:
            raise ValueError("temporal margin input must be [batch, time, features]")
        if memory is None:
            memory = self.initial_state(state.shape[0], device=state.device)
        encoded = self.input_projection(state)
        remembered, next_memory = self.memory(encoded, memory)
        public_globals = state[..., -18:]
        current_margin = (
            public_globals[..., 8:11].sum(dim=-1)
            - public_globals[..., 11:14].sum(dim=-1)
        ) / 3.0
        remaining = (1.0 - public_globals[..., 0]).clamp(0.0, 1.0).pow(
            self.progress_power
        )
        prediction = (
            current_margin
            + self.residual_scale
            * remaining
            * self.residual(remembered).squeeze(-1).tanh()
        ).clamp(-1.0, 1.0)
        return prediction, next_memory
