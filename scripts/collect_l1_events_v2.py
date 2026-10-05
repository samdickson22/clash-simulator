"""Single-tick event windows from the unchanged, isolated native renderer."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import random
import shutil
import subprocess
import time
import tomllib

import cv2
import numpy as np

from collect_l1_rendered import ADB, BASE, REPORT, append, digest, progress, public_targets, visible_clock
from smoke_reference_battle import request
from clasher.data import CardDataLoader
from clasher.rl.native_public_observation import PUBLIC_REFERENCE_CARDS
from clasher.vision.l1 import Geometry
from clasher.vision.l1_perception import HudReader
from clasher.vision.l1_stream import GrpcScreenStream


def disk_bytes(path):
    seen = set()
    total = 0
    for p in path.rglob('*'):
        if p.is_file():
            s = p.stat()
            key = s.st_dev, s.st_ino
            if key not in seen:
                total += s.st_size
                seen.add(key)
    return total


def prepare(output, config):
    loader = CardDataLoader()
    ids = {n: loader.get_card(n)._raw_entry['id'] for n in PUBLIC_REFERENCE_CARDS}
    excluded = set()
    for source in (REPORT/'dataset/manifest.json', REPORT/'v1/dataset-merged/manifest.json'):
        excluded.update(tuple(sorted(d)) for e in json.loads(source.read_text())['matches'] for d in e['decks'])
    entries = []
    c = config['collection']
    for i in range(c['matches']):
        seed = c['seed_base'] + i
        rng = random.Random(seed)
        split = 'train' if i < c['training_matches'] else 'validation' if i < c['training_matches']+c['validation_matches'] else 'heldout'
        decks = []
        for side in (0, 1):
            if i % 2:
                deck = sorted(set(PUBLIC_REFERENCE_CARDS)-set(entries[-1]['decks'][side]))
                rng.shuffle(deck)
                if tuple(sorted(deck)) in excluded:
                    raise ValueError('Complement collides; choose a new seed before collection')
            else:
                while True:
                    deck = rng.sample(list(PUBLIC_REFERENCE_CARDS), 8)
                    complement = tuple(sorted(set(PUBLIC_REFERENCE_CARDS)-set(deck)))
                    if tuple(sorted(deck)) not in excluded and complement not in excluded:
                        break
            excluded.add(tuple(sorted(deck)))
            decks.append(deck)
        native = json.loads(BASE.read_text())['config']
        native.update(rndSeed=seed, endTick=7200)
        for side in (0, 1):
            native['battle'][f'deck{side}']['sp'] = [{'d': ids[n]} for n in decks[side]]
        entries.append(dict(episode_id=f'l1v2-{seed}', seed=seed, split=split, decks=decks, config=native))
    result = dict(schema='clasher.l1.events.v2', matches=entries, config=config,
                  pairing='single native tick, fresh produced screenshot, unchanged observe; no compositor fence')
    output.mkdir(parents=True, exist_ok=False)
    (output/'frames').mkdir()
    (output/'evaluation_only').mkdir()
    (output/'manifest.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--config', type=Path, default=REPORT/'v2/config.toml')
    p.add_argument('--ownership', type=Path, default=REPORT/'v2/emulator/complete.json')
    p.add_argument('--prepare', action='store_true')
    p.add_argument('--episode-limit', type=int)
    p.add_argument('--frame-limit', type=int)
    a = p.parse_args()
    conf = tomllib.loads(a.config.read_text())
    manifest = json.loads((a.output/'manifest.json').read_text()) if (a.output/'manifest.json').exists() else prepare(a.output, conf)
    if manifest['config'] != conf:
        raise ValueError('Frozen config changed')
    if a.prepare:
        print('Prepared disjoint seeds and decks', flush=True)
        return
    receipt = json.loads(a.ownership.read_text())
    command = subprocess.check_output(['ps','-p',str(receipt['pid']),'-o','command='], text=True)
    if 'clasher_reference_api35' not in command or f"-port {receipt['serial'].split('-')[-1]}" not in command:
        raise ValueError('Owned emulator identity changed')
    for firewall in ('iptables','ip6tables'):
        subprocess.run([str(ADB),'-s',receipt['serial'],'shell',firewall,'-C','OUTPUT','-m','owner',
                        '--uid-owner',str(receipt['app_uid']),'!','-o','lo','-j','REJECT'],check=True,capture_output=True)
    loader = CardDataLoader()
    names = {loader.get_card(n)._raw_entry['id']: n for n in PUBLIC_REFERENCE_CARDS}
    geo = Geometry(REPORT/'calibration.json')
    hud = HudReader(REPORT/'v1/model/hud.npz')
    call = lambda command: request(receipt['probe_port'], command)
    discovery = Path.home()/f"Library/Caches/TemporaryItems/avd/running/pid_{receipt['pid']}.ini"
    completed_path = a.output/'episodes.jsonl'
    completed = {json.loads(l)['episode_id'] for l in completed_path.read_text().splitlines()} if completed_path.exists() else set()
    existing = a.output/'inputs.jsonl'
    partial = {json.loads(l)['episode_id'] for l in existing.read_text().splitlines()}-completed if existing.exists() else set()
    if partial:
        raise ValueError('Partial episodes cannot be silently replayed or mixed')
    baseline = disk_bytes(REPORT.parent)-disk_bytes(a.output)
    data_bytes = disk_bytes(a.output)
    cfg = conf['collection']
    with GrpcScreenStream(receipt['grpc_port'], REPORT/'v1/grpc', discovery) as stream:
        for entry in manifest['matches'][:a.episode_limit]:
            episode = entry['episode_id']
            if episode in completed:
                continue
            rng = random.Random(entry['seed'])
            seq = call('configure-native '+json.dumps(entry['config'],separators=(',',':')))['sequence']
            deadline = time.monotonic()+45
            while time.monotonic()<deadline:
                s=call('status')
                if s['nativeRenderLoaded']==seq and s['nativeRenderReady']:
                    break
                time.sleep(.1)
            else:
                raise TimeoutError('Native renderer loading')
            tick=call('pause')['tick']
            call('speed 1');call('render on')
            if tick>=340:
                raise ValueError('Missed intro warmup boundary')
            call(f'advance-native {340-tick}')
            tick=340
            for _ in range(30):
                frame=stream.read(after_time=time.perf_counter()+.12)
                if hud.read(frame.pixels)['clock']==visible_clock(tick):
                    break
                call('advance-native 20');tick+=20
            else:
                raise ValueError('Visible HUD warmup failed')
            call('speed 4')
            start_tick=tick
            end=cfg['heldout_end_tick'] if entry['split']=='heldout' else cfg['train_end_tick']
            next_window=tick
            capture_until=tick+cfg['before_ticks']+cfg['after_ticks']
            uses={(side,n):0 for side in (0,1) for n in PUBLIC_REFERENCE_CARDS}
            scheduled=[]
            frames=events=0
            last_observe=call('observe')
            while tick<=end:
                if tick==next_window:
                    deploy_tick=tick+cfg['before_ticks']
                    capture_until=deploy_tick+cfg['after_ticks']
                    scheduled=[]
                    # Every fourth command window is explicitly negative.
                    negative=((tick-start_tick)//cfg['command_interval_ticks'])%4==3
                    if not negative:
                        for player in last_observe['players']:
                            choices=[c for c in player['hand'] if c['cost']<=player['elixir']]
                            if not choices:
                                continue
                            card=min(choices,key=lambda c:uses[player['owner'],names[c['cardId']]]+rng.random()*.2)
                            side=player['owner'];name=names[card['cardId']]
                            x=rng.choice([2500,4500,6500,11500,13500,15500])
                            if name in ('Fireball','Zap'):
                                y=rng.choice([6500,9500,12500]) if side==1 else rng.choice([19500,22500,25500])
                            else:
                                y=rng.choice([7500,10500,13500]) if side==0 else rng.choice([18500,21500,24500])
                            rec=call(f"replay-schedule-card {side} {card['cardId']} {x} {y} {deploy_tick}")
                            scheduled.append(dict(player=player,card=card,x=x,y=y,sequence=rec['sequence']))
                    append(a.output/'evaluation_only/windows.jsonl',dict(episode_id=episode,start_tick=tick,
                           deploy_tick=deploy_tick,end_tick=capture_until,scheduled=len(scheduled),negative=not scheduled))
                    next_window+=cfg['command_interval_ticks']
                should_capture=entry['split']=='heldout' or tick<=capture_until
                if should_capture:
                    if data_bytes>=cfg['max_new_data_bytes']-2000000 or baseline+data_bytes>=cfg['max_live_loop_bytes']-2000000 or shutil.disk_usage(a.output).free<6*1024**3:
                        raise RuntimeError('Resource guard; existing artifacts preserved')
                    before=call('observe')
                    if before['tick']!=tick or before.get('truncated') or before.get('finalized'):
                        raise ValueError('Invalid native tick/observe')
                    barrier=time.time()+.06
                    frame=stream.read(after_time=time.perf_counter()+.06)
                    while frame.produced_at is None or frame.produced_at<barrier:
                        frame=stream.read(after_sequence=frame.sequence)
                    after=call('observe')
                    if before!=after:
                        raise ValueError('Native state changed across capture')
                    ok,jpg=cv2.imencode('.jpg',frame.pixels,[cv2.IMWRITE_JPEG_QUALITY,cfg['jpeg_quality']])
                    if not ok:raise ValueError('JPEG encode')
                    image=f'frames/{episode}-{tick:05d}.jpg'
                    (a.output/image).write_bytes(jpg.tobytes());data_bytes+=len(jpg)
                    identity=dict(episode_id=episode,frame_id=str(tick),timestamp_ms=tick*50,split=entry['split'],image=image)
                    append(a.output/'inputs.jsonl',identity)
                    targets,_=public_targets(before,names,geo)
                    append(a.output/'labels.jsonl',dict(**identity,targets=targets))
                    append(a.output/'pairing.jsonl',dict(episode_id=episode,frame_id=str(tick),tick=tick,
                        jpeg_sha256=hashlib.sha256(jpg).hexdigest(),observe_sha256=digest(before),before_after_equal=True,
                        screenshot_produced_at=frame.produced_at,capture_barrier=barrier,render_tick_certified=False))
                    opponent=next(p for p in before['players'] if p['owner']==0)
                    append(a.output/'evaluation_only/truth.jsonl',dict(episode_id=episode,frame_id=str(tick),tick=tick,
                        opponent_elixir=opponent['elixir'],opponent_hand=[names[c['cardId']] for c in opponent['hand']],
                        opponent_cycle=[names[c['cardId']] for c in opponent['cycle']]))
                    last_observe=before
                    frames+=1
                    if a.frame_limit and frames>=a.frame_limit:
                        progress(f'v2 diagnostic frame limit reached: {episode}, {frames} frames. Not a completed dataset.')
                        return
                if tick==deploy_tick and scheduled:
                    for s in scheduled:
                        side=s['player']['owner'];card=s['card'];name=names[card['cardId']]
                        player=next(p for p in last_observe['players'] if p['owner']==side)
                        remain={c['handIndex']:c['cardId'] for c in player['hand']}
                        status=call(f"replay-schedule-status {s['sequence']}")
                        accepted=remain.get(card['handIndex'])!=card['cardId'] and player['elixir']<s['player']['elixir']-card['cost']+.4
                        if not accepted:
                            append(a.output/'evaluation_only/rejected.jsonl',dict(episode_id=episode,tick=tick,card=name,side=side,state=status['state']))
                            continue
                        uses[side,name]+=1;events+=1
                        append(a.output/'evaluation_only/events.jsonl',dict(episode_id=episode,tick=tick,player_id=side,
                            card=name,x_tiles=s['x']/1000,y_tiles=s['y']/1000,pixel=geo.pixel(s['x']/1000,s['y']/1000),
                            acceptance='hand_change_and_elixir_spend',schedule_state=status['state'],
                            visual_cues={'deploy_clock':'unannotated','unit_spawn':'unannotated','spell_projectile_area':'unannotated'}))
                if tick>=end or last_observe.get('ended'):
                    break
                # Every captured interval advances exactly one simulation tick.
                amount=1 if entry['split']=='heldout' or tick<capture_until else min(next_window-tick,end-tick)
                result=call(f'advance-native {amount}')
                if result['tick']!=tick+amount:
                    raise ValueError('Native tick step mismatch')
                tick+=amount
                if amount>1:last_observe=call('observe')
            append(completed_path,dict(episode_id=episode,split=entry['split'],frames=frames,events=events,final_tick=tick,
                   coverage={f'{side}:{n}':v for (side,n),v in uses.items()}))
            progress(f'v2 collected {episode} {entry["split"]}: {frames} frames, {events} accepted events, {data_bytes} image bytes.')
    selected=manifest['matches'][:a.episode_limit]
    (a.output/'complete.json').write_text(json.dumps(dict(matches=len(selected),data_bytes=disk_bytes(a.output),
        full_plan=len(selected)==len(manifest['matches']),render_tick_certified=False),indent=2)+'\n')


if __name__=='__main__':
    main()
