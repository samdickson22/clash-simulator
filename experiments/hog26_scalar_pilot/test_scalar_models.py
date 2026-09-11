from dataclasses import fields

import pytest
import torch
from scalar_models import EntityHistoryOutcome, GlobalWDL, PublicSequence


def synthetic(batch=2, time=8, entities=12):
    generator = torch.Generator().manual_seed(932)
    features = torch.rand(batch, time, entities, 32, generator=generator)
    features[..., 2:9] = 0
    features[..., 2] = 1
    features[..., 4] = 1
    ids = torch.full((batch, time, entities), 30, dtype=torch.long)
    for slot, (side, xpos, ypos, token) in enumerate([
        (2, .2, .8, 10), (2, .5, .9, 11), (2, .8, .8, 10),
        (3, .2, .2, 10), (3, .5, .1, 11), (3, .8, .2, 10),
    ]):
        ids[..., slot] = token
        features[..., slot, :9] = 0
        features[..., slot, 0] = xpos
        features[..., slot, 1] = ypos
        features[..., slot, side] = 1
        features[..., slot, 5] = 1
    return PublicSequence(
        entity_ids=ids, entity_features=features,
        entity_mask=torch.ones(batch, time, entities, dtype=torch.bool),
        entity_id_confidence=torch.ones(batch, time, entities),
        entity_feature_confidence=torch.ones_like(features),
        hand_ids=torch.full((batch, time, 4), 20, dtype=torch.long),
        hand_id_confidence=torch.ones(batch, time, 4),
        global_features=torch.rand(batch, time, 18, generator=generator),
        global_feature_confidence=torch.ones(batch, time, 18),
    )


def cloned(x):
    return PublicSequence(**{f.name: getattr(x, f.name).clone() for f in fields(x)})


def model():
    torch.manual_seed(1279501)
    return EntityHistoryOutcome(498, princess_tower_token=10, king_tower_token=11)


def test_future_causality():
    x = synthetic()
    changed = cloned(x)
    changed.global_features[:, 4:] = 1 - changed.global_features[:, 4:]
    changed.entity_features[:, 4:, 6:, :2] *= .2
    net = model()
    original = net(x, torch.tensor([8, 8]))
    future = net(changed, torch.tensor([8, 8]))
    for a, b in zip(original[:2], future[:2]):
        torch.testing.assert_close(a[:, :4], b[:, :4], rtol=0, atol=0)
    assert not torch.equal(original[0][:, 4:], future[0][:, 4:])


def test_entity_permutation():
    x = synthetic()
    values = {}
    for field in fields(x):
        value = getattr(x, field.name)
        values[field.name] = value.flip(2) if field.name.startswith('entity_') else value
    net = model()
    a, b = net(x, torch.tensor([8, 8])), net(PublicSequence(**values), torch.tensor([8, 8]))
    for left, right in zip(a, b):
        torch.testing.assert_close(left, right, rtol=1e-5, atol=1e-7)


def test_padding_values_and_lengths_do_not_change_valid_output():
    x = synthetic()
    changed = cloned(x)
    for field in fields(changed):
        value = getattr(changed, field.name)
        value[1, 3:] = 999 if value.dtype == torch.long else 0
    lengths = torch.tensor([8, 3])
    net = model()
    a, b = net(x, lengths), net(changed, lengths)
    for left, right in zip(a, b):
        torch.testing.assert_close(left, right, rtol=0, atol=0)
    assert a[0][1, 3:].count_nonzero() == 0
    assert a[1][1, 3:].count_nonzero() == 0
    separate = PublicSequence(**{f.name: getattr(x, f.name)[1:2, :3] for f in fields(x)})
    alone = net(separate, torch.tensor([3]))
    torch.testing.assert_close(a[0][1:2, :3], alone[0], rtol=1e-5, atol=1e-7)
    torch.testing.assert_close(a[2][:, 1:2], alone[2], rtol=1e-5, atol=1e-7)


def test_episode_reset_and_all_parameters_receive_gradients():
    net = model()
    x = synthetic()
    a = net(x, torch.tensor([8, 8]))
    net(synthetic(time=3), torch.tensor([3, 3]))
    b = net(x, torch.tensor([8, 8]))
    for left, right in zip(a, b):
        torch.testing.assert_close(left, right, rtol=0, atol=0)
    (a[0].square().mean() + (a[1] - .7).abs().mean()).backward()
    for name, parameter in net.named_parameters():
        assert parameter.grad is not None, name
        assert torch.isfinite(parameter.grad).all(), name
        assert parameter.grad.abs().sum() > 0, name


def test_missing_features_and_entities_cannot_leak():
    net = model()
    x = synthetic()
    x.entity_mask[..., -1] = False
    x.entity_feature_confidence[..., 6:, 30] = 0
    x.global_feature_confidence[..., 5] = 0
    x.hand_id_confidence[..., 0] = 0
    changed = cloned(x)
    changed.entity_ids[..., -1] = 999999
    changed.entity_features[..., -1, :] = float('nan')
    changed.entity_features[..., 6:, 30] = float('nan')
    changed.global_features[..., 5] = float('nan')
    changed.hand_ids[..., 0] = 999999
    for left, right in zip(net(x, torch.tensor([8, 8])), net(changed, torch.tensor([8, 8]))):
        torch.testing.assert_close(left, right, rtol=0, atol=0)


def test_tower_geometry_retains_missing_slot_and_rejects_duplicate():
    net = model()
    x = synthetic(batch=1, time=1)
    args = [x.entity_ids, x.entity_features, x.entity_feature_confidence,
            x.entity_id_confidence, x.entity_mask]
    geometry = net.tower_geometry(*args)
    torch.testing.assert_close(geometry[0, 0, 1, :2], torch.tensor([.3, .1]))
    assert geometry[0, 0, 1, 3] == 1
    x.entity_mask[..., 0] = False
    missing = net.tower_geometry(*args)
    assert missing[..., :4].count_nonzero() == 0
    assert missing[0, 0, 1, 11] == 1  # right princess remains in right slot
    x.entity_mask[..., 0] = True
    x.entity_ids[..., 6] = 10
    x.entity_features[..., 6, :] = x.entity_features[..., 0, :]
    with pytest.raises(ValueError, match='multiple visible towers'):
        net.tower_geometry(*args)


def test_global_contract_and_missing_confidence():
    net = GlobalWDL()
    values = torch.randn(2, 18)
    confidence = torch.ones_like(values)
    confidence[:, 5] = 0
    original = net(values, confidence)
    values[:, 5] = float('nan')
    torch.testing.assert_close(original, net(values, confidence), rtol=0, atol=0)
    assert original.shape == (2, 3)
    with pytest.raises(ValueError):
        net(values[:, :17], confidence[:, :17])


def test_output_bounds_and_parameter_counts():
    x = synthetic()
    net = model()
    logits, margin, hidden = net(x, torch.tensor([8, 8]))
    assert logits.shape == (2, 8, 3)
    assert margin.shape == (2, 8)
    assert hidden.shape == (1, 2, 64)
    assert ((margin >= -1) & (margin <= 1)).all()
    assert sum(p.numel() for p in GlobalWDL().parameters()) == 2339
    assert sum(p.numel() for p in net.parameters()) == 116900
