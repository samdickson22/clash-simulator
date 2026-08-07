"""Deprecated feed-forward raster policy kept only for legacy utilities.

The active training/evaluation stack uses :mod:`clasher.rl.model`. This file
exists temporarily so old benchmark and DAgger helpers remain importable while
the RL stack is migrated.
"""

from __future__ import annotations

from typing import Optional, Tuple

import torch
from torch import Tensor, nn
from torch.distributions import Categorical


class MaskedPolicyValueNet(nn.Module):
    def __init__(
        self,
        board_channels: int,
        hud_size: int,
        num_actions: int,
        hidden_size: int = 256,
        recurrent: bool = False,
    ) -> None:
        super().__init__()
        self.num_actions = num_actions
        self.recurrent = recurrent
        self.board_encoder = nn.Sequential(
            nn.Conv2d(board_channels, 32, 3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(32, 64, 3, stride=2, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(64, 96, 3, stride=2, padding=1),
            nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool2d((1, 1)),
            nn.Flatten(),
        )
        self.hud_encoder = nn.Sequential(
            nn.Linear(hud_size, 128),
            nn.ReLU(inplace=True),
            nn.Linear(128, 128),
            nn.ReLU(inplace=True),
        )
        self.fusion = nn.Sequential(nn.Linear(224, hidden_size), nn.ReLU(inplace=True))
        if recurrent:
            self.rnn = nn.LSTM(hidden_size, hidden_size, batch_first=True)
        self.policy_head = nn.Linear(hidden_size, num_actions)
        self.value_head = nn.Linear(hidden_size, 1)

    def forward(
        self,
        board: Tensor,
        hud: Tensor,
        hidden: Optional[Tuple[Tensor, Tensor]] = None,
    ) -> tuple[Tensor, Tensor, Optional[Tuple[Tensor, Tensor]]]:
        features = self.fusion(
            torch.cat([self.board_encoder(board), self.hud_encoder(hud)], dim=-1)
        )
        if self.recurrent:
            output, hidden = self.rnn(features.unsqueeze(1), hidden)
            features = output[:, -1]
        return self.policy_head(features), self.value_head(features).squeeze(-1), hidden

    @staticmethod
    def _masked_logits(logits: Tensor, action_mask: Tensor) -> Tensor:
        return logits.masked_fill(~action_mask, -1e9)

    def distribution(self, logits: Tensor, action_mask: Tensor) -> Categorical:
        return Categorical(logits=self._masked_logits(logits, action_mask))

    @torch.no_grad()
    def act(
        self,
        board: Tensor,
        hud: Tensor,
        action_mask: Tensor,
        deterministic: bool = False,
        hidden: Optional[Tuple[Tensor, Tensor]] = None,
    ) -> tuple[Tensor, Tensor, Tensor, Optional[Tuple[Tensor, Tensor]]]:
        logits, value, next_hidden = self.forward(board, hud, hidden)
        distribution = self.distribution(logits, action_mask)
        action = (
            torch.argmax(self._masked_logits(logits, action_mask), dim=-1)
            if deterministic
            else distribution.sample()
        )
        return action, distribution.log_prob(action), value, next_hidden

