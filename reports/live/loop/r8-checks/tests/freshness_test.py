"""F1/F2 exact old-source negatives and new-source producer/constructor regressions.
Actual source AST + frozen metadata consumer, fixture leaves only; no model/input/host.
"""
from pathlib import Path
import ast,types,json,datetime,os
from dataclasses import replace
R=Path(__file__).resolve().parents[1]
OUT=Path(os.environ['R8_TEST_OUT'])
p=R/'tests/producer_test.py';nodes=[]
for n in ast.parse(p.read_text()).body:
 if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='results'for t in n.targets):break
 nodes.append(n)
x={'__file__':str(p),'__name__':'freshness_fixture'};exec(compile(ast.Module(body=nodes,type_ignores=[]),str(p),'exec'),x)
x['sys'].modules['clasher.rl.public_observation'].ConfidenceAwareActorObservation=x['Packet']
b=x['b'];checks=[];results={}
def check(name,condition):
 assert condition,name
 checks.append(name)
def loader(path):
 source=ast.parse(path.read_text());cl=next(n for n in source.body if isinstance(n,ast.ClassDef)and n.name=='SyncSession')
 methods=[n for n in cl.body if isinstance(n,ast.FunctionDef)and n.name in('_slot_permission_view','tap_guard')]
 subject=ast.ClassDef(name='FreshnessSubject',bases=[],keywords=[],body=methods,decorator_list=[])
 scope=dict(x['ns']);exec(compile(ast.fix_missing_locations(ast.Module(body=[subject],type_ignores=[])),str(path),'exec'),scope)
 init=next(n for n in cl.body if isinstance(n,ast.FunctionDef)and n.name=='__init__');body=[]
 for n in init.body:
  if isinstance(n,ast.Expr)and isinstance(n.value,ast.Call)and ast.unparse(n.value.func)=='kw.setdefault':break
  body.append(n)
 init.name='constructor_check';init.body=body
 exec(compile(ast.fix_missing_locations(ast.Module(body=[init],type_ignores=[])),str(path),'exec'),scope)
 return scope['FreshnessSubject'],scope['constructor_check']
def session(row,loader):
 subject,init=loader;s,v=x['fixture'](row);s.__class__=subject
 init(s,None,types.SimpleNamespace(slot_permission_mode='required'),[],slot_permission_mode='required')
 return s,v
for label,path in [('old_r1',R/'fixtures/pre-fix-handsync.py'),('candidate',R/'candidate/live/loop/handsync.py')]:
 source=loader(path);rows=[]
 for row in x['T']:
  a,va=session(row,source);s,v=session(row,source)
  # Distinct sessions, same capture/poll, DIFFERENT current UI/permissions.
  s._rec['hand']['ui'][1]='empty'
  av=a._slot_permission_view(va);sv=s._slot_permission_view(v)
  check(label+' own permission differs '+str(row['n']),av.reserved.packet.slot_permission.allowed[1]and not sv.reserved.packet.slot_permission.allowed[1])
  packet=replace(sv.reserved.packet,slot_permission=av.reserved.packet.slot_permission)
  foreign=replace(sv,reserved=replace(sv.reserved,packet=packet));bound=b.bind_view(foreign,'required')
  allowed,status=b.permission_state(bound.reserved.packet);choice=b.choice_or_wait(576,bound.reserved.packet)
  if label=='old_r1':check(label+' F1 old defect reproduced '+str(row['n']),status['status']=='current'and allowed[1]and choice==576 and s.tap_guard(576)=='empty')
  else:
   check(label+' F1 foreign namespace stale WAIT '+str(row['n']),status['status']=='stale'and allowed==(False,)*4 and choice==2304)
   check(label+' constructor session IDs distinct '+str(row['n']),a._permission_session_id!=s._permission_session_id and len(a._permission_session_id)==32)
  s,v=session(row,source);original=s._rec['timestamp_ms'];s._rec['timestamp_ms']=original+1
  first=s._slot_permission_view(v);highwater=s._permission_last_actable_frame
  check(label+' mismatch-first denies '+str(row['n']),first.reserved.packet.slot_permission.allowed==(False,)*4)
  s._rec['timestamp_ms']=original
  second=s._slot_permission_view(replace(v,tick=v.tick+5));bound=b.bind_view(second,'required')
  allowed,status=b.permission_state(bound.reserved.packet);choice=b.choice_or_wait(576,bound.reserved.packet)
  if label=='old_r1':check(label+' F2 old defect reproduced '+str(row['n']),highwater is None and allowed[1]and choice==576)
  else:
   check(label+' F2 corrected same capture WAIT '+str(row['n']),highwater==original and allowed==(False,)*4 and choice==2304)
   s._rec['timestamp_ms']+=1;s._rec['ts_ms']+=1;s._frame_ms=s._rec['ts_ms']
   new=s._slot_permission_view(replace(v,tick=v.tick+10));allowed,status=b.permission_state(b.bind_view(new,'required').reserved.packet)
   check(label+' new valid capture recovers '+str(row['n']),any(allowed)and status['status']=='current')
  rows.append(dict(n=row['n'],cross_session=label=='candidate',initial_consumed=highwater,corrected_capture_choice=choice))
 results[label]=rows
