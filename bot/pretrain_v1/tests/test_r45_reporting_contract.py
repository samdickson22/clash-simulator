"""CPU reporting contracts. Synthetic boundaries are never training evidence."""
import copy
from dataclasses import asdict
import json
from pathlib import Path
import shutil
import sys
import threading

import numpy as np
import pytest
import torch

from bot.pretrain_v1 import rl_reporting as R, rl_schedule as S, rl_evaluate as E
from bot.pretrain_v1 import rl_coordinator as C, rl_driver as D, stream_actor as A
from bot.pretrain_v1.tests.test_rl_learner import admitted, cpu_threads

REVIEW = Path('/mpac/sdicks02/scratch/pretrain-v1-dev/rl-readiness')
RUNTIME = Path('/mpac/sdicks02/repos/pretrain-v1-rl-runtime-0dcab45f7-joint')
ACTORS = Path('/mpac/sdicks02/repos/pretrain-v1-rl-actors-0dcab45f7-joint')


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(S.encoded(value))
    return dict(path=str(path), sha256=S.file_sha(path))


def normal_row(tmp_path):
    """Copy exact approved bytes; keep the complete manifest, without imports."""
    manifest = REVIEW/'joint-manifest.json'
    lineage = json.loads(manifest.read_text())
    origins = {}
    for name in ('bot', 'bot.players.ours', 'bot.rl.actor', 'clasher', 'clasher.arena'):
        relative = name.replace('.', '/')+('/__init__.py' if name in ('bot', 'clasher') else '.py')
        engine = name == 'clasher' or name.startswith('clasher.')
        if engine:
            relative = 'src/'+relative
        root = RUNTIME if engine else ACTORS
        source = root/relative
        files = lineage['files' if engine else 'source_files']
        assert S.file_sha(source) == files[relative]
        target = tmp_path/('runtime' if engine else 'actors')/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        origins[name] = str(target)
    for name in ('bot.pretrain_v1', 'bot.pretrain_v1.rl_evaluate', 'bot.pretrain_v1.rl_driver',
                 'bot.pretrain_v1.sim_ours', 'bot.pretrain_v1.model'):
        relative = name.replace('.', '/')+('/__init__.py' if name == 'bot.pretrain_v1' else '.py')
        origins[name] = str(D.ROOT/relative)
    manifest_copy = tmp_path/'lineage.json'
    shutil.copyfile(manifest, manifest_copy)
    config = dict(runtime=str(tmp_path/'runtime'), actor_source=str(tmp_path/'actors'),
                  runtime_manifest=dict(path=str(manifest_copy), sha256=S.file_sha(manifest)))
    case = dict(index=0, seed=12, seat=0, decks=[list(S.HOG), list(S.HOG)])
    row = dict(index=0, case=case, case_sha256=S.digest(case), policy_sha256='p', bank_sha256='b',
               runtime_manifest={}, module_origins_after=origins,
               result=dict(terminal=True, winner=None, seed=12, decks=case['decks']), win=0, draw=1, score=.5)
    return row, case, config


def test_normal_pinned_bootstrap_origins_and_terminal_draw(tmp_path):
    row, case, config = normal_row(tmp_path)
    assert R.validate_origins(row['module_origins_after'], config) is None
    assert E.validate_result(row, case, policy='p', bank='b', runtime={}, config=config) == 0
    assert not any(name == 'clasher' or name.startswith('clasher.') for name in sys.modules)
    lineage = R.read(S.pinned(config['runtime_manifest']))
    assert lineage == R.read(REVIEW/'joint-manifest.json')
    assert config['runtime_manifest']['sha256'] == S.file_sha(REVIEW/'joint-manifest.json')
    assert 'src/clasher/__init__.py' in lineage['files']


@pytest.mark.parametrize('change', ['flat_package', 'flat_module', 'wrong_root', 'wrong_name',
                                  'changed_bytes', 'missing_package', 'missing_actor', 'missing_harness',
                                  'wrong_candidate', 'missing_origins'])
