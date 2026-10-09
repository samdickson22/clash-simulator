"""Crown attribution and public end-screen routing across episode boundaries."""
from dataclasses import asdict
import unittest
import numpy as np
from clasher.live.crown_counter import CrownObservation,CrownCounterReader,color_feature
from clasher.live.result_screen import ResultScreenDetector,ResultScreenObservation,text_feature
from clasher.live.tower_channel import TowerChannel,TowerObservation
from clasher.live.perception_adapter import PublicTowerAdapter
from clasher.live.public_root import apply_match_result,PublicMatchResult
from clasher.live.tower_model import tower_packet_builder
from clasher.rl.live_inference_contract import parse_public_vision_frame
from test_tower_channel import artifact,canvas,public


def score_data(image=None,label='ended'):
    data=dict(schema='clasher.public-score-templates.v1',crowns=[[],[]],result=dict(box=[70,490,470,550],size=[100,20],templates={},distance=.01,margin=.01,gap_ms=600,confirmation_frames=2,score_max_age_ms=500))
    if image is not None:
        data['result']['templates'][label]=[text_feature(image,data['result']['box'],(100,20)).tolist()]
    return data


def result_image():
    image=np.zeros((1140,540,3),np.uint8)
    # Distinctive interior pattern exercises the actual foreground extraction.
    image[499:530,91:145]=255
    image[504:537,192:210]=255
    image[491:544,295:339]=255
    return image


class CrownTests(unittest.TestCase):
    def crowns(self,time,counts=(None,1),ep='one'):
        return CrownObservation(ep,time,counts,.98)

    def test_increment_uniquely_attributes_missing_slot_without_waiting_for_rubble(self):
        c=TowerChannel(artifact());c.step(canvas(c,[180]*6),'one',0)
        missing=canvas(c,[180,0,180,180,180,180])
        self.assertEqual(c.step(missing,'one',50,crowns=self.crowns(50))[1].state,'unknown')
        obs=c.step(missing,'one',100,crowns=self.crowns(100))
        self.assertEqual(obs[1].state,'destroyed')
        self.assertEqual(obs[1].destruction_evidence,'crown_increment_slot')
        self.assertEqual(obs[2].state,'alive')
        row=asdict(public(obs,time=100));outer={k:row.pop(k) for k in ('episode_id','frame_id','timestamp_ms')}
        self.assertEqual(parse_public_vision_frame(dict(schema_version=1,public=row,**outer)).tower_observations,obs)

    def test_absence_score_alone_and_ambiguous_slots_never_confirm(self):
        for values,counts in (([180,0,180,180,180,180],None),([180]*6,(None,1)),([180,0,0,180,180,180],(None,1))):
            c=TowerChannel(artifact());c.step(canvas(c,[180]*6),'one',0)
            for time in (50,100,150):
                obs=c.step(canvas(c,values),'one',time,crowns=self.crowns(time,counts) if counts else None)
                self.assertFalse(any(o.state=='destroyed' for o in obs))

    def test_capture_start_absence_jumps_stale_witness_and_episode_reset(self):
        c=TowerChannel(artifact());missing=canvas(c,[180,0,180,180,180,180])
        c.step(missing,'one',0)
        for time in (50,100):
            self.assertEqual(c.step(missing,'one',time,crowns=self.crowns(time))[1].state,'unknown')
        c=TowerChannel(artifact());c.step(canvas(c,[180]*6),'one',0)
        for time in (50,100):
            self.assertEqual(c.step(missing,'one',time,crowns=self.crowns(time,(None,2)))[1].state,'unknown')
        c=TowerChannel(artifact());c.step(canvas(c,[180]*6),'one',0)
        for time in (5000,5050):
            self.assertEqual(c.step(missing,'one',time,crowns=self.crowns(time))[1].state,'unknown')
        self.assertEqual(c.step(missing,'next',0)[1].state,'unknown')
        with self.assertRaises(ValueError):c.step(missing,'next',50,crowns=self.crowns(50))

    def test_late_score_for_previously_confirmed_rubble_does_not_destroy_peer(self):
        c=TowerChannel(artifact());c.step(canvas(c,[180]*6),'one',0)
        rubble=canvas(c,[180,60,180,180,180,180])
        for time in (50,100,150):c.step(rubble,'one',time)
        self.assertIn(1,c.dead)
        hidden=canvas(c,[180,60,0,180,180,180])
        c.step(hidden,'one',200,crowns=self.crowns(200))
        self.assertEqual(c.step(hidden,'one',250,crowns=self.crowns(250))[2].state,'unknown')

    def test_hud_reader_abstains_and_prefers_earlier_banner_score(self):
        image=np.zeros((1140,540,3),np.uint8);image[480:500,480:500]=100;image[680:700,180:200]=200
        data=score_data()
        for box,count in (([480,480,500,500],0),([180,680,200,700],1)):
            data['crowns'][1].append(dict(box=box,size=[4,4],templates={str(count):[color_feature(image,box,(4,4)).tolist()]},distance=.01,margin=.01))
        reader=CrownCounterReader(data)
        self.assertEqual(reader.read(image,'one',0).crowns,(None,1))
        self.assertIsNone(reader.read(np.zeros_like(image),'one',50))
        with self.assertRaises(ValueError):CrownObservation('one',0,(None,None),.9)
        with self.assertRaises(ValueError):CrownObservation('one',0,(True,1),.9)
        with self.assertRaises(ValueError):TowerObservation('opp_king','destroyed',confidence=.9,last_observed_ms=0,destruction_evidence='crown_increment_slot')


