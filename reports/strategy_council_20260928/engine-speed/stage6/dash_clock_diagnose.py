"""Capture the first latent dash-to-ordinary-clock divergence."""
import hashlib,json
from pathlib import Path
import cloudpickle,clasher_core
from differential import CARDS,Position,config,initial,snapshot,battle_digest
from stage2 import fingerprint
s=Path(__file__).resolve().parent;cfg=config((*CARDS,'Assassin'));b=initial(21006,cards=('Assassin',*CARDS));r=clasher_core.BattleState(snapshot(b,cfg))
actions=iter(json.loads((s/'dash-r28-focused.json').read_text())['results']['Assassin-6']['actions']);a=next(actions,None);rows=[];saved=False
while b.tick<831:
    while a and a[0]==b.tick:
        _,seat,card,x,y,ok,_=a
        assert b.deploy_card(seat,card,Position(x,y))==ok;assert r.apply_action(seat,card,x,y)==ok;a=next(actions,None)
    old=b.clone();b.step();r.step()
    data=json.loads(r.snapshot())
    if b.tick>=740:
        for id in (79,80):
            if id not in b.entities:continue
            e=b.entities[id];n=next(e for e in data['entities'] if e['id']==id);c=e._ordinary_clock
            py=dict(timeline=c.hit_timeline_ms if c else 0,remaining=c.load_remaining_ms if c else 0,finish=c.finish_elapsed_ms if c else 0)
            rows.append(dict(tick=b.tick,id=id,python_clock=py,native_clock=n['clock'],cooldown=e.attack_cooldown,projection=e._ordinary_clock_projection,native_cooldown=n['cooldown'],phase='travel' if e._bandit_dashing else 'charging' if e._bandit_charging else 'idle',native_phase=n['dash']['phase'],target=e.target_id,native_target=n['target'],moving=e._native_natural_movement_active,native_moving=n['moving']))
            if not saved and any(py[k]!=n['clock'][k] for k in py):
                path=s/f'dash-clock-r28-root{old.tick}.pkl';assert not path.exists();path.write_bytes(cloudpickle.dumps((old,cfg,dict(source=fingerprint()))))
                entry=json.loads((s/'entry.json').read_text())['sha256'];path.with_suffix('.meta.json').write_text(json.dumps(dict(root_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),reference={n:h for n,h in entry.items() if n.startswith('src/clasher/') and not n.startswith('src/clasher/vision/') or n=='gamedata.json'}),indent=2)+'\n')
                saved=True;print('firstlatent',rows[-1],flush=True)
    if battle_digest(b)!=r.digest():break
(s/'dash-clock-r28.json').write_text(json.dumps(rows,indent=2)+'\n')
