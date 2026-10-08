"""Exact full-source train frequency counts, dev-only baseline, T11 release."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import json
import multiprocessing as mp
from pathlib import Path
import socket
import sys
import time
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
IM=ROOT/'reports/strategy_council_20260928/imitation'
sys.path.insert(0,str(IM))
from replay_sidecars import sha,write
from packed_store import PackedStore
from baselines import buckets,Metrics
# Training/evaluation dependencies live in T11's owned source snapshot.
sys.path.insert(0,'/mpac/sdicks02/jobs/clasher/t11-20261008-v1/source')
from imitation.t11.frequency import frequency_rows


def fit_part(units):
    gate=np.zeros((33,3),np.int64); cards=np.zeros(360,np.int64); tiles=np.zeros((360,576),np.int64)
    rows=0
    for unit in units:
        if not any(p['role']=='train' for p in unit['perspectives']): continue
        assert sha(unit['raw'])==unit['raw_sha256']
        with np.load(unit['raw'],allow_pickle=False) as z:
            actions=z['expert_actions']; hand=z['hand_ids']; valid=z['expert_action_supervision_valid']
            tick=z['submitted_ticks']; glob=z['global_features']
        for p in unit['perspectives']:
            if p['role']!='train': continue
            start=p['source_start']; end=start+p['source_rows']; ix=np.arange(start,end); ix=ix[valid[ix]]
            act=actions[ix]; h=hand[ix]; b=buckets(tick[ix],glob[ix]); kind=np.where(act<2304,1,np.where(act==2305,2,0))
            np.add.at(gate,(b,kind),1)
            play=np.flatnonzero(act<2304); token=h[play,act[play]//576]
            np.add.at(cards,token,1);np.add.at(tiles,(token,act[play]%576),1);rows+=len(ix)
    return gate,cards,tiles,rows


def score_dev(root,out,counts):
    store=PackedStore(root,'dev'); a=store.arrays
    store.mask_bitorder='big';a['mask_table']=store.mask_table
    metrics=Metrics(); corpus={c:{n:[0.,0] for n in ('joint_nll','play_wait_nll','card_nll','tile_nll')} for c in ('c56','s122')}
    for start in range(0,len(store),2048):
        ix=np.arange(start,min(len(store),start+2048));ix=ix[a['expert_action_supervision_valid'][ix]]
        if not len(ix):continue
        act=a['expert_actions'][ix];hand=a['hand_ids'][ix,:4]
        mask=np.unpackbits(store.mask_table[a['mask_index'][ix]],axis=1,count=2306).astype(bool)
        placements=mask[:,:2304].reshape(-1,4,576);legal=placements.any(2)
        bucket=buckets(a['submitted_ticks'][ix],a['global_features'][ix]);gate=counts['gate'][bucket].astype(np.float64)
        gate[:,1]*=legal.any(1);gate[:,2]*=mask[:,2305];empty=gate.sum(1)==0
        if empty.any():
            gate[empty]=counts['gate'].sum(0);gate[empty,1]*=legal[empty].any(1);gate[empty,2]*=mask[empty,2305]
        gate/=gate.sum(1,keepdims=True)
        play=act<2304;selected=np.flatnonzero(play);slot=act[play]//576;tile=act[play]%576
        cp=counts['cards'][hand[play]].astype(np.float64)*legal[play];empty=cp.sum(1)==0;cp[empty]=legal[play][empty];cp/=cp.sum(1,keepdims=True)
        hist=(counts['tiles'][hand[selected,slot]]+1).astype(np.float64)*placements[selected,slot]
        tp=hist[np.arange(len(tile)),tile]/hist.sum(1);top=hist.argmax(1)
        metrics.add(act,gate,cp,tp,slot,tile,top,legal.any(1))
        values=frequency_rows(store,ix,counts)
        for c in corpus:
            use=a['corpus_s122'][ix] == (c=='s122')
            for n,v in values.items():
                valid=use & np.isfinite(v);corpus[c][n][0]+=float(v[valid].sum());corpus[c][n][1]+=int(valid.sum())
    result=dict(role='dev',full_natural_rows=True,metrics=metrics.result(),
                corpus={c:{n:dict(sum=v[0],rows=v[1],mean=v[0]/v[1] if v[1] else None) for n,v in m.items()} for c,m in corpus.items()},
                count_sha256=sha(out/'frequency-counts.npz'),store_sha256=sha(root/'manifest.json'),heldout_scored=False)
    write(out/'frequency-dev.json',result)
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--store',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--workers',type=int,default=8);a=p.parse_args()
    assert socket.gethostname()=='127x01' and 1<=a.workers<=12
    a.out.mkdir(parents=True,exist_ok=True);start=time.monotonic()
    manifest=json.loads((a.store/'manifest.json').read_text());plan=json.loads((a.store/'plan.json').read_text())
    assert manifest['passed'] and manifest['production'] and sha(a.store/'plan.json')==manifest['plan_sha256']
    count_path=a.out/'frequency-counts.npz';fit_path=a.out/'frequency-fit.json'
    if not fit_path.exists():
        assert not count_path.exists(), 'preserve unexpected partial counts; use fresh out'
        with ProcessPoolExecutor(a.workers,mp_context=mp.get_context('fork')) as pool:
            parts=list(pool.map(fit_part,[plan['units'][i::a.workers] for i in range(a.workers)]))
        counts={n:sum(part[j] for part in parts) for j,n in enumerate(('gate','cards','tiles'))}
        np.savez(count_path,**counts)
        write(fit_path,dict(count_sha256=sha(count_path),full_unthinned_train_rows=sum(x[3] for x in parts),
                           eligibility='v2 eligible train perspectives; all supervised source rows before store wait thinning; unit weight',
                           store_sha256=sha(a.store/'manifest.json'),source_sha256=sha(__file__)))
    fit=json.loads(fit_path.read_text());assert fit['count_sha256']==sha(count_path) and fit['store_sha256']==sha(a.store/'manifest.json')
    counts=dict(np.load(count_path,allow_pickle=False));result=score_dev(a.store,a.out,counts)
    receipt=dict(schema='clasher.imitation.t11-store-pass.v1',passed=True,store_manifest_sha256=sha(a.store/'manifest.json'),
                 role_file_sha256=manifest['role_file_sha256'],roles=manifest['roles'],role_manifests=manifest['role_manifests'],
                 plan_sha256=manifest['plan_sha256'],eval_spec_sha256=manifest['eval_spec_sha256'],inputs=manifest['inputs'],
                 roundtrip_perspectives=manifest['roundtrip_perspectives'],roundtrip_exact=manifest['roundtrip_exact'],
                 counts_equal_eligible_roles=True,raw_role_counts=manifest['raw_role_counts'],excluded_3m_by_role=manifest['excluded_3m_by_role'],
                 leak_check=manifest['leak_check'],thinning=manifest['thinning'],
                 frequency_counts_sha256=sha(count_path),frequency_dev_sha256=sha(a.out/'frequency-dev.json'),
                 baseline_fit=fit,heldout_scored=False,wall_seconds=time.monotonic()-start)
    write(IM/'data/receipts/T11-STORE-PASS.json',receipt)
    print(json.dumps(receipt),flush=True)


if __name__=='__main__':main()
