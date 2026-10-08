import numpy as np
import pytest
from clasher.analysis.loss_review.metrics import Game,extract
from clasher.analysis.loss_review.human import TrainDevStore
from clasher.analysis.loss_review.summarize import bootstrap_matrix,ingest

CAT={'cards':{'Knight':{'cost':3,'token':2,'spell':None},'HogRider':{'cost':4,'token':3,'spell':None}},'bodies':{}}

def game(threat=True):
    ticks=np.arange(90,691,5);n=len(ticks)
    g=np.zeros((n,18));g[:,5]=.3;g[:,8:14]=1
    hands=np.tile([2,3,0,0],(n,1));entities=[];offsets=[0]
    for t in ticks:
        rows=[]
        if threat and 190<=t<300:
            row=np.zeros(17);row[[0,1,3,4,9]]=[.25,.45,1,1,1];rows.append(row)
        entities.extend(rows);offsets.append(len(entities))
    return Game('x','match','human','train','other vs other',['Knight','HogRider'],0,
        ticks,g,hands,np.array(offsets),np.array(entities).reshape(-1,17),np.zeros(len(entities),int),[],{})

def test_arrival_response_and_nonresponse():
    x=game();x.plays=[dict(tick=210,card='Knight',x=4,y=10,accepted=True,elixir_before=3)]
    r=extract(x,CAT)['stats']['all']
    assert r['arrival_under4_fraction']==[1,1]
    assert r['response_latency_capped8_seconds']==[1,1]
    assert r['no_response_within8_fraction']==[0,1]
    x.plays=[]
    assert extract(x,CAT)['stats']['all']['response_latency_capped8_seconds']==[8,1]

def test_no_push_is_missing_and_unused_card_has_exposure():
    r=extract(game(False),CAT)['stats']['all']
    assert 'arrival_under4_fraction' not in r
    assert r['card_per_deck_minute:Knight']==pytest.approx([0,.5])

def test_phase_duration_and_cap_leak_exclude_action_interval():
    x=game(False);x.globals[:,5]=1;x.globals[40:,2]=1
    x.plays=[dict(tick=90,card='Knight',x=4,y=10,accepted=True,elixir_before=10)]
    r=extract(x,CAT)['stats']
    assert r['phase=single']['time_at_max_fraction']==[10,10]
    assert r['phase=double']['time_at_max_fraction']==[20,20]
    assert r['all']['leaked_elixir_lower_bound_per_minute'][0]==pytest.approx(60*(9.75*.356+20*.714))

def test_lane_reset_censoring_and_enemy_buildings_not_pushes():
    x=game();x.entities[:,4]=0;x.entities[:,5]=1
    assert 'arrival_elixir' not in extract(x,CAT)['stats']['all']
    x=game();x.ticks=x.ticks[:30];x.globals=x.globals[:30];x.hands=x.hands[:30]
    end=x.offsets[30];x.offsets=x.offsets[:31];x.entities=x.entities[:end];x.entity_ids=x.entity_ids[:end]
    assert 'arrival_elixir' not in extract(x,CAT)['stats']['all']

def test_roles_rejected_before_file_access(tmp_path):
    for role in ('eval','eval_ood','heldout','../dev'):
        with pytest.raises(ValueError):TrainDevStore(tmp_path,role)
    x=game();x.role='eval'
    with pytest.raises(ValueError):extract(x,CAT)

def test_cluster_bootstrap_denominators_and_reproducibility():
    m=np.array([[[1.,1.]],[[0.,9.]]])
    p,a,t=bootstrap_matrix(m,7,200)
    assert p[0]==.1
    assert np.array_equal(a,bootstrap_matrix(m,7,200)[1])
    assert set(a[:,0])=={0.,.1,1.}

def test_two_perspectives_clustered(tmp_path):
    import json
    rows=[]
    for i in range(2):
        r=extract(game(),CAT);r['identity']=str(i);rows.append(r)
    p=tmp_path/'g.jsonl';p.write_text('\n'.join(map(json.dumps,rows)))
    data,_,_=ingest([p])
    assert len(data['human']['all'])==1
    assert data['human']['all']['match']['arrival_under4_fraction']==[2,2]

def test_cycle_distance_separates_resources_from_card_availability():
    x=game();x.hands[:]=[3,0,0,0];x.queues=np.tile([3,2,0,0],(len(x.ticks),1))
    r=extract(x,CAT)['stats']['all']
    assert r['defender_not_in_hand_fraction']==[1,1]
    assert r['defender_cycle_distance']==[2,1]
    x.hands[:,0]=2;x.globals[:,5]=.1
    r=extract(x,CAT)['stats']['all']
    assert r['defender_not_in_hand_fraction']==[0,1]
    assert r['no_affordable_defender_in_hand_fraction']==[1,1]
    assert r['defender_cycle_distance']==[0,1]


def test_opposite_lane_not_counted_as_defense_and_seven_elixir_boundary():
    x=game();x.plays=[dict(tick=200,card='Knight',x=14,y=10,accepted=True,elixir_before=10)]
    r=extract(x,CAT)['stats']['all'];assert r['no_response_within8_fraction']==[1,1]
    x.plays=[dict(tick=200,card='Knight',x=4,y=10,accepted=True,elixir_before=10),
             dict(tick=230,card='HogRider',x=4,y=10,accepted=True,elixir_before=7)]
    assert extract(x,CAT)['stats']['all']['defensive_commitment_ge7_fraction']==[1,1]


def test_bootstrap_absent_opportunities_not_zero():
    m=np.array([[[0.,0.]],[[2.,1.]]])
    point,boot,_=bootstrap_matrix(m,3,100)
    assert point[0]==2
    assert np.isnan(boot).any()
    assert (boot[np.isfinite(boot)]==2).all()

def test_canonical_wallbreakers_alias_is_win_condition():
    from clasher.analysis.loss_review.metrics import archetype,WIN_CONDITIONS
    assert archetype(['Wallbreakers'])=='chip'
    assert 'Wallbreakers' in WIN_CONDITIONS


def test_summary_rejects_duplicate_and_forbidden_role(tmp_path):
    import json
    r=extract(game(),CAT);p=tmp_path/'g.jsonl'
    p.write_text(json.dumps(r)+'\n'+json.dumps(r)+'\n')
    with pytest.raises(ValueError,match='duplicate'):ingest([p])
    r['role']='eval';p.write_text(json.dumps(r)+'\n')
    with pytest.raises(ValueError,match='forbidden'):ingest([p])
