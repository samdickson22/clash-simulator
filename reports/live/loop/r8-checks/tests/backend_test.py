"""Actual isolated source orchestration; AST-loaded code + fake leaves only.
No torch import, checkpoints, model forward, native/search rollouts, Runtime,
network, capture, helpers, host commands or original future trajectory replay.
"""
import ast
import os
from contextlib import nullcontext
import copy
from dataclasses import dataclass, replace, field
from collections import Counter
from collections.abc import Mapping
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import types
import numpy as np

P=Path(__file__).resolve().parents[1]
OUT=Path(os.environ['R8_TEST_OUT'])
C=P/'candidate'
checks=[]
def check(name,condition):
    assert condition,name
    checks.append(name)
def pkg(name):
    m=types.ModuleType(name);m.__path__=[];sys.modules[name]=m;return m
for name in ['clasher','clasher.rl','imitation','imitation.evaluation','imitation.model','bot','bot.players','bot.live','bot.search']:
    pkg(name)
def module(name,ns):
    m=types.ModuleType(name);m.__dict__.update(ns);sys.modules[name]=m;return m
spec=importlib.util.spec_from_file_location('clasher.rl.slot_permission',C/'src/clasher/rl/slot_permission.py')
sp=importlib.util.module_from_spec(spec);sys.modules[spec.name]=sp;spec.loader.exec_module(sp)
SlotPermission=sp.SlotPermission

def selected(path,names,ns=None):
    """Execute exact functions/classes without runtime-owned imports/top-level effects."""
    source=path.read_text();tree=ast.parse(source)
    nodes=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef,ast.Assign)) and
           ((getattr(n,'name',None) in names) or isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in names for t in n.targets))]
    class StripTorch(ast.NodeTransformer):
        def visit_FunctionDef(self,n):
            n.decorator_list=[d for d in n.decorator_list if 'torch.' not in ast.unparse(d)]
            return self.generic_visit(n)
    tree=ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0)]+nodes,type_ignores=[])
    tree=StripTorch().visit(tree);ast.fix_missing_locations(tree)
    scope={'np':np,'dataclass':dataclass,'replace':replace,'field':field,'math':math,'copy':copy,'Mapping':Mapping,'WAIT':2304}
    scope.update(ns or {})
    name='offline_'+str(len(sys.modules))+'_'+path.stem
    scope['__name__']=name
    scope['__package__']='clasher.rl' if path.parent.name=='rl' else ''
    owner=types.ModuleType(name);owner.__dict__.update(scope);sys.modules[name]=owner;scope=owner.__dict__
    exec(compile(tree,str(path),'exec'),scope)
    return scope

# Literal original numeric feature builder; no torch dependency or execution.
feature_path=C/'imitation/model/features.py'
fs=selected(feature_path,['get','build_row','GLOBAL_COLUMNS','ENTITY_COLUMNS','BUCKETS'])
build_row=fs['build_row']
@dataclass(frozen=True)
class Info:
    packet:object
    own:object
    tick:int=90
    seat:int=0
    events:object=None
base=selected(C/'bot/players/base.py',['PublicView','Decision','MatchContext'])
PublicView,Decision,MatchContext=(base[k] for k in ['PublicView','Decision','MatchContext'])
obsclass=selected(C/'src/clasher/rl/public_observation.py',['ConfidenceAwareActorObservation'],{'PUBLIC_OBSERVATION_SCHEMA_VERSION':4})['ConfidenceAwareActorObservation']
module('clasher.rl.public_observation',dict(SlotPermission=SlotPermission,ConfidenceAwareActorObservation=obsclass))
maskns=selected(C/'src/clasher/rl/public_action_mask.py',['PublicActionMaskInput','PublicActionMaskBuilder'],dict(
    NUM_HAND_SLOTS=4,NUM_TILES=576,BOARD_WIDTH=18,BOARD_HEIGHT=32,SPELL_REGISTRY={},MirrorSpell=type('MirrorSpell',(),{}),
    resolve_card_name=lambda n,d:n))
Input=maskns['PublicActionMaskInput'];Mask=maskns['PublicActionMaskBuilder']
module('clasher.rl.public_action_mask',dict(PublicActionMaskInput=Input))
contracts=selected(C/'src/clasher/rl/contract_v5.py',['ContractV5ActionMaskBuilder','CachedContractV5ActionMask'],dict(
    PublicActionMaskBuilder=Mask,PublicActionMaskInput=Input,NUM_HAND_SLOTS=4))
