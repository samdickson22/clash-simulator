"""Continuous YOLO detection pass over the Null's night capture (runs on a GPU host, data stays on 05).

Loop: list raw chunks on REMOTE (raw/i<N>/<run>/chunk-NNNNNN/READY) that have no dets/<rel>/READY; rsync their `purpose == "scene"`
jpg+json, plus one labelled json per run (for `arena_calib`), to local scratch; predict with r3's x1h-e12 (KataCR YOLO_CR, 896x576,
class-agnostic NMS .6, conf >= .2) on the 568x896 crop made by the nulls_to_cr least-squares tower affine; write dets.json with boxes
in FULL-FRAME px (inverse affine); rsync it to REMOTE dets/<rel>/dets.json, then touch READY there; delete the local copies.

dets.json = {model, model_md5, settings, affine (frame -> crop 2x3), fit_resid, calib_from, frames: {stem: [[x1, y1, x2, y2, class,
belong, conf], ...]}}; belong 0 = ours/bottom, 1 = opp/top; towers and non-unit classes kept as named (as r3's qa/det-v1).
A run with no labelled json carrying arena_calib yet uses the last calib seen (the camera is fixed); calib_from records the source.

  python det_night.py --weights W.pt --katacr-src SRC [--remote 127x05] [--local /mpac/sdicks02/scratch/nulls-det] [--batch 16]
  python det_night.py ... --verify qa/det-v1/dets.json      # re-run r3's 40 frames and report box deltas, then exit
"""
import argparse
import hashlib
import json
import os
import queue
import shlex
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'perception'/'yolo'))
from nulls_to_cr import calib_points, fit, WK, HK  # noqa: E402

NIGHT = '/mpac/sdicks02/scratch/nulls/night'
DEFAULT_CAL = {'opp_king': [540.0, 650.0], 'opp_left': [276.0, 798.2], 'opp_right': [804.0, 798.2], 'own_king': [540.0, 1667.0],
               'own_left': [276.0, 1529.8], 'own_right': [804.0, 1529.8]}

# Runs on REMOTE with its stock python3 (stdlib only). argv: night root, max chunks, json list of runs whose calib we already hold.
LISTER = r'''
import json, os, sys
root, maxn, known = sys.argv[1], int(sys.argv[2]), set(json.loads(sys.argv[3]))
raw, dets = os.path.join(root, 'raw'), os.path.join(root, 'dets')
todo, backlog = [], 0
for inst in sorted(os.listdir(raw)):
    ip = os.path.join(raw, inst)
    if not inst.startswith('i') or not os.path.isdir(ip):
        continue
    for run in os.listdir(ip):
        rp = os.path.join(ip, run)
        if not os.path.isdir(rp):
            continue
        for ch in os.listdir(rp):
            if not ch.startswith('chunk-'):
                continue
            rel = '/'.join((inst, run, ch))
            try:
                t = os.path.getmtime(os.path.join(rp, ch, 'READY'))
            except OSError:
                continue
            if os.path.exists(os.path.join(dets, rel, 'READY')):
                continue
            backlog += 1
            todo.append((t, rel))
todo.sort()
out = []
for t, rel in todo[:maxn]:
    cd = os.path.join(raw, rel); stems = []
    for f in sorted(os.listdir(cd)):
        if not f.endswith('.json') or f.endswith('.obs.json'):
            continue
        try:
            m = json.load(open(os.path.join(cd, f)))
        except Exception:
            continue
        if isinstance(m, dict) and m.get('purpose') == 'scene' and os.path.exists(os.path.join(cd, f[:-5] + '.jpg')):
            stems.append(f[:-5])
    out.append(dict(rel=rel, stems=stems, ready_mtime=t))
calib = {}
for run in sorted({'/'.join(c['rel'].split('/')[:2]) for c in out} - known):
    rd = os.path.join(root, run)
    if not os.path.isdir(rd):
        continue
    for ch in sorted(os.listdir(rd)):
        cd = os.path.join(rd, ch)
        if not os.path.isdir(cd):
            continue
        for f in sorted(os.listdir(cd)):
            if f.endswith('.json') and '-bg' not in f and not f.endswith('.obs.json'):
                try:
                    if json.load(open(os.path.join(cd, f))).get('arena_calib'):
                        calib[run] = '/'.join((run, ch, f)); break
                except Exception:
                    pass
        if run in calib:
            break
print(json.dumps(dict(backlog=backlog, chunks=out, calib=calib)))
'''


def log(*a):
    print(time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), *a, flush=True)


def sh(cmd, inp=None, tries=3):
    for i in range(tries):
        r = subprocess.run(cmd, input=inp, capture_output=True, text=True)
        if r.returncode == 0:
            return r.stdout
        log('cmd failed', r.returncode, cmd[:4], r.stderr[-400:])
        time.sleep(5*(i+1))
    raise RuntimeError(f'{cmd[:4]} failed')


