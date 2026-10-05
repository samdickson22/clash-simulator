"""Anchored recurrent CE using repo inputs, checkpoint schema and full-prefix recurrence."""
from dataclasses import replace
from datetime import datetime, timezone
import json
import time
import numpy as np
import torch
from kit import ROOT, HERE, INITIAL, FINAL, TRAINING, DEVICE, config, ev, sha, write_json, log, budget, source_hashes, sources_match, check_data_pins
from clasher.rl.common import NUM_HAND_SLOTS, NUM_TILES
from clasher.rl.imitation import (load_corpus, split_indices, _sequence_batch_inputs,
    _imitation_evaluation_batches, _checkpoint_payload, _council_imitation_state, sequence_chunks)


def student_kl(logits, anchor_logits):
    """KL(student || initial) on the same legal action support."""
    lp = logits.log_softmax(-1)
    aq = anchor_logits.log_softmax(-1)
    return (lp.exp() * (lp - aq)).sum(-1)


@torch.no_grad()
def measure(model, arrays, rows, *, capture_logits=None):
    valid = arrays['expert_action_supervision_valid'][rows]
    indices = rows[valid]
    count = correct = waits = wait_correct = 0
    nll = 0.
    for selected, _, output in _imitation_evaluation_batches(model, arrays, indices,
            batch_size=128, device=DEVICE, trim_entity_padding=True):
        logits = output.joint_logits[:, 0]
        if capture_logits is not None:
            capture_logits[torch.as_tensor(selected, device=DEVICE)] = logits
        target = torch.as_tensor(arrays['expert_actions'][selected], device=DEVICE)
        prediction = logits.argmax(-1)
        iswait = target == NUM_HAND_SLOTS * NUM_TILES
        count += len(selected)
        correct += int((prediction == target).sum())
        waits += int(iswait.sum())
        wait_correct += int(((prediction == target) & iswait).sum())
        nll += float(torch.nn.functional.cross_entropy(logits, target, reduction='sum'))
    return dict(labels=count, ce=nll/count, agreement=correct/count, teacher_waits=waits,
        wait_agreement=wait_correct/max(1, waits),
        play_agreement=(correct-wait_correct)/max(1, count-waits))


def aggregate(cfg):
    canonical = json.loads((HERE/'canonical-data.json').read_text())
    parts = [HERE/'games'/f'game-{g:03d}.npz' for g in range(cfg.games)]
    loaded = [load_corpus(p) for p in parts]
    for part, (meta, arrays) in zip(parts, loaded):
        receipt = json.loads(part.with_suffix('.json').read_text())
        assert receipt.get('gamedata_sha256') == canonical['gamedata_sha256'] and receipt.get('backend') == 'native'
        assert sha(part) == receipt['npz_sha256']
        assert arrays['episode_starts'][0] and arrays['terminal_status'][-1] == 1
        assert not arrays['expert_action_supervision_valid'][-1]
    arrays = {key: np.concatenate([a[key] for _,a in loaded]) for key in loaded[0][1]}
    metadata = replace(loaded[0][0], created_at=datetime.now(timezone.utc).isoformat(), samples=len(arrays['episode_ids']),
        decisions=len(arrays['episode_ids'])-cfg.games,
        provenance=json.dumps(dict(role='training', complete_game=True,
            games=cfg.games, teacher='privileged-srp-xm', parts=[sha(p) for p in parts])))
    path = HERE/'aggregate.npz'
    with path.open('wb') as stream:
        np.savez_compressed(stream, metadata_json=np.asarray(metadata.to_json()), **arrays)
    load_corpus(path)
    return metadata, arrays, path


