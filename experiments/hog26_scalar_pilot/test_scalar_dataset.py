from dataclasses import fields

import numpy as np
import pytest
import torch
from scalar_dataset import PUBLIC_FIELDS, Game, load_complete_pilot, public_batch
from scalar_models import PublicSequence


def game(length=3):
    shapes={'entity_ids':(length,4),'entity_features':(length,4,32),'entity_mask':(length,4),
            'entity_id_confidence':(length,4),'entity_feature_confidence':(length,4,32),
            'hand_ids':(length,4),'hand_id_confidence':(length,4),
            'global_features':(length,18),'global_feature_confidence':(length,18)}
    public={key:np.zeros(shape,dtype=np.int64 if key.endswith('_ids') else np.bool_ if key=='entity_mask' else np.float32) for key,shape in shapes.items()}
    return Game(public,2,.7,'family-007','secret-style',1,'cluster-secret','path-secret','digest-secret')


def test_refuses_partial_before_any_npz_access(tmp_path, monkeypatch):
    def forbidden(*a,**k):raise AssertionError('partial corpus access')
    monkeypatch.setattr(np,'load',forbidden)
    with pytest.raises(ValueError,match='incomplete'):
        load_complete_pilot(tmp_path,plan_path=tmp_path/'missing',preflight_path=tmp_path/'missing')


def test_public_batch_whitelist_and_padding_cannot_encode_labels_metadata():
    a,b=game(2),game(3)
    assert tuple(f.name for f in fields(PublicSequence))==PUBLIC_FIELDS
    x,lengths=public_batch([a,b])
    assert lengths.tolist()==[2,3]
    assert x.entity_features.shape==(2,3,1,32)
    assert not x.entity_features[0,2].any()
    altered=Game(a.public,0,-.9,'family-000','different',0,'other','other','other')
    y,_=public_batch([altered,b])
    for key in PUBLIC_FIELDS:assert torch.equal(getattr(x,key),getattr(y,key))


def test_cropping_masked_storage_preserves_model_outputs():
    from scalar_models import EntityHistoryOutcome
    g=game(3)
    g.public['entity_mask'][:,2]=True
    g.public['entity_ids'][:,2]=2
    g.public['entity_id_confidence'][:,2]=1
    g.public['entity_features'][:,2,2]=1
    g.public['entity_features'][:,2,4]=1
    g.public['entity_feature_confidence'][:,2,:]=1
    cropped,lengths=public_batch([g])
    full=PublicSequence(**{k:torch.from_numpy(v)[None] for k,v in g.public.items()})
    assert cropped.entity_ids.shape[-1]==3
    torch.manual_seed(7)
    model=EntityHistoryOutcome(10,princess_tower_token=3,king_tower_token=4).eval()
    with torch.no_grad():
        a,b=model(cropped,lengths),model(full,lengths)
    for x,y in zip(a,b):torch.testing.assert_close(x,y,rtol=1e-6,atol=1e-6)
