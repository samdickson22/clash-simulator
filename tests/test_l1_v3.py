"""Timing honesty and public-only noisy-event posterior regression tests."""
import numpy as np
import pytest

from clasher.rl.live_inference_contract import PublicPlayEvent
from clasher.vision.l1_derived_v3 import OpponentPosterior,StreamPublicClock
from clasher.vision.l1_timing_v3 import fit_timing
from clasher.vision.l1_events_v3 import secondary_birth, StreamFusion, SpellCueBuffer


COSTS={f'Card{i}':1+(i%4) for i in range(16)}


def event(i,name='Card0',confidence=.99,side=0):
    return PublicPlayEvent(str(i),side,name,confidence,None,None)


def test_zero_event_exact_integer_regeneration():
    p=OpponentPosterior(COSTS,particles=64,missed_plays_per_second=0)
    p.advance(10)
    assert p.distribution()['elixir_mean']==pytest.approx((60000+10*int(500/2.8))/10000)
    p.advance(6000)
    assert p.distribution()['elixir_mean']==pytest.approx(10)
    assert p.distribution()['hand'] is None
    assert p.distribution()['calibrated'] is False


def test_own_events_do_not_change_opponent():
    a=OpponentPosterior(COSTS,particles=64,missed_plays_per_second=0,seed=8)
    b=OpponentPosterior(COSTS,particles=64,missed_plays_per_second=0,seed=8)
    assert a.observe(10,[event(0,side=1)])==b.observe(10,[])


def test_duplicates_do_not_spend_twice():
    a=OpponentPosterior(COSTS,particles=128,missed_plays_per_second=0,seed=6)
    b=OpponentPosterior(COSTS,particles=128,missed_plays_per_second=0,seed=6)
    a.observe(20,[event(0)]);a.observe(20,[event(0)])
    b.observe(20,[event(0)])
    np.testing.assert_array_equal(a.elixir,b.elixir)
    np.testing.assert_array_equal(a.cards,b.cards)


def test_uncertain_event_retains_spend_and_no_spend():
    p=OpponentPosterior(COSTS,particles=512,missed_plays_per_second=0)
    d=p.observe(0,[event(0,confidence=.8)])
    assert d['elixir_bounds']==[5.,6.]
    assert d['elixir_sd']>0
    assert d['hand'] is None


def test_misses_create_uncertainty_without_contradictory_event():
    p=OpponentPosterior(COSTS,particles=512,missed_plays_per_second=.2)
    p.advance(100)
    assert p.diagnostics['latent_plays']>0
    assert p.distribution()['elixir_sd']>.1
    assert 0<=p.elixir.min()<=p.elixir.max()<=100000


def test_sampling_respects_deck_uniqueness_and_refill():
    p=OpponentPosterior(COSTS,particles=128,missed_plays_per_second=0)
    p.observe(0,[event(0,confidence=1)])
    sample=p.sample(np.random.default_rng(23))
    assert len([v for v in sample['hand'] if v is None])==1
    p.advance(1)
    sample=p.sample(np.random.default_rng(23))
    assert None not in sample['hand']
    assert len(set(sample['hand']+sample['cycle']))==8
    assert sample['cycle'][-1]=='Card0'


def test_impossible_high_confidence_event_does_not_collapse():
    p=OpponentPosterior(COSTS,particles=128,missed_plays_per_second=0)
    p.observe(0,[event(0,confidence=1)])
    before=p.elixir.copy()
    p.observe(0,[event(1,confidence=1)])
    assert p.diagnostics['contradictions']==1
    np.testing.assert_array_equal(p.elixir,before)
    assert np.isfinite(p.weights).all()


def test_clock_cannot_move_backwards():
    p=OpponentPosterior(COSTS,particles=32)
    p.advance(10)
    with pytest.raises(ValueError,match='monotone'):p.advance(9)


def test_reveal_and_cycle_can_concentrate_hand():
    p=OpponentPosterior(COSTS,particles=1024,missed_plays_per_second=0)
    for i in range(16):
        p.observe(i*240,[event(i,f'Card{i%8}',1)])
        p.advance(i*240+21)
    assert p.distribution()['hand'] is not None
    assert p.distribution()['hand_probability']>=.9


