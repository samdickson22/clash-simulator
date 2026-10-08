"""Dev-only byte equality proof for masked-padding compatibility."""
import json
from pathlib import Path
import socket
import sys
from types import SimpleNamespace
import numpy as np

ROOT=Path('/mpac/sdicks02/repos/clasher')
sys.path.insert(0,str(ROOT/'reports/strategy_council_20260928/imitation'))
from packed_store import PackedStore
from baselines import buckets
from imitation.t5.guards import sha
from imitation.t5.baseline import frequency_rows as original
from .frequency import frequency_rows
from . import frequency


def main():
    assert socket.gethostname()=='127x01'
    data=ROOT/'reports/strategy_council_20260928/imitation/data'
    store=PackedStore(data/'v2-store-v1','dev');a=store.arrays;a['mask_table']=store.mask_table;store.mask_bitorder='big'
    counts=dict(np.load(data/'t11-baselines-v1/frequency-counts.npz',allow_pickle=False))
    ix=np.r_[np.arange(128),8762043,11393318];before=a['hand_ids'][ix].tobytes()
    got=frequency_rows(store,ix,counts)
    act=a['expert_actions'][ix];valid=a['expert_action_supervision_valid'][ix];hand=a['hand_ids'][ix,:4]
    mask=np.unpackbits(store.mask_table[a['mask_index'][ix]],axis=1,count=2306).astype(bool)
    placement=mask[:,:2304].reshape(-1,4,576);legal=placement.any(2)
    bucket=buckets(a['submitted_ticks'][ix],a['global_features'][ix]);gate=counts['gate'][bucket].astype(np.float64)
    gate[:,1]*=legal.any(1);gate[:,2]*=mask[:,2305];empty=gate.sum(1)==0
    gate[empty]=counts['gate'].sum(0);gate[empty,1]*=legal[empty].any(1);gate[empty,2]*=mask[empty,2305];gate/=gate.sum(1,keepdims=True)
    row=np.flatnonzero(valid&(act<2304));slot=act[row]//576;tile=act[row]%576
    cp=counts['cards'][hand[row]].astype(np.float64)*legal[row];empty=cp.sum(1)==0;cp[empty]=legal[row][empty];cp/=cp.sum(1,keepdims=True)
    hist=(counts['tiles'][hand[row,slot]]+1).astype(np.float64)*placement[row,slot]
    card=-np.log(cp[np.arange(len(row)),slot].clip(1e-300,1));tile_nll=-np.log((hist[np.arange(len(row)),tile]/hist.sum(1)).clip(1e-300,1))
    kind=np.where(act==2304,0,np.where(act==2305,2,1));joint=-np.log(gate[np.arange(len(ix)),kind].clip(1e-300,1));joint[row]+=card+tile_nll
    expected={'joint_nll':np.where(valid,joint,np.nan),'play_wait_nll':np.where(valid&legal.any(1),-np.log(np.where(act==2304,gate[:,0],gate[:,1:].sum(1)).clip(1e-300,1)),np.nan),
              'card_nll':np.full(len(ix),np.nan),'tile_nll':np.full(len(ix),np.nan)}
    expected['card_nll'][row]=card;expected['tile_nll'][row]=tile_nll
    for k in got:np.testing.assert_array_equal(got[k],expected[k])
    regular=original(store,ix[:128],counts);wrapped=frequency_rows(store,ix[:128],counts)
    for k in regular:np.testing.assert_array_equal(regular[k],wrapped[k])
    assert a['hand_ids'][ix].tobytes()==before
    private={n:np.asarray(a[n][ix]).copy() for n in ['expert_actions','expert_action_supervision_valid','hand_ids','submitted_ticks','global_features']}
    private['action_mask']=mask.copy();private['hand_ids'][-1,1]=private['hand_ids'][-1,0]
    try:frequency_rows(SimpleNamespace(arrays=private),np.arange(len(ix)),counts)
    except AssertionError:negative=True
    else:raise AssertionError('nonpadding duplicate was accepted')
    result=dict(passed=True,heldout_scored=False,real_fitting=False,rows=len(ix),affected_dev_rows=[8762043,11393318],
                all_four_statistics_byte_equal_to_t3=True,ordinary_rows_equal_unchanged_t5=True,source_bytes_unchanged=True,
                nonpadding_duplicates_rejected=negative,adapter_sha256=sha(frequency.__file__),validator_sha256=sha(__file__),
                frequency_counts_sha256=sha(data/'t11-baselines-v1/frequency-counts.npz'))
    path=ROOT/'imitation/t11/receipts/frequency-padding-validation.json';path.write_text(json.dumps(result,indent=2)+'\n');print(path.read_text())


if __name__=='__main__':main()
