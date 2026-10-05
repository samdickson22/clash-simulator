"""Public-only native SRP. No live BattleState enters the planner."""
from __future__ import annotations

import copy
import json
import random
from dataclasses import dataclass

import numpy as np
import torch

from clasher.rl.public_observation import project_council_public_observation
from clasher.rl.public_action_mask import PublicActionMaskInput
from clasher.rl.script_rollout_planner import ScriptRolloutPlanner
from clasher.rl.strategy_bots import StrategyBot
from clasher.rl.train_recurrent import _stack_step_inputs


@dataclass(frozen=True)
class Information:
    tick: int
    seat: int
    packet: object
    own: dict
    history: tuple


def observe(env, seat):
    """Trusted sensor adapter: own player plus explicitly public actor/history."""
    b = env.battle
    p = b.players[seat]
    packet = project_council_public_observation(env.structured_obs_builder.build_actor(b, seat))
    return Information(b.tick, seat, packet,
                       dict(elixir=p.elixir, hand=list(p.hand), cycle=list(p.cycle_queue),
                            refill=p.next_card_refill_cooldown_ms),
                       tuple(b.public_card_play_history[1-seat]))


from derived_public_state import DerivedPublicState

# Compatibility name for the original local checks.
DeckBelief = DerivedPublicState

class PublicPlanner:
    def __init__(self, resources, prior, *, k=1, seed=0, policy=False):
        self.resources = resources
        self.k = k
        self.rng = np.random.default_rng(seed)
        self.belief = DeckBelief(prior, resources.costs)
        self.policy = policy
        self.state = resources.loaded.model.initial_state(1, device=torch.device('cpu')) if policy else None
        self.previous = resources.no_op
        self.calls = self.rollouts = 0
        self.last = None
        self.derived_decisions = self.hand_determined = self.cycle_determined = 0

    @torch.no_grad()
    def policy_top(self, info, mask):
        r = self.resources
        from clasher.rl.structured_obs import StructuredObservation
        # The shared model wrapper expects critic arrays even at inference.
        # Supply zeros; never construct the privileged observation.
        observation = StructuredObservation(**vars(info.packet.observation),
            **{name: getattr(info.packet, name) for name in (
                'entity_id_confidence', 'entity_feature_confidence',
                'hand_id_confidence', 'global_feature_confidence')},
            critic_entity_ids=np.zeros(1, dtype=np.int64),
            critic_entity_features=np.zeros((1,32), dtype=np.float32),
            critic_entity_mask=np.zeros(1, dtype=bool),
            critic_card_ids=np.zeros(10, dtype=np.int64),
            critic_global_features=np.zeros(r.loaded.builder.spec.critic_global_size,dtype=np.float32))
        inputs = _stack_step_inputs([observation], mask[None],
                                    np.array([self.previous], dtype=np.int64),
                                    np.zeros(1, dtype=np.float32),
                                    np.array([info.tick == 0], dtype=np.bool_),
                                    torch.device('cpu'),
                                    public_observation_confidence=r.loaded.model.config.public_observation_confidence,
                                    builder=r.loaded.builder)
        _, _, _, self.state, output = r.loaded.model.act(inputs, self.state, deterministic=True)
        probs = output.distribution().probs.detach().numpy().reshape(-1)
        legal = np.flatnonzero(mask)
        return legal[np.argsort(-probs[legal], kind='stable')[:8]].tolist()

    def decide(self, info, decision):
        r = self.resources
        self.belief.update(info.tick, info.history)
        known = self.belief.derived()
        self.derived_decisions += 1
        self.hand_determined += int(known['hand'] is not None)
        self.cycle_determined += int(known['cycle'] is not None)
        mask = r.mask_builder.build(PublicActionMaskInput.from_confidence_observation(info.packet))
        top = self.policy_top(info, mask) if self.policy else []
        if decision % 2 or not np.any(mask[:r.no_op]):
            self.previous = r.no_op
            return r.no_op, mask
        ranked = r.bot._ranked_actions(info.packet, all_plays=True)
        script = int(r.bot.decide(info.packet).action_id)
        if not self.policy:
            pool = np.flatnonzero(mask[:r.no_op])
            top = self.rng.choice(pool, size=min(16, len(pool)), replace=False).tolist()
        candidates = []
        for a in [script, r.no_op]+[int(x.action_id) for x in ranked[:4]]+top:
            if mask[a] and a not in candidates:
                candidates.append(a)
        scores = np.zeros(len(candidates))
        root_hashes = []
        import hashlib
        for _ in range(self.k):
            other = self.belief.sample(self.rng)
            root, payload = r.root(info, other, self.rng)
            root_hashes.append(hashlib.sha256(payload.encode()).hexdigest())
            opponent = r.native.select_action(root, 1-info.seat, 'sb-balanced')
            for i, a in enumerate(candidates):
                scores[i] += r.native.rollout(root, info.seat, a, opponent,
                                              'balanced', 'sb-balanced', 160, 10, 1.0)[0]
        scores /= self.k
        best = 0
        for i in range(1, len(scores)):
            if scores[i] > scores[best]+1e-9:
                best = i
        self.previous = candidates[best]
        self.calls += 1
        self.rollouts += len(candidates)*self.k
        self.last = dict(candidates=candidates, scores=scores.tolist(), roots=root_hashes)
        return self.previous, mask


