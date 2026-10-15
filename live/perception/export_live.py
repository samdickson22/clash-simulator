"""TorchScript export + parity on real validation frames + latency, for a live-dense-v1 checkpoint.

  python live/perception/export_live.py --checkpoint CKPT --output DIR [--device cuda]
Writes frame.pt (encode: arena [1,3,832,448], hud [1,3,64,448], BGR float in [0,1]),
vocab.json, parity.json, latency.json. Validation frames only (guarded).
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch
from torch import nn

import common as C

FRAME_KEYS = ('body_heatmap', 'body_box', 'body_hp', 'body_hp_visible', 'hud_cards', 'elixir_digit', 'elixir_fraction',
              'clock_seconds', 'phase', 'features')
EVENT_KEYS = ('event_heatmap', 'event_age_ms', 'event_sigma_ms', 'cast_origin')


class EventExport(nn.Module):
    def __init__(self, head):
        super().__init__(); self.head = head

    def forward(self, cache, ages_ms, valid, births):
        out = self.head(cache, ages_ms, valid, births)
        return tuple(out[k] for k in EVENT_KEYS)


class FrameExport(nn.Module):
    def __init__(self, model):
        super().__init__(); self.model = model

    def forward(self, arena, hud):
        out = self.model.encode(arena, hud)
        return tuple(out[k] for k in FRAME_KEYS)


def val_frames(n=64):
    guard = C.HeldoutGuard(); eps = guard.episodes('validation')[:4]; guard.check(eps); res = []
    for ep in eps:
        px = C.Pixels(guard, ep, C.load_receipt(guard, ep, 'validation'))
        for k in np.linspace(0, len(px.idx['blocks'])-1, n//len(eps)).astype(int):
            ar, hu = px.block(int(k)); res.append((ar[0], hu[0]))
    return res


def tens(a, h, dev):
    t = lambda x: torch.from_numpy(np.ascontiguousarray(x)).permute(2, 0, 1)[None].float().div(255).to(dev)
    return t(a), t(h)


def bench(fn, inputs, sync, n=200, warm=30):
    for i in range(warm):
        fn(*inputs[i % len(inputs)])
    sync(); ts = []
    for i in range(n):
        t0 = time.perf_counter(); fn(*inputs[i % len(inputs)]); sync(); ts.append((time.perf_counter()-t0)*1000)
    ts = np.asarray(ts)
    return dict(p50_ms=round(float(np.median(ts)), 3), p95_ms=round(float(np.quantile(ts, .95)), 3), n=n)


def main():
    p = argparse.ArgumentParser(); p.add_argument('--checkpoint', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True); p.add_argument('--device', default='cuda')
    p.add_argument('--cpu-threads', default='16,4'); a = p.parse_args(); a.output.mkdir(parents=True, exist_ok=True)
    from clasher.vision.l1_v4 import PerceptionV4
    state = torch.load(a.checkpoint, map_location='cpu', weights_only=False)
    if state.get('format') != 'live-dense-v1':
        raise ValueError('expects a live-dense-v1 checkpoint')
    model = PerceptionV4(len(state['cards']), len(state['identities'])); model.load_state_dict(state['model']); model.eval()
    frames = val_frames()
    wrapper = FrameExport(model).eval()
    with torch.inference_mode():
        ex = tens(*frames[0], 'cpu')
        traced = torch.jit.trace(wrapper, ex, strict=True); traced.save(str(a.output/'frame.pt'))
        loaded = torch.jit.load(str(a.output/'frame.pt'))
        err = {k: 0. for k in FRAME_KEYS}; decisions = dict(frames=0, hand_equal=0, units_equal=0)
        for ar, hu in frames:
            x = tens(ar, hu, 'cpu'); e = wrapper(*x); s = loaded(*x)
            for k, u, v in zip(FRAME_KEYS, e, s):
                err[k] = max(err[k], float((u-v).abs().max()))
            de = C.decode_frame({k: v.numpy() for k, v in zip(FRAME_KEYS, e)}, 0, state['cards'], state['identities'], offsets=True)
            ds = C.decode_frame({k: v.numpy() for k, v in zip(FRAME_KEYS, s)}, 0, state['cards'], state['identities'], offsets=True)
            decisions['frames'] += 1; decisions['hand_equal'] += de['hand'] == ds['hand'] and de['next'] == ds['next']
            decisions['units_equal'] += [(u['identity'], u['owner']) for u in de['units']] == [(u['identity'], u['owner']) for u in ds['units']]
    # event head: trace on real cached features from 16 consecutive validation frames + gap/padding variants
    ev = EventExport(model.temporal).eval()
    with torch.inference_mode():
        feats = torch.cat([model.encode(*tens(ar, hu, 'cpu'))['features'] for ar, hu in frames[:16]])[None]
        ages = torch.arange(15, -1, -1, dtype=torch.float32)[None]*66.7; valid = torch.ones(1, 16, dtype=torch.bool)
        births = torch.zeros(1, 2, 64, 36)
        tev = torch.jit.trace(ev, (feats, ages, valid, births), strict=True); tev.save(str(a.output/'event.pt'))
        lev = torch.jit.load(str(a.output/'event.pt')); eerr = 0.
        for variant in range(3):
            f2, a2, v2, b2 = feats.clone(), ages.clone(), valid.clone(), births.clone()
            if variant == 1:
                v2[:, :8] = False; a2[:, :8] = 9000
            if variant == 2:
                a2[:, :8] += 1200; b2[:, :, 30:34, 10:14] = 1
            for u, v in zip(ev(f2, a2, v2, b2), lev(f2, a2, v2, b2)):
                eerr = max(eerr, float((u-v).abs().max()))
    err['event_head_max'] = eerr
    parity = dict(passed=max(err.values()) < 1e-3, max_abs_error=err, decisions=decisions, real_validation_frames=len(frames),
                  checkpoint=str(a.checkpoint), checkpoint_sha256=C.sha(a.checkpoint), frame_pt_sha256=C.sha(a.output/'frame.pt'),
                  event_pt_sha256=C.sha(a.output/'event.pt'),
                  torch=torch.__version__)
    (a.output/'parity.json').write_text(json.dumps(parity, indent=1)+'\n')
    vocab = dict(identities=state['identities'], cards=state['cards'], heatmap_channel='owner*len(identities)+identity',
                 native_owner={'0': 'opponent', '1': 'own (recorded viewpoint)'}, grid='64 rows x 36 cols, half tiles, native y down the screen',
                 body_box='channels 0/1 = sub-cell x/y offset in [0,1]; x_tiles=(col+off_x)/2, y_tiles=(row+off_y)/2; channels 2/3 unused',
                 body_hp='fraction of max HP at the peak cell', hud_cards='5 slots (4 hand + next), classes = cards + [unknown]',
                 elixir='argmax(elixir_digit) + elixir_fraction',
                 event_pt='inputs: features ring [1,16,64,52,28] (frame.pt features of the last 16 processed frames, oldest first, zero padded), ages_ms [1,16] (now - frame time), valid [1,16] bool, births [1,2,64,36] (infer.visual_births); outputs EVENT_KEYS; channel = side*56+card; placement x=col/2, y=row/2 (tile centres)',
                 record='common.frame_record converts to the bot frame (owner 0 = us, y = 32 - native)')
    (a.output/'vocab.json').write_text(json.dumps(vocab, indent=1)+'\n')
    lat = {}
    with torch.inference_mode():
        if a.device == 'cuda':
            dev = 'cuda'; inp = [tens(ar, hu, dev) for ar, hu in frames[:16]]; sync = torch.cuda.synchronize
            m = torch.jit.load(str(a.output/'frame.pt'), map_location=dev)
            lat['cuda_fp32_torchscript_b1'] = bench(m, inp, sync)
            mh = model.to(dev).half(); inph = [(x.half(), y.half()) for x, y in inp]
            lat['cuda_fp16_eager_b1'] = bench(lambda x, y: mh.encode(x, y), inph, sync)
            model.float().cpu()
        if a.device == 'cuda':
            me = torch.jit.load(str(a.output/'event.pt'), map_location='cuda')
            lat['cuda_fp32_event_head_b1'] = bench(me, [(feats.cuda(), ages.cuda(), valid.cuda(), births.cuda())], torch.cuda.synchronize)
        cpu_in = [tens(ar, hu, 'cpu') for ar, hu in frames[:8]]
        m = torch.jit.load(str(a.output/'frame.pt'))
        for th in [int(t) for t in a.cpu_threads.split(',')]:
            torch.set_num_threads(th); lat[f'cpu_fp32_torchscript_{th}threads'] = bench(m, cpu_in, lambda: None, n=40, warm=5)
        me = torch.jit.load(str(a.output/'event.pt'))
        for th in [int(t) for t in a.cpu_threads.split(',')]:
            torch.set_num_threads(th); lat[f'cpu_fp32_event_head_{th}threads'] = bench(me, [(feats, ages, valid, births)], lambda: None, n=40, warm=5)
        out = [{k: v.numpy() for k, v in zip(FRAME_KEYS, m(*cpu_in[i]))} for i in range(4)]
        t0 = time.perf_counter()
        for i in range(200):
            C.frame_record(C.decode_frame(out[i % 4], 0, state['cards'], state['identities'], offsets=True))
        lat['cpu_decode_plus_record_ms'] = round((time.perf_counter()-t0)*1000/200, 3)
    from clasher.vision.l1_v4 import prepare_pixels  # noqa: F401  (prep cost measured separately on raw frames when available)
    lat['note'] = 'A6000 + 01 Threadripper (shared, loaded host). Mac MPS/CPU/CoreML numbers pending.'
    (a.output/'latency.json').write_text(json.dumps(lat, indent=1)+'\n')
    print(json.dumps(dict(parity=parity['passed'], max_err=max(err.values()), latency=lat)), flush=True)


if __name__ == '__main__':
    main()
