"""CPU-only process, boundary and fault tests; no emulator/network access."""
from dataclasses import replace
import gzip
import json
import multiprocessing as mp
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from clasher.live.actuation import Actuation, MockInput
from clasher.live.belief import Belief, OwnLedger
from clasher.live.capture import admit_replay
from clasher.live.contracts import Command, Frame, Snapshot
from clasher.live.decision import Triggers, RustPlanner
from clasher.live.loading import actuator_module, tracker_class
from clasher.live.runtime import run, summarize, configure_timing
from clasher.live.timing import backend_timing
from clasher.live.transport import FrameRing, should_drop

DECK = ['Knight', 'Archers', 'Giant', 'Musketeer', 'Fireball', 'Zap', 'Cannon', 'Skeletons']
COSTS = dict(zip(DECK, [3, 3, 5, 4, 4, 2, 3, 1]))


def config(directory, frames=42):
    prior = Path(directory)/'prior.json'
    prior.write_text(json.dumps({'decks': [{'cards': DECK}]}))
    return dict(source={'kind': 'synthetic', 'episode': 'test'}, frames=frames, fps=20,
                perception={'kind': 'synthetic', 'deck': DECK},
                belief={'own_deck': DECK, 'prior': str(prior), 'costs': COSTS},
                planner={'kind': 'synthetic'}, actuator={'kind': 'mock', 'tap_seconds': .001},
                startup_timeout=60, max_seconds=30)


