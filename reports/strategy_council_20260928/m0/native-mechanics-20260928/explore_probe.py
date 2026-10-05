"""Exploration: format of tower/projectile rows; Fireball on dormant King."""
import json, sys
sys.path.insert(0, '.')
import nm_lib as L
D0 = ['Knight','Giant','HogRider','Skeletons','DarkPrince','IceGolem','Musketeer','Cannon']
D1 = ['Knight','Giant','HogRider','Fireball','Zap','Log','IceSpirit','DarkPrince']
port = 26790
seed, config, initial = L.find_seed(port, D0, D1, need1=('Fireball','Zap'))
print('seed', seed, [p['elixir'] for p in initial['players']])
cmds = [{'tick': 100, 'owner': 1, 'card': 'Fireball', 'xy': (9.0, 3.0)}]
nat = L.run_native(port, config, cmds, 240, rich=True)
json.dump(nat, open('/tmp/nm_explore.json', 'w'))
for f in nat['frames'][95:240:6]:
    print(f['tick'], [(o['name'], o['owner'], o['x'], o['y'], o['hp'], o.get('target'), o.get('stage'), o.get('projectile')) for o in f['objects'] if o['name'] in ('tower','Fireball') or o.get('projectile')][:8])
