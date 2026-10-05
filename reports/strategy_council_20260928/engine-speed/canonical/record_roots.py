"""Fresh canonical-data roots, never reuse pre-canonical pickled card stats."""
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import random
import cloudpickle
from clasher.data import CardDataLoader
from differential import Position, battle_digest
from stage2_matches import battle

out = Path(__file__).resolve().parent
games = json.loads((out / 'stage2_games.json').read_text())['results']
loader = CardDataLoader()
roots, rows = [], []
for case in range(8):
    record = games[str(case)]
    b = battle(record['episode'], loader)
    ticks = set(random.Random(20261004 + case).sample(range(90, record['ticks'] - 200), 32))
    schedule = defaultdict(list)
    for a in record['actions']:
        schedule[a[0]].append(a)
    while ticks:
        if b.tick in ticks:
            ticks.remove(b.tick)
            roots.append(b.clone())
            rows.append(dict(case=case, tick=b.tick, digest=battle_digest(b)))
        for a in schedule[b.tick]:
            assert b.deploy_card(a[1], a[3], Position(a[4], a[5])) == a[6]
        b.step()
    print('roots', case, len(roots), flush=True)
p = out / 'stage3_roots.pkl'
p.write_bytes(cloudpickle.dumps(roots))
(out / 'stage3_roots.json').write_text(json.dumps(dict(sha256=hashlib.sha256(p.read_bytes()).hexdigest(), roots=rows), indent=2)+'\n')
