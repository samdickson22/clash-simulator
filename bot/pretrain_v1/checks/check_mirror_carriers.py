"""Regression for Sol R3 #1: Fireball then Mirror-Fireball at one aim must not collide reader ids in sim_rsim."""
import json, sys
sys.path.insert(0, '/mpac/sdicks02/repos/clasher-pretrain-v1')
import royalesim as rs
from bot.pretrain_v1.sim_rsim import RsimFrames
from bot.pretrain_v1 import featurize as F
b = rs.Battle(card_names=None, slot_of_k=[[0, 1, 2], [0, 1, 2]], calibration_overrides={}, level=11, tower_level=11)
cat = json.loads(b.catalogue_json()); names = [r[0] for r in cat]; ids = {n: i for i, n in enumerate(names)}
d0 = ['Fireball', 'Mirror', 'Knight', 'Archer', 'Arrows', 'Valkyrie', 'Miner', 'Giant']
d1 = ['HogRider', 'Musketeer', 'IceGolemite', 'Cannon', 'Zap', 'IceSpirits', 'Skeletons', 'Log']
b.reset(seed=1, decks=[[ids[c] for c in d0], [ids[c] for c in d1]], shuffle=0, start_tick=0, elixir_milli=[10000, 6000],
        tower_hp=None, spawns=[])
b.set_command_delay_ticks(0, 0)
types = json.loads(b.unit_types_json())
fr = RsimFrames(names, types, 1, rs.ENTITY_FIELDS, rs.SPELL_FIELDS, lambda n: {'Archer': 'Archers', 'IceGolemite': 'IceGolem', 'IceSpirits': 'IceSpirit'}.get(n, n))
b.step([], 90)
aim = (4*18000 + 9000, 26*18000 + 9000)
print('fireball', b.step([(0, 0, *aim)], 0))
errors, carriers, h = [], 0, F.History()
for k in range(12):
    if k == 6:
        s = json.loads(b.state_json()); slot = s['players'][0]['hand'].index(ids['Mirror'])
        print('mirror', b.step([(0, slot, *aim)], 0))
    b.step([], 5)
    s = json.loads(b.state_json())
    got, why, line = fr.record(s)
    if got is None:
        errors.append(why); continue
    rec, ex = got
    carriers = max(carriers, len(ex['spells']))
    F.observe(rec, ex, h)
print('errors', errors, 'max simultaneous carriers seen', carriers, 'opp casts', len(h.opp))
assert not errors
