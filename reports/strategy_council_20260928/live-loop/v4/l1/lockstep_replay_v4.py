"""Validation-only lockstep experiment; never a production admission certificate.

Each slot owns nine trackers/HUD histories/fusions and one feature ring. Ordinary
batching is opt-in and must pass tensor and full-record equality. ``graph`` keeps
the original batch-one reductions inside one CUDA graph launch for the causal
step. Encoder lookahead never sees truth and does not advance causal state.
"""
import argparse
from collections import deque
from contextlib import ExitStack
from dataclasses import asdict
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import socket
import subprocess
import shutil
import time

import numpy as np
import torch
from torch.nn import functional as F

from clasher.vision import l1_v4 as runtime
from decoder_records_v4 import RecordedEventFusion
from shared_temporal_v4 import prefix, tail

BRANCHES = tuple(range(1, 10))
HUD_KEYS = ('own_hand', 'next_card', 'own_elixir', 'hud_card_probabilities',
            'clock_seconds', 'phase')


def frame_times(frames):
    # Same validation and arithmetic as validation_replay_v4.frame_times, kept
    # local so the experiment does not import production admission machinery.
    if not frames:
        raise ValueError('Empty validation episode')
    times = []
    for i, frame in enumerate(frames):
        value = frame['produced_at']
        if (type(frame['seq']) is not int or frame['seq'] != i or isinstance(value, bool)
                or not isinstance(value, (int, float)) or not math.isfinite(value)):
            raise ValueError('Invalid frame identity/production timestamp')
        times.append(value)
    if any(b <= a for a, b in zip(times, times[1:])):
        raise ValueError('Nonchronological validation frames')
    return [(value-times[0])*1000 for value in times]


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def json_bytes(value):
    # Same whitespace/key order as the admitted capture writer.
    return (json.dumps(value, allow_nan=False) + '\n').encode()


def nonclock(payload):
    result = dict(payload)
    result.pop('available_timestamp_ms', None)
    result['event_candidates'] = [
        {k: v for k, v in row.items() if k != 'available_timestamp_ms'}
        for row in result['event_candidates']]
    return result


def tensor_equal(a, b):
    """Bit equality including signed zero, unlike torch.equal on floats."""
    return (a.dtype == b.dtype and a.shape == b.shape
            and torch.equal(a.contiguous().view(torch.uint8),
                            b.contiguous().view(torch.uint8)))


def exact_hypot(dx, dy):
    # numpy.hypot can differ from CPython math.hypot by one ULP. Hungarian
    # assignment ties depend on those bits; broadcast pairs, keep the old op.
    return np.frompyfunc(math.hypot, 2, 1)(dx, dy).astype(np.float64)


class Trackers:
    """Broadcast association across lanes; independent exact Hungarian solves.

    No detection cap, track eviction, changed tie-breaking, or approximate
    distance. Dictionary insertion order and the high/low two-pass order match
    BodyTracker. The expensive nested pair loops become numpy broadcasts.
    """
    def __init__(self, highs):
        self.highs = list(highs)
        self.tracks = [{} for _ in highs]
        self.next_ids = [0 for _ in highs]

    def update(self, detections, now):
        from scipy.optimize import linear_sum_assignment
        if not (len(detections) == len(now) == len(self.tracks)):
            raise ValueError('One detection list/public time per tracker lane')
        self.tracks = [{i: t for i, t in ts.items() if stamp-t['seen'] <= 600}
                       for ts, stamp in zip(self.tracks, now)]
        unmatched = [set(ts) for ts in self.tracks]
        observed = [[] for _ in now]
        births = [[] for _ in now]
        for high in (True, False):
            ds = [[d for d in rows if (d['confidence'] >= threshold if high else
                   .1 <= d['confidence'] < threshold)]
                  for rows, threshold in zip(detections, self.highs)]
            ids = [sorted(u) for u in unmatched]
            nt = max(map(len, ids), default=0)
            nd = max(map(len, ds), default=0)
            costs = np.full((len(now), nt, nd), 1e6, dtype=np.float64)
            if nt and nd:
                tx = np.zeros((len(now), nt, 2), dtype=np.float64)
                dx = np.zeros((len(now), nd, 2), dtype=np.float64)
                tk = np.full((len(now), nt), -1, dtype=np.int64)
                dk = np.full((len(now), nd), -2, dtype=np.int64)
                names = {}
                def key(d):
                    k = (d['identity'], d['owner'])
                    return names.setdefault(k, len(names))
                for lane, (tids, rows) in enumerate(zip(ids, ds)):
                    for j, tid in enumerate(tids):
                        d = self.tracks[lane][tid]
                        tx[lane, j] = d['x'], d['y']; tk[lane, j] = key(d)
                    for j, d in enumerate(rows):
                        dx[lane, j] = d['x'], d['y']; dk[lane, j] = key(d)
                same = tk[:, :, None] == dk[:, None, :]
                delta = tx[:, :, None] - dx[:, None, :]
                costs[same] = exact_hypot(delta[..., 0][same], delta[..., 1][same])
            for lane, (tids, rows, stamp) in enumerate(zip(ids, ds, now)):
                paired = set()
                cost = costs[lane, :len(tids), :len(rows)]
                if cost.size:
                    ii, jj = linear_sum_assignment(cost)
                    for i, j in zip(ii, jj):
                        if cost[i, j] > 1.5:
                            continue
                        tid = tids[i]; old = self.tracks[lane][tid]
                        d = dict(rows[j]); paired.add(j); unmatched[lane].discard(tid)
                        if d['hp_fraction'] is None:
                            d['hp_fraction'] = old['hp_fraction']
                        d.update(track_id=tid, seen=stamp, hits=old['hits']+1)
                        self.tracks[lane][tid] = d; observed[lane].append(d)
                        if d['hits'] == 2:
                            births[lane].append(d)
                if high:
                    for j, d in enumerate(rows):
                        if j in paired:
                            continue
                        tid = self.next_ids[lane]; self.next_ids[lane] += 1
                        self.tracks[lane][tid] = dict(d, track_id=tid, seen=stamp, hits=1)
        return [[d for d in rows if d['hits'] >= 2] for rows in observed], births


