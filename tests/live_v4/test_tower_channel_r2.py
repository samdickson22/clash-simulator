"""Round-2 result routing, activation, OCR, and native-label safety tests."""
from dataclasses import asdict, replace
import importlib.util
from pathlib import Path
import sys
import time
from types import SimpleNamespace
import unittest
import cv2
import numpy as np
from clasher.live.tower_channel import TowerChannel,TowerObservation,glyphs,SLOT_NAMES,activation_feature
from clasher.live.public_root import PublicMatchResult,apply_match_result,public_resources
from clasher.live.tower_model import PublicTowerModel,tower_packet_builder
from clasher.live.perception_adapter import PublicTowerAdapter
from clasher.rl.live_inference_contract import parse_public_vision_frame

# Reuse round-1 public fixtures; that suite remains unchanged.
from test_tower_channel import public,observations,artifact,canvas

ROOT=Path(__file__).resolve().parents[2]
STUDY=ROOT/'reports/strategy_council_20260928/live-loop/v4/tower-channel'
sys.path.insert(0,str(STUDY))
spec=importlib.util.spec_from_file_location('tower_truth_r2',STUDY/'truth_r2.py')
truth=importlib.util.module_from_spec(spec);spec.loader.exec_module(truth)


def snapshot(tick,slots=(0,1,2,3,4,5)):
    objects=[]
    for s in slots:
        owner,x,y=truth.ANCHORS[s]
        objects.append(dict(native_id=5000000+s,owner=owner,card_id=-1,x=int(x*1000),y=int(y*1000),max_hp=4824 if s%3==0 else 3052,hp=100))
    return dict(tick=tick,objects=objects,fence=dict(no_logic_step_during_observation=True))


class Round2TruthTests(unittest.TestCase):
    def derive(self,rows,ticks=(10,11,12,13,20),terminal=20):
        frames=[dict(tick_lo=t,tick_hi=t) for t in ticks]
        return truth.derive(rows,[],frames,dict(tick=terminal,ended=True))

    def test_permanent_disappearance_has_positive_witness_and_interval(self):
        rows=[snapshot(10),snapshot(12,(0,2,3,4,5)),snapshot(13,(0,2,3,4,5))]
        r=self.derive(rows)
        self.assertEqual(len(r['events']),1)
        self.assertEqual((r['events'][0]['last_positive_tick'],r['events'][0]['destruction_tick']),(10,12))
        self.assertEqual(r['labels'][0]['states'][1],'alive')
        self.assertIsNone(r['labels'][1]['states'][1])
        self.assertEqual(r['labels'][2]['states'][1],'destroyed')
        self.assertIsNone(r['labels'][-1]['states'][1])

    def test_capture_start_absence_terminal_teardown_and_unfenced_rows_masked(self):
        self.assertEqual(self.derive([snapshot(10,(0,2,3,4,5)),snapshot(12,(0,2,3,4,5)),snapshot(13,(0,2,3,4,5))])['events'],[])
        self.assertEqual(self.derive([snapshot(10),snapshot(19,(0,2,3,4,5)),snapshot(20,(0,2,3,4,5))])['events'],[])
        self.assertEqual(self.derive([snapshot(10),snapshot(12,()),snapshot(13,())])['events'],[])
        bad=snapshot(12,(0,2,3,4,5));bad['fence']={}
        self.assertEqual(self.derive([snapshot(10),bad,snapshot(13,(0,2,3,4,5))])['events'],[])

    def test_duplicate_ticks_are_coalesced_only_when_towers_agree(self):
        r=self.derive([snapshot(10),snapshot(10),snapshot(12),snapshot(13)])
        self.assertEqual(r['duplicate_identical_ticks'],1)
        with self.assertRaises(ValueError):self.derive([snapshot(10),snapshot(10,(0,2,3,4,5)),snapshot(12)])
        with self.assertRaises(ValueError):self.derive([snapshot(12),snapshot(10)])

    def test_transient_disappearance_and_missing_king_do_not_establish_death(self):
        self.assertEqual(self.derive([snapshot(10),snapshot(12,(0,2,3,4,5)),snapshot(13)])['events'],[])
        self.assertEqual(self.derive([snapshot(10),snapshot(12,(2,3,4,5)),snapshot(13,(2,3,4,5))])['events'],[])


