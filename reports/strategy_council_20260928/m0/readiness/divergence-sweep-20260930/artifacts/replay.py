"""Scalar replay (current main src) of a Tier A job with dumps at native frame ticks. Read-only on artifacts."""
import argparse, gzip, json, sys, time, shutil, importlib, math, os, contextlib, glob
from pathlib import Path
REPO=Path('/Users/sam/Desktop/code/clasher')
SRC=os.environ.get('DSWEEP_SRC','/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/m0/runtime-snapshots/native-final-v6/src')
sys.path[:0]=[SRC,str(REPO/'scripts'),'/tmp/dsweep']
import run_readiness_v2 as rr
from clasher.rl.readiness_execution import ExecutionPlan, jobs
from clasher.battle import BattleState
import clasher.entities as _ce; assert os.path.realpath(_ce.__file__).startswith(os.path.realpath(SRC)), _ce.__file__
from compare import native_bodies, scalar_bodies, match
R=REPO/'reports/strategy_council_20260928/m0/readiness'
SP={'IceSpirits','ElectroSpirit','FireSpirit','HealSpirit'}
def snap_entities(b):
    out=[]
    for e in b.entities.values():
        cs=getattr(e,'card_stats',None)
        rec={'id':e.id,'o':e.player_id,'n':getattr(cs,'name',type(e).__name__),'k':type(e).__name__,'x':round(e.position.x,4),'y':round(e.position.y,4),
             'hp':round(float(getattr(e,'hitpoints',0) or 0),2),'t':getattr(e,'target_id',None),'alive':getattr(e,'is_alive',True)}
        if DETAIL:
            for k in ('_movement_target_id','_native_navigation_target_id','attack_cooldown','stun_timer','_native_avoidance','_facing_x_units','_facing_y_units','deploy_delay_remaining','spawn_stagger_remaining','_native_natural_movement_active','_attack_finish_elapsed_ms','_attack_windup_elapsed_ms','load_time_remaining','first_hit_remaining','activation_delay_remaining','lifetime_remaining','_freeze_target_pause_remaining'):
                v=getattr(e,k,None)
                if v is not None and not callable(v): rec[k]=round(v,4) if isinstance(v,float) else v
            rc=getattr(e,'_native_ground_route_cells',None)
            if rc: rec['route']=[list(c) for c in list(rc)[:4]]
            kt=getattr(e,'_knockback_target',None)
            if kt is not None: rec['kb']=str(kt)
            try: rec['stunned']=bool(e.is_stunned())
            except Exception: pass
            bl=getattr(e,'active_buffs',None) or getattr(e,'buffs',None)
            if bl:
                try: rec['buffs']=[getattr(b,'name',str(b)) for b in (bl.values() if isinstance(bl,dict) else bl)]
                except Exception: pass
        out.append(rec)
    return out
DETAIL=False
def native_cache(v,rj,rdir):
    p=f'/tmp/dsweep/ncache/v{v}-{rj:05d}.json.gz'
    if os.path.exists(p): return {int(k):x for k,x in json.load(gzip.open(p)).items()}
    N={}
    for j in map(json.loads,gzip.open(rdir+'/decisions.jsonl.gz')):
        N[j['tick']]=dict(actions=j['actions'],bodies=native_bodies(j['native_frame']))
    os.makedirs('/tmp/dsweep/ncache',exist_ok=True)
    with gzip.open(p+'.tmp','wt') as f: json.dump(N,f)
    os.replace(p+'.tmp',p)
    return N
