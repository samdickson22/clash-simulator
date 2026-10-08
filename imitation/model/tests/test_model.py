import copy
import math
import numpy as np
import pytest
import torch
from imitation.model.features import build_row, collate_features, ENTITY_COLUMNS
from imitation.model.inference import Policy, load_policy, single_features
from imitation.model.losses import hazard_loss, intent_target, loss_parts, total_loss
from imitation.model.network import masked_log_softmax
from imitation.model.synthetic import batch, model, packet
from imitation.model.train import denominators, optimizer_step


def setup_module():
    torch.set_num_threads(1)


def test_masks_empty_support_and_script(tmp_path):
    m = model().eval(); b, y = batch(2)
    b["action_mask"][0] = False; b["action_mask"][0, 2304] = True
    b["action_mask"][1, 576:1152] = False
    lp = m.log_policy(b)
    assert lp["gate"][0].exp().tolist() == [1., 0., 0.]
    assert lp["card"][0].exp().sum() == 0
    assert lp["tile"][0].exp().sum() == 0
    assert lp["card"][1, 1].exp() == 0
    assert lp["tile"][1, 1].exp().sum() == 0
    script = Policy(m).export(tmp_path/"policy.ts")
    reloaded = torch.jit.load(str(tmp_path/"policy.ts"))
    api = load_policy(tmp_path/"policy.ts")
    for key, value in lp.items():
        torch.testing.assert_close(value, script.log_policy(b)[key])
        torch.testing.assert_close(value, reloaded.log_policy(b)[key])
        torch.testing.assert_close(value, api.model.log_policy(b)[key])


def test_hand_equivariance_entities_and_padding():
    torch.manual_seed(1); m = model().eval(); b, y = batch(1, 10)
    before = m.log_policy(b)
    p = torch.tensor([2, 0, 3, 1]); z = {k: v.clone() for k, v in b.items()}
    for key in ("ids", "types", "numeric", "valid"):
        z[key][:, :4] = b[key][:, p]
    z["action_mask"][:, :2304] = b["action_mask"][:, :2304].view(1, 4, 576)[:, p].flatten(1)
    after = m.log_policy(z)
    torch.testing.assert_close(before["gate"], after["gate"], atol=1e-6, rtol=1e-6)
    torch.testing.assert_close(before["card"][:, p], after["card"], atol=2e-6, rtol=1e-6)
    torch.testing.assert_close(before["tile"][:, p], after["tile"], atol=2e-6, rtol=1e-6)
    idx = torch.where(b["valid"][0] & (b["types"][0] == 0))[0]
    for key in ("ids", "types", "numeric", "valid"):
        z[key] = b[key].clone(); z[key][:, idx] = b[key][:, idx.flip(0)]
    z["action_mask"] = b["action_mask"]
    # Arbitrary padded numeric content cannot change any active output.
    z["numeric"][~z["valid"]] = 1e3
    after = m.log_policy(z)
    for key in before:
        torch.testing.assert_close(before[key], after[key], atol=2e-6, rtol=1e-6)


def test_hidden_poisoning_and_missing_d1():
    p, d = packet(3); full = np.zeros((3, 32), np.float32)
    full[:, ENTITY_COLUMNS] = p["entity_features"]; p["entity_features"] = full
    costs = np.full(360, 3.)
    first = build_row(p, d, costs)
    hidden = sorted(set(range(32))-set(ENTITY_COLUMNS))
    p["entity_features"][:, hidden] = np.nan
    p["global_features"][[6, 7, 16]] = np.nan
    d["audit_hidden_hand"] = [9999]*8
    second = build_row(p, d, costs)
    for key in first:
        np.testing.assert_array_equal(first[key], second[key])
    del d["opp_elixir"]
    with pytest.raises(KeyError):
        build_row(p, d, costs)


