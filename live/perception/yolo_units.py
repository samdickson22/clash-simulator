"""YOLO unit detector for the live loop: an Ultralytics-style detector + a class mapping -> the record's `units` (and the
additive `unknown_units`) in exactly the LivePerception format. Our frame model keeps hand, elixir, towers, clock and events;
only `units` are replaced (drive.py --units yolo:<model>:<classes.json>[:k=v,...]).

  y = from_spec('yolo:yolo-v2m-e2-896x576-fp16.mlpackage:live/yolo_synth/classes.json:offsets=ground-offsets.json')
  out = y.step(android_bgr)      # the driver's normalized official frame (any size, 9:16; drive.normalize(to_android(..)))
  out['units'], out['unknown_units'], out['units_yolo'] (the detector class name per unit)

Matches the r3 owner's reference, live/perception/yolo/eval_yolo.py predict():
* Crop: capture box (42.2, 31.3)-(674.2, 1019.3) in 720x1280 px, scaled to the frame size, INTER_AREA warp to 568x896
  (KataCR arena crop; tile grid at (6, 64)-(562, 864)); Ultralytics letterbox into the model input (896x576: 4 px of
  gray 114 each side; smaller inputs resize first).
* Head (format auto): KataCR CRDetectionModel = class channels + a last team channel 'padding_belong' (> .5 = opponent;
  class = argmax over the others), or a plain head with id = 2*name_idx + team over the class list. Class-wise NMS iou .6,
  threshold conf .5 (KataCR custom_utils.non_max_suppression).
* Units only: drop NON_UNIT (eval_yolo.py) + KataCR spell_unit_list + object_unit_list (+ any name whose mapping kind is
  not troop/building). Identity: mapping identity (perception vocab body) -> `units` {cls, card, owner, x, y, hp_frac: None,
  score}; identity null / 'unknown_unit' or a name missing from the mapping -> `unknown_units` {owner, kind, x, y, score}.
* Ground point (tiles): x = ((x1+x2)/2 - 6)/30.889 + dx, y_top = (y2 - 64)/25 + dy in crop px, record y = 32 - y_top;
  (dx, dy) per class from ground-offsets.json (spec offsets=), fallback dy: KataCR flyers +.56, buildings -.8, else -.05.
* Owner: team 0 = ours -> record owner 0.

Models: .mlpackage (CoreML; cu=ne|gpu|cpu|all), .torchscript (device=cpu|mps), .pt (needs ultralytics, $KATACR_SRC). Class
names from the model metadata ('names'), a `<model>.meta.json` sidecar, or the mapping. Input range: metadata
'input_range' '0-255' (our exports divide inside the model), else 0..1.
Mapping: classes.json ({"names": [{name, kind, identity, card, air}, ...]}, live/yolo_synth) or {"classes": {name: {identity,
unit, kind, air}}} (katacr_to_clasher.json).
"""
import ast
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2
import numpy as np

TEAM_NAMES = ('padding_belong', 'belong', 'team')
CROP_720 = (42.2, 31.3, 674.2, 1019.3)        # r3 interface: capture box -> KataCR 568x896 arena crop
WK, HK = 568, 896
GX0, GY0, CELL_W, CELL_H = 6., 64., 30.889, 25.
NON_UNIT = {'king-tower', 'queen-tower', 'cannoneer-tower', 'dagger-duchess-tower', 'dagger-duchess-tower-bar', 'tower-bar',
            'king-tower-bar', 'bar', 'bar-level', 'clock', 'emote', 'text', 'elixir', 'selected', 'skeleton-king-bar'}
SPELL_UNITS = {'arrows', 'clone', 'earthquake', 'fireball', 'freeze', 'giant-snowball', 'goblin-barrel', 'graveyard', 'lightning',
               'poison', 'rage', 'rocket', 'skeleton-king-skill', 'tesla-evolution-shock', 'tornado', 'zap'}
