"""Regression checks for guarded public reconstruction and IPC/ABI adapters."""
from dataclasses import replace
import json
import multiprocessing as mp
from pathlib import Path
from queue import Queue
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from clasher.live.contracts import Frame
from clasher.live.perception_adapter import vectorized_runtime
from clasher.live.selection import body_threshold
from clasher.live.public_root import player_model
from clasher.live.tower_model import PublicTowerModel, SLOTS
from clasher.live.transport import FrameRing, drain_latest
from clasher.rl.live_inference_contract import PublicVisionFrame, VisionEntity


def public(entities=(), episode='synthetic'):
    return PublicVisionFrame(episode, '0', 0, 180., 1., 10., 1.,
                             ('Knight',)*4, (1.,)*4, 'Zap', 1., tuple(entities), ())


class TowerTests(unittest.TestCase):
    def test_empty_hud_sentinel_is_a_missing_slot_and_unknown_cards_fail_closed(self):
        raw = dict(hand=['empty', 'Knight', None, ''], cycle=['Zap'], elixir=5., refill=0)
        normalized = player_model(raw, {'Knight', 'Zap'})
        self.assertEqual(normalized['hand'], [None, 'Knight', None, None])
        self.assertEqual(raw['hand'][0], 'empty')
        with self.assertRaises(ValueError):
            player_model(dict(raw, hand=['unmodeled', None, None, None]), {'Knight', 'Zap'})

    def test_absence_is_unknown_and_raw_predictions_are_preserved(self):
        raw = public([VisionEntity('phantom', 'Tower', 'building', 0, 9., 3., .9, .12, .8),
                      VisionEntity('king', 'KingTower', 'building', 0, 9., 3., .5, .9, .8)])
        before = raw.entities
        modeled, diagnostic = PublicTowerModel().reconcile(raw)
        self.assertEqual(raw.entities, before)
        self.assertEqual(diagnostic['tower_identity_rejected'], 1)
        self.assertEqual(len(modeled.entities), 6)
        self.assertEqual(modeled.entities[0].hp_fraction, .9)
        self.assertEqual(modeled.entities[3].card, 'KingTower')
        self.assertEqual(modeled.entities[3].confidence, .01)

    def test_duplicate_identity_alias_and_public_zero_hp_persist(self):
        model = PublicTowerModel()
        king = VisionEntity('king', 'TowerKing', 'building', 1, 9., 29., .8, 0., .9)
        weak = replace(king, track_id='duplicate', confidence=.3, hp_fraction=1.)
        modeled, d = model.reconcile(public([king, weak]))
        self.assertEqual(d['tower_duplicates'], 1)
        self.assertEqual(modeled.entities[3].hp_fraction, 0.)
        missed, _ = model.reconcile(public())
        self.assertEqual(missed.entities[3].hp_fraction, 0.)
        reset, _ = model.reconcile(public(episode='next'))
        self.assertEqual(reset.entities[3].hp_fraction, 1.)

    def test_valid_six_towers_keep_positions_hp_and_owner(self):
        towers = [VisionEntity(str(i), c, 'building', s, x, y, .8, .5, .7)
                  for i, (s, c, x, y) in enumerate(SLOTS)]
        modeled, d = PublicTowerModel().reconcile(public(towers))
        self.assertEqual(modeled.entities, tuple(towers))
        self.assertEqual(d['tower_priors'], 0)