def test_origin_tampering_fails_closed(tmp_path, change):
    row, case, config = normal_row(tmp_path)
    origins = row['module_origins_after']
    if change.startswith('flat_'):
        name = 'clasher' if change == 'flat_package' else 'clasher.arena'
        relative = 'clasher/__init__.py' if name == 'clasher' else 'clasher/arena.py'
        dest = tmp_path/'runtime'/relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origins[name], dest)
        origins[name] = str(dest)
        # Even a pinned flattened alias is outside the approved import layout.
        lineage = R.read(S.pinned(config['runtime_manifest']))
        lineage['files'][relative] = S.file_sha(dest)
        config['runtime_manifest'] = write(tmp_path/'altered-lineage.json', lineage)
    elif change == 'wrong_root':
        origins['clasher'] = str(RUNTIME/'src/clasher/__init__.py')
    elif change == 'wrong_name':
        origins['bot.players.ours'] = origins['bot.rl.actor']
    elif change == 'changed_bytes':
        Path(origins['clasher.arena']).write_text('# changed pinned bytes\n')
    elif change == 'wrong_candidate':
        origins['bot.pretrain_v1.model'] = origins['bot.pretrain_v1.rl_driver']
    elif change == 'missing_origins':
        row.pop('module_origins_after')
    else:
        origins.pop({'missing_package': 'clasher', 'missing_actor': 'bot.rl.actor',
                     'missing_harness': 'bot.pretrain_v1.sim_ours'}[change])
    with pytest.raises(ValueError):
        E.validate_result(row, case, policy='p', bank='b', runtime={}, config=config)


def test_invalid_and_failed_attempts_stay_missing_but_identity_is_fatal(tmp_path):
    row, case, config = normal_row(tmp_path)
    row.update(invalid=True, win=1, score=1)
    assert E.validate_result(row, case, policy='p', bank='b', runtime={}, config=config) is None
    row['policy_sha256'] = 'stale'
    with pytest.raises(ValueError, match='provenance'):
        E.validate_result(row, case, policy='p', bank='b', runtime={}, config=config)
    row.update(policy_sha256='p', invalid=False, error='assigned attempt failed')
    assert E.validate_result(row, case, policy='p', bank='b', runtime={}, config=config) is None


