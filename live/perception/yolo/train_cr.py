"""YOLO v1 for LIVE units: fine-tune KataCR's CRDetectionModel (ultralytics 8.1.24 fork with a team/'belong' head) as ONE detector
over all 155 KataCR classes, on KataCR's on-the-fly synthetic generator mixed with REAL annotated frames.

Real frames: list files of `image_path label_path` pairs; images are KataCR arena crops (568x896; other sizes are resized), labels
`name_idx cx cy w h belong [...]` normalised (KataCR part2 format; our official frames via live/perception/yolo/official_to_cr.py).
Each generated sample is replaced by a real one with probability --p-real (weights per list via --real LIST:WEIGHT).

Never put EVAL-SPLIT held-out battles in a real list (reports/live/perception/EVAL-SPLIT.md); validation here is a KataCR part2 slice
(checkpoint plots only); candidates are scored on EVAL-SPLIT separately (eval_yolo.py).

  python train_cr.py --katacr-src SRC --dataset DATASET --init WEIGHTS.pt|yolov8m.pt --model yolov8l.yaml --out DIR \
      --real LIST:W [...] --p-real .35 --epochs 40 --datasize 6000 --batch 16 --workers 10
"""
import argparse
import os
import random
import sys
from pathlib import Path

import cv2
import numpy as np


