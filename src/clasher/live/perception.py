"""P2 pixel adapters. V4 uses its streaming ABI; fallback retains real gaps."""
from collections import deque
from dataclasses import replace
from pathlib import Path
import time
from .contracts import Observation


class V4Perception:
    def __init__(self, config):
        import json
        import torch
        from clasher.vision.l1_v4 import PerceptionV4, PixelPerception
        state = torch.load(config['checkpoint'], map_location='cpu', weights_only=True)
        calibration = json.loads(Path(config['calibration']).read_text())
        # No silent use of random/shakedown parameters as formal weights.
        self.qualification = calibration.get('qualification', 'unqualified')
        model = PerceptionV4(len(state['cards']), len(state['bodies']))
        model.load_state_dict(state['model'])
        self.sensor = PixelPerception(model, state['cards'], state['bodies'], calibration['spells'],
                                      calibration['thresholds'], calibration['calibration'], config.get('device', 'cpu'))
        from .loading import ROOT
        data = json.loads((ROOT/'gamedata.json').read_text())['items']['spells']
        self.buildings = {'Tower', 'KingTower', 'TowerPrincess', 'TowerKing'}
        for card in data:
            body = card.get('summonCharacterData') or {}
            if isinstance(body, dict) and body.get('source') == 'buildings':
                self.buildings.update((card['name'], body['name']))
        self.parts = {}
        # Instrument the two public model entry points without changing T7 code.
        for name, key in (('encode', 'backbone_hud'), ('temporal', 'temporal_fusion')):
            target = getattr(model, name)
            def timed(*args, _target=target, _key=key, **kwargs):
                start = time.monotonic()
                result = _target(*args, **kwargs)
                if config.get('device') == 'mps':
                    torch.mps.synchronize()
                self.parts[_key] = (time.monotonic()-start)*1000
                return result
            # temporal is an nn.Module: use forward, preserve module registration.
            if name == 'temporal':
                forward = target.forward
                def temporal(*args, **kwargs):
                    start = time.monotonic()
                    result = forward(*args, **kwargs)
                    if config.get('device') == 'mps':
                        torch.mps.synchronize()
                    self.parts['temporal_fusion'] = (time.monotonic()-start)*1000
                    return result
                target.forward = temporal
            else:
                model.encode = timed

    def step(self, frame):
        from clasher.rl.live_inference_contract import PublicVisionFrame, VisionEntity
        start = time.monotonic()
        row = self.sensor.step(frame.pixels, frame.episode, frame.timestamp_ms)
        finished = time.monotonic()
        for event in row['event_candidates']:
            event['available_timestamp_ms'] = frame.timestamp_ms+(finished-frame.produced_at)*1000
        entities = tuple(VisionEntity(str(t['track_id']), t['identity'],
                           'building' if t['identity'] in self.buildings else 'troop',
                           t['owner'], t['x'], t['y'], t['confidence'], t['hp_fraction'],
                           t['confidence'] if t['hp_fraction'] is not None else 0.) for t in row['tracks'])
        confidence = tuple(max(p) for p in row['hud_card_probabilities'])
        public = PublicVisionFrame(frame.episode, str(frame.sequence), round(frame.timestamp_ms),
                    row['clock_seconds'], .8, row['own_elixir'], .8, tuple(c or '' for c in row['own_hand']),
                    tuple(q if c else 0. for c, q in zip(row['own_hand'], confidence[:4])),
                    row['next_card'], confidence[4] if row['next_card'] else 0., entities, ())
        parts = dict(self.parts)
        # Include host association, preparation and event decoding in fusion.
        parts['temporal_fusion'] = max(0., (finished-start)*1000-parts.get('backbone_hud', 0.))
        return Observation(frame, public, tuple(row['event_candidates']),
                           'overtime' if row['phase'] == 3 else 'regulation', finished, parts)