class CaptureTests(unittest.TestCase):
    def test_ring_overflow_and_copy(self):
        import numpy as np
        ring = FrameRing(mp.get_context('spawn'), capacity=2, shape=(2, 2, 3))
        for seq in range(4):
            ring.write(Frame('a', seq, seq, seq+.01, seq*50, np.full((2, 2, 3), seq, np.uint8)))
        frame, seq, lost = ring.read(-1, 'a')
        self.assertEqual((seq, lost), (2, 2))
        ring.write(Frame('a', 4, 4, 4, 200, np.zeros((2, 2, 3), np.uint8)))
        self.assertTrue((frame.pixels == 2).all())

    def test_heldout_rejected_before_media_open(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            (path/'receipt.json').write_text(json.dumps({'seed': 1, 'split': 'heldout'}))
            split = path/'split.json'
            split.write_text(json.dumps({'matches': [{'seed': 1, 'split': 'heldout'}]}))
            with self.assertRaisesRegex(ValueError, 'train membership'):
                admit_replay(path, split)

    def test_backpressure_preserves_irregular_time(self):
        self.assertFalse(should_drop(2, .16))
        self.assertTrue(should_drop(3, .16))
        self.assertTrue(should_drop(2, .41))


class BeliefTests(unittest.TestCase):
    def test_frozen_tracker_import_has_no_bootstrap_side_effects(self):
        import os
        import sys
        before = os.environ.get('CLASHER_ROOT')
        paths = sys.path[:]
        cls = tracker_class()
        self.assertEqual(cls.__name__, 'TrackerV3')
        self.assertEqual(os.environ.get('CLASHER_ROOT'), before)
        self.assertEqual(sys.path, paths)

    def test_ledger_spends_once_and_ignores_old_feedback(self):
        api = actuator_module()
        ledger = OwnLedger(DECK)
        actor = Actuation(MockInput(0))
        hud = api.Hud(10., tuple(DECK[:4]), 8., DECK[4])
        command = Command(1, 'a', 1, 10., 10., 0, 'Knight', 3., (3., 20.), 10.4)
        feedback, _ = actor.submit(command, hud, 10.01)
        self.assertTrue(ledger.feedback(feedback))
        self.assertFalse(ledger.feedback(feedback))
        public = type('Public', (), {'own_hand': hud.hand, 'own_next_card': hud.next_card, 'own_elixir': 8.})()
        state = ledger.state(public, 10., 1)
        self.assertEqual(state['elixir'], 5.)
        self.assertEqual(state['hand'][0], DECK[4])
        self.assertFalse(state['cycle_exact'])


class DecisionTests(unittest.TestCase):
    def test_backend_delay_and_verifier_share_selected_profile(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'timing.json'
            path.write_text(json.dumps({'backends': {'test': dict(
                p50_ticks=7.6, p50_ms=390, p99_ms=480)}}))
            cfg = configure_timing(dict(planner={'kind': 'rust'}, actuator={'kind': 'mock'},
                                        backend='test', timing_path=str(path)))
            self.assertEqual(backend_timing(cfg['planner'])[3], 8)
            actor = Actuation(MockInput(0), 'test', path)
            self.assertEqual(actor.delay_ticks, 8)
            self.assertAlmostEqual(actor.machine.verify_seconds, 1.08)
            cfg['actuator']['backend'] = 'different'
            with self.assertRaisesRegex(ValueError, 'disagree'):
                configure_timing(cfg)
        self.assertEqual(backend_timing({})[3], 23)
        self.assertEqual(backend_timing({'backend': 'offline-renderer-adb-spawn'})[3], 24)

    def test_pending_p4_reservation_blocks_s6_without_second_spend(self):
        from types import SimpleNamespace
        actor = Actuation(MockInput(0))
        hud = actuator_module().Hud(10., tuple(DECK[:4]), 8., DECK[4])
        command = Command(17, 'a', 1, 10., 10., 0, 'Knight', 3., (3., 20.), 10.4)
        feedback, _ = actor.submit(command, hud, 10.01)
        ledger = OwnLedger(DECK)
        ledger.feedback(feedback)
        planner = object.__new__(RustPlanner)
        planner.backend, planner.delay_ticks, planner.delay_aware = actor.backend, actor.delay_ticks, True
        public = SimpleNamespace(own_hand=hud.hand, own_next_card=hud.next_card, own_elixir=8.)
        for tick in (1, 21, 101):
            own = ledger.state(public, 10., tick)
            snapshot = Snapshot('a', 1, 10., 10., 10., tick, None, own, (), {},
                                ledger.revision, ledger.pending, 0, 0)
            action, diagnostic = planner.decide(snapshot, time.monotonic()+.2)
            self.assertEqual(action, 2304)
            self.assertEqual(diagnostic['pending_command_id'], 17)
            self.assertEqual(own['elixir'], 5.)
            self.assertEqual(own['hand'][0], DECK[4])
        # A retry retains the same identity, cost and slot, not another debit.
        retry_at = 10.01+actor.machine.verify_seconds+.15
        retry, request = actor.observe(replace(hud, produced_at=retry_at), retry_at)
        self.assertEqual(request['attempt'], 2)
        ledger.feedback(retry)
        self.assertEqual(ledger.pending['command_id'], 17)
        self.assertEqual(ledger.state(public, retry_at, 101)['elixir'], 5.)

    def test_s6_deadline_discards_incomplete_candidate_and_restores_native(self):
        from types import SimpleNamespace
        planner = object.__new__(RustPlanner)
        planner.delay_aware, planner.delay_ticks = True, 23
        planner.resources = SimpleNamespace(costs={})
        native = SimpleNamespace(evaluate=lambda: 1.)
        core = SimpleNamespace(native=native)
        def score(root, seat, candidates):
            # A deadline before the first style must never publish a score.
            value = core.native.evaluate()
            core.last = {'scores': [value]}
        core.score_candidates = score
        values = planner.score(core, None, SimpleNamespace(seat=1), [0, 2304], time.monotonic()-1)
        self.assertEqual(values, [None, None])
        self.assertIs(core.native, native)

    def test_cadence_and_rate_limited_event_and_verification(self):
        s = Snapshot('a', 1, 0, 0, 0, 0, None, {'elixir': 4}, (), {}, 0, None, 0, 0)
        t = Triggers()
        self.assertEqual(t.reason(s, 1.), 'elixir')
        event = replace(s, event_serial=1)
        self.assertIsNone(t.reason(event, 1.1))
        self.assertEqual(t.reason(event, 1.21), 'event')
        self.assertEqual(t.reason(replace(event, verification_serial=1), 1.42), 'verification')
        self.assertEqual(t.reason(replace(event, tick=10, verification_serial=1), 1.63), 'cadence')
        self.assertIsNone(t.reason(replace(s, pending={'card': 'Knight'}), 10.))


class ActuationTests(unittest.TestCase):
    def setUp(self):
        self.api = actuator_module()
        self.actor = Actuation(MockInput(0))
        self.hud = self.api.Hud(10., tuple(DECK[:4]), 8., DECK[4])
        self.command = Command(1, 'a', 1, 10., 10., 0, 'Knight', 3., (3., 20.), 10.4)

    def test_remap_and_delayed_acceptance(self):
        remapped = replace(self.hud, hand=tuple(reversed(self.hud.hand)))
        feedback, request = self.actor.submit(self.command, remapped, 10.01)
        self.assertEqual(request['slot'], 3)
        self.actor.execute(request)
        _, early = self.actor.observe(replace(remapped, produced_at=10.7), 10.71)
        self.assertEqual(early['state'], 'pending')
        after = replace(remapped, produced_at=11.15, hand=(*remapped.hand[:3], DECK[4]), elixir=5.)
        feedback, result = self.actor.observe(after, 11.16)
        self.assertEqual(result['state'], 'accepted')
        self.assertIsNone(feedback.pending)
        self.assertEqual(len(self.actor.channel.taps), 1)

    def test_no_stale_retap_after_stall_or_duplicate(self):
        feedback, request = self.actor.submit(self.command, self.hud, 10.01)
        self.actor.execute(request)
        self.assertAlmostEqual(self.actor.machine.verify_seconds, 1.7873178738285787)
        duplicate, result = self.actor.submit(self.command, self.hud, 10.02)
        self.assertIsNone(duplicate)
        self.assertEqual(result['reason'], 'duplicate command')
        # A stall beyond rollback cannot trigger the optional retry.
        feedback, result = self.actor.observe(self.hud, 12.2)
        self.assertEqual(result['state'], 'failed')
        old = replace(self.command, command_id=2, revision=feedback.revision, expires_at=20.)
        _, result = self.actor.submit(old, replace(self.hud, produced_at=12.21), 12.22)
        self.assertEqual(result['reason'], 'pre-terminal decision')
        self.assertEqual(len(self.actor.channel.taps), 1)

    def test_ambiguous_transport_keeps_reservation(self):
        _, request = self.actor.submit(self.command, self.hud, 10.01)
        with patch.object(self.actor.channel, 'play', side_effect=TimeoutError('injected')):
            result = self.actor.execute(request)
        self.assertTrue(result['ambiguous'])
        self.assertIsNotNone(self.actor.machine.pending)

    def test_expired_and_revision_rejected(self):
        _, result = self.actor.submit(self.command, self.hud, 11.)
        self.assertEqual(result['reason'], 'expired command')
        command = replace(self.command, command_id=2, expires_at=20.)
        _, result = self.actor.submit(command, replace(self.hud, produced_at=11.), 11.01)
        self.assertEqual(result['reason'], 'old ledger revision')


class SupervisorTests(unittest.TestCase):
    def test_empty_latency_is_not_pass(self):
        c = {'source': {'kind': 'replay'}, 'perception': {'kind': 'v3'},
             'planner': {'kind': 'rust'}, 'actuator': {'kind': 'mock'}}
        self.assertFalse(summarize([], c, [], 0)['end_to_end_budget_pass'])

    def test_pipeline_and_stage_stall(self):
        with tempfile.TemporaryDirectory() as folder:
            c = config(folder)
            c['fault'] = {'stage': 'P2', 'after': 10, 'seconds': .65}
            result = run(c, Path(folder)/'run')
            self.assertEqual(result['failures'], [])
            self.assertGreater(result['processed'], 15)
            self.assertGreater(result['dropped_frames'], 0)
            self.assertEqual(result['history_resets'], 0)
            with gzip.open(Path(folder)/'run/latency.jsonl.gz', 'rt') as stream:
                rows = [json.loads(line) for line in stream]
            attempts = [(r['command_id'], r['attempt']) for r in rows if r['metric'] == 'taps']
            self.assertEqual(len(attempts), len(set(attempts)))
            self.assertTrue(attempts)

    def test_search_stall_discards_expired_command(self):
        with tempfile.TemporaryDirectory() as folder:
            c = config(folder, frames=12)
            c['fault'] = {'stage': 'P3', 'after': 0, 'seconds': .65}
            result = run(c, Path(folder)/'run')
            self.assertEqual(result['failures'], [])
            self.assertGreaterEqual(result['counts'].get('expired_decision', 0), 1)
            self.assertEqual(result['counts'].get('taps', 0), 0)




class FairBoundaryTests(unittest.TestCase):
    def test_belief_denied_reads_and_backdated_event(self):
        import builtins
        import io
        import socket
        import numpy as np
        from clasher.live.perception import SyntheticPerception
        with tempfile.TemporaryDirectory() as folder:
            c = config(folder)
            belief = Belief(c['belief'])
            sensor = SyntheticPerception(c['perception'])
            frame = Frame('test', 2, 1., 1., 100., np.zeros((1140, 540, 3), np.uint8))
            observation = sensor.step(frame)
            event = dict(side=0, card='Knight', execution_timestamp_ms=50.,
                         x_tiles=3., y_tiles=5., existence_q=.9, card_distribution=(('Knight', 1.),))
            observation = replace(observation, events=(event,))
            with patch.object(builtins, 'open', side_effect=AssertionError('file read')),\
                 patch.object(io, 'open', side_effect=AssertionError('path read')),\
                 patch.object(socket, 'socket', side_effect=AssertionError('socket')):
                snapshot = belief.update(observation)
                same = belief.update(replace(observation, frame=replace(frame, sequence=3, timestamp_ms=150.),
                                             public=replace(observation.public, timestamp_ms=150.)))
            self.assertEqual(snapshot.event_serial, 1)
            self.assertEqual(same.event_serial, 1)
            self.assertEqual(len(snapshot.roots), 4)
            self.assertEqual(belief.tracker.n_events, 1)

    def test_sanitizer_ignores_opponent_hud(self):
        import numpy as np
        from clasher.live.capture import sanitize
        a = np.zeros((2280, 1080, 3), np.uint8)
        b = a.copy()
        b[:280] = np.random.default_rng(123).integers(0, 256, b[:280].shape, dtype=np.uint8)
        np.testing.assert_array_equal(sanitize(a), sanitize(b))

    def test_replay_projects_only_public_fields(self):
        from clasher.live.capture import sha256
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            decks = [DECK[::-1], DECK]
            split = path/'split.json'
            split.write_text(json.dumps({'matches': [{'seed': 1, 'split': 'train', 'decks': decks}]}))
            (path/'video.mp4').write_bytes(b'test-media-not-decoded-in-admission')
            (path/'frames.jsonl').write_text(json.dumps(dict(seq=0, produced_mono=1., received_at=1.01,
                                                           media_pts=0., tick_lo=999, opponent_elixir=10.))+'\n')
            receipt = dict(seed=1, split='train', decks=decks, episode='train-example', render_backend='host',
                           files={n: sha256(path/n) for n in ('video.mp4', 'frames.jsonl')})
            (path/'receipt.json').write_text(json.dumps(receipt))
            source = admit_replay(path, split)
            self.assertEqual(source['own_deck'], DECK)
            self.assertNotIn('decks', source)
            self.assertEqual(set(source['rows'][0]), {'seq', 'produced_mono', 'received_at', 'media_pts'})



class PerceptionTests(unittest.TestCase):
    def test_v3_fallback_retains_tracker_across_long_gap(self):
        import numpy as np
        from types import SimpleNamespace
        from clasher.live.perception import SyntheticPerception, V3Fallback
        base = SyntheticPerception({'deck': DECK})
        sensor = V3Fallback.__new__(V3Fallback)
        sensor.episode, sensor.net, sensor.thresholds = None, None, {'default': .7}
        sensor.body = SimpleNamespace(step=lambda image, episode, sequence, timestamp:
                      base.step(Frame(episode, int(sequence), 1., 1., timestamp, image)).public)
        pixels = np.zeros((1140, 540, 3), np.uint8)
        first = sensor.step(Frame('gap', 0, 1., 1., 0., pixels))
        tracker = sensor.tracker
        second = sensor.step(Frame('gap', 1, 2.2, 2.2, 1200., pixels))
        self.assertIs(sensor.tracker, tracker)
        self.assertEqual(second.public.timestamp_ms-first.public.timestamp_ms, 1200)

    def test_v4_adapter_canonical_unknowns_and_completion_timestamp(self):
        import numpy as np
        from unittest.mock import MagicMock
        from clasher.live.perception import V4Perception
        from clasher.rl.live_inference_contract import validate_public_vision_frame
        row = dict(clock_seconds=120., own_elixir=6., own_hand=[None, *DECK[1:4]], next_card=None,
                   hud_card_probabilities=[[.4, .6]]*5, phase=1, tracks=[],
                   event_candidates=[dict(card='Knight', side=0, x_tiles=2., y_tiles=5.,
                        execution_timestamp_ms=100., execution_sigma_ms=20., existence_q=.9,
                        card_distribution=(('Knight', 1.),))])
        with tempfile.TemporaryDirectory() as folder:
            calibration = Path(folder)/'calibration.json'
            calibration.write_text(json.dumps(dict(spells=[], thresholds={'default': .5}, calibration={})))
            model = MagicMock()
            with patch('torch.load', return_value={'cards': DECK, 'bodies': ['Knight'], 'model': {}}), \
                 patch('clasher.vision.l1_v4.PerceptionV4', return_value=model), \
                 patch('clasher.vision.l1_v4.PixelPerception') as abi:
                abi.return_value.step.return_value = row
                sensor = V4Perception(dict(checkpoint='unused', calibration=str(calibration), device='cpu'))
                now = time.monotonic()
                observed = sensor.step(Frame('v4', 1, now-.02, now-.01, 134.7,
                                             np.zeros((1140, 540, 3), np.uint8)))
            validate_public_vision_frame(observed.public)
            self.assertEqual(observed.public.timestamp_ms, 135)
            self.assertEqual(observed.public.own_hand[0], '')
            self.assertEqual(observed.public.own_next_card_confidence, 0.)
            self.assertGreater(observed.events[0]['available_timestamp_ms'], 154.)

    def test_downscaled_allowlist_matches_original_sanitizer(self):
        import cv2
        import numpy as np
        from clasher.live.capture import sanitize
        from clasher.vision.l1 import public_pixels
        raw = np.random.default_rng(123).integers(0, 256, (1140, 540, 3), np.uint8)
        original = public_pixels(cv2.resize(raw, (1080, 2280), interpolation=cv2.INTER_NEAREST))
        np.testing.assert_array_equal(sanitize(raw), original)




class GrpcCaptureTests(unittest.TestCase):
    def test_rpc_sampling_timestamp_anchor_and_close_without_network(self):
        import sys
        import threading
        from types import SimpleNamespace
        import numpy as np
        from clasher.live.capture import grpc_frames
        wall, mono = 1700000000., 100.
        position = [0]
        clock_calls = [0]
        def clock():
            clock_calls[0] += 1
            return mono+position[0]/60+(0. if clock_calls[0] == 1 else .01)
        image = bytes(2280*1080*3)
        class ImageFormat:
            RGB888 = 1
            SerializeToString = staticmethod(lambda value: b'')
            def __init__(self, **kwargs):
                pass
        class Rpc:
            cancelled = False
            def __iter__(self):
                for i in range(60):
                    position[0] = i
                    yield SimpleNamespace(timestampUs=(wall+i/60)*1e6, image=image,
                                          format=SimpleNamespace(width=1080, height=2280))
            def cancel(self):
                self.cancelled = True
        rpc = Rpc()
        channel = SimpleNamespace(unary_stream=lambda *a, **k: lambda *a, **k: rpc, close=lambda: None)
        grpc = SimpleNamespace(insecure_channel=lambda *a, **k: channel)
        pb = SimpleNamespace(ImageFormat=ImageFormat, Image=SimpleNamespace(FromString=lambda value: None))
        with tempfile.TemporaryDirectory() as folder:
            discovery = Path(folder)/'discovery.ini'
            discovery.write_text('grpc.port=12345\ngrpc.token=test-only\n')
            with patch.dict(sys.modules, {'grpc': grpc}), \
                 patch('clasher.live.loading.module', return_value=pb), \
                 patch('clasher.live.capture.time.time', return_value=wall), \
                 patch('clasher.live.capture.time.monotonic', side_effect=clock):
                frames = list(grpc_frames(dict(port=12345, proto_dir=folder, discovery=str(discovery),
                                               episode='rpc-unit'), threading.Event(), lambda *a, **k: None))
        self.assertEqual([frame.sequence for frame in frames], list(range(len(frames))))
        self.assertGreaterEqual(len(frames), 19)
        self.assertLessEqual(len(frames), 21)
        self.assertAlmostEqual(frames[0].produced_at, mono)
        self.assertTrue(all(a.produced_at < b.produced_at for a, b in zip(frames, frames[1:])))
        self.assertTrue(rpc.cancelled)


if __name__ == '__main__':
    unittest.main()