class Detector:
    def __init__(self, a):
        sys.path.insert(0, a.katacr_src)
        import torch
        from katacr.yolov8.train import YOLO_CR
        if a.device != 'cpu':
            torch.cuda.set_per_process_memory_fraction(a.gpu_gb*2**30/torch.cuda.get_device_properties(int(a.device)).total_memory,
                                                       int(a.device))
        self.torch, self.m, self.a = torch, YOLO_CR(a.weights), a
        self.pool = ThreadPoolExecutor(a.threads)

    def load(self, paths, M):
        def one(p):
            im = cv2.imread(str(p))
            return None if im is None else cv2.warpAffine(im, M, (WK, HK), flags=cv2.INTER_AREA)
        return list(self.pool.map(one, paths))

    def predict(self, crops):
        a, out = self.a, []
        for i in range(0, len(crops), a.batch):
            rs = self.m.predict(crops[i:i+a.batch], device=a.device, verbose=False, conf=a.conf, iou=a.iou, agnostic_nms=True,
                                imgsz=(896, 576), batch=a.batch)
            out += [r.orig_boxes.cpu().numpy() for r in rs]
        return out


def to_frame(boxes, Minv, names):
    rows = []
    for b in boxes:
        x1, y1, x2, y2 = (float(v) for v in b[:4])
        c = np.array([[x1, y1, 1], [x2, y1, 1], [x1, y2, 1], [x2, y2, 1]]) @ Minv.T
        rows.append([round(float(c[:, 0].min()), 1), round(float(c[:, 1].min()), 1), round(float(c[:, 0].max()), 1),
                     round(float(c[:, 1].max()), 1), names[int(b[5])], int(b[6]), round(float(b[4]), 4)])
    return rows


def affine(cal):
    M, resid = fit(calib_points(cal))
    return M, np.linalg.inv(np.vstack([M, [0, 0, 1]]))[:2], resid


