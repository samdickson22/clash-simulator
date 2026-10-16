"""Final canonical backend160 plus main config protocol/full-pool/root integration.
No actual model, engine, worker process, Runtime, network/capture/input. Real source AST, fake leaves.
"""
from pathlib import Path
import runpy,os,sys,types,json,hashlib,ast,importlib,time
P=Path(__file__).resolve().parents[1];OUT=Path(os.environ['R8_TEST_OUT']);C=P/'candidate'
x=runpy.run_path(str(P/'tests/backend_test.py'));selected=x['selected'];check=x['check'];before=len(x['checks'])
# Main-only config transport implementation is preserved in full, not transplanted from deployed lineage.
def node(tree,name):
 return next(n for n in ast.walk(tree)if isinstance(n,(ast.FunctionDef,ast.ClassDef,ast.Assign))and(getattr(n,'name',None)==name or isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id==name for t in n.targets)))
a=ast.parse((P/'base/bot/search/lopp_fast.py').read_text());b=ast.parse((C/'bot/search/lopp_fast.py').read_text())
for name in ['split_snapshot','_card_names','config_need','ConfigCache','_pool_worker','CONFIG_CACHE','LearnedPool','reduce_fast','_FastMixin']:
 check('main config AST retained '+name,ast.dump(node(a,name))==ast.dump(node(b,name)))
ns=selected(C/'bot/search/lopp_fast.py',['split_snapshot','_card_names','config_need','ConfigCache','LearnedPool','CONFIG_CACHE','_pool_worker'],dict(importlib=importlib,time=time,fatal=lambda ex:isinstance(ex,(KeyboardInterrupt,SystemExit))))
Pool=ns['LearnedPool'];CC=ns['ConfigCache'];worker=ns['_pool_worker']
class Root:
 def __init__(self,cfg):self.cfg=cfg
 def snapshot(self):return json.dumps(dict(players=[dict(hand=['A'],cycle=['B']),dict(hand=['B'],cycle=['A'])],entities=[],config=self.cfg,pending_casts=[]),separators=(',',':'))
def pool():
 p=object.__new__(Pool);p.gen=0;p.config=None;p.base_config={'cards':{},'rate':1};p.base_sent=False;p.shipped={};p.messages=[];p._send_all=p.messages.append
 return p
cfg1={'cards':{'A':{'hp':100},'B':{'hp':200},'unused':{'hp':300}},'rate':.05}
cfg2=json.loads(json.dumps(cfg1));cfg2['cards']['A']['hp']=101
for raw in [True,False]:
 p=pool();r1,r2=Root(cfg1),Root(cfg2)
 for root in[r1,r1,r2,r1]:p.begin(root,0,{},'balanced',None,base_cut=raw)
 configs=[m for m in p.messages if m[0]=='config'];roots=[m for m in p.messages if m[0]=='root']
 check('content change ships twice, same content reuses '+str(raw),len(configs)==2 and len(roots)==4 and roots[0][2][2]==roots[1][2][2]==roots[3][2][2]and roots[2][2][2]!=roots[0][2][2])
 check('content hash raw/cut flag preserved '+str(raw),all(m[3]is raw and m[2].endswith('r'if raw else'c')for m in configs))
 parsed=[]
 class FakeState:
  def __init__(self,payload):parsed.append(json.loads(payload))
 mod=types.ModuleType('r8_fake_native');mod.BattleState=FakeState;sys.modules[mod.__name__]=mod
 Native=type('Native',(),{'__module__':mod.__name__})
 class Conn:
  def __init__(self,msgs):self.msgs=iter(msgs)
  def recv(self):return next(self.msgs,('stop',))
  def send(self,msg):raise AssertionError('no run/native tasks in config probe')
 worker(Conn(p.messages),Native())
 check('worker reconstructs corresponding changed config '+str(raw),[v['config']['cards']['A']['hp']for v in parsed]==[100,100,101,100])
 check('raw config exact; nonraw needed-card cut '+str(raw),all(set(v['config']['cards'])==({'A','B','unused'}if raw else{'A','B'})for v in parsed))
 for i in range(ns['CONFIG_CACHE']+2):
  cfg=json.loads(json.dumps(cfg1));cfg['rate']=i;p.begin(Root(cfg),0,{},'balanced',None,base_cut=raw)
 check('content FIFO bounded '+str(raw),len(p.shipped)==ns['CONFIG_CACHE'])
 # A key evicted from the parent mirror must be shipped again before its next root.
 n=sum(m[0]=='config'for m in p.messages);p.begin(r1,0,{},'balanced',None,base_cut=raw)
 check('evicted config reships before root '+str(raw),sum(m[0]=='config'for m in p.messages)==n+1 and p.messages[-2][0]=='config'and p.messages[-1][0]=='root')
 # Reconstruct entire >16-key stream, so worker FIFO matches parent; no stale missing cache key.
 parsed.clear();worker(Conn(p.messages),Native())
 check('worker FIFO survives eviction/reload '+str(raw),len(parsed)==len([m for m in p.messages if m[0]=='root'])and parsed[-1]['config']['cards']['A']['hp']==100)
