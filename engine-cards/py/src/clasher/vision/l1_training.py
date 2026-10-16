"""L1 training adapters. Call offline_ml before importing this module."""
from copy import copy
import gc
import json
import re
import shutil
import subprocess
import time

import torch

from ultralytics.models.yolo.detect.train import DetectionTrainer
from ultralytics.models.yolo.detect.val import DetectionValidator
from ultralytics.utils import ops


class CompleteValidation(DetectionValidator):
    def postprocess(self, predictions):
        # MPS NMS repeatedly synchronizes for tiny indexing operations and can
        # hit Ultralytics' batch deadline, silently skipping later images.
        # Move the compact prediction tensor once, then return selected boxes.
        raw=predictions[0] if isinstance(predictions,(tuple,list)) else predictions
        result=ops.non_max_suppression(raw.cpu(), self.args.conf, self.args.iou,
            labels=[x.cpu() for x in self.lb], multi_label=True,
            agnostic=self.args.single_cls, max_det=self.args.max_det,max_time_img=float('inf'))
        return result

    def update_metrics(self, predictions, batch):
        # Variable-sized per-image box matching creates many tiny MPS graphs.
        # Keep both metric operands and retained statistics on CPU instead.
        cpu_batch=dict(batch)
        for key in ('batch_idx','cls','bboxes'):cpu_batch[key]=batch[key].cpu()
        device,iouv=self.device,self.iouv
        self.device=torch.device('cpu');self.iouv=iouv.cpu()
        try:
            return super().update_metrics(predictions,cpu_batch)
        finally:
            self.device,self.iouv=device,iouv


class L1Trainer(DetectionTrainer):
    def get_validator(self):
        self.loss_names='box_loss','cls_loss','dfl_loss'
        return CompleteValidation(self.test_loader,save_dir=self.save_dir,
                                  args=copy(self.args),_callbacks=self.callbacks)


def mps_memory_callbacks(output):
    """Bound cache accumulation and record host pressure during resumed fits."""
    calls=0
    def record(context, force=False):
        nonlocal calls
        calls+=1
        if not force and calls%25:return
        torch.mps.synchronize();gc.collect()
        before=torch.mps.driver_allocated_memory()
        torch.mps.empty_cache()
        swap=subprocess.check_output(['sysctl','-n','vm.swapusage'],text=True)
        used=float(re.search(r'used = ([\d.]+)M',swap).group(1))*1024**2
        free=shutil.disk_usage(output).free
        row=dict(time=time.time(),epoch=getattr(context,'epoch',None),calls=calls,
                 driver_before=before,driver_after=torch.mps.driver_allocated_memory(),
                 allocated=torch.mps.current_allocated_memory(),swap_used=used,disk_free=free)
        with (output/'mps-memory.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
        if used>14*1024**3 or free<4*1024**3:
            raise RuntimeError('L1 host resource guard: swap >14 GiB or free disk <4 GiB')
    return record,lambda context:record(context,True)