def birth_maps_many(births, sources, now, device, *, groups=False):
    """Exact ordered float32 scatter on CPU, one transfer and max pool."""
    from clasher.vision.l1_events_v3 import SPAWN_SOURCES, GROUP_COUNTS
    result = np.zeros((len(births), 2, 64, 36), dtype=np.float32)
    for lane, (rows, src, stamp) in enumerate(zip(births, sources, now)):
        src = [dict(s, card=runtime.body_action(s['card'])) for s in src]
        if src:
            sx = np.array([s['x'] for s in src], dtype=np.float64)
            sy = np.array([s['y'] for s in src], dtype=np.float64)
        indices = []; increments = []
        for b in rows:
            card = runtime.body_action(b['identity'])
            if src:
                compatible = np.array([s['card'] in SPAWN_SOURCES.get(card, ())
                    and s['side'] == b['owner'] and stamp-s['time'] <= 1600
                    for s in src], dtype=bool)
                if compatible.any():
                    distances = exact_hypot(sx[compatible]-b['x'], sy[compatible]-b['y'])
                    radii = np.array([s.get('radius', 4) for s, yes in zip(src, compatible) if yes])
                    if (distances <= radii).any():
                        continue
            x = min(35, max(0, int(b['x']*2)))
            y = min(63, max(0, int(b['y']*2)))
            indices.append((b['owner']*64+y)*36+x)
            increments.append(np.float32(1/GROUP_COUNTS.get(card, (1, 1))[0]))
        # add.at retains repeated-cell addition order, including rounded thirds.
        if indices:
            np.add.at(result[lane].reshape(-1), indices, increments)
    pooled = F.max_pool2d(torch.from_numpy(result).to(device), 7, 1, 3).clamp(max=8)
    if not groups:
        return pooled
    if len(births) % 9:
        raise ValueError('Nine branches per match required for tail reuse')
    representatives = []
    for first in range(0, len(births), 9):
        seen = {}; aliases = []
        for branch in range(9):
            # Equality before maxpool is sufficient to establish equality
            # afterwards. Nonnegative float32 maps use exact byte equality.
            key = result[first+branch].tobytes()
            aliases.append(seen.setdefault(key, branch))
        representatives.append(tuple(aliases))
    return pooled, tuple(representatives)


def body_packet(out):
    heat = out['body_heatmap'][0].detach().float(); scores = heat.sigmoid()
    peaks = scores == F.max_pool2d(scores[None], 3, 1, 1)[0]
    values, indices = (scores*peaks).flatten().topk(min(128, scores.numel()))
    cls = indices//(64*36); cell = indices % (64*36); y = cell//36; x = cell % 36
    visible = out['body_hp_visible'][0, 0, y, x].sigmoid().float()
    hp = out['body_hp'][0, 0, y, x].float()
    boxes = out['body_box'][0, :, y, x].detach().float().transpose(0, 1)
    return torch.cat((torch.stack((values, cls, x, y, visible, hp), 1), boxes), 1)


