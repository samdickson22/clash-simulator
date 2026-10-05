"""Freeze screen-only v2 candidates from a strict media-only manifest."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time

os.environ['TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD']='1'
os.environ.setdefault('PYTORCH_MPS_HIGH_WATERMARK_RATIO','0.35')
os.environ.setdefault('PYTORCH_MPS_LOW_WATERMARK_RATIO','0.25')
import cv2
import numpy as np
import torch

from clasher.vision.l1_events_v2 import TemporalEventDetector
from clasher.vision.l1_offline import offline_ml
from clasher.vision.l1_perception import Perception,serialize_frame
REPORT=Path(__file__).resolve().parents[1]/'reports/strategy_council_20260928/live-loop/l1'


def append(path,row):
    with path.open('a') as f:f.write(json.dumps(row,separators=(',',':'),allow_nan=False)+'\n')


def progress(message):
    with (REPORT/'PROGRESS.md').open('a') as f:f.write(f'\n{time.strftime("%Y-%m-%d %H:%M:%S")}: {message}\n')
    print(message,flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--inputs',type=Path,required=True)
    p.add_argument('--image-root',type=Path,required=True)
    p.add_argument('--model',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    rows=[json.loads(l) for l in a.inputs.read_text().splitlines()]
    if not rows or any(set(r)!={'episode_id','frame_id','timestamp_ms','image'} for r in rows):
        raise ValueError('Inference requires media identity only')
    a.output.mkdir(parents=True,exist_ok=False)
    offline_ml(a.output/'offline');torch.set_num_threads(2);cv2.setNumThreads(1)
    body=Perception(REPORT/'v1/model/detector/weights/best.pt',REPORT/'v1/model/hud.npz',
                    REPORT/'calibration.json',imgsz=640)
    offset_path=a.model.parent/'marker-offsets.json'
    offsets=json.loads(offset_path.read_text())['offsets'] if offset_path.exists() else None
    temporal=TemporalEventDetector(a.model,body.geo,marker_offsets=offsets)
    sources=[a.model,a.inputs,REPORT/'v1/model/detector/weights/best.pt',REPORT/'v1/model/hud.npz']
    if offset_path.exists():sources.append(offset_path)
    (a.output/'manifest.json').write_text(json.dumps(dict(
        pixel_inputs_only=True,labels_opened=False,model_sources={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}),indent=2)+'\n')
    image=cv2.imread(str(a.image_root/rows[0]['image']))
    for i in range(3):
        frame=body.step(image,'warmup',str(i),i*100)
        temporal.step(image,frame)
    times=[]
    for i,row in enumerate(rows):
        path=(a.image_root/row['image']).resolve()
        if not path.is_relative_to(a.image_root.resolve()) or path.suffix!='.jpg':
            raise ValueError('Image path escaped media root')
        torch.mps.synchronize();start=time.perf_counter()
        image=cv2.imread(str(path))
        public=body.step(image,row['episode_id'],row['frame_id'],row['timestamp_ms'])
        result,cues=temporal.step(image,public)
        append(a.output/'frames.jsonl',serialize_frame(result))
        append(a.output/'candidates.jsonl',dict(episode_id=row['episode_id'],frame_id=row['frame_id'],
                    timestamp_ms=row['timestamp_ms'],**cues))
        torch.mps.synchronize();times.append(time.perf_counter()-start)
        if i%100==0:
            torch.mps.empty_cache()
            print(f'{i+1}/{len(rows)} frames',flush=True)
    timing=dict(frames=len(rows),fps=len(times)/sum(times),p95_ms=float(np.quantile(times,.95)*1000),
                capture_excluded=True,labels_opened=False)
    (a.output/'timing.json').write_text(json.dumps(timing,indent=2)+'\n')
    (a.output/'complete.json').write_text(json.dumps(dict(
        frames_sha256=hashlib.sha256((a.output/'frames.jsonl').read_bytes()).hexdigest(),
        candidates_sha256=hashlib.sha256((a.output/'candidates.jsonl').read_bytes()).hexdigest()))+'\n')
    progress(f'v2 pixel inference frozen: {a.output.name}, {len(rows)} frames, {timing["fps"]:.2f} FPS excluding capture.')


if __name__=='__main__':main()
