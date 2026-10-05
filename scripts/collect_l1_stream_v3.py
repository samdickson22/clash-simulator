"""Continuous offline capture with independent native timing and H.264 storage.

Timing labels remain estimates with explicit intervals until visual validation
passes. The collector never treats an enqueue acknowledgement as a deployment.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import threading
import time

import cv2
import numpy as np

from certify_l1_timing_v3 import verify_owner
from collect_l1_events_v2 import disk_bytes
from collect_l1_rendered import BASE, REPORT, append, progress
from clasher.data import CardDataLoader
from clasher.rl.c56_scripted import C56_ADDED_CARDS
from clasher.rl.native_public_observation import PUBLIC_REFERENCE_CARDS
from clasher.vision.l1_stream import GrpcScreenStream
from smoke_reference_battle import request
from l1_native_capture_v3 import consistent_observation


def prepare(output, count, seed_base=261007100, varied_phases=False):
    roster = sorted(set(PUBLIC_REFERENCE_CARDS)|C56_ADDED_CARDS)
    loader = CardDataLoader()
    ids = {n: loader.get_card(n)._raw_entry['id'] for n in roster}
    used = set()
    entries = []
    blocks = {}
    for block in range((count+6)//7):
        for side in (0,1):
            rng=random.Random(seed_base+900+block*2+side)
            while True:
                shuffled=rng.sample(roster,len(roster))
                groups=[shuffled[j:j+8] for j in range(0,len(roster),8)]
                champions={'ArcherQueen','Goblinstein','MightyMiner'}
                if all(len(set(g)&champions)<=1 and tuple(sorted(g)) not in used for g in groups):break
            for group in groups:used.add(tuple(sorted(group)))
            blocks[block,side]=groups
    for i in range(count):
        seed = seed_base+i
        rng = random.Random(seed)
        split = ('heldout' if i//7==(count-1)//7 else 'validation' if i//7==(count-1)//7-1 else 'train')
        decks = [blocks[i//7,side][i%7] for side in (0,1)]
        config = json.loads(BASE.read_text())['config']
        config.update(rndSeed=seed,endTick=7200)
        for side in (0,1):
            config['battle'][f'deck{side}']['sp']=[{'d':ids[n]} for n in decks[side]]
        starts=(340,1200,2400,3600,4200,4800,5200)
        entries.append(dict(episode_id=f'l1v3-{seed}',seed=seed,split=split,decks=decks,
            config=config,start_tick=starts[i%7] if varied_phases else 340 if i%7==0 else 2400,end_tick=5900))
    output.mkdir(parents=True,exist_ok=False)
    (output/'videos').mkdir()
    (output/'evaluation_only').mkdir()
    manifest=dict(schema='clasher.l1.stream.v3',matches=entries,cards=roster,ids=ids,
        target_fps=10,new_data_limit=2*1024**3,live_loop_limit=int(5.5*1024**3),
        inference_inputs='sanitized video frames, timestamps only',
        exact_render_tick_certified=False)
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--ownership',type=Path,default=REPORT/'v3/emulator/complete.json')
    p.add_argument('--matches',type=int,default=56)
    p.add_argument('--seed-base',type=int,default=261007100)
    p.add_argument('--varied-phases',action='store_true')
    p.add_argument('--adaptive-minimum',type=int)
    p.add_argument('--shard',type=int,default=0)
    p.add_argument('--shards',type=int,default=1)
    p.add_argument('--episode-limit',type=int)
    p.add_argument('--seconds-limit',type=float)
    p.add_argument('--prepare',action='store_true')
    a=p.parse_args();cv2.setNumThreads(1)
    manifest=json.loads((a.output/'manifest.json').read_text()) if (a.output/'manifest.json').exists() else prepare(a.output,a.matches,a.seed_base,a.varied_phases)
    if a.prepare:
        print('Frozen stream seeds/decks prepared',flush=True)
        return
    receipt=json.loads(a.ownership.read_text());verify_owner(receipt)
    producer_paths=[Path(__file__),Path(__file__).with_name('l1_native_capture_v3.py')]
    append(a.output/'producers.jsonl',dict(pid=os.getpid(),shard=a.shard,
        ownership=str(a.ownership),source_hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in producer_paths}))
    ids=manifest['ids'];names={v:k for k,v in ids.items()}
    selected=[m for i,m in enumerate(manifest['matches']) if i%a.shards==a.shard][:a.episode_limit]
    if a.adaptive_minimum:
        selected.sort(key=lambda e:({'heldout':0,'validation':1,'train':2}[e['split']],e['seed']))
    record=a.output/f'episodes-{a.shard}.jsonl'
    completed={json.loads(l)['episode_id'] for l in record.read_text().splitlines()} if record.exists() else set()
    discovery=Path.home()/f"Library/Caches/TemporaryItems/avd/running/pid_{receipt['pid']}.ini"
    call=lambda command:request(receipt['probe_port'],command)
    with ExitStack() as capture_resources:
        for entry in selected:
            if a.adaptive_minimum:
                completed_rows=[];required=set()
                for corpus in ('dataset','dataset-extra'):
                    folder=REPORT/'v3'/corpus
                    plan=json.loads((folder/'manifest.json').read_text())
                    required.update(e['episode_id'] for e in plan['matches'] if e['split']!='train')
                    for path in folder.glob('episodes-*.jsonl'):
                        completed_rows.extend(json.loads(line) for line in path.read_text().splitlines())
                if (sum(r['accepted_events'] for r in completed_rows)>=a.adaptive_minimum and
                        required<={r['episode_id'] for r in completed_rows}):
                    progress(f'v3 shard {a.shard}: adaptive minimum reached with all frozen validation/heldout matches complete.')
                    break
            ep=entry['episode_id']
            if ep in completed:
                continue
            out=a.output/'evaluation_only'/ep
            out.mkdir(exist_ok=False)
            rng=random.Random(entry['seed']);uses=Counter();stop=threading.Event()
            seq=call('configure-native '+json.dumps(entry['config'],separators=(',',':')))['sequence']
            deadline=time.perf_counter()+45
            while time.perf_counter()<deadline:
                s=call('status')
                if s['nativeRenderLoaded']==seq and s['nativeRenderReady']:
                    break
                time.sleep(.1)
            else:
                raise TimeoutError('Renderer startup')
            tick=call('pause')['tick'];call('speed 4');call('render on')
            while tick<entry['start_tick']:
                tick=call(f"advance-native {min(1000,entry['start_tick']-tick)}")['tick']
            call('speed 1')
            time.sleep(.4)
            observations=[];accepted=[];finished_at=[None]

            def observe_and_play():
                pending=[];next_action=entry['start_tick']+200;next_observe=0.
                while not stop.is_set():
                    if time.perf_counter()<next_observe:
                        begin=time.perf_counter_ns();status=call('status');end=time.perf_counter_ns()
                        append(out/'timing.jsonl',dict(start_ns=begin,end_ns=end,tick=status['tick']))
                        stop.wait(.03)
                        continue
                    obs,fence=consistent_observation(call,record=lambda row:append(out/'observation-rejections.jsonl',row))
                    begin,end=fence['start_ns'],fence['end_ns']
                    next_observe=time.perf_counter()+.3
                    players={p['owner']:p for p in obs['players']}
                    def summary(player):
                        hand=[None]*4
                        for c in player['hand']:hand[c['handIndex']]=names[c['cardId']]
                        return dict(elixir=player['elixir'],hand=hand,
                            cycle=[names[c['cardId']] for c in player['cycle']])
                    row=dict(start_ns=begin,end_ns=end,tick=obs['tick'],observation_fence=fence,
                        players=[summary(players[s]) for s in (0,1)])
                    observations.append(row);append(out/'observations.jsonl',row)
                    for e in list(pending):
                        if obs['tick']<e['tick']+2 and not obs.get('ended'):
                            continue
                        status=call(f"replay-schedule-status {e['sequence']}")
                        player=players[e['player_id']]
                        still=any(c['cardId']==e['card_id'] for c in player['hand'])
                        # Bound elapsed regeneration, including triple elixir.
                        spend=e['before_elixir']-player['elixir']+(obs['tick']-e['before_tick'])*.054
                        valid=status['state']=='succeeded' and not still and spend>=e['cost']-.1
                        record_event=dict(e,status=status,accepted=valid,after_tick=obs['tick'])
                        append(out/'events.jsonl',record_event)
                        if valid:
                            accepted.append(record_event);uses[e['player_id'],e['card']]+=1
                        pending.remove(e)
                    if obs.get('ended') or obs['tick']>=entry['end_tick']:
                        terminal=call('pause')
                        append(out/'terminal.jsonl',dict(paused_tick=terminal['tick'],observed_tick=obs['tick'],
                            observed_ended=obs.get('ended'),at_mono_s=time.perf_counter()))
                        finished_at[0]=time.perf_counter()
                        stop.set();break
                    if obs['tick']>=next_action and not pending and obs['tick']<entry['end_tick']-40:
                        next_action=obs['tick']+20
                        negative=((obs['tick']-entry['start_tick'])//100)%9==8
                        if negative:
                            append(out/'negative-windows.jsonl',dict(start_tick=obs['tick'],end_tick=next_action))
                        else:
                            for side,player in players.items():
                                choices=list(player['hand'])
                                if not choices:continue
                                card=min(choices,key=lambda c:uses[side,names[c['cardId']]]+rng.random()*.3)
                                if card['cost']>player['elixir']:continue
                                x=rng.choice([1500,4500,7500,10500,13500,16500])
                                # Vary lanes and depth; spells use either half.
                                y=rng.choice([1500,4500,8500,11500,13500]) if side==0 else rng.choice([18500,20500,23500,27500,30500])
                                if card['cardId']//1000000==28 and rng.random()<.5:y=32000-y
                                at=call('status')['tick']+8
                                scheduled=call(f"replay-schedule-card {side} {card['cardId']} {x} {y} {at}")
                                command_event=dict(tick=at,player_id=side,card=names[card['cardId']],
                                    card_id=card['cardId'],cost=card['cost'],x_tiles=x/1000,y_tiles=y/1000,
                                    sequence=scheduled['sequence'],before_elixir=player['elixir'],before_tick=obs['tick'])
                                pending.append(command_event);append(out/'commands.jsonl',command_event)
                    stop.wait(.05)

            video=a.output/'videos'/f'{ep}.mp4'
            command=[shutil.which('ffmpeg'),'-nostdin','-v','error','-f','rawvideo','-pix_fmt','bgr24','-s','540x1140',
                '-r','10','-i','pipe:0','-an','-c:v','libx264','-threads','1','-preset','veryfast',
                '-crf','32','-g','10','-pix_fmt','yuv420p','-movflags','+faststart',str(video)]
            frames=[];start=time.perf_counter();last=0;next_capture=start
            with (out/'encoder.log').open('w') as log:
                # Use posix_spawn on macOS and open gRPC afterwards. Forking an
                # active gRPC process produced a stalled screenshot stream.
                encoder=subprocess.Popen(command,stdin=subprocess.PIPE,stderr=log,close_fds=False)
                stream=capture_resources.enter_context(GrpcScreenStream(receipt['grpc_port'],REPORT/'v1/grpc',discovery))
                try:
                    last=stream.read().sequence
                    start=time.perf_counter();next_capture=start
                    call('resume')
                    with ThreadPoolExecutor(max_workers=1) as pool:
                        future=pool.submit(observe_and_play)
                        try:
                            while not stop.is_set() or (finished_at[0] is not None and time.perf_counter()<finished_at[0]+1.):
                                if future.done():future.result()
                                if a.seconds_limit and time.perf_counter()-start>a.seconds_limit:
                                    stop.set();break
                                frame=stream.read(after_sequence=last);last=frame.sequence
                                if frame.decoded_at<next_capture:continue
                                next_capture+=.1
                                if next_capture<frame.decoded_at:next_capture=frame.decoded_at+.1
                                mono0=time.perf_counter_ns();wall=time.time_ns();mono1=time.perf_counter_ns()
                                encoder.stdin.write(frame.pixels.tobytes())
                                row=dict(episode_id=ep,frame_index=len(frames),sequence=frame.sequence,
                                    timestamp_ms=round((frame.decoded_at-start)*1000),produced_epoch_s=frame.produced_at,
                                    received_mono_s=frame.decoded_at,mono_before_ns=mono0,wall_ns=wall,mono_after_ns=mono1,
                                    split=entry['split'],video=f'videos/{ep}.mp4')
                                frames.append(row);append(out/'frames.jsonl',row)
                                if len(frames)%200==0:
                                    if (disk_bytes(REPORT/'v3')>1.9*1024**3 or disk_bytes(REPORT.parent)>5.4*1024**3
                                            or shutil.disk_usage(a.output).free<5*1024**3):
                                        raise RuntimeError('Storage guard; preserve partial recording')
                        finally:
                            stop.set();future.result()
                finally:
                    stop.set();call('pause');capture_resources.close();encoder.stdin.close()
                    if encoder.wait(timeout=30):raise RuntimeError('H.264 encoder failed')
            verify_owner(receipt)
            stats=dict(episode_id=ep,split=entry['split'],frames=len(frames),accepted_events=len(accepted),
                final_tick=observations[-1]['tick'],seconds=frames[-1]['produced_epoch_s']-frames[0]['produced_epoch_s'],
                fps=(len(frames)-1)/(frames[-1]['produced_epoch_s']-frames[0]['produced_epoch_s']),
                video_bytes=video.stat().st_size,video_sha256=hashlib.file_digest(video.open('rb'),'sha256').hexdigest(),
                timing_certified=False,limited=a.seconds_limit is not None,capture_protocol=2,
                trailing_window_ms=max(0.,(frames[-1]['received_mono_s']-finished_at[0])*1000) if finished_at[0] is not None else 0)
            append(record,stats)
            progress(f"v3 stream {ep}: {len(accepted)} accepted deployments, {len(frames)} frames at {stats['fps']:.2f} FPS, {video.stat().st_size} H.264 bytes; timing audit pending.")
    (a.output/f'complete-{a.shard}.json').write_text(json.dumps(dict(planned_episodes=len(selected),
        completed_episodes=sum(1 for _ in record.open()),adaptive_minimum=a.adaptive_minimum))+'\n')


if __name__=='__main__':main()
