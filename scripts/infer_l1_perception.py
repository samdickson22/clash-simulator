"""Run screen-only inference. Inputs contain JPEG paths and media IDs only."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path

os.environ['TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD']='1'
os.environ['YOLO_OFFLINE']='true'
os.environ['YOLO_AUTOINSTALL']='false'

import cv2
import numpy as np
import torch

from clasher.vision.l1_perception import Perception, serialize_frame
from clasher.vision.l1_offline import offline_ml


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--inputs',type=Path,required=True)
    p.add_argument('--image-root',type=Path,required=True)
    p.add_argument('--model',type=Path,required=True)
    p.add_argument('--hud',type=Path,required=True)
    p.add_argument('--calibration',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--v1',action='store_true')
    p.add_argument('--imgsz',type=int,default=416)
    p.add_argument('--hp-model',type=Path)
    args=p.parse_args()
    rows=[json.loads(l) for l in args.inputs.read_text().splitlines()]
    allowed={'episode_id','frame_id','timestamp_ms','image'}
    if any(set(row)!=allowed for row in rows):
        raise ValueError('Inference manifest must contain media identity only')
    if not rows:
        raise ValueError('No frames')
    args.output.mkdir(parents=True,exist_ok=False)
    torch.set_num_threads(2)
    offline_ml(args.output/'ultralytics-config')
    model=Perception(args.model,args.hud,args.calibration,imgsz=args.imgsz)
    if args.v1:
        from dataclasses import replace
        from clasher.vision.l1_temporal import DeploymentTracker
        from clasher.vision.l1_hp import MarkerHealthReader
        tracker=DeploymentTracker()
        health=MarkerHealthReader(args.hp_model,model.geo)
    artifacts=[args.inputs,args.model,args.hud,args.calibration]
    if args.v1:artifacts += [args.hp_model/'hp.json',args.hp_model/'hp-icon-0.png',args.hp_model/'hp-icon-1.png']
    (args.output/'manifest.json').write_text(json.dumps(dict(
        pixel_inputs_only=True,imgsz=args.imgsz,v1=args.v1,
        artifacts={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in artifacts}),indent=2)+'\n')
    for i in range(3):
        image=cv2.imread(str(args.image_root/rows[0]['image']))
        model.step(image,'warmup',str(i),i*100)
    durations=[]
    for row in rows:
        torch.mps.synchronize()
        started=time.perf_counter()
        image=cv2.imread(str(args.image_root/row['image']))
        frame=model.step(image,row['episode_id'],row['frame_id'],row['timestamp_ms'])
        if args.v1:
            frame=replace(frame,entities=health.read(image,frame.entities))
            frame=tracker.update(frame)
        payload=serialize_frame(frame)
        with (args.output/'frames.jsonl').open('a') as target:
            target.write(json.dumps(payload,separators=(',',':'),allow_nan=False)+'\n')
        torch.mps.synchronize()
        durations.append(time.perf_counter()-started)
    timing=dict(frames=len(rows),seconds=sum(durations),fps=len(rows)/sum(durations),
                mean_ms=float(np.mean(durations)*1000),p50_ms=float(np.quantile(durations,.5)*1000),
                p99_ms=float(np.quantile(durations,.99)*1000),
                p95_ms=float(np.quantile(durations,.95)*1000),
                scope='JPEG decode + YOLO + HUD + HP + tracking + PublicVisionFrame validation + JSON write; synchronized MPS, batch 1; excludes adb capture',
                warmup_frames=3,device='mps',labels_opened=False)
    (args.output/'timing.json').write_text(json.dumps(timing,indent=2)+'\n')
    print(json.dumps(timing),flush=True)


if __name__=='__main__':
    main()