OBJECT_UNITS = {'axe', 'dirt', 'goblin-ball', 'bomb'}
DROP = NON_UNIT | SPELL_UNITS | OBJECT_UNITS
FLYING = {'arrows', 'axe', 'baby-dragon', 'bat', 'bat-evolution', 'flying-machine', 'fireball', 'giant-snowball', 'goblin-ball',
          'goblin-barrel', 'inferno-dragon', 'lightning', 'mega-minion', 'minion', 'phoenix-big', 'phoenix-small', 'rocket',
          'skeleton-barrel', 'skeleton-dragon', 'tornado', 'zap'}          # KataCR flying_unit_list (eval_yolo fallback)
BUILDINGS = {'goblin-hut', 'goblin-cage', 'tombstone', 'cannon', 'tesla', 'inferno-tower', 'bomb-tower', 'x-bow', 'mortar',
             'furnace', 'barbarian-hut', 'elixir-collector', 'goblin-drill'}
DY_FLY, DY_BUILDING, DY_OTHER = .56, -.8, -.05


def _names(v):
    if isinstance(v, str):
        try:
            v = json.loads(v)
        except ValueError:
            v = ast.literal_eval(v)
    if isinstance(v, dict):
        return [v[k] for k in sorted(v, key=int)]
    return list(v)


def load_mapping(m):
    """-> (classes {name: entry}, class list [name] or None, raw dict). Accepts classes.json or katacr_to_clasher.json."""
    d = json.loads(Path(m).read_text()) if not isinstance(m, dict) else m
    names = d.get('names')
    if isinstance(names, list) and names and isinstance(names[0], dict):          # live/yolo_synth/classes.json
        ent = {e['name']: e for e in names}
        return ent, [e['name'] for e in sorted(names, key=lambda e: e['idx'])], d
    return d.get('classes', {}), (names if isinstance(names, list) else None), d


def crop(frame):
    """eval_yolo.crop on any 9:16 frame: the capture box scaled to the frame -> 568x896 (INTER_AREA)."""
    h, w = frame.shape[:2]
    x0, y0, x1, y1 = CROP_720[0]*w/720, CROP_720[1]*h/1280, CROP_720[2]*w/720, CROP_720[3]*h/1280
    sx, sy = WK/(x1 - x0), HK/(y1 - y0)
    return cv2.warpAffine(frame, np.array([[sx, 0, -x0*sx], [0, sy, -y0*sy]]), (WK, HK), flags=cv2.INTER_AREA)


def letterbox(im, h, w):
    """Ultralytics LetterBox(auto=False, center): scale to fit (never up), pad with 114 -> (img, k, pad_x, pad_y)."""
    k = min(h/im.shape[0], w/im.shape[1], 1.)
    nw, nh = int(round(im.shape[1]*k)), int(round(im.shape[0]*k))
    if (nw, nh) != (im.shape[1], im.shape[0]):
        im = cv2.resize(im, (nw, nh), interpolation=cv2.INTER_LINEAR)
    dw, dh = (w - nw)/2, (h - nh)/2
    top, bottom, left, right = int(round(dh - .1)), int(round(dh + .1)), int(round(dw - .1)), int(round(dw + .1))
    return cv2.copyMakeBorder(im, top, bottom, left, right, cv2.BORDER_CONSTANT, value=(114, 114, 114)), k, left, top


