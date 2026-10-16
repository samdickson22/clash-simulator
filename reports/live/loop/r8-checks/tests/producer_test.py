"""Actual loop producer AST + final canonical backend metadata; no model/engine/input.

Packet and player leaves are fixtures. Original four field states come from exact logged input replay.
"""
import ast
import os
import copy
from collections import Counter
from dataclasses import dataclass, replace
import importlib.util
import json
import math
from numbers import Real
from pathlib import Path
import sys
import types
import numpy as np
R=Path(__file__).resolve().parents[1]
OUT=Path(os.environ['R8_TEST_OUT'])
backend=R/'candidate/src/clasher/rl/slot_permission.py'
spec=importlib.util.spec_from_file_location('producer_actual_permission_backend',backend)
b=importlib.util.module_from_spec(spec);sys.modules[spec.name]=b;spec.loader.exec_module(b)
# This alias exposes the actual helper's immutable class through its proposed public re-export.
sys.modules['clasher.rl.public_observation']=types.SimpleNamespace(SlotPermission=b.SlotPermission)
source=ast.parse((R/'candidate/live/loop/handsync.py').read_text())
cl=next(n for n in source.body if isinstance(n,ast.ClassDef)and n.name=='SyncSession')
methods=[n for n in cl.body if isinstance(n,ast.FunctionDef)and n.name in('_slot_permission_view','tap_guard')]
subject=ast.ClassDef(name='Subject',bases=[],keywords=[],body=methods,decorator_list=[])
ns=dict(replace=replace,Real=Real,math=math)
conf=next(n for n in source.body if isinstance(n,ast.FunctionDef)and n.name=='confident')
exec(compile(ast.fix_missing_locations(ast.Module(body=[conf,subject],type_ignores=[])),'actual-loop-producer','exec'),ns)
@dataclass(frozen=True)
class Packet:
 observation:object
 hand_id_confidence:object
 global_feature_confidence:object
 slot_permission:object=None
 slot_permission_capture_id:object=None
 slot_permission_poll_tick:object=None
 slot_permission_mode:str='legacy'
@dataclass(frozen=True)
class Info:
 tick:int
 own:dict
 packet:Packet
@dataclass(frozen=True)
class View:
 tick:int
 info:Info
 reserved:Info
 public_events:list
 pending:tuple=()
 can_act:bool=True

fixture_data=json.loads((R/'fixtures/original-four.json').read_text())
T=fixture_data['timeline']
P={p['n']:p for p in fixture_data['perception']}

def fixture(row):
 rec=copy.deepcopy(P[row['n']]);s=ns['Subject']();s._rec=rec;s._frame_ms=rec['ts_ms']
 s.slot_permission_mode='required';s._permission_session_id='producer-fixture-session';s._permission_last_actable_frame=None;s.guard_p=.1
 s.tr=types.SimpleNamespace(own_tracker=types.SimpleNamespace(hand=list(row['tracker_hand'])),stats=Counter())
 own=copy.deepcopy(row['physical_own']);obs=types.SimpleNamespace(hand_ids=np.array([1,2,3,4,5]),global_features=np.arange(18,dtype=np.float32),hand_levels=np.full(5,11),hand_level_confidence=np.ones(5),entity_ids=np.arange(3),entity_features=np.ones((3,32)),entity_levels=np.full(3,11),entity_mask=np.ones(3,dtype=bool),opponent_seen_card_ids=np.arange(8))
 packet=Packet(obs,np.ones(5),np.ones(18));info=Info(row['poll'],own,packet)
 return s,View(row['poll'],info,info,[],())