def test_timing_reports_quantization_without_claiming_fence():
    requests=[dict(command='resume')]
    frames=[]
    for i in range(600):
        t=i*.05
        requests.append(dict(command='observe',start_ns=round((100+t)*1e9),
            end_ns=round((100+t+.001)*1e9),result=dict(tick=340+i)))
        if i%2==0:
            rendered=max(340,340+i-2)
            frames.append(dict(produced_epoch_s=1100+t,received_mono_s=100+t+.06,
                mono_before_ns=round((100+t+.06)*1e9),mono_after_ns=round((100+t+.06)*1e9),
                wall_ns=round((1100+t+.06)*1e9),clock=180-(rendered-1)//20,clock_confidence=1.))
    result=fit_timing(requests,frames)
    assert result['ticks_per_second']==pytest.approx(20)
    assert result['fps']==pytest.approx(10)
    assert result['exact_render_tick_certified'] is False
    assert result['clock_interval_width_p95_ms']>0


def test_timing_rejects_reordered_native_anchors():
    requests=[dict(command='resume')]+[dict(command='observe',start_ns=i*1000000,
        end_ns=i*1000000+100,result=dict(tick=100-i)) for i in range(50)]
    with pytest.raises(ValueError,match='monotone'):fit_timing(requests,[{}]*50)


def test_secondary_spawns_need_nearby_same_side_recent_source():
    source=dict(card='Golem',side=0,x=3.,y=4.,time=100)
    assert secondary_birth('Golemite',0,3.5,4.,[source],200)
    assert not secondary_birth('Golemite',1,3.5,4.,[source],200)
    assert not secondary_birth('Golemite',0,13.5,4.,[source],200)
    assert not secondary_birth('Golemite',0,3.5,4.,[source],2000)
    assert not secondary_birth('Knight',0,3.5,4.,[source],200)


def test_multi_cue_fusion_emits_one_event_and_does_not_invent_placement():
    fusion=StreamFusion({'default':.7})
    cue=dict(card='Fireball',side=1,x=None,y=None,confidence=.9)
    events=fusion.update('1',100,[cue,cue])
    assert len(events)==1 and events[0].x_tiles is None
    assert fusion.update('2',200,[cue])==[]


def test_native_counter_bracket_rejects_races():
    from scripts.l1_native_capture_v3 import consistent_observation
    def status(t):return dict(mode='native-render',generation=1,stateEpoch=1,tick=t,
        steps=t,nativeStockStepCallbacks=t)
    def observation(t):return dict(generation=1,stateEpoch=1,tick=t,truncated=False,count=0,returned=0)
    replies=iter([status(4),observation(4),status(5),status(6),observation(6),status(6)])
    rejections=[]
    obs,fence=consistent_observation(lambda _:next(replies),record=rejections.append)
    assert obs['tick']==6 and fence['no_logic_step_during_observation']
    assert len(rejections)==1


def test_native_counter_identity_rejects_active_step():
    from scripts.l1_native_capture_v3 import identity
    assert identity(dict(mode='native-render',steps=2,nativeStockStepCallbacks=3)) is None


def test_calibrated_distribution_and_search_sampler_agree():
    p=OpponentPosterior(COSTS,particles=32,missed_plays_per_second=0,
        calibration_residuals=[-1.,1.])
    d=p.distribution()
    assert d['calibrated'] and d['elixir_interval_90']==[5.,7.]
    assert d['elixir_mean']==pytest.approx(6.) and d['elixir_sd']==pytest.approx(1.)
    rng=np.random.default_rng(6)
    samples=[p.sample(rng)['elixir'] for _ in range(1000)]
    assert set(samples)=={5.,7.} and np.mean(samples)==pytest.approx(6.,abs=.1)


def test_spell_ownership_waits_for_own_hud_and_retains_brief_effect():
    cue=dict(card='Zap',side=0,x=3.,y=5.,confidence=.9,source='spell_pixels')
    buffer=SpellCueBuffer()
    assert buffer.update(100,[cue],[],hud_reliable=True)==[]
    # The effect can disappear before the hand reader resolves the spend.
    own=buffer.update(200,[],['Zap'],hud_reliable=False)
    assert len(own)==1 and own[0]['side']==1 and own[0]['confidence']==.9
    buffer=SpellCueBuffer();buffer.update(100,[cue],[],hud_reliable=True)
    enemy=buffer.update(300,[],[],hud_reliable=True)
    assert len(enemy)==1 and enemy[0]['side']==0


def test_late_entry_keeps_unrevealed_deck_generic():
    p=OpponentPosterior(COSTS,particles=64,missed_plays_per_second=.2)
    p.start_at(4800)
    assert np.all(p.cards==-1)
    assert p.distribution()['elixir_bounds']==[0.,10.]
    assert p.diagnostics['latent_plays']==0
    with pytest.raises(ValueError,match='before'):p.start_at(4801)


def test_visible_overtime_phase_disambiguates_same_digits():
    regular=StreamPublicClock();overtime=StreamPublicClock()
    assert overtime.update(61,0,'overtime')-regular.update(61,0,'regulation')==2400


def test_white_digits_survive_red_overtime_background():
    import cv2
    from clasher.vision.l1 import CLOCK
    from clasher.vision.l1_hud_v3 import clock_digits_v3,visible_clock_phase
    image=np.zeros((1140,540,3),np.uint8);x1,y1,x2,y2=CLOCK
    patch=np.full((y2-y1,x2-x1,3),(90,80,200),np.uint8)
    cv2.putText(patch,'1:01',(8,24),cv2.FONT_HERSHEY_SIMPLEX,.7,(255,255,255),2)
    image[y1:y2,x1:x2]=patch
    assert len(clock_digits_v3(image))==3
    assert visible_clock_phase(image)=='overtime'


def test_zero_match_threshold_tie_suppresses_false_positives(monkeypatch):
    import importlib
    from pathlib import Path
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]/'scripts'))
    rank=importlib.import_module('evaluate_l1_stream_v3').threshold_rank
    trials=[dict(threshold=.3,metrics=dict(per_card={'Miner':dict(truth=5,predictions=47,matched=0)})),
            dict(threshold=.9,metrics=dict(per_card={'Miner':dict(truth=5,predictions=0,matched=0)}))]
    assert max(trials,key=lambda trial:rank(trial,'Miner'))['threshold']==.9


