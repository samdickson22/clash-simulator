"""Per-frame live inference -> downstream record (clasher.live.perception-frame.v1).

  from live.perception.infer import LivePerception
  p = LivePerception('EXPORT_DIR', device='cpu')          # frame.pt + event.pt + vocab.json
  rec = p.step(bgr_540x1140, timestamp_ms)               # call on every processed frame, in order

Input is the sanitized 540x1140 BGR canvas used in training (offline renderer 1080x2280 downscaled 2x).
Official-client frames must be scaled to that canvas; the domain gap is unmeasured.
Record coordinates: owner 0 = us, 1 = opponent; x in tiles from the screen left (0..18), y in tiles from
the screen bottom (0..32, our king at (9, 3)). hp is a fraction of max HP. Play events come from the
retrained TemporalHead over the last 16 processed frames (trained at 8-25 FPS) + events.EventTracker
(location-level tracks, card voted over frames, emitted once after the body-fusion hold, events.LIVE_DEFAULT;
fusion={'hold_ms': 0} restores the original immediate emission); `tick` is the estimated execution time in ms
on the caller's timestamp clock.
"""
import json
from pathlib import Path

import numpy as np
import torch
from torch.nn import functional as F

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

FRAME_KEYS = ('body_heatmap', 'body_box', 'body_hp', 'body_hp_visible', 'hud_cards', 'elixir_digit', 'elixir_fraction',
              'clock_seconds', 'phase', 'features')
EVENT_KEYS = ('event_heatmap', 'event_age_ms', 'event_sigma_ms', 'cast_origin')
SPELLS = {'Arrows', 'BarbLog', 'Earthquake', 'Fireball', 'GoblinBarrel', 'Lightning', 'Log', 'Poison', 'Rocket',
          'RoyalDelivery', 'Tornado', 'Zap'}


def visual_births(new_heat, old_heat):
    """Same rule as training (finetune2.visual_births): fresh body peaks vs the previous processed frame."""
    if old_heat is None:
        return torch.zeros(1, 2, 64, 36, device=new_heat.device)
    new, old = new_heat.sigmoid(), old_heat.sigmoid()
    peaks = (new == F.max_pool2d(new, 3, 1, 1)) & (new >= .5)
    fresh = peaks & (F.max_pool2d(old, 7, 1, 3) < .3)
    vb = fresh.reshape(1, 2, -1, 64, 36).sum(2).float()
    return F.max_pool2d(vb, 7, 1, 3).clamp(max=8)


class LivePerception:
    def __init__(self, export_dir, device='cpu', unit_threshold=.4, tower_threshold=.5, event_threshold=.6, fusion=None):
        from events import EventTracker, LIVE_DEFAULT
        self.fusion = dict(LIVE_DEFAULT if fusion is None else fusion, threshold=event_threshold)
        d = Path(export_dir); self.device = device; self.ut = unit_threshold; self.tt = tower_threshold
        self.frame = torch.jit.load(str(d/'frame.pt'), map_location=device).eval()
        self.event = torch.jit.load(str(d/'event.pt'), map_location=device).eval()
        vocab = json.loads((d/'vocab.json').read_text()); self.cards, self.identities = vocab['cards'], vocab['identities']
        self.et = event_threshold; self.tracker = EventTracker(self.cards, **self.fusion)
        self.ring = []; self.prev_heat = None

    def reset(self):
        """New match."""
        from events import EventTracker
        self.ring = []; self.prev_heat = None; self.tracker = EventTracker(self.cards, **self.fusion)

    def step(self, image_bgr, timestamp_ms):
        from clasher.vision.l1_v4 import prepare_pixels
        arena, hud = prepare_pixels(image_bgr)
        return self.step_prepared(arena, hud, timestamp_ms)

    @torch.inference_mode()
    def step_prepared(self, arena, hud, timestamp_ms, unit_floor=None):
        """Same as step() on the prepared 832x448 arena + 64x448 HUD (the pixel cache format). With `unit_floor`,
        units down to that score are decoded and kept in self.last['units_lo'] (record frame); the record itself
        keeps the unit threshold. self.last also holds the frame's event peaks (offline tracker replays)."""
        t = lambda x: torch.from_numpy(np.ascontiguousarray(x)).permute(2, 0, 1)[None].float().div(255).to(self.device)
        outs = dict(zip(FRAME_KEYS, self.frame(t(arena), t(hud))))
        self.ring = (self.ring+[(float(timestamp_ms), outs['features'][0])])[-16:]
        n = len(self.ring)
        cache = torch.zeros(1, 16, *outs['features'].shape[1:], device=self.device)
        cache[0, 16-n:] = torch.stack([f for _, f in self.ring])
        ages = torch.zeros(1, 16, device=self.device); ages[0, 16-n:] = torch.tensor([timestamp_ms-s for s, _ in self.ring], device=self.device)
        valid = torch.zeros(1, 16, dtype=torch.bool, device=self.device); valid[0, 16-n:] = True
        births = visual_births(outs['body_heatmap'], self.prev_heat); self.prev_heat = outs['body_heatmap']
        ev = {k: v.float() for k, v in zip(EVENT_KEYS, self.event(cache, ages, valid, births))}
        out = {k: v.float().cpu().numpy() for k, v in outs.items() if k != 'features'}
        floor = self.ut if unit_floor is None else min(unit_floor, self.ut)
        dec = C.decode_frame(out, 0, self.cards, self.identities, threshold=floor, offsets=True)
        lo = C.frame_record(dec, timestamp_ms=timestamp_ms)['units']
        dec['units'] = [u for u in dec['units'] if u['score'] >= self.ut]
        peaks = self.tracker.peaks(ev)
        events = self.tracker.update(ev, float(timestamp_ms), peaks=peaks, units=[u for u in lo if u['score'] >= self.tracker.unit_floor])
        self.last = dict(peaks=peaks, units_lo=lo)
        return C.frame_record(dec, timestamp_ms=timestamp_ms, tower_threshold=self.tt, events=events)
