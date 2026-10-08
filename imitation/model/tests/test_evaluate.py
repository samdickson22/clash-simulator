import math
import numpy as np
import pytest
import torch
from imitation.model.evaluate import metric_rows, summarize, calibration, _cluster_ci, fit_temperature, compare_paired


def known():
    # Two play, one wait, one ability. Gate uniform, only slot0 and two tiles legal.
    n=4
    o = {"gate": torch.zeros(n,3), "card": torch.zeros(n,4), "tile": torch.zeros(n,4,576),
         "gate_mask": torch.ones(n,3,dtype=torch.bool), "card_mask": torch.zeros(n,4,dtype=torch.bool),
         "tile_mask": torch.zeros(n,4,576,dtype=torch.bool),
         "intent_card": torch.zeros(n,8), "hazard": torch.zeros(n,13)}
    o["card_mask"][:,0] = True; o["tile_mask"][:,0,:2] = True
    y = {"action": torch.tensor([0,1,2304,2305]), "supervised": torch.ones(n,dtype=torch.bool),
         "intent_card": torch.zeros(n,dtype=torch.long), "intent_bin": torch.zeros(n,dtype=torch.long),
         "intent_observed": torch.ones(n,dtype=torch.bool), "intent_valid": torch.ones(n,dtype=torch.bool)}
    return o,y,torch.tensor([[1,2,3,4]]*n)


def test_metrics_known_answers():
    o,y,h = known(); rows=metric_rows(o,y,h)
    r=summarize(rows,np.array([0,0,1,1]),resamples=100)
    m=r["metrics"]
    assert m["joint_nll"]["value"] == pytest.approx(math.log(3)+math.log(2)/2)
    assert m["play_wait_nll"]["value"] == pytest.approx((3*-math.log(2/3)+math.log(3))/4)
    assert m["play_wait_brier"]["value"] == pytest.approx(7/36)
    assert m["card_nll"]["value"] == 0
    assert m["card_top1"]["value"] == 1
    assert m["tile_nll"]["value"] == pytest.approx(math.log(2))
    assert m["median_tile_error"]["value"] == .5
    assert m["top8_recall"]["value"] == 1
    assert m["top8_within1"]["value"] == 1
    assert m["ability_nll"]["value"] == pytest.approx(math.log(3))
    assert r["card_ece"]["ece"] == 0
    assert r["intent_hazard_calibration"][0]["observed"] == 1
    assert r["intent_hazard_calibration"][1]["at_risk"] == 0
    deltas=compare_paired(rows,rows,np.array([0,0,1,1]),100)
    assert all(d["delta"] == 0 and d["ci95"] == [0.,0.] for d in deltas.values())


def test_cluster_not_row_bootstrap_and_median():
    # Each cluster repeats one value. Whole-cluster two-sample CI spans 0..1.
    values=np.array([0.]*100+[1.]*100); clusters=np.repeat([0,1],100)
    assert _cluster_ci(values,clusters,10000,1) == [0.,1.]
    assert _cluster_ci(values,clusters,1000,1,True) == [0.,1.]
    assert calibration(np.array([.2,.8]),np.array([0.,1.]))["ece"] == pytest.approx(.2)


def test_temperature_dev_only_and_improves_overconfidence():
    logits=torch.tensor([[4.,0.]]*100); masks=torch.ones_like(logits,dtype=torch.bool)
    target=torch.tensor([0]*75+[1]*25)
    t=fit_temperature(logits,masks,target)
    p=torch.softmax(logits/t,-1)[:,0].mean().item()
    assert p == pytest.approx(.75, abs=.005)
    with pytest.raises(ValueError):
        fit_temperature(logits,masks,target,role="eval")


def test_frequency_counts_and_a1_a4_gates():
    from imitation.model.evaluate import frequency_output, offline_gates
    o,y,h=known()
    mask=torch.cat((o['tile_mask'].flatten(1),torch.ones(4,2,dtype=torch.bool)),1)
    counts={'gate':np.ones((33,3)), 'cards':np.ones(360), 'tiles':np.zeros((360,576))}
    baseline=frequency_output(mask,h,torch.zeros(4,dtype=torch.long),torch.ones(4)*.5,counts)
    rows=metric_rows(o,y,h); base_rows=metric_rows(baseline,y,h)
    for key in ('joint_nll','play_wait_nll','card_nll','tile_nll'):
        np.testing.assert_allclose(rows[key],base_rows[key],equal_nan=True)
    gates=offline_gates(rows,base_rows,np.array([0,0,1,1]),[1,2],np.ones(4,bool),base_rows,100)
    assert gates['A1']['pass'] is False
    assert gates['A2']['pass'] is True
    assert gates['A3']['passing_cards']==1
    assert gates['A3']['scoped_cards']==2
    assert gates['A3']['pass'] is False
    assert gates['A4']['pass'] is False


def test_shared_bootstrap_matches_original_each_statistic():
    from imitation.model.evaluate import summary_cluster_cis, _cluster_ci, calibration_ci, MEAN_METRICS
    rng=np.random.default_rng(17)
    clusters=np.repeat(np.arange(7),[4,2,8,2,5,1,4])
    n=len(clusters)
    rows={k:rng.normal(size=n).astype(np.float32) for k in MEAN_METRICS}
    rows['tile_error']=np.sqrt(rng.integers(0,20,n)).astype(np.float32)
    for k in rows: rows[k][rng.random(n)<.3]=np.nan
    for p,y in [('p_act','acted'),('gate_confidence','gate_correct'),('card_confidence','card_correct')]:
        rows[p]=rng.random(n).astype(np.float32);rows[y]=rng.integers(0,2,n).astype(np.float32)
    result=summary_cluster_cis(rows,clusters,333,5)
    for k in (*MEAN_METRICS,'tile_error'):
        np.testing.assert_allclose(result[k],_cluster_ci(rows[k],clusters,333,5,k=='tile_error'),atol=1e-12,rtol=1e-12)
    for k,p,y in [('gate_ece','p_act','acted'),('gate_multiclass_ece','gate_confidence','gate_correct'),('card_ece','card_confidence','card_correct')]:
        np.testing.assert_allclose(result[k],calibration_ci(rows[p],rows[y],clusters,333,5),atol=1e-12,rtol=1e-12)