class _Model:
    """One detector: run(x_rgb_hw3_uint8) -> raw (4+nc, N) float32; .names, .h, .w."""
    def __init__(self, path, compute_units='ne', device='cpu', names=None, size=None, threads=0):
        p = Path(path); self.path, meta, self.threads = p, {}, int(threads)
        if p.suffix in ('.mlpackage', '.mlmodel'):
            ct = _coremltools()
            cu = dict(ne=ct.ComputeUnit.CPU_AND_NE, gpu=ct.ComputeUnit.CPU_AND_GPU, cpu=ct.ComputeUnit.CPU_ONLY,
                      all=ct.ComputeUnit.ALL)[compute_units]
            self.m = ct.models.MLModel(str(p), compute_units=cu)
            spec = self.m.get_spec()
            meta = dict(spec.description.metadata.userDefined)
            inp = spec.description.input[0]; self.inp, self.outname = inp.name, spec.description.output[0].name
            if inp.type.WhichOneof('Type') == 'imageType':
                self.h, self.w, self.image = inp.type.imageType.height, inp.type.imageType.width, True
            else:
                shp = inp.type.multiArrayType.shape; self.h, self.w, self.image = int(shp[2]), int(shp[3]), False
            self.kind = 'coreml'
        elif p.suffix == '.pt':             # Ultralytics / KataCR checkpoint (needs ultralytics, + $KATACR_SRC for CRDetectionModel)
            import os
            import sys
            import torch
            if os.environ.get('KATACR_SRC'):
                sys.path.insert(0, os.environ['KATACR_SRC'])
            ck = torch.load(str(p), map_location='cpu', weights_only=False)
            mod = ck.get('ema') or ck['model'] if isinstance(ck, dict) else ck
            self.m = mod.float().fuse().eval().to(device); meta = dict(names=mod.names)
            self.kind, self.torch, self.half, self.dev = 'torch', torch, False, torch.device(device)
            self.h, self.w = 896, 576
        else:
            import torch
            extra = {'config.txt': ''}
            self.m = torch.jit.load(str(p), map_location='cpu', _extra_files=extra).eval()
            if extra['config.txt']:
                meta = json.loads(extra['config.txt'])
            self.half = next(self.m.parameters()).dtype == torch.float16
            if device == 'cpu' and self.half:
                self.m, self.half = self.m.float(), False
            self.dev = torch.device(device); self.m = self.m.to(self.dev)
            self.kind, self.torch = 'torch', torch
            sz = meta.get('imgsz', [896, 576])
            self.h, self.w = (sz, sz) if isinstance(sz, int) else tuple(sz)
        side = p.with_name(p.name + '.meta.json')         # sidecar: names / input_range / imgsz
        if side.exists():
            meta.update(json.loads(side.read_text()))
            if 'imgsz' in meta and self.kind == 'torch':
                sz = meta['imgsz']; self.h, self.w = (sz, sz) if isinstance(sz, int) else tuple(sz)
        if size:
            self.h, self.w = size
        self.names = _names(meta['names']) if 'names' in meta else names
        if not self.names:
            raise ValueError(f'{p}: no class names (model metadata, {side.name} or mapping["names"])')
        self.scale255 = str(meta.get('input_range', '0-1')) == '0-255'

    def run(self, rgb):
        if self.kind == 'coreml':
            if self.image:
                from PIL import Image
                y = self.m.predict({self.inp: Image.fromarray(rgb)})[self.outname]
            else:
                x = rgb.transpose(2, 0, 1)[None].astype(np.float32)
                y = self.m.predict({self.inp: x if self.scale255 else x/255.})[self.outname]
        else:
            t = self.torch
            nt = t.get_num_threads()
            if self.threads:          # the bot sets 1 torch thread process-wide (rext_policy); offline replays only
                t.set_num_threads(self.threads)
            with t.inference_mode():
                x = t.from_numpy(np.ascontiguousarray(rgb.transpose(2, 0, 1)[None])).to(self.dev)
                x = x.half() if self.half else x.float()
                y = self.m(x if self.scale255 else x/255.)
                y = (y[0] if isinstance(y, (list, tuple)) else y).float().cpu().numpy()
            if self.threads:
                t.set_num_threads(nt)
        y = np.asarray(y, np.float32)[0]
        return y if y.shape[0] == 4 + len(self.names) else y.T


