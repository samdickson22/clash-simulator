"""Optimization contracts: exact arithmetic, cache invalidation, IPC events."""
from collections import deque
from dataclasses import replace
import math
import struct
import unittest
from clasher.live.tracker import FastHand, DerivedD1, TrackerV3, FrozenTrackerV3
from clasher.live.transport import ObservationWindow
from clasher.live.contracts import Frame, Observation

DECK = ['Knight', 'Archers', 'Giant', 'Musketeer', 'Fireball', 'Zap', 'Cannon', 'Skeletons']
COSTS = dict(zip(DECK, [3, 3, 5, 4, 4, 2, 3, 1]))


class ExactAccelerationTests(unittest.TestCase):
    def test_jump_matches_tick_loop_at_rate_and_refill_boundaries(self):
        for start in (0, 2390, 2399, 2400, 4790, 4799, 4800):
            for elapsed in (0, 1, 2, 9, 20, 50, 301):
                for refill in (0, 1, 50, 350, 500, 1000):
                    for elixir in (.00005, .00015, 6.12345, 9.9999, 10.):
                        a, b = DerivedD1(COSTS), FastHand(COSTS)
                        for d in (a, b):
                            d.tick, d.elixir, d.refill = start, elixir, refill
                            d.queue = deque(DECK)
                        a.advance(start+elapsed)
                        b.advance(start+elapsed)
                        self.assertEqual(a.derived(), b.derived())
                        self.assertEqual(struct.pack('!d', a.elixir), struct.pack('!d', b.elixir))

    def test_shift_accumulation_matches_full_lattice_bits(self):
        import numpy as np
        from clasher.live.tracker import add_shift, shift, N
        from clasher.live.lattice import mix
        rng = np.random.default_rng(1208)
        p = rng.random(N)
        p /= p.sum()
        components = [(s, .31) for s in (-100001, -100000, -50000, -1, 0, 1, 40000, 100000, 100001)]
        expected = np.zeros(N)
        sliced = np.zeros(N)
        for units, weight in components:
            expected += weight*shift(p, units)
            add_shift(sliced, p, units, weight)
        self.assertEqual(expected.tobytes(), sliced.tobytes())
        native = mix(p, components, .3, .7, .999, .002/N)
        if native is not None:
            expected = .999*(.3*p+.7*expected)+.002/N
            self.assertEqual(expected.tobytes(), native.tobytes())

    def test_mutated_pending_cue_invalidates_cycle_cache(self):
        import sys
        import numpy as np
        Evidence = sys.modules['clasher_live_tracker_v2'].Evidence
        trackers = [c({'decks': [{'cards': DECK}]}, COSTS, recall=.9, precision=.9)
                    for c in (FrozenTrackerV3, TrackerV3)]
        for q, card in ((.9, 'Knight'), (.99, 'Knight'), (.99, 'Archers')):
            for t in trackers:
                t.pending = [Evidence(10, ((card, 1.),), q, 'event')]
                t.advance(20)
            self.assertEqual(trackers[0].distribution(), trackers[1].distribution())
            self.assertEqual(trackers[0]._p.tobytes(), trackers[1]._p.tobytes())
            for seed in range(4):
                self.assertEqual(trackers[0].sample(np.random.default_rng(seed)),
                                 trackers[1].sample(np.random.default_rng(seed)))

    def test_latest_frame_retains_unacknowledged_events_without_pixels(self):
        window = ObservationWindow(capacity=4)
        frame = Frame('episode', 0, 0., 0., 0., object())
        a = Observation(frame, None, ({'event_id': 'a'},), 'regulation', 0.)
        b = replace(a, frame=replace(frame, sequence=1), events=({'event_id': 'b'},))
        c = replace(a, frame=replace(frame, sequence=2), events=())
        window.message(a, -1)  # This IPC value is dropped.
        message = window.message(b, -1)
        self.assertEqual(message.events, a.events+b.events)
        self.assertIsNone(message.frame.pixels)
        # Ack only frame 0; frame 1's candidate still needs delivery.
        self.assertEqual(window.message(c, 0).events, b.events)
        self.assertEqual(window.message(replace(c, frame=replace(frame, sequence=3)), 2).events, ())

    def test_event_overflow_fails_closed(self):
        window = ObservationWindow(capacity=1)
        observation = Observation(Frame('episode', 0, 0., 0., 0., None), None,
                                  ({'id': 1}, {'id': 2}), 'regulation', 0.)
        with self.assertRaises(RuntimeError):
            window.message(observation, -1)