class Round2PublicTests(unittest.TestCase):
    def test_king_death_comes_from_three_crown_public_result(self):
        frame=public(observations('alive',0),time=100)
        ended=apply_match_result(frame,PublicMatchResult('one',100,(0,3),.99))
        self.assertEqual(ended.tower_observations[0].state,'destroyed')
        self.assertEqual(ended.tower_observations[0].destruction_evidence,'public_match_result')
        self.assertTrue(ended.tower_observations[3].match_ended)
        self.assertEqual(ended.tower_observations[3].state,'unknown')
        m=PublicTowerModel();modeled,_=m.reconcile(ended)
        self.assertEqual(modeled.entities[0].hp_fraction,0.)
        timed=apply_match_result(frame,PublicMatchResult('one',100,(1,2),.99))
        self.assertTrue(all(o.state=='unknown' for o in timed.tower_observations))
        with self.assertRaises(ValueError):TowerObservation('opp_king','destroyed',confidence=.9,last_observed_ms=100,destruction_evidence='rubble_template')
        with self.assertRaises(ValueError):apply_match_result(frame,PublicMatchResult('other',100,(0,3),.9))
        with self.assertRaises(ValueError):apply_match_result(frame,PublicMatchResult('one',101,(0,3),.9))
        with self.assertRaises(ValueError):PublicMatchResult('one',100,(3,3),.9)

    def test_result_bypasses_pixel_reads_and_sets_packet_terminal_even_two_crowns(self):
        adapter=PublicTowerAdapter(artifact())
        frame=public(time=100)
        result=PublicMatchResult('one',100,(1,2),.99)
        observed=adapter.observe(frame,None,result=result)
        class Base:
            def __init__(self,builder):self.hp,self.positions,self.last_time={},{},None
            def build(self,frame,tick,seat=1,terminal=False):return frame,dict(terminal=terminal)
        builder=tower_packet_builder(Base,only_channel=True)(None)
        packet,d=builder.build(observed,2)
        self.assertTrue(d['terminal'])
        self.assertTrue(builder.build(frame,2,result=result)[1]['terminal'])
        self.assertTrue(builder.build(public(time=150),3)[1]['terminal'])
        self.assertFalse(builder.build(public(episode='next'),0)[1]['terminal'])
        class Resources:
            def root(self,*args):raise AssertionError('Terminal must not enter a native root')
        with self.assertRaises(ValueError):public_resources(Resources)().root(SimpleNamespace(packet=SimpleNamespace(observation=SimpleNamespace(terminal=True))),{},None)

    def test_planner_returns_wait_before_searching_a_public_terminal_packet(self):
        from clasher.live.decision import RustPlanner
        planner=RustPlanner.__new__(RustPlanner)
        planner.delay_aware,planner.delay_ticks,planner.backend=True,3,'native'
        packet=SimpleNamespace(observation=SimpleNamespace(terminal=True))
        planner.packets=SimpleNamespace(build=lambda frame,tick:(packet,{'terminal':True}))
        snapshot=SimpleNamespace(public=public(),tick=0,pending=None)
        action,diagnostic=planner.decide(snapshot,time.monotonic()+1)
        self.assertEqual(action,2304)
        self.assertEqual(diagnostic['reason'],'public_match_result')
        self.assertEqual(diagnostic['completed'],0)

    def test_activation_is_typed_visual_latched_public_state(self):
        data=artifact();base=TowerChannel(data);image=canvas(base,[180]*6);x,y=base.centers[0]
        f=activation_feature(image[y-95:y+55,x-48:x+48]).tolist()
        data['activation']={'0':{'active':[f],'sleeping':[[90/255]*576]}}
        c=TowerChannel(data);measured=c.step(image,'one',0)
        self.assertTrue(measured[0].king_active)
        self.assertIsNone(measured[3].king_active)
        self.assertIsNone(c.read_activation(np.full((150,96,3),150,np.uint8),0))
        m=PublicTowerModel();_,d=m.reconcile(public(measured));self.assertEqual(d['tower_king_active'],{'opp_king':True})
        sleeping=list(observations('alive',50));sleeping[0]=replace(sleeping[0],king_active=False)
        self.assertTrue(m.reconcile(public(sleeping,time=50))[1]['tower_king_active']['opp_king'])
        self.assertEqual(m.reconcile(public(episode='next'))[1]['tower_king_active'],{})
        with self.assertRaises(ValueError):TowerObservation('opp_left','alive',confidence=.9,last_observed_ms=0,king_active=True)
        with self.assertRaises(ValueError):TowerObservation('opp_king',king_active=True)

    def test_new_number_families_have_separate_glyph_geometry_and_abstention_gate(self):
        data=artifact();tables={}
        panels={}
        for slot,text,left,top in ((1,'3052',32,20),(3,'1700',42,40)):
            p=np.zeros((80,110,3),np.uint8)
            for j,d in enumerate(text):
                x=left+j*10
                p[top:top+12,x:x+8]=255
                # Connected glyphs with different internal holes and fixed
                # baseline exercise the real side-specific segmentation.
                hole=2+int(d)
                p[top+2:top+2+hole,x+2:x+5]=0
            gs=glyphs(p,slot);self.assertEqual(len(gs),4)
            family='opp_princess' if slot==1 else 'own_king';table={}
            for d,g in zip(text,gs):table.setdefault(d,[]).append(g.tolist())
            tables[family]=table;panels[slot]=p
        data['digits_by_family']=tables
        data['parameters']['digit_margin']=.005  # Synthetic adjacent shapes differ by one row.
        c=TowerChannel(data);sprite=np.full((150,96,3),180,np.uint8)
        self.assertEqual(c.read_crop(sprite,panels[1],1)[2],3052)
        self.assertEqual(c.read_crop(sprite,panels[3],3)[2],1700)
        data['number_enabled']={'opp_princess':False,'own_king':False};c=TowerChannel(data)
        self.assertIsNone(c.read_crop(sprite,panels[1],1)[2])
        self.assertIsNone(c.read_crop(sprite,panels[3],3)[2])
        self.assertEqual(glyphs(panels[3],0),[])

    def test_new_fields_survive_serialized_transport(self):
        frame=apply_match_result(public(time=100),PublicMatchResult('one',100,(3,0),.99))
        row=asdict(frame);outer={k:row.pop(k) for k in ('episode_id','frame_id','timestamp_ms')}
        self.assertEqual(parse_public_vision_frame(dict(schema_version=1,public=row,**outer)),frame)

if __name__=='__main__':unittest.main()