class V3Fallback:
    """V1 body model + v3 HUD/temporal interfaces, without gap resets.

    Optional v3 event weights run on the last three actual frames. Without them,
    the v3 DeploymentTracker supplies only body/HUD events. Neither mode is a
    qualified v4 event detector; missing spell weights are explicitly logged.
    """
    def __init__(self, config):
        import json
        import torch
        from clasher.vision.l1_perception import Perception
        from clasher.vision.l1_hud_v3 import StreamHudReader
        from clasher.vision.l1_events_v3 import StreamEventNet
        # Ultralytics 8.1 checkpoints contain an nn.Module, not a state_dict.
        # This adapter is only for the repository's trusted legacy artifact.
        import os
        old = os.environ.get('TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD')
        os.environ['TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD'] = '1'
        try:
            self.body = Perception(config['body'], config['hud'], Path(config['geometry']),
                                   device=config.get('device', 'cpu'), imgsz=config.get('imgsz', 416))
        finally:
            if old is None:
                os.environ.pop('TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD', None)
            else:
                os.environ['TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD'] = old
        self.body.hud = StreamHudReader(config['hud'])
        read_hud = self.body.hud.read
        def canonical_hud(image):
            hud = read_hud(image)
            if hud['next_confidence'] <= 0:
                hud['next_card'] = None
            if hud['clock_confidence'] <= 0:
                hud['clock'] = None
            return hud
        self.body.hud.read = canonical_hud
        self.net = None
        self.device = config.get('device', 'cpu')
        self.thresholds = {'default': .7}
        if config.get('selection'):
            self.thresholds = json.loads(Path(config['selection']).read_text())['thresholds']
        if config.get('events'):
            state = torch.load(config['events'], map_location='cpu', weights_only=True)
            self.cards, self.spells = state['cards'], set(state['spells'])
            self.net = StreamEventNet(self.cards).to(self.device).eval()
            self.net.load_state_dict(state['model'])
        self.episode = None

    def step(self, frame):
        import cv2
        import numpy as np
        import torch
        from clasher.vision.l1_temporal import DeploymentTracker
        from clasher.vision.l1_events_v3 import StreamFusion, SpellCueBuffer, reduced, stack_pixels
        from clasher.vision.l1_hud_v3 import visible_clock_phase
        if self.episode != frame.episode:
            self.episode = frame.episode
            self.history = deque(maxlen=3)
            self.tracker = DeploymentTracker()
            self.fusion = StreamFusion(self.thresholds)
            self.spells_buffer = SpellCueBuffer()
        start = time.monotonic()
        public = self.body.step(frame.pixels, frame.episode, str(frame.sequence), round(frame.timestamp_ms))
        encoded = time.monotonic()
        tracked = self.tracker.update(public)
        candidates = [dict(card=e.card, side=e.player_id, x=e.x_tiles, y=e.y_tiles,
                           confidence=e.confidence) for e in tracked.play_events]
        if self.net is not None:
            self.history.append(reduced(frame.pixels))
            images = [self.history[0]]*(3-len(self.history))+list(self.history)
            with torch.inference_mode():
                scores = self.net(torch.from_numpy(stack_pixels(images)[None]).to(self.device)).sigmoid()[0].cpu().numpy()
            spells = []
            for cls, values in enumerate(scores):
                side, idx = divmod(cls, len(self.cards))
                card = self.cards[idx]
                if card in self.spells:
                    if side == 1:
                        continue
                    values = np.minimum(.995, values+scores[cls+len(self.cards)])
                peaks = (values == cv2.dilate(values, np.ones((5, 5), np.uint8))) & (values >= .3)
                for gy, gx in zip(*np.where(peaks)):
                    x, y = self.body.geo.tile((gx+.5)*540/68, 200+(gy+.5)*8)
                    if 0 <= x <= 18 and 0 <= y <= 32:
                        value = dict(card=card, side=side, x=x, y=y, confidence=float(values[gy, gx]))
                        (spells if card in self.spells else candidates).append(value)
            candidates.extend(self.spells_buffer.update(frame.timestamp_ms, spells,
                              [e.card for e in tracked.play_events if e.player_id == 1],
                              hud_reliable=min(public.own_hand_confidence) >= .7))
        events = self.fusion.update(str(frame.sequence), frame.timestamp_ms, candidates)
        finished = time.monotonic()
        converted = tuple(dict(card=e.card, side=e.player_id, x_tiles=e.x_tiles, y_tiles=e.y_tiles,
                         existence_q=e.confidence, card_distribution=((e.card, 1.),),
                         execution_timestamp_ms=frame.timestamp_ms, execution_sigma_ms=150.,
                         available_timestamp_ms=frame.timestamp_ms+(finished-frame.produced_at)*1000,
                         event_id=e.event_id) for e in events)
        return Observation(frame, replace(tracked, play_events=tuple(events)), converted,
                  visible_clock_phase(frame.pixels), finished,
                  dict(backbone_hud=(encoded-start)*1000, temporal_fusion=(finished-encoded)*1000))


class SyntheticPerception:
    """Only deterministic transport/fault tests; never selected for a real run."""
    def __init__(self, config):
        self.deck = config['deck']

    def step(self, frame):
        from clasher.rl.live_inference_contract import PublicVisionFrame
        public = PublicVisionFrame(frame.episode, str(frame.sequence), round(frame.timestamp_ms),
                    180-frame.timestamp_ms/1000, 1., 10., 1., tuple(self.deck[:4]), (1.,)*4,
                    self.deck[4], 1., (), ())
        return Observation(frame, public, (), 'regulation', time.monotonic(),
                           dict(backbone_hud=0., temporal_fusion=0.))


def make_perception(config):
    return {'v4': V4Perception, 'v3': V3Fallback, 'synthetic': SyntheticPerception}[config['kind']](config)
