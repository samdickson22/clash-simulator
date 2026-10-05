"""Privacy and scoring regressions for L1's offline screen boundary."""
from pathlib import Path

import cv2
import numpy as np
import pytest

from clasher.rl.live_inference_contract import VisionEntity
from clasher.vision.l1 import Geometry, fit_calibration, public_pixels
from clasher.vision.l1_perception import clock_digits, train_hud
from scripts.evaluate_l1_perception import match_entities


def test_private_top_hud_changes_cannot_change_public_pixels():
    rng=np.random.default_rng(3)
    a=rng.integers(0,256,(2280,1080,3),dtype=np.uint8)
    b=a.copy()
    b[:288]=255-b[:288]
    b[350:400]=255-b[350:400]
    # In the clock band, mutate only pixels outside the isolated clock.
    b[288:350,:892]=255-b[288:350,:892]
    b[288:350,1064:]=255-b[288:350,1064:]
    assert np.array_equal(public_pixels(a),public_pixels(b))


def test_uncalibrated_resolution_rejected():
    with pytest.raises(ValueError,match='Uncalibrated'):
        public_pixels(np.zeros((1920,1080,3),np.uint8))


def test_identity_and_owner_errors_are_not_position_matches():
    p=[VisionEntity('v1','Knight','troop',0,3,4,.9)]
    t=[dict(card='Knight',player_id=1,x_tiles=3,y_tiles=4),
       dict(card='Giant',player_id=0,x_tiles=3,y_tiles=4)]
    assert match_entities(p,t)==[]


def test_matching_is_one_to_one_and_counts_large_misses():
    p=[VisionEntity('a','Knight','troop',0,3,4,.9),
       VisionEntity('b','Knight','troop',0,3.1,4,.9)]
    t=[dict(card='Knight',player_id=0,x_tiles=3,y_tiles=4)]
    assert len(match_entities(p,t))==1
    assert match_entities(p,[dict(card='Knight',player_id=0,x_tiles=15,y_tiles=28)])==[]


def test_body_names_keep_action_names_out_of_entity_tokens():
    from clasher.vision.l1_perception import BODY_NAMES,ACTION_NAMES
    from clasher.data import CardDataLoader
    loader=CardDataLoader()
    for action,body in BODY_NAMES.items():
        assert loader.get_card(action).name==body
        assert ACTION_NAMES[body]==action
        p=[VisionEntity('v',body,'troop',0,3,4,.9)]
        assert match_entities(p,[dict(card=action,player_id=0,x_tiles=3,y_tiles=4)])==[(0,0,0.0)]


def test_calibration_heldout_and_roundtrip(tmp_path):
    p=tmp_path/'calibration.json'; result=fit_calibration(p); g=Geometry(p)
    assert result['max_tile_error']<.1
    for x,y in ((0,0),(18,32),(5.7,13.2)):
        np.testing.assert_allclose(g.tile(*g.pixel(x,y)),[x,y],atol=1e-10)


def test_hud_fitting_never_opens_heldout_images(tmp_path):
    # A heldout path is deliberately nonexistent; fitting must not open it.
    rows=[dict(split='heldout',image='forbidden.jpg',targets={})]
    with pytest.raises(ValueError,match='No usable training HUD'):
        train_hud(rows,tmp_path,tmp_path/'hud.npz')


def test_intro_has_no_clock_measurement():
    assert clock_digits(np.zeros((1140,540,3),np.uint8))==[]


def test_red_warning_clock_is_still_visible():
    im=np.zeros((1140,540,3),np.uint8)
    # One minute digit and two second digits, separated from a short colon.
    for x in (449,480,505):
        cv2.rectangle(im,(x,148),(x+12,170),(0,0,255),-1)
    cv2.rectangle(im,(470,155),(473,158),(0,0,255),-1)
    assert len(clock_digits(im))==3


def test_native_pairing_rejects_simulation_movement(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]/'scripts'))
    from scripts import collect_l1_rendered as collector
    count=0
    def call(command):
        nonlocal count
        if command=='status':
            return dict(paused=True,renderSuppressed=False,mode='native-render')
        count+=1
        return dict(tick=200 if count==1 else 201,truncated=False,finalized=False)
    _,png=cv2.imencode('.png',np.zeros((2280,1080,3),np.uint8))
    monkeypatch.setattr(collector.subprocess,'check_output',lambda *a,**kw:png.tobytes())
    monkeypatch.setattr(collector.time,'sleep',lambda _:None)
    with pytest.raises(RuntimeError,match='Observe changed'):
        collector.capture(call,'owned-test',200)
