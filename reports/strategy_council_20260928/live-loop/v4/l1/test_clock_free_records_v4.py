import unittest
from copy import deepcopy
from clock_free_records_v4 import checked_records, body_frames, event_predictions


def records():
    peak=dict(card='Knight',side=0,x_tiles=1.,y_tiles=2.,execution_timestamp_ms=0.,
              execution_sigma_ms=10.,existence_q=.4,card_distribution=[['Knight',1.]],
              cast_origin_probability=None)
    return [dict(schema='clasher.v4.decoder-frame.v1',episode_id='v',source_seq=i,
                 timestamp_ms=t,bodies=[],event_peaks=[deepcopy(peak)],causal_own_hud_cards=[],hud={})
            for i,t in enumerate((0.,100.))]


class ClockFreeTests(unittest.TestCase):
    def test_no_clock_or_future_frame_accepted(self):
        for field in ('service_ms','available_timestamp_ms','clock'):
            r=records();r[0][field]=123
            with self.assertRaises(ValueError):checked_records(r,episode='v',expected_times=[0.,100.])
        r=records();r[1]['timestamp_ms']=99
        with self.assertRaises(ValueError):checked_records(r,episode='v',expected_times=[0.,100.])

    def test_full_population_and_identity(self):
        for r in (records()[:1], records()[::-1]):
            with self.assertRaises(ValueError):checked_records(r,episode='v',expected_times=[0.,100.])

    def test_body_view_needs_no_events_or_clocks(self):
        r=records()
        for x in r:
            del x['event_peaks'];del x['causal_own_hud_cards'];del x['hud']
        self.assertEqual(body_frames(r,episode='v',expected_times=[0.,100.],body_threshold=.1),[[],[]])

    def test_independent_threshold_nms_and_no_synthetic_clock_escapes(self):
        low=event_predictions(records(),episode='v',expected_times=[0.,100.],spells=[],threshold=.1)
        high=event_predictions(records(),episode='v',expected_times=[0.,100.],spells=[],threshold=.5)
        self.assertEqual(len(low),1);self.assertEqual(high,[])
        self.assertEqual(low[0]['production_timestamp_ms'],0.)
        self.assertNotIn('available_timestamp_ms',low[0])
        self.assertEqual(low[0]['execution_timestamp_ms'],0.)


if __name__=='__main__':unittest.main()