def decode_body_packets(outputs, names):
    packets = [body_packet(out) for out in outputs]
    packed = torch.cat(packets).cpu().tolist(); offset = 0; result = []
    for packet in packets:
        rows = []
        for r in packed[offset:offset+len(packet)]:
            if r[0] < .1:
                continue
            owner, identity = divmod(int(r[1]), len(names))
            rows.append(dict(identity=names[identity], owner=owner, x=(r[2]+.5)/2,
                y=(r[3]+.5)/2, confidence=r[0], box=r[6:],
                hp_fraction=r[5] if r[4] >= .5 else None))
        result.append(rows); offset += len(packet)
    return result


def event_packet(out, cards):
    # Preserve the vectorized decoder's per-frame softmax/topk reductions. No
    # cross-match classifier/distribution reduction is introduced here.
    heat = out['event_heatmap'][0].detach().float(); scores = heat.sigmoid()
    peaks = scores == F.max_pool2d(scores[None], 3, 1, 1)[0]
    values, indices = (scores*peaks).flatten().topk(min(256, scores.numel()))
    keep = values >= .1; values = values[keep]; indices = indices[keep]
    cls = indices//(64*36); cell = indices % (64*36); gy = cell//36; gx = cell % 36
    n = len(cards); side = cls//n; card_index = cls % n
    channels = side[:, None]*n + torch.arange(n, device=heat.device)[None, :]
    probabilities, identities = heat[channels, gy[:, None], gx[:, None]].softmax(1).topk(min(3, n), dim=1)
    age = out['event_age_ms'][0, cls, gy, gx].float()
    sigma = out['event_sigma_ms'][0, cls, gy, gx].float()
    origins = ('Rocket', 'Fireball', 'Arrows', 'Log', 'GoblinBarrel')
    mapping = torch.tensor([origins.index(c) if c in origins else -1 for c in cards], device=heat.device)
    origin_index = mapping[card_index]
    origin = out['cast_origin'][0, side*5+origin_index.clamp_min(0), gy, gx].sigmoid().float()
    if heat.device.type == 'cpu' and len(values):
        # CPU vector sigmoid uses a different approximation from scalar
        # sigmoid. Keep the original scalar operation on this backend.
        origin = torch.stack([out['cast_origin'][0, int(s)*5+max(0, int(o)), int(y), int(x)].sigmoid()
            for s, o, y, x in zip(side, origin_index, gy, gx)]).float()
    return torch.cat((torch.stack((values, card_index, side, gx, gy, age, sigma, origin_index, origin), 1),
                      identities, probabilities), 1)


def decode_event_packets(outputs, cards, stamps):
    unique = {}; selected = []; indices = []
    for out, stamp in zip(outputs, stamps):
        key = id(out), stamp
        if key not in unique:
            unique[key] = len(selected); selected.append((out, stamp))
        indices.append(unique[key])
    packets = [event_packet(out, cards) for out, stamp in selected]
    packed = torch.cat(packets).cpu().tolist(); offset = 0; result = []; k = min(3, len(cards))
    for packet, (out, stamp) in zip(packets, selected):
        rows = []
        for r in packed[offset:offset+len(packet)]:
            q, identity, side, x, y, age, sigma, origin_id, origin = r[:9]
            rows.append(dict(card=cards[int(identity)], side=int(side), x_tiles=(x+.5)/2, y_tiles=(y+.5)/2,
                execution_timestamp_ms=stamp-age, execution_sigma_ms=sigma, existence_q=q,
                card_distribution=[(cards[int(i)], p) for i, p in zip(r[9:9+k], r[9+k:])],
                cast_origin_probability=origin if origin_id >= 0 else None))
        result.append(rows); offset += len(packet)
    return [result[i] for i in indices]


def split_outputs(out):
    return [{k: v[i:i+1] for k, v in out.items()} for i in range(len(next(iter(out.values()))))]


