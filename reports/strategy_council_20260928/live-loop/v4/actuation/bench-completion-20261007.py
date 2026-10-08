"""Factorial transport bench; probe truth never enters the pixel verifier."""
import argparse
from collections import defaultdict,Counter
import itertools
import gzip
import hashlib
import json
from pathlib import Path
import sys
import time
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from common import *
from actuator import Hud, Actuator
from clasher.vision.l1_stream import GrpcScreenStream
from clasher.vision.l1_perception import HudReader
from clasher.data import CardDataLoader
from clasher.rl.native_public_observation import PUBLIC_REFERENCE_CARDS
from clasher.rl.c56_scripted import C56_ADDED_CARDS


def own(obs): return next(p for p in obs['players'] if p['owner']==1)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--trials',type=int,default=40);a=ap.parse_args()
    out=HERE/'actuation';r=Renderer(HERE/'emulator-host/complete.json')
    inp=GrpcInput(r);hud=HudReader(HERE.parent/'l1/v1/model/hud.npz')
    loader=CardDataLoader();names={loader.get_card(n)._raw_entry['id']:n for n in set(PUBLIC_REFERENCE_CARDS)|C56_ADDED_CARDS}
    from collector import Scripts,prepare
    scripts=Scripts(prepare())
    config=json.loads((HERE/'base-config.json').read_text());config['endTick']=7200
    path=out/'trials-completion-20261007.jsonl'
    retained=[out/'trials.jsonl',path]
    done={tuple(json.loads(l)['cell'])+(json.loads(l)['trial'],) for f in retained if f.exists() for l in f.read_text().splitlines()}
    cells=list(itertools.product(['grpc','adb-spawn'],[0.,.02],[3,24],[.1,1.]))
    write(out/'plan-completion-20261007.json',dict(cells=cells,trials_per_cell=a.trials,seed_base=1974100700,acceptance_window_s=1.8,pixel_gate_s=.6,truth_legal=True))
    try:
      obs=None
      configured_seed=None
      with GrpcScreenStream(r.owner['grpc_port'],PROTO,r.discovery) as stream:
        for ci,cell in enumerate(cells):
          method,delay,since,margin=cell
          for trial in range(a.trials):
            if tuple(cell)+(trial,) in done: continue
            config['rndSeed']=1974100700+ci*100+trial
            if obs is None or obs.get('ended') or obs['tick']>1600:
                obs=r.configure(config,tick=340);configured_seed=config['rndSeed']
            else:
                r.call('speed 4');r.call('advance-native 25');obs=r.call('observe')
                if obs.get('ended'):
                    obs=r.configure(config,tick=340);configured_seed=config['rndSeed']
            # Place a real own setup play, then measure a second truth-legal play
            # exactly since ticks later. Fast stepping is setup only.
            p=own(obs)
            ordered=sorted(p['hand'],key=lambda c:(c['cost'],c['cardId']))
            first,target=ordered[:2]
            # Drain other cards, then regenerate to the requested margin before
            # the last setup play. No hidden elixir mutation is used.
            desired=first['cost']+target['cost']+margin-(since+1)*.0178
            r.call('speed 4')
            while p['elixir']>desired:
                drains=[c for c in p['hand'] if c['cardId'] not in (first['cardId'],target['cardId']) and c['cost']<=p['elixir']]
                if not drains:
                    r.call('advance-native 22');obs=r.call('observe');p=own(obs);continue
                drain=max(drains,key=lambda c:c['cost']);at=obs['tick']+1
                sc=r.call(f"replay-schedule-card 1 {drain['cardId']} 14500 28500 {at}")
                r.call('advance-native 22');obs=r.call('observe');p=own(obs)
            steps=max(0,int(np.ceil((desired-p['elixir'])/.0178)))
            if steps:r.call(f'advance-native {steps}')
            obs=r.call('observe');at=obs['tick']+1
            sc=r.call(f"replay-schedule-card 1 {first['cardId']} 14500 28500 {at}")
            r.call('advance-native 1');receipt=r.call(f"replay-schedule-status {sc['sequence']}")
            r.call(f'advance-native {since}');r.call('speed 1')
            obs=r.call('observe');p=own(obs)
            c=next(c for c in p['hand'] if c['cardId']==target['cardId'])
            assert c['cost']<=p['elixir']
            assert abs(p['elixir']-c['cost']-margin)<.06,(p['elixir'],c['cost'],margin)
            slot=c['handIndex'];card=names[c['cardId']]
            public=scripts.project(obs,scripts.loader,scripts.names,1)
            packet,_=scripts.packets[1].build(public,obs['tick'],seat=1)
            legal=[d.action_id for d in scripts.bots['balanced'].ranked_plays(scripts.model(packet)) if d.action_id//576==slot]
            assert legal,'No truth-legal placement for affordable card'
            action=min(legal,key=lambda a:((a%576)%18-13)**2+((a%576)//18-11)**2)
            tile=action%576;x,y=18-(tile%18+.5),32-(tile//18+.5)
            from shipper import BUFFER
            truth_dir=BUFFER/'actuation';truth_dir.mkdir(parents=True,exist_ok=True)
            truth=dict(cell=cell,trial=trial,observation=obs,legal_action=action,tile=[x,y])
            truth_raw=json.dumps(truth,separators=(',',':'))
            with gzip.open(truth_dir/'truth-before-completion-20261007.jsonl.gz','at') as f:f.write(truth_raw+'\n')
            frame=stream.read(after_time=time.perf_counter()+.6)
            before=hud.read(frame.pixels)
            r.call('resume');start=time.perf_counter()
            if method=='grpc': ms=inp.play(slot,x,y,delay)
            else:
                st=time.perf_counter();r.adb('shell','input','tap',str([211,354,497,640][slot]),'1749')
                if delay:time.sleep(delay)
                r.adb('shell','input','tap',str(round(111+x/18*856)),str(round(436+y/32*1230)));ms=(time.perf_counter()-st)*1000
            detected=None;truth_time=None;after=None;seq=frame.sequence;fps_times=[]
            while time.perf_counter()-start<1.8:
                frame=stream.read(after_sequence=seq);seq=frame.sequence;fps_times.append(frame.produced_at)
                h=hud.read(frame.pixels)
                if detected is None and h['hand'][slot]!=before['hand'][slot] and abs(before['elixir']-h['elixir']-c['cost'])<=1:
                    detected=(time.perf_counter()-start)*1000
                if truth_time is None:
                    after,_=r.observe();p2=own(after)
                    if not any(x['cardId']==c['cardId'] for x in p2['hand']) and p['elixir']-p2['elixir']>=c['cost']-.8:
                        truth_time=(time.perf_counter()-start)*1000
                if truth_time is not None and detected is not None:break
            r.call('pause')
            if after is None:after=r.call('observe')
            append(path,dict(cell=cell,trial=trial,seed=configured_seed,card=card,slot=slot,cost=c['cost'],
                before_tick=obs['tick'],tile=[x,y],legal_action=action,legality_verified=True,truth_before_sha256=hashlib.sha256(truth_raw.encode()).hexdigest(),actual_margin=p['elixir']-c['cost'],since_last_exec_ticks=since,
                setup_receipt=receipt,tap_ms=ms,truth_accepted=truth_time is not None,truth_latency_ms=truth_time,
                pixel_latency_ms=detected,pixel_within_600ms=detected is not None and detected<=600,
                before_hud=before,capture_fps=(len(fps_times)-1)/(fps_times[-1]-fps_times[0]) if len(fps_times)>1 else 0))
            obs=r.call('observe')
            if trial%10==0:print('cell',ci,'trial',trial,'tap',round(ms,1),'truth',truth_time,'pixel',detected,flush=True)
    finally:r.call('pause');inp.close()
    rows=[json.loads(l) for f in retained if f.exists() for l in f.read_text().splitlines()];summary={}
    for method in ['grpc','adb-spawn']:
        x=[v for v in rows if v['cell'][0]==method]
        summary[method]=dict(n=len(x),accepted=sum(v['truth_accepted'] for v in x),
          tap_p95_ms=float(np.percentile([v['tap_ms'] for v in x],95)),
          pixel_600ms=sum(v['pixel_within_600ms'] for v in x),
          truth_latency_p50_ms=float(np.median([v['truth_latency_ms'] for v in x if v['truth_accepted']])),
          capture_fps_median=float(np.median([v['capture_fps'] for v in x])))
    write(out/'summary-completion-20261007.json',summary);print(summary,flush=True)
if __name__=='__main__':main()