def build_chain(path, anchor, *, eligible=False):
    """Production learner budgets, toy admitted tensors, real coordinator format.

    No optimizer updates or games occur. We independently construct boundary
    states and receipt metadata, and use the actual snapshot/finalize writers.
    This fixture cannot pass registered run admission.
    """
    config = dict(seed=S.SEEDS[0], size='M', precision='float64', workers=32, chunk_rows=128,
                  precision_registration_id='dual-size-fp64-20261022-r1', wait_seconds=60,
                  anchor=dict(path=str(anchor['anchor_path']), sha256=anchor['anchor_sha256']),
                  model_cfg=write(path/'cfg.json', anchor['model_cfg']))
    runtime = anchor['runtime_manifest']
    proof = R.learner(config, runtime)
    # No worker or queue is started. The object only exercises the existing
    # coordinator's durable checkpoint and finalization format.
    c = C.Coordinator.__new__(C.Coordinator)
    c.learner, c.config = proof, C.CoordinatorConfig(wait_seconds=60)
    c.quotas = {f'actor-{i:02d}': 8192 for i in range(32)}
    c.budgets = {k: n*32 for k, n in c.quotas.items()}
    c.steps, c.updates, c.version = 262144, 32, 0
    c.model_cfg, c.runtime = proof.model.cfg, runtime
    c.anchor, c.provenance = proof.anchor_sha256, proof.provenance_sha256
    c.path = path/'checkpoints'; c.path.mkdir()
    c.condition = threading.Condition()
    c.reason, c._previous_checkpoint, c.games = None, None, []
    c.actors = {k: dict(generated=0, observed=0, accepted=0, trained=0, sequence=0,
                        reported_until=0, unpublished_reported=0, reported_ranges=[], update_rows=0,
                        boundary_declined=0, completed=0, chain='0'*64, last=None) for k in c.quotas}
    rng = np.random.default_rng(config['seed'])
    optimizer = proof.optimizer.state_dict()
    parameters = dict(enumerate(proof.model.named_parameters()))
    for v in range(33):
        receipts = []
        if v:
            for key, a in c.actors.items():
                for i in range(64):
                    seq = a['sequence']
                    game_seq, part = divmod(seq, 9)
                    terminal = part == 8
                    game_id = f'{key}/game-{game_seq}'
                    total = a['accepted']+128
                    reason = 'budget' if total == c.budgets[key] else 'quota' if i == 63 else 'terminal' if terminal else 'chunk'
                    tick = 90+(part*128+127)*5
                    publication = asdict(C.Publication(seq, game_id, game_seq, tick+(1 if terminal else 5), terminal,
                        C.L.PlayRate(game_id, 30, 300.) if terminal else None))
                    boundary = asdict(A.Boundary(reason, total, c.budgets[key]-total, (63-i)*128,
                                                terminal, reason == 'budget' and not terminal, 0))
                    identity = f'{key}/{seq}'
                    receipt = asdict(A.Receipt('chunk-'+S.digest(identity)[:32], S.digest(['manifest', identity]),
                                              100000, 128, v-1, 128))
                    binding = dict(actor_id=key, receipt=receipt, boundary=boundary,
                                   publication=publication, previous=a['chain'])
                    binding['sha256'] = S.digest(binding)
                    receipts.append(binding)
                    a.update(generated=total, observed=total, accepted=total, sequence=seq+1,
                             update_rows=(i+1)*128, chain=binding['sha256'],
                             last=dict(game_id=game_id, game_sequence=game_seq, tick=tick, terminal=terminal,
                                       bootstrap=0., version=v-1, declined=False, opponent_id='frozen-live'))
                    if terminal:
                        c.games.append(dict(actor_id=key, game_id=game_id, game_sequence=game_seq,
                                            accepted_plays=30, seconds=300., terminal_reward=0.,
                                            engine_tick=publication['engine_tick']))
                        a['completed'] += 1
                a['trained'] = v*8192
            for _ in range(2):
                rng.permutation(262144)
        proof.update_index = v
        proof.generated_steps = proof.trained_steps = v*262144
        proof.optimizer_steps = v*256
        proof.shuffle_rng.bit_generator.state = copy.deepcopy(rng.bit_generator.state)
        proof._ppo_actor_masks = [(b'\xff' if eligible else b'\0')*32768]*max(0, v-3)
        optimizer['state'] = {}
        for pid, (name, parameter) in parameters.items():
            steps = v*256 if name.startswith('value.') else 0 if not eligible and name.startswith(('noop.', 'ptr.', 'tile.')) else max(0, v-3)*256
            if steps:
                optimizer['state'][pid] = dict(step=torch.tensor(float(steps), dtype=torch.float32),
                    exp_avg=torch.zeros_like(parameter), exp_avg_sq=torch.zeros_like(parameter))
        proof.optimizer.load_state_dict(optimizer)
        if v:
            new_games = [g for g in c.games if (v-1)*64 <= g['game_sequence']*9+8 < v*64]
            proof.last_metrics = dict(update=v, version=v, warmup=v <= 3, generated_steps=v*262144,
                trained_steps=v*262144, optimizer_steps=v*256, polls=262144, legal_action_checks=262144,
                cadence_checks=262144, policy_sha256=proof.policy_sha256, halted_reason=None, high_kl_streak=0,
                actor_polls=262144 if eligible else 0, forced_polls=0 if eligible else 262144,
                busy_polls=0, boundary_declined_steps=0, old_logp_max_error=0., old_value_max_error=0.,
                mean_entropy=.5 if eligible else 0., mean_kl=0., p95_kl=0.,
                per_opponent_kl={'frozen-live': dict(mean=0., p95=0., polls=262144)},
                plays_per_300s={S.digest([g['actor_id'], g['game_id']]): 30. for g in new_games},
                play_rates_reported=bool(new_games))
        c._checkpoint(receipts)
        c.version = v
        for a in c.actors.values():
            a['update_rows'] = 0
    final = c.finalize()
    write(path/'completed.json', dict(status='training_complete', optimizer_resume_proof=True,
        engine_resume_qualified=False, generated_counts=c.budgets, final=final))
    return config, runtime


@pytest.fixture(scope='module')
def chain_source(tmp_path_factory):
    path = tmp_path_factory.mktemp('r45-chain')
    torch.set_num_threads(1)
    anchor = admitted.__wrapped__(path)
    config, runtime = build_chain(path, anchor)
    return path, config, runtime


