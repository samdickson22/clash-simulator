"""Pin the spawn-slam import continuation's first divergent boundary."""
import hashlib,json
from pathlib import Path
import cloudpickle,clasher_core
from differential import Position,config,initial,snapshot,battle_digest
from diagnostics import phase_step
from stage2 import fingerprint
s=Path(__file__).resolve().parent;cards=('MegaKnight','Giant','Log','Zap');cfg=config(cards)
b=initial(669531,cards=cards);b.players[1].elixir=10;assert b.deploy_card(1,'Giant',Position(13.5,18.5))
for _ in range(100):b.step()
b.players[0].elixir=10;assert b.deploy_card(0,'MegaKnight',Position(13.5,13.5))
for _ in range(19):b.step()
r=clasher_core.BattleState(snapshot(b,cfg));assert battle_digest(b)==r.digest()
for _ in range(30):
    old=b.clone();before=json.loads(r.snapshot());trace=phase_step(b,r)
    if battle_digest(b)!=r.digest():
        path=s/f'leap-spawn-r31-root{old.tick}.pkl';assert not path.exists();path.write_bytes(cloudpickle.dumps((old,cfg,dict(source=fingerprint()))))
        entry=json.loads((s/'entry.json').read_text())['sha256'];path.with_suffix('.meta.json').write_text(json.dumps(dict(root_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),reference={n:h for n,h in entry.items() if n.startswith('src/clasher/') and not n.startswith('src/clasher/vision/') or n=='gamedata.json'}),indent=2)+'\n')
        (s/f'leap-spawn-r31-phase{b.tick}.json').write_text(json.dumps(trace,indent=2)+'\n')
        for name,data in trace.items():print(name,data['field_diff'][:15],flush=True)
        break
