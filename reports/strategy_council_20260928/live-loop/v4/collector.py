import argparse
from collections import Counter
import copy
import fcntl
from fractions import Fraction
import gzip
import json
import math
import os
from pathlib import Path
import random
import shutil
import sys
import threading
import time
import traceback
import cv2
import numpy as np
from common import *
from shipper import BUFFER, CAP, FLOOR, ship
from clasher.data import CardDataLoader
from clasher.rl.c56_scripted import C56_ADDED_CARDS
from clasher.rl.native_public_observation import PUBLIC_REFERENCE_CARDS
from clasher.vision.l1_stream import GrpcScreenStream

TARGET_HOURS=24
RESERVE=400*1024**2
CHAMPIONS={'ArcherQueen','Goblinstein','MightyMiner'}


def progress(message):
    print(message,flush=True)
    with (HERE/'T1-PROGRESS.md').open('a') as f:f.write(f'\n{time.strftime("%Y-%m-%d %H:%M:%S %z")}: {message}\n')


def buffer_bytes():
    return sum(p.stat().st_size for p in BUFFER.rglob('*') if p.is_file())


def guard(reserve=RESERVE):
    return buffer_bytes()+reserve<=CAP and shutil.disk_usage(BUFFER).free>=FLOOR+reserve


def prepare():
    path=HERE/'split.json'
    if path.exists():return json.loads(path.read_text())
    loader=CardDataLoader();cards=sorted(set(PUBLIC_REFERENCE_CARDS)|C56_ADDED_CARDS)
    ids={n:loader.get_card(n)._raw_entry['id'] for n in cards}
    used=set();entries=[]
    # Fixed seed/deck split, interleaved 8/1/1. Stopping depends only on elapsed
    # collection time, never outcomes or a heldout learning curve.
    for i in range(2400):
        seed=1975100700+i;rng=random.Random(seed);decks=[]
        for side in (0,1):
            while True:
                d=rng.sample(cards,8);key=tuple(sorted(d))
                if len(CHAMPIONS&set(d))<=1 and key not in used:break
            used.add(key);decks.append(d)
        entries.append(dict(episode=f'v4-phase-a-{seed}',seed=seed,split=('train' if i%10<8 else 'validation' if i%10==8 else 'heldout'),decks=decks,
          styles=[['balanced','pressure','defense'][(i+s)%3] for s in (0,1)],
          start_tick=[340,1200,2400,3600,4200,4800,5200][i%7],end_tick=5980))
    smoke=[]
    for i in range(3):
        e=copy.deepcopy(entries[i]);e.update(episode=f'v4-smoke-{i}',seed=1975100000+i,start_tick=[340,2400,4800][i],end_tick=[1540,3600,5980][i],split='smoke');smoke.append(e)
    plan=dict(schema='clasher.live-v4.split.v1',cards=cards,ids=ids,matches=entries,smoke=smoke,
      target_emulator_hours=24,max_matches=2400,target_fps=20,render_backend='host',workers=1,
      buffer_cap_bytes=CAP,free_floor_bytes=FLOOR,hub='127x02:/mpac/sdicks02/repos/clasher-v4-data',
      split_unit='seed and unordered deck multiset, globally unique across both seats',
      random_legal_placement_probability=.3,double_play_probability=.1,negative_turn_probability=.05)
    write(path,plan)
    write(HERE/'seed-audit.json',dict(seeds_unique=len({e['seed'] for e in entries})==len(entries),
       deck_multisets_unique=len(used)==len(entries)*2,phase_range=[entries[0]['seed'],entries[-1]['seed']],
       smoke_range=[smoke[0]['seed'],smoke[-1]['seed']],prior_ranges='L1 261007xxx; L2 196704xxxx; explicit prior schedule scan at freeze'))
    return plan


