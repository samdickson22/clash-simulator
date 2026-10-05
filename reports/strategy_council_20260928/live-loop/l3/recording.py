"""Save every delivered screenshot at its original cadence, downscaled to 360x640."""
from fractions import Fraction
from pathlib import Path
import json
import time
import av
from official_loop import ROOT

class Recorder:
    def __init__(self,path,max_bytes=250_000_000):
        self.path=Path(path)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        if self.path.exists():raise FileExistsError(self.path)
        self.max_bytes=max_bytes
        self.container=av.open(str(self.path),'w')
        self.stream=self.container.add_stream('libx264',rate=60)
        self.stream.width=360;self.stream.height=640;self.stream.pix_fmt='yuv420p'
        self.stream.time_base=Fraction(1,90000)
        self.stream.codec_context.time_base=Fraction(1,90000)
        self.stream.options={'crf':'28','preset':'ultrafast','tune':'zerolatency'}
        self.frames=0;self.first=None;self.previous=-1;self.last_check=0
        self.sidecar=self.path.with_suffix('.frames.jsonl').open('x')

    def __call__(self,frame):
        if frame.pixels.shape[:2]!=(640,360):raise ValueError('Recording requires 360x640')
        if time.monotonic()-self.last_check>1:
            total=sum(p.stat().st_size for p in (ROOT/'recordings').glob('*.mp4'))
            if total>=950_000_000 or (self.path.stat().st_size if self.path.exists() else 0)>=self.max_bytes:
                raise RuntimeError('Recording storage cap reached')
            self.last_check=time.monotonic()
        if self.first is None:self.first=frame.produced_at
        pts=max(self.previous+1,round((frame.produced_at-self.first)*90000))
        picture=av.VideoFrame.from_ndarray(frame.pixels,format='bgr24')
        picture.pts=pts;picture.time_base=Fraction(1,90000)
        for packet in self.stream.encode(picture):self.container.mux(packet)
        self.sidecar.write(json.dumps({'sequence':frame.sequence,'pts':pts,
            'produced_at':frame.produced_at,'received_at':frame.received_at})+'\n')
        self.frames+=1;self.previous=pts

    def close(self):
        for packet in self.stream.encode():self.container.mux(packet)
        self.container.close();self.sidecar.close()
    def __enter__(self):return self
    def __exit__(self,*_):self.close()