class ResultTests(unittest.TestCase):
    def test_result_text_debounces_unknown_crowns_and_routes_terminal(self):
        image=result_image();data=score_data(image)
        adapter=PublicTowerAdapter(artifact(),score_artifact=data)
        self.assertFalse(any(o.match_ended for o in adapter.observe(public(time=0),image).tower_observations))
        ended=adapter.observe(public(time=50),image)
        self.assertTrue(ended.tower_observations[0].match_ended)
        self.assertTrue(all(o.state=='unknown' for o in ended.tower_observations))
        self.assertIsNone(adapter.last_result.outcome)
        self.assertEqual(adapter.last_result.crowns,(None,None))
        class Base:
            def __init__(self,builder):self.hp,self.positions,self.last_time={},{},None
            def build(self,frame,tick,seat=1,terminal=False):return frame,dict(terminal=terminal)
        builder=tower_packet_builder(Base,only_channel=True)(None)
        self.assertTrue(builder.build(ended,1)[1]['terminal'])
        self.assertTrue(builder.build(public(time=100),2)[1]['terminal'])
        self.assertFalse(builder.build(public(episode='next'),0)[1]['terminal'])

    def test_outcome_classes_partial_scores_and_equal_score_not_draw(self):
        image=result_image()
        for outcome in ('win','loss','draw','ended'):
            d=ResultScreenDetector(score_data(image,outcome));counts=CrownObservation('one',0,(1,1),.9)
            d.step(image,'one',0,counts)
            result=d.step(image,'one',50)
            self.assertEqual(result.outcome,None if outcome=='ended' else outcome)
            self.assertEqual(result.crowns,(1,1))
        result=ResultScreenObservation('one',50,'win',(None,3),.98)
        routed=apply_match_result(public(time=50),result.as_match_result())
        self.assertEqual(routed.tower_observations[0].state,'destroyed')
        self.assertEqual(routed.tower_observations[3].state,'unknown')
        with self.assertRaises(ValueError):PublicMatchResult('one',50,(0,1),.9,'loss')

    def test_absence_gaps_bad_times_and_episode_reset(self):
        image=result_image();d=ResultScreenDetector(score_data(image))
        self.assertIsNone(d.step(np.zeros_like(image),'one',0))
        self.assertIsNone(d.step(image,'one',50))
        self.assertIsNone(d.step(image,'one',1000))
        self.assertIsNotNone(d.step(image,'one',1050))
        with self.assertRaises(ValueError):d.step(image,'one',1050)
        self.assertIsNone(d.step(np.zeros_like(image),'next',0))

if __name__=='__main__':unittest.main()
