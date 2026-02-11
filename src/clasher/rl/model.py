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
            nn.Conv2d(board_channels, 32, kernel_size=3, stride=1, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(32, 64, kernel_size=3, stride=2, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(64, 96, kernel_size=3, stride=2, padding=1),
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

        self.fusion = nn.Sequential(
            nn.Linear(96 + 128, hidden_size),
            nn.ReLU(inplace=True),
        )

        if recurrent:
            self.rnn = nn.LSTM(hidden_size, hidden_size, num_layers=1, batch_first=True)

        self.policy_head = nn.Linear(hidden_size, num_actions)
        self.value_head = nn.Linear(hidden_size, 1)

    def forward(
        self,
        board: Tensor,
        hud: Tensor,
        hidden: Optional[Tuple[Tensor, Tensor]] = None,
    ) -> tuple[Tensor, Tensor, Optional[Tuple[Tensor, Tensor]]]:
        board_features = self.board_encoder(board)
        hud_features = self.hud_encoder(hud)
        features = self.fusion(torch.cat([board_features, hud_features], dim=-1))

        if self.recurrent:
            seq_features = features.unsqueeze(1)
            seq_out, hidden = self.rnn(seq_features, hidden)
            core = seq_out[:, -1, :]
        else:
            core = features

        logits = self.policy_head(core)
        value = self.value_head(core).squeeze(-1)
        return logits, value, hidden

    @staticmethod
    def _masked_logits(logits: Tensor, action_mask: Tensor) -> Tensor:
        # Keep at least one valid action (no-op should guarantee this in env/action space).
        return logits.masked_fill(~action_mask, -1e9)

    def distribution(self, logits: Tensor, action_mask: Tensor) -> Categorical:
        masked = self._masked_logits(logits, action_mask)
        return Categorical(logits=masked)

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
        dist = self.distribution(logits, action_mask)

        if deterministic:
            action = torch.argmax(self._masked_logits(logits, action_mask), dim=-1)
        else:
            action = dist.sample()

        log_prob = dist.log_prob(action)
        return action, log_prob, value, next_hidden