class Resources:
    """Immutable card templates and native code, initialized on a dummy env."""
    def __init__(self, ctx):
        from differential import entity, initial
        from clasher.rl.public_action_mask import PublicActionMaskBuilder
        self.loaded = ctx.loaded
        env = ctx.envs('holdout', 1)[0]
        self.bot = ctx.bot('balanced')
        base = ScriptRolloutPlanner(env, self.bot, backend='native', opponent_model=StrategyBot('balanced'))
        self.native = base._native_scripts
        self.config = base._native_config
        self.native_class = base._native_class
        self.no_op = env.action_space.no_op_action
        self.mask_builder = PublicActionMaskBuilder(ctx.loaded.builder)
        self.costs = {n: c['cost'] for n, c in self.config['cards'].items()}
        self.templates = {}
        for card_name, card in self.config['cards'].items():
            for e in card['units'][0]:
                self.templates[(e['stats']['name'] or card_name, e['class'])] = e
        tower_stats = {}
        for e in initial().entities.values():
            out = entity(e)
            self.templates[(out['stats']['name'], out['class'])] = out
            tower_stats[out['stats']['name']] = e.card_stats
        for e in self.config['death_areas'].values():
            self.templates[(e['stats']['name'], e['class'])] = e
        # Public projection names the Ice Golem death field by its buff payload.
        self.templates[('FreezeIceGolemite', 'AreaEffect')] = self.templates[('IceGolemite', 'AreaEffect')]
        for token, stats in self.bot.bodies.items():
            alias = self.loaded.builder.token_names[token]
            for (name, kind), template in list(self.templates.items()):
                if name == stats.name:
                    self.templates[(alias, kind)] = template
            projectile = getattr(stats, 'projectile_data', None) or {}
            if projectile.get('name'):
                base_kind = 'Building' if (stats.name, 'Building') in self.templates else 'Troop'
                shot = copy.deepcopy(self.templates[(stats.name, base_kind)])
                shot.update(hp=1., king=False, shield=0., spell_name='', **{'class':'Projectile'})
                shot['stats'].update(max_hp=1., speed=int(projectile.get('speed',0)),
                                     range=0., radius=0., ordinary=False)
                self.templates[(projectile['name'], 'Projectile')] = shot
        # Crown shots are represented by their serialized projectile identity.
        for name in ('Tower', 'KingTower'):
            stats = tower_stats.get(name)
            if stats is not None:
                projectile = getattr(stats, 'projectile_data', None) or {}
                if projectile.get('name'):
                    shot = copy.deepcopy(self.templates[(name, 'Building')])
                    shot.update(hp=1., king=False, shield=0., spell_name='', **{'class':'Projectile'})
                    shot['stats'].update(max_hp=1., speed=int(projectile.get('speed',0)),range=0.,radius=0.,ordinary=False)
                    self.templates[(projectile['name'], 'Projectile')] = shot

        # PyTorch lazily imports validation machinery on its first attention call.
        # Pay that one-time setup cost before live decisions. The temporary
        # recurrence is discarded; each real game starts with model.initial_state.
        packet = project_council_public_observation(self.loaded.builder.build_actor(initial(), 0))
        warm = PublicPlanner(self, dict(decks=[dict(cards=list(self.costs)[:8])]), policy=True)
        warm.policy_top(Information(0, 0, packet, {}, ()),
                        self.mask_builder.build(PublicActionMaskInput.from_confidence_observation(packet)))

    def root(self, info, opponent, rng):
        """Construct a model state solely from sensor fields and independent priors.

        Hidden combat phases are uniform within the public card hit interval;
        unknown shields start full; status/route caches reset. Projectiles aim
        along visible facing, with their public card range as remaining distance.
        These are modeling approximations, not claims of recovered hidden state.
        """
        obs = info.packet.observation
        entities = []
        for token, row in zip(obs.entity_ids[obs.entity_mask], obs.entity_features[obs.entity_mask]):
            name = self.loaded.builder.token_names[int(token)]
            kind = ['Troop','Building','Projectile','AreaEffect','Entity'][int(np.argmax(row[4:9]))]
            # Rolling spells have the public projectile kind.
            key = (name, kind)
            if key not in self.templates and (name, 'RollingProjectile') in self.templates:
                key = (name, 'RollingProjectile')
            if key not in self.templates:
                # Ordinary tower/troop shots retain their public source identity.
                choices = [v for (n, _), v in self.templates.items() if n == name]
                if not choices:
                    raise ValueError(f'no public template for {name}/{kind}')
                e = copy.deepcopy(choices[0])
                e['class'] = kind
                if kind == 'Projectile':
                    e['stats']['speed'] = e['stats']['projectile_speed']
                    e['spell_name'] = ''
            else:
                e = copy.deepcopy(self.templates[key])
            x, y = float(row[0])*18, float(row[1])*32
            fx, fy = float(row[27]), float(row[28])
            if info.seat == 1:
                x, y, fx, fy = 18-x, 32-y, -fx, -fy
            owner = info.seat if row[2] else 1-info.seat
            hp = float(row[9])*e['stats']['max_hp']
            e.update(id=len(entities)+1, owner=owner, x=x, y=y, hp=hp,
                     alive=True, target=None, deploy=0.0, stagger=0.0,
                     facing=[round(fx*1000), round(fy*1000)], age=1000,
                     birth=info.tick-1, lane=1 if x < 9 else 2)
            if row[9] < 1:
                e['shield'] = 0.
            interval = max(1, e['stats']['interval'])
            e['clock'] = dict(interval=interval, load=e['stats']['load'],
                              timeline=int(rng.integers(interval)), remaining=0, finish=0)
            e['cooldown'] = e['clock']['timeline']/1000
            if e['king']:
                base = 8 if owner == info.seat else 11
                e['active'] = bool(row[9] < 1 or obs.global_features[base] == 0 or obs.global_features[base+1] == 0)
            else:
                e['active'] = True
            if e['class'] == 'Projectile':
                distance = max(1., e['stats']['range'])
                e.update(aim=[x+fx*distance, y+fy*distance], shot_target=None)
            entities.append(e)
        players = [None, None]
        players[info.seat] = info.own
        players[1-info.seat] = opponent
        state = random.Random(int(rng.integers(2**63))).getstate()[1]
        payload = json.dumps(dict(tick=info.tick, next_id=len(entities)+1,
                                  players=players, entities=entities, pending_casts=[],
                                  sudden_death=bool(obs.global_features[4]),
                                  rng=dict(state=state[:-1], index=state[-1]),
                                  game_over=False, winner=None, config=self.config))
        return self.native_class(payload), payload
