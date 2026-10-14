"""Decode variants of the policy players, and the public scripted opponents as Players.

- v1-greedy: the v1 imitation policy decoded by argmax (gate, then card, then tile) instead of T=1 sampling.
- R3a-sampled: the R3a student with its play/wait gate SAMPLED (play with probability P(play)) instead of the
  calibrated threshold; when it plays it takes the same top-1 legal action. This is ClashAI's "sampled gate"
  arm (they measured ~-20 pp vs greedy); R3a's threshold arm is the greedy one.
- scripted-<style>: clasher.rl.public_scripted_opponent.PublicScriptedOpponent (balanced/pressure/defense) on
  the same public packet the policies read.
"""
from __future__ import annotations

import numpy as np
import torch

from .base import Decision, MatchContext, PublicView, WAIT
from .policy import POLICY_SEED_OFFSET, PolicyPlayer


def _cached_cls():
    from cached_policy import CachedPolicy
    from imitation.model.inference import single_features
    from proposals import outputs, rank_actions

    class GreedyCached(CachedPolicy):
        """v1 decoded greedily: PLAY when P(play) >= tau (tau=None: argmax gate), then argmax card and tile.
        With log_path set it also samples like stock v1 (tau ignored) and records P(play) per poll."""
        def __init__(self, base, tau=None, log_path=None):
            super().__init__(base, None, None)
            self.tau, self.log_path, self.p_log = tau, log_path, []

        @torch.inference_mode()
        def sample(self, packet, d1, generator=None):
            if self.log_path is not None:
                b = single_features(packet, d1, self.costs)
                self.p_log.append(float(self.model.log_policy(b)['gate'][0][1].exp()))
                return super().sample(packet, d1, generator)
            self.cache = None; self.fallback_calls += 1
            b = single_features(packet, d1, self.costs); self.forward_calls += 1
            lp = self.model.log_policy(b)
            if self.tau is None:
                gate = int(torch.argmax(lp['gate'][0]))
            else:
                gate = 1 if float(lp['gate'][0][1].exp()) >= self.tau else 0
            if gate != 1:
                action = 2304 if gate == 0 else 2305
            else:
                slot = int(torch.argmax(lp['card'][0]))
                tile = int(torch.argmax(lp['tile'][0, slot]))
                action = slot * 576 + tile
            count = min(8, int(b['action_mask'][0, :2304].sum()))
            joint = (lp['card'][:, :, None] + lp['tile']).flatten(1)[0]
            values, indices = torch.topk(joint, count)
            proposals = [dict(action=int(i), slot=int(i) // 576, tile=int(i) % 576, probability=float(v))
                         for i, v in zip(indices.tolist(), values.exp().tolist())]
            self.cache = (d1, packet['action_mask'].copy(), proposals)
            return action

    class SampledGateCached(CachedPolicy):
        def __init__(self, base, seed):
            super().__init__(base, threshold=0.5, check=None)
            self.rng = np.random.default_rng(seed)
            self.p_sum = 0.0; self.n = 0

        @torch.inference_mode()
        def sample(self, packet, d1, generator=None):
            self.cache = None; self.fallback_calls += 1
            b = single_features(packet, d1, self.costs); self.forward_calls += 1
            prob, ranks = outputs(self.model, b)
            order = rank_actions(ranks[0].numpy(), packet['action_mask'])
            p = float(prob[0]); self.p_sum += p; self.n += 1
            action = int(order[0]) if len(order) and self.rng.random() < p else 2304
            proposals = [dict(action=int(a), slot=int(a) // 576, tile=int(a) % 576, probability=None) for a in order[:8]]
            self.cache = (d1, packet['action_mask'].copy(), proposals)
            return action

    return GreedyCached, SampledGateCached


class VariantPolicyPlayer(PolicyPlayer):
    def __init__(self, rt, variant, tau=None, log_path=None):
        assert variant in ('v1-greedy', 'R3a-sampled', 'v1-logged')
        self.rt, self.source, self.variant = rt, variant, variant
        self.tau, self.log_path = tau, log_path
        self.name = variant if tau is None else f'{variant}-tau{tau:g}'

    def start(self, ctx: MatchContext):
        from policy import V1Policy
        self.ctx = ctx
        seed = ctx.seed + POLICY_SEED_OFFSET + ctx.seat
        Greedy, Sampled = _cached_cls()
        if self.variant == 'v1-greedy':
            self.cached = Greedy(self.rt.POLICY, tau=self.tau)
        elif self.variant == 'v1-logged':
            self.cached = Greedy(self.rt.POLICY, log_path=self.log_path)
        else:
            self.cached = Sampled(self.rt.STUDENT, seed)
        self.poller = V1Policy(self.cached, self.rt.R.builder, self.rt.R.costs, ctx.seat, list(ctx.own_order), seed)


class ScriptedPlayer:
    deadline_seconds = None

    def __init__(self, rt, style):
        self.rt, self.style, self.name = rt, style, f'scripted-{style}'

    def start(self, ctx: MatchContext):
        from clasher.rl.public_scripted_opponent import PublicScriptedOpponent
        self.bot = PublicScriptedOpponent(self.rt.R.builder, style=self.style, card_scope='c56')

    def act(self, view: PublicView) -> Decision:
        action = int(self.bot.select_action(view.reserved.packet))
        return Decision(action if action < WAIT else WAIT)

    def close(self):
        pass


def close_logged(player):
    """Append a v1-logged player's P(play) samples to its log file."""
    if getattr(player, 'variant', None) == 'v1-logged' and player.log_path:
        import json
        with open(player.log_path, 'a') as fh:
            fh.write(json.dumps(player.cached.p_log) + '\n')
