"""Retain the first default Giant-drag differential transition."""
import argparse,hashlib,json
from pathlib import Path
import cloudpickle,clasher_core
from differential import Position,config,initial,snapshot,battle_digest
from diagnostics import phase_step
from stage2 import fingerprint
p=argparse.ArgumentParser();p.add_argument('--label',required=True);a=p.parse_args()
s=Path(__file__).resolve().parent;cards=('Fisherman','Giant','Zap','Knight');cfg=config(cards)
b=initial(669533,cards=cards)
for seat,name,y in ((0,'Fisherman',13.5),(1,'Giant',18.5)):
    b.players[seat].elixir=10;assert b.deploy_card(seat,name,Position(13.5,y))
r=clasher_core.BattleState(snapshot(b,cfg))
for _ in range(260):
    old=b.clone();trace=phase_step(b,r)
    if battle_digest(b)!=r.digest():
        path=s/f'hook-{a.label}-root{old.tick}.pkl';assert not path.exists();path.write_bytes(cloudpickle.dumps((old,cfg,dict(source=fingerprint()))))
        entry=json.loads((s/'entry.json').read_text())['sha256'];path.with_suffix('.meta.json').write_text(json.dumps(dict(root_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),reference={n:h for n,h in entry.items() if n.startswith('src/clasher/') and not n.startswith('src/clasher/vision/') or n=='gamedata.json'}),indent=2)+'\n')
        (s/f'hook-{a.label}-phase{b.tick}.json').write_text(json.dumps(trace,indent=2)+'\n')
        for name,data in trace.items():print(name,data['field_diff'][:15],flush=True)
        break
