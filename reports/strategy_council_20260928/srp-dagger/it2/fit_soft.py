"""Candidate-conditioned soft CE and full-distribution anchored recurrent BC."""
import json,time,sys
from pathlib import Path
from dataclasses import replace
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import kit,fit as base
from kit import np,torch
from clasher.rl.imitation import load_corpus,split_indices,sequence_chunks,_sequence_batch_inputs,_council_imitation_state,_checkpoint_payload,_imitation_evaluation_batches
from clasher.rl.tbptt import ImitationStateCache
sys.path.insert(0,str(Path(__file__).resolve().parent))
from collect import config,note,OUT

def targets(arrays,train):
    n=len(arrays['episode_ids']); ids=np.zeros((n,24),np.int64); scores=np.full((n,24),-np.inf); counts=np.zeros(n,int); advantages=np.zeros(n)
    offset=0
    for path in sorted((OUT/'games').glob('game-*.npz')):
        with np.load(path) as d:
            for row in np.flatnonzero(d['expert_action_supervision_valid']):
                actions=d['root_candidate_ids'][d['root_candidate_rows']==row]; values=d['root_candidate_values'][d['root_candidate_rows']==row]
                assert len(actions)<=24 and len(actions)==len(set(actions))
                assert np.isfinite(values).all() and d['action_masks'][row,actions].all()
                student=int(d['student_actions'][row]); assert np.count_nonzero(actions==student)==1
                idx=offset+row;ids[idx,:len(actions)]=actions;scores[idx,:len(actions)]=values;counts[idx]=len(actions)
                advantages[idx]=values.max()-values[actions==student][0]
            offset+=len(d['episode_ids'])
    queried=arrays['expert_action_supervision_valid'];keep=queried&(advantages>0.05)
    train_keep=train[keep[train]];assert len(train_keep)>0
    def probs(rows,tau):
        s=scores[rows];z=(s-s.max(-1,keepdims=True))/tau
        p=np.exp(z);p/=p.sum(-1,keepdims=True)
        h=-(p*np.log(np.maximum(p,1e-300))).sum(-1)
        return p,h
    lo,hi=1e-10,10.
    assert np.median(probs(train_keep,lo)[1])<=1<=np.median(probs(train_keep,hi)[1])
    for _ in range(70):
        mid=np.sqrt(lo*hi)
        if np.median(probs(train_keep,mid)[1])<1:lo=mid
        else:hi=mid
    tau=np.sqrt(lo*hi); p=np.zeros_like(scores);p[queried]=probs(np.flatnonzero(queried),tau)[0]
    report=dict(tau=float(tau),margin=0.05,queried=int(queried.sum()),kept=int(keep.sum()),kept_fraction=float(keep.sum()/queried.sum()),train_kept=len(train_keep),median_entropy_training_kept=float(np.median(probs(train_keep,tau)[1])),median_entropy_all_queried=float(np.median(probs(np.flatnonzero(queried),tau)[1])),median_entropy_all_kept=float(np.median(probs(np.flatnonzero(keep),tau)[1])),advantage_quantiles=np.quantile(advantages[queried],[0,.25,.5,.75,.9,.99,1]).tolist(),score_quantiles=np.quantile(scores[np.isfinite(scores)],[0,.01,.5,.99,1]).tolist(),candidate_count_quantiles=np.quantile(counts[queried],[0,.5,1]).tolist(),tau_fit_split='training kept decisions only')
    kit.write_json(OUT/'targets.json',report);kit.log(report)
    return ids,counts,p.astype(np.float32),keep

def candidate_ce(logits,ids,counts,p):
    gathered=logits.gather(-1,ids)
    valid=torch.arange(ids.shape[-1],device=logits.device)<counts[...,None]
    lp=gathered.masked_fill(~valid,-1e9).log_softmax(-1)
    return -(p*lp).sum(-1)

