"""Screen-only I/O for the dedicated official-client emulator.

No game state reads, hooks, app modifications, or private-reference imports.
Frame timestamps measure screenshot production, not game rendering.
"""
from __future__ import annotations
import argparse
from dataclasses import dataclass
import importlib.util
import json
from pathlib import Path
import subprocess
import threading
import time
import cv2
import grpc
import numpy as np

ROOT = Path(__file__).resolve().parent
SDK = Path.home()/'.cache/clasher-native-reference/android-sdk'
AVD = Path.home()/'.cache/clasher-official/avd/clasher_official_play_api35.avd'
NAME = 'clasher_official_play_api35'
SERIAL = 'emulator-5590'
WIDTH, HEIGHT = 720, 1280


def owned_pid():
    receipt = json.loads((ROOT/'ownership.json').read_text())
    pid = int(receipt['pid'])
    command = subprocess.check_output(['ps','-p',str(pid),'-o','command='],text=True)
    if f'-avd {NAME} ' not in command or '-port 5590 ' not in command:
        raise RuntimeError('Dedicated emulator ownership mismatch')
    return pid


def adb(*args, timeout=30):
    owned_pid()
    return subprocess.run([str(SDK/'platform-tools/adb'),'-s',SERIAL,*map(str,args)],
                          check=True,capture_output=True,timeout=timeout)


class Input:
    """Times are command completion, not game acceptance or visual feedback."""
    def __init__(self, log=None):
        self.log = Path(log) if log else ROOT/'input.jsonl'

    def _run(self, args, kind):
        started = time.perf_counter()
        adb('shell',*args)
        end = time.perf_counter()
        row = {'kind':kind,'args':args,'started_monotonic':started,
               'completed_monotonic':end,'command_ms':1000*(end-started)}
        with self.log.open('a') as f: f.write(json.dumps(row)+'\n')
        return row

    @staticmethod
    def point(x,y):
        x,y=int(x),int(y)
        if not 0<=x<WIDTH or not 0<=y<HEIGHT: raise ValueError('Point outside display')
        return x,y

    def tap(self,x,y):
        x,y=self.point(x,y)
        return self._run(['input','tap',str(x),str(y)],'tap')

    def drag(self,x1,y1,x2,y2,duration_ms=250):
        x1,y1=self.point(x1,y1);x2,y2=self.point(x2,y2)
        if not 1<=duration_ms<=2000: raise ValueError('Drag duration out of range')
        return self._run(['input','swipe',*map(str,[x1,y1,x2,y2,duration_ms])],'drag')

    def play(self,slot,x,y,calibration):
        if not calibration.get('validated'): raise ValueError('Unvalidated game calibration')
        if slot not in range(4): raise ValueError('Slot must be 0..3')
        sx,sy=self.point(*calibration['hand_centers'][slot]);x,y=self.point(x,y)
        # One shell call, two ordinary sequential Android input commands.
        return self._run(['input','tap',str(sx),str(sy),';','input','tap',str(x),str(y)],'card_then_arena')


@dataclass(frozen=True)
class Frame:
    sequence:int
    produced_at:float
    received_at:float
    received_monotonic:float
    pixels:np.ndarray


