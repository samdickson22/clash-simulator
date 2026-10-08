import json,os,socket,sys,time
from pathlib import Path
root=Path('/mpac/sdicks02/repos/clasher')
sys.path[:0]=[str(root/'engine-rs'),str(root/'src')]
from clasher.rl.contract_v5 import ContractV5ObservationBuilder
b=ContractV5ObservationBuilder()
print('TOKENS', b.token_names[:12],flush=True)
print('HOG', b.loader.get_card('HogRider').mana_cost, b.token_id('HogRider',namespace='card_action'),flush=True)
p=root/'reports/strategy_council_20260928/imitation/data/c56-store-v1/dev/manifest.json'
d=json.loads(p.read_text())
import numpy as np
for x in d['perspectives'][:3]:
 i=x['target_start']; print('DECK',x['summary']['own_deck'],np.load(p.parent/'own_deck.npy',mmap_mode='r')[i].tolist(),flush=True)
f=root/'reports/explore/loss-review/seed-exclusion.json'
meta=Path('/mpac/sdicks02/jobs/clasher/seed-inventory/gates-bc-parallel-r4')
z=json.loads((meta/'inventory.json').read_text());c=json.loads((meta/'compact.json').read_text())
f.write_text(json.dumps(dict(proposed=z['proposed'],explicit=c['explicit_seed_values'],source=str(meta),formulas=c['formula_groups'])))
print('SEEDS',len(z['proposed']),len(c['explicit_seed_values']),flush=True)