@torch.no_grad()
def measure(model,a,rows,tensors,anchor=None):
    ids,counts,p,keep=tensors; total=0;ce=kl=0.; kept=0
    for selected,_,output in _imitation_evaluation_batches(model,a,rows[a['expert_action_supervision_valid'][rows]],batch_size=128,device=kit.DEVICE,trim_entity_padding=True):
        logits=output.joint_logits[:,0]; idx=torch.as_tensor(selected);chosen=keep[idx]
        if chosen.any():ce+=float(candidate_ce(logits[chosen],ids[idx][chosen],counts[idx][chosen],p[idx][chosen]).sum());kept+=int(chosen.sum())
        if anchor is not None:kl+=float(base.student_kl(logits,anchor[idx]).sum())
        total+=len(selected)
    return dict(candidate_ce=ce/max(1,kept),kept=kept,queried=total,kl_student_initial=kl/max(1,total))

def main():
    cfg=config();assert not (OUT/'student.pt').exists();kit.torch.set_num_threads(2);torch.manual_seed(cfg.fit_seed)
    pins=json.loads((kit.HERE/'preflight.json').read_text());kit.check_data_pins(pins);assert kit.sources_match(pins['sources'])
    started=time.perf_counter();parts=[OUT/'games'/f'game-{i:03d}.npz' for i in range(cfg.games)];loaded_parts=[]
    for part in parts:
        r=json.loads(part.with_suffix('.json').read_text());assert kit.sha(part)==r['npz_sha256'] and r['backend']=='native' and r['gamedata_sha256']==pins['gamedata_sha256']
        loaded_parts.append(load_corpus(part))
    a={k:np.concatenate([v[k] for _,v in loaded_parts]) for k in loaded_parts[0][1]}
    metadata=replace(loaded_parts[0][0],created_at=datetime.now(timezone.utc).isoformat(),samples=len(a['episode_ids']),decisions=len(a['episode_ids'])-cfg.games,provenance=json.dumps(dict(role='training',complete_game=True,games=cfg.games,teacher='privileged-srp-xm',parts=[kit.sha(p) for p in parts])))
    del loaded_parts
    corpus=OUT/'aggregate.npz'
    with corpus.open('wb') as f:np.savez_compressed(f,metadata_json=np.asarray(metadata.to_json()),**a)
    load_corpus(corpus)
    train,val=split_indices(a['episode_ids'],validation_fraction=.2,seed=cfg.split_seed)
    kit.write_json(OUT/'split.json',dict(train_games=np.unique(a['episode_ids'][train]).tolist(),heldout_games=np.unique(a['episode_ids'][val]).tolist()))
    raw=targets(a,train);tensors=tuple(torch.as_tensor(x) for x in raw);ids,counts,p,keep=tensors
    chunks=sequence_chunks(a['episode_ids'],train,sequence_length=cfg.chunk,preserve_tails=True)
    flat=chunks.ravel();assert np.array_equal(np.sort(flat[a['expert_action_supervision_valid'][flat]]),train[a['expert_action_supervision_valid'][train]])
    offsets={int(g):int(np.flatnonzero(a['episode_ids']==g)[0]) for g in np.unique(a['episode_ids'][train])}
    loaded=kit.ev.load_policy_checkpoint(kit.INITIAL,device=kit.DEVICE,decks_path=kit.TRAINING);model=loaded.model
    anchor=torch.zeros(a['action_masks'].shape,dtype=torch.float32)
    # Cache anchor on both splits with the original full recurrent measurement helper.
    base.measure(model,a,train,capture_logits=anchor);base.measure(model,a,val,capture_logits=anchor)
    curves=[dict(epoch=0,train=measure(model,a,train,tensors,anchor),heldout=measure(model,a,val,tensors,anchor))]
    cache=ImitationStateCache(model,a,chunks,episode_offsets=offsets,burn_in=16,device=kit.DEVICE)
    parity_rows=chunks[np.linspace(0,len(chunks)-1,4,dtype=int)]
    with torch.no_grad():
        full=_council_imitation_state(model,a,parity_rows,device=kit.DEVICE,episode_offsets=offsets)
        stored=cache.initial_state(model,a,parity_rows,device=kit.DEVICE)
        inputs=_sequence_batch_inputs(a,parity_rows,kit.DEVICE,trim_entity_padding=True,reset_memory=False)
        delta=float((model(inputs,full).joint_logits-model(inputs,stored).joint_logits).abs().max());assert delta<1e-4,delta
    # Candidate normalization has no direct gradient outside the candidate set.
    probe=torch.randn(1,6,requires_grad=True);loss=candidate_ce(probe,torch.tensor([[1,3]]),torch.tensor([2]),torch.tensor([[.4,.6]])).sum();loss.backward();assert torch.equal(probe.grad[0,[0,2,4,5]],torch.zeros(4))
    opt=torch.optim.AdamW(model.parameters(),lr=cfg.learning_rate);rng=np.random.default_rng(cfg.fit_seed);shuffled=chunks[rng.permutation(len(chunks))]
    model.train();updates=0
    with (OUT/'fit-batches.jsonl').open('x') as stream:
        for step in range(0,len(shuffled),4):
            rows=shuffled[step:step+4];idx=torch.as_tensor(rows);q=torch.as_tensor(a['expert_action_supervision_valid'][rows]);chosen=keep[idx]
            if not q.any():continue
            state=cache.initial_state(model,a,rows,device=kit.DEVICE)
            inputs=_sequence_batch_inputs(a,rows,kit.DEVICE,trim_entity_padding=True,reset_memory=False)
            logits=model(inputs,state).joint_logits
            ce=candidate_ce(logits[chosen],ids[idx][chosen],counts[idx][chosen],p[idx][chosen]).mean() if chosen.any() else logits[q].sum()*0
            kl=base.student_kl(logits[q],anchor[idx][q]).mean();loss=ce+cfg.anchor_kl*kl
            assert torch.isfinite(loss);opt.zero_grad(set_to_none=True);loss.backward();grad=torch.nn.utils.clip_grad_norm_(model.parameters(),.5);assert torch.isfinite(grad);opt.step();updates+=1
            record=dict(step=updates,ce=float(ce.detach()),kl=float(kl.detach()),kept=int(chosen.sum()),queried=int(q.sum()),grad_norm=float(grad));stream.write(json.dumps(record)+'\n');stream.flush()
    model.eval();curves.append(dict(epoch=1,train=measure(model,a,train,tensors,anchor),heldout=measure(model,a,val,tensors,anchor)))
    payload=_checkpoint_payload(model=model,metadata=metadata,corpus_path=corpus,metrics={'validation_accuracy':0.,'validation_loss':curves[-1]['heldout']['candidate_ce']},seed=cfg.fit_seed,split_seed=cfg.split_seed,trained=True,initial_checkpoint=kit.INITIAL,source_update=int(loaded.checkpoint.get('update',0)),source_total_transitions=int(loaded.checkpoint.get('total_transitions',0)),anchor_policy_kl_coef=cfg.anchor_kl,trim_entity_padding=True)
    payload['gamedata_sha256']=pins['gamedata_sha256'];payload['training_decks_sha256']=kit.sha(kit.TRAINING)
    payload['srp_dagger']=dict(iteration=2,config=cfg.model_dump(),targets=json.loads((OUT/'targets.json').read_text()),recurrent_update='stored-state',burn_in=16,kl_direction='student || initial',kl_rows='all queried training rows',initial_sha256=kit.sha(kit.INITIAL))
    torch.save(payload,OUT/'student.pt');kit.ev.load_policy_checkpoint(OUT/'student.pt',device=kit.DEVICE,decks_path=kit.TRAINING)
    result=dict(curves=curves,updates=updates,wall_s=time.perf_counter()-started,initial_tbptt_fullprefix_max_logit_delta=delta,outside_candidate_direct_gradient_zero=True,checkpoint_sha256=kit.sha(OUT/'student.pt'),bytes=kit.budget())
    kit.write_json(OUT/'fit.json',result);kit.log(result);note(f'Fit completed: one TBPTT epoch, {updates} updates; checkpoint reloaded; initial state parity delta {delta}; see it2/fit.json.')
if __name__=='__main__':main()
