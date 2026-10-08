"""Preserve the specialist's stored descriptors during its prescribed v5 upgrade.

The checkpoint was trained on daa58b28 gamedata, the corpus on 3d99987c. The
checkpoint's descriptor buffers are part of its learned policy inputs. Rebuild
only the builder's old-vocabulary rows from those buffers before invoking the
unchanged contract upgrader; no learned tensor or frozen runtime is edited.
"""
import copy
import numpy as np
import torch
from clasher.rl.contract_v5 import upgrade_policy_payload_to_v5


def upgrade_p16(payload, builder):
    compatible=copy.copy(builder)
    compatible.card_stat_features=np.array(builder.card_stat_features,copy=True)
    positions={n:i for i,n in enumerate(builder.token_names)}
    rows=np.array([positions[n] for n in payload['token_names']])
    state=payload['model_state_dict']
    base=state['actor_encoder.card_stat_features']
    semantic=state['actor_encoder.semantic_card_features']
    assert torch.equal(base,state['critic_encoder.card_stat_features'])
    assert torch.equal(semantic,state['critic_encoder.semantic_card_features'])
    source=torch.cat([base,semantic],dim=1).cpu().numpy()
    original=compatible.card_stat_features[rows,:source.shape[1]].copy()
    changed=np.any(original!=source,axis=1)
    compatible.card_stat_features[rows,:source.shape[1]]=source
    upgraded=upgrade_policy_payload_to_v5(payload,compatible)
    new=upgraded['model_state_dict']
    for key,value in state.items():
        target=new[key]
        if value.shape==target.shape:
            assert torch.equal(value,target),(key,'checkpoint changed')
        elif target.shape[0]==len(builder.token_names) and value.shape[0]==len(rows):
            assert torch.equal(value,target[rows]),(key,'vocabulary rows changed')
        else:raise AssertionError((key,value.shape,target.shape))
    receipt=dict(source_gamedata_sha256=payload.get('gamedata_sha256'),
                 preserved_source_descriptors=True,learned_tensors_unchanged=True,
                 changed_descriptor_tokens=[n for n,different in zip(payload['token_names'],changed) if different],
                 changed_descriptor_values=int((original!=source).sum()),
                 rule='source vocabulary descriptor rows copied from checkpoint into builder copy; unchanged contract_v5 upgrader invoked')
    return upgraded,receipt