class AdapterTests(unittest.TestCase):
    def test_live_constructor_refuses_missing_selected_threshold_in_both_modes(self):
        from clasher.live.perception import V4Perception
        with tempfile.TemporaryDirectory() as directory:
            calibration = Path(directory)/'unselected.json'
            calibration.write_text(json.dumps({'spells': ['Zap'], 'thresholds': {'default': .1},
                                               'calibration': {}, 'body_threshold': .7}))
            for vectorized in (False, True):
                with self.subTest(vectorized=vectorized), \
                     patch('torch.load', return_value={}), \
                     patch('clasher.vision.l1_v4.PerceptionV4') as model, \
                     patch('clasher.vision.l1_v4.PixelPerception') as sensor, \
                     patch('clasher.live.perception_adapter.vectorized_runtime') as adapter:
                    with self.assertRaisesRegex(ValueError, 'separately authenticated final joint selection'):
                        V4Perception(dict(checkpoint='unused', calibration=str(calibration),
                                          body_threshold=.7, authenticated_selection={'authenticated': True},
                                          vectorized_decoder=vectorized))
                    model.assert_not_called()
                    sensor.assert_not_called()
                    adapter.assert_not_called()

    def test_threshold_rejects_missing_bool_nonfinite_and_outside_registered_grid(self):
        for value in (None, True, False, .55, .0, 1., float('nan'), float('inf'), '.7'):
            with self.assertRaises(ValueError):
                body_threshold(value)
        for value in (.1, .7, .9):
            self.assertEqual(body_threshold(value), value)

    def test_vectorized_adapter_is_isolated_and_nonclock_records_equal(self):
        import numpy as np
        import torch
        import clasher.vision.l1_v4 as reference
        torch.set_num_threads(1)
        torch.manual_seed(6127)
        original = reference.decode_bodies
        runtime, adapter = vectorized_runtime()
        self.assertIs(reference.decode_bodies, original)
        self.assertIsNot(runtime.decode_bodies, original)
        model = reference.PerceptionV4(2, 1)
        args = (model, ['Knight', 'Zap'], ['Knight'], ['Zap'], {'default': .1}, {})
        sensors = [r.PixelPerception(*args, body_threshold=.7) for r in (reference, runtime)]
        image = np.zeros((1140, 540, 3), np.uint8)
        def strip(row):
            return {key: ([{k: v for k, v in e.items() if k != 'available_timestamp_ms'} for e in value]
                          if key == 'event_candidates' else value)
                    for key, value in row.items() if key != 'available_timestamp_ms'}
        for stamp in (0., 50., 1250.):
            rows = [strip(s.step(image, 'synthetic', stamp)) for s in sensors]
            self.assertEqual(json.dumps(rows[0], sort_keys=True), json.dumps(rows[1], sort_keys=True))
            self.assertEqual(sensors[1].tracker.high, .7)
        self.assertIs(reference.decode_bodies, original)
        adapter.restore()

    def test_decoder_provenance_pins_executable_abi_and_existing_adapter_sources(self):
        from clasher.live.capture import sha256
        from clasher.live.loading import ROOT, V4
        from clasher.live.runtime import provenance
        from test_runtime import config
        import clasher.vision.l1_v4 as reference
        source = ROOT/'src/clasher/vision/l1_v4.py'
        before = sha256(source)
        original = reference.decode_bodies
        runtime, adapter = vectorized_runtime()
        try:
            self.assertEqual(Path(runtime.__file__).resolve(), source.resolve())
            with tempfile.TemporaryDirectory() as directory:
                cfg = config(directory)
                cfg['perception']['vectorized_decoder'] = True
                record = provenance(cfg)
            sources = [source, *(V4/'l1'/name for name in
                ('decoder_records_v4.py', 'vectorized_decoder_v4.py', 'vectorized_runtime_adapter_v4.py'))]
            hashes = {str(path): record['hashes'][str(path)] for path in sources}
            for path in sources:
                self.assertEqual(hashes[str(path)], sha256(path))
            self.assertEqual(hashes[str(source)], before)
            self.assertIs(reference.decode_bodies, original)
            print('DECODER_PROVENANCE '+json.dumps({'hashes': hashes, 'reference_untouched': True}))
        finally:
            adapter.restore()


class BlockingTests(unittest.TestCase):
    def test_queue_get_wakes_on_data_and_drains_latest(self):
        q = Queue()
        producer = threading.Thread(target=lambda: (time.sleep(.01), q.put(1), q.put(2)))
        producer.start()
        self.assertEqual(drain_latest(q, timeout=.2), 2)
        producer.join()
        self.assertIsNone(drain_latest(q, timeout=.001))

    def test_ring_notification_does_not_lose_preexisting_write(self):
        import numpy as np
        ring = FrameRing(mp.get_context('spawn'), capacity=2, shape=(2, 2, 3))
        frame = Frame('synthetic', 0, 0., 0., 0., np.zeros((2, 2, 3), np.uint8))
        ring.write(frame)
        start = time.monotonic()
        ring.wait(-1, .2)
        self.assertLess(time.monotonic()-start, .1)
        received, sequence, _ = ring.read(-1, 'synthetic')
        self.assertEqual(sequence, 0)
        producer = threading.Thread(target=lambda: (time.sleep(.01), ring.write(replace(frame, sequence=1))))
        producer.start()
        ring.wait(sequence, .2)
        self.assertEqual(ring.read(sequence, 'synthetic')[1], 1)
        producer.join()

    def test_blocking_process_loop_and_fault_shutdown(self):
        from test_runtime import config
        from clasher.live.runtime import run
        for fault in (None, 'P1', 'P3'):
            with tempfile.TemporaryDirectory() as directory:
                cfg = config(directory, frames=24)
                cfg['blocking_queues'] = True
                if fault:
                    cfg['fault'] = dict(stage=fault, after=5, seconds=.65)
                result = run(cfg, Path(directory)/'result')
                self.assertEqual(result['failures'], [])
                self.assertEqual(result['log_drops'], 0)


if __name__ == '__main__':
    unittest.main()
