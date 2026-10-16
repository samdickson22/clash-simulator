"""Print one card's paired fidelity records side by side (ours / rsim). Usage: show.py RESULTS.jsonl CARD [SCENARIO]"""
import json, sys
path, card = sys.argv[1], sys.argv[2]
want = sys.argv[3] if len(sys.argv) > 3 else None
for l in open(path):
    r = json.loads(l)
    if r['card'] != card or (want and r['scenario'] != want):
        continue
    print('=====', r['card'], r['scenario'], r['table'])
    for k in ('ours', 'rsim'):
        x = r[k]
        if 'error' in x:
            print(k, 'ERROR', x['error'][-800:]); continue
        print('--', k, 'deploy', x['deployments'], 'tower', x['tower_damage'], 'alive', x['alive_at'], 'counters', x['counters'])
        for u in x['units']:
            print('   unit', {kk: u[kk] for kk in ('name', 'birth', 'ready', 'death', 'max_hp', 'speed_tiles_s', 'position', 'configured_damage', 'configured_speed') if kk in u})
        print('   tower_hits', x['tower_hits'][:30])
        print('   enemy_hits', x['enemy_hits'][:30])
        print('   own_hits', x['own_hits'][:30])