source=loader(R/'candidate/live/loop/handsync.py');s,v=session(x['T'][0],source)
s._rec['timestamp_ms']+=1;s._slot_permission_view(replace(v,can_act=False))
check('catchup malformed read does not consume actable capture',s._permission_last_actable_frame is None)
s._rec['timestamp_ms']-=1;out=s._slot_permission_view(v)
check('first actual poll can use current valid capture after catchup',any(out.reserved.packet.slot_permission.allowed))
for bad in(None,'',123,'x'*65):
 s,v=session(x['T'][0],source);s._permission_session_id=bad
 out=s._slot_permission_view(v);allowed,status=b.permission_state(b.bind_view(out,'required').reserved.packet)
 check('missing/malformed session scope denied '+repr(bad),allowed==(False,)*4)
 s._permission_session_id='restored-metadata-only';out=s._slot_permission_view(replace(v,tick=v.tick+5))
 check('scope correction same capture remains consumed '+repr(bad),out.reserved.packet.slot_permission.allowed==(False,)*4)
for bad in(None,float('nan'),True,'invalid'):
 s,v=session(x['T'][0],source);original=s._rec['timestamp_ms'];s._rec['timestamp_ms']=bad
 out=s._slot_permission_view(v)
 check('invalid native timestamp first denied '+repr(bad),out.reserved.packet.slot_permission.allowed==(False,)*4 and s._permission_last_actable_frame==original)
 s._rec['timestamp_ms']=original;out=s._slot_permission_view(replace(v,tick=v.tick+5))
 check('native timestamp correction no new capture denied '+repr(bad),out.reserved.packet.slot_permission.allowed==(False,)*4)
 s._rec['timestamp_ms']+=1;s._rec['ts_ms']+=1;s._frame_ms=s._rec['ts_ms'];out=s._slot_permission_view(replace(v,tick=v.tick+10))
 check('native timestamp new valid capture recovers '+repr(bad),any(out.reserved.packet.slot_permission.allowed))
s,v=session(x['T'][0],source);source[1](s,None,types.SimpleNamespace(),[],slot_permission_mode='legacy')
check('legacy has no nonce and exact view identity',s._permission_session_id is None and s._slot_permission_view(v)is v)
receipt={'UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'passed':len(checks),'checks':checks,'results':results,'scope':'old exact r1 negative + actual new producer/constructor + actual frozen consumer, fixture leaves; no input/NN/runtime/field-future claim'}
(OUT/'freshness-result.json').write_text(json.dumps(receipt,indent=2)+'\n');print('PASS',len(checks),'F1/F2/session/legacy/catchup controls')