class CausalWork:
    """One graph replay over all slots; each branch retains batch-one shapes."""
    def __init__(self, head, mode='scalar', prefix_batch=1, tail_batch=1):
        if mode not in ('scalar', 'graph'):
            raise ValueError('Unknown causal execution mode')
        self.head = head; self.mode = mode
        self.prefix_batch = prefix_batch; self.tail_batch = tail_batch
        self.graph = None; self.key = None

    def compute(self, cache, ages, valid, births, representatives=None):
        n = len(cache)
        if representatives is None:
            representatives = tuple(tuple(range(9)) for _ in range(n))
        mixed = []
        for start in range(0, n, self.prefix_batch):
            end = min(n, start+self.prefix_batch)
            value = prefix(self.head, cache[start:end], ages[start:end], valid[start:end])
            mixed.extend(value[i:i+1] for i in range(len(value)))
        outputs = [[None]*9 for _ in range(n)]
        # Batch matches within the same branch only. Nine branches never share
        # tracker state or enter one tensor reduction dimension.
        for branch in range(9):
            active = [slot for slot in range(n) if representatives[slot][branch] == branch]
            for start in range(0, len(active), self.tail_batch):
                slots = active[start:start+self.tail_batch]
                if len(slots) == 1:
                    s = slots[0]
                    value = tail(self.head, mixed[s], births[s:s+1, branch], valid[s:s+1])
                else:
                    value = tail(self.head, torch.cat([mixed[s] for s in slots]),
                        torch.cat([births[s:s+1, branch] for s in slots]), torch.cat([valid[s:s+1] for s in slots]))
                for slot, out in zip(slots, split_outputs(value)):
                    outputs[slot][branch] = out
            for slot in range(n):
                representative = representatives[slot][branch]
                if representative != branch:
                    outputs[slot][branch] = outputs[slot][representative]
        return outputs

    @torch.inference_mode()
    def __call__(self, cache, ages, valid, births, representatives=None):
        if self.mode == 'scalar':
            return self.compute(cache, ages, valid, births, representatives)
        if cache.device.type != 'cuda':
            raise ValueError('CUDA graph requires CUDA')
        args = (cache, ages, valid, births)
        key = tuple((a.shape, a.dtype, a.device) for a in args), representatives
        if self.key != key:
            # Only the current shape is retained, bounding variable-length
            # match tails. No reset of any match's causal state occurs.
            self.graph = None; self.output = None
            self.static = tuple(a.clone() for a in args)
            stream = torch.cuda.Stream(); stream.wait_stream(torch.cuda.current_stream())
            with torch.cuda.stream(stream):
                for _ in range(2):
                    self.compute(*self.static, representatives)
            torch.cuda.current_stream().wait_stream(stream)
            self.graph = torch.cuda.CUDAGraph()
            with torch.cuda.graph(self.graph):
                self.output = self.compute(*self.static, representatives)
            self.key = key
        for dst, src in zip(self.static, args):
            dst.copy_(src)
        self.graph.replay()
        return self.output


class Branch:
    def __init__(self, cards, spells):
        self.sources = []; self.own_plays = []
        self.last_hand = None; self.last_elixir = None
        self.fusion = RecordedEventFusion(spells, {'default': .5}, {})

    def hud(self, out, cards, stamp):
        # Original shape5 x vocab softmax, before concatenating host transfers.
        probs = out['hud_cards'][0].float().softmax(-1)
        ids = probs.argmax(-1).tolist()
        names = [cards[i] if i < len(cards) else None for i in ids]
        elixir = int(out['elixir_digit'][0].argmax()) + float(out['elixir_fraction'][0])
        self.own_plays = [p for p in self.own_plays if stamp-p[1] <= 600]
        if (self.last_hand is not None and self.last_elixir-elixir >= .5
                and float(probs[:4].max(-1).values.min()) >= .7):
            for old, new in zip(self.last_hand, names[:4]):
                if old and old != new:
                    self.own_plays.append((old, stamp))
        self.last_hand = names[:4]; self.last_elixir = elixir
        return dict(own_hand=names[:4], next_card=names[4], own_elixir=min(10, elixir),
            hud_card_probabilities=probs.cpu().tolist(), clock_seconds=float(out['clock_seconds'][0]),
            phase=int(out['phase'][0].argmax())+1)


