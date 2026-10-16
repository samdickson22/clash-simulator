"""Full games through the real sensor and three public-root consumers.

Run only on admitted compute using the reviewed driver. No direct object spawn,
private battle snapshot, forced HP/death, elixir refill or hidden identity enters
any root. Games use play_match's ordinary natural economy and command delays.
"""
from collections import Counter
from dataclasses import replace
import copy
import json
from pathlib import Path
import random

import numpy as np

CARDS = ['GoblinGiant', 'ThreeMusketeers', 'RamRider', 'SkeletonBalloon',
         'Clone', 'Rage', 'Fisherman', 'Zap']


def require(ok, detail):
    if not ok:
        raise AssertionError(detail)


def graph(snapshot):
    rows = snapshot['entities']
    ids = {e['id']: e for e in rows}
    require(len(ids) == len(rows), 'duplicate reconstructed IDs')
    slots = set()
    for e in rows:
        if e.get('mount') is not None:
            p = ids.get(e['mount'])
            require(e['class'] == 'Troop' and e['stats']['name'] == 'SpearGoblinGiant', 'non-rider attached')
            require(p is not None and p['class'] == 'Troop' and p['stats']['name'] == 'GoblinGiant'
                    and p['owner'] == e['owner'], 'invalid parent owner/type/closure')
            slot = (p['id'], e.get('rider_rank', 0))
            require(slot[1] in (0, 1) and slot not in slots, 'duplicate/out-of-range rider slot')
            slots.add(slot)
        elif e['class'] == 'Troop' and e['stats']['name'] == 'SpearGoblinGiant':
            raise AssertionError('observed rider lost its mount')
    return len(slots)


def reverse_rows(info):
    o = info.packet.observation
    active = np.flatnonzero(o.entity_mask)
    ids, rows = o.entity_ids.copy(), o.entity_features.copy()
    ids[active], rows[active] = ids[active[::-1]], rows[active[::-1]]
    return replace(info, packet=replace(info.packet, observation=replace(o, entity_ids=ids, entity_features=rows)))