@pytest.fixture
def chain(tmp_path, chain_source):
    source, config, runtime = chain_source
    shutil.copytree(source/'checkpoints', tmp_path/'checkpoints')
    shutil.copyfile(source/'completed.json', tmp_path/'completed.json')
    return tmp_path, copy.deepcopy(config), copy.deepcopy(runtime)


def rehash_chain(path, start=0):
    """Relink every file/ledger and both completion copies after an attack."""
    previous = None
    for v in range(33):
        pt = path/f'checkpoints/update-{v:02d}.pt'
        ledger = R.read(pt.with_suffix('.json'))
        ledger['previous_checkpoint_sha256'] = previous
        ledger['learner_checkpoint']['sha256'] = S.file_sha(pt)
        if v >= start:
            write(pt.with_suffix('.json'), ledger)
        previous = S.digest(ledger)
    final = R.read(path/'checkpoints/final-manifest.json')
    final.update(previous_checkpoint_sha256=previous, checkpoint_sha256=previous)
    write(path/'checkpoints/final-manifest.json', final)
    saved = R.read(path/'completed.json'); saved['final'] = final
    write(path/'completed.json', saved)


def test_completed_chain_deserializes_all_33_even_for_only_own_bc(chain, monkeypatch):
    path, config, runtime = chain
    seen = []
    verify = R.verify_checkpoint
    def record(*args, **kwargs):
        seen.append(args[2])
        return verify(*args, **kwargs)
    monkeypatch.setattr(R, 'verify_checkpoint', record)
    # A read-only verifier must not call the resume path or restore process RNG.
    monkeypatch.setattr(C.L.Learner, 'load_checkpoint', lambda *a: pytest.fail('resume loader called'))
    monkeypatch.setattr(torch.cuda, 'set_rng_state_all', lambda *a: pytest.fail('CUDA RNG restore'))
    monkeypatch.setattr(torch, 'set_rng_state', lambda *a: pytest.fail('process RNG restore'))
    assert set(R.authenticate_checkpoints(config, path, runtime, {0}, completed=True)) == {0}
    assert seen == list(range(33))


@pytest.mark.parametrize('change', ['runtime', 'junk', 'Adam_step', 'dtype', 'feature', 'policy',
                                  'generated', 'trained', 'optimizer_steps', 'config', 'masks', 'shuffle', 'progress'])
def test_rehashed_update01_serialized_state_is_always_checked(chain, change):
    path, config, runtime = chain
    pt = path/'checkpoints/update-01.pt'
    state = torch.load(pt, weights_only=False)
    if change == 'runtime': state['runtime_manifest'] = dict(runtime, assembler='wrong-runtime')
    elif change == 'Adam_step': next(iter(state['optimizer']['state'].values()))['step'] += 7
    elif change == 'dtype': state['model'] = {k: v.float() for k, v in state['model'].items()}
    elif change == 'feature': state['feature_hash'] = 'f'*64
    elif change == 'policy': state['policy_sha256'] = 'f'*64
    elif change in ('generated', 'trained', 'optimizer_steps'):
        key = change if change == 'optimizer_steps' else change+'_steps'
        state[key] += 7
    elif change == 'config': state['config']['test_only'] = True
    elif change == 'progress': state['last_metrics'] = None
    elif change == 'masks': state['optimizer_resume']['ppo_actor_masks'] = [bytes(32768)]
    elif change == 'shuffle': state['shuffle_rng'] = torch.load(path/'checkpoints/update-00.pt', weights_only=False)['shuffle_rng']
    if change == 'junk': pt.write_bytes(b'not a torch checkpoint\n')
    else: torch.save(state, pt)
    rehash_chain(path, 1)
    with pytest.raises((ValueError, RuntimeError, EOFError, __import__('pickle').UnpicklingError)):
        R.authenticate_checkpoints(config, path, runtime, {0, 10, 20, 30, 32}, completed=True)


