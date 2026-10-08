"""Controlled stale-frame re-tap and no-input specificity trials on pinned native."""
import json
from pathlib import Path
import sys
import time
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from common import *
from actuator import Actuator,Hud
from clasher.vision.l1_stream import GrpcScreenStream
from clasher.vision.l1_perception import HudReader


def own(o):return next(p for p in o['players'] if p['owner']==1)


def main():
    r=Renderer(HERE/'emulator-host/complete.json');inp=GrpcInput(r);reader=HudReader(HERE.parent/'l1/v1/model/hud.npz')
    config=json.loads((HERE/'base-config.json').read_text());results=[]
    try:
      with GrpcScreenStream(r.owner['grpc_port'],PROTO,r.discovery) as stream:
        for mode in ('stale-retap','pending-ledger'):
          config['rndSeed']=1974100600
          obs=r.configure(config,340)
          # Spend until below 4.1, then wait to 4.1. Keep one cost-four target.
          p=own(obs);target=next(c for c in p['hand'] if c['cost']==4)
          r.call('speed 4')
          while p['elixir']>4.1:
            choices=[c for c in p['hand'] if c['cardId']!=target['cardId'] and c['cost']<=p['elixir']]
            if choices:
              c=max(choices,key=lambda c:c['cost']);r.call(f"replay-schedule-card 1 {c['cardId']} 14500 28500 {obs['tick']+1}")
            r.call('advance-native 25');obs=r.call('observe');p=own(obs)
          steps=max(1,int(np.ceil((4.1-p['elixir'])/.0178)));r.call(f'advance-native {steps}');r.call('speed 1')
          obs=r.call('observe');p=own(obs);target=next(c for c in p['hand'] if c['cardId']==target['cardId']);slot=target['handIndex']
          frame=stream.read(after_time=time.perf_counter()+.6);h=reader.read(frame.pixels);card=h['hand'][slot]
          a=Actuator();now=time.perf_counter();hud=Hud(now,tuple(h['hand']),h['elixir'],h['next_card'])
          first=a.submit(card,4,(4.5,20.5),hud,now);assert first['state']=='tap',first
          r.call('resume');start=time.perf_counter();inp.play(slot,4.5,20.5,.02)
          time.sleep(.7)
          # Emulates L2's cached frame. The ledger sees the same stale payload.
          if mode=='stale-retap':second=dict(state='tap',slot=slot);inp.play(slot,4.5,20.5,.02)
          else:second=a.submit(card,4,(4.5,20.5),hud,time.perf_counter())
          time.sleep(1.8);r.call('pause');after=r.call('observe');pa=own(after)
          accepted_first=not any(c['cardId']==target['cardId'] for c in pa['hand'])
          actual_spend=p['elixir']-pa['elixir']+(after['tick']-obs['tick'])*.0178
          row=dict(mode=mode,seed=config['rndSeed'],before=obs,after=after,pixel_before=h,second_command=second,
             attempted=2 if second['state']=='tap' else 1,accepted=1 if accepted_first and abs(actual_spend-4)<.15 else None,
             measured_spend=actual_spend,scope='cached-frame submission test at 700 ms with backend-relative pending-command ledger')
          results.append(row);append(HERE/'actuation/stale-completion-20261007.jsonl',row)
        # No-input negative windows include continuing native animation/regen.
        r.configure(config,340);r.call('resume');neg=[];window=Actuator().verify_seconds;native_begin=r.call('status')['tick'];native_start=time.perf_counter()
        for n in range(40):
          before=stream.read(after_time=time.perf_counter());h=reader.read(before.pixels);last=before.sequence;detected=False;slot=n%4
          truth_before=own(r.call('observe'))
          cost=next(c['cost'] for c in truth_before['hand'] if c['handIndex']==slot)
          if n%2:inp.tap([211,354,497,640][slot],1749)
          start=time.perf_counter()
          while time.perf_counter()-start<window:
            f=stream.read(after_sequence=last);last=f.sequence;x=reader.read(f.pixels)
            if x['hand'][slot]!=h['hand'][slot] and h['elixir']>x['elixir'] and abs(h['elixir']-x['elixir']-cost)<=1:detected=True
          truth_after=own(r.call('observe'))
          assert [c['cardId'] for c in truth_before['hand']]==[c['cardId'] for c in truth_after['hand']] and truth_after['elixir']>=truth_before['elixir']
          row=dict(trial=n,control='selection-only' if n%2 else 'no-input',cost=cost,truth_accepted=False,pixel_predicted=detected,window_seconds=window,before=truth_before,after=truth_after)
          neg.append(row);append(HERE/'actuation/specificity-completion-20261007.jsonl',row)
        write(HERE/'actuation/reproduction-completion-20261007.json',dict(stale=results,negatives=neg,native_ticks_per_second=(r.call('status')['tick']-native_begin)/(time.perf_counter()-native_start),specificity=sum(not x['pixel_predicted'] for x in neg)/len(neg)))
    finally:r.call('pause');inp.close()

if __name__=='__main__':main()
