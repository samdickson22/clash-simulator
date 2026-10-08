"""Frozen natural-row frequency and upgraded recurrent P16 BC baselines."""
import argparse
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
import json
import multiprocessing
from pathlib import Path
import resource
import time
import numpy as np
from packed_store import PackedStore
from replay_sidecars import HERE, DATA, sha, write


def buckets(ticks, globals):
    # Frozen spec phase slices, including the separate overtime reporting phase.
    phase = np.where(ticks<2400,0,np.where(ticks<3600,1,2))
    elixir = np.clip(np.floor(globals[:,5]*10+1e-5),0,10).astype(np.int64)
    return phase*11+elixir


class Metrics:
    def __init__(self):
        self.sums=defaultdict(float);self.distances=[];self.prob=[];self.truth=[];self.playable=[]

    def add(self, actions, gate, card, tile, label_slot, label_tile, tile_argmax, playable=None):
        # gate columns wait/play/ability. card and tile are conditional.
        play=actions<2304; ability=actions==2305; active=actions!=2304
        targets=np.where(play,1,np.where(ability,2,0))
        n=len(actions);rows=np.arange(n)
        p=np.clip(gate[rows,targets],1e-300,1.)
        joint=-np.log(p)
        pc=np.clip(card[np.arange(play.sum()),label_slot],1e-300,1.)
        pt=np.clip(tile,1e-300,1.)
        joint[play] -= np.log(pc)+np.log(pt)
        p_active=1-gate[:,0]
        playable=np.ones(n,bool) if playable is None else np.asarray(playable,bool)
        binary_nll=-np.log(np.clip(np.where(active,p_active,1-p_active),1e-300,1.))
        brier=np.square(p_active-active)
        self.sums['rows']+=n;self.sums['play_rows']+=play.sum();self.sums['ability_rows']+=ability.sum()
        self.sums['joint_nll_sum']+=joint.sum()
        self.sums['play_wait_nll_sum']+=binary_nll.sum()
        self.sums['play_wait_brier_sum']+=brier.sum()
        self.sums['playable_rows']+=playable.sum()
        self.sums['play_wait_nll_playable_sum']+=binary_nll[playable].sum()
        self.sums['play_wait_brier_playable_sum']+=brier[playable].sum()
        self.sums['card_nll_sum']+=-np.log(pc).sum();self.sums['tile_nll_sum']+=-np.log(pt).sum()
        self.sums['ability_nll_sum']+=-np.log(p[ability]).sum()
        order=np.argsort(-card,axis=1,kind='stable')
        self.sums['card_top1_count']+=(order[:,0]==label_slot).sum()
        self.sums['card_top3_count']+=(order[:,:3]==label_slot[:,None]).any(1).sum()
        distance=np.hypot(tile_argmax%18-label_tile%18,tile_argmax//18-label_tile//18)
        self.distances.append(distance);self.prob.append(p_active);self.truth.append(active);self.playable.append(playable)

    def result(self):
        s=dict(self.sums);n=max(1,s['rows']);p=max(1,s['play_rows']);a=max(1,s['ability_rows'])
        result={**s,'joint_nll':s['joint_nll_sum']/n,'play_wait_nll':s['play_wait_nll_sum']/n,
                'play_wait_brier':s['play_wait_brier_sum']/n,'card_nll':s['card_nll_sum']/p,'tile_nll':s['tile_nll_sum']/p,
                'ability_nll':s['ability_nll_sum']/a,'card_top1':s['card_top1_count']/p,'card_top3':s['card_top3_count']/p,
                'median_tile_error':float(np.median(np.concatenate(self.distances))) if s['play_rows'] else None}
        prediction=np.concatenate(self.prob);truth=np.concatenate(self.truth)
        order=np.argsort(prediction,kind='stable')
        bins=[dict(rows=len(ix),predicted=float(prediction[ix].mean()),observed=float(truth[ix].mean()))
              for ix in np.array_split(order,10) if len(ix)]
        result['hazard_calibration']=bins
        result['ece']=sum(b['rows']*abs(b['predicted']-b['observed']) for b in bins)/n
        # Keep the frozen JSON all-row metrics and DESIGN's playable-row timing
        # metrics explicit, so neither denominator is silently substituted.
        count=s['playable_rows'];use=np.concatenate(self.playable)
        result['play_wait_nll_playable']=s['play_wait_nll_playable_sum']/count if count else None
        result['play_wait_brier_playable']=s['play_wait_brier_playable_sum']/count if count else None
        prediction=prediction[use];truth=truth[use];order=np.argsort(prediction,kind='stable')
        result['hazard_calibration_playable']=[dict(rows=len(ix),predicted=float(prediction[ix].mean()),observed=float(truth[ix].mean()))
            for ix in np.array_split(order,10) if len(ix)]
        result['ece_playable']=sum(b['rows']*abs(b['predicted']-b['observed']) for b in result['hazard_calibration_playable'])/count if count else None
        return result


def fit_frequency(root,out):
    store=PackedStore(root,'train');a=store.arrays
    gate=np.zeros((33,3),np.int64);cards=np.zeros(360,np.int64);tiles=np.zeros((360,576),np.int64)
    for start in range(0,len(store),65536):
        sl=slice(start,start+65536);valid=a['expert_action_supervision_valid'][sl]
        act=a['expert_actions'][sl][valid];hand=a['hand_ids'][sl][valid]
        bucket=buckets(a['submitted_ticks'][sl][valid],a['global_features'][sl][valid])
        kind=np.where(act<2304,1,np.where(act==2305,2,0))
        np.add.at(gate,(bucket,kind),1)
        ix=np.flatnonzero(act<2304);token=hand[ix,act[ix]//576]
        np.add.at(cards,token,1);np.add.at(tiles,(token,act[ix]%576),1)
    np.savez(out/'frequency-counts.npz',gate=gate,cards=cards,tiles=tiles)
    return gate,cards,tiles


def score_frequency(root,out,counts):
    gate_counts,cards,tiles=counts
    for role in ('dev','eval','eval_ood'):
        if (out/f'frequency-{role}.json').exists(): continue
        store=PackedStore(root,role);a=store.arrays;metrics=Metrics();p16=Metrics();per=[]
        for perspective in store.manifest['perspectives']:
            start=perspective['target_start'];end=start+perspective['rows'];local=Metrics()
            for begin in range(start,end,2048):
                ix=np.arange(begin,min(end,begin+2048));ix=ix[a['expert_action_supervision_valid'][ix]]
                if not len(ix): continue
                act=a['expert_actions'][ix];hand=a['hand_ids'][ix,:4]
                mask=np.unpackbits(store.mask_table[a['mask_index'][ix]],axis=1,count=2306).astype(bool)
                placements=mask[:,:2304].reshape(-1,4,576);legal=placements.any(2)
                bucket=buckets(a['submitted_ticks'][ix],a['global_features'][ix])
                gate=gate_counts[bucket].astype(np.float64)
                gate[:,1]*=legal.any(1);gate[:,2]*=mask[:,2305]
                # Empty train bucket backs off to the global train gate counts.
                empty=gate.sum(1)==0
                if empty.any():
                    gate[empty]=gate_counts.sum(0);gate[empty,1]*=legal[empty].any(1);gate[empty,2]*=mask[empty,2305]
                gate/=gate.sum(1,keepdims=True)
                play=act<2304;selected=np.flatnonzero(play);slot=act[play]//576;tile=act[play]%576
                cp=cards[hand[play]].astype(np.float64)*legal[play]
                empty=cp.sum(1)==0
                cp[empty]=legal[play][empty]
                cp/=cp.sum(1,keepdims=True)
                hist=(tiles[hand[selected,slot]]+1).astype(np.float64)*placements[selected,slot]
                tp=hist[np.arange(len(tile)),tile]/hist.sum(1)
                top=hist.argmax(1)
                values=(act,gate,cp,tp,slot,tile,top,legal.any(1))
                metrics.add(*values);local.add(*values)
                if perspective['p16']:p16.add(*values)
            per.append(dict(identity=perspective['identity'],**local.result()))
        write(out/f'frequency-{role}.json',dict(role=role,metrics=metrics.result(),p16=p16.result() if p16.sums else None,
              count_sha256=sha(out/'frequency-counts.npz'),perspectives=len(per)))
        write(out/f'frequency-{role}-perspectives.json',per)
        print(json.dumps(dict(role=role,frequency=metrics.result())),flush=True)


def p16_partition(args):
    root,role,device,partition,partitions=args
    import torch
    from clasher.rl.contract_v5 import ContractV5ObservationBuilder
    from p16_upgrade import upgrade_p16
    from clasher.rl.model import ClasherPolicy,PolicyConfig
    from clasher.rl.human_replay_v5 import load_human_replay_shard_v5
    from clasher.rl.human_replay_bc import _run_streams
    torch.set_num_threads(1)
    path=HERE.parent/'human-prior-p16/checkpoints/human-bc-natural-seed2903.pt'
    builder=ContractV5ObservationBuilder()
    payload,upgrade_receipt=upgrade_p16(torch.load(path,map_location='cpu',weights_only=False),builder)
    model=ClasherPolicy(PolicyConfig.from_dict(payload['model_config']),torch.as_tensor(builder.card_stat_features))
    model.load_state_dict(payload['model_state_dict']);model.to(device).eval()
    plan=json.loads((root/'plan.json').read_text())
    metrics=Metrics();perspectives=[0]
    def episodes():
        for number,unit in enumerate(plan['units']):
            if number%partitions!=partition:continue
            selected=[p for p in unit['perspectives'] if p['role']==role and p['p16']]
            if not selected:continue
            shard=load_human_replay_shard_v5(DATA/'recon/engine-v3'/f"{unit['key']}.npz")
            for p in selected:
                perspectives[0]+=1
                a=p['source_start'];yield p['summary'],shard.arrays(slice(a,a+p['rows']))
    def step(output,batch,labels,weights):
        valid=weights>0
        joint=output.joint_logits.reshape(-1,2306)[valid].double().exp().cpu().numpy()
        act=labels[valid].cpu().numpy();play=act<2304
        mass=joint[:,:2304].reshape(-1,4,576)
        gate=np.stack([joint[:,2304],mass.sum((1,2)),joint[:,2305]],axis=1)
        marginal=mass[play].sum(2);cp=marginal/marginal.sum(1,keepdims=True)
        slot=act[play]//576;tile=act[play]%576;ix=np.arange(play.sum())
        chosen=mass[play][ix,slot];tp=chosen[ix,tile]/chosen.sum(1)
        playable=batch['action_masks'][valid.cpu().numpy(),:2304].any(1)
        metrics.add(act,gate,cp,tp,slot,tile,chosen.argmax(1),playable)
    with torch.no_grad():
        _run_streams(model,episodes(),streams=4,sequences_per_step=4,sequence_length=64,
            device=torch.device(device),step=step,select_play_rows=False,
            weights_for=lambda summary,arrays:arrays['expert_action_supervision_valid'].astype(np.float32))
    return metrics,perspectives[0],sha(path),upgrade_receipt


def p16_bc(root,out,device):
    # Disjoint whole units: no episode is split and no recurrent state is reset
    # at a worker boundary. Merge raw statistics before computing calibration.
    plan=json.loads((root/'plan.json').read_text())
    # S122 takes 78 CPU workers after T2 exits; retain its allocation and keep
    # this host at the shared 80-worker ceiling. No statistical recipe changes.
    workers=2 if device=='cpu' else 1
    for role in ('dev','eval','eval_ood'):
        if (out/f'p16-bc-{role}.json').exists():continue
        expected=sum(p['role']==role and p['p16'] for u in plan['units'] for p in u['perspectives'])
        metrics=Metrics();perspectives=0;checkpoint_sha=None;upgrade_receipt=None
        if expected:
            with ProcessPoolExecutor(workers,mp_context=multiprocessing.get_context('spawn')) as pool:
                for partial,count,digest,upgrade in pool.map(p16_partition,[(root,role,device,k,workers) for k in range(workers)]):
                    for key,value in partial.sums.items():metrics.sums[key]+=value
                    for name in ('distances','prob','truth','playable'):getattr(metrics,name).extend(getattr(partial,name))
                    perspectives+=count
                    if checkpoint_sha is not None:assert checkpoint_sha==digest and upgrade_receipt==upgrade
                    checkpoint_sha=digest;upgrade_receipt=upgrade
        assert perspectives==expected,(role,perspectives,expected)
        write(out/f'p16-bc-{role}.json',dict(role=role,perspectives=perspectives,metrics=metrics.result() if metrics.sums else None,
              checkpoint_sha256=checkpoint_sha,upgrade=upgrade_receipt,device=device,workers=workers))
        print(json.dumps(dict(role=role,p16_perspectives=perspectives)),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['frequency','p16']);p.add_argument('--store',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--device',default='cpu');args=p.parse_args()
    assert json.loads((args.store/'manifest.json').read_text())['passed']
    args.out.mkdir(parents=True,exist_ok=True)
    # Written before fitting or looking at evaluation results. No tuning on eval.
    prereg=dict(recipe=sha(Path(__file__)),store_manifest=sha(args.store/'manifest.json'),
                upgrade_adapter=sha(HERE/'p16_upgrade.py'),
                eval_spec=sha(DATA/'eval/heldout_eval_spec_v1.json'),bucket='floor(own_elixir), phase at 2400/3600',
                frequency='natural train counts; gate legal renormalization; global-train backoff for empty buckets; tile add-one; card uniform legal only if all train counts zero',
                p16='upgraded natural seed2903; whole recurrent perspectives; natural supervised rows',
                timing='play_wait_* uses all supervised rows per frozen JSON; *_playable additionally uses rows with a legal card play per DESIGN')
    path=args.out/'prereg.json'
    if path.exists():assert json.loads(path.read_text())==prereg
    else:write(path,prereg)
    start=time.perf_counter();cpu=time.process_time();children=resource.getrusage(resource.RUSAGE_CHILDREN)
    if args.mode=='frequency':
        if (args.out/'frequency-counts.npz').exists():
            with np.load(args.out/'frequency-counts.npz') as z:counts=tuple(z[n] for n in ('gate','cards','tiles'))
        else:counts=fit_frequency(args.store,args.out)
        score_frequency(args.store,args.out,counts)
    else:p16_bc(args.store,args.out,args.device)
    end_children=resource.getrusage(resource.RUSAGE_CHILDREN)
    write(args.out/f'{args.mode}-complete.json',dict(passed=True,wall_seconds=time.perf_counter()-start,
          cpu_seconds=time.process_time()-cpu+end_children.ru_utime+end_children.ru_stime-children.ru_utime-children.ru_stime))