V5=contracts['ContractV5ActionMaskBuilder']
loader=types.SimpleNamespace(get_card=lambda n:types.SimpleNamespace(mana_cost=3,card_type='troop',collision_radius=.5),load_card_definitions=lambda:{})
builder=types.SimpleNamespace(loader=loader,token_names=['PAD']+[f'C{i}' for i in range(1,20)],card_name_for_token_id=lambda i:f'C{i}')
def mask_builder():
    m=object.__new__(V5);m.builder=builder;m.mask_version=1;m.no_op_action=2304;m.ability_action=2305;m.num_actions=2306
    m._placement_v2=None;m._non_blocked=np.ones(576,bool);m._deploy_zone=lambda o:np.ones(576,bool)
    m._building_blockers=lambda *a,**kw:[];m._placement_occupied=lambda *a,**kw:False;m.ability_legal=lambda o:False
    return m
module('clasher.rl.contract_v5',dict(ContractV5ActionMaskBuilder=lambda b:mask_builder(),champion_button_flags=lambda c:False))

def source(permission=None,mode='legacy',capture='frame-90',tick=90):
    o=types.SimpleNamespace(hand_ids=np.array([1,2,3,4,5],np.int64),hand_levels=np.ones(5,np.int64)*11,
      global_features=np.array([0]*5+[1]+[0]*12,np.float32),entity_ids=np.zeros(0,np.int64),entity_features=np.zeros((0,32),np.float32),
      entity_mask=np.zeros(0,bool),entity_levels=np.zeros(0,np.int64),opponent_seen_card_ids=np.zeros(8,np.int64),
      own_last_play=None,terminal=False,board_rotated=False)
    return obsclass(o,np.zeros(0,np.float32),np.zeros((0,32),np.float32),np.ones(5,np.float32),np.ones(18,np.float32),
        np.zeros(8,np.float32),np.zeros(8,np.float32),slot_permission=permission,slot_permission_capture_id=capture,
        slot_permission_poll_tick=tick,slot_permission_mode=mode)

def side(allowed=(True,False,True,True),tick=90,capture='frame-90'):
    return SlotPermission(allowed,capture,tick,tuple('verified' if a else 'mismatch' for a in allowed))

def request(s):return Input.from_confidence_observation(s)
m=mask_builder();native=m.build(request(source()))
check('native all four slots usable',native[:2304].all() and native[2304] and not native[2305])
for mode in ['legacy','required']:
 for allowed in [(True,True,True,True),(False,)*4,(True,False,True,False),(False,True,False,True)]:
    s=source(side(allowed),mode);out=m.build(request(s))
    check(f'{mode} mask {allowed}',[out[i*576:(i+1)*576].any() for i in range(4)]==list(allowed) and not (out & ~native).any())
check('legacy None mask exactly original',np.array_equal(m.build(request(source())),native))
invalid=[('missing',None),('dict',{}),('wrong_length',replace(side(),allowed=(True,))),('ints',replace(side(),allowed=(1,False,True,True))),
 ('list',replace(side(),allowed=[True]*4)),('reasons',replace(side(),reasons=('x',)*3)),('blank_reason',replace(side(),reasons=('',)*4)),
 ('bool_tick',replace(side(),poll_tick=True)),('stale_tick',replace(side(),poll_tick=85)),('stale_frame',replace(side(),capture_id='old'))]
for name,p in invalid:
 s=source(p,'required');out=m.build(request(s));check('required invalid '+name,not out[:2304].any() and out[2304] and not out[2305])
for s in [source(side(),'invalid'),source(side(),'required',capture=None),source(side(),'required',tick=None)]:
 check('bad current binding',not m.build(request(s))[:2304].any())
class Explosive:
 @property
 def slot_permission(self):raise RuntimeError('metadata access error')
check('metadata exception failclosed',sp.permission_state(Explosive())[0]==(False,)*4)
# actual cache method must bypass an identical legacy cached key under every permission change.
cached=object.__new__(contracts['CachedContractV5ActionMask']);cached.inner=m
for a in [(True,False,False,False),(False,True,False,False)]:
 check('cache sidecar cannot reuse previous mask',np.array_equal(cached.build(source(side(a),'required')),m.build(request(source(side(a),'required')))))

