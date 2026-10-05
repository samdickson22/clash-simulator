"""Streaming reuse of DAgger soft targets and the repository full-prefix BC path."""
import argparse
import time
from common import *
from clasher.rl.imitation import (load_corpus, sequence_chunks, _sequence_batch_inputs,
    _council_imitation_state, _imitation_evaluation_batches, _checkpoint_payload)

QUANTILES = [0, .25, .5, .75, .9, .99, 1]

def target_rows(path):
    with np.load(path) as d:
        valid = d['expert_action_supervision_valid']; rows = np.flatnonzero(valid)
        ids = np.zeros((len(valid), 14), np.int64)
        scores = np.full((len(valid), 14), -np.inf)
        counts = np.zeros(len(valid), np.int64)
        raw_rows, raw_ids, raw_values = d['root_candidate_rows'], d['root_candidate_ids'], d['root_candidate_values']
        for row in rows:
            chosen = raw_rows == row; actions, values = raw_ids[chosen], raw_values[chosen]
            assert 1 < len(actions) <= 14 and len(actions) == len(set(actions))
            assert d['action_masks'][row, actions].all() and np.isfinite(values).all()
            assert d['expert_actions'][row] in actions
            ids[row, :len(actions)] = actions; scores[row, :len(actions)] = values; counts[row] = len(actions)
    return rows, ids, scores, counts

def probabilities(scores, tau):
    z = (scores-scores.max(-1, keepdims=True))/tau
    p = np.exp(z); p /= p.sum(-1, keepdims=True)
    return p, -(p*np.log(np.maximum(p, 1e-300))).sum(-1)

def gap(scores, counts):
    # Equal scores must have exactly zero weight, including roundoff in the mean.
    maximum = scores.max(-1, keepdims=True)
    return np.where(np.isfinite(scores), maximum-scores, 0.).sum(-1)/counts

