"""Localize one native-diff game's first divergence: mixed_games.run_one (fresh config), then print each phase's
field differences that were not already present before the step. Usage (PYTHONPATH as replay_games.py):
triage_game.py PLAN.json GAME [N]"""
import json, sys
import differential as D
import mixed_games as M

plan = json.load(open(sys.argv[1])); g = int(sys.argv[2]); n = int(sys.argv[3]) if len(sys.argv) > 3 else 25
game = next(x for x in plan['games'] if x['game'] == g)
cfg = D.config(tuple(sorted(plan['kinds'])))
r = M.run_one(game, cfg, plan)
print('first', r.get('first', {}) and {k: r['first'][k] for k in ('kind', 'tick')})
ph = (r.get('triage') or {}).get('phases') or {}
base = {json.dumps(d, sort_keys=True) for d in ph.get('before', {}).get('field_diff', [])}
for label, data in ph.items():
    fd = [d for d in data['field_diff'] if json.dumps(d, sort_keys=True) not in base]
    print(label, len(fd))
    for d in fd[:n]:
        print('   ', d)
    for eid, pr in list(data.get('entities', {}).items())[:0]:
        pass
ids = sorted({int(d['field'].split('.')[2]) for v in ph.values() for d in v['field_diff']
              if d['field'].startswith('.entities.') and d['field'].split('.')[2].isdigit()})
for eid in ids[:12]:
    e = next((v['entities'][str(eid)]['python'] for v in ph.values()
              if v.get('entities', {}).get(str(eid), {}).get('python')), None)
    if e:
        print('entity', eid, e.get('class'), e.get('stats', {}).get('name'), 'owner', e.get('owner'), (e.get('x'), e.get('y')),
              {k: e.get(k) for k in ('target', 'move_target', 'last_target', 'windup', 'started', 'cooldown', 'clock', 'stun', 'freeze_pause', 'push', 'deploy', 'hp')})
