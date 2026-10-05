"""Safety and data-boundary checks before confirmatory games."""
import json,unittest,sys
from unittest.mock import patch
from dataclasses import replace
from bootstrap import setup,HERE
r,_=setup('c56')
import numpy as np,cv2
from pixel_player import PixelPlayer,PacketBuilder,model_hypothesis
from clasher.vision.l1 import public_pixels
from clasher.rl.live_inference_contract import PublicVisionFrame,VisionEntity,PublicPlayEvent
row=json.loads((HERE/'pixel-diagnostics.json').read_text())[0]
from clasher.rl.live_inference_contract import parse_public_vision_frame
v=dict(row['frame']);identity={k:v.pop(k) for k in ['episode_id','frame_id','timestamp_ms']}
frame=parse_public_vision_frame(dict(schema_version=1,**identity,public=v))
class Boundaries(unittest.TestCase):
    def test_opponent_hud_cannot_change_pixels(self):
        a=cv2.imread(str(HERE/'preflight.png'));b=a.copy();b[:280]=np.random.default_rng(123).integers(0,256,b[:280].shape,dtype=np.uint8)
        np.testing.assert_array_equal(public_pixels(a),public_pixels(b))
    def test_model_cannot_relabel_original_confidence(self):
        packet,_=PacketBuilder(r.builder).build(frame,220)
        measured=packet.entity_feature_confidence.copy();hand=packet.hand_id_confidence.copy()
        model=model_hypothesis(packet)
        np.testing.assert_array_equal(measured,packet.entity_feature_confidence);np.testing.assert_array_equal(hand,packet.hand_id_confidence)
        self.assertTrue((packet.entity_id_confidence[packet.observation.entity_mask]<1).any())
        self.assertIsNot(model.entity_feature_confidence,packet.entity_feature_confidence)
        model.validate()
    def test_actor_has_no_io_or_privileged_state_read(self):
        # Load resources/weights before denial; forbid every file/socket read in decisions.
        outputs=[]
        for _ in range(2):
            player=PixelPlayer(r,'c56',12345)
            with patch('builtins.open',side_effect=AssertionError('actor file read')),patch('socket.socket',side_effect=AssertionError('actor socket')):
                tick=player.ingest(frame,row['cues']);action,diag=player.decide(frame,tick)
            self.assertLess(action,2306);self.assertEqual(diag['deadline']['completed'],diag['deadline']['total']);outputs.append(action)
        self.assertEqual(outputs[0],outputs[1])
    def test_registration_balanced_and_disjoint(self):
        s=json.loads((HERE/'schedule.json').read_text())['matches'];self.assertEqual(len(s),48);self.assertEqual(len({x['seed'] for x in s}),48)
        for key in ['family','style']:
            self.assertEqual(sorted([sum(x[key]==v for x in s) for v in {x[key] for x in s}]),[16,16,16])
        self.assertTrue(json.loads((HERE/'seed-audit.json').read_text())['passed'])
if __name__=='__main__':unittest.main()
