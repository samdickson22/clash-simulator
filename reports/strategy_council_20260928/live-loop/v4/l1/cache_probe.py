"""Bounded real-media lossless cache size/decompression probe."""
import argparse
import json
from pathlib import Path
import time
import zlib
import cv2
import numpy as np
from clasher.vision.l1_v4 import prepare_pixels


def main():
    p=argparse.ArgumentParser();p.add_argument('--match',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    r=json.loads((a.match/'receipt.json').read_text())
    if r['split'] not in ('train','validation'):raise ValueError('Heldout forbidden')
    cv2.setNumThreads(1)
    cap=cv2.VideoCapture(str(a.match/'video.mp4'),cv2.CAP_FFMPEG,[cv2.CAP_PROP_N_THREADS,1])
    rows=[]
    for start in (0, min(1500,r['frames']-64),r['frames']-64):
        cap.set(cv2.CAP_PROP_POS_FRAMES,start)
        raw=[];pixels=[]
        for _ in range(64):
            ok,img=cap.read()
            if not ok:raise ValueError('Truncated')
            arena,hud=prepare_pixels(img)
            raw.append(img.ravel());pixels.append(np.concatenate((arena.ravel(),hud.ravel())))
        for name,frames in [('raw',raw),('pixels',pixels)]:
            for block in (1,4,16,64):
                for level in (1,6):
                    size=0;encode=0.;decode=0.
                    for i in range(0,len(frames),block):
                        x=np.stack(frames[i:i+block]);t=time.perf_counter()
                        delta=np.concatenate((x[:1],np.bitwise_xor(x[1:],x[:-1])))
                        blob=zlib.compress(delta.tobytes(),level);encode+=time.perf_counter()-t;size+=len(blob)
                        t=time.perf_counter();y=np.frombuffer(zlib.decompress(blob),np.uint8).reshape(x.shape)
                        y=np.bitwise_xor.accumulate(y,axis=0);decode+=time.perf_counter()-t
                        assert np.array_equal(x,y)
                    rows.append(dict(start=start,format=name,block=block,level=level,bytes_per_frame=size/64,
                                     encode_fps=64/encode,decode_fps=64/decode))
    cap.release()
    a.output.write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps(rows),flush=True)


if __name__=='__main__':main()