mpns=selected(C/'imitation/evaluation/d1.py',['model_packet'])
model_packet=mpns['model_packet'];module('imitation.evaluation.d1',dict(model_packet=model_packet))
d1=dict(own_deck=np.arange(1,9),own_queue=np.array([5,6,7,8]),opp_hand_known=np.zeros(4),opp_next_card=0,opp_queue=np.zeros(4),
    opp_history=[],own_history=[],opp_abilities=[],opp_elixir=6.,opp_refill_remaining=0.,own_refill_remaining=0.,opp_cards_revealed=0,elixir_exact=True)
costs=np.ones(360,np.float32)*3
s=source();original=model_packet(s,native);restricted=model_packet(s,native,eligibility_mask=m.build(request(source(side(),'required'))))
a,b=build_row(original,d1,costs),build_row(restricted,d1,costs)
check('every actual model feature byte equal',all(a[k].dtype==b[k].dtype and a[k].tobytes()==b[k].tobytes() for k in a))
wrong=build_row(model_packet(s,restricted['eligibility_mask']),d1,costs)
check('negative control single-mask changes numeric',a['numeric'].tobytes()!=wrong['numeric'].tobytes())
check('model packet array identities unchanged',all(original[k] is restricted[k] for k in original))

# Minimal numerical tensor fake; NO torch or model code is imported or executed.
class T:
 def __init__(self,a):self.a=np.asarray(a)
 def __getitem__(self,k):return T(self.a[k])
 def __int__(self):return int(self.a.reshape(-1)[0])
 def __float__(self):return float(self.a)
 def __add__(self,o):return T(self.a+(o.a if isinstance(o,T) else o))
 def __invert__(self):return T(~self.a)
 def sum(self):return T(self.a.sum())
 def exp(self):return T(np.exp(self.a))
 def numpy(self):return self.a.copy()
 def tolist(self):return self.a.tolist()
 def flatten(self,start=0):return T(self.a.reshape(self.a.shape[:start]+(-1,)))
 def masked_fill(self,mask,value):return T(np.where(mask.a,value,self.a))
 def any(self,dim=-1):return T(self.a.any(dim))
 def fill_(self,v):self.a.fill(v)
class Generator:
 def __init__(self,**kw):pass
 def manual_seed(self,v):return self
class TorchFake:
 inf=np.inf;long='long';Generator=Generator
 @staticmethod
 def multinomial(a,n,generator=None):
    x=a.a;assert np.isfinite(x).all() and x.sum()>0;return T(np.array([int(np.argmax(x))]))
 @staticmethod
 def from_numpy(a):return T(a)
 @staticmethod
 def topk(a,k):
    ids=np.argsort(-a.a,kind='stable')[:k];return T(a.a[ids]),T(ids)
 @staticmethod
 def inference_mode():return nullcontext()
 @staticmethod
 def empty(*a,**kw):return T([])
torch=TorchFake()
fake_torch_module=module('torch',{k:getattr(torch,k) for k in dir(torch) if not k.startswith('__')})
def sf(packet,row,c):return {k:T(v[None]) for k,v in build_row(packet,row,c).items()}
rank=selected(C/'reports/explore/s1/proposals.py',['rank_actions'])['rank_actions']
class Leaf:
 def __init__(self):self.temperatures=T([1.,1.,1.]);self.inputs=[];self.gate=.9
 def log_policy(self,b):
    self.inputs.append({k:v.a.copy() for k,v in b.items()})
    cards=np.array([0.,6.,3.,2.]);tiles=np.tile(np.linspace(1,0,576),(4,1))
    return dict(gate=T(np.log([[.05,.9,.05]])),card=T(cards[None]),tile=T(tiles[None]))
def outputs(model,b):
 model.inputs.append({k:v.a.copy() for k,v in b.items()});r=np.arange(2304,dtype=float)*-.001;r[576]=100;r[1152]=99
 return T([model.gate]),T(r[None])
