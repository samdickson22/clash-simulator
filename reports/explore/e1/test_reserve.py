from types import SimpleNamespace
import numpy as np
from reserve import filter_candidates


def packet(enemy_y=None):
    features=np.zeros((1,32),np.float32)
    if enemy_y is not None:
        features[0,[0,1,3,4,9]]=[4.5/18,enemy_y/32,1,1,1]
    return SimpleNamespace(observation=SimpleNamespace(global_features=np.array([0]*5+[.6]),
        hand_ids=np.array([2,2,2,2]),entity_features=features,entity_mask=np.array([enemy_y is not None]),entity_ids=np.array([2])))
CAT=dict(token_names=['pad','unknown','Knight'],cards={'Knight':dict(cost=3)},bodies={})
A=[4+18*10,13+18*10,2304,2400,2401,2402]


def test_off_identity_and_no_rng():
    assert filter_candidates(A,packet(),CAT,10) is A


def test_low_estimate_allows_all():
    assert filter_candidates(A,packet(),CAT,4.99,enabled=True) is A


def test_floor_keeps_waits_without_threat():
    assert filter_candidates(A,packet(),CAT,5,enabled=True)==A[2:]


def test_defensive_same_lane_in_radius_kept():
    assert filter_candidates(A,packet(11.5),CAT,5,enabled=True)==[A[0]]+A[2:]


def test_enemy_not_across_bridge_no_defensive_exception():
    assert filter_candidates(A,packet(18),CAT,5,enabled=True)==A[2:]


def test_four_elixir_boundary_kept():
    p=packet();p.observation.global_features[5]=.7
    assert filter_candidates(A,p,CAT,5,enabled=True)==A