class LockstepReplay:
    def __init__(self, base, cards, bodies, spells, episodes, *, device='cpu',
                 mode='scalar', encoder_batch=1, prefix_batch=1, tail_batch=1):
        if len(set(episodes)) != len(episodes) or not episodes:
            raise ValueError('Unique nonempty match slots required')
        self.base = base.to(device).eval(); self.device = device
        self.cards = cards; self.bodies = bodies; self.episodes = tuple(episodes)
        self.rings = {ep: runtime.FeatureRing() for ep in episodes}
        self.branches = {ep: [Branch(cards, spells) for _ in BRANCHES] for ep in episodes}
        self.trackers = Trackers([i/10 for ep in episodes for i in BRANCHES])
        self.encoder_batch = encoder_batch
        self.work = CausalWork(base.temporal, mode, prefix_batch, tail_batch)
        self.counts = dict.fromkeys(episodes, 0)

    @torch.inference_mode()
    def encode(self, pixel_pairs):
        def tensor(images):
            # Keep the reference permute layout; convolution choices can depend
            # on strides. A stack/contiguous NCHW silently changes that layout.
            if len(images) == 1:
                # Exactly the PixelPerception tensor constructor, including
                # singleton strides retained during the device transfer.
                return torch.from_numpy(images[0].copy()).permute(2, 0, 1)[None].to(self.device).float()/255
            return torch.from_numpy(np.stack(images)).permute(0, 3, 1, 2).to(self.device).float()/255
        result = []
        for start in range(0, len(pixel_pairs), self.encoder_batch):
            rows = pixel_pairs[start:start+self.encoder_batch]
            result.extend(split_outputs(self.base.encode(tensor([r[0] for r in rows]), tensor([r[1] for r in rows]))))
        return result

    @torch.inference_mode()
    def step(self, episodes, stamps, encoded):
        if (len(episodes) != len(stamps) or len(stamps) != len(encoded)
                or len(set(episodes)) != len(episodes) or not set(episodes) <= set(self.episodes)):
            raise ValueError('Invalid active match slots')
        detections = decode_body_packets(encoded, self.bodies)
        for ep, stamp, out in zip(episodes, stamps, encoded):
            self.rings[ep].append(stamp, out['features'][0])
        # Update every lane together; inactive lanes retain state verbatim.
        indices = [self.episodes.index(ep)*9+i for ep in episodes for i in range(9)]
        selected = Trackers([self.trackers.highs[j] for j in indices])
        selected.tracks = [self.trackers.tracks[j] for j in indices]
        selected.next_ids = [self.trackers.next_ids[j] for j in indices]
        tracks, births = selected.update([d for d in detections for _ in BRANCHES],
                                         [s for s in stamps for _ in BRANCHES])
        sources = []; now = []; hud = []
        for slot, (ep, stamp, out) in enumerate(zip(episodes, stamps, encoded)):
            # HUD history is identical across body branches; keep separate
            # histories but only evaluate the GPU probabilities once.
            value = self.branches[ep][0].hud(out, self.cards, stamp)
            for i, branch in enumerate(self.branches[ep]):
                lane = slot*9+i
                if i:
                    first = self.branches[ep][0]
                    branch.own_plays = list(first.own_plays)
                    branch.last_hand = list(first.last_hand); branch.last_elixir = first.last_elixir
                branch.sources = [s for s in branch.sources if stamp-s['time'] <= 1600] + [
                    dict(card=t['identity'], side=t['owner'], x=t['x'], y=t['y'], time=stamp) for t in tracks[lane]]
                sources.append(branch.sources); now.append(stamp); hud.append(value)
        for j, lane in enumerate(indices):
            self.trackers.tracks[lane] = selected.tracks[j]
            self.trackers.next_ids[lane] = selected.next_ids[j]
        maps, representatives = birth_maps_many(births, sources, now, self.device, groups=True)
        maps = maps.reshape(len(episodes), 9, 2, 64, 36)
        windows = [self.rings[ep].window() for ep in episodes]
        cache, ages, valid = (torch.cat([w[j] for w in windows]) for j in range(3))
        events = self.work(cache, ages, valid, maps, representatives)
        peaks = decode_event_packets([e for row in events for e in row], self.cards, now)
        result = []
        for slot, (ep, stamp) in enumerate(zip(episodes, stamps)):
            for i, branch in enumerate(self.branches[ep]):
                lane = slot*9+i
                candidates = branch.fusion.update(peaks[lane], stamp, stamp, [c for c, _ in branch.own_plays])
                payload = dict(episode_id=ep, timestamp_ms=stamp, tracks=tracks[lane], **hud[lane],
                               event_candidates=[asdict(e) for e in candidates], available_timestamp_ms=stamp)
                record = dict(schema='clasher.v4.decoder-frame.v1', source_seq=self.counts[ep],
                    episode_id=ep, timestamp_ms=stamp, bodies=detections[slot], event_peaks=peaks[lane],
                    causal_own_hud_cards=[c for c, _ in branch.own_plays], hud=hud[lane])
                result.append((ep, i+1, record, payload))
            self.counts[ep] += 1
        return result