def test_rehashed_self_consistent_eligibility_cannot_rewrite_prior_updates(chain):
    path, config, runtime = chain
    pt = path/'checkpoints/update-05.pt'
    state = torch.load(pt, weights_only=False)
    masks = state['optimizer_resume']['ppo_actor_masks']
    masks[0] = b'\x01'+masks[0][1:]
    proof = R.learner(config, runtime)
    # Make this boundary internally valid, including all newly eligible heads.
    counters = proof._checkpoint_optimizer_counters(state)
    for pid, parameter in enumerate(proof.model.parameters()):
        if pid in counters:
            state['optimizer']['state'][pid] = dict(step=torch.tensor(float(counters[pid]), dtype=torch.float32),
                exp_avg=torch.zeros_like(parameter), exp_avg_sq=torch.zeros_like(parameter))
    torch.save(state, pt)
    rehash_chain(path, 5)
    with pytest.raises(ValueError, match='eligibility history changed'):
        R.authenticate_checkpoints(config, path, runtime, {0, 32}, completed=True)


@pytest.mark.parametrize('change', ['missing_actors', 'missing_receipts', 'missing_quotas', 'missing_budget',
                                  'actor_generated', 'actor_observed', 'actor_trained', 'actor_sequence',
                                  'actor_chain', 'actor_last', 'actor_completed', 'actor_discarded',
                                  'actor_declined', 'actor_reported', 'receipt_rows', 'receipt_budget',
                                  'receipt_chain', 'receipt_sequence', 'receipt_game', 'missing_game'])
def test_rehashed_ledger_progress_cannot_be_invented(chain, change):
    path, config, runtime = chain
    ledger_path = path/'checkpoints/update-01.json'
    ledger = R.read(ledger_path)
    if change.startswith('missing_') and change != 'missing_game':
        ledger.pop({'missing_actors': 'actors', 'missing_receipts': 'receipts',
                    'missing_quotas': 'quotas', 'missing_budget': 'budgets'}[change])
    elif change.startswith('actor_'):
        actor = ledger['actors']['actor-00']
        field = change.removeprefix('actor_')
        if field == 'chain': actor['chain'] = 'f'*64
        elif field == 'last': actor['last']['game_id'] = 'wrong-game'
        elif field == 'reported': actor['reported_ranges'] = [[0, 128]]
        else: actor[{'declined': 'boundary_declined'}.get(field, field)] += 1
    elif change == 'missing_game': ledger['games'].pop(0)
    else:
        binding = ledger['receipts'][0]
        if change == 'receipt_rows': binding['receipt']['rows'] += 1
        elif change == 'receipt_budget': binding['boundary']['remaining_budget'] += 1
        elif change == 'receipt_chain': binding['previous'] = 'f'*64
        elif change == 'receipt_sequence': binding['publication']['sequence'] += 1
        elif change == 'receipt_game': binding['publication']['game_sequence'] += 1
        binding['sha256'] = S.digest({k: v for k, v in binding.items() if k != 'sha256'})
    write(ledger_path, ledger); rehash_chain(path, 1)
    with pytest.raises((ValueError, KeyError)):
        R.authenticate_checkpoints(config, path, runtime, {0, 32}, completed=True)


@pytest.mark.parametrize('change', ['totals', 'actor_counts', 'completed_games', 'unfinished_games',
                                  'game_hash', 'final_receipts', 'final_actors', 'no_resume_marker'])
def test_final_manifest_and_driver_totals_reconcile(chain, change):
    path, config, runtime = chain
    final = R.read(path/'checkpoints/final-manifest.json')
    saved = R.read(path/'completed.json')
    if change == 'totals': final['accepted'] -= 1
    elif change == 'actor_counts': saved['generated_counts']['actor-00'] -= 1
    elif change == 'completed_games': final['completed_games'] += 1
    elif change == 'unfinished_games': final['unfinished_games'] += 1
    elif change == 'game_hash': final['games_sha256'] = 'f'*64
    elif change == 'final_receipts': final['receipts'] = R.read(path/'checkpoints/update-32.json')['receipts']
    elif change == 'final_actors': final['actors']['actor-00']['accepted'] -= 1
    elif change == 'no_resume_marker': saved.pop('engine_resume_qualified')
    write(path/'checkpoints/final-manifest.json', final)
    saved['final'] = final; write(path/'completed.json', saved)
    with pytest.raises(ValueError):
        R.authenticate_checkpoints(config, path, runtime, {0, 32}, completed=True)
