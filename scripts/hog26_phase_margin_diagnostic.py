"""Independent phase heads for diagnosing shared-margin fitting interference."""

from types import SimpleNamespace

import torch
from torch import nn


class PhaseMarginDiagnostic(nn.Module):
    def __init__(self, input_size, hidden_size, *, residual_scale, progress_power):
        super().__init__()
        self.residual_scale = residual_scale
        self.progress_power = progress_power
        self.margin_trunk = nn.ModuleList([
            nn.Sequential(nn.Linear(input_size, hidden_size), nn.GELU(),
                          nn.Linear(hidden_size, 1)) for _ in range(3)
        ])
        for trunk in self.margin_trunk:
            nn.init.zeros_(trunk[-1].weight)
            nn.init.zeros_(trunk[-1].bias)

    def forward(self, state, *, calibrated=False):
        public = state[..., -18:]
        phase = (public[..., 0] * 3).long().clamp(0, 2)
        current = (public[..., 8:11].sum(-1) - public[..., 11:14].sum(-1)) / 3
        delta = torch.zeros_like(current)
        for index, trunk in enumerate(self.margin_trunk):
            selected = phase == index
            if selected.any():
                delta[selected] = trunk(state[selected]).squeeze(-1).tanh()
        gate = (1 - public[..., 0]).clamp(0, 1).pow(self.progress_power)
        prediction = (current + self.residual_scale * gate * delta).clamp(-1, 1)
        return SimpleNamespace(terminal_tower_margin=prediction)
