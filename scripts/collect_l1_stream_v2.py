"""Continuous 1x gRPC replay of heldout commands, with event-time brackets."""
import argparse
from bisect import bisect_right
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

import cv2
import numpy as np

from clasher.data import CardDataLoader
from clasher.vision.l1_stream import GrpcScreenStream
from collect_l1_rendered import REPORT,ADB,append,progress,public_targets
from clasher.vision.l1 import Geometry
from smoke_reference_battle import request
from collect_l1_events_v2 import disk_bytes


def read(p):return [json.loads(l) for l in p.read_text().splitlines()]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,default=REPORT/'v2/dataset')
    p.add_argument('--output',type=Path,default=REPORT/'v2/stream-dataset')
    p.add_argument('--ownership',type=Path,default=REPORT/'v2/emulator/complete.json')
    p.add_argument('--mode',choices=['single-tick','event-boundaries'],default='single-tick')
    p.add_argument('--jpeg-quality',type=int,default=82)
    p.add_argument('--resume',action='store_true')
    a=p.parse_args();cv2.setNumThreads(1)
    receipt=json.loads(a.ownership.read_text())
    command=subprocess.check_output(['ps','-p',str(receipt['pid']),'-o','command='],text=True)
    if 'clasher_reference_api35' not in command or '-port '+receipt['serial'].split('-')[-1] not in command:
        raise ValueError('Owned emulator identity mismatch')
    for firewall in ('iptables','ip6tables'):
        subprocess.run([str(ADB),'-s',receipt['serial'],'shell',firewall,'-C','OUTPUT','-m','owner',
            '--uid-owner',str(receipt['app_uid']),'!','-o','lo','-j','REJECT'],check=True,capture_output=True)
    if not (a.source/'complete.json').exists():raise ValueError('Source collection must finish first')
    manifest=json.loads((a.source/'manifest.json').read_text())
    matches=[m for m in manifest['matches'] if m['split']=='heldout']
    events=read(a.source/'evaluation_only/events.jsonl')
    truth={(t['episode_id'],int(t['frame_id'])):t for t in read(a.source/'evaluation_only/truth.jsonl')}
    end=manifest['config']['collection']['heldout_end_tick']
    a.output.mkdir(parents=True,exist_ok=a.resume);(a.output/'frames').mkdir(exist_ok=a.resume);(a.output/'evaluation_only').mkdir(exist_ok=a.resume)
    payload=dict(schema='clasher.l1.stream.v2',matches=matches,
        source=str(a.source),command_replay=True,render_tick_certified=False,mode=a.mode,
        jpeg_quality=a.jpeg_quality)
    if a.resume:
        if json.loads((a.output/'manifest.json').read_text())!=payload:raise ValueError('Stream resume manifest changed')
    else:(a.output/'manifest.json').write_text(json.dumps(payload,indent=2)+'\n')
    completed={r['episode_id'] for r in read(a.output/'episodes.jsonl')} if (a.output/'episodes.jsonl').exists() else set()
    present={r['episode_id'] for r in read(a.output/'inputs.jsonl')} if (a.output/'inputs.jsonl').exists() else set()
    if present-completed:raise ValueError('Quarantine incomplete episode before resuming')
    (a.output/'active-process.json').write_text(json.dumps(dict(pid=os.getpid(),mode=a.mode,output=str(a.output.resolve())))+'\n')
    initial_bytes=disk_bytes(REPORT/'v2');written_bytes=0
    call=lambda c:request(receipt['probe_port'],c)
    loader=CardDataLoader()
    names={loader.get_card(n)._raw_entry['id']:n for n in manifest['matches'][0]['decks'][0]}
    for m in matches:
        for deck in m['decks']:
            for n in deck:names[loader.get_card(n)._raw_entry['id']]=n
    ids={v:k for k,v in names.items()};geo=Geometry(REPORT/'calibration.json')
    discovery=Path.home()/f"Library/Caches/TemporaryItems/avd/running/pid_{receipt['pid']}.ini"
    with GrpcScreenStream(receipt['grpc_port'],REPORT/'v1/grpc',discovery) as stream:
        for entry in matches:
            if entry['episode_id'] in completed:continue
            ep=entry['episode_id'];expected=[e for e in events if e['episode_id']==ep]
            seq=call('configure-native '+json.dumps(entry['config'],separators=(',',':')))['sequence']
            deadline=time.monotonic()+40
            while time.monotonic()<deadline:
                status=call('status')
                if status['nativeRenderLoaded']==seq and status['nativeRenderReady']:break
                time.sleep(.1)
            else:raise TimeoutError('Native startup')
            tick=call('pause')['tick'];call('speed 1');call('render on')
            call(f'advance-native {340-tick}')
            schedules=[]
            for e in expected:
                rec=call(f"replay-schedule-card {e['player_id']} {ids[e['card']]} {round(e['x_tiles']*1000)} {round(e['y_tiles']*1000)} {e['tick']}")
                schedules.append(rec['sequence'])
            frame=stream.read(after_time=time.perf_counter()+.2)
            start_wall=frame.produced_at
            observations=[(time.time(),call('observe'))]
            step_intervals={}
            samples=[];durations=[];saved=[];last_sequence=frame.sequence
            def advance():
                at=340
                boundaries=sorted({end,*[e['tick'] for e in expected],*[e['tick']-1 for e in expected]})
                while at<end:
                    step=1 if a.mode=='single-tick' else min(200,next(t for t in boundaries if t>at)-at)
                    started=time.time();result=call(f'advance-native {step}');finished=time.time()
                    if result['tick']!=at+step:raise ValueError('Continuous advance mismatch')
                    at=result['tick'];step_intervals[at]=[started,finished]
                    observations.append((time.time(),call('observe')))
                    if result['ended']:break
                return result
            with ThreadPoolExecutor(max_workers=1) as pool:
                future=pool.submit(advance)
                while not future.done():
                    frame=stream.read(after_sequence=last_sequence)
                    last_sequence=frame.sequence
                    ok,jpg=cv2.imencode('.jpg',frame.pixels,[cv2.IMWRITE_JPEG_QUALITY,a.jpeg_quality])
                    if not ok:raise ValueError('JPEG encode')
                    if initial_bytes+written_bytes+len(jpg)+64*1024**2>1.5*1024**3:
                        # Concurrent verified archival can release bytes. Recheck
                        # actual storage before rejecting a stale upper estimate.
                        initial_bytes=disk_bytes(REPORT/'v2');written_bytes=0
                        if initial_bytes+len(jpg)+64*1024**2>1.5*1024**3:
                            raise RuntimeError('New-data guard reserves 64 MiB for metadata/inference')
                    written_bytes+=len(jpg)+4096
                    frame_id=str(frame.sequence);image=f'frames/{ep}-{frame_id}.jpg'
                    (a.output/image).write_bytes(jpg.tobytes())
                    timestamp=(frame.produced_at-start_wall)*1000
                    row=dict(episode_id=ep,frame_id=frame_id,timestamp_ms=timestamp,split='heldout',image=image)
                    append(a.output/'inputs.jsonl',row)
                    saved.append((row,frame.produced_at,hashlib.sha256(jpg).hexdigest()))
                    samples.append(frame.produced_at)
                    durations.append((time.time()-frame.produced_at)*1000)
                    if len(samples)%200==0:
                        if disk_bytes(REPORT/'v2')>1.5*1024**3 or disk_bytes(REPORT.parent)>4*1024**3:
                            raise RuntimeError('Disk guard')
                final=future.result()
            observation_times=[t for t,obs in observations]
            for row,produced,sha in saved:
                index=max(0,bisect_right(observation_times,produced)-1)
                observed_at,obs=observations[index]
                next_at,next_obs=observations[min(index+1,len(observations)-1)]
                targets,_=public_targets(obs,names,geo)
                append(a.output/'labels.jsonl',dict(**row,targets=targets))
                opp=next(p for p in obs['players'] if p['owner']==0)
                append(a.output/'evaluation_only/truth.jsonl',dict(episode_id=ep,frame_id=row['frame_id'],tick=obs['tick'],
                    opponent_elixir=opp['elixir'],opponent_hand=[names[c['cardId']] for c in opp['hand']],
                    opponent_cycle=[names[c['cardId']] for c in opp['cycle']],native_tick_bracket=[obs['tick'],next_obs['tick']]))
                append(a.output/'pairing.jsonl',dict(episode_id=ep,frame_id=row['frame_id'],screenshot_produced_at=produced,
                    observe_before_at=observed_at,observe_after_at=next_at,native_tick_bracket=[obs['tick'],next_obs['tick']],
                    render_tick_certified=False,jpeg_sha256=sha))
            statuses=[call(f'replay-schedule-status {seq}')['state'] for seq in schedules]
            if any(s!='succeeded' for s in statuses):raise ValueError('Continuous command replay rejected')
            for e in expected:
                lo,hi=step_intervals[e['tick']]
                interval=[(lo-start_wall)*1000,(hi-start_wall)*1000]
                append(a.output/'evaluation_only/events.jsonl',dict(**e,timestamp_ms=sum(interval)/2,
                        event_time_interval_ms=interval,timing='native tick-crossing bracket, no render fence'))
            after=call('observe');opp=next(p for p in after['players'] if p['owner']==0)
            reference=truth.get((ep,after['tick']))
            parity=reference is not None and abs(opp['elixir']-reference['opponent_elixir'])<1e-8 and sorted(names[c['cardId']] for c in opp['hand'])==sorted(reference['opponent_hand'])
            report=dict(episode_id=ep,frames=len(samples),seconds=samples[-1]-samples[0],
                fps=(len(samples)-1)/(samples[-1]-samples[0]),screenshot_to_saved_p95_ms=float(np.quantile(durations,.95)),
                simulation_ticks_per_wall_second=(after['tick']-340)/(samples[-1]-samples[0]),
                stepping=f'1x {a.mode} RPCs in independent worker; screenshot consumer never calls probe',
                all_commands_succeeded=True,final_opponent_hand_elixir_match=parity,final_tick=after['tick'])
            append(a.output/'episodes.jsonl',report)
            progress(f'v2 continuous stream {ep}: {len(samples)} frames at {report["fps"]:.2f} FPS; final hand/elixir replay parity {parity}.')
    (a.output/'complete.json').write_text(json.dumps(dict(status='complete',render_tick_certified=False))+'\n')


if __name__=='__main__':main()
