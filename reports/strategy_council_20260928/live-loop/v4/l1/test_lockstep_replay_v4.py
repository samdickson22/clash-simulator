"""CPU-only exactness/isolation tests; no corpus or heldout payload access."""
from contextlib import ExitStack
from dataclasses import asdict
import gzip
import json
import math
from pathlib import Path
import tempfile
import unittest

import numpy as np
import torch

from clasher.vision import l1_v4 as reference
from decoder_records_v4 import extract_event_records
from shared_model_v4 import SharedModel
from vectorized_decoder_v4 import bodies, event_records
from lockstep_replay_v4 import (Trackers, birth_maps_many, tensor_equal, exact_hypot,
    decode_body_packets, decode_event_packets, LockstepReplay, CausalWork,
    RecordWriter, nonclock, json_bytes)


def detection(identity='Knight', owner=0, x=5., y=6., q=.9, hp=.7):
    return dict(identity=identity, owner=owner, x=x, y=y, confidence=q,
                hp_fraction=hp, box=[.1, .2, .3, .4])


class FakeBase(torch.nn.Module):
    """Dense deterministic outputs with a real temporal head and tiny cache."""
    def __init__(self):
        super().__init__(); self.temporal = reference.TemporalHead(3)
        self.register_buffer('feature', torch.randn(1, 64, 2, 2))
        self.register_buffer('heat', torch.randn(1, 4, 64, 36))

    def encode(self, arena, hud):
        n = len(arena); offset = arena[:, :1, :1, :1]*.01
        return dict(features=self.feature.expand(n, -1, -1, -1)+offset,
            body_heatmap=self.heat.expand(n, -1, -1, -1)+offset,
            body_box=torch.full((n, 4, 64, 36), .5), body_hp=torch.full((n, 1, 64, 36), .7),
            body_hp_visible=torch.ones(n, 1, 64, 36),
            hud_cards=torch.tensor([[[8., 0., 0., 0.]]*5]).expand(n, -1, -1),
            elixir_digit=torch.tensor([[0., 0., 8., 0., 0., 0., 0., 0., 0., 0., 0.]]).expand(n, -1),
            elixir_fraction=torch.full((n,), .3), clock_seconds=torch.full((n,), 30.),
            phase=torch.tensor([[1., 0., 0.]]).expand(n, -1))


class LockstepTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)

    def test_distance_bits_and_signed_zero(self):
        rng = np.random.default_rng(6125)
        dx = rng.normal(size=1000); dy = rng.normal(size=1000)
        actual = exact_hypot(dx, dy)
        expected = np.array([math.hypot(x, y) for x, y in zip(dx, dy)])
        self.assertTrue(np.array_equal(actual.view(np.uint64), expected.view(np.uint64)))
        self.assertFalse(tensor_equal(torch.tensor([0.]), torch.tensor([-0.])))

    def test_tracker_all_branches_dense_ties_gaps_low_and_hp(self):
        rng = np.random.default_rng(6126)
        highs = [i/10 for _ in range(3) for i in range(1, 10)]
        expected = [reference.BodyTracker(high=q) for q in highs]
        actual = Trackers(highs)
        for step, stamp in enumerate((0., 50., 100., 200., 850., 900., 1000.)):
            ds = []
            for lane in range(len(highs)):
                rows = [detection(identity=('Knight', 'Skeleton')[j % 2], owner=j % 2,
                    x=float(rng.integers(0, 36))/2, y=float(rng.integers(0, 64))/2,
                    q=float(rng.choice([.05, .1, .2, .5, .9])), hp=None if step % 2 else .7)
                    for j in range(45)]
                rows += [detection(x=4., y=4., q=.9, hp=None if step % 2 else .7)]*3
                ds.append(rows)
            now = [stamp+lane*3 for lane in range(len(highs))]
            tracks, births = actual.update(ds, now)
            for i, (tracker, rows, t) in enumerate(zip(expected, ds, now)):
                want_tracks, want_births = tracker.update(rows, t)
                self.assertEqual(tracks[i], want_tracks)
                self.assertEqual(births[i], want_births)
                self.assertEqual(actual.tracks[i], tracker.tracks)
                self.assertEqual(actual.next_ids[i], tracker.next_id)

    def test_births_exact_repeated_thirds_suppression_and_edges(self):
        births = [[detection('Bat', x=2.25, y=3.25)]*11,
                  [detection('Skeleton', x=4., y=4.), detection(x=-2., y=35.)], []]
        sources = [[], [dict(card='Witch', side=0, x=4., y=4., time=10.)], []]
        stamps = [50., 50., 5000.]
        actual = birth_maps_many(births, sources, stamps, 'cpu')
        expected = torch.cat([reference.birth_maps(b, s, t) for b, s, t in zip(births, sources, stamps)])
        self.assertTrue(tensor_equal(actual, expected))

    def test_tail_reuse_keeps_original_shapes_and_separate_branches(self):
        torch.manual_seed(6130)
        head = reference.TemporalHead(3).eval()
        cache = torch.randn(2, 16, 64, 2, 2); ages = torch.zeros(2, 16)
        valid = torch.ones(2, 16, dtype=torch.bool); maps = torch.zeros(2, 9, 2, 64, 36)
        maps[1, 4, 0, 20, 20] = 1.
        shapes = []
        hook = head.birth.register_forward_pre_hook(lambda module, args: shapes.append(tuple(args[0].shape)))
        with torch.inference_mode():
            work = CausalWork(head)
            expected = work(cache, ages, valid, maps)
            self.assertEqual(len(shapes), 18); shapes.clear()
            actual = work(cache, ages, valid, maps, ((0,)*9, (0, 0, 0, 0, 4, 0, 0, 0, 0)))
        hook.remove()
        self.assertEqual(shapes, [(1, 2, 64, 36)]*3)
        for left, right in zip(expected, actual):
            for a, b in zip(left, right):
                self.assertTrue(all(tensor_equal(a[k], b[k]) for k in a))

    def test_record_extraction_bit_exact_ties_dense_and_empty(self):
        torch.manual_seed(6127)
        outputs = []
        for offset in (0., -100.):
            heat = torch.randn(1, 6, 64, 36)+offset
            outputs.append(dict(body_heatmap=heat, body_box=torch.rand(1, 4, 64, 36),
                body_hp=torch.rand(1, 1, 64, 36), body_hp_visible=torch.randn(1, 1, 64, 36),
                event_heatmap=heat, event_age_ms=torch.rand_like(heat)*1500,
                event_sigma_ms=torch.rand_like(heat)*100+10, cast_origin=torch.randn(1, 10, 64, 36)))
        cards = ['Knight', 'Fireball', 'Rocket']; names = ['Knight', 'Skeleton', 'Bat']
        for i, row in enumerate(decode_body_packets(outputs, names)):
            self.assertEqual(json_bytes(row), json_bytes(reference.decode_bodies(outputs[i], names, .1)))
            self.assertEqual(json_bytes(row), json_bytes(bodies(outputs[i], names, .1)))
        for i, row in enumerate(decode_event_packets(outputs, cards, [0., 1500.])):
            self.assertEqual(json_bytes(row), json_bytes(extract_event_records(outputs[i], cards, i*1500.)))
            # The quarantined vectorized decoder can differ onCPU scalar
            # sigmoid origins; original admitted operations are authoritative.

    def test_scalar_lockstep_against_original_pixel_runtime(self):
        torch.manual_seed(6128)
        base = FakeBase().eval(); cards = ['Knight', 'Fireball', 'Rocket']; names = ['Knight', 'Skeleton']
        spells = ['Fireball', 'Rocket']; episodes = ['synthetic-a', 'synthetic-b']
        engine = LockstepReplay(base, cards, names, spells, episodes)
        class Recorded(SharedModel):
            def temporal(self, *args):
                self.event = super().temporal(*args); return self.event
        models = {ep: Recorded(base) for ep in episodes}
        refs = {ep: [reference.PixelPerception(models[ep], cards, names, spells, {'default': .5}, {},
                    body_threshold=i/10) for i in range(1, 10)] for ep in episodes}
        for seq in range(4):
            active = episodes if seq < 3 else episodes[:1]
            images = [np.full((1140, 540, 3), seq+slot, np.uint8) for slot, ep in enumerate(active)]
            stamps = [seq*100.+slot*17 for slot, ep in enumerate(active)]
            encoded = engine.encode([reference.prepare_pixels(im) for im in images])
            actual = engine.step(active, stamps, encoded)
            for ep, branch, record, payload in actual:
                slot = active.index(ep); model = models[ep]
                if branch == 1:
                    model.begin_frame()
                r = refs[ep][branch-1]
                value = r.step(images[slot], ep, stamps[slot])
                expected = dict(schema='clasher.v4.decoder-frame.v1', source_seq=seq, episode_id=ep,
                    timestamp_ms=stamps[slot], bodies=reference.decode_bodies(model.encoded, names, .1),
                    event_peaks=extract_event_records(model.event, cards, stamps[slot]),
                    causal_own_hud_cards=[c for c, _ in r.own_plays],
                    hud={k: value[k] for k in ('own_hand', 'next_card', 'own_elixir',
                        'hud_card_probabilities', 'clock_seconds', 'phase')})
                self.assertEqual(json_bytes(record), json_bytes(expected))
                self.assertEqual(json_bytes(nonclock(payload)), json_bytes(nonclock(value)))
        self.assertEqual(engine.counts, {'synthetic-a': 4, 'synthetic-b': 3})
        self.assertEqual(len(engine.rings['synthetic-b'].frames), 3)

    def test_buffered_writer_hashes_and_fifo_after_flush(self):
        ticks = iter((1., 1.2, 1.5))
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            root = Path(directory)
            writer = RecordWriter(root, ['ep'], stack, clock=lambda: next(ticks))
            rows = [(dict(source_seq=i, timestamp_ms=i*50.), {}) for i in range(3)]
            for record, payload in rows:
                writer.append([('ep', 1, record, payload)])
            writer.flush()
            writer.append([('ep', 1, dict(source_seq=3, timestamp_ms=150.), {})]); writer.flush()
            stack.close()
            with gzip.open(root/'body-1/ep-decoder.jsonl.gz', 'rb') as f:
                data = f.read()
            self.assertEqual(writer.hashes['ep', 1].hexdigest(), __import__('hashlib').sha256(data).hexdigest())
            journal = [json.loads(s) for s in (root/'body-1/ep-completion.jsonl').read_text().splitlines()]
            ready = 0.
            for row in journal:
                ready = max(ready, row['timestamp_ms'])+row['service_ms']
                self.assertEqual(ready, row['available_timestamp_ms'])
            self.assertGreaterEqual(journal[0]['available_timestamp_ms'], 199.)


if __name__ == '__main__':
    unittest.main(verbosity=2)