def make_init(init, model_yaml, names, out):
    """Init checkpoint with nc = len(names): every shape-matching tensor from `init`, plus, for a KataCR detector, its class
    rows (last 1x1 conv of each cv3 branch) copied BY NAME, incl. the team channel ('padding_belong'). COCO inits keep a fresh head."""
    import torch
    from ultralytics.nn.tasks import attempt_load_one_weight
    from katacr.yolov8.custom_model import CRDetectionModel
    src, _ = attempt_load_one_weight(init)
    dst = CRDetectionModel(model_yaml, nc=len(names), verbose=False)
    dst.load(src)
    copied = 0
    if 'padding_belong' in src.names.values():
        idx = {n: i for i, n in names.items()}
        sh, dh = src.model[-1], dst.model[-1]
        with torch.no_grad():
            for k in range(len(dh.cv3)):
                sw, sb = sh.cv3[k][-1].weight, sh.cv3[k][-1].bias; dw, db = dh.cv3[k][-1].weight, dh.cv3[k][-1].bias
                for j, n in src.names.items():
                    if n in idx:
                        dw[idx[n]] = sw[j]; db[idx[n]] = sb[j]; copied += 1
    dst.names = names
    path = out/'init.pt'
    torch.save(dict(model=dst, train_args={}, date=None, version='8.1.24'), path)
    print(f'init {init} -> {path}: nc={len(names)}, head rows copied by name: {copied//3}', flush=True)
    return path


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--katacr-src', required=True); p.add_argument('--dataset', required=True)
    p.add_argument('--init', required=True); p.add_argument('--model', default='yolov8l.yaml'); p.add_argument('--out', required=True)
    p.add_argument('--name', default='v1'); p.add_argument('--real', action='append', default=[])
    p.add_argument('--p-real', type=float, default=.35); p.add_argument('--epochs', type=int, default=40)
    p.add_argument('--datasize', type=int, default=6000); p.add_argument('--batch', type=int, default=16)
    p.add_argument('--workers', type=int, default=10); p.add_argument('--val-list', required=True)
    p.add_argument('--device', default='0'); p.add_argument('--lr0', type=float, default=.002)
    p.add_argument('--imgsz', type=int, default=896); p.add_argument('--seed', type=int, default=0)
    p.add_argument('--optimizer', default='AdamW')
    p.add_argument('--box-up', type=float, default=0.,
                   help='extend every non-tower unit box UPWARD by this fraction of its height (bottom edge kept, so ground points are '
                        'unchanged): puts the level badge / HP bar above the unit inside the box the team head is trained on')
    p.add_argument('--owner-weight', type=float, default=1.,
                   help='weight of the team channel (last class channel, padding_belong) in the BCE class loss')
    p.add_argument('--share', action='store_true', help='--real LIST:W gives each list a total share W (not a per-item weight)')
    a = p.parse_args()
    sys.path.insert(0, a.katacr_src)
    # --- KataCR configuration overrides (one detector covering every class; our dataset path) ---
    import katacr.build_dataset.constant as kconst
    kconst.path_dataset = Path(a.dataset)
    import katacr.yolov8.cfg as kcfg
    kcfg.train_datasize = a.datasize; kcfg.noise_unit_ratio = 0; kcfg.num_detector = 1
    from katacr.constants.label_list import unit_list
    import katacr.yolov8.custom_dataset as kds
    kds.train_datasize, kds.noise_unit_ratio = a.datasize, 0

    import time
    state = dict(real=[], weights=None, mtimes=None, checked=0.)

    def load_real():
        """(Re)read the real lists when any file changed (checked every 60 s per worker): frames can be added mid-run."""
        if time.time()-state['checked'] < 60 and state['mtimes'] is not None:
            return
        state['checked'] = time.time()
        specs = [(spec.rsplit(':', 1)+['1'])[:2] for spec in a.real]
        mt = [Path(pth).stat().st_mtime if Path(pth).exists() else 0 for pth, _ in specs]
        if mt == state['mtimes']:
            return
        real = []
        for (pth, w), m in zip(specs, mt):
            if m:
                items = [ln.split()[:2] for ln in Path(pth).read_text().splitlines() if ln.strip()]
                # --share: W is the list's total share of real samples; else W is a per-item weight
                real += [(im, lb, float(w)/max(1, len(items)) if a.share else float(w)) for im, lb in items]
        wts = np.array([w for _, _, w in real], np.float64)
        state.update(real=real, weights=wts/wts.sum() if len(real) else wts, mtimes=mt)
        print(f'real frames: {len(real)} from {len(specs)} lists; p_real={a.p_real}', flush=True)
    load_real()
    W, H = kcfg.img_size  # (576, 896) in KataCR cfg: width, height
    Wk, Hk = 568, 896

    orig0 = kds.CRDataset.get_image_and_label
    from katacr.constants.label_list import tower_unit_list
    no_ext = {i for i, n in enumerate(unit_list) if n in set(tower_unit_list) | {'king-tower-bar', 'tower-bar', 'bar', 'bar-level',
                                                                                    'clock', 'emote', 'text', 'elixir', 'selected'}}

    def extend_up(label):
        if a.box_up <= 0 or label.get('instances') is None:
            return label
        inst = label['instances']; b = inst.bboxes  # xywh, normalised
        if len(b):
            cls = label['cls'][:, 0].astype(int)
            m = np.array([c not in no_ext for c in cls])
            dh = b[m, 3]*a.box_up
            dh = np.minimum(dh, np.maximum(0, b[m, 1]-b[m, 3]/2))  # stay inside the image
            b[m, 1] -= dh/2; b[m, 3] += dh
        return label

    def orig(self, index):
        return extend_up(orig0(self, index))

    def get_image_and_label(self, index):
        if self.img_path is not None or random.random() >= a.p_real:
            return orig(self, index)
        load_real()
        if not state['real']:
            return orig(self, index)
        from ultralytics.utils.instance import Instances
        im_path, lb_path, _ = state['real'][int(np.random.choice(len(state['real']), p=state['weights']))]
        img = cv2.imread(im_path)
        if img.shape[:2] != (Hk, Wk):
            img = cv2.resize(img, (Wk, Hk), interpolation=cv2.INTER_AREA)
        if (W, H) != (Wk, Hk):  # KataCR cfg size (576x896): pad right like its generator canvas
            img = cv2.copyMakeBorder(img, 0, H-Hk, 0, W-Wk, cv2.BORDER_CONSTANT, value=0)
        rows = [r.split() for r in Path(lb_path).read_text().splitlines() if r.strip()]
        lab = np.array([[float(x) for x in r[:6]] for r in rows], np.float32).reshape(-1, 6)
        if (W, H) != (Wk, Hk) and len(lab):  # renormalise from 568 to 576 width
            lab[:, 1] *= Wk/W; lab[:, 3] *= Wk/W
        cls = np.stack([lab[:, 0], lab[:, 5]], 1).astype(np.float32)
        return extend_up({'im_file': None, 'ratio_pad': (1.0, 1.0), 'rect_shape': np.array((H, W), np.float32), 'ori_shape': img.shape[:2],
                'resized_shape': img.shape[:2], 'cls': cls, 'bbox_format': 'xywh', 'img': img,
                'instances': Instances(lab[:, 1:5].copy(), np.zeros((0, 1000, 2), np.float32), None, 'xywh', True)})
    kds.CRDataset.get_image_and_label = get_image_and_label

    if a.owner_weight != 1.:
        import torch
        import katacr.yolov8.custom_model as kcm
        orig_init = kcm.CRDetectionLoss.__init__

        def init(self, model):
            orig_init(self, model)
            w = torch.ones(self.nc, device=self.device); w[-1] = a.owner_weight
            # a plain BCEWithLogitsLoss (picklable: ultralytics pickles the model incl. its criterion at every checkpoint)
            self.bce = torch.nn.BCEWithLogitsLoss(weight=w, reduction='none')
        kcm.CRDetectionLoss.__init__ = init
        print(f'owner (team channel) loss weight {a.owner_weight}', flush=True)
    from ultralytics.cfg import get_cfg
    from katacr.yolov8.train import YOLO_CR
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    # KataCR's head: last class channel = team ('padding_belong'), read by its loss/NMS as `belong`
    names = {i: n for i, n in enumerate(list(unit_list)+['padding_belong'])}
    data = out/'data.yaml'
    import yaml
    data.write_text(yaml.safe_dump(dict(path=str(Path(a.val_list).parent), train=None, val=Path(a.val_list).name, names=names)))
    model = YOLO_CR(str(make_init(a.init, a.model, names, out)), task='detect')
    cfg = dict(get_cfg(str(Path(a.katacr_src)/'katacr/yolov8/ClashRoyale.yaml')))
    cfg.update(data=str(data), project=str(out), name=a.name, epochs=a.epochs, batch=a.batch, workers=a.workers, device=a.device,
               imgsz=a.imgsz, lr0=a.lr0, seed=a.seed, optimizer=a.optimizer, cos_lr=True, warmup_epochs=1, exist_ok=True, patience=100, pretrained=False, plots=False, save_period=1,
               deterministic=False)
    cfg.pop('model', None)
    model.train(**cfg)


if __name__ == '__main__':
    os.environ.setdefault('NUMPY_MADVISE_HUGEPAGE', '0')
    main()
