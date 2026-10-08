"""Infer v3 candidates from a strict video-and-arrival-time manifest."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time

os.environ['TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD']='1'
os.environ.setdefault('PYTORCH_MPS_HIGH_WATERMARK_RATIO','.35')
os.environ.setdefault('PYTORCH_MPS_LOW_WATERMARK_RATIO','.25')
import cv2
import numpy as np
import torch

from clasher.vision.l1_events_v3 import StreamEventDetector
from clasher.vision.l1_offline import offline_ml
from clasher.vision.l1_perception import Perception,serialize_frame
from clasher.vision.l1_hud_v3 import StreamHudReader
REPORT=Path(__file__).resolve().parents[1]/'reports/strategy_council_20260928/live-loop/l1'


from train_l1_stream_v3 import empty_cache

def synchronize(device):
    if device == 'mps': torch.mps.synchronize()
    elif device == 'cuda': torch.cuda.synchronize()

def append(path,row):
    with path.open('a') as f:f.write(json.dumps(row,separators=(',',':'),allow_nan=False)+'\n')


def progress(message):
    with (REPORT/'PROGRESS.md').open('a') as f:f.write(f'\n{time.strftime("%Y-%m-%d %H:%M:%S")}: {message}\n')
    print(message,flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--inputs',type=Path,required=True);p.add_argument('--media-root',type=Path,required=True)
    p.add_argument('--model',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--device',default='mps',choices=['mps','cuda','cpu'])
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    rows=[json.loads(l) for l in a.inputs.read_text().splitlines()]
    if not rows or any(set(r)!={'episode_id','frame_index','timestamp_ms','video'} for r in rows):
        raise ValueError('Inference accepts media identities and arrival timestamps only')
    offline_ml(a.output/'offline');cv2.setNumThreads(1);torch.set_num_threads(2)
    body=Perception(REPORT/'v1/model/detector/weights/best.pt',a.model.parent/'hud.npz',
        REPORT/'calibration.json',imgsz=640,device=a.device)
    body.hud=StreamHudReader(a.model.parent/'hud.npz')
    detector=StreamEventDetector(a.model,body.geo,device=a.device)
    paths=[a.inputs,a.model,a.model.parent/'hud.npz',REPORT/'v1/model/detector/weights/best.pt']
    source_root=Path(__file__).resolve().parents[1]
    paths.extend(source_root/'src/clasher/vision'/name for name in (
        'l1.py','l1_perception.py','l1_temporal.py','l1_events_v2.py','l1_events_v3.py','l1_hud_v3.py','l1_offline.py'))
    paths.append(Path(__file__))
    (a.output/'manifest.json').write_text(json.dumps(dict(labels_opened=False,
        sources={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}),indent=2)+'\n')
    video=None;last_episode=None;times=[]
    try:
        for i,row in enumerate(rows):
            if last_episode!=row['episode_id']:
                if video is not None:video.release()
                path=(a.media_root/row['video']).resolve()
                if not path.is_relative_to(a.media_root.resolve()) or path.suffix!='.mp4':
                    raise ValueError('Video path escaped media root')
                video=cv2.VideoCapture(str(path));last_episode=row['episode_id'];index=0;ready_ms=0.
            if row['frame_index']!=index:raise ValueError('Stream inference requires every frame in order')
            synchronize(a.device);start=time.perf_counter()
            ok,image=video.read()
            if not ok:raise ValueError('Truncated video')
            public=body.step(image,row['episode_id'],str(index),row['timestamp_ms'])
            result,cues=detector.step(image,public)
            synchronize(a.device);elapsed=time.perf_counter()-start;times.append(elapsed)
            ready_ms=max(ready_ms,row['timestamp_ms'])+elapsed*1000
            append(a.output/'frames.jsonl',serialize_frame(result))
            append(a.output/'candidates.jsonl',dict(episode_id=row['episode_id'],frame_id=str(index),
                timestamp_ms=row['timestamp_ms'],inference_ms=elapsed*1000,available_timestamp_ms=ready_ms,**cues))
            index+=1
            if i%200==0:
                empty_cache(a.device);print(f'{i+1}/{len(rows)}',flush=True)
    finally:
        if video is not None:video.release()
    timing=dict(frames=len(times),fps=len(times)/sum(times),p95_ms=float(np.quantile(times,.95)*1000),capture_excluded=True)
    (a.output/'timing.json').write_text(json.dumps(timing,indent=2)+'\n')
    (a.output/'complete.json').write_text(json.dumps(dict(frames_sha256=hashlib.sha256(
        (a.output/'frames.jsonl').read_bytes()).hexdigest(),candidates_sha256=hashlib.sha256(
        (a.output/'candidates.jsonl').read_bytes()).hexdigest()))+'\n')
    progress(f"v3 inference complete: {len(times)} video frames, {timing['fps']:.2f} FPS excluding capture.")


if __name__=='__main__':main()