def prepare(out, iteration):
    cfg = config(); pairs = np.arange(cfg.games//2)
    np.random.default_rng(cfg.split_seed+iteration).shuffle(pairs)
    heldout = set(pairs[:max(1, round(len(pairs)*.2))].tolist())
    split = {'train_games': [], 'heldout_games': []}
    data = []
    for g in range(cfg.games):
        path = out/'games'/f'game-{g:03d}.npz'; r = json.loads(path.with_suffix('.json').read_text())
        assert sha(path) == r['npz_sha256'] and r['checkpoint_sha256'] == sha(previous(iteration))
        rows, _, s, c = target_rows(path); istrain = g//2 not in heldout
        split['train_games' if istrain else 'heldout_games'].append(g)
        data.append((s[rows], c[rows], istrain, r['family_id']=='hog26'))
    train_scores = np.concatenate([s for s,c,t,h in data if t]); train_counts = np.concatenate([c for s,c,t,h in data if t])
    lo, hi = 1e-12, max(1., float(np.ptp(train_scores[np.isfinite(train_scores)]))*100)
    reachable = float(np.median(probabilities(train_scores,lo)[1])) <= 1 <= float(np.median(probabilities(train_scores,hi)[1]))
    for _ in range(70):
        mid = np.sqrt(lo*hi)
        if np.median(probabilities(train_scores, mid)[1]) < 1: lo = mid
        else: hi = mid
    tau = float(np.sqrt(lo*hi)); normalizer = float(gap(train_scores, train_counts).mean())
    assert normalizer > 0
    report = dict(tau=tau, entropy_target_reachable=reachable, weight_normalizer=normalizer,
        tau_fit_split='training game pairs only', hard_margin_filter=False, quantiles=QUANTILES, groups={})
    for name, predicate in [('all', lambda t,h:True), ('training',lambda t,h:t), ('heldout',lambda t,h:not t), ('hog26',lambda t,h:h)]:
        scores = np.concatenate([s for s,c,t,h in data if predicate(t,h)])
        counts = np.concatenate([c for s,c,t,h in data if predicate(t,h)])
        weights = gap(scores,counts)/normalizer; _, entropy = probabilities(scores,tau)
        report['groups'][name] = dict(rows=len(weights), weight_quantiles=np.quantile(weights,QUANTILES).tolist(),
            gap_quantiles=np.quantile(weights*normalizer,QUANTILES).tolist(), entropy_quantiles=np.quantile(entropy,QUANTILES).tolist(),
            score_quantiles=np.quantile(scores[np.isfinite(scores)],QUANTILES).tolist(),
            weight_mean=float(weights.mean()), zero_weight_fraction=float(np.mean(weights==0)),
            effective_sample_size=float(weights.sum()**2/max(1e-30,(weights**2).sum())))
    write_json(out/'split.json', split); write_json(out/'targets.json',report); log(report)
    return split, report

def tensors(path, targets):
    rows, ids, scores, counts = target_rows(path)
    p = np.zeros_like(scores, dtype=np.float32); w = np.zeros(len(counts), np.float32)
    p[rows] = probabilities(scores[rows], targets['tau'])[0]
    w[rows] = gap(scores[rows],counts[rows])/targets['weight_normalizer']
    return tuple(torch.as_tensor(x) for x in (ids, counts, p, w))

def candidate_ce(logits, ids, counts, p):
    valid = torch.arange(ids.shape[-1]) < counts[..., None]
    lp = logits.gather(-1,ids).masked_fill(~valid, -1e9).log_softmax(-1)
    return -(p*lp).sum(-1)

def student_kl(logits, reference):
    lp, lq = logits.log_softmax(-1), reference.log_softmax(-1)
    return (lp.exp()*(lp-lq)).sum(-1)

@torch.no_grad()
def anchor_logits(model, a):
    result = torch.zeros(a['action_masks'].shape, dtype=torch.float32)
    for rows, _, output in _imitation_evaluation_batches(model,a,np.flatnonzero(a['expert_action_supervision_valid']),batch_size=128,device=DEVICE,trim_entity_padding=True):
        result[torch.as_tensor(rows)] = output.joint_logits[:,0]
    return result

@torch.no_grad()
def measure(model, anchor, out, games, targets):
    totals = {name:dict(rows=0, ce=0., weighted_ce=0., kl=0.) for name in ('all','hog26')}
    for g in games:
        path = out/'games'/f'game-{g:03d}.npz'; _, a = load_corpus(path)
        ids, counts, p, w = tensors(path, targets); ref = anchor_logits(anchor,a)
        for rows, _, output in _imitation_evaluation_batches(model,a,np.flatnonzero(a['expert_action_supervision_valid']),batch_size=128,device=DEVICE,trim_entity_padding=True):
            logits = output.joint_logits[:,0]; idx = torch.as_tensor(rows)
            ce = candidate_ce(logits,ids[idx],counts[idx],p[idx]); kl = student_kl(logits,ref[idx])
            for group in ('all','hog26') if (g//2)%3 == 0 else ('all',):
                t = totals[group]; t['rows'] += len(rows); t['ce'] += float(ce.sum()); t['weighted_ce'] += float((w[idx]*ce).sum()); t['kl'] += float(kl.sum())
    return {group:{k:v if k=='rows' else v/max(1,t['rows']) for k,v in t.items()} for group,t in totals.items()}

def main(iteration):
    verify(); cfg = config(); out = folder(iteration)
    assert not (out/'fit.json').exists()
    torch.set_num_threads(1); torch.manual_seed(cfg.fit_seed+iteration)
    split, targets = prepare(out,iteration); started = time.perf_counter()
    loaded = cl_eval.load_policy_checkpoint(previous(iteration),device=DEVICE,decks_path=TRAIN_DECKS); model = loaded.model
    anchor = cl_eval.load_policy_checkpoint(previous(iteration),device=DEVICE,decks_path=TRAIN_DECKS).model
    anchor.eval(); anchor.requires_grad_(False)
    baseline = dict(epoch=0, heldout=measure(model,anchor,out,split['heldout_games'],targets)); log(baseline)
    curves = [baseline]; write_json(out/'fit-curves.json',curves)
    optimizer = torch.optim.AdamW(model.parameters(),lr=cfg.learning_rate)
    rng = np.random.default_rng(cfg.fit_seed+iteration); updates = 0
    with (out/'fit-batches.jsonl').open('w') as stream:
        for epoch in range(1,cfg.epochs+1):
            # Load one complete game at a time to bound RAM. Shuffle games and chunks.
            for g in rng.permutation(split['train_games']):
                verify(); path = out/'games'/f'game-{g:03d}.npz'; metadata, a = load_corpus(path)
                ids, counts, p, w = tensors(path,targets); ref = anchor_logits(anchor,a)
                chunks = sequence_chunks(a['episode_ids'],np.arange(len(a['episode_ids'])),sequence_length=cfg.chunk,preserve_tails=True)
                flat = chunks.ravel(); valid = a['expert_action_supervision_valid']
                assert np.array_equal(np.sort(flat[valid[flat]]),np.flatnonzero(valid))
                shuffled = chunks[rng.permutation(len(chunks))]; model.train()
                for start in range(0,len(shuffled),4):
                    rows = shuffled[start:start+4]; q = torch.as_tensor(valid[rows]); idx = torch.as_tensor(rows)
                    if not q.any(): continue
                    state = _council_imitation_state(model,a,rows,device=DEVICE,episode_offsets={int(g):0})
                    inputs = _sequence_batch_inputs(a,rows,DEVICE,trim_entity_padding=True,reset_memory=False)
                    logits = model(inputs,state).joint_logits[q]
                    ce = (w[idx][q]*candidate_ce(logits,ids[idx][q],counts[idx][q],p[idx][q])).mean()
                    kl = student_kl(logits,ref[idx][q]).mean()
                    if updates == 0: assert abs(float(kl.detach())) < 1e-4
                    loss = ce+cfg.anchor_kl*kl; assert torch.isfinite(loss)
                    optimizer.zero_grad(set_to_none=True); loss.backward()
                    grad = torch.nn.utils.clip_grad_norm_(model.parameters(),.5); assert torch.isfinite(grad)
                    optimizer.step(); updates += 1
                    stream.write(json.dumps(dict(epoch=epoch,game=int(g),update=updates,weighted_ce=float(ce.detach()),kl=float(kl.detach()),rows=int(q.sum())))+'\n'); stream.flush()
                log(dict(event='fit_game',epoch=epoch,game=int(g),updates=updates,elapsed_s=time.perf_counter()-started))
            model.eval(); rec = dict(epoch=epoch,heldout=measure(model,anchor,out,split['heldout_games'],targets))
            curves.append(rec); write_json(out/'fit-curves.json',curves); log(rec)
    payload = _checkpoint_payload(model=model,metadata=metadata,corpus_path=out/'games',
        metrics={'validation_accuracy':0.,'validation_loss':curves[-1]['heldout']['all']['weighted_ce']},
        seed=cfg.fit_seed+iteration,split_seed=cfg.split_seed+iteration,trained=True,initial_checkpoint=previous(iteration),
        source_update=int(loaded.checkpoint.get('update',0)),source_total_transitions=int(loaded.checkpoint.get('total_transitions',0)),
        anchor_policy_kl_coef=cfg.anchor_kl,trim_entity_padding=True)
    payload['gamedata_sha256'] = sha(ROOT/'gamedata.json'); payload['training_decks_sha256'] = sha(TRAIN_DECKS)
    payload['exit'] = dict(iteration=iteration,recurrent_update='full-prefix',previous_sha256=sha(previous(iteration)),targets=targets,config=cfg.model_dump())
    verify(); tmp = out/'student.tmp.pt'; torch.save(payload,tmp); tmp.replace(out/'student.pt')
    cl_eval.load_policy_checkpoint(out/'student.pt',device=DEVICE,decks_path=TRAIN_DECKS)
    write_json(out/'fit.json',dict(curves=curves,updates=updates,wall_s=time.perf_counter()-started,checkpoint_sha256=sha(out/'student.pt'),bytes=budget()))
if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--iteration',type=int,required=True);main(p.parse_args().iteration)
