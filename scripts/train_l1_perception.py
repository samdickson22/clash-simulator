"""Train offline L1 YOLOv8n and HUD models exclusively on training matches."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

# These checkpoints are produced locally by this script, not arbitrary inputs.
os.environ['TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD'] = '1'
os.environ['YOLO_OFFLINE'] = 'true'
os.environ['YOLO_AUTOINSTALL'] = 'false'

import cv2
import torch
import yaml

from clasher.vision.l1 import ARENA, crop
from clasher.vision.l1_perception import train_hud
from clasher.vision.l1_offline import offline_ml


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dataset',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--epochs',type=int,default=40)
    p.add_argument('--imgsz',type=int,default=416)
    p.add_argument('--batch',type=int,default=8)
    p.add_argument('--initialize',type=Path)
    p.add_argument('--v1-augmentation',action='store_true')
    args=p.parse_args()
    if not (args.dataset/'complete.json').exists():
        raise ValueError('Collection must complete before fitting')
    args.output.mkdir(parents=True,exist_ok=False)
    rows=[json.loads(l) for l in (args.dataset/'labels.jsonl').read_text().splitlines()]
    train=[r for r in rows if r['split']=='train']
    val=[r for r in rows if r['split']=='validation']
    if not train or not val:
        raise ValueError('Training and validation matches are required')
    split_keys={}
    for e in json.loads((args.dataset/'manifest.json').read_text())['matches']:
        for deck in e['decks']:
            key=tuple(sorted(deck))
            if key in split_keys and split_keys[key] != e['split']:
                raise ValueError('Deck leakage across splits')
            split_keys[key]=e['split']
    # P16 has thirteen body cards and three spells. Spells require a separate
    # visible-phase annotation pass; they are never relabelled as body boxes.
    from clasher.rl.native_public_observation import SUPPORTED_BODY_CARDS
    classes=[f'{owner}:{card}' for owner in (0,1) for card in sorted([*SUPPORTED_BODY_CARDS,'Tower','KingTower'])]
    counts={name:0 for name in classes}
    yolo_root=args.output.parent/(args.output.name+'-data') if args.v1_augmentation else args.output/'yolo'
    for split, subset in [('train',train),('val',val)]:
        for sub in ('images','labels'):
            (yolo_root/sub/split).mkdir(parents=True)
        for r in subset:
            stem=Path(r['image']).stem
            image=cv2.imread(str(args.dataset/r['image']))
            if args.v1_augmentation and split=='train':
                import numpy as np
                rng=np.random.default_rng(int(hashlib.sha256(stem.encode()).hexdigest()[:8],16))
                if rng.random()<.3:image=cv2.GaussianBlur(image,(3,3),float(rng.uniform(.3,.9)))
                if rng.random()<.5:
                    ok,encoded=cv2.imencode('.jpg',image,[cv2.IMWRITE_JPEG_QUALITY,int(rng.integers(45,86))])
                    if not ok:raise RuntimeError('Augmentation encoding failed')
                    image=cv2.imdecode(encoded,cv2.IMREAD_COLOR)
            cv2.imwrite(str(yolo_root/'images'/split/(stem+'.jpg')),crop(image,ARENA),
                        [cv2.IMWRITE_JPEG_QUALITY,87])
            labels=[]
            for e in r['targets']['entities']:
                name=f'{e["player_id"]}:{e["card"]}'
                x1,y1,x2,y2=e['pixel_box']
                x1,x2=max(0,x1),min(540,x2)
                y1,y2=max(0,y1-200),min(800,y2-200)
                if x2<=x1 or y2<=y1:
                    continue
                labels.append(f'{classes.index(name)} {(x1+x2)/1080:.7f} {(y1+y2)/1600:.7f} {(x2-x1)/540:.7f} {(y2-y1)/800:.7f}')
                if split=='train': counts[name]+=1
            (yolo_root/'labels'/split/(stem+'.txt')).write_text('\n'.join(labels)+'\n')
    data=args.output/'data.yaml'
    missing=[name for name,count in counts.items() if count==0]
    if missing:
        raise ValueError(f'Body classes without training support: {missing}')
    data.write_text(yaml.safe_dump(dict(path=str(yolo_root.resolve()),
                                       train='images/train',val='images/val',names=classes)))
    hud_rows=rows
    if args.v1_augmentation:
        import random
        from bisect import bisect_left, bisect_right
        from collections import defaultdict
        episodes=defaultdict(list)
        for row in train:episodes[row['episode_id']].append(row)
        hud_rows=[]
        for episode in episodes.values():
            episode.sort(key=lambda row:row['timestamp_ms'])
            times=[row['timestamp_ms'] for row in episode]
            for i,row in enumerate(episode):
                hand=row['targets']['own_hand']
                start=bisect_left(times,row['timestamp_ms']-500)
                end=bisect_right(times,row['timestamp_ms']+500)
                if all(other['targets']['own_hand']==hand for other in episode[start:end]):
                    hud_rows.append(row)
        random.Random(261005).shuffle(hud_rows)
    hud=train_hud(hud_rows,args.dataset,args.output/'hud.npz',max_per_value=100 if args.v1_augmentation else None)
    hud['eligible_frames']=sum(row['split']=='train' for row in hud_rows)
    manifest=dict(train_frames=len(train),validation_frames=len(val),classes=counts,hud=hud,
                  label_sha256=hashlib.sha256((args.dataset/'labels.jsonl').read_bytes()).hexdigest(),
                  device='mps',pretrained=bool(args.initialize),external_weights=False,epochs=args.epochs,
                  imgsz=args.imgsz,batch=args.batch,compression_blur=args.v1_augmentation,
                  initialization=None if args.initialize is None else dict(path=str(args.initialize),sha256=hashlib.sha256(args.initialize.read_bytes()).hexdigest()),
                  targets='weak ground-anchor boxes; no private HUD labels')
    source_root=Path(__file__).resolve().parents[1]
    source_paths=[Path(__file__),*sorted((source_root/'src/clasher/vision').glob('*.py'))]
    manifest['sources']={str(p.relative_to(source_root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths}
    manifest['torch_version']=torch.__version__
    (args.output/'training_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    if not torch.backends.mps.is_available():
        raise RuntimeError('L1 requires MPS')
    torch.set_num_threads(2)
    offline_ml(args.output/'ultralytics-config')
    from ultralytics import YOLO
    from ultralytics.utils import SETTINGS
    SETTINGS.update({'sync':False,'wandb':False,'comet':False,'mlflow':False,'clearml':False})
    model=YOLO(str(args.initialize) if args.initialize else 'yolov8n.yaml')
    options={}
    if args.v1_augmentation:
        from clasher.vision.l1_training import L1Trainer
        options['trainer']=L1Trainer
    model.train(**options,data=str(data.resolve()),epochs=args.epochs,imgsz=args.imgsz,batch=args.batch,device='mps',
                workers=0,cache=False,project=str(args.output.resolve()),name='detector',exist_ok=False,
                pretrained=False,amp=False,plots=False,save=True,save_period=-1,patience=15,
                optimizer='AdamW',lr0=.002,weight_decay=.0005,warmup_epochs=2,
                mosaic=0,fliplr=0,flipud=0,translate=.05,scale=.15,hsv_h=.01,hsv_s=.15,hsv_v=.15,
                seed=261004,deterministic=True,verbose=False)
    size=sum(p.stat().st_size for p in args.output.rglob('*.pt'))
    if size>=1024**3:
        raise RuntimeError('Model disk budget exceeded')
    (args.output/'complete.json').write_text(json.dumps(dict(status='complete',checkpoint_bytes=size),indent=2)+'\n')


if __name__=='__main__':
    main()
