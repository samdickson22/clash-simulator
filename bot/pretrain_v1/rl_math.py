"""Terminal-reward PPO math for the exact five-tick Session distribution."""
from __future__ import annotations

import torch

from . import featurize as F


def joint_terms(gate, tiles, action, dt):
    """Joint log probability and entropy. Gate is Bx5, tiles Bx4x576, NOOP is F.NOOP."""
    if not bool(torch.all(dt == F.POLL)):
        raise ValueError('RL requires exactly five ticks between actor polls')
    lg = torch.log_softmax(gate.float(), -1)
    lt = torch.log_softmax(tiles.float(), -1)
    play = action != F.NOOP
    if bool(torch.any((action < 0) | (action > F.NOOP))):
        raise ValueError('action outside the joint action space')
    slot = torch.div(action, F.NTILE, rounding_mode='floor').clamp(max=3)
    tile = action.remainder(F.NTILE)
    rows = torch.arange(len(action), device=action.device)
    logp = torch.where(play, lg[rows, slot+1]+lt[rows, slot, tile], lg[:, 0])
    entropy = -(lg.exp()*lg).sum(-1) - (lg[:, 1:].exp()*(lt.exp()*lt).sum(-1)).sum(-1)
    return logp, entropy


def joint_kl(gate, tiles, anchor_gate, anchor_tiles):
    """KL(policy || human anchor), exactly summed over the legal joint distribution."""
    lg, la = torch.log_softmax(gate.float(), -1), torch.log_softmax(anchor_gate.float(), -1)
    lt, lat = torch.log_softmax(tiles.float(), -1), torch.log_softmax(anchor_tiles.float(), -1)
    return (lg.exp()*(lg-la)).sum(-1) + (lg[:, 1:].exp()*(lt.exp()*(lt-lat)).sum(-1)).sum(-1)


def gae(rewards, values, terminated, bootstrap, gamma=1., lam=.95):
    """One chronological environment chunk. Reset at real terminal boundaries; bootstrap an unfinished tail."""
    if rewards.ndim != 1 or values.shape != rewards.shape or terminated.shape != rewards.shape:
        raise ValueError('one chronological reward/value/terminal vector is required')
    advantages = torch.zeros_like(values)
    following_value = torch.as_tensor(bootstrap, device=values.device, dtype=values.dtype)
    following_advantage = torch.zeros_like(following_value)
    for i in range(len(values)-1, -1, -1):
        continuation = (~terminated[i].bool()).to(values.dtype)
        delta = rewards[i] + gamma*following_value*continuation-values[i]
        following_advantage = delta + gamma*lam*continuation*following_advantage
        advantages[i] = following_advantage
        following_value = values[i]
    return advantages, advantages+values


def normalize_advantages(advantages, actor):
    """Normalize once over the complete update's eligible policy rows, before minibatching."""
    selected = advantages[actor.bool()]
    out = torch.zeros_like(advantages)
    if len(selected):
        out[actor.bool()] = (selected-selected.mean())/selected.std(unbiased=False).clamp(min=1e-8)
    return out


def ppo_sums(logp, old_logp, advantages, value, returns, entropy, kl, actor, clip=.2):
    """Unreduced sums for exact accumulation. Divide by whole-minibatch counts, not microbatch counts."""
    eligible = actor.bool()
    ratio = (logp-old_logp).exp()
    surrogate = torch.minimum(ratio*advantages, ratio.clamp(1-clip, 1+clip)*advantages)
    return dict(policy=-surrogate[eligible].sum(), value=(value-returns).square().sum(),
                entropy=entropy[eligible].sum(), kl=kl[eligible].sum(),
                actor_count=eligible.sum(), value_count=value.numel())