def freeze():
    plan=prepare()
    # Include source actually imported by collection; content identity, not dirty git HEAD.
    paths=list((ROOT/'src/clasher').rglob('*.py'))+list(HERE.glob('*.py'))+[ROOT/'scripts/collect_l1_stream_v4.py',ROOT/'scripts/l1_native_capture_v3.py',ROOT/'scripts/smoke_reference_battle.py',HERE/'split.json',HERE/'base-config.json',HERE/'body-catalog.json',ROOT/'gamedata.json',HERE/'PREREG.md',PROTO/'emulator_controller_pb2.py']
    paths += [HERE.parent/'l2'/n for n in ('pixel_player.py','offline_loop.py','bootstrap.py')]
    prior=set();scanned=[]
    def seeds(value):
        if isinstance(value,dict):
            for k,v in value.items():
                if k in ('seed','rndSeed') and isinstance(v,int):prior.add(v)
                else:seeds(v)
        elif isinstance(value,list):
            for v in value:seeds(v)
    for source in [*(HERE.parent/'l1').rglob('manifest.json'),HERE.parent/'l2/schedule.json']:
        if source.is_file() and source.stat().st_size<20*1024**2:
            seeds(json.loads(source.read_text()));scanned.append(str(source.relative_to(ROOT)))
    overlap=prior&{e['seed'] for e in plan['matches']+plan['smoke']}
    if overlap:raise ValueError('Prior seed overlap')
    audit=json.loads((HERE/'seed-audit.json').read_text());audit.update(scanned=scanned,prior_seed_count=len(prior),overlap=[])
    write(HERE/'seed-audit.json',audit);paths.append(HERE/'seed-audit.json')
    files={str(p.relative_to(ROOT)):sha(p) for p in paths}
    import importlib.metadata
    versions={n:importlib.metadata.version(n) for n in ('numpy','av','grpcio','torch')}
    write(HERE/'frozen-manifest.json',dict(frozen_at=time.time(),versions=versions,git_head=subprocess.check_output([shutil.which('git'),'rev-parse','HEAD'],text=True).strip(),files=files))
    # Preserve the producer sources, not just their hashes, before long runs.
    import tarfile
    registration=BUFFER/('v4-registration-'+sha(HERE/'frozen-manifest.json')[:16]);registration.mkdir(exist_ok=True)
    for name in ('PREREG.md','split.json','seed-audit.json','body-catalog.json','frozen-manifest.json'):
        shutil.copyfile(HERE/name,registration/name)
    with tarfile.open(registration/'producer-source.tar.gz','w:gz') as archive:
        for name in files:archive.add(ROOT/name,arcname=name,recursive=False)
    write(registration/'receipt.json',dict(schema='clasher.live-v4.registration.v1',source_manifest_sha256=sha(HERE/'frozen-manifest.json'),training_eligible=False))
    ship(registration)
    progress(f'Frozen {len(files)} source/config hashes; split SHA256 {sha(HERE/"split.json")}.')


def verify_freeze():
    frozen=json.loads((HERE/'frozen-manifest.json').read_text())
    bad=[p for p,h in frozen['files'].items() if sha(ROOT/p)!=h]
    if bad:raise RuntimeError('Frozen inputs changed: '+str(bad[:5]))


