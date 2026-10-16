"""Measurement-only native fixture trace. Select source/native/root through the caller's environment."""
import hashlib,json,sys
from pathlib import Path
import differential as D
from bot.fidelity import rs_parity as rp
from bot.fidelity.fixture import load_fixture,load_split
rp.D=Path(sys.argv[1]);ep=sys.argv[2];out=Path(sys.argv[3]);out.mkdir(exist_ok=True)
fix=load_fixture(rp.D/'t1-trainval'/ep,load_split(rp.D/'t1-split.json'))
b=rp._py_battle(fix)
cards=tuple(sorted({rp._name(rp.ID2N[i]) for s in (0,1) for i in fix.initial_order[s]}))
initial=D.snapshot(b,D.config(cards));(out/'input.json').write_text(initial)
r=D.clasher_core.BattleState(initial)
plays=sorted((p for p in fix.plays if p.kind!='champion ability'),key=lambda p:(p.exec_tick,p.side,p.slot))
pi=0; rows=[]
for t in range(fix.start_tick,fix.end_tick+1):
 s=r.snapshot()
 rows.append(dict(tick=t,digest=str(r.digest()),snapshot_sha=hashlib.sha256(s.encode()).hexdigest()))
 if t==fix.start_tick or (t-fix.start_tick)%100==0 or t==fix.end_tick or t==int(sys.argv[4] if len(sys.argv)>4 else -1):
  (out/f'snapshot-{t}.json').write_text(s)
 if t==fix.end_tick:break
 while pi<len(plays) and plays[pi].exec_tick-1<=t:
  p=plays[pi];r.apply_action(p.side,rp._name(p.card),p.tile[0],p.tile[1]);pi+=1
 r.step(1)
(out/'trace.json').write_text(json.dumps(dict(episode=ep,cards=cards,start=fix.start_tick,end=fix.end_tick,rows=rows)))
print(json.dumps(dict(episode=ep,cards=cards,start=fix.start_tick,end=fix.end_tick)),flush=True)
