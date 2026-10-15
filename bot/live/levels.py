"""Level-aware planner root (LIVE track, exploration).

The frozen fair_player.Resources.root builds the native root from level-11 templates. Live games have real card and
tower levels. `LevelRoot.root` is Resources.root (engine-speed/stage5/fair_player.py) copied verbatim, plus one step:
each board body's level-scaled stats (STAT_KEYS, the template's hp/shield/bomb damage) are multiplied by
level_multiplier(L)/level_multiplier(11) (clasher.stat_scaling, the game's table) BEFORE hp = hp_fraction*max_hp.

Levels: Levels(own=11, opp=11, own_tower=11, opp_tower=11, own_bodies={}, opp_bodies={}) - per-owner defaults with
per-body overrides (body token names, e.g. {'Knight': 9}). Towers (KingTower, Tower) use the tower levels.
Limits (documented, not hidden): only bodies ON THE BOARD are scaled. Cards played inside rollouts spawn from the
shared native config at level 11 for both sides (per-player card levels need an engine change); R3a/it5s2 still
see level 11 in their packets (they never saw anything else). With every level 11 the payload is byte-identical
to Resources.root (test_levels).
"""
from __future__ import annotations

import copy
import json
import random
from dataclasses import dataclass, field

import numpy as np

STAT_KEYS = ('max_hp', 'damage', 'child_damage', 'death_damage', 'projectile_damage', 'special_damage', 'crown_damage')
TOP_KEYS = ('shield', 'bomb_damage')
TOWERS = ('KingTower', 'Tower')


@dataclass(frozen=True)
class Levels:
    own: int = 11
    opp: int = 11
    own_tower: int = 11
    opp_tower: int = 11
    own_bodies: dict = field(default_factory=dict)
    opp_bodies: dict = field(default_factory=dict)

    def level(self, body, own):
        if body in TOWERS:
            return self.own_tower if own else self.opp_tower
        return (self.own_bodies if own else self.opp_bodies).get(body, self.own if own else self.opp)

    def trivial(self):
        return {self.own, self.opp, self.own_tower, self.opp_tower} == {11} and \
            all(v == 11 for v in list(self.own_bodies.values()) + list(self.opp_bodies.values()))


def ratio(level):
    from clasher.stat_scaling import level_multiplier
    return level_multiplier(int(level))/level_multiplier(11)


def scale(e, r):
    if r == 1.:
        return e
    for k in STAT_KEYS:
        v = e['stats'].get(k)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            e['stats'][k] = type(v)(v*r) if isinstance(v, float) else int(v*r)
    for k in TOP_KEYS:
        v = e.get(k)
        if isinstance(v, (int, float)) and not isinstance(v, bool) and v:
            e[k] = v*r
    return e


class LevelRoot:
    def __init__(self, R, levels: Levels):
        self.R, self.levels = R, levels

    def payload(self, info, opponent, rng):
        """Resources.root up to json.dumps, with level scaling (see module docstring)."""
        from clasher.rl.contract_v5 import CHAMPION_COOLDOWN_GLOBAL, CHAMPION_DURATION_GLOBAL
        R = self.R
        names = R.builder.token_names
        obs = info.packet.observation
        entities = []
        for token, row in zip(obs.entity_ids[obs.entity_mask], obs.entity_features[obs.entity_mask]):
            kind = ('Troop', 'Building', 'Projectile', 'AreaEffect', 'Entity')[int(np.argmax(row[4:9]))]
            key = (int(token), kind)
            if key not in R.templates:
                raise ValueError(f'no C56 public model template: {names[int(token)]}/{kind}')
            e = copy.deepcopy(R.templates[key])
            x, y = float(row[0])*18, float(row[1])*32
            fx, fy = float(row[27]), float(row[28])
            if info.seat == 1:
                x, y, fx, fy = 18-x, 32-y, -fx, -fy
            owner = info.seat if row[2] else 1-info.seat
            scale(e, ratio(self.levels.level(names[int(token)], owner == info.seat)))          # <- the only addition
            e.update(id=len(entities)+1, owner=owner, x=x, y=y, hp=float(row[9])*e['stats']['max_hp'],
                     alive=True, target=None, deploy=0., stagger=0., facing=[round(fx*1000), round(fy*1000)],
                     age=1000, birth=info.tick-1, lane=1 if x < 9 else 2, clock=dict(interval=max(1, e['stats']['interval']),
                     load=e['stats']['load'], timeline=0, remaining=0, finish=0), cooldown=0.)
            if row[9] < 1:
                e['shield'] = 0.
            if e['king']:
                base = 8 if owner == info.seat else 11
                e['active'] = bool(row[9] < 1 or obs.global_features[base] == 0 or obs.global_features[base+1] == 0)
            else:
                e['active'] = True
            if e['class'] == 'Projectile':
                distance = max(1., e['stats'].get('projectile_range', 0), e['stats']['range'])
                e.update(aim=[x+fx*distance, y+fy*distance], shot_target=None)
            c = e.get('champion')
            if c and owner == info.seat:
                a = c['ability']; now = info.tick*50
                remaining = round(float(obs.global_features[CHAMPION_DURATION_GLOBAL])*a['duration'])
                cooldown = round(float(obs.global_features[CHAMPION_COOLDOWN_GLOBAL])*a['cooldown'])
                if remaining > 0:
                    a.update(active=True, start=now-a['duration']+remaining, last_use=now-a['duration']+remaining)
                elif cooldown > 0:
                    a.update(active=False, start=now-a['duration']-a['cooldown']+cooldown,
                             last_use=now-a['duration']-a['cooldown']+cooldown)
            entities.append(e)
        for e in entities:
            c = e.get('champion')
            if c and c['effect']['kind'] == 'Goblin':
                monsters = [m for m in entities if m['owner'] == e['owner'] and m['stats']['name'] == 'Goblinstein']
                m = min(monsters, key=lambda m: (m['x']-e['x'])**2+(m['y']-e['y'])**2, default=None)
                c['effect'].update(monster=m['id'] if m else None, anchor=[m['x'], m['y']] if m else [e['x'], e['y']])
        players = [None, None]; players[info.seat] = info.own; players[1-info.seat] = opponent
        state = random.Random(int(rng.integers(2**63))).getstate()[1]
        return json.dumps(dict(tick=info.tick, next_id=len(entities)+1, players=players, entities=entities,
                               pending_casts=[], sudden_death=bool(obs.global_features[4]),
                               rng=dict(state=state[:-1], index=state[-1]), game_over=False, winner=None,
                               config=R.config))

    def root(self, info, opponent, rng):
        if self.levels.trivial():
            return self.R.root(info, opponent, rng)
        import clasher_core
        return clasher_core.BattleState(self.payload(info, opponent, rng))