class YoloUnits:
    def __init__(self, models, mapping, conf=.5, iou=.6, compute_units='ne', device='cpu', every=1, fmt=None, offsets=None,
                 threads=0):
        """models: path or list of paths (merged, class-agnostic NMS); mapping: classes.json / katacr_to_clasher.json path or
        dict. every: the driver detects on every Nth battle frame and reuses the last detections in between."""
        self.every = max(1, int(every))
        self.cls, self.class_list, self.map = load_mapping(mapping)
        self.mapping_path = None if isinstance(mapping, dict) else str(mapping)
        self.offsets_path = str(offsets) if offsets else None
        self.offsets = json.loads(Path(offsets).read_text()) if offsets else {}
        paths = [models] if isinstance(models, (str, Path)) else list(models)
        self.models = [_Model(p, compute_units, device, names=self.class_list, threads=threads) for p in paths]
        self.conf, self.iou, self.fmt = conf, iou, fmt or self.map.get('format', 'auto')
        for m in self.models:
            team = m.names[-1] in TEAM_NAMES
            m.fmt = self.fmt if self.fmt != 'auto' else 'katacr' if team else 'name_team'
            if m.fmt == 'katacr' and not team:
                raise ValueError(f'{m.path}: format katacr needs a last team class {TEAM_NAMES}')
            if m.fmt == 'name_team' and not self.class_list:
                raise ValueError(f'{m.path}: format name_team needs a class list (classes.json mapping)')
        self.pool = None
        self.last_ms = None

    def info(self):
        import hashlib

        def sha(p):
            p = Path(p)
            files = sorted(f for f in p.rglob('*') if f.is_file()) if p.is_dir() else [p]
            h = hashlib.sha256()
            for f in files:
                h.update(f.read_bytes())
            return h.hexdigest()
        return dict(models=[dict(path=str(m.path), sha256=sha(m.path), input_hw=[m.h, m.w], kind=m.kind, format=m.fmt)
                            for m in self.models],
                    mapping=self.mapping_path, mapping_sha256=sha(self.mapping_path) if self.mapping_path else None,
                    offsets=self.offsets_path, offsets_sha256=sha(self.offsets_path) if self.offsets_path else None,
                    conf=self.conf, iou=self.iou, every=self.every)

    def _detect(self, m, cr):
        """568x896 crop -> [dict(name, team, score, box=(x1, y1, x2, y2) in crop px)] after class-wise NMS."""
        img, k, px, py = letterbox(cr, m.h, m.w)
        raw = m.run(np.ascontiguousarray(img[..., ::-1]))
        names, team = m.names, m.fmt == 'katacr'
        ncls = len(names) - (1 if team else 0)
        sc = raw[4:4 + ncls]
        c = sc.argmax(0); s = sc[c, np.arange(sc.shape[1])]
        keep = np.nonzero(s > self.conf)[0]
        if not len(keep):
            return []
        b, s, c = raw[:4, keep].T, s[keep], c[keep]
        xywh = np.c_[b[:, 0] - b[:, 2]/2, b[:, 1] - b[:, 3]/2, b[:, 2], b[:, 3]]
        off = xywh.copy(); off[:, :2] += c[:, None]*7680.      # class-wise NMS (KataCR / Ultralytics max_wh offset)
        idx = np.array(cv2.dnn.NMSBoxes(off.tolist(), s.tolist(), self.conf, self.iou), int).reshape(-1)
        tm = raw[-1, keep] if team else None
        out = []
        for i in idx:
            if team:
                name, tv = names[c[i]], int(tm[i] > .5)
            elif c[i]//2 < len(self.class_list):           # id = 2*name_idx + team
                name, tv = self.class_list[c[i]//2], int(c[i] % 2)
            else:
                continue
            x1, y1, w, h = xywh[i]
            box = ((x1 - px)/k, (y1 - py)/k, (x1 + w - px)/k, (y1 + h - py)/k)        # crop px (Ultralytics scale_boxes)
            out.append(dict(name=str(name), team=tv, score=float(s[i]), box=box))
        return out

    def ground(self, d):
        """eval_yolo.predict ground point -> record (x, y from the bottom)."""
        x1, y1, x2, y2 = d['box']
        o = self.offsets.get(d['name']) or dict(dx=0., dy=DY_FLY if d['name'] in FLYING else DY_BUILDING if d['name'] in BUILDINGS
                                                 else DY_OTHER)
        return ((x1 + x2)/2 - GX0)/CELL_W + o['dx'], 32. - ((y2 - GY0)/CELL_H + o['dy'])

    def detections(self, frame_bgr):
        cr = crop(frame_bgr)
        dets = []
        for m in self.models:
            dets += self._detect(m, cr)
        if len(self.models) > 1 and dets:      # cross-model, class-agnostic (KataCR combo_detect)
            bx = [[d['box'][0], d['box'][1], d['box'][2] - d['box'][0], d['box'][3] - d['box'][1]] for d in dets]
            idx = np.array(cv2.dnn.NMSBoxes(bx, [d['score'] for d in dets], self.conf, self.iou), int).reshape(-1)
            dets = [dets[i] for i in sorted(idx, key=lambda i: -dets[i]['score'])]
        return dets

    def is_unit(self, name):
        e = self.cls.get(name)
        if name in DROP or (e is not None and e.get('unit') is False):
            return False
        return e is None or 'kind' not in e or e['kind'] in ('troop', 'building') or e.get('unit') is True

    def step(self, frame_bgr):
        t0 = time.perf_counter()
        units, unknown, src = [], [], []
        for d in self.detections(frame_bgr):
            if not self.is_unit(d['name']):
                continue
            x, y = self.ground(d)
            owner = d['team']
            e = self.cls.get(d['name']) or {}
            ident = e.get('identity')
            if ident and ident != 'unknown_unit':
                units.append(dict(cls=ident, card=_body_card(ident), owner=int(owner), x=round(float(x), 3), y=round(float(y), 3),
                                  hp_frac=None, score=round(d['score'], 4)))
                src.append(d['name'])
            else:
                unknown.append(dict(owner=int(owner), kind=e.get('kind', 'troop'), x=round(float(x), 3), y=round(float(y), 3),
                                    score=round(d['score'], 4)))
        self.last_ms = 1e3*(time.perf_counter() - t0)
        return dict(units=units, unknown_units=unknown, units_yolo=src)

    def submit(self, frame_bgr):
        """Run step() on a worker thread (overlaps our frame model); .result() of the returned future."""
        if self.pool is None:
            self.pool = ThreadPoolExecutor(1, thread_name_prefix='yolo-units')
        return self.pool.submit(self.step, frame_bgr)


def _coremltools():
    """coremltools from the runtime venv, else (appended last, so it never shadows runtime packages) from
    $CLASHER_YOLO_SITE or ~/clasher-live/yolo/venv's site-packages (Mac: the live venv need not change)."""
    try:
        import coremltools
    except ImportError:
        import os
        import sys
        site = os.path.expanduser(os.environ.get('CLASHER_YOLO_SITE', '~/clasher-live/yolo/venv/lib/python3.12/site-packages'))
        sys.path.append(site)
        import coremltools
    return coremltools


def _body_card(identity):
    try:
        from common import body_card
    except ImportError:
        from live.perception.common import body_card
    return body_card(identity)


def from_spec(spec):
    """drive.py --units 'yolo:<model>[+<model>...]:<mapping>[:k=v,...]' (k: conf, iou, cu, device, every, format, offsets,
    threads (torch backend intra-op threads while detecting; offline replays))."""
    import os
    parts = spec.split(':')
    if parts[0] != 'yolo' or len(parts) < 3:
        raise ValueError(f'--units: expected yolo:<model>[+<model>]:<mapping.json>[:k=v,...], got {spec!r}')
    opts = dict(kv.split('=', 1) for kv in parts[3].split(',') if kv) if len(parts) > 3 else {}
    ex = os.path.expanduser
    return YoloUnits([ex(p) for p in parts[1].split('+')], ex(parts[2]), conf=float(opts.get('conf', .5)),
                     iou=float(opts.get('iou', .6)), compute_units=opts.get('cu', 'ne'), device=opts.get('device', 'cpu'),
                     every=int(opts.get('every', 1)), fmt=opts.get('format'),
                     offsets=ex(opts['offsets']) if 'offsets' in opts else None, threads=int(opts.get('threads', 0)))