cpns=selected(C/'reports/explore/s1/cached_policy.py',['CachedPolicy'],dict(torch=torch,single_features=sf,outputs=outputs,rank_actions=rank,eligibility_mask=sp.eligibility_mask))
Cached=cpns['CachedPolicy'];module('cached_policy',dict(CachedPolicy=Cached))
infer=selected(C/'imitation/model/inference.py',['Policy'],dict(torch=torch,single_features=sf))
# Call actual Policy methods without constructor; fake leaf substitutes only model.
generic=object.__new__(infer['Policy']);generic.model=Leaf();generic.costs=costs
check('generic stochastic sample allowed other slot',generic.sample(restricted,d1)//576!=1)
check('generic proposals filtered before topk',all(p['slot']!=1 for p in generic.propose(restricted,d1,16)))
for threshold in [.5,None]:
 leaf=Leaf();policy=Cached(types.SimpleNamespace(model=leaf,costs=costs),threshold)
 action=policy.sample(restricted,d1)
 check('cached sample allowed '+str(threshold),action<2304 and action//576!=1)
 proposals=policy.propose(restricted,d1)
 check('cached topk permission '+str(threshold),all(p['slot']!=1 for p in proposals))
 check('cached raw input features unchanged '+str(threshold),all(np.array_equal(leaf.inputs[-1][k][0],a[k]) for k in a))
 try:policy.propose(dict(restricted,eligibility_mask=native),d1)
 except AssertionError:checks.append('cached reuse rejects changed eligibility '+str(threshold))
 else:raise AssertionError('stale cache accepted')
 allmask=native.copy();allmask[:2304]=False
 allpacket=model_packet(s,native,eligibility_mask=allmask)
 check('all denied cached WAIT '+str(threshold),policy.sample(allpacket,d1)==2304 and policy.propose(allpacket,d1)==[])
# Exact legacy source CachedPolicy vs candidate with same fake outputs, no metadata.
oldcp=selected(P/'base/reports/explore/s1/cached_policy.py',['CachedPolicy'],dict(torch=torch,single_features=sf,outputs=outputs,rank_actions=rank_actions if 'rank_actions' in globals() else rank))['CachedPolicy']
for th in [.5,None]:
 p1=oldcp(types.SimpleNamespace(model=Leaf(),costs=costs),th);p2=Cached(types.SimpleNamespace(model=Leaf(),costs=costs),th)
 check('legacy cached choice/proposals exact '+str(th),p1.sample(original,d1)==p2.sample(original,d1) and p1.propose(original,d1)==p2.propose(original,d1))

# Actual Standalone -> V1 -> Student -> LivePlayer path, fake model leaf and D1 leaf.
class D1Fake:
 def __init__(self,*a):self.calls=[]
 def update(self,t,ev):self.calls.append((t,ev));return d1
sys.modules['imitation.evaluation.d1'].D1Tracker=D1Fake
standns=selected(C/'imitation/evaluation/standalone.py',['StandalonePlayer'],dict(torch=torch,D1Tracker=D1Fake,
    ContractV5ActionMaskBuilder=lambda b:mask_builder(),PublicActionMaskInput=Input,model_packet=model_packet))
Standalone=standns['StandalonePlayer'];module('imitation.evaluation.standalone',dict(StandalonePlayer=Standalone))
V1=selected(P/'base/reports/explore/e1/policy.py',['V1Policy'],dict(StandalonePlayer=Standalone))['V1Policy']
module('policy',dict(V1Policy=V1))
module('bot.players.base',dict(Decision=Decision,PublicView=PublicView,MatchContext=MatchContext,WAIT=2304,SEARCH_INTERVAL=10))
def new_base_policy():return types.SimpleNamespace(model=Leaf(),costs=costs)
student=selected(C/'bot/exit/student.py',['StudentPlayer'],dict(Path=Path,POLICY_SEED_OFFSET=271828,Decision=Decision,WAIT=2304,
    load_policy=lambda *a:new_base_policy(),parse_spec=lambda x:('fake.pt',.5)))['StudentPlayer']
class Clock:
 t=0.
 def monotonic(self):return self.t
 def process_time(self):return self.t
clock=Clock()
def search_done(self,action,stats,wall0,wait_ticks=0):return Decision(int(action) if action<2304 else 2304,wait_ticks,dict(stats,wall_seconds=clock.t-wall0))
class MultiBase:
 def act(self,view):raise AssertionError('unbounded route not in deployed wall path')
class CandidateBase(MultiBase):pass
live_ns=selected(C/'bot/live/player.py',['_WallMulti','LivePlayer','_reraise_control','_is_panic','_search_failure_counts','search_stats','SEARCH_KEYS','RENAMED','FAILURE_MARKS','make_live_player','parse_wall_name'],dict(
    MultiSearchPlayer=MultiBase,time=clock,Decision=Decision,PublicView=PublicView,MatchContext=MatchContext,SEARCH_INTERVAL=10,WAIT=2304,
    RETURN_RESERVE=.008,FAST_DEFAULT='fake.pt',Counter=Counter,load_fast=lambda rt,spec:student(rt,'fake.pt',.5),
    _HEADLINE_MAKE_PLAYER=lambda rt,n:('legacy-other',n)))
Wall=live_ns['_WallMulti'];Live=live_ns['LivePlayer']
module('bot.live.player',dict(LivePlayer=Live,live_belief_class=lambda:None))
module('imitation.model.inference',dict(single_features=sf));module('proposals',dict(outputs=outputs,rank_actions=rank))
class Belief:
 update_error=False;sample_error=False
 def update(self,*a,**kw):
    if self.update_error:raise TimeoutError('fake belief cutoff')
 def sample(self,*a,**kw):
    if self.sample_error:raise TimeoutError('fake sample cutoff')
    return object()
class Script:
 def __init__(self):self.mask_builder=mask_builder()
 def _ranked_actions(self,p,all_plays=False):return [types.SimpleNamespace(action_id=i) for i in [576,1152,0]]
 def decide(self,p):return types.SimpleNamespace(action_id=576)
corefn=selected(C/'src/clasher/rl/c56_rollout_planner.py',['C56RolloutPlanner'],dict(
    C56SearchConfig=lambda:None,PublicActionMaskInput=Input))['C56RolloutPlanner'].candidates
class Core:
 def __init__(self):
    self.bots={'balanced':Script()};self.config=types.SimpleNamespace(samples=3,script_top=3,wait_screen8=False)
    self.rng=np.random.default_rng(19);self.selected_wait_ticks=0;self.deadline_stats={};self.calls=[];self.hook=None
 def candidates(self,packet,extra):
    out,mask=corefn(self,packet,extra)
    self.calls.append(('candidates',packet,tuple(out),mask.copy()))
    if self.hook=='candidates_cutoff':clock.t+=1
    return out,mask
 def score_candidates(self,root,seat,candidates,**kw):
    self.calls.append(('score',root,tuple(candidates),kw))
    if self.hook=='exception':raise RuntimeError('fake scoring exception')
    if self.hook=='panic':raise type('PanicException',(BaseException,),{})('fake native panic')
    self.deadline_stats=dict(hit=self.hook=='native_failure',fallback=self.hook=='native_failure',completed=0)
    if self.hook=='native_failure':self.deadline_stats['native_failure']='fake';return kw['fallback']
    if self.hook=='bad_native_return':return 576
    return next((a for a in candidates if a<2304),2304)

def make_search():
 w=object.__new__(Wall);w.name='fake';w.threads=4;w.deadline_seconds=.2;w.wall_ms=200;w.root_fn=lambda i,o,r:('root',i)
 w.poller=V1(Cached(new_base_policy(),.5),builder,costs,0,list(range(8)),1);w.cached=w.poller.player.policy
 w.rt=types.SimpleNamespace(R=types.SimpleNamespace(costs=costs));w.student_candidates=True;w.student_last=True;w.student_refine=True
 w.p=types.SimpleNamespace(core=Core(),belief=Belief(),rng=np.random.default_rng(1));w._done=types.MethodType(search_done,w)
 w.roots=1;w.start=lambda ctx:None;w.close=lambda:None
 return w
live_ns['WallCandidatePlayer']=lambda *a,**kw:make_search()
live_ns['root_state_breaks']=lambda info,opp:{}
ctx=MatchContext(0,1,tuple(range(8)))
rt=types.SimpleNamespace(R=types.SimpleNamespace(builder=builder,costs=costs),PRIOR={})
def player(mode='required',tier='search',dflt='it5s2'):
 p=Live(rt,tier=tier,slot_permission_mode=mode,cutoff_default=dflt)
 # Avoid start()'s real belief class assignment, but execute actual Student.start.
 p.ctx=ctx;p.errors=0;p.search_disabled=False;p.panics=0;p.native_failures=Counter();p.fast.start(ctx)
 return p
own=dict(hand=['C1','C2','C3','C4'],cycle=['C5','C6','C7','C8'],elixir=10)
events=[];pending=()
def view(t=90,allowed=(True,False,True,True),mode='required',permission=True,can_act=True):
 cap='frame-'+str(t);pkt=source(side(allowed,t,cap) if permission else None,mode,capture=cap,tick=t)
 info=Info(pkt,own,tick=t,events=events)
 return PublicView(t,0,info,info,events,pending,can_act)
for tier in ['fast','search']:
 for dflt in ['it5s2','R3a']:
  p=player(tier=tier,dflt=dflt);v=view();snapshot=copy.deepcopy(v)
  d=p.act(v)
  check(f'actual facade other slot {tier}/{dflt}',d.action<2304 and d.action//576!=1)
  check(f'authoritative source object unchanged {tier}/{dflt}',v.info is v.reserved and v.info.own is own and v.pending is pending and
      v.public_events is events and v.reserved.packet.slot_permission_poll_tick==90 and
      np.array_equal(v.reserved.packet.observation.hand_ids,snapshot.reserved.packet.observation.hand_ids))
  if tier=='search':
   score=[c for c in p.search.p.core.calls if c[0]=='score'][0]
   check('root is original info',score[1][1] is v.info)
   check('native receives permitted candidates and fallback',all(a==2304 or a//576!=1 for a in score[2]) and score[3]['fallback']//576!=1)
   check('refinement/student-last/coarse hints restricted',all(a//576!=1 for a in p.search.p.core.refine_proposals) and all(a//576!=1 for a in p.search.p.core.coarse_order))
for allowed in [(False,)*4,(True,False,True,True)]:
 p=player()
 for t in [90,95,100]:
  d=p.act(view(t,allowed,can_act=t!=95))
  check('cadence all/partial at '+str((t,allowed)),d.action==2304 if (not any(allowed) or t==95) else d.action//576!=1)
 check('both actual pollers advance every five', [c[0] for c in p.fast.poller.player.d1.calls]==[90,95,100] and [c[0] for c in p.search.poller.player.d1.calls]==[90,95,100])
 if not any(allowed):check('all denied runs no scoring or candidates',p.search.p.core.calls==[])
# Session mode cannot downgrade when current metadata disappears or producer says legacy.
p=player();p.act(view(90));v=view(95,mode='legacy',permission=False);d=p.act(v)
check('required session stays denied after metadata loss',d.action==2304 and d.stats['slot_permission']['status']=='missing')
try:p.slot_permission_mode='legacy'
except AttributeError:checks.append('pinned mode has no setter')
else:raise AssertionError('mutable session mode')
for kind in ['belief','sample','candidates_cutoff','native_failure','exception','panic','bad_native_return','disabled','fast_error']:
 for default in ['it5s2','R3a']:
  p=player(dflt=default)
  if kind=='belief':p.search.p.belief.update_error=True
  elif kind=='sample':p.search.p.belief.sample_error=True
  elif kind=='disabled':p.search_disabled=True
  elif kind=='fast_error':
   original_fast=p.fast.act
   def badfast(v,old=original_fast):old(v);raise RuntimeError('fake fast failure')
   p.fast.act=badfast
  else:p.search.p.core.hook=kind
  clock.t=0;d=p.act(view())
  check('actual fallback '+kind+'/'+default,d.action==2304 or d.action//576!=1)
# Legacy facade equivalence: output and model-feature bytes against original facade class.
oldlive=selected(P/'base/bot/live/player.py',['LivePlayer','_reraise_control','_is_panic','_search_failure_counts','search_stats','SEARCH_KEYS','RENAMED','FAILURE_MARKS'],dict(
    time=clock,Decision=Decision,WAIT=2304,SEARCH_INTERVAL=10,FAST_DEFAULT='fake.pt',Counter=Counter,
    load_fast=lambda rt,spec:student(rt,'fake.pt',.5),WallCandidatePlayer=lambda *a,**kw:make_search()))['LivePlayer']
p1=oldlive(rt,tier='fast');p1.fast.start(ctx);p2=player('legacy',tier='fast');v=view(mode='legacy',permission=False)
check('legacy actual facade action identical',p1.act(v).action==p2.act(v).action)
check('legacy original view identity preserved',sp.bind_view(v,'legacy') is v)

# Actual LIVE-K4L factory functions, fake construction/search leaves only.
fakesearch=types.SimpleNamespace(deadline_seconds=.2,threads=4)
module('bot.search.lopp',dict(make_lopp_player=lambda rt,n:fakesearch))
loppns=selected(C/'bot/search/lopp_fast.py',['make_live_lopp'])
module('bot.search.lopp_fast',dict(make_live_lopp=loppns['make_live_lopp']))
for name in ['LIVE-fast-it5s2','LIVE-K4CW-r16-w200-t4','LIVE-K4L-R-gs-rw-fc-w200-t4-p4','LIVE-K4L-R-gs-rw-fc-w200-t4-p4-dR3a']:
 p=live_ns['make_live_player'](rt,name,slot_permission_mode='required')
 check('factory required '+name,p.slot_permission_mode=='required')
check('factory LL0 legacy',live_ns['make_live_player'](rt,'LIVE-K4L-R-gs-rw-fc-w200-t4-p4').slot_permission_mode=='legacy')
for name in ['K4CW-r16','PERC-emp:LIVE-fast-it5s2','OTHER']:
 try:live_ns['make_live_player'](rt,name,slot_permission_mode='required')
 except ValueError:checks.append('unsupported required factory rejects '+name)
 else:raise AssertionError('unsupported factory accepted')
# Actual r16 proposal wrapper and rank helper, not merely a copied top-k loop.
class CandidateParent:
 def start(self,ctx):pass
candidate_ns=selected(C/'bot/search/candidates.py',['CandidateSearchPlayer','ranked'],dict(
    MultiSearchPlayer=CandidateParent,Path=Path))
Cand=candidate_ns['CandidateSearchPlayer']
for active in [False,True]:
 w=make_search();c=object.__new__(Cand);c.__dict__.update(w.__dict__)
 del c.__dict__['start']
 c.r3a=16;c.second=0;c.second_path=None;c._info={}
 c.rt=types.SimpleNamespace(R=w.rt.R,STUDENT=new_base_policy())
 c._done=types.MethodType(search_done,c)
 c.start(ctx)
 v=view(mode='required' if active else 'legacy',permission=active)
 clock.t=0;d=Wall.act(c,v)
 check('actual r16 candidate wrapper '+str(active),len(c._info.get('first',()))==16 and
      (not active or all(a//576!=1 for a in c._info['first'])))
# Actual default all-denied/stale paths through both real adapters.
for name,p in invalid:
 w=player();v=view();v=replace(v,reserved=replace(v.reserved,packet=replace(v.reserved.packet,slot_permission=p)))
 d=w.act(v)
 check('facade failclosed '+name,d.action==2304 and d.stats['slot_permission']['status']!='current')
 check('facade invalid cadence '+name,len(w.fast.poller.player.d1.calls)==1 and len(w.search.poller.player.d1.calls)==1 and not w.search.p.core.calls)
for mode in [None,1,True,[],np.array(['legacy','required'])]:
 w=player();v=view();v=replace(v,reserved=replace(v.reserved,packet=replace(v.reserved.packet,slot_permission_mode=mode)))
 d=w.act(v);check('malformed packet mode fails closed '+str(type(mode)),d.action==2304 and d.stats['slot_permission']['status']!='current')
# Feature/gate/ranking identity for the actual fast/R3a adapters under changed permissions.
w1=player();w2=player();w1.act(view(allowed=(True,)*4));w2.act(view())
for label,p1,p2 in [('fast',w1.fast.cached,w2.fast.cached),('R3a',w1.search.cached,w2.search.cached)]:
 i1=p1.model.inputs[-1];i2=p2.model.inputs[-1]
 check('actual '+label+' model feature bytes exact',all(i1[k].dtype==i2[k].dtype and i1[k].tobytes()==i2[k].tobytes() for k in i1))
 check('actual '+label+' native original action retained',p1.original_action==p2.original_action==576)
check('original native selection logged separately',w2.decisions[-1]['slot_permission']['native_fast_action']==576)
# Original PublicActionMaskBuilder.build is an independent legacy negative control.
oldmask=selected(P/'base/src/clasher/rl/public_action_mask.py',['PublicActionMaskInput','PublicActionMaskBuilder'],dict(
    NUM_HAND_SLOTS=4,NUM_TILES=576,BOARD_WIDTH=18,BOARD_HEIGHT=32,SPELL_REGISTRY={},MirrorSpell=type('MirrorSpell',(),{}),
    resolve_card_name=lambda n,d:n))
oldbuild=oldmask['PublicActionMaskBuilder'].build
for elixir in [0.,.29,.3,1.]:
 for terminal in [None,False,True]:
  s=source();s.observation.global_features[5]=elixir;s.observation.terminal=terminal
  r=request(s)
  check('original native mask legacy parity '+str((elixir,terminal)),np.array_equal(oldbuild(m,r),Mask.build(m,r)))
# Binding only metadata: all original confidence/feature arrays and physical state retain object identity.
v=view();bound=sp.bind_view(v,'required')
for key in ['observation','entity_id_confidence','entity_feature_confidence','hand_id_confidence','global_feature_confidence',
            'opponent_history_confidence','opponent_seen_card_confidence']:
 check('bound packet retains '+key,getattr(bound.reserved.packet,key) is getattr(v.reserved.packet,key))
check('binding retains authoritative info/own/ledger/events',bound.info is v.info and bound.reserved.own is v.reserved.own and bound.pending is v.pending and bound.public_events is v.public_events)
# Fake-leaf score must never mutate/mask simulated future root hand state.
check('root hand retains denied card',own['hand'][1]=='C2')
# Backend current tick is authoritative even when producer incorrectly repeats sidecar tick.
w=player();v=view(100);q=replace(v.reserved.packet,slot_permission=side(tick=95,capture='frame-100'),slot_permission_poll_tick=95)
v=replace(v,reserved=replace(v.reserved,packet=q));d=w.act(v)
check('backend tick cannot be copied from stale sidecar',d.action==2304 and d.stats['slot_permission']['status']=='stale')
w=player();v=view();q=replace(v.reserved.packet,slot_permission_capture_id='independent-other-frame')
v=replace(v,reserved=replace(v.reserved,packet=q));d=w.act(v)
check('expected capture independent of sidecar',d.action==2304 and d.stats['slot_permission']['status']=='stale')
class ExplosivePacket:
 def __init__(self,source):self.source=source
 @property
 def slot_permission(self):raise RuntimeError('injected metadata failure')
 def __getattr__(self,key):return getattr(self.source,key)
ps=Standalone(Cached(new_base_policy(),.5),builder,costs,0,list(range(8)),1)
action,_=ps.decide(90,ExplosivePacket(source()),events)
check('actual standalone metadata exception fails closed',action==2304 and ps.last_permission_status['status']=='metadata_exception')
check('metadata exception still advances actual D1',ps.d1.calls==[(90,events)])
# Off-cadence/missing metadata remains visible without skipping either poller.
w=player();w.act(view(90));d=w.act(view(95,permission=False,can_act=False))
check('catch-up required loss visible WAIT',d.action==2304 and d.stats['slot_permission']['status']=='missing')
check('catch-up loss advances both five-tick pollers',[c[0] for c in w.fast.poller.player.d1.calls]==[90,95] and [c[0] for c in w.search.poller.player.d1.calls]==[90,95])
# A newly chosen action ends the fake trace; no historical input is replayed after it.
# Slot permission is not an extra ability grant/denial: preserve native valid ability;
# malformed required metadata independently denies it. Actual LIVE facade always disables ability.
a_builder=mask_builder();a_builder.ability_legal=lambda o:True
check('valid sidecar preserves native ability legality',bool(a_builder.build(request(source(side(),'required')))[2305]))
check('required failure disallows ability',not a_builder.build(request(source(None,'required')))[2305])
# Failed native return is recorded before the built-in eligibility safeguard.
w=player();w.search.p.core.hook='bad_native_return';d=w.act(view())
check('native denied return diagnostic retained',d.action==2304 and d.stats['permission_proposed_action']==576 and d.stats['permission_final_action']==2304)
# Disabled search retains the old fast-only behavior; never label its old cached choice as current.
w=player();w.act(view(90));w.search_disabled=True;d=w.act(view(100))
check('disabled stale default choice not misreported','native_default_action' not in d.stats['slot_permission'])
# Syntax-check whole candidate source files without importing them or generating pyc.
for path in C.rglob('*.py'):compile(path.read_text(),str(path),'exec')
check('no model/torch/runtime import executed',sys.modules.get('torch') is fake_torch_module and 'clasher_core' not in sys.modules)
(OUT/'backend-result.json').write_text(json.dumps(dict(passed=len(checks),checks=checks,scope='AST-extracted actual source with fake leaves; no model/search/runtime execution',
    feature_source=str(feature_path),feature_sha256=hashlib.sha256(feature_path.read_bytes()).hexdigest()),indent=2)+'\n')
print('PASS',len(checks),'checks; fake torch module only, no model/native/search execution')
