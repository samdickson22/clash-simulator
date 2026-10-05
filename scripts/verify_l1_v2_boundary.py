"""Run v2 pixels with private-label/native-data reads and all sockets denied."""
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
from clasher.vision.l1_events_v2 import TemporalEventDetector
from clasher.vision.l1_perception import Perception,serialize_frame
from clasher.vision.l1_offline import offline_ml

ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/'reports/strategy_council_20260928/live-loop/l1'


def main():
    output=REPORT/'v2/boundary-runtime.json'
    rows=[json.loads(l) for l in (REPORT/'v2/validation-inputs.jsonl').read_text().splitlines()][:4]
    denied=[];network=[]
    original_open=builtins.open;original_io=io.open
    def check(file):
        name=str(file)
        if any(word in name for word in ('evaluation_only','labels.jsonl','srp-public','gamedata.json','native_probe')):
            denied.append(name);raise PermissionError('Private input denied by L1 v2 audit')
    def guarded_open(file,*args,**kwargs):
        check(file);return original_open(file,*args,**kwargs)
    def guarded_io(file,*args,**kwargs):
        check(file);return original_io(file,*args,**kwargs)
    def no_network(sock,address):
        if sock.family in (socket.AF_INET,socket.AF_INET6):
            network.append(str(address));raise PermissionError('All INET sockets denied by boundary audit')
        return original_connect(sock,address)
    offline_ml(REPORT/'v2/boundary-offline')
    original_connect=socket.socket.connect
    builtins.open=guarded_open;io.open=guarded_io;socket.socket.connect=no_network
    torch.set_num_threads(2);cv2.setNumThreads(1)
    model=Perception(REPORT/'v1/model/detector/weights/best.pt',REPORT/'v1/model/hud.npz',REPORT/'calibration.json',imgsz=640)
    offsets=json.loads((REPORT/'v2/model/marker-offsets.json').read_text())['offsets']
    temporal=TemporalEventDetector(REPORT/'v2/model/last.pt',model.geo,marker_offsets=offsets)
    results=[]
    for r in rows:
        image=cv2.imread(str(REPORT/'v2/dataset'/r['image']))
        frame=model.step(image,r['episode_id'],r['frame_id'],r['timestamp_ms'])
        result,_=temporal.step(image,frame);results.append(serialize_frame(result))
    builtins.open=original_open;io.open=original_io;socket.socket.connect=original_connect
    output.write_text(json.dumps(dict(passed=not denied,frames=len(rows),denied_read_attempts=denied,
        blocked_network_attempts=network,network_connections_succeeded=0,
        output_sha256=hashlib.sha256(json.dumps(results,sort_keys=True).encode()).hexdigest(),
        scope='Python file APIs deny labels, evaluation truth, native data/probe, protected derived-state source; INET sockets denied. OpenCV receives only allowlisted JPEG paths.'),indent=2)+'\n')
    print(output.read_text())


if __name__=='__main__':main()