def main():
    cfg = config()
    if FINAL.exists() or (HERE/'fit.json').exists():
        raise RuntimeError('fit already exists; refusing a second fit')
    pins = json.loads((HERE/'preflight.json').read_text())
    if not sources_match(pins['sources']) or sha(INITIAL) != pins['initial_sha256']:
        raise RuntimeError('source/checkpoint drift before fitting')
    check_data_pins(pins)
    torch.set_num_threads(2)
    torch.manual_seed(cfg.fit_seed)
    np.random.seed(cfg.fit_seed)
    start = time.perf_counter()
    cpu_start = time.process_time()
    metadata, arrays, corpus = aggregate(cfg)
    train, val = split_indices(arrays['episode_ids'], validation_fraction=0.2, seed=cfg.split_seed)
    train_games = sorted(set(arrays['episode_ids'][train].tolist()))
    val_games = sorted(set(arrays['episode_ids'][val].tolist()))
    assert not set(train_games) & set(val_games)
    offsets = {g: int(np.flatnonzero(arrays['episode_ids'] == g)[0]) for g in train_games}
    chunks = sequence_chunks(arrays['episode_ids'], train,
        sequence_length=cfg.chunk, preserve_tails=True)
    # The repo pads only the unsupervised terminal row. Every label occurs once.
    flattened = chunks.reshape(-1)
    assert np.array_equal(np.sort(flattened[arrays['expert_action_supervision_valid'][flattened]]),
                          train[arrays['expert_action_supervision_valid'][train]])
    write_json(HERE/'split.json', dict(train_games=train_games, heldout_games=val_games,
        train_rows=len(train), heldout_rows=len(val), seed=cfg.split_seed))
    loaded = ev.load_policy_checkpoint(INITIAL, device=DEVICE, decks_path=TRAINING)
    model = loaded.model
    anchor_logits_cache = torch.zeros(arrays['action_masks'].shape, dtype=torch.float32, device=DEVICE)
    optimizer = torch.optim.AdamW(model.parameters(), lr=cfg.learning_rate)
    rng = np.random.default_rng(cfg.fit_seed)
    curves = []
    baseline = dict(epoch=0, train=measure(model, arrays, train, capture_logits=anchor_logits_cache), heldout=measure(model, arrays, val))
    for split, games in (('train', train_games), ('heldout', val_games)):
        receipts = [json.loads((HERE/'games'/f'game-{g:03d}.json').read_text()) for g in games]
        assert baseline[split]['labels'] == sum(r['labels'] for r in receipts)
        assert baseline[split]['teacher_waits'] == sum(r['teacher_waits'] for r in receipts)
    curves.append(baseline); log(baseline)
    anchor_checked = False
    with (HERE/'fit-batches.jsonl').open('x') as stream:
        for epoch in range(1, cfg.epochs+1):
            shuffled = chunks[rng.permutation(len(chunks))]
            batches = [shuffled[i:i+4] for i in range(0,len(shuffled),4)]
            model.train()
            for step, rows in enumerate(batches):
                inputs = _sequence_batch_inputs(arrays, rows, DEVICE, trim_entity_padding=True, reset_memory=False)
                selected = torch.as_tensor(arrays['expert_action_supervision_valid'][rows], device=DEVICE)
                if not selected.any(): continue
                state = _council_imitation_state(model, arrays, rows, device=DEVICE, episode_offsets=offsets)
                output = model(inputs, state)
                alogits = anchor_logits_cache[torch.as_tensor(rows, device=DEVICE)]
                logits = output.joint_logits[selected]
                targets = torch.as_tensor(arrays['expert_actions'][rows], device=DEVICE)[selected]
                ce = torch.nn.functional.cross_entropy(logits, targets)
                kl = student_kl(logits, alogits[selected]).mean()
                if not anchor_checked:
                    if abs(float(kl.detach())) > 1e-4:
                        raise AssertionError('initial full-prefix policy differs from frozen reference cache')
                    anchor_checked = True
                loss = ce + cfg.anchor_kl * kl
                if not torch.isfinite(loss): raise FloatingPointError('nonfinite loss')
                optimizer.zero_grad(set_to_none=True)
                loss.backward()
                grad = torch.nn.utils.clip_grad_norm_(model.parameters(), 0.5)
                if not torch.isfinite(grad): raise FloatingPointError('nonfinite gradient')
                optimizer.step()
                record = dict(epoch=epoch, step=step, ce=float(ce.detach()),
                    kl_student_initial=float(kl.detach()), loss=float(loss.detach()),
                    grad_norm=float(grad), labels=int(selected.sum()))
                stream.write(json.dumps(record)+'\n'); stream.flush()
            model.eval()
            record = dict(epoch=epoch, train=measure(model, arrays, train), heldout=measure(model, arrays, val),
                elapsed_s=time.perf_counter()-start)
            curves.append(record); log(record)
            write_json(HERE/'fit-curves.json', curves)
    payload = _checkpoint_payload(model=model, metadata=metadata, corpus_path=corpus,
        metrics={'validation_accuracy': curves[-1]['heldout']['agreement'],
                 'validation_loss': curves[-1]['heldout']['ce']},
        seed=cfg.fit_seed, split_seed=cfg.split_seed, trained=True,
        initial_checkpoint=INITIAL, source_update=int(loaded.checkpoint.get('update',0)),
        source_total_transitions=int(loaded.checkpoint.get('total_transitions',0)),
        anchor_policy_kl_coef=cfg.anchor_kl, trim_entity_padding=True)
    payload['gamedata_sha256'] = sha(ROOT/'gamedata.json')
    payload['training_decks_sha256'] = sha(TRAINING)
    payload['srp_dagger'] = dict(config=cfg.model_dump(), kl_direction='student || initial',
        recurrent_update='full-prefix', anchor_recurrence='cached frozen full-episode outputs', torch_threads=torch.get_num_threads(),
        source_hashes=source_hashes(), initial_sha256=sha(INITIAL), teacher_manifest_sha256=sha(HERE/'teacher.json'))
    torch.save(payload, FINAL)
    ev.load_policy_checkpoint(FINAL, device=DEVICE, decks_path=TRAINING)
    write_json(HERE/'fit.json', dict(curves=curves, torch_threads=torch.get_num_threads(), checkpoint_sha256=sha(FINAL),
        corpus_sha256=sha(corpus), wall_s=time.perf_counter()-start, cpu_s=time.process_time()-cpu_start, bytes=budget()))


if __name__ == '__main__': main()
