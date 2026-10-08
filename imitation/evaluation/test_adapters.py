import unittest
import numpy as np
from .candidates import replacement_candidates
from .d1 import D1Tracker, model_packet
from sidecar_observer import SidecarObserver
from derived_d1 import PublicEvent
from own_cycle import OwnCycle


class Builder:
    def token_id(self, name, namespace):
        return 2 + ord(name)-ord('a')


class AdapterTests(unittest.TestCase):
    def test_matched_count_dedup_and_fewer_legal(self):
        mask = np.ones(2306, bool)
        rng = np.random.default_rng(8)
        for base, baseline in [([1, 2304, 2], [1, 2304, 2, 3, 4, 5]), ([2304], [2304]),
                               ([1,2304], [1,2304,2])]:
            got = replacement_candidates(base, baseline, [1,2,6,7,8,9,10,11], mask, rng)
            self.assertEqual(len(got), len(baseline))
            self.assertEqual(got[:len(base)], base)
            self.assertEqual(len(set(got)), len(got))
        mask[9] = False
        with self.assertRaises(ValueError):
            replacement_candidates([2304], [2304, 1], [9], mask, rng)

    def test_d1_bytes_against_independent_sidecar_layout_both_seats(self):
        # Includes abilities, Collector, queue refill and phase-boundary ages.
        for seat in (0,1):
            tracker = D1Tracker(Builder(), dict.fromkeys('abcdefgh', 1), seat, list('abcdefgh'))
            events = [dict(seat=0, **PublicEvent(90,'card','a',0.,4.5,12.5).__dict__),
                      dict(seat=1, **PublicEvent(90,'card','b',0.,13.5,21.5).__dict__),
                      dict(seat=1, **PublicEvent(95,'ability','b',1.).__dict__),
                      dict(seat=0, **PublicEvent(100,'collector','',1.).__dict__)]
            # Independent state consumption through T2's event method.
            sidecar = SidecarObserver(Builder())
            from derived_d1 import DerivedD1
            sidecar.trackers = [DerivedD1(dict.fromkeys('abcdefgh',1)) for _ in (0,1)]
            sidecar.learner=seat; sidecar.own=OwnCycle(list('abcdefgh'))
            for row in events:
                sidecar.event(row['seat'], PublicEvent(**{k:row[k] for k in PublicEvent.__dataclass_fields__}))
            for tick in (100, 110, 2401, 4801):
                row=tracker.update(tick, events)
                for t in sidecar.trackers: t.advance(tick)
                sidecar.own.advance(tick)
                ids, feat=sidecar.history(sidecar.trackers[1-seat],tick)
                np.testing.assert_array_equal(ids,row['opp_recent_play_ids'])
                self.assertEqual(feat.tobytes(),row['opp_recent_play_features'].tobytes())
                self.assertEqual(np.float32(sidecar.trackers[1-seat].elixir).tobytes(),row['opp_elixir'].tobytes())
                self.assertEqual(list(sidecar.own.queue),list(tracker.own.queue))


if __name__ == '__main__':
    unittest.main()
