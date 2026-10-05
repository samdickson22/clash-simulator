"""Replay a scalar job (base src + patches) and print primitive attributes of selected entities per tick.
usage: trace.py V SJ LO-HI ID[,ID] [--patch p] [--attrs a,b] [--all]"""
import argparse, sys, time, json, os, contextlib, importlib
from pathlib import Path
REPO=Path('/Users/sam/Desktop/code/clasher')
SRC=os.environ.get('DSWEEP_SRC','/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/m0/runtime-snapshots/native-final-v6/src')
sys.path[:0]=[SRC,str(REPO/'scripts'),'/tmp/dsweep']
import run_readiness_v2 as rr
from clasher.rl.readiness_execution import ExecutionPlan, jobs
from clasher.battle import BattleState
ap=argparse.ArgumentParser(); ap.add_argument('v',type=int); ap.add_argument('sj',type=int); ap.add_argument('rng'); ap.add_argument('ids')
ap.add_argument('--patch',action='append',default=[]); ap.add_argument('--attrs',default=None); ap.add_argument('--hook',default=None)
a=ap.parse_args()
for p in a.patch:
    spec=importlib.util.spec_from_file_location('patch_'+Path(p).stem,p); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
lo,hi=map(int,a.rng.split('-')); ids=[int(x) for x in a.ids.split(',')] if a.ids else []
attrs=a.attrs.split(',') if a.attrs else None
prev={}
def prim(v): return isinstance(v,(int,float,str,bool,type(None))) or (isinstance(v,(list,tuple)) and len(v)<8 and all(isinstance(x,(int,float,str,bool,tuple,list)) for x in v))
orig=BattleState.step
def step(self,*args,**kw):
    orig(self,*args,**kw)
    if lo<=self.tick<=hi:
        for i in ids:
            e=self.entities.get(i)
            if e is None: print(self.tick,i,'GONE'); continue
            d={k:(round(v,4) if isinstance(v,float) else v) for k,v in vars(e).items() if prim(v) and (attrs is None or k in attrs)}
            d['pos']=(round(e.position.x,4),round(e.position.y,4))
            if attrs is None:
                ch={k:v for k,v in d.items() if prev.get(i,{}).get(k,'<none>')!=v}
                print(self.tick,i,type(e).__name__,json.dumps(ch,default=str)); prev[i]=d
            else: print(self.tick,i,json.dumps(d,default=str))
        if not ids:
            print(self.tick,[(e.id,type(e).__name__,getattr(getattr(e,'card_stats',None),'name',None),e.player_id,round(e.position.x,3),round(e.position.y,3)) for e in self.entities.values()])
BattleState.step=step
if a.hook:
    exec(open(a.hook).read())
R=REPO/'reports/strategy_council_20260928/m0/readiness'
plan=ExecutionPlan.model_validate_json((R/f'tier-a-fresh-v{a.v}'/'branch-plan.json').read_text())
J=jobs(plan)
out=Path(f'/tmp/dsweep/tr/v{a.v}-{a.sj}-{os.getpid()}'); out.mkdir(parents=True,exist_ok=True)
class Stop(Exception): pass
orig2=BattleState.step
def step2(self,*args,**kw):
    step(self,*args,**kw) if False else None
    orig2(self,*args,**kw)
    if self.tick>hi: raise Stop()
BattleState.step=step2
try:
    with contextlib.ExitStack() as st:
        rr._execute_job_body(plan,J[a.sj],out,argparse.Namespace(deadline=time.monotonic()+36000,port=None),st,[],None)
except Stop: pass