class RecordWriter:
    """One write/flush per lane per block, then real completion timestamps.

    Measured FIFO intervals include lookahead/cache/model/serialization. Buffered
    frames conservatively become available at their block's flush. Clocks are
    new experiment clocks, never copied from the serial baseline.
    """
    def __init__(self, root, episodes, stack, *, payloads=False, clock=time.perf_counter):
        self.clock = clock; self.started = clock(); self.last = self.started
        self.handles = {}; self.journals = {}; self.payload_handles = {}
        self.pending = {}; self.ready = {}; self.hashes = {}; self.payloads = payloads
        for i in BRANCHES:
            folder = root/f'body-{i}'; folder.mkdir()
            for ep in episodes:
                key = ep, i
                self.handles[key] = stack.enter_context(gzip.open(folder/f'{ep}-decoder.jsonl.gz', 'xb', compresslevel=1))
                self.journals[key] = stack.enter_context((folder/f'{ep}-completion.jsonl').open('x'))
                if payloads:
                    self.payload_handles[key] = stack.enter_context(gzip.open(folder/f'{ep}-payload.jsonl.gz', 'xb', compresslevel=1))
                self.pending[key] = []; self.ready[key] = 0.; self.hashes[key] = hashlib.sha256()

    def append(self, rows):
        for ep, i, record, payload in rows:
            blob = json_bytes(record); self.hashes[ep, i].update(blob)
            self.pending[ep, i].append((record['source_seq'], record['timestamp_ms'], blob,
                                      json_bytes(nonclock(payload)) if self.payloads else None))

    def flush(self):
        active = {k: rows for k, rows in self.pending.items() if rows}
        if not active:
            return
        for key, rows in active.items():
            self.handles[key].write(b''.join(r[2] for r in rows)); self.handles[key].flush()
            if self.payloads:
                self.payload_handles[key].write(b''.join(r[3] for r in rows)); self.payload_handles[key].flush()
        finished = self.clock(); service = (finished-self.last)*1000
        for key, rows in active.items():
            lines = []
            for j, (seq, stamp, _, _) in enumerate(rows):
                # Charge the block to its first frame; subsequent records were
                # already flushed. All branches include whole-shard wall cost.
                duration = service if j == 0 else 0.
                self.ready[key] = max(self.ready[key], stamp)+duration
                lines.append(json.dumps(dict(episode_id=key[0], source_seq=seq, timestamp_ms=stamp,
                    service_ms=duration, available_timestamp_ms=self.ready[key]))+'\n')
            self.journals[key].write(''.join(lines)); self.journals[key].flush()
            self.pending[key].clear()
        self.last = finished


def gpu_snapshot():
    output = subprocess.check_output(['nvidia-smi', '--query-gpu=index,memory.free,utilization.gpu',
                                      '--format=csv,noheader,nounits'], text=True)
    return [dict(zip(('index', 'free_mib', 'utilization_percent'), map(int, row.split(','))))
            for row in output.strip().splitlines()]


def resource_guard():
    host = socket.gethostname().split('.')[0]
    if host != '127x08' or os.environ.get('CLASHER_LOCKSTEP_GPU_AUTHORIZED') != host:
        raise ValueError('01 authorization revoked;02 excluded;08 only after owner assigns window')
    path = os.environ.get('CLASHER_LOCKSTEP_OWNER_WINDOW_FILE')
    digest = os.environ.get('CLASHER_LOCKSTEP_OWNER_WINDOW_SHA256')
    if not path or not digest or sha(Path(path)) != digest:
        raise ValueError('Externally pinned coordinator08 window required')
    window = json.loads(Path(path).read_text())
    start = window['starts_at_unix']; end = window['ends_at_unix']
    if (window.get('schema') != 'clasher.v4.lockstep-owner-window.v1' or window.get('host') != host
            or window.get('t5_gru_exit_checked') is not True or window.get('authorized_by') != 'coordinator'
            or type(start) not in (int, float) or type(end) not in (int, float)
            or not math.isfinite(start) or not math.isfinite(end) or start < 1791522000
            or not 0 < end-start <= 300 or not start <= time.time() < end):
        raise ValueError('Outside assigned<=5-minute08 window after05:00Z/T5 exit check')
    if os.getpriority(os.PRIO_PROCESS, 0) < 10:
        raise ValueError('nice>=10 required')
    memory = {row.split(':')[0]: int(row.split()[1]) for row in Path('/proc/meminfo').read_text().splitlines()}
    if memory['MemAvailable'] < 24*1024**2:
        raise ValueError('Stop: MemAvailable below24GiB')
    free, _ = torch.cuda.mem_get_info()
    if free < 8*1024**3:
        raise ValueError('Stop: less than8GiB GPU headroom')


def validate_bundle(bundle):
    manifest = json.loads((bundle/'manifest.json').read_text())
    stage = json.loads((bundle/'stage-complete.json').read_text())
    if sha(bundle/'manifest.json') != stage['manifest_sha256']:
        raise ValueError('Bundle manifest changed')
    for name, digest in manifest['files_sha256'].items():
        path = bundle/name
        if not path.resolve().is_relative_to(bundle.resolve()) or sha(path) != digest:
            raise ValueError('Changed or escaping bundle input: '+name)
    episodes = sorted(manifest['validation_episodes'])
    if len(episodes) != 64 or len(set(episodes)) != 64:
        raise ValueError('Authenticated64-match validation population required')
    receipts = {}; frames = {}
    for ep in episodes:
        if '/' in ep or not ep.startswith('v4-phase-a-'):
            raise ValueError('Unsafe episode identity')
        folder = bundle/'matches'/ep
        r = json.loads((folder/'receipt.json').read_text())
        if r['episode'] != ep or r['split'] != 'validation':
            raise ValueError('Validation only')
        if sha(folder/'frames.jsonl') != r['files']['frames.jsonl']:
            raise ValueError('Changed frame metadata')
        rows = [json.loads(line) for line in (folder/'frames.jsonl').read_text().splitlines()]
        frame_times(rows)
        if len(rows) != r['frames']:
            raise ValueError('Incomplete frames')
        frames[ep] = rows; receipts[ep] = dict(r, receipt_sha256=sha(folder/'receipt.json'))
    if sum(map(len, frames.values())) != 106744:
        raise ValueError('Full validation frame population differs')
    return manifest, receipts, frames