def compare_run(v,rj,rdir, dumps, sdec):
    N=native_cache(v,rj,rdir)
    ok=0;tot=0;first=None;fd=None
    for t in sorted(N):
        if t not in dumps: continue
        tot+=1
        pairs,uS,uN=match(scalar_bodies({'ents':dumps[t]}),N[t]['bodies']); uS=[s for s in uS if s['n'] not in SP]
        w=max(pairs,key=lambda p:math.hypot(p[0]['x']-p[1]['x'],p[0]['y']-p[1]['y']),default=None)
        dp=math.hypot(w[0]['x']-w[1]['x'],w[0]['y']-w[1]['y']) if w else 0
        h=max(pairs,key=lambda p:abs(p[0]['hp']-p[1]['hp']),default=None); dh=abs(h[0]['hp']-h[1]['hp']) if h else 0
        g=dp<0.001 and dh<1 and not uS and not uN
        ok+=g
        if not g and first is None:
            first=t; fd=dict(dpos=round(dp,4),pos_ent=(w[0]['n'],w[0]['id'],w[1]['id'],w[0]['o']) if w else None,dhp=dh,hp_ent=(h[0]['n'],h[0]['id'],h[1]['id']) if h and dh>=1 else None,unS=[(s['n'],s['id']) for s in uS],unN=[(n['n'],n['id']) for n in uN])
    Na={t:N[t]['actions'] for t in N}
    fa=next((t for t in sorted(set(sdec)|set(Na)) if sdec.get(t)!=Na.get(t)),None)
    amatch=sum(1 for t in sdec if Na.get(t)==sdec[t])
    return dict(frames_ok=ok,frames=tot,first_state=first,first_state_detail=fd,first_action=fa,actions_match=amatch,n_actions=len(sdec),n_native=len(Na))
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('v',type=int); ap.add_argument('jobs'); ap.add_argument('--tag',required=True)
    ap.add_argument('--patch',action='append',default=[]); ap.add_argument('--every-tick',default=None); ap.add_argument('--detail',action='store_true')
    a=ap.parse_args()
    global DETAIL; DETAIL=a.detail
    for p in a.patch:
        spec=importlib.util.spec_from_file_location('patch_'+Path(p).stem,p); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    idx={p['sj']:p for p in json.load(open('/tmp/dsweep/index.json'))[str(a.v)]}
    ATT=R/f'tier-a-fresh-v{a.v}'
    plan=ExecutionPlan.model_validate_json((ATT/'branch-plan.json').read_text())
    J=jobs(plan)
    et=None
    if a.every_tick: lo,hi=map(int,a.every_tick.split('-')); et=(lo,hi)
    cur={'d':None}
    orig=BattleState.step
    def step(self,*args,**kw):
        orig(self,*args,**kw)
        d=cur['d']
        if d is not None and (self.tick%5==0 or (et and et[0]<=self.tick<=et[1])):
            d[self.tick]=snap_entities(self)
    BattleState.step=step
    for sj in [int(x) for x in a.jobs.split(',')]:
        out=Path(f'/tmp/dsweep/runs/{a.tag}/v{a.v}-{sj:05d}')
        if (out/'summary.json').exists(): continue
        out.parent.mkdir(parents=True,exist_ok=True)
        try: os.mkdir(str(out)+'.lock')
        except FileExistsError: continue
        if (out/'summary.json').exists(): continue
        if out.exists(): shutil.rmtree(out)
        out.mkdir(parents=True)
        dumps={}; cur['d']=dumps
        import dsweep_gates; dsweep_gates.reset()
        args=argparse.Namespace(deadline=time.monotonic()+36000,port=None)
        try:
            with contextlib.ExitStack() as st:
                res=rr._execute_job_body(plan,J[sj],out,args,st,[],None)
        except Exception as ex:
            import traceback; print('JOBFAIL',a.v,sj,repr(ex),flush=True); traceback.print_exc(); cur['d']=None; continue
        cur['d']=None
        sdec={j['tick']:j['actions'] for j in map(json.loads,gzip.open(out/'decisions.jsonl.gz'))}
        p=idx[sj]
        cmpr=compare_run(a.v,p['rj'],p['rdir'],dumps,sdec)
        rec_same=gzip.open(out/'decisions.jsonl.gz').read()==gzip.open(p['sdir']+'/decisions.jsonl.gz').read()
        summ=dict(v=a.v,sj=sj,rj=p['rj'],fam=p['fam'],cond=p['cond'],role=p['role'],root=p['root'],score=res['score'],own=res['own_remaining_hp'],en=res['enemy_remaining_hp'],
                  gates=dict(__import__('dsweep_gates').FIRED),native=p['native'],recorded_scalar=p['scalar'],same_as_recorded=rec_same,hp_eq_native=[res['own_remaining_hp'],res['enemy_remaining_hp']]==p['native'][1:],**cmpr)
        with gzip.open(out/'ticks.jsonl.gz','wt') as f:
            for t in sorted(dumps): f.write(json.dumps({'tick':t,'ents':dumps[t]})+'\n')
        (out/'summary.json').write_text(json.dumps(summ))
        for f in ('transport.jsonl.gz',):
            pass
        print(json.dumps({k:summ[k] for k in ('v','sj','fam','cond','role','score','own','en','native','same_as_recorded','frames_ok','frames','first_state','first_action')}),flush=True)
main()
