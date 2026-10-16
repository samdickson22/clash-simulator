"""EmpiricalNoise plus per-match YOLO-like augmentations, preserving true_uid."""
import json

import numpy as np

from bot.live.empirical import EmpiricalNoise, STATS


def sample_parameters(rng, perfect=False):
    return dict(perfect=bool(perfect), empirical_strength=float(rng.uniform(.55, 1.2)),
                frame_drop=float(rng.uniform(.02, .04)), burst_start=float(rng.uniform(.003, .015)),
                burst_ticks=[5, 40], family_flip=float(rng.uniform(.01, .16)),
                cross_family_flip=float(rng.uniform(.0005, .004)),
                unknown_buildings=bool(rng.random() < .3), provenance_p=float(rng.uniform(.1, .9)),
                provenance_frames=int(rng.integers(1, 3)))


class NoiseChannel:
    def __init__(self, rng, deck, bodies, parameters, stats=STATS):
        self.rng, self.bodies, self.p = rng, bodies, parameters
        self.cards = sorted(c for c in bodies.main if bodies.main[c])
        self.emp = EmpiricalNoise(json.loads(stats.read_text()), rng, deck, self.cards)
        strength = parameters['empirical_strength']
        self.emp.pos = self.emp.pos * strength
        self.emp.hp = self.emp.hp * strength
        self.emp.fp_rate = {k: v * strength for k, v in self.emp.fp_rate.items()}
        det_p = self.emp._det_p
        self.emp._det_p = lambda card, was: float(np.clip(1-strength*(1-det_p(card, was)), 0, 1))
        # EmpiricalNoise's unit dict copies retain true_uid exactly; FPs omit it.
        self.bursts, self.hints, self.deployment_frames = {}, {}, {}
        self.previous_tick = None

    def __call__(self, record, origins):
        tick, p, rng = record['tick'], self.p, self.rng
        if p['perfect']:
            noisy = record
        else:
            noisy = self.emp(dict(record, events=[]))
        hint_for_dep = {}
        for u in record['units']:
            o = origins[u['true_uid']]
            dep = o['deployment_index']
            if o['kind'] != 'main' or dep is None:
                continue
            if dep not in self.hints:
                self.hints[dep] = bool(rng.random() < p['provenance_p'])
            hint_for_dep[dep] = self.hints[dep] and self.deployment_frames.get(dep, 0) < p['provenance_frames']
        for dep in hint_for_dep:
            self.deployment_frames[dep] = self.deployment_frames.get(dep, 0) + 1
        out, ids, unknown = [], [], []
        for u in noisy['units']:
            uid = u.get('true_uid')
            if not p['perfect'] and uid is not None:
                if tick < self.bursts.get(uid, -1):
                    continue
                if rng.random() < p['burst_start']:
                    self.bursts[uid] = tick + int(rng.integers(5, 41))
                    continue
            u = dict(u)
            if not p['perfect']:
                family = self.bodies.families.get(self.bodies.family_of(u['card']), {u['card']})
                internal = sorted(c for c in family if c != u['card'] and c in self.cards)
                if rng.random() < p['cross_family_flip']:
                    options = [c for c in self.cards if c not in family]
                    if options:
                        u['card'] = str(rng.choice(options))
                elif internal and rng.random() < p['family_flip']:
                    u['card'] = str(rng.choice(internal))
                # Entire building families become class-only for this match,
                # simulating missing card vocabulary (children remain labelled).
                origin = origins.get(uid, {})
                if p['unknown_buildings'] and origin.get('is_building', False):
                    unknown.append(dict(kind='building', owner=u['owner'], x=u['x'], y=u['y'],
                                        score=u.get('score', .8), true_uid=uid, false_positive=False))
                    continue
            o = origins.get(uid, {})
            hint = o.get('source_card') if hint_for_dep.get(o.get('deployment_index'), False) else None
            if o.get('kind') != 'main':
                hint = None
            out.append([u['card'], u['owner'], u['x'], u['y'], u.get('score', 1.), hint])
            ids.append(uid)
        dropped = not p['perfect'] and bool(rng.random() < p['frame_drop'])
        if dropped:
            out, ids, unknown = [], [], []
        return dict(units=out, true_uid=ids, false_positive=[uid is None for uid in ids],
                    unknown_units=unknown, towers=noisy['towers'], frame_dropped=dropped)