def open_readers(a, receipts):
    from cache_transport_v4 import RangeStore, RemotePixelCache
    pins = {ep: sha(a.bundle/'fit/model/cache-indices'/ep/'index.json') for ep in receipts}
    if a.local_cache:
        expected = Path('/mpac/sdicks02/repos/clasher-v4-cache/post0500-validation-20261008-r1/cache')
        if socket.gethostname().split('.')[0] != '127x08' or a.local_cache.resolve() != expected:
            raise ValueError('Only owner verified08 cache in assigned window; never01 disk cache')
        cache = RangeStore(a.local_cache, list(receipts.values()), pins).cache
        return dict.fromkeys(receipts, cache)
    if a.connections.stat().st_mode & 0o077:
        raise ValueError('Private connections required')
    readers = {}
    for group in json.loads(a.connections.read_text())['shards']:
        members = set(group['episodes']) & set(receipts)
        if not members:
            continue
        if members & set(readers):
            raise ValueError('Overlapping cache shards')
        token = Path(group['token_file'])
        if token.stat().st_mode & 0o077:
            raise ValueError('Private token required')
        cache = RemotePixelCache(group['endpoint'], token.read_text().strip(),
                                 [receipts[e] for e in sorted(members)], {e: pins[e] for e in members})
        readers.update(dict.fromkeys(members, cache))
    if set(readers) != set(receipts):
        raise ValueError('Incomplete cache readers')
    return readers


