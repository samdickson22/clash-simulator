"""Validation-only L2 empirical-gap replay with unchanged v3 perception/fusion."""
import argparse
from collections import defaultdict
from dataclasses import replace
import gzip
import hashlib
import json
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'scripts'))
import cv2
import numpy as np
import torch
from infer_l1_stream_v3 import REPORT, append, synchronize, empty_cache
from clasher.vision.l1_offline import offline_ml
from clasher.vision.l1_perception import Perception,serialize_frame
from clasher.vision.l1_events_v3 import StreamEventDetector
from clasher.vision.l1_hud_v3 import StreamHudReader
from clasher.rl.live_inference_contract import parse_public_vision_frame
from evaluate_l1_stream_v3 import replay,read,score_events
from gap_schedule_v4 import audit_sources, make_schedules


def main():
    p=argparse.ArgumentParser();p.add_argument('--dataset',type=Path,required=True);p.add_argument('--run',type=Path,required=True)
    p.add_argument('--l2',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    manifest=json.loads((a.dataset/'manifest.json').read_text())
    if any(e['split'] not in ('train','validation') for e in manifest['matches']):raise ValueError('Heldout forbidden')
    a.output.mkdir(parents=True,exist_ok=False)
    source=audit_sources(a.l2);gaps=source['intervals_ms']
    (a.output/'gap-source.json').write_text(json.dumps(source,indent=2)+'\n')
    inputs={}
    for e in manifest['matches']:
        if e['split']!='validation':continue
        ep=e['episode_id']
        if ep in inputs:raise ValueError('Duplicate validation episode')
        inputs[ep]=read(a.dataset/'audit'/ep/'inputs.jsonl')
    plan=make_schedules({ep:[r['timestamp_ms'] for r in rows] for ep,rows in inputs.items()},gaps)
    # Preserve original times in the schedule; retain the existing v3 integer-ms
    # boundary adapter required by its public-frame contract.
    selected=[]
    for ep,rows in plan['schedules'].items():
        for r in rows:
            original=inputs[ep][r['frame_index']]
            selected.append(dict(original,source_timestamp_ms=original['timestamp_ms'],
                                 timestamp_ms=int(original['timestamp_ms'])))
    selection_path=a.output/'inputs.jsonl';selection_path.write_text(''.join(json.dumps(x)+'\n' for x in selected))
    (a.output/'schedule.json').write_text(json.dumps(dict(seed=6109,gaps=len(gaps),p95_ms=float(np.quantile(gaps,.95)),
        source_files=source['source_files'],source_field=source['source_field'],plan=plan,
        selected=len(selected),inputs_sha256=hashlib.sha256(selection_path.read_bytes()).hexdigest()),indent=2)+'\n')
    offline_ml(a.output/'offline');cv2.setNumThreads(1);torch.set_num_threads(1)
    model=a.run/'model';body=Perception(REPORT/'v1/model/detector/weights/best.pt',model/'hud.npz',REPORT/'calibration.json',imgsz=640,device='cuda')
    body.hud=StreamHudReader(model/'hud.npz');detector=StreamEventDetector(model/'last.pt',body.geo,device='cuda')
    video=None;ep=None;timings=[]
    try:
        for n,row in enumerate(selected):
            if row['episode_id']!=ep:
                if video is not None:video.release()
                ep=row['episode_id'];video=cv2.VideoCapture(str(a.dataset/row['video']));index=0;ready=0.
            synchronize('cuda');begin=time.perf_counter()
            while index<row['frame_index']:
                if not video.grab():raise ValueError('Truncated skipped media')
                index+=1
            ok,image=video.read()
            if not ok:raise ValueError('Truncated media')
            frame=body.step(image,ep,str(index),row['timestamp_ms']);result,cues=detector.step(image,frame)
            synchronize('cuda');elapsed=(time.perf_counter()-begin)*1000;timings.append(elapsed)
            ready=max(ready,row['timestamp_ms'])+elapsed
            append(a.output/'frames.jsonl',serialize_frame(result));append(a.output/'candidates.jsonl',dict(episode_id=ep,frame_id=str(index),
                timestamp_ms=row['timestamp_ms'],inference_ms=elapsed,available_timestamp_ms=ready,**cues));index+=1
            if n%500==0:print(f'{n}/{len(selected)}',flush=True)
    finally:
        if video is not None:video.release()
    selection=json.loads((a.run/'validation-evaluation/selection.json').read_text())
    frames=[parse_public_vision_frame(x) for x in read(a.output/'frames.jsonl')];cues=read(a.output/'candidates.jsonl')
    predictions=replay(frames,cues,selection['thresholds'])
    truth=[r for e in manifest['matches'] if e['split']=='validation' for r in read(a.dataset/'audit'/e['episode_id']/'events.jsonl')]
    scored=[replace(f,timestamp_ms=round(c['available_timestamp_ms'])) for f,c in zip(predictions,cues)]
    opponent=[replace(f,play_events=tuple(e for e in f.play_events if e.player_id==0)) for f in scored]
    metrics=dict(split='validation',all_sides=score_events(scored,truth),opponent=score_events(opponent,[e for e in truth if e['player_id']==0]),
                 frames=len(selected),fps=1000/np.mean(timings),inference_p95_ms=float(np.quantile(timings,.95)),
                 historical_gap_p95_ms=float(np.quantile(gaps,.95)),thresholds='frozen on regular validation; no gap retuning',heldout_opened=False)
    (a.output/'complete.json').write_text(json.dumps(metrics,indent=2)+'\n');print(json.dumps(metrics),flush=True)

if __name__=='__main__':main()
