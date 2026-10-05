"""Run real v3 pixels while denying private files and every INET connection."""
import argparse
import builtins
import hashlib
import io
import json
import os
from pathlib import Path
import socket

os.environ['TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD']='1'
import cv2
import torch

from clasher.vision.l1_events_v3 import StreamEventDetector
from clasher.vision.l1_perception import Perception,serialize_frame
from clasher.vision.l1_offline import offline_ml
from clasher.vision.l1_hud_v3 import StreamHudReader

REPORT=Path(__file__).resolve().parents[1]/'reports/strategy_council_20260928/live-loop/l1'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--inputs',type=Path,required=True);p.add_argument('--media-root',type=Path,required=True)
    p.add_argument('--model',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();all_rows=[json.loads(l) for l in a.inputs.read_text().splitlines()]
    first=[r for r in all_rows if r['episode_id']==all_rows[0]['episode_id']]
    rows=first[100:112] if len(first)>=112 else first[:6]
    if any(set(r)!={'episode_id','frame_index','timestamp_ms','video'} for r in rows):raise ValueError('Non-media input')
    denied=[];network=[];original_open=builtins.open;original_io=io.open;original_connect=socket.socket.connect
    def check(file):
        if any(part in str(file) for part in ('evaluation_only','labels.jsonl','srp-public','gamedata.json','native_probe')):
            denied.append(str(file));raise PermissionError('Private file denied by v3 audit')
    def guarded_open(file,*args,**kwargs):check(file);return original_open(file,*args,**kwargs)
    def guarded_io(file,*args,**kwargs):check(file);return original_io(file,*args,**kwargs)
    def connect(sock,address):
        if sock.family in (socket.AF_INET,socket.AF_INET6):
            network.append(str(address));raise PermissionError('INET denied by v3 audit')
        return original_connect(sock,address)
    offline_ml(a.output.parent/'boundary-offline');results=[]
    builtins.open=guarded_open;io.open=guarded_io;socket.socket.connect=connect
    try:
        torch.set_num_threads(2);cv2.setNumThreads(1)
        body=Perception(REPORT/'v1/model/detector/weights/best.pt',a.model.parent/'hud.npz',REPORT/'calibration.json',imgsz=640)
        body.hud=StreamHudReader(a.model.parent/'hud.npz')
        detector=StreamEventDetector(a.model,body.geo)
        path=(a.media_root/rows[0]['video']).resolve()
        if not path.is_relative_to(a.media_root.resolve()) or path.suffix!='.mp4':raise ValueError('Unsafe video path')
        video=cv2.VideoCapture(str(path))
        video.set(cv2.CAP_PROP_POS_FRAMES,rows[0]['frame_index'])
        try:
            for row in rows:
                if row['video']!=rows[0]['video']:raise ValueError('Boundary sample crosses videos')
                ok,image=video.read()
                if not ok:raise ValueError('Truncated boundary sample')
                public=body.step(image,row['episode_id'],str(row['frame_index']),row['timestamp_ms'])
                result,_=detector.step(image,public);results.append(serialize_frame(result))
        finally:video.release()
    finally:
        builtins.open=original_open;io.open=original_io;socket.socket.connect=original_connect
    a.output.write_text(json.dumps(dict(passed=not denied,frames=len(results),denied_reads=denied,
        blocked_network_attempts=network,successful_network_connections=0,
        public_output_sha256=hashlib.sha256(json.dumps(results,sort_keys=True).encode()).hexdigest()),indent=2)+'\n')
    if denied:raise ValueError('Private read attempted')


if __name__=='__main__':main()
