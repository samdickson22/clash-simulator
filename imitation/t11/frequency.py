"""Output-identical compatibility for duplicate, illegal padding hand slots.

T5's baseline rejects ANY duplicate hand token, including two masked pad slots.
Give only those zero-mass entries unique temporary token IDs in a private
baseline view; every probability and source/model tensor remains unchanged.
Non-padding or legally selectable duplicate tokens still fail closed.
"""
from types import SimpleNamespace
import numpy as np
from imitation.t5.baseline import frequency_rows as qualified_frequency_rows


def frequency_rows(store,indices,counts):
    ix=np.asarray(indices);a=store.arrays;hand=np.asarray(a['hand_ids'][ix,:4])
    play=a['expert_action_supervision_valid'][ix] & (a['expert_actions'][ix]<2304)
    duplicate=(np.diff(np.sort(hand,axis=1),axis=1)==0).any(1)&play
    if not duplicate.any():return qualified_frequency_rows(store,ix,counts)
    if 'action_mask' in a:mask=a['action_mask'][ix].astype(bool)
    else:mask=np.unpackbits(a['mask_table'][a['mask_index'][ix]],axis=1,bitorder=getattr(store,'mask_bitorder','little'))[:,:2306].astype(bool)
    legal=mask[:,:2304].reshape(-1,4,576).any(2);repaired=hand.copy()
    for row in np.flatnonzero(duplicate):
        tokens,number=np.unique(hand[row],return_counts=True)
        assert tokens[number>1].tolist()==[0], 'non-padding duplicate needs separate qualification'
        pads=np.flatnonzero(hand[row]==0);assert not legal[row,pads].any()
        action=int(a['expert_actions'][ix[row]]);assert hand[row,action//576]!=0
        for slot in pads[1:]:
            replacement=next(t for t in range(1,len(counts['cards'])) if t not in repaired[row])
            repaired[row,slot]=replacement
    class HandView:
        def __getitem__(self,key):
            rows,columns=key
            assert np.array_equal(rows,ix) and columns==slice(None,4)
            return repaired
    view=SimpleNamespace(arrays={**a,'hand_ids':HandView()},mask_bitorder=getattr(store,'mask_bitorder','little'))
    return qualified_frequency_rows(view,ix,counts)
