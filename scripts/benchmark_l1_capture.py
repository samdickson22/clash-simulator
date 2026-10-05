"""Measure owned offline adb capture through complete screen perception."""
import argparse
import json
import os
import struct
import subprocess
import time
from pathlib import Path

os.environ['TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD']='1'

import cv2
import numpy as np
import torch

from smoke_reference_battle import request
from clasher.vision.l1 import public_pixels
from clasher.vision.l1_offline import offline_ml
from clasher.vision.l1_perception import Perception,serialize_frame,clock_digits

ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/'reports/strategy_council_20260928/live-loop/l1'
ADB=Path.home()/'.cache/clasher-native-reference/android-sdk/platform-tools/adb'


def grab(serial,kind):
    command=[str(ADB),'-s',serial,'exec-out','screencap']
    if kind=='png':command.append('-p')
    raw=subprocess.check_output(command,timeout=30)
    if kind=='png':return cv2.imdecode(np.frombuffer(raw,np.uint8),cv2.IMREAD_COLOR)
    width,height,fmt=struct.unpack_from('<III',raw)
    if (width,height,fmt)!=(1080,2280,1):
        raise ValueError(f'Unrecognized raw screen format {width,height,fmt}')
    offset=len(raw)-width*height*4
    if offset not in (12,16):raise ValueError('Unrecognized screencap header')
    rgba=np.frombuffer(raw,np.uint8,offset=offset).reshape(height,width,4)
    return cv2.cvtColor(rgba,cv2.COLOR_RGBA2BGR)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--samples',type=int,default=10)
    p.add_argument('--ownership',type=Path,default=REPORT/'emulator/complete.json')
    args=p.parse_args()
    if not (REPORT/'pipeline-complete.json').exists():
        raise RuntimeError('Wait for collection/training/evaluation to finish')
    receipt=json.loads(args.ownership.read_text())
    serial,port=receipt['serial'],receipt['probe_port']
    cmd=subprocess.check_output(['ps','-p',str(receipt['pid']),'-o','command='],text=True)
    if 'clasher_reference_api35' not in cmd or f'-port {serial.split("-")[-1]}' not in cmd:
        raise ValueError('Owned emulator identity differs')
    for firewall in ('iptables','ip6tables'):
        subprocess.run([str(ADB),'-s',serial,'shell',firewall,'-C','OUTPUT','-m','owner',
                        '--uid-owner',str(receipt['app_uid']),'!','-o','lo','-j','REJECT'],
                       capture_output=True,check=True,timeout=20)
    c=json.loads((REPORT/'dataset/manifest.json').read_text())['matches'][0]['config']
    c['rndSeed']=261004999
    r=request(port,'configure-native '+json.dumps(c,separators=(',',':')))
    deadline=time.monotonic()+30
    while time.monotonic()<deadline:
        s=request(port,'status')
        if s['nativeRenderReady'] and s['nativeRenderLoaded']==r['sequence']:break
        time.sleep(.1)
    else:raise TimeoutError('Render scene unavailable')
    paused=request(port,'pause');request(port,'speed 1')
    if paused['tick']>=200:raise ValueError('Startup missed timing boundary')
    request(port,f"advance-native {200-paused['tick']}")
    offline_ml(REPORT/'capture-benchmark-config')
    torch.set_num_threads(2)
    model=Perception(REPORT/'model/detector/weights/best.pt',REPORT/'model/hud.npz',REPORT/'calibration.json')
    image=public_pixels(grab(serial,'png'))
    if not clock_digits(image):raise ValueError('Benchmark HUD hidden')
    for i in range(3):model.step(image,'warmup',str(i),i*100)
    results={}
    for kind in ('png','raw'):
        samples=[];acquisition=[]
        for i in range(args.samples):
            torch.mps.synchronize();started=time.perf_counter()
            image=public_pixels(grab(serial,kind));acquisition.append(time.perf_counter()-started)
            frame=model.step(image,'capture-'+kind,str(i),i*1000)
            json.dumps(serialize_frame(frame),allow_nan=False)
            torch.mps.synchronize();samples.append(time.perf_counter()-started)
        results[kind]=dict(samples=args.samples,fps=args.samples/sum(samples),
                           capture_mean_ms=float(np.mean(acquisition)*1000),
                           total_mean_ms=float(np.mean(samples)*1000),
                           total_p99_ms=float(np.quantile(samples,.99)*1000))
    results['scope']='adb screencap + decode + privacy sanitizer/downscale + YOLO/HUD/HP/tracking + PublicVisionFrame validation + JSON serialization; paused offline frame; synchronized MPS; no native truth in inference'
    (REPORT/'capture-timing.json').write_text(json.dumps(results,indent=2)+'\n')
    print(json.dumps(results))


if __name__=='__main__':main()
