"""Causal event timing and recovery boundaries for L1 v2."""
from pathlib import Path
from dataclasses import replace

import numpy as np
import pytest

from clasher.rl.live_inference_contract import PublicPlayEvent
from clasher.vision.l1_events_v2 import EventFusion,stack_pixels
from clasher.vision.l1_derived_v2 import RobustPublicState,PublicTickClock


def exact_type():
    path=Path(__file__).resolve().parents[1]/'reports/strategy_council_20260928/live-loop/l1/v2/derived_public_state_reference.py'
    ns={'__name__':'test_reference'}
    exec(compile(path.read_text(),str(path),'exec'),ns)
    return ns['DerivedPublicState']


def candidate(card='Knight',side=0,x=3.,score=.9):
    return dict(player_id=side,card=card,x=x,y=12.,confidence=score,source='temporal_pixels')


def test_temporal_stack_preserves_order_and_uses_only_supplied_frames():
    ims=[np.full((2,3,3),n,np.uint8) for n in (10,20,30)]
    out=stack_pixels(ims)
    assert out.shape==(9,2,3)
    np.testing.assert_allclose(out[0],30/255)
    np.testing.assert_allclose(out[3],10/255)
    np.testing.assert_allclose(out[6],20/255)


def test_fusion_deduplicates_persistent_cues_but_admits_later_play():
    f=EventFusion(.3)
    assert not f.update('0',0,[candidate()],fresh=True)
    assert len(f.update('1',100,[candidate()]))==1
    assert not f.update('2',200,[candidate()])
    assert len(f.update('3',2000,[candidate()]))==1
    assert len(f.update('4',2100,[candidate(side=1)]))==1


def test_fusion_uses_validation_threshold_and_marker_position():
    f=EventFusion(.8)
    marker=dict(candidate(x=4.),source='clock_and_v1_identity',confidence=.7)
    result=f.update('1',100,[candidate(score=.5),marker])
    assert len(result)==1 and result[0].x_tiles==4.


def states():
    names=['Archers','Cannon','Fireball','Giant','Goblins','Knight','Log','Zap']
    costs={n:1 for n in names}
    prior={'decks':[{'cards':names}]}
    exact=exact_type()
    return names,exact(prior,costs),RobustPublicState(exact,prior,costs)


def test_robust_true_events_match_exact_and_never_read_private_state():
    names,reference,robust=states();history=[]
    for i in range(16):
        tick=100+i*80;name=names[i%8]
        history.append((tick,name));reference.update(tick+20,history)
        robust.observe(tick,[PublicPlayEvent(str(i),0,name,.995)])
        actual=robust.observe(tick+20,[])
        assert abs(actual['elixir']-reference.elixir_units/10000)<.08
        if reference.derived()['hand'] is not None:
            assert actual['hand']==reference.derived()['hand']


def test_spurious_impossible_play_and_duplicate_do_not_collapse():
    names,reference,robust=states()
    event=PublicPlayEvent('same',0,names[0],.99)
    before=robust.observe(100,[event])
    after=robust.observe(100,[event])
    assert before==after and robust.diagnostics['duplicates']==1
    # A played card cannot immediately be replayed from a four-card cycle.
    actual=robust.observe(101,[replace(event,event_id='extra')])
    assert np.isfinite(actual['elixir']) and actual['hypotheses']>0
    with pytest.raises(ValueError):robust.observe(99,[])


def test_unknown_card_is_ignored_and_own_events_do_not_spend_opponent_elixir():
    _,_,robust=states()
    before=robust.observe(100,[])
    after=robust.observe(100,[PublicPlayEvent('own',1,'Knight',1.),PublicPlayEvent('bad',0,'NotP16',1.)])
    assert before==after and robust.diagnostics['unknown_cards']==1


def test_public_clock_ignores_absolute_media_epoch_and_stays_monotone():
    a=PublicTickClock();b=PublicTickClock()
    for clock,media in [(164,1000),(164,1100),(163,1200),(164,1300),(None,1400)]:
        before=a.tick
        assert a.update(clock,media)==b.update(clock,media+100000)
        assert a.tick>=before


def test_own_spell_never_uses_unrelated_troop_clock(monkeypatch):
    from collections import deque
    from types import SimpleNamespace
    import torch
    import clasher.vision.l1_events_v2 as module
    from clasher.rl.live_inference_contract import PublicVisionFrame,VisionEntity
    detector=module.TemporalEventDetector.__new__(module.TemporalEventDetector)
    detector.episode='e';detector.last_time=0;detector.device='cpu'
    detector.images=deque([np.zeros((400,272,3),np.uint8)]*3,maxlen=3)
    detector.tracker=SimpleNamespace(update=lambda frame:frame)
    detector.net=lambda x:torch.full((1,32,100,68),-20.)
    detector.geo=SimpleNamespace(tile=lambda x,y:(x/30,y/30))
    detector.offsets={'0':[0,0],'1':[0,0]}
    detector.markers=[];detector.pending=[];detector.fusion=EventFusion(.5,.8)
    monkeypatch.setattr(module,'clock_markers',lambda image:[dict(player_id=1,px=150.,py=600.,confidence=.95,radius=17.)])
    event=PublicPlayEvent('zap',1,'Zap',.85)
    knight=VisionEntity('knight','Knight','troop',1,5.,20.,.9)
    frame=PublicVisionFrame('e','1',100,174.,1.,4.,1.,('Knight','Giant','Log','Archers'),(1.,)*4,'Skeletons',1.,(knight,),(event,))
    result,cues=detector.step(np.zeros((1140,540,3),np.uint8),frame)
    spells=[e for e in result.play_events if e.card=='Zap']
    assert len(spells)==1 and spells[0].x_tiles is None
    assert not any(c['card']=='Zap' and c['source']=='clock_and_v1_identity' for c in cues['candidates'])


def test_stream_event_scoring_requires_whole_time_bracket(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]/'scripts'))
    from evaluate_l1_events_v2 import score_events
    from clasher.rl.live_inference_contract import PublicVisionFrame
    event=PublicPlayEvent('play',0,'Knight',.9,3.,12.)
    truth=[dict(episode_id='e',tick=10,player_id=0,card='Knight',x_tiles=3.,y_tiles=12.,
                event_time_interval_ms=[450.,550.])]
    def frame(t):
        return PublicVisionFrame('e',str(t),t,174.,1.,4.,1.,('Knight','Giant','Log','Archers'),
                                 (1.,)*4,'Skeletons',1.,(),(event,))
    for t in (500.,951.):assert score_events([frame(t)],truth)['recall']==0
    for t in (550.,950.):assert score_events([frame(t)],truth)['recall']==1


def test_stream_sampler_canonicalizes_fractional_media_time(tmp_path,monkeypatch):
    import json
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]/'scripts'))
    from evaluate_l1_events_v2 import sample_inputs
    rows=[dict(episode_id='e',frame_id=str(i),timestamp_ms=t,image=f'{i}.jpg',split='heldout')
          for i,t in enumerate((31.913,132.142,233.789))]
    (tmp_path/'inputs.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
    output=tmp_path/'public.jsonl';sample_inputs(tmp_path,'heldout',10.,output)
    actual=[json.loads(l) for l in output.read_text().splitlines()]
    assert [r['timestamp_ms'] for r in actual]==[31,132,233]
    assert all(set(r)=={'episode_id','frame_id','timestamp_ms','image'} for r in actual)
    sample_inputs(tmp_path,'heldout',None,output)
    assert len(output.read_text().splitlines())==len(rows)
