"""Stochastic T=1 gate -> card -> tile every 5 ticks; no intent-hazard rescaling."""
import torch
from .d1 import D1Tracker, model_packet
from clasher.rl.contract_v5 import ContractV5ActionMaskBuilder
from clasher.rl.public_action_mask import PublicActionMaskInput


class StandalonePlayer:
    def __init__(self, policy, builder, costs, seat, own_order, seed):
        self.policy, self.builder = policy, builder
        # Gate (c) explicitly uses T=1, including checkpoints carrying dev temperatures.
        self.policy.model.temperatures.fill_(1.)
        self.d1 = D1Tracker(builder, costs, seat, own_order)
        self.mask_builder = ContractV5ActionMaskBuilder(builder)
        self.generator = torch.Generator(device='cpu').manual_seed(seed)
        self.last_tick = None
        self.last_d1 = None

    def decide(self, tick, packet, events):
        if self.last_tick is not None and tick-self.last_tick != 5:
            raise ValueError('standalone gate must run once per 250 ms')
        self.last_tick = tick
        self.last_d1 = self.d1.update(tick, events)
        from clasher.rl.slot_permission import native_request, permission_state
        request = PublicActionMaskInput.from_confidence_observation(packet)
        allowed, self.last_permission_status = permission_state(request)
        if allowed is None:
            mask = self.mask_builder.build(request)
            self.last_feature_mask = mask
            mp = model_packet(packet, mask)
        else:
            self.last_feature_mask = self.mask_builder.build(native_request(request))
            mask = self.mask_builder.build(request)
            mp = model_packet(packet, self.last_feature_mask, eligibility_mask=mask)
        action = self.policy.sample(mp, self.last_d1, self.generator)
        if not mask[action]:
            raise AssertionError(f'illegal imitation sample {action}')
        return action, mask