class Scripts:
    def __init__(self, plan):
        # These adapters project only own HUD and public board for the scripts.
        sys.path.insert(0,str(HERE.parent/'l2'))
        from pixel_player import PacketBuilder,model_hypothesis
        from offline_loop import native_frame
        from clasher.rl.contract_v5 import ContractV5ObservationBuilder
        from clasher.rl.public_scripted_opponent import PublicScriptedOpponent
        self.loader=CardDataLoader();self.names={v:k for k,v in plan['ids'].items()}
        self.builder=ContractV5ObservationBuilder(card_loader=self.loader)
        self.bots={style:PublicScriptedOpponent(self.builder,style=style,card_scope='c56') for style in ('balanced','pressure','defense')}
        self.packets=[PacketBuilder(self.builder),PacketBuilder(self.builder)]
        self.project=native_frame;self.model=model_hypothesis
        from clasher.rl.card_semantics import _walk_payload
        self.abilities={}
        for card in CHAMPIONS:
            for item in _walk_payload(self.loader.get_card(card)._raw_entry):
                if isinstance(item,dict) and item.get('source')=='character_abilities' and 'manaCost' in item:
                    self.abilities[item['name']]=(card,item['manaCost'])

    def choose(self, obs, side, style, rng, uses, random_place):
        frame=self.project(obs,self.loader,self.names,side)
        packet,_=self.packets[side].build(frame,obs['tick'],seat=side)
        ranked=self.bots[style].ranked_plays(self.model(packet))
        if not ranked:return None
        # Upweight underrepresented cards while retaining the script's placement
        # score. Random placements are drawn only from the script's legal set.
        byslot={}
        for v in ranked: byslot.setdefault(v.action_id//576,[]).append(v)
        slot=min(byslot,key=lambda s:(uses[side,frame.own_hand[s]],-byslot[s][0].score))
        selected=rng.choice(byslot[slot]) if random_place else byslot[slot][0]
        a=selected.action_id;tile=a%576;x,y=tile%18+.5,tile//18+.5
        if side:x,y=18-x,32-y
        return dict(side=side,card=frame.own_hand[slot],tile=[x,y],slot=slot,random_placement=random_place)


def rows(path):
    return [json.loads(l) for l in Path(path).read_text().splitlines()]


def collect(r, plan, entry, scripts):
    import av
    out=BUFFER/entry['episode']
    if out.exists():
        if (out/'receipt.json').exists():return json.loads((out/'receipt.json').read_text())
        # Keep incomplete artifacts and logs. They count against the buffer cap.
        archive=BUFFER/'incomplete';archive.mkdir(exist_ok=True)
        out.rename(archive/(out.name+'-'+str(time.time_ns())))
        progress(f'Technical rerun of {entry["episode"]}; incomplete attempt retained.')
    out.mkdir(parents=True)
    for name in ('events.jsonl','commands.jsonl','negative-windows.jsonl'): (out/name).touch()
    config=json.loads((HERE/'base-config.json').read_text());config.update(rndSeed=entry['seed'],endTick=7200)
    for side in (0,1):config['battle'][f'deck{side}']['sp']=[{'d':plan['ids'][n]} for n in entry['decks'][side]]
    r.verify();initial=r.configure(config,entry['start_tick']);time.sleep(.5)
    stop=threading.Event();error=[];samples=[];events=[];uses=Counter();rng=random.Random(entry['seed']);pending=[]
    body_catalog=json.loads((HERE/'body-catalog.json').read_text())['names'];body_metadata={};rich_snapshots=[]
    lock=threading.Lock();terminal={};capture_rows=[];started=time.perf_counter();start_epoch=time.time()
    object_log=gzip.open(out/'objects.jsonl.gz','wt');private_log=gzip.open(out/'evaluation-only.jsonl.gz','wt')
    write(out/'setup.json',dict(entry=entry,config=config,initial=initial))

    def emit(f,value):f.write(json.dumps(value,separators=(',',':'))+'\n')
    def observer():
      try:
        next_turn=entry['start_tick']+20;next_ability=next_turn+100;last_coherent=time.perf_counter();last_rich_tick=-1000;rich=None;double_waiting=False
        while not stop.is_set():
          t=time.perf_counter()
          try:obs,fence=r.observe()
          except TimeoutError:
            append(out/'observation-skips.jsonl',dict(time=time.perf_counter(),since_coherent=time.perf_counter()-last_coherent))
            if time.perf_counter()-last_coherent>10:raise
            continue
          last_coherent=time.perf_counter();tick=obs['tick'];players={p['owner']:p for p in obs['players']}
          unknown=any(o['nativeObjectId'] not in body_metadata and o.get('hp') is not None for o in obs['objects'])
          if unknown and tick-last_rich_tick>=20:
            obs,rich,fence=r.atomic();tick=obs['tick'];players={p['owner']:p for p in obs['players']};last_rich_tick=rich['tick']
            # Retain the object snapshot, not cumulative telemetry rings.
            rich_snapshots.append(dict(tick=rich['tick'],objects=rich['objects'],players=rich['players']))
            for o in rich['objects']:
                if 'nativeObjectId' not in o:continue
                meta=dict(data_global_id=o['dataGlobalId'],body_name=body_catalog.get(str(o['dataGlobalId'])),metadata_tick=rich['tick'])
                old=body_metadata.get(o['nativeObjectId'])
                if old and old['data_global_id']!=meta['data_global_id']:meta['body_name']=None;meta['identity_changed']=True
                body_metadata[o['nativeObjectId']]=meta
          rich_objects={o['nativeObjectId']:o for o in rich['objects']} if rich and rich['tick']==tick else {}
          sample=dict(t=(fence['start_ns']+fence['end_ns'])/2e9,tick=tick,fence=fence,players=players)
          with lock:samples.append(sample)
          emit(private_log,dict(observed_at=sample['t'],observation=obs,fence=fence))
          objects=[]
          for o in obs['objects']:
            n=scripts.names.get(o['cardId']);stats=scripts.loader.get_card(n) if n else None
            rich_object=rich_objects.get(o['nativeObjectId'],{});phase=rich_object.get('phaseRuntime') or {}
            objects.append(dict(native_id=o['nativeObjectId'],card_id=o['cardId'],
              body_name=None,body_name_hint=((stats._raw_entry.get('summonCharacterData') or {}).get('name',n) if stats else ('KingTower' if abs(o['x']-9000)<1000 else 'Tower')),
              owner=o['owner'],x=o['x'],y=o['y'],hp=o.get('hp'),max_hp=o.get('maxHp'),
              deploying=(phase['deployRemainingMs']>0 if phase.get('deployRemainingMs') is not None else None),
              visible_hint=rich_object.get('visibilityState'),
              visibility_provenance='same-tick rich snapshot or unavailable',deploying_provenance='same-tick rich phase runtime or unavailable',raw=o))
          emit(object_log,dict(tick=tick,observed_at=sample['t'],fence=fence,objects=objects))
          for e in list(pending):
            if tick<e['scheduled_tick']+2 and not obs['ended']:continue
            status=r.call(f"replay-schedule-status {e['sequence']}")
            if status['state']=='pending':
                if not obs['ended']:continue
                e.update(accepted=False,exec_tick=None,receipt=status,spawned_native_ids=[],
                  observed_after_tick=tick,negative_reason='match ended before execution')
                del e['before_ids'];append(out/'events.jsonl',e);events.append(e);pending.remove(e)
                continue
            p=players[e['side']]
            if e['kind']=='champion ability':
                # A successful enqueue alone is insufficient. Require the known
                # elixir spend, or retain this attempt as a rejected/unknown negative.
                rich=r.rich()
                after_ability=next((a for rp in rich.get('players',[]) if rp['owner']==e['side'] for a in (rp.get('abilityRuntime') or []) if a['actionDataName']==e['ability_name']),None)
                accepted=status['state']=='succeeded' and tick>=status['executeTick'] and e['before_elixir']-p['elixir']+(tick-e['before_tick'])*.054 >= e['cost']-.1 and after_ability is not None and (after_ability['remainingCooldownMs']>0 or after_ability['remainingChargesRaw']<e['before_ability']['remainingChargesRaw'])
                e['after_ability']=after_ability
            else:
                accepted=status['state']=='succeeded' and tick>=status['executeTick'] and not any(c['cardId']==e['card_id'] for c in p['hand']) and e['before_elixir']-p['elixir']+(tick-e['before_tick'])*.054 >= e['cost']-.1
            if e['command_tick']!=status['registeredAtTick']:raise RuntimeError('Command registration receipt changed')
            exact=status['state']=='succeeded' and status['queuedAtTick']==status['executeTick']-1
            if accepted and not exact:raise RuntimeError('Accepted play lacks exact schedule boundary')
            e.update(accepted=accepted,exec_tick=status['executeTick'] if accepted else None,receipt=status,
               spawned_native_ids=[o['nativeObjectId'] for o in obs['objects'] if o['nativeObjectId'] not in e['before_ids'] and o['owner']==e['side'] and o['cardId']==e.get('card_id')],
               observed_after_tick=tick)
            del e['before_ids'];append(out/'events.jsonl',e);events.append(e);pending.remove(e)
            if accepted:uses[e['side'],e['card']]+=1
          if obs['ended'] or tick>=entry['end_tick']:
            terminal.update(tick=tick,ended=obs['ended'],mono=time.perf_counter());r.call('pause');stop.set();break
          if tick>=next_turn and not pending and tick<entry['end_tick']-40:
            next_turn=tick+20
            if rng.random()<.05:
                append(out/'negative-windows.jsonl',dict(start_tick=tick,end_tick=next_turn));continue
            double=double_waiting or rng.random()<.1
            choices=[scripts.choose(obs,side,entry['styles'][side],rng,uses,rng.random()<.3) for side in (0,1)]
            if double and not all(choices):
                double_waiting=True
                append(out/'negative-windows.jsonl',dict(start_tick=tick,end_tick=next_turn,reason='waiting for simultaneous affordability'))
                continue
            double_waiting=False
            # Select both actions before taking one shared scheduling anchor.
            # Forced pairs have a 1-tick separation, independent of planner time.
            base_at=r.call('status')['tick']+8
            for side,chosen in enumerate(choices):
              if not chosen:continue
              card=next(c for c in players[side]['hand'] if scripts.names[c['cardId']]==chosen['card'])
              at=base_at+(side if double else side*12)
              scheduled=r.call(f"replay-schedule-card {side} {card['cardId']} {round(chosen['tile'][0]*1000)} {round(chosen['tile'][1]*1000)} {at}")
              kind=str(scripts.loader.get_card(chosen['card']).card_type).lower()
              if chosen['card']=='Miner':kind='underground'
              elif chosen['card'] in ('Fireball','Rocket','GoblinBarrel','Arrows','RoyalDelivery'):kind='flight'
              e=dict(chosen,event_id=f"{entry['episode']}-{scheduled['sequence']}",card_id=card['cardId'],cost=card['cost'],kind=kind,
                command_tick=scheduled['registeredAtTick'],before_tick=tick,scheduled_tick=at,sequence=scheduled['sequence'],before_elixir=players[side]['elixir'],
                before_ids=[o['nativeObjectId'] for o in obs['objects']],near_simultaneous=double)
              pending.append(e);append(out/'commands.jsonl',e)
          if tick>=next_ability and not pending and tick<entry['end_tick']-40:
            next_ability=tick+100
            rich=r.rich()
            for rp in rich.get('players',[]):
              side=rp['owner']
              for ability in rp.get('abilityRuntime') or []:
                name=ability['actionDataName']
                if not ability['available'] or name not in scripts.abilities:continue
                card,cost=scripts.abilities[name]
                if players[side]['elixir']<cost+.1:continue
                body=next((o for o in obs['objects'] if o['owner']==side and o['cardId']==plan['ids'][card]),None)
                if body is None:continue
                at=r.call('status')['tick']+8
                sc=r.call(f'replay-schedule-ability {side} {name} {at}')
                e=dict(event_id=f"{entry['episode']}-{sc['sequence']}",side=side,card=card,card_id=plan['ids'][card],
                  tile=[body['x']/1000,body['y']/1000],kind='champion ability',cost=cost,ability_name=name,
                  before_ability=ability,command_tick=sc['registeredAtTick'],before_tick=tick,scheduled_tick=at,sequence=sc['sequence'],
                  before_elixir=players[side]['elixir'],before_ids=[o['nativeObjectId'] for o in obs['objects']])
                pending.append(e);append(out/'commands.jsonl',e)
          stop.wait(max(0,.05-(time.perf_counter()-t)))
      except BaseException:
        error.append(traceback.format_exc());stop.set()

    video=av.open(str(out/'video.mp4'),'w')
    encoder=video.add_stream('libx264',rate=20);encoder.width=540;encoder.height=1140;encoder.pix_fmt='yuv420p'
    encoder.time_base=Fraction(1,90000);encoder.codec_context.time_base=Fraction(1,90000)
    encoder.options={'crf':'23','preset':'veryfast','threads':'1','g':'20'}
    worker=threading.Thread(target=observer,daemon=True)
    try:
      with GrpcScreenStream(r.owner['grpc_port'],PROTO,r.discovery) as stream:
        last=stream.read().sequence;r.call('resume');started=time.perf_counter();start_epoch=time.time();worker.start()
        due=0.;first_pts=None;last_pts=-1
        while not stop.is_set() or (terminal and time.perf_counter()<terminal['mono']+.7):
          if error:raise RuntimeError(error[0])
          frame=stream.read(after_sequence=last);last=frame.sequence
          if frame.produced_at<due:continue
          if first_pts is None:first_pts=frame.produced_at;due=first_pts
          due+=.05
          if due<frame.produced_at-.05:due=frame.produced_at+.05
          pts=max(last_pts+1,round((frame.produced_at-first_pts)*90000));last_pts=pts
          # Keep the 400 MiB reserve during capture for encoder/finalization buffers. Stop at the guard, before
          # crossing the hard cap. A partial match is retained, never admitted.
          if len(capture_rows)%20==0 and not guard(RESERVE):raise RuntimeError('Storage guard paused collection; incomplete match preserved')
          vf=av.VideoFrame.from_ndarray(frame.pixels,format='bgr24');vf.pts=pts;vf.time_base=Fraction(1,90000)
          for packet in encoder.encode(vf):video.mux(packet)
          mono=time.perf_counter();offset=time.time()-mono
          capture_rows.append(dict(seq=len(capture_rows),source_seq=frame.sequence,produced_at=frame.produced_at,
             received_at=frame.decoded_at,produced_mono=frame.produced_at-offset,media_pts=pts/90000,
             render_backend=r.owner['render_backend'],capture_fps_nominal=20))
          if time.perf_counter()-started>380:raise TimeoutError('Match wall guard')
    finally:
      stop.set();r.call('pause');worker.join(timeout=35)
      for packet in encoder.encode():video.mux(packet)
      video.close();object_log.close();private_log.close()
    if worker.is_alive():raise RuntimeError('Observation worker did not exit')
    if error:raise RuntimeError(error[0])
    if pending:raise RuntimeError('Unresolved scheduled commands at match end')
    # Budget all remaining writes before finalization. Deflate output is bounded
    # conservatively by raw JSON plus 1%; metadata reserves cover frames/HUD.
    object_raw=0
    with gzip.open(out/'objects.jsonl.gz','rt') as src:
        for line in src:
            row=json.loads(line)
            for o in row['objects']:o.update(body_metadata.get(o['native_id'],{}))
            object_raw+=len(json.dumps(row,separators=(',',':')).encode())+1
    rich_raw=sum(len(json.dumps(r,separators=(',',':')).encode())+1 for r in rich_snapshots)
    final_reserve=math.ceil((object_raw+rich_raw)*1.01)+len(capture_rows)*2048+2*1024**2
    if not guard(final_reserve):raise RuntimeError('Storage pause before finalization; incomplete match retained')
    # Bind body identity to the native data ID, including spawned/transformed
    # bodies that share a deployment card ID. Unknown identities remain null.
    with gzip.open(out/'objects.jsonl.gz','rt') as src,gzip.open(out/'objects-final.jsonl.gz','wt') as dst:
        for line in src:
            row=json.loads(line)
            for o in row['objects']:
                o.update(body_metadata.get(o['native_id'],{}))
            emit(dst,row)
    (out/'objects-final.jsonl.gz').replace(out/'objects.jsonl.gz')
    with gzip.open(out/'rich-objects.jsonl.gz','wt') as dst:
        for value in rich_snapshots:emit(dst,value)
    if not terminal or len(capture_rows)<20:raise RuntimeError('Incomplete match')
    # Bracket screenshot production with completed coherent observation reads.
    # These are empirical timing brackets, not a compositor fence.
    sample_times=np.array([s['t'] for s in samples])
    with (out/'frames.jsonl').open('w') as frames,(out/'hud.jsonl').open('w') as hud:
      for f in capture_rows:
        j=int(np.searchsorted(sample_times,f['produced_mono']));lo=samples[max(0,j-1)];hi=samples[min(len(samples)-1,j)]
        f.update(tick_lo=lo['tick'],tick_hi=hi['tick'],tick_bracket_certified=False,
          bracket_source='coherent started/completed step counters',bracket_extrapolated=j==0 or j==len(samples))
        emit(frames,f);p=lo['players'][1];hand=[None]*4
        for c in p['hand']:hand[c['handIndex']]=scripts.names[c['cardId']]
        tick=lo['tick'];emit(hud,dict(seq=f['seq'],label_tick=tick,tick_lo=f['tick_lo'],tick_hi=f['tick_hi'],
          own_hand=hand,own_next_card=scripts.names[p['cycle'][0]['cardId']] if p['cycle'] else None,
          own_elixir=p['elixir'],displayed_integer_elixir=math.floor(p['elixir']),
          clock=max(0,(180 if tick<=3600 else 300)-max(0,(tick-1)//20)),phase=1 if tick<2400 else 2 if tick<4800 else 3))
    fps=(len(capture_rows)-1)/(capture_rows[-1]['produced_at']-capture_rows[0]['produced_at'])
    r.verify()
    receipt=dict(schema='clasher.live-v4.match.v1',**entry,owner=r.owner,attestation_sha256=PIN,
      ipv4_uid_reject_verified=True,ipv6_uid_reject_verified=True,render_backend=r.owner['render_backend'],
      frames=len(capture_rows),capture_fps=fps,capture_fps_nominal=20,started_epoch=start_epoch,
      elapsed_emulator_seconds=terminal['mono']-started,native_seconds=(terminal['tick']-initial['tick'])/20,
      terminal=terminal,accepted_events=sum(e['accepted'] for e in events),events=len(events),
      accepted_opponent_events=sum(e['accepted'] and e['side']==0 for e in events),
      exact_tick_events=sum(e['accepted'] and isinstance(e['exec_tick'],int) for e in events),
      card_side_counts=dict(Counter(f"{e['side']}:{e['card']}" for e in events if e['accepted'] and e['kind']!='champion ability')),
      frame_gap_p99_ms=float(np.percentile(np.diff([f['produced_at'] for f in capture_rows])*1000,99)),
      tick_semantics='executeTick plus succeeded and queuedAtTick == executeTick - 1, corroborated by hand and spend',
      source_manifest_sha256=sha(HERE/'frozen-manifest.json'),ability_events=sum(e['accepted'] and e['kind']=='champion ability' for e in events),buffer_bytes=buffer_bytes(),
      free_disk_bytes=shutil.disk_usage(BUFFER).free,files={p.name:sha(p) for p in out.iterdir() if p.is_file()})
    write(out/'receipt.json',receipt)
    return receipt


def summary():
    receipts=[json.loads(p.read_text()) for p in (HERE/'data').glob('v4-*.json')]
    phase=[v for v in receipts if v['receipt']['split']!='smoke'];smoke=[v for v in receipts if v['receipt']['split']=='smoke']
    def stats(values):
        rr=[v['receipt'] for v in values]
        return dict(matches=len(rr),deployments=sum(v['accepted_events'] for v in rr),
          emulator_hours=sum(v['elapsed_emulator_seconds'] for v in rr)/3600,
          bytes_on_hub=sum(v['hub']['bytes'] for v in values),hub_verified_matches=len(values),
          min_capture_fps=min([v['capture_fps'] for v in rr],default=0),
          fps_pass_matches=sum(v['capture_fps']>=19.8 for v in rr),
          exact_ticks=sum(v['exact_tick_events'] for v in rr),
          heldout_matches=sum(v['split']=='heldout' for v in rr),
          heldout_opponent_events=sum(v['accepted_opponent_events'] for v in rr if v['split']=='heldout'),
          ability_events=sum(v.get('ability_events',0) for v in rr),
          card_side_counts=dict(sum((Counter(v.get('card_side_counts',{})) for v in rr),Counter())))
    return dict(phase_a=stats(phase),smoke=stats(smoke),buffer_bytes=buffer_bytes(),free_disk_bytes=shutil.disk_usage(BUFFER).free)


def main():
    cv2.setNumThreads(1)
    ap=argparse.ArgumentParser();ap.add_argument('--prepare',action='store_true');ap.add_argument('--smoke',action='store_true');ap.add_argument('--status',action='store_true');a=ap.parse_args()
    BUFFER.mkdir(parents=True,exist_ok=True);(HERE/'data').mkdir(exist_ok=True)
    if a.prepare:freeze();return
    if a.status:print(json.dumps(summary(),indent=2));return
    with (BUFFER/'collector.lock').open('w') as lock:
      fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
      verify_freeze();plan=prepare()
      if not a.smoke:
        admission=json.loads((HERE/'smoke-admission.json').read_text())
        if not admission['passed'] or admission['source_manifest_sha256']!=sha(HERE/'frozen-manifest.json'):raise RuntimeError('Smoke admission missing or stale')
      r=Renderer(HERE/'emulator-host/complete.json');scripts=Scripts(plan)
      schedule=plan['smoke'] if a.smoke else plan['matches']
      for leftover in sorted(BUFFER.glob('v4-*')):
        if (leftover/'receipt.json').exists() or (leftover/'sha256.json').exists():ship(leftover)
      for entry in schedule:
        if (HERE/'data'/(entry['episode']+'.json')).exists():continue
        if not a.smoke and summary()['phase_a']['emulator_hours']>=TARGET_HOURS:break
        # Ship finished matches left by interruption before opening another match.
        for out in sorted(BUFFER.glob('v4-*')):
          if (out/'receipt.json').exists() or (out/'sha256.json').exists():ship(out)
        if (HERE/'data'/(entry['episode']+'.json')).exists():continue
        from shipper import run,HOST,DEST
        hub_bytes=int(run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10',HOST,'nice -n 10 du -sb '+DEST]).stdout.split()[0])
        if hub_bytes+RESERVE>40_000_000_000:raise RuntimeError('Hub 40 GB footprint limit reached')
        while not guard():
          r.call('pause');progress('Storage pause: waiting for 400 MiB reserve below 6 GB and above 15 GiB free.');time.sleep(30)
        receipt=collect(r,plan,entry,scripts)
        if a.smoke and not (HERE/'converter-smoke.json').exists():
          from convert_v3 import convert
          result=convert(BUFFER/entry['episode'],BUFFER/('converter-'+str(time.time_ns())))
          write(HERE/'converter-smoke.json',result)
        # Transfer failure pauses collection and retries this immutable match.
        while True:
          try:ack=ship(BUFFER/entry['episode']);break
          except Exception as e:progress(f'Shipping paused: {type(e).__name__}: {e}');time.sleep(30)
        progress(f"{entry['episode']}: {receipt['frames']} frames, {receipt['capture_fps']:.3f} FPS, {receipt['accepted_events']} plays, all exact ticks; hub verified {ack['bytes']} bytes.")
        write(HERE/'status.json',summary())
      status=summary();write(HERE/'status.json',status)
      if a.smoke:
        smoke_receipts=[json.loads((HERE/'data'/(e['episode']+'.json')).read_text())['receipt'] for e in plan['smoke']]
        same_freeze=all(r['source_manifest_sha256']==sha(HERE/'frozen-manifest.json') for r in smoke_receipts)
        s=status['smoke'];passed=same_freeze and (HERE/'converter-smoke.json').exists() and s['matches']==3 and s['fps_pass_matches']==3 and s['exact_ticks']==s['deployments'] and s['deployments']>0
        write(HERE/'smoke-results.json',dict(passed=passed,**status))
        if passed:write(HERE/'smoke-admission.json',dict(passed=True,source_manifest_sha256=sha(HERE/'frozen-manifest.json')))
        else:raise RuntimeError('Smoke gates failed')
      else:
        if status['phase_a']['emulator_hours']<TARGET_HOURS:raise RuntimeError('Frozen schedule exhausted before 24 emulator-hours')
        progress('Phase A duration reached; final status recorded.')
        phase=status['phase_a']
        gates=dict(capture=phase['fps_pass_matches']/phase['matches']>=.95,
          exact_ticks=phase['exact_ticks']==phase['deployments'],hub_checksums=phase['hub_verified_matches']==phase['matches'],
          heldout_matches=phase['heldout_matches']>=20,heldout_opponent_events=phase['heldout_opponent_events']>=1500,
          buffer=status['buffer_bytes']<=CAP,free_disk=status['free_disk_bytes']>=FLOOR)
        write(HERE/'phase-a-results.json',dict(status=status,gates=gates))
        (HERE/'T1-RESULTS.md').write_text('# T1 results\n\nPhase A duration complete. Technical and coverage gates are listed below. No training or strength claim is made.\n\n```json\n'+json.dumps(dict(status=status,gates=gates),indent=2)+'\n```\n')
if __name__=='__main__':main()
