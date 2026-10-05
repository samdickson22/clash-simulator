"""Guard regressions: no offline-device input and no invented game calibration."""
import json
import unittest
from unittest.mock import patch
import numpy as np
import official_loop as loop

class Boundaries(unittest.TestCase):
    def test_offline_process_rejected_before_adb_dispatch(self):
        with patch.object(loop.subprocess,'check_output',return_value='emulator -avd clasher_reference_api35 -port 5590 '), patch.object(loop.subprocess,'run') as run:
            with self.assertRaises(RuntimeError):loop.adb('shell','input','tap','10','10')
            run.assert_not_called()

    def test_unvalidated_calibration_cannot_play(self):
        calibration=json.loads((loop.ROOT/'calibration.json').read_text())
        with patch.object(loop,'adb') as adb:
            with self.assertRaises(ValueError):loop.Input().play(0,100,500,calibration)
            with self.assertRaises(ValueError):loop.tile_to_pixel(4,20,calibration)
            adb.assert_not_called()

    def test_unvalidated_states_are_unknown_for_any_pixels(self):
        reader=loop.ScreenStates()
        for image in [np.zeros((640,360,3),np.uint8),np.full((640,360,3),255,np.uint8)]:
            self.assertEqual(reader.recognize(image)['state'],'unknown')

    def test_out_of_screen_tap_rejected_before_adb(self):
        with patch.object(loop,'adb') as adb:
            with self.assertRaises(ValueError):loop.Input().tap(720,10)
            with self.assertRaises(ValueError):loop.Input().drag(20,20,20,1280)
            adb.assert_not_called()

if __name__=='__main__':unittest.main()