def test_positive_f1_tie_preserves_more_matches(monkeypatch):
    import importlib
    from pathlib import Path
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]/'scripts'))
    rank=importlib.import_module('evaluate_l1_stream_v3').threshold_rank
    trials=[dict(threshold=.3,metrics=dict(per_card={'Knight':dict(truth=6,predictions=6,matched=3)})),
            dict(threshold=.9,metrics=dict(per_card={'Knight':dict(truth=6,predictions=2,matched=2)}))]
    assert max(trials,key=lambda trial:rank(trial,'Knight'))['threshold']==.3


def test_timing_clock_reset_can_cross_a_missing_frame():
    requests=[dict(command='resume')];frames=[]
    for i in range(600):
        t=i*.05;tick=3500+i
        requests.append(dict(command='observe',start_ns=round((100+t)*1e9),
            end_ns=round((100+t+.001)*1e9),result=dict(tick=tick)))
        if i%2==0:
            rendered=tick-2
            clock=(180 if rendered<=3600 else 300)-(rendered-1)//20
            if rendered==3600:clock=None
            frames.append(dict(produced_epoch_s=1100+t,received_mono_s=100+t+.06,
                mono_before_ns=round((100+t+.06)*1e9),mono_after_ns=round((100+t+.06)*1e9),
                wall_ns=round((1100+t+.06)*1e9),clock=clock,clock_confidence=1.))
    result=fit_timing(requests,frames)
    assert max(e['tick'] for e in result['clock_edges'])>3900
    assert len(result['clock_edges'])>=25