results=[]
for row in T:
 s,v=fixture(row);h=copy.deepcopy(s._rec['hand']);out=s._slot_permission_view(v)
 assert out is not v and out.info is v.info and out.reserved.own is v.reserved.own
 assert out.reserved.packet is not v.reserved.packet and v.reserved.packet.slot_permission is None
 assert out.public_events is v.public_events and out.pending is v.pending
 for name in ('observation','hand_id_confidence','global_feature_confidence'):
  assert getattr(out.reserved.packet,name)is getattr(v.reserved.packet,name)
 assert s._rec['hand']==h and s.tr.own_tracker.hand==row['tracker_hand']
 pre,why=b.permission_state(out.reserved.packet);assert pre==(False,)*4 and why['status']=='missing_current_capture'
 bound=b.bind_view(out,'required');allowed,why=b.permission_state(bound.reserved.packet)
 expected=tuple(s.tap_guard(i*576)is None for i in range(4));assert allowed==expected and why['status']=='current'
 assert allowed[row['slot']]is False and any(allowed)
 # Backend binds actual poll independently; old permission/capture cannot authorize a different current poll.
 stale=b.bind_view(replace(out,tick=v.tick+5),'required');a,status=b.permission_state(stale.reserved.packet)
 assert a==(False,)*4 and status['status']=='stale'
 capture=replace(bound.reserved.packet,slot_permission_capture_id='different-current-capture')
 assert b.permission_state(capture)[1]['status']=='stale'
 # Explicit repeated-frame control: no new actable poll from the same captured input.
 reused=s._slot_permission_view(replace(v,tick=v.tick+5));assert reused.reserved.packet.slot_permission.allowed==(False,)*4
 assert set(reused.reserved.packet.slot_permission.reasons)=={'invalid_or_stale_observation'}
 # Legacy path is the identical view, with no metadata or model-array change.
 s.slot_permission_mode='legacy';assert s._slot_permission_view(v)is v
 results.append(dict(n=row['n'],allowed=allowed,reasons=why['reasons']))
 print('PASS original producer state, immutable model/ledger, independent bindings, reuse/legacy',row['n'],allowed)

row=T[0]
for mode in ('ui_missing','ui_unknown','cards_short','probs_short','capture_mismatch','capture_missing','capture_nan'):
 s,v=fixture(row)
 if mode=='ui_missing':s._rec['hand'].pop('ui')
 elif mode=='ui_unknown':s._rec['hand']['ui'][1]='unknown'
 elif mode=='cards_short':s._rec['hand']['cards']=[]
 elif mode=='probs_short':s._rec['hand']['probs']=[]
 elif mode=='capture_mismatch':s._rec['timestamp_ms']+=1
 elif mode=='capture_missing':s._rec['ts_ms']=None
 elif mode=='capture_nan':s._rec['ts_ms']=float('nan')
 out=s._slot_permission_view(v);bound=b.bind_view(out,'required')
 assert b.permission_state(bound.reserved.packet)[0]==(False,)*4
 assert out.info is v.info and out.reserved.own is v.reserved.own
 print('PASS malformed/stale producer WAIT-only',mode)

# A corrected read on the same already-consumed capture cannot unlock a later actable poll.
s,v=fixture(row);original_ui=s._rec['hand'].pop('ui')
assert s._slot_permission_view(v).reserved.packet.slot_permission.allowed==(False,)*4
s._rec['hand']['ui']=original_ui
assert s._slot_permission_view(replace(v,tick=v.tick+5)).reserved.packet.slot_permission.allowed==(False,)*4
s._rec['ts_ms']+=1;s._rec['timestamp_ms']+=1;s._frame_ms=s._rec['ts_ms']
fresh=s._slot_permission_view(replace(v,tick=v.tick+10))
assert any(fresh.reserved.packet.slot_permission.allowed)
print('PASS denied malformed read cannot reuse capture; fresh distinct frame recovers eligibility')

# A deliberately noncompliant inner ignores permission. The unchanged guard must STILL count/refuse it.
wrapper=next(n for n in source.body if isinstance(n,ast.ClassDef)and n.name=='_GuardedPlayer')
# Its import resolves to the real lightweight pinned Decision/WAIT definitions.
for name in ('bot','bot.players'):
 m=types.ModuleType(name);m.__path__=[];sys.modules[name]=m
spec=importlib.util.spec_from_file_location('bot.players.base',R/'candidate/bot/players/base.py')
base_module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=base_module;spec.loader.exec_module(base_module)
from bot.players.base import Decision,WAIT
exec(compile(ast.Module(body=[wrapper],type_ignores=[]),'actual-loop-wrapper','exec'),ns)
for row in T:
 s,v=fixture(row);s.guard='enforce';s.hold_reason=None;s.guarded=[];s._refusals=0;s._refusal_since=None
 s.refusal_limit=24;s.hold_ms=6000
 inner=types.SimpleNamespace(act=lambda view:Decision(row['original_action']))
 d=ns['_GuardedPlayer'](inner,s).act(v)
 assert d.action==WAIT and d.stats['tap_guard']==row['reason']
 assert s.tr.stats['tap_guard:'+row['reason']]==1 and s._refusals==1
 assert s.guarded==[(row['poll'],row['original_action'],row['reason'])]
 print('PASS noncompliant policy still reaches counted unchanged final guard',row['n'])
(OUT/'producer-result.json').write_text(json.dumps(dict(rows=results,source_scope='Actual packaged producer/wrapper AST + actual isolated SlotPermission/bind/validate helper; packet/player leaves fixtures, no model/runtime inference or input.'),indent=2)+'\n')
