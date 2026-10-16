"""Opt-in exploration command runtime/planner; defaults delegate to frozen S6.

No live match or hidden opponent input is accepted by the forward adapter.
The native state passed here is the planner's public, sampled hypothetical root.
"""
import copy
from dataclasses import dataclass, replace
import json
import math
import numpy as np

WAIT = 2304


def ticks(value, name):
    if type(value) is not int or value < 0:
        raise ValueError(f'{name} must be a nonnegative integer')
    return value


@dataclass(frozen=True)
class Reservation:
    submitted: int
    due: int
    action: int
    card: str
    cost: float

    def native(self):
        return self.due, self.action, self.card, self.cost


class CommandQueue:
    """Exact unexecuted own reservations against the current physical HUD.

    A reserved slot stays unavailable until execution, even after the old
    ledger's freshness/refill cutoffs. Each completion removes only its debit.
    Rejected execution never refunds the physical engine: it was never debited.
    """
    def __init__(self, delay=22, max_outstanding=1):
        self.delay = ticks(delay, 'delay')
        if type(max_outstanding) is not int or max_outstanding < 1:
            raise ValueError('max_outstanding must be a positive integer')
        self.capacity = max_outstanding
        self.pending = []
        self.submitted = self.executed = self.rejected = self.blocked = self.peak = 0

    @property
    def available(self):
        return len(self.pending) < self.capacity

    def reserved_own(self, own):
        result = copy.deepcopy(own)
        for c in self.pending:
            if result['hand'][c.action // 576] != c.card:
                raise ValueError('physical HUD changed a reserved slot before completion')
            result['elixir'] -= c.cost
            result['hand'][c.action // 576] = None
            result['cycle'].append(c.card)
        if result['elixir'] < -1e-6:
            raise ValueError('reservations exceed physical elixir')
        return result

    def submit(self, info, action, costs, builder=None):
        if action == WAIT:
            return
        if type(action) is not int or not 0 <= action < WAIT:
            raise ValueError('exploration queue supports only card commands')
        if not self.available:
            raise ValueError('command capacity reached')
        own = self.reserved_own(info.own)
        card = own['hand'][action // 576]
        if card is None or card not in costs or costs[card] > own['elixir'] + 1e-6:
            raise ValueError('empty/reserved slot or unaffordable command')
        self.pending.append(Reservation(info.tick, info.tick+self.delay, action, card, costs[card]))
        self.submitted += 1
        self.peak = max(self.peak, len(self.pending))

    def ready(self, tick):
        return bool(self.pending and self.pending[0].due <= tick)

    def finish(self, accepted):
        if not self.pending:
            raise ValueError('no pending command')
        self.pending.pop(0)
        self.executed += 1
        self.rejected += not accepted

    def own_packet(self, info, builder):
        if not self.pending:
            return info
        own = self.reserved_own(info.own)
        packet = copy.deepcopy(info.packet)
        obs = packet.observation
        for i, name in enumerate(own['hand']):
            obs.hand_ids[i] = builder.token_id(name, namespace='card_action') if name else 0
        if len(obs.hand_ids) > 4:
            obs.hand_ids[4] = builder.token_id(own['cycle'][0], namespace='card_action') if own['cycle'] else 0
        present = obs.hand_ids != 0
        packet.hand_id_confidence[:] = present
        obs.hand_levels[:] = present * 11
        obs.hand_level_confidence[:] = present
        obs.global_features[5] = own['elixir']/10
        return replace(info, own=own, packet=packet)

    def diagnostics(self):
        assert self.submitted == self.executed + len(self.pending)
        return dict(submitted=self.submitted, executed=self.executed, rejected=self.rejected,
                    blocked_polls=self.blocked, pending_at_end=len(self.pending), peak_pending=self.peak)


def planner_class(base):
    class DelayFixPlanner(base):
        def __init__(self, *args, symmetric_opponent=False, opponent_delay=22,
                     opponent_interval=10, max_outstanding=1, opponent_capacity=4,
                     forward_prior=False, **kwargs):
            super().__init__(*args, **kwargs)
            self.symmetric_opponent = bool(symmetric_opponent)
            self.opponent_delay = ticks(opponent_delay, 'opponent_delay')
            self.opponent_interval = ticks(opponent_interval, 'opponent_interval')
            if not self.opponent_interval:
                raise ValueError('opponent_interval must be positive')
            CommandQueue(self.command_delay, max_outstanding)
            CommandQueue(self.opponent_delay, opponent_capacity)
            self.max_outstanding, self.opponent_capacity = max_outstanding, opponent_capacity
            self.forward_prior = bool(forward_prior)
            self.pending = ()

        @property
        def active(self):
            return self.symmetric_opponent or self.max_outstanding != 1 or self.forward_prior

        def simulate_commands(self, root, seat, action, style, horizon, *, forward=False, trace=False):
            return self.native.rollout_commands(root, seat, action,
                [c.native() for c in self.pending], style, self.command_delay,
                self.opponent_delay if self.symmetric_opponent else 0,
                self.max_outstanding, self.opponent_capacity if self.symmetric_opponent else 1,
                horizon, self.config.interval, self.opponent_interval,
                self.config.elixir_weight, not forward, forward, trace)

        def forward_state(self, root, seat):
            # No speculative new own commands before the candidate's due tick.
            _, events, sim = self.simulate_commands(root, seat, WAIT, 'balanced',
                self.command_delay, forward=True, trace=True)
            return sim, events

        def score_candidates(self, root, seat, candidates, *, trace=False, deadline=None):
            if not self.active:
                if self.pending:
                    raise ValueError('pending roots require max_outstanding flag')
                return super().score_candidates(root, seat, candidates, trace=trace, deadline=deadline)
            if deadline is not None or self.config.deadline_seconds is not None or self.config.threads != 1:
                raise ValueError('exploration requires fixed-budget single-thread scoring')
            scores = np.zeros(len(candidates)); traces = []
            for style in ('balanced', 'pressure', 'defense'):
                for i, action in enumerate(candidates):
                    value, events, _ = self.simulate_commands(root, seat, action, style,
                        self.config.horizon, trace=trace)
                    scores[i] += value/3
                    if trace:
                        traces.append((style, action, events))
            best = 0
            for i in range(1, len(candidates)):
                if scores[i] > scores[best]+1e-9:
                    best = i
            self.last = dict(candidates=candidates, scores=scores.tolist(), traces=traces)
            return candidates[best]
    return DelayFixPlanner


def hypothetical_packet(resources, sim, info):
    """Project a *hypothetical* native root onto public v5, never a live snapshot.

    The root's sampled hidden hand/order/RNG are not copied into this packet.
    Static templates resolve public entity tokens; only own HUD and public
    entity fields are projected. Unsupported templates fail closed.
    """
    from clasher.rl.contract_v5 import project_public_v5
    from clasher.kinematics import logic_speed_to_tiles_per_second
    state = json.loads(sim.snapshot())
    builder = resources.builder; seat = info.seat
    templates = {}
    for (token, kind), template in resources.templates.items():
        templates.setdefault((template['stats']['name'], template['class']), (token, kind))
    rows = []; towers = [0.]*6
    for e in state['entities']:
        if not e['alive'] or e.get('spirit', False):
            continue
        if e['owner'] != seat and (e.get('underground', False) or e.get('stealth_until', 0) > state['tick']*50):
            continue
        token, kind = templates[(e['stats']['name'], e['class'])]
        k = ('Troop', 'Building', 'Projectile', 'AreaEffect', 'Entity').index(kind)
        own = e['owner'] == seat
        x, y = e['x'], e['y']
        fx, fy = e.get('facing', (0, 0))
        if seat:
            x, y, fx, fy = 18-x, 32-y, -fx, -fy
        row = np.zeros(32, np.float32)
        row[:4] = [np.clip(x/18,0,1), np.clip(y/32,0,1), own, not own]
        row[4+k] = 1.; row[9] = np.clip(e['hp']/max(1.,e['stats']['max_hp']),0,1)
        static = builder.card_stat_features[token]
        row[23] = np.clip(math.log1p(abs(logic_speed_to_tiles_per_second(e['stats']['speed'])))/math.log1p(1000),0,1)
        row[24], row[25], row[26], row[30] = static[7], static[8], static[12], static[6]
        magnitude = max(1., math.hypot(fx,fy)); row[27:29] = fx/magnitude, fy/magnitude
        rows.append(((k, int(not own), token, round(float(row[1]),5), round(float(row[0]),5)), token, row))
        if e['stats']['name'] in ('Tower', 'KingTower'):
            j = (0 if own else 3)+(2 if e['king'] else 0 if x<9 else 1)
            towers[j] = row[9]
    ids, features, mask = builder._pack_entity_rows(rows)
    obs = copy.deepcopy(info.packet.observation)
    obs = replace(obs, entity_ids=ids, entity_features=features, entity_mask=mask,
                  entity_levels=np.where(mask,11,0), entity_level_confidence=mask.astype(np.float32))
    own = state['players'][seat]
    names = own['hand'][:4]+([own['cycle'][0]] if own['cycle'] else [None])
    obs.hand_ids[:] = [builder.token_id(n,namespace='card_action') if n else 0 for n in names]
    obs.hand_levels[:] = (obs.hand_ids>1)*11
    obs.hand_level_confidence[:] = obs.hand_ids>1
    g = obs.global_features
    t = state['tick']; g[:6] = [min(t/6000,1), max(0,1-t/6000), t>=2400,t>=4800,t>=3600,own['elixir']/10]
    g[6:8] = [sum(v==0 for v in towers[3:])/3,sum(v==0 for v in towers[:3])/3]
    g[8:14] = towers; g[14:16] = 0; g[16] = own['refill']/1000; g[17] = towers[5]>0
    obs = replace(obs, terminal=state['game_over'])
    return project_public_v5(obs, champion_button=False)


def imitation_candidates(core, resources, root, info, d1, policy, *, forward=False):
    """Gate-(b) matched-count replacement pattern, exploratory d=27 only."""
    from imitation.evaluation.d1 import model_packet
    from imitation.evaluation.candidates import replacement_candidates
    baseline, mask = core.candidates(info.packet)
    baseline = [a for a in baseline if a != 2305]
    config = core.config
    try:
        core.config = replace(config, samples=0)
        base, _ = core.candidates(info.packet)
        base = [a for a in base if a != 2305]
    finally:
        core.config = config
    proposal_packet = info.packet
    predicted = copy.deepcopy(d1)
    if forward:
        sim, events = core.forward_state(root, info.seat)
        proposal_packet = hypothetical_packet(resources, sim, info)
        # Future D1 uses only public simulated events, never sampled hidden order.
        future = []
        for kind, tick, actor, action, accepted, card in events:
            if kind != 'execute' or not accepted:
                continue
            tile = action % 576; x, y = tile%18+.5, tile//18+.5
            if actor: x,y = 18-x,32-y
            future.append(dict(tick=tick,seat=actor,kind='card',name=card,amount=0.,x=x,y=y))
        predicted = copy.deepcopy(d1)
        events_so_far = getattr(d1, '_exploration_events', [])
        predicted_row = predicted.update(info.tick+core.command_delay, events_so_far+future)
    else:
        predicted_row = d1.row(info.tick)
    from clasher.rl.public_action_mask import PublicActionMaskInput
    future_mask = core.bots['balanced'].mask_builder.build(PublicActionMaskInput.from_confidence_observation(proposal_packet))
    # A forward-legal play must also be affordable and in that same slot now.
    eligible = mask & future_mask; eligible[2305] = False; eligible[WAIT] = True
    same = proposal_packet.observation.hand_ids[:4] == info.packet.observation.hand_ids[:4]
    for slot in range(4):
        if not same[slot]: eligible[slot*576:(slot+1)*576] = False
    proposals = policy.propose(model_packet(proposal_packet, eligible), predicted_row, k=8)
    candidates = replacement_candidates(base, baseline, [p['action'] for p in proposals], mask, core.rng)
    return candidates, dict(proposals=[p['action'] for p in proposals], forward=forward,
                           candidates=len(candidates), baseline_candidates=len(baseline))