def verify(a, det):
    ref = json.loads(Path(a.verify).read_text())
    loc = Path(a.local)/'verify'; loc.mkdir(parents=True, exist_ok=True)
    files = [v['frame'] for v in ref['frames'].values()] + list(ref['frames'])
    sh(['rsync', '-rt', '--chmod=Du+rwx,Fu+rw', '--files-from=-', f'{a.remote}:/', str(loc)], inp='\n'.join(f.lstrip('/') for f in files)+'\n')
    worst, nref, nmine, unmatched = 0., 0, 0, 0
    for jf, v in ref['frames'].items():
        cal = json.loads((loc/jf.lstrip('/')).read_text())['arena_calib']
        M, Minv, resid = affine(cal)
        dM = float(np.abs(M - np.array(v['crop_affine_frame_to_568x896'])).max())
        mine = to_frame(det.predict(det.load([loc/v['frame'].lstrip('/')], M))[0], Minv, det.m.names)
        r = [d for d in v['dets'] if d[6] >= a.conf]; nref += len(r); nmine += len(mine)
        for d in r:
            cand = [max(abs(d[i]-e[i]) for i in range(4)) for e in mine if e[4] == d[4] and e[5] == d[5]]
            if not cand or min(cand) > 8:
                unmatched += 1
            else:
                worst = max(worst, min(cand))
        log(f'verify {Path(jf).stem}: affine dmax {dM:.2e} resid {resid:.2f} ref {len(r)} mine {len(mine)}')
    log(f'VERIFY frames {len(ref["frames"])} ref boxes {nref} mine {nmine} unmatched {unmatched} worst corner delta {worst:.2f} px')
    shutil.rmtree(loc)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--weights', required=True); p.add_argument('--katacr-src', required=True)
    p.add_argument('--remote', default='127x05'); p.add_argument('--night', default=NIGHT)
    p.add_argument('--local', default='/mpac/sdicks02/scratch/nulls-det'); p.add_argument('--device', default='0')
    p.add_argument('--batch', type=int, default=16); p.add_argument('--chunks', type=int, default=8, help='chunks per fetch')
    p.add_argument('--conf', type=float, default=.2); p.add_argument('--iou', type=float, default=.6)
    p.add_argument('--gpu-gb', type=float, default=6.); p.add_argument('--threads', type=int, default=6)
    p.add_argument('--idle', type=float, default=30., help='seconds to sleep when nothing is pending')
    p.add_argument('--verify'); p.add_argument('--once', action='store_true')
    a = p.parse_args()
    det = Detector(a)
    md5 = hashlib.md5(Path(a.weights).read_bytes()).hexdigest()
    log('model', a.weights, md5, 'names', len(det.m.names))
    if a.verify:
        return verify(a, det)
    loc = Path(a.local); inbox, outbox = loc/'in', loc/'out'
    for d in (inbox, outbox):
        shutil.rmtree(d, ignore_errors=True); d.mkdir(parents=True)
    sh(['ssh', a.remote, f'mkdir -p "{a.night}/dets"'])
    calib = {}                 # run -> (cal, calib_from)
    last = [(DEFAULT_CAL, 'default-constant')]
    inflight, todo, done = set(), queue.Queue(2), queue.Queue()
    stats = dict(frames=0, chunks=0, t0=time.time(), backlog=None)

    def fetcher():
        k = 0
        while True:
            try:
                ls = json.loads(sh(['ssh', a.remote, ' '.join(shlex.quote(v) for v in (
                    'nice', '-n', '10', 'python3', '-', a.night, str(a.chunks*3), json.dumps(sorted(calib))))], inp=LISTER))
            except Exception as e:
                log('lister error', e); time.sleep(a.idle); continue
            stats['backlog'] = ls['backlog']
            chunks = [c for c in ls['chunks'] if c['rel'] not in inflight][:a.chunks]
            if not chunks:
                if a.once:
                    todo.put(None); return
                time.sleep(a.idle); continue
            k += 1; bdir = inbox/f'b{k:06d}'; bdir.mkdir()
            new_cal = {run: rel for run, rel in ls['calib'].items() if run not in calib}
            files = [f'raw/{c["rel"]}/{s}{e}' for c in chunks for s in c['stems'] for e in ('.jpg', '.json')] + list(new_cal.values())
            try:
                if files:
                    sh(['rsync', '-rt', '--chmod=Du+rwx,Fu+rw', '--files-from=-', f'{a.remote}:{a.night}/', str(bdir)], inp='\n'.join(files)+'\n')
            except Exception as e:
                log('fetch error', e); shutil.rmtree(bdir, ignore_errors=True); time.sleep(a.idle); continue
            for run, rel in new_cal.items():
                try:
                    calib[run] = (json.loads((bdir/rel).read_text())['arena_calib'], rel)
                except Exception as e:
                    log('calib read error', run, e)
            for c in chunks:
                inflight.add(c['rel'])
            todo.put((bdir, chunks))

    def uploader():
        while True:
            item = done.get()
            if item is None:
                return
            rels, bout = item
            try:
                sh(['rsync', '-a', f'{bout}/', f'{a.remote}:{a.night}/dets/'])
                mk = ' '.join(f'"{a.night}/dets/{r}/READY"' for r in rels)
                sh(['ssh', a.remote, f'for f in {mk}; do test -s "$(dirname "$f")/dets.json" && touch "$f"; done'])
            except Exception as e:
                log('upload error', e)
            shutil.rmtree(bout, ignore_errors=True)
            for r in rels:
                inflight.discard(r)

    def decoder():                     # decodes + warps batch k+1 on CPU threads while the GPU predicts batch k
        while True:
            item = todo.get()
            if item is None:
                ready.put(None); return
            bdir, chunks = item; jobs = []
            for c in chunks:
                run = '/'.join(c['rel'].split('/')[:2])
                if run in calib:
                    last[0] = calib[run]
                cal, src = calib.get(run, last[0])
                M, Minv, resid = affine(cal)
                crops = det.load([bdir/'raw'/c['rel']/f'{s}.jpg' for s in c['stems']], M)
                jobs.append((c, M, Minv, resid, src, crops))
            shutil.rmtree(bdir, ignore_errors=True)
            ready.put((bdir.name, jobs))

    ready = queue.Queue(1)
    threading.Thread(target=fetcher, daemon=True).start()
    threading.Thread(target=decoder, daemon=True).start()
    up = threading.Thread(target=uploader, daemon=True); up.start()
    while True:
        item = ready.get()
        if item is None:
            done.put(None); up.join(); return
        name, jobs = item
        bout = outbox/name; t1 = time.time()
        flat = [im for j in jobs for im in j[5] if im is not None]
        boxes = iter(det.predict(flat) if flat else [])
        for c, M, Minv, resid, src, crops in jobs:
            frames = {s: to_frame(next(boxes), Minv, det.m.names) for s, im in zip(c['stems'], crops) if im is not None}
            od = bout/c['rel']; od.mkdir(parents=True, exist_ok=True)
            (od/'dets.json').write_text(json.dumps(dict(
                model='candidates/yolo-x1h-e12-stripped.pt' if 'x1h-e12' in a.weights else a.weights, model_md5=md5,
                settings=dict(imgsz=[896, 576], agnostic_nms=True, iou=a.iou, conf=a.conf),
                affine=M.tolist(), fit_resid=round(resid, 2), calib_from=src,
                unreadable=[s for s, im in zip(c['stems'], crops) if im is None], frames=frames)))
        nf = len(flat); dt = time.time()-t1
        stats['frames'] += nf; stats['chunks'] += len(jobs)
        mem = det.torch.cuda.max_memory_reserved()/2**30 if a.device != 'cpu' else 0
        el = time.time()-stats['t0']
        log(f'{name} chunks {len(jobs)} frames {nf} {nf/max(dt, 1e-6):.1f} f/s (pred) | total {stats["chunks"]} ch '
            f'{stats["frames"]} fr {stats["frames"]/el:.2f} f/s wall | backlog {stats["backlog"]} | gpu reserved max {mem:.2f} GB')
        done.put(([c['rel'] for c, *_ in jobs], bout))

if __name__ == '__main__':
    main()