class Capture:
    """Authenticated emulator screenshot stream with a bounded one-frame buffer.

    Optional sink sees every delivered frame before the latest-frame buffer; a
    slow sink can reduce acquisition rate. Sequence gaps expose consumer drops.
    """
    def __init__(self,sink=None,width=360,height=640):
        pid=owned_pid()
        settings=dict(line.strip().split('=',1) for line in
            (Path.home()/f'Library/Caches/TemporaryItems/avd/running/pid_{pid}.ini').read_text().splitlines()
            if '=' in line and not line.lstrip().startswith('#'))
        if settings.get('grpc.port')!='8590': raise RuntimeError('gRPC port mismatch')
        token=settings.get('grpc.token')
        if not token: raise RuntimeError('gRPC authentication token missing')
        spec=importlib.util.spec_from_file_location('official_emulator_pb2',ROOT/'grpc/emulator_controller_pb2.py')
        pb=importlib.util.module_from_spec(spec);spec.loader.exec_module(pb)
        self.channel=grpc.insecure_channel('127.0.0.1:8590',options=[('grpc.max_receive_message_length',8*1024*1024)])
        method=self.channel.unary_stream('/android.emulation.control.EmulatorController/streamScreenshot',
            request_serializer=pb.ImageFormat.SerializeToString,response_deserializer=pb.Image.FromString)
        self.rpc=method(pb.ImageFormat(format=pb.ImageFormat.RGB888,width=width,height=height),
            metadata=(('authorization','Bearer '+token),))
        self.width,self.height=width,height
        self.condition=threading.Condition();self.stopped=False;self.latest=None;self.error=None
        self.count=0;self.sink=sink
        self.thread=threading.Thread(target=self._run,daemon=True);self.thread.start()

    def _run(self):
        try:
            for image in self.rpc:
                if self.stopped: break
                if not image.image: continue
                received=time.time();mono=time.perf_counter()
                if (image.format.width,image.format.height)!=(self.width,self.height):
                    raise ValueError('Unexpected screenshot dimensions')
                pixels=np.frombuffer(image.image,np.uint8).reshape(self.height,self.width,3)
                self.count+=1
                frame=Frame(self.count,image.timestampUs/1e6,received,mono,cv2.cvtColor(pixels,cv2.COLOR_RGB2BGR))
                if self.sink:self.sink(frame)
                with self.condition:self.latest=frame;self.condition.notify_all()
        except BaseException as exc:
            if not self.stopped:
                with self.condition:self.error=exc;self.condition.notify_all()

    def read(self,after=0,timeout=15):
        deadline=time.monotonic()+timeout
        with self.condition:
            while True:
                if self.error: raise RuntimeError('Capture failed') from self.error
                if self.latest is not None and self.latest.sequence>after:return self.latest
                remaining=deadline-time.monotonic()
                if remaining<=0 or self.stopped:raise TimeoutError('No new screenshot')
                self.condition.wait(remaining)

    def close(self):
        self.stopped=True;self.rpc.cancel();self.channel.close()
        with self.condition:self.condition.notify_all()
        self.thread.join(timeout=5)
        if self.thread.is_alive():raise RuntimeError('Capture thread did not stop')
    def __enter__(self):return self
    def __exit__(self,*_):self.close()


class ScreenStates:
    """Fail closed on unknown screens. Templates must be real client crops.

    Entries: state, image, roi=[x,y,w,h] in 720x1280 coordinates, threshold.
    A state requires all of its configured anchors. No templates means unknown.
    """
    def __init__(self,path=ROOT/'states.json'):
        self.path=Path(path)
        self.config=json.loads(self.path.read_text())
        self.entries=[]
        for anchor in self.config['anchors']:
            template=cv2.imread(str(self.path.parent/anchor['image']))
            if template is None: raise ValueError('Missing state template')
            self.entries.append((anchor,template))
    def recognize(self,pixels):
        if not self.config.get('validated'):
            return {'state':'unknown','scores':{},'reason':'unvalidated templates'}
        full=cv2.resize(pixels,(WIDTH,HEIGHT))
        scores={}
        for anchor,template in self.entries:
            x,y,w,h=anchor['roi'];crop=full[y:y+h,x:x+w]
            if crop.shape!=template.shape: raise ValueError('Template/ROI mismatch')
            score=float(cv2.matchTemplate(crop,template,cv2.TM_SQDIFF_NORMED)[0,0])
            scores.setdefault(anchor['state'],[]).append((score,anchor['threshold']))
        matches=[state for state,vals in scores.items() if all(s<t for s,t in vals)]
        return {'state':matches[0] if len(matches)==1 else 'unknown','scores':scores}


def tile_to_pixel(x,y,calibration):
    if not calibration.get('validated'):raise ValueError('Unvalidated game calibration')
    if not 0<=x<=18 or not 0<=y<=32:raise ValueError('Tile outside arena')
    m=np.asarray(calibration['homography'],dtype=float)
    p=m@np.array([x,y,1.]);return Input.point(*(p[:2]/p[2]))


def benchmark(seconds,output):
    ages=[];times=[]
    def sink(frame):
        ages.append((frame.received_at-frame.produced_at)*1000);times.append(frame.received_monotonic)
    with Capture(sink) as stream:
        stream.read();time.sleep(seconds)
    if len(times)<2:raise RuntimeError('Insufficient frames')
    report={'frames':len(times),'seconds':times[-1]-times[0],
            'fps':(len(times)-1)/(times[-1]-times[0]),
            'screenshot_production_to_receipt_ms':{'mean':float(np.mean(ages)),
                'p50':float(np.quantile(ages,.5)),'p95':float(np.quantile(ages,.95)),
                'p99':float(np.quantile(ages,.99))},
            'dimensions':[360,640],'game_render_latency_ms':None,
            'scope':'Emulator screenshot timestamp to host receipt; no certified game render fence'}
    Path(output).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--benchmark',type=float,default=10)
    p.add_argument('--output',type=Path,default=ROOT/'capture-benchmark.json');a=p.parse_args()
    benchmark(a.benchmark,a.output)