# Legacy two-part config protocol remains supported for other pool users; no base_cut keyword.
p=pool();p.begin(Root(cfg1),0,{},'balanced',None)
check('legacy config/root shapes',len(p.messages[0])==2 and len(p.messages[-1][2])==2)
# Actual main MultiSearchPlayer act, under real final metadata/caches/masks with fake scoring.
class SearchBase:pass
mp=selected(C/'bot/search/players.py',['MultiSearchPlayer'],dict(SearchPlayer=SearchBase,Decision=x['Decision'],PublicView=x['PublicView'],MatchContext=x['MatchContext'],SEARCH_INTERVAL=10,WAIT=2304,EXTRA_ROOT_KEY=0x5ea4c4,np=x['np']))
Multi=mp['MultiSearchPlayer'];mp['make_poller']=lambda rt,ctx,name:('poller','cache')
for custom in[False,True]:
 w=x['make_search']();w.__class__=Multi;w._done=types.MethodType(x['search_done'],w);w.seed=3
 calls=[];w.rt.R.root=lambda info,opp,rng:calls.append(('default',info))or('default-root',info)
 w.root_fn=(lambda info,opp,rng:calls.append(('custom',info))or('custom-root',info))if custom else None
 w.p.belief.derived=lambda:{'hand':[1],'cycle':[2]}
 v=x['view']();d=w.act(v)
 check('main root hook/default invoked '+str(custom),len(calls)==1 and calls[0][0]==('custom'if custom else'default')and calls[0][1]is v.info)
 check('main root state identity retained '+str(custom),w.p.core.calls[-1][1][1]is v.info and w.p.core.info is v.info and w.p.core.pending==tuple(v.pending))
 check('root selection still uses current eligibility '+str(custom),d.action<2304 and d.action//576!=1 and all(a==2304 or a//576!=1 for a in w.p.core.calls[-1][2]))
# Actual start dispatch through actual full-pool selection; construction leaves have no runtime/model.
for pkg in['bot.fullpool']:
 m=types.ModuleType(pkg);m.__path__=[];sys.modules[pkg]=m
fp=selected(C/'bot/fullpool/belief.py',['belief_spec','planner_belief'],dict(os=types.SimpleNamespace(environ={}),_CACHE={}))
class BaseBelief:pass
class SelectedBelief(BaseBelief):pass
selection=('selected-prior',SelectedBelief);fp['_CACHE'][('fullpool:fixture',BaseBelief)]=selection
m=types.ModuleType('bot.fullpool.belief');m.planner_belief=fp['planner_belief'];sys.modules[m.__name__]=m
class Planner:
 def __init__(self,R,prior,seed):self.prior=prior;self.belief=BaseBelief()
class CoreLeaf:
 def __init__(self,*a,**kw):self.kw=kw
for module,attrs in [('fair_player',dict(PublicPlanner=Planner)),('delay',dict(DelayAwarePlanner=object)),('belief',dict(Belief=BaseBelief)),('sdefault',dict(planner_class=lambda cls:cls,apply_default=lambda:None))]:
 m=types.ModuleType(module);m.__dict__.update(attrs);sys.modules[module]=m
sys.modules['clasher.rl.c56_rollout_planner']=types.SimpleNamespace(C56SearchConfig=lambda **kw:kw)
mp['planner_class']=lambda cls,rule:CoreLeaf
for spec in['c56','fullpool:fixture']:
 w=object.__new__(Multi);R=types.SimpleNamespace(builder=object(),bots={},native=object(),config={'live':'native'})
 w.rt=types.SimpleNamespace(R=R,PRIOR=object(),CAT=object(),belief_prior=spec);w.samples=16;w.horizon=160;w.budget=None
 ctx=types.SimpleNamespace(seed=5,command_delay=27,opponent_delay=27)
 w.start(ctx)
 check('main fullpool/default selection retained '+spec,(w.p.prior is w.rt.PRIOR and type(w.p.belief)is BaseBelief)if spec=='c56'else(w.p.prior=='selected-prior'and type(w.p.belief)is SelectedBelief))
 check('main start forwards unchanged native config/delay '+spec,w.p.core.kw['native_config']is R.config and w.p.core.kw['command_delay']==27 and w.p.core.kw['catalog']is w.rt.CAT and(w.poller,w.cached)==('poller','cache'))
# Exact main startup and immutable hook declaration match before/after; only act gained eligibility.
a=ast.parse((P/'base/bot/search/players.py').read_text());b=ast.parse((C/'bot/search/players.py').read_text())
check('main Multi.start AST exact',ast.dump(node(a,'start'))==ast.dump(node(b,'start')))
check('main root_fn declaration retained',Multi.root_fn is None)
(OUT/'combined-result.json').write_text(json.dumps(dict(backend_checks=before,additional_checks=len(x['checks'])-before,checks=x['checks'],scope='final canonical source AST; fake model/native/worker/construction leaves; no actual process/engine/search execution'),indent=2)+'\n')
print('PASS',len(x['checks']),'combined source checks')
