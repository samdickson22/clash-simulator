"""Public tower safety, identity, lifecycle and transport regressions."""
from dataclasses import asdict, replace
import unittest

import numpy as np

from clasher.live.perception_adapter import PublicTowerAdapter
from clasher.live.tower_channel import TowerChannel, TowerObservation, SLOT_NAMES
from clasher.live.tower_model import PublicTowerModel, tower_packet_builder
from clasher.rl.live_inference_contract import (PublicVisionFrame, VisionEntity,
    InferenceContractError, validate_public_vision_frame, parse_public_vision_frame)


def public(towers=(), entities=(), episode='one', time=0):
    return PublicVisionFrame(episode, str(time), time, 180., 1., 10., 1.,
                             ('Knight',)*4, (1.,)*4, 'Zap', 1., tuple(entities), (),
                             tower_observations=tuple(towers))


def observations(state='unknown', time=None):
    return tuple(TowerObservation(s,state,confidence=.9 if state != 'unknown' else 0.,
                                 last_observed_ms=time) for s in SLOT_NAMES)


def artifact():
    return dict(schema='clasher.public-tower-templates.v1',
        parameters=dict(alive_distance=.15,rubble_distance=.055,rubble_margin=.035,
                        digit_distance=.18,digit_margin=.03,confirmation_frames=3,confirmation_gap_ms=600),
        sprites=[dict(alive=[[180/255]*648],destroyed=[[60/255]*648]) for _ in range(6)],digits={})


def canvas(channel, values):
    image = np.zeros((1140,540,3),np.uint8)
    for (x,y),value in zip(channel.centers,values):
        image[y-65:y+45,x-36:x+36] = value
    return image


class TowerChannelTests(unittest.TestCase):
    def test_fixed_slot_identity_and_missing_observations(self):
        channel = TowerChannel(artifact())
        alive = canvas(channel,[180]*6)
        first = channel.step(alive,'one',0)
        self.assertEqual([o.slot for o in first],list(SLOT_NAMES))
        self.assertEqual([o.state for o in first],['alive']*6)
        missing = channel.step(np.zeros_like(alive),'one',50)
        self.assertEqual([o.state for o in missing],['unknown']*6)
        self.assertEqual([o.last_observed_ms for o in missing],[0]*6)
        self.assertTrue(all(not o.hp_known and o.hp is None and o.destruction_evidence is None for o in missing))

    def test_positive_rubble_requires_distinct_consecutive_frames_and_resets(self):
        channel = TowerChannel(artifact())
        image = canvas(channel,[180,60,180,180,180,180])
        self.assertEqual(channel.step(image,'one',0)[1].state,'unknown')
        self.assertEqual(channel.step(image,'one',50)[1].state,'unknown')
        hit = channel.step(image,'one',100)
        self.assertEqual(hit[1].state,'destroyed')
        self.assertEqual(hit[1].destruction_evidence,'rubble_template')
        self.assertEqual(hit[0].state,'alive')
        with self.assertRaises(ValueError):
            channel.step(image,'one',100)
        self.assertEqual(channel.step(image,'one',1000)[1].state,'unknown')
        self.assertEqual(channel.step(image,'next',0)[1].state,'unknown')

    def test_model_latches_only_public_destruction_and_ignores_conflicting_body_hp(self):
        model = PublicTowerModel()
        living = list(observations('alive',0))
        living[1] = replace(living[1],hp_known=True,hp=model.max_hp[1]//2)
        wrong = VisionEntity('body','Tower','building',0,3.5,6.5,.99,.01,.99)
        modeled,_ = model.reconcile(public(living,[wrong]))
        self.assertEqual(modeled.entities[1].hp_fraction,.5)
        unknown,_ = model.reconcile(public(observations(),time=50))
        self.assertEqual(unknown.entities[1].hp_fraction,.5)
        self.assertEqual(len(unknown.entities),6)
        rubble = list(observations())
        rubble[1] = TowerObservation('opp_left','destroyed',confidence=.98,last_observed_ms=100,
                                     destruction_evidence='rubble_template')
        dead,d = model.reconcile(public(rubble,time=100))
        self.assertEqual(dead.entities[1].hp_fraction,0.)
        self.assertEqual(d['tower_destroyed'],1)
        contradiction,_ = model.reconcile(public(observations('alive',150),[wrong],time=150))
        self.assertEqual(contradiction.entities[1].hp_fraction,0.)
        reset,_ = model.reconcile(public(episode='two'))
        self.assertEqual(reset.entities[1].hp_fraction,1.)

    def test_transport_rejects_unproven_death_future_time_and_duplicate_slots(self):
        validate_public_vision_frame(public(observations('alive',0)))
        with self.assertRaises(ValueError):
            TowerObservation('own_king','destroyed',confidence=1.,last_observed_ms=0)
        with self.assertRaises(ValueError):
            TowerObservation('opp_left','unknown',hp_known=True,hp=0)
        with self.assertRaises(InferenceContractError):
            validate_public_vision_frame(public(observations('alive',1)))
        with self.assertRaises(InferenceContractError):
            validate_public_vision_frame(public([observations()[0]]*6))

    def test_adapter_preserves_raw_body_tracks_and_public_metadata(self):
        raw = public(entities=[VisionEntity('body','KingTower','building',0,9.,3.,.8,.12,.8)])
        adapter = PublicTowerAdapter(artifact())
        image = canvas(adapter.channel,[180]*6)
        measured = adapter.observe(raw,image)
        self.assertEqual(measured.entities,raw.entities)
        self.assertEqual(measured.own_hand,raw.own_hand)
        self.assertEqual(raw.tower_observations,())
        self.assertEqual(len(measured.tower_observations),6)
        validate_public_vision_frame(measured)

    def test_input_rejects_uncalibrated_pixels_and_invalid_evidence(self):
        channel = TowerChannel(artifact())
        with self.assertRaises(ValueError):
            channel.step(np.zeros((2280,1080,3),np.uint8),'one',0)
        with self.assertRaises(ValueError):
            TowerObservation('own_left','destroyed',hp_known=True,hp=123,confidence=1.,
                             last_observed_ms=0,destruction_evidence='rubble_template')

    def test_packet_adapter_activates_from_channel_and_preserves_legacy_producers(self):
        class Base:
            def __init__(self,builder):
                self.hp,self.positions,self.last_time = {},{},None
            def build(self,frame,tick,seat=1,terminal=False):
                validate_public_vision_frame(frame)
                return frame,{}
        builder = tower_packet_builder(Base,only_channel=True)(None)
        raw = public()
        self.assertEqual(builder.build(raw,0)[0],raw)
        measured = public(observations('alive',50),time=50)
        packet,diagnostic = builder.build(measured,1)
        self.assertEqual(len(packet.entities),6)
        self.assertEqual(diagnostic['tower_channel_slots'],6)
        missed,_ = builder.build(public(time=100),2)
        self.assertEqual(len(missed.entities),6)
        next_raw = public(episode='next')
        self.assertEqual(builder.build(next_raw,0)[0],next_raw)

    def test_serialized_channel_roundtrip_keeps_observation_fields(self):
        frame = public(observations('alive',0))
        row = asdict(frame)
        outer = {k:row.pop(k) for k in ('episode_id','frame_id','timestamp_ms')}
        result = parse_public_vision_frame(dict(schema_version=1,public=row,**outer))
        self.assertEqual(result,frame)


if __name__ == '__main__':
    unittest.main()