def run(a):
    import cv2
    from clasher.data import CardDataLoader
    resource_guard(); torch.set_num_threads(1); cv2.setNumThreads(1)
    if a.deterministic:
        if os.environ.get('CUBLAS_WORKSPACE_CONFIG') not in (':4096:8', ':16:8'):
            raise ValueError('Set CUBLAS_WORKSPACE_CONFIG before starting Python')
        torch.use_deterministic_algorithms(True); torch.backends.cudnn.benchmark = False
    if a.output.exists():
        raise ValueError('Fresh experiment output required')
    root = Path('/mpac/sdicks02/repos/clasher-v4-cache')
    if not a.output.resolve().is_relative_to(root/'lockstep-20261009'):
        raise ValueError('Isolated lockstep experiment output required')
    manifest, receipts, frames = validate_bundle(a.bundle)
    episodes = sorted(receipts)[:a.match_limit]
    readers = open_readers(a, {ep: receipts[ep] for ep in episodes})
    checkpoint = a.bundle/'fit/model'/f'epoch-{a.epoch}.pt'
    state = torch.load(checkpoint, map_location='cpu', weights_only=True)
    os.environ['CLASHER_ROOT'] = str(a.bundle/'runtime')
    loader = CardDataLoader()
    spells = [c for c in state['cards'] if str(loader.get_card(c).card_type).lower() == 'spell']
    base = runtime.PerceptionV4(len(state['cards']), len(state['bodies'])); base.load_state_dict(state['model'])
    # Bound our allocator, preserving at least8GiB free even at full capacity.
    free, total = torch.cuda.mem_get_info()
    # CUDA context/driver overhead also counts toward coordinator's8GiB cap.
    torch.cuda.set_per_process_memory_fraction(min(7.25*1024**3/total, max(0., (free-8*1024**3)/total)))
    a.output.mkdir(parents=True)
    pinned = dict(schema='clasher.v4.lockstep-experiment.v1', formal_admitted=False, epoch=a.epoch,
        match_limit=a.match_limit, shard_size=a.batch_size, frame_limit=a.frame_limit, mode=a.mode,
        encoder_batch=a.encoder_batch, prefix_batch=a.prefix_batch, tail_batch=a.tail_batch,
        deterministic=a.deterministic, bundle_sha256=sha(a.bundle/'manifest.json'), checkpoint_sha256=sha(checkpoint),
        driver_sha256=sha(Path(__file__)), validation_only=True, heldout_payloads_opened=False,
        selection_seal=False, spells=spells, body_thresholds=[i/10 for i in BRANCHES], event_threshold=.5,
        precision='fp32', max_output_bytes=a.max_output_bytes,
        timing='measured block FIFO after serialization/flush; all lookahead included')
    (a.output/'manifest.json').write_bytes(json_bytes(pinned))
    gpu_samples = [gpu_snapshot()]; started = time.perf_counter(); counts = {}; hashes = {}
    with ExitStack() as stack:
        writer = RecordWriter(a.output, episodes, stack, payloads=a.payloads)
        for first in range(0, len(episodes), a.batch_size):
            shard = episodes[first:first+a.batch_size]
            engine = LockstepReplay(base, state['cards'], state['bodies'], spells, shard, device='cuda',
                mode=a.mode, encoder_batch=a.encoder_batch, prefix_batch=a.prefix_batch, tail_batch=a.tail_batch)
            times = {ep: frame_times(frames[ep])[:a.frame_limit or None] for ep in shard}
            lookahead = {}; longest = max(map(len, times.values()))
            for seq in range(longest):
                resource_guard()
                if seq % a.lookahead == 0:
                    # Encode noncausal data ahead in bounded chunks. Only the
                    # current frame features advance rings/trackers below.
                    lookahead = {}
                    for ep in shard:
                        ordinals = list(range(seq, min(seq+a.lookahead, len(times[ep]))))
                        if not ordinals:
                            continue
                        pairs = readers[ep].get(ep, ordinals, raw=False)
                        lookahead[ep] = engine.encode(pairs)
                active = [ep for ep in shard if seq < len(times[ep])]
                values = engine.step(active, [times[ep][seq] for ep in active],
                                      [lookahead[ep][seq % a.lookahead] for ep in active])
                writer.append(values)
                if (seq+1) % a.write_block == 0 or seq+1 == longest:
                    writer.flush(); gpu_samples.append(gpu_snapshot())
                    # Only our isolated directory is traversed. No global cache
                    # inventories or other workers' output trees are scanned.
                    if (sum(p.stat().st_size for p in a.output.rglob('*') if p.is_file()) > a.max_output_bytes
                            or shutil.disk_usage(a.output).free < 200_000_000_000):
                        raise ValueError('Experiment output cap/free disk floor; preserve partial')
                if (seq+1) % 128 == 0:
                    print(json.dumps(dict(epoch=a.epoch, shard=first//a.batch_size, step=seq+1)), flush=True)
            counts.update(engine.counts)
            del engine
        writer.flush(); hashes = {f'{ep}/body-{i}': h.hexdigest() for (ep, i), h in writer.hashes.items()}
    torch.cuda.synchronize(); seconds = time.perf_counter()-started
    complete = dict(pinned, schema='clasher.v4.lockstep-experiment-complete.v1', episodes=counts,
        frames=sum(counts.values()), seconds=seconds, frames_per_second_per_gpu=sum(counts.values())/seconds,
        record_stream_sha256=hashes, gpu_samples=gpu_samples,
        files_sha256={str(p.relative_to(a.output)): sha(p) for p in a.output.rglob('*') if p.is_file()})
    (a.output/'complete.json').write_bytes(json_bytes(complete)); print(json.dumps(complete), flush=True)


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('bundle', 'output'):
        p.add_argument('--'+name, type=Path, required=True)
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument('--local-cache', type=Path); group.add_argument('--connections', type=Path)
    p.add_argument('--epoch', type=int, choices=range(1, 25), required=True)
    p.add_argument('--match-limit', type=int, choices=(8, 16, 32, 64), default=64)
    p.add_argument('--batch-size', type=int, choices=(8, 16, 32, 64), default=8)
    p.add_argument('--frame-limit', type=int, default=0, help='0=complete matches; prefixes never satisfy full gate')
    p.add_argument('--mode', choices=('scalar', 'graph'), default='graph')
    for name in ('encoder-batch', 'prefix-batch', 'tail-batch'):
        p.add_argument('--'+name, type=int, choices=(1, 2, 4, 8, 16, 32, 64), default=1)
    p.add_argument('--lookahead', type=int, default=16)
    p.add_argument('--write-block', type=int, default=16)
    p.add_argument('--max-output-bytes', type=int, default=128*1024**2,
                   help='Bound new experiment storage; owner must allocate a larger full-match reservation')
    p.add_argument('--payloads', action='store_true'); p.add_argument('--deterministic', action='store_true')
    return p


if __name__ == '__main__':
    args = parser().parse_args()
    if (args.frame_limit < 0 or not 1 <= args.lookahead <= 64 or not 1 <= args.write_block <= 64
            or args.max_output_bytes < 1):
        raise ValueError('Invalid bounded frame/lookahead/write options')
    run(args)
