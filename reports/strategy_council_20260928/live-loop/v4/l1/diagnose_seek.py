"""Bounded train-only evidence for OpenCV VFR frame-number seek drift."""
import argparse,json
from pathlib import Path
import cv2
import numpy as np


def main():
    p=argparse.ArgumentParser();p.add_argument('--match',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    r=json.loads((a.match/'receipt.json').read_text())
    if r['split'] not in ('train','validation'):raise ValueError('Heldout forbidden')
    cv2.setNumThreads(1);target=1867;video=str(a.match/'video.mp4')
    cap=cv2.VideoCapture(video,cv2.CAP_FFMPEG,[cv2.CAP_PROP_N_THREADS,1]);frames={}
    for i in range(target+5):
        ok,img=cap.read()
        if not ok:raise ValueError('truncated')
        if i>=target-4:frames[i]=img
    cap.release();rows=[]
    for start in (target-4,target):
        cap=cv2.VideoCapture(video,cv2.CAP_FFMPEG,[cv2.CAP_PROP_N_THREADS,1]);cap.set(cv2.CAP_PROP_POS_FRAMES,start)
        for i in range(start,target+1):
            ok,img=cap.read()
            if not ok:raise ValueError('truncated')
        rows.append(dict(seek_start=start,requested=target,equal_to_sequential=[i for i,x in frames.items() if np.array_equal(x,img)],
                         unequal_elements=int(np.count_nonzero(frames[target]!=img)),reported_frame=cap.get(cv2.CAP_PROP_POS_FRAMES),reported_ms=cap.get(cv2.CAP_PROP_POS_MSEC)))
        cap.release()
    a.output.write_text(json.dumps(dict(opencv=cv2.__version__,rows=rows,heldout_opened=False),indent=2)+'\n')
    print(json.dumps(rows),flush=True)


if __name__=='__main__':main()
