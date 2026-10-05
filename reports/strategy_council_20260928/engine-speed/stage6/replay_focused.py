"""Pin a fresh failing focused trajectory's first transition and root."""
import argparse,hashlib,json
from pathlib import Path
import cloudpickle,clasher_core
from diagnostics import phase_step
from differential import CARDS,Position,config,initial,snapshot,battle_digest
from stage2 import fingerprint

p=argparse.ArgumentParser();p.add_argument('--receipt',type=Path,required=True);p.add_argument('--key',required=True);p.add_argument('--prefix',required=True);a=p.parse_args()
folder=Path(__file__).resolve().parent;r0=json.loads(a.receipt.read_text())['results'][a.key]
card,case=a.key.rsplit('-',1);cards=(card,)+tuple(c for c in CARDS if c!=card);cfg=config((*CARDS,card))
b=initial(21000+int(case),cards=cards)
for player in b.players:player.elixir=max(player.elixir,cfg['cards'][card]['cost'])
r=clasher_core.BattleState(snapshot(b,cfg));actions=iter(r0['actions']);action=next(actions,None)
while b.tick<r0['tick']-1:
    while action and action[0]==b.tick:
        _,seat,name,x,y,expected,_=action
        assert b.deploy_card(seat,name,Position(x,y))==expected
        assert r.apply_action(seat,name,x,y)==expected
        action=next(actions,None)
    b.step();r.step();assert battle_digest(b)==r.digest(),b.tick
path=folder/f'{a.prefix}-root{b.tick}.pkl';assert not path.exists()
path.write_bytes(cloudpickle.dumps((b,cfg,dict(source=fingerprint(),native=hashlib.sha256(Path(clasher_core.__file__).read_bytes()).hexdigest()))))
entry=json.loads((folder/'entry.json').read_text())['sha256'];refs={n:h for n,h in entry.items() if n.startswith('src/clasher/') and not n.startswith('src/clasher/vision/') or n=='gamedata.json'}
path.with_suffix('.meta.json').write_text(json.dumps(dict(root_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),reference=refs),indent=2)+'\n')
trace=phase_step(b,r);(folder/f'{a.prefix}-phase{b.tick}.json').write_text(json.dumps(trace,indent=2)+'\n')
for name,state in trace.items():print(name,state['field_diff'][:15],flush=True)
