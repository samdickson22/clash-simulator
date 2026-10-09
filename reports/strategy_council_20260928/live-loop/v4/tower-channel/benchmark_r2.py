"""Final deployed-artifact timing on admitted FIT crops, without native labels."""
import json,sys,time
from pathlib import Path
import cv2,numpy as np
from extract import sha
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'src'))
from clasher.live.tower_channel import TowerChannel
root=Path(sys.argv[1]);model=root/'deployed-templates.json';manifest=json.loads((root/'manifest.json').read_text());cv2.setNumThreads(1)
c=TowerChannel(model);samples=[]
for ep in manifest['fit'][:8]:
    d=np.load(root/(ep+'.npz'));sprites,panels=d['sprite'],d['panel'];rows=json.loads((root/(ep+'.json')).read_text())['rows'];stamp=0
    for i in range(0,len(rows),6):
        if i+6>len(rows):continue
        image=np.zeros((1140,540,3),np.uint8)
        for s,(x,y) in enumerate(c.centers):
            image[y-95:y+55,x-48:x+48]=sprites[i+s]
        for s,(x,y) in enumerate(c.centers):
            offset=(-130 if s%3 == 0 else -110) if s<3 else (20 if s%3 == 0 else -25)
            image[y+offset:y+offset+80,x-55:x+55]=panels[i+s]
        t=time.perf_counter_ns();c.step(image,ep,stamp);elapsed=(time.perf_counter_ns()-t)/1e6;stamp+=50
        if i>=96:samples.append(elapsed)
r=dict(host='127x03',nice=10,workers=1,cpu_only=True,model_sha256=sha(model),source_sha256=sha(Path(__file__).resolve().parents[5]/'src/clasher/live/tower_channel.py'),scope='Reconstructed six-slot canvases from first eight fit episodes; measures all crops/OCR/bars/activation/confirmation/observation construction, excludes canvas assembly and I/O',samples=len(samples),mean_ms=float(np.mean(samples)),p95_ms=float(np.quantile(samples,.95)),p99_ms=float(np.quantile(samples,.99)))
(root/'benchmark.json').write_text(json.dumps(r,indent=2)+'\n');print(r,flush=True)