def run(rt, output):
    import clasher_core
    from bot.players.base import Decision, WAIT
    from bot.players.ours import play_match
    from bot.levels.root import ExactLevelRoot
    from bot.live.levels import LevelRoot, Levels, scale, ratio
    from clasher.rl.public_action_mask import PublicActionMaskInput
    from derived_public_state import DerivedPublicState
    from bot.search.lopp_fast import split_snapshot
    R = rt.R
    output = Path(output)
    require(not output.exists(), 'fresh output required')
    # Level caches are configured by the driver under the fresh job only.
    exact = ExactLevelRoot(rt, {c: 11 for c in CARDS}, lambda c: 11, 11, 11, force=True)
    scaled = LevelRoot(R, Levels(own=10, opp=10, own_tower=10, opp_tower=10))
    consumers = {'plain': R.root, 'exact11': exact.root, 'live10': scaled.root}
    metrics = Counter()
    names = Counter()
    kinds = Counter()
    games = []
    examples = {}
    barrel_children = {e['stats']['name'] for e in R.config['bomb_children']['SkeletonBalloon']}
    barrel_template = next(e for e in R.templates.values() if e['class'] == 'TimedExplosive'
                           and e['stats']['name'] == 'SkeletonBalloon')

    def inspect_root(info, opponent, label, fn, permuted=False):
        rng = np.random.default_rng(700000 + info.tick + info.seat)
        root = fn(info, opponent, rng)
        head, _, tail = split_snapshot(root.snapshot())
        # Keep the complete state envelope while avoiding a large config parse.
        state = json.loads(head + '{}' + tail)
        entities = state['entities']
        active = int(info.packet.observation.entity_mask.sum())
        require(len(entities) == active, ('invented/dropped public row', label, info.tick, active, len(entities)))
        attached = graph(state)
        report = copy.deepcopy(R.public_graph_report)
        require(report['matched'] == report['riders'] == attached and not report['unsupported'], report)
        metrics[label] += 1
        metrics['attached_rows'] += attached
        if report.get('structural_fallback'):
            metrics['transport_frames'] += 1
        if len([e for e in entities if e['class'] == 'Troop' and e['stats']['name'] == 'GoblinGiant']) > 1:
            metrics['multiple_parent_frames'] += 1
        three = [e for e in entities if e['class'] == 'Troop' and
                 e['stats']['name'] == 'ThreeMusketeer_Rework_Character_1']
        metrics['max_3m_bodies'] = max(metrics['max_3m_bodies'], len(three))
        for e in entities:
            n = e['stats']['name']
            names[n] += 1
            kinds[e['class']] += 1
            if n == 'ThreeMusketeer_Rework_Character_1' and e['class'] == 'Troop':
                require(e['stats']['load'] == 700 and e.get('mount') is None, '3M public default/graph changed')
            if n != 'SpearGoblinGiant':
                require(e.get('mount') is None, ('unrelated body/carrier attached', n, e['class']))
            if e['class'] == 'TimedExplosive' and e['stats']['name'] == 'SkeletonBalloon':
                metrics['barrel_bomb_frames'] += 1
                expected = scale(copy.deepcopy(barrel_template), ratio(10)) if label == 'live10' else barrel_template
                for key in ('bomb_timer','bomb_damage','bomb_radius','freeze_carrier'):
                    require(e[key] == expected[key], ('wrong public container mechanics',label,key,e[key],expected[key]))
            if n in barrel_children and e['class'] == 'Troop':
                metrics['released_barrel_child_rows'] += 1
            if n in ('RamRider', 'RamRiderBola', 'ThreeMusketeer_Rework_Character_1', 'SkeletonBalloon'):
                examples.setdefault((n, e['class']), dict(tick=info.tick, seat=info.seat, consumer=label,
                    name=n, kind=e['class'], mounted=e.get('mount') is not None))
        if info.tick % 100 == 0 and not permuted:
            a, b = root.clone(), clasher_core.BattleState(root.snapshot())
            for _ in range(4):
                a.step(); b.step()
                require(a.snapshot() == b.snapshot(), 'native full-state continuation/reload mismatch')
            metrics['continuations'] += 1
        return state

    class Player:
        deadline_seconds = None
        name = 'public-graph-game-probe'
        def start(self, ctx):
            self.seat = ctx.seat
            self.lane_phase = ctx.seed % 2
            self.rng = random.Random(ctx.seed + ctx.seat)
            # Declared fixture deck prior, unknown order. No real opponent hand,
            # hidden IDs or private battle object is supplied to the planner.
            self.belief = DerivedPublicState({'decks': [dict(cards=CARDS, frequency=1)]}, R.costs)
            self.np_rng = np.random.default_rng(ctx.seed + ctx.seat)
            self.plays = Counter()
        def act(self, view):
            info = view.info
            if view.tick % 10 == 0 and not info.packet.observation.terminal:
                self.belief.update(info.tick, info.events)
                opponent = self.belief.sample(self.np_rng)
                for label, fn in consumers.items():
                    inspect_root(info, opponent, label, fn)
                if view.tick % 50 == 0:
                    inspect_root(reverse_rows(info), opponent, 'reversed', R.root, True)
            if not view.can_act or view.tick % 10:
                return Decision(WAIT)
            mask = R.bots['balanced'].mask_builder.build(PublicActionMaskInput.from_confidence_observation(view.reserved.packet))
            obs = view.reserved.packet.observation
            giant = R.builder.token_id('GoblinGiant', namespace='troop_body')
            gg = [row for token, row in zip(obs.entity_ids[obs.entity_mask], obs.entity_features[obs.entity_mask])
                  if int(token) == giant and row[2] and row[4]]
            choices = []
            for slot, card in enumerate(info.own['hand'][:4]):
                legal = np.flatnonzero(mask[slot*576:(slot+1)*576])
                if not len(legal) or card not in CARDS:
                    continue
                if card in ('Clone', 'Rage'):
                    if not gg:
                        continue
                    x, y = float(gg[0][0])*18, float(gg[0][1])*32
                else:
                    x, y = (5.5 if (self.plays[card]+self.seat+self.lane_phase) % 2 == 0 else 12.5), 5.5
                tile = min(map(int, legal), key=lambda t: ((t%18+.5-x)**2+(t//18+.5-y)**2, t))
                choices.append((self.plays[card], CARDS.index(card), slot*576+tile, card))
            if not choices:
                return Decision(WAIT)
            _, _, action, card = min(choices)
            self.plays[card] += 1
            return Decision(action)
        def close(self):
            pass

    for seed in (20261016600, 20261016601):
        # Complete natural matches; no source object is spawned by the probe.
        result = play_match(rt, {0: Player(), 1: Player()}, seed=seed,
                            decks=[CARDS[:], CARDS[:]], max_ticks=4001, verbose=True)
        log = result.pop('play_log')
        accepted = {str(seat): dict(Counter(card for _,card,_,ok in log[seat] if ok)) for seat in (0,1)}
        for seat in ('0','1'):
            require(all(accepted[seat].get(card,0) > 0 for card in CARDS[:4]), ('missing real deployment', seed, seat, accepted))
        result['accepted_cards'] = accepted
        games.append(result)
    require(metrics['plain'] > 100 and metrics['exact11'] == metrics['plain'] == metrics['live10'], metrics)
    require(metrics['attached_rows'] > 0 and metrics['multiple_parent_frames'] > 0 and metrics['continuations'] > 0, metrics)
    require(names['ThreeMusketeer_Rework_Character_1'] > 0 and names['RamRider'] > 0 and names['SkeletonBalloon'] > 0, names)
    require(metrics['barrel_bomb_frames'] > 0 and metrics['released_barrel_child_rows'] > 0, 'no actual barrel container/release')
    require(metrics['max_3m_bodies'] >= 3, 'no complete 3M multi-body observation')
    require(('ThreeMusketeer_Rework_Character_1', 'Projectile') in examples, 'no actual 3M shot observation')
    output.write_text(json.dumps(dict(games=games, metrics=dict(metrics), names=dict(names), kinds=dict(kinds),
        examples=list(examples.values())), indent=2)+'\n')