def test_full_packet_entity_cap_preserves_all_entities():
    costs = np.full(360, 3.)
    p, d = packet(128)
    row = build_row(p, d, costs)
    assert (row["types"] == 0).sum() == 128
    b = collate_features([row])
    assert b["ids"].shape[1] == 191
    with torch.inference_mode():
        values = model().eval().log_policy(b)
    assert all(torch.isfinite(v).all() for v in values.values())
    p, d = packet(129)
    with pytest.raises(ValueError, match="128 visible"):
        build_row(p, d, costs)


def test_unpadded_single_inference_matches_training_bucket():
    m = model().eval()
    p, d = packet(78)
    padded = collate_features([build_row(p, d, m.costs.numpy())])
    single = single_features(p, d, m.costs.numpy())
    assert single["ids"].shape[1] < padded["ids"].shape[1]
    with torch.inference_mode():
        a, b = m.log_policy(single), m.log_policy(padded)
    for key in a:
        torch.testing.assert_close(a[key], b[key], atol=2e-6, rtol=1e-6)


def test_handbuilt_loss_censor_and_forced_wait():
    n = 3
    o = {"gate": torch.zeros(n, 3), "card": torch.zeros(n, 4), "tile": torch.zeros(n, 1, 576),
         "gate_mask": torch.tensor([[1,1,0],[1,1,1],[1,0,0]], dtype=torch.bool),
         "card_mask": torch.tensor([[1,1,0,0],[1,0,0,0],[0,0,0,0]], dtype=torch.bool),
         "tile_mask": torch.zeros(n, 1, 576, dtype=torch.bool),
         "intent_card": torch.zeros(n, 8), "hazard": torch.zeros(n, 13)}
    o["tile_mask"][:2, :, :2] = True
    y = {"action": torch.tensor([0,2304,2304]), "supervised": torch.ones(n,dtype=torch.bool),
         "weight": torch.tensor([2.,4.,99.]), "intent_card": torch.tensor([0,-1,-1]),
         "intent_bin": torch.tensor([1,2,0]), "intent_observed": torch.tensor([True,False,False]),
         "intent_valid": torch.ones(n,dtype=torch.bool)}
    parts = loss_parts(o, y); terms = total_loss(parts)
    assert terms["gate"].item() == pytest.approx((2*math.log(2)+4*math.log(3))/6)
    assert terms["card"].item() == pytest.approx(math.log(2))
    assert terms["tile"].item() == pytest.approx(math.log(2))
    assert terms["hazard"].item() == pytest.approx(12*math.log(2)/105)
    assert terms["intent_card"].item() == pytest.approx(math.log(8))
    assert intent_target(.01, False) == (0, False)
    assert intent_target(11, False) == (12, False)
    assert intent_target(11, True) == (12, True)


def test_teacher_matches_all_and_accumulation_denominators():
    m = model().eval(); b, y = batch(3); teacher = (y["action"]//576).clamp(0, 3)
    full = m(b, torch.empty(0,dtype=torch.long)); forced = m(b, teacher)
    torch.testing.assert_close(forced["tile"][:, 0], full["tile"][torch.arange(3), teacher])
    den = denominators(b,y)
    all_loss = total_loss(loss_parts(full, y))["loss"]
    accumulated = 0
    for i in range(3):
        oo = {k:v[i:i+1] for k,v in full.items()}; yy = {k:v[i:i+1] for k,v in y.items()}
        accumulated += total_loss(loss_parts(oo,yy),den)["loss"]
    torch.testing.assert_close(all_loss, accumulated)


def test_proposal_legality_and_no_play():
    policy = Policy(model()); p,d = packet()
    proposals = policy.propose(p,d)
    assert len(proposals) == 8
    assert all(p["action_mask"][r["action"]] for r in proposals)
    assert [r["probability"] for r in proposals] == sorted([r["probability"] for r in proposals], reverse=True)
    p["action_mask"][:2304] = False
    assert policy.propose(p,d) == []
