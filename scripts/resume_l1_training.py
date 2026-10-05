"""Resume an owned L1 checkpoint with a smaller, bounded MPS allocation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import time

os.environ['TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD']='1'
os.environ['PYTORCH_MPS_HIGH_WATERMARK_RATIO']='0.4'
os.environ['PYTORCH_MPS_LOW_WATERMARK_RATIO']='0.25'

import torch
from clasher.vision.l1_offline import offline_ml


class EpochCheckpointReady(Exception):
    pass


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--one-epoch',action='store_true')
    a=p.parse_args();manifest=json.loads((a.output/'training_manifest.json').read_text())
    dataset=a.output.parent/'dataset-merged'
    if hashlib.sha256((dataset/'labels.jsonl').read_bytes()).hexdigest()!=manifest['label_sha256']:
        raise ValueError('Training labels changed since the original fit')
    if (a.output/'complete.json').exists():raise ValueError('Training is already complete')
    checkpoint=a.output/'detector/weights/last.pt'
    backup=a.output.parent/'checkpoint-epoch1.pt'
    if not backup.exists():shutil.copyfile(checkpoint,backup)
    for name in ('producer-sources.json','producer-sources.zip'):
        initial=a.output.parent/name.replace('.', '-initial.',1)
        if not initial.exists():shutil.copyfile(a.output.parent/name,initial)
    offline_ml(a.output/'ultralytics-config');torch.set_num_threads(2)
    from ultralytics import YOLO
    from clasher.vision.l1_training import L1Trainer,mps_memory_callbacks
    source_root=Path(__file__).resolve().parents[1]
    sources=[Path(__file__),source_root/'src/clasher/vision/l1_training.py']
    model=YOLO(str(checkpoint))
    completed_epoch=model.ckpt['epoch']+1
    backup=a.output.parent/f'checkpoint-epoch{completed_epoch}.pt'
    if not backup.exists():shutil.copyfile(checkpoint,backup)
    record=dict(started_at=time.time(),checkpoint_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
                batch=8,high_watermark_ratio=.4,low_watermark_ratio=.25,
                cache_cleanup_every_batches=25,completed_epoch=completed_epoch,
                discarded_partial_epoch=completed_epoch+1,
                sources={str(p.relative_to(source_root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
    (a.output/'resume_manifest.json').write_text(json.dumps(record,indent=2)+'\n')
    with (a.output/'resume_history.jsonl').open('a') as f:f.write(json.dumps(record)+'\n')
    batch_callback,epoch_callback=mps_memory_callbacks(a.output)
    model.add_callback('on_train_batch_end',batch_callback)
    model.add_callback('on_train_epoch_end',epoch_callback)
    model.add_callback('on_val_end',epoch_callback)
    if a.one_epoch:
        def checkpoint_boundary(trainer):
            if trainer.epoch+1<trainer.epochs:
                raise EpochCheckpointReady(trainer.epoch+1)
        model.add_callback('on_model_save',checkpoint_boundary)
    try:
        model.train(resume=True,batch=8,trainer=L1Trainer)
    except EpochCheckpointReady as done:
        (a.output/'epoch-phase.json').write_text(json.dumps(dict(completed_epoch=done.args[0],
            checkpoint_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest(),at=time.time()))+'\n')
        return 75  # A complete checkpoint, not a complete six-epoch fit.
    size=sum(p.stat().st_size for p in a.output.rglob('*.pt'))
    if size>=1024**3:raise RuntimeError('Model disk budget exceeded')
    (a.output/'complete.json').write_text(json.dumps(dict(status='complete',checkpoint_bytes=size,resumed=True))+'\n')


if __name__=='__main__':raise SystemExit(main())
