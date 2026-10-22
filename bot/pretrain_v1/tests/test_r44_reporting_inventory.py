"""CPU adversarial tests for reporting authentication and historical exclusions."""
import copy
import json
from pathlib import Path

import pytest
import torch

from bot.pretrain_v1 import rl_schedule as S, rl_evaluate as E, rl_reporting as R
from bot.pretrain_v1 import rl_exclusions as X, rl_driver as D
from bot.pretrain_v1 import prepare_registered_rl as F, summarize_registered_rl as Summary
from bot.pretrain_v1.tests.test_rl_learner import admitted, cpu_threads


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(S.encoded(value))
    return F.reference(path)


@pytest.fixture
def checkpoint(tmp_path, admitted):
    config = dict(seed=S.SEEDS[0], size='M', precision='float64', workers=32, chunk_rows=128,
                  precision_registration_id='dual-size-fp64-20261022-r1', wait_seconds=60,
                  anchor=F.reference(admitted['anchor_path']),
                  model_cfg=write(tmp_path/'cfg.json', admitted['model_cfg']))
    runtime = admitted['runtime_manifest']
    proof = R.learner(config, runtime)
    path = tmp_path/'checkpoints/update-00.pt'
    proof.save_checkpoint(path)
    def ledger():
        state = torch.load(path, weights_only=False)
        return write(path.with_suffix('.json'), dict(schema=1, test_only=False, version=0,
            config=dict(wait_seconds=60, test_only=False), learner_config=proof.config.record(),
            anchor_sha256=proof.anchor_sha256, model_cfg=proof.model.cfg, model_cfg_sha256=S.digest(proof.model.cfg),
            feature_hash=proof.feature_hash, runtime_manifest=runtime, provenance_sha256=proof.provenance_sha256,
            previous_checkpoint_sha256=None, engine_resume_qualified=False,
            quotas={f'actor-{i:02d}': 8192 for i in range(32)},
            budgets={f'actor-{i:02d}': 262144 for i in range(32)}, receipts=[], games=[],
            actors={f'actor-{i:02d}': dict(generated=0, observed=0, accepted=0, trained=0, sequence=0,
                reported_until=0, unpublished_reported=0, reported_ranges=[], update_rows=0,
                boundary_declined=0, completed=0, chain='0'*64, last=None, discarded=0,
                games_sha256=S.digest([])) for i in range(32)},
            policy_sha256=state['policy_sha256'], learner_checkpoint=dict(file=path.name, sha256=S.file_sha(path))))
    ledger()
    return config, runtime, proof, path, ledger


def test_verified_fp64_own_bc_and_missing_checkpoint_or_ledger(checkpoint, tmp_path):
    config, runtime, proof, path, _ = checkpoint
    assert R.authenticate_checkpoints(config, tmp_path, runtime, {0}, completed=False) == {0: proof.policy_sha256}
    path.rename(path.with_suffix('.missing'))
    with pytest.raises(FileNotFoundError):
        R.authenticate_checkpoints(config, tmp_path, runtime, {0}, completed=False)
    path.with_suffix('.missing').rename(path)
    path.with_suffix('.json').unlink()
    with pytest.raises(FileNotFoundError):
        R.authenticate_checkpoints(config, tmp_path, runtime, {0}, completed=False)


def test_self_consistent_real_alternate_checkpoint_cannot_replace_own_bc(checkpoint, tmp_path):
    config, runtime, proof, path, ledger = checkpoint
    original = proof.policy_sha256
    with torch.no_grad():
        next(proof.model.parameters()).add_(.01)
    proof.save_checkpoint(path)
    ledger()  # Update the file SHA AND policy claim, as a stale internally consistent phase would.
    assert torch.load(path, weights_only=False)['policy_sha256'] != original
    with pytest.raises(ValueError, match='own BC'):
        R.authenticate_checkpoints(config, tmp_path, runtime, {0}, completed=False)


@pytest.mark.parametrize('change', ['runtime', 'dtype', 'feature', 'test_only', 'version'])
def test_checkpoint_identity_cannot_be_relabelled(checkpoint, tmp_path, change):
    config, runtime, _, path, ledger = checkpoint
    state = torch.load(path, weights_only=False)
    if change == 'runtime':
        state['runtime_manifest'] = dict(runtime, assembler='other-runtime')
    elif change == 'dtype':
        state['model'] = {k: v.float() if v.is_floating_point() else v for k, v in state['model'].items()}
    elif change == 'feature':
        state['feature_hash'] = 'f'*64
    elif change == 'test_only':
        state['config']['test_only'] = True
    else:
        state['update_index'] = 1
    torch.save(state, path)
    ledger()
    with pytest.raises((ValueError, RuntimeError)):
        R.authenticate_checkpoints(config, tmp_path, runtime, {0}, completed=False)


@pytest.mark.parametrize('change', ['qualification', 'test', 'scope', 'runtime', 'admission', 'config'])
def test_registered_run_authenticates_independent_expected_chain(tmp_path, monkeypatch, change):
    config = dict(qualification_only=False)
    admission = dict(status='GO', failures=[], source_sha256='expected-source', config_sha256='expected-config')
    runtime = dict(precision='float64', candidate_source_sha256='expected-source')
    monkeypatch.setattr(D, 'audit', lambda config: admission)
    monkeypatch.setattr(D, 'make_manifest', lambda config: runtime)
    write(tmp_path/'scope.json', dict(scope='registered-experiment', counted_registered_prefix=True,
        maximum_updates=32, minimum_qualification_seconds=None, checkpoint_or_data_promotion_allowed=False, test_only=False))
    write(tmp_path/'admission.json', admission)
    write(tmp_path/'runtime.json', dict(runtime, scope='registered-experiment'))
    assert R.authenticate_run(config, tmp_path)['scope'] == 'registered-experiment'
    if change == 'qualification':
        write(tmp_path/'qualification.json', dict(scope='separate-six-hour-qualification'))
    elif change == 'test':
        config['test_only'] = True
    elif change == 'scope':
        write(tmp_path/'scope.json', dict(scope='separate-six-hour-qualification', counted_registered_prefix=False))
    elif change == 'runtime':
        write(tmp_path/'runtime.json', dict(runtime, scope='registered-experiment', precision='float32'))
    elif change == 'admission':
        write(tmp_path/'admission.json', dict(admission, source_sha256='other-source'))
    else:
        write(tmp_path/'admission.json', dict(admission, config_sha256='other-config'))
    with pytest.raises(ValueError):
        R.authenticate_run(config, tmp_path)


@pytest.fixture
def row(tmp_path):
    from bot.pretrain_v1.tests.test_r45_reporting_contract import normal_row
    return normal_row(tmp_path)


def test_invalid_rows_and_missing_attempts_stay_missing_and_origins_are_mandatory(row):
    data, case, config = row
    def validate():
        return E.validate_result(data, case, policy='p', bank='b', runtime={}, config=config)
    assert validate() == 0
    data['invalid'] = True
    data.update(win=1, score=1)
    assert validate() is None
    data.pop('invalid'); data.update(win=0, score=.5)
    data['module_origins_after']['bot'] = '/wrong/tree/bot/__init__.py'
    with pytest.raises(ValueError, match='outside registered root'):
        validate()
    data['error'] = 'interrupted assigned attempt'
    assert validate() is None
    bounds = E.paired_bootstrap({0: None, 1: 1}, {0: 0, 1: None}, draws=128)
    assert bounds['complete_pairs']['n'] == 0 and bounds['all_assigned_lower']['n'] == 2
    assert not bounds['a_wins_by_registered_rule']


def test_pinned_historical_source_union_rejects_agreeing_truncated_inventories(tmp_path):
    bank = write(tmp_path/'bank.json', dict(cases=[dict(seed=s, own_deck=list(S.HOG), source_run=f'run{s}',
                                                    opponent_deck=list(S.HOG)) for s in (12, 13)]))
    inventory = dict(sources=[bank], seeds=[12, 13])
    assert X.validate(inventory)['seeds'] == [12, 13]
    inventory['seeds'] = [12]
    with pytest.raises(ValueError, match='source union'):
        X.validate(inventory)


def test_discovery_reconciles_aliases_and_detects_omitted_source(tmp_path):
    root = tmp_path/'history'; root.mkdir()
    bank = write(root/'bank.json', dict(cases=[dict(seed=12, own_deck=list(S.HOG), source_run='physical-12')]))
    (root/'bank-alias.json').symlink_to(root/'bank.json')
    doc = write(tmp_path/'runs.json', dict(runs=['physical-13']))
    inventory = X.discover([root], [Path(doc['path'])], tmp_path/'coverage.json')
    assert X.validate(inventory)['physical_source_ids'] == ['physical-12', 'physical-13']
    assert len(json.loads((tmp_path/'coverage.json').read_text())['files']) == 2
    inventory['seeds'] = [12, 13]
    with pytest.raises(ValueError, match='source union'):
        X.validate(inventory)


def test_cpu_reporting_verifies_cuda_checkpoint_without_restoring_cuda_rng(checkpoint, tmp_path):
    config, runtime, proof, path, ledger = checkpoint
    state = torch.load(path, weights_only=False)
    state['cuda_rng'] = [torch.zeros(128, dtype=torch.uint8)]
    torch.save(state, path); ledger()
    assert R.authenticate_checkpoints(config, tmp_path, runtime, {0}, completed=False) == {0: proof.policy_sha256}


@pytest.mark.parametrize('phase', ['primary-bc', 'primary-final', 'dev-0', 'dev-10', 'dev-20', 'dev-30'])
@pytest.mark.parametrize('change', ['policy', 'runtime', 'source', 'config', 'checkpoint', 'version'])
def test_each_phase_rejects_self_consistent_stale_manifest(checkpoint, tmp_path, monkeypatch, phase, change):
    config, runtime, proof, path, _ = checkpoint
    # Tiny raw checkpoints still exercise real file hashes and real alternate
    # policy hashes. Run/ledger authentication has its own tests above.
    alternate = copy.deepcopy(proof.model)
    with torch.no_grad():
        next(alternate.parameters()).add_(.02)
    from bot.pretrain_v1 import rl_learner as L
    alternate_policy = L.policy_sha256(alternate, proof.feature_hash)
    version = {'primary-bc': 0, 'primary-final': 32}.get(phase, int(phase.split('-')[-1]) if phase.startswith('dev-') else 0)
    checkpoint_path = tmp_path/f'checkpoints/update-{version:02d}.pt'
    if version:
        checkpoint_path.write_bytes(path.read_bytes())
    case = dict(index=0, seed=12, seat=0, decks=[list(S.HOG), list(S.HOG)])
    config.update(size='M', seed=S.SEEDS[0], banks={})
    banks = dict(primary=[case], dev={str(v): [case] for v in (0, 10, 20, 30)})
    bank_ref = write(tmp_path/'bank.json', banks)
    config['banks'] = bank_ref
    write(tmp_path/'config.json', config)
    write(tmp_path/'stopped.json', dict(status='stopped'))
    monkeypatch.setattr(D, 'read_config', lambda _: config)
    monkeypatch.setattr(R, 'authenticate_run', lambda *args: runtime)
    monkeypatch.setattr(R, 'authenticate_checkpoints', lambda *args, **kwargs: dict.fromkeys((0, 10, 20, 30, 32), proof.policy_sha256))
    monkeypatch.setattr(S, 'validate_banks', lambda value, seed: value)
    manifest = R.phase_manifest(config, tmp_path, runtime, version, [case], proof.policy_sha256)
    if change == 'policy': manifest['policy_sha256'] = alternate_policy
    elif change == 'runtime': manifest['runtime_manifest'] = dict(runtime, assembler='alternate')
    elif change == 'source': manifest['source_sha256'] = 'wrong-source'
    elif change == 'config': manifest['config_sha256'] = 'wrong-config'
    elif change == 'checkpoint': manifest['checkpoint'] = dict(path=str(tmp_path/'alternate.pt'), sha256='e'*64)
    else: manifest['version'] = (version+1) % 33
    write(tmp_path/f'evaluation/{phase}/manifest.json', manifest)
    with pytest.raises(ValueError, match='phase/checkpoint provenance'):
        Summary.load_arm(tmp_path, 'M')


def test_freezer_rejects_legacy_unsearched_inventory_before_output(tmp_path):
    from bot.pretrain_v1.tests.test_rl_driver import populations
    bank = write(tmp_path/'prior.json', dict(cases=[dict(seed=12, own_deck=list(S.HOG))]))
    train = dict(populations(), role='training-only', physical_source_ids=['history'], sources=[bank])
    evaluation = dict(populations(), role='evaluation-only', physical_source_ids=['heldout'], sources=[bank])
    bundle = dict(populations=write(tmp_path/'train.json', train), evaluation_populations=write(tmp_path/'eval.json', evaluation),
                  excluded_seeds=write(tmp_path/'seeds.json', dict(sources=[bank], seeds=[12])))
    with pytest.raises(ValueError, match='audited historical'):
        F.freeze(bundle, tmp_path/'must-not-exist')
    assert not (tmp_path/'must-not-exist').exists()


def test_freezer_new_audited_inventory_pairs_all_seeds_and_rejects_derived_contamination(tmp_path):
    from bot.pretrain_v1.tests.test_rl_driver import populations
    root = tmp_path/'history'; root.mkdir()
    source = write(root/'prior.json', dict(cases=[dict(seed=12, own_deck=list(S.HOG), source_run='excluded-physical')]))
    document = tmp_path/'prereg.md'; document.write_text('Fixture historical scope\n')
    inventory = X.discover([root], [document], tmp_path/'coverage.json')
    excluded_ref = write(tmp_path/'excluded.json', inventory)
    train = dict(populations(), role='training-only', physical_source_ids=['fixture-history', 'fixture-adjacent'],
                 sources=[source], exclusion_inventory=excluded_ref)
    evaluation = copy.deepcopy(train)
    evaluation.update(role='evaluation-only', physical_source_ids=['heldout-history', 'heldout-adjacent'])
    for rows in list(evaluation['opponents'].values())+[evaluation['meta']]:
        for row in rows:
            row['source_id'] = row['source_id'].replace('fixture-', 'heldout-')
    bundle = dict(populations=write(tmp_path/'train.json', train), evaluation_populations=write(tmp_path/'eval.json', evaluation),
        excluded_seeds=excluded_ref, audits=dict(defense=source, spell=source),
        audit_input_manifest=write(tmp_path/'audits.json', [source]), evaluation_seed_base=20261022000000,
        common={}, anchors=dict.fromkeys(S.ANCHORS, source), model_cfg=dict.fromkeys(S.ANCHORS, source))
    assert len(F.freeze(bundle, tmp_path/'frozen')) == 8
    seen = set(inventory['seeds'])
    for seed in S.SEEDS:
        m = json.loads((tmp_path/f'frozen/M-{seed}.json').read_text())
        s = json.loads((tmp_path/f'frozen/S100-{seed}.json').read_text())
        assert m['banks'] == s['banks']
        banks = json.loads(S.pinned(m['banks']).read_text())
        seeds = {c['seed'] for c in banks['primary']+banks['dev']['0']}
        assert len(seeds) == 1800 and not seeds & seen
        seen.update(seeds)
    for field in ('stress', 'meta'):
        bad = copy.deepcopy(train)
        row = bad['meta'][0] if field == 'meta' else bad['opponents']['stress'][0]
        row['physical_source_id'] = 'excluded-physical'
        bundle['populations'] = write(tmp_path/f'bad-{field}.json', bad)
        with pytest.raises(ValueError, match='contamination'):
            F.freeze(bundle, tmp_path/f'bad-output-{field}')
        assert not (tmp_path/f'bad-output-{field}').exists()
    bad = copy.deepcopy(train)
    bad['opponents']['adjacent'] = []
    bundle['populations'] = write(tmp_path/'insufficient.json', bad)
    with pytest.raises(ValueError, match='missing opponent stratum'):
        F.freeze(bundle, tmp_path/'insufficient-output')
    assert not (tmp_path/'insufficient-output').exists()


@pytest.mark.parametrize('change', ['missing', 'missing_harness', 'wrong_named_module'])
def test_successful_rows_require_complete_matching_module_origins(row, change):
    data, case, config = row
    if change == 'missing':
        data.pop('module_origins_after')
    elif change == 'missing_harness':
        data['module_origins_after'].pop('bot.pretrain_v1.sim_ours')
    else:
        data['module_origins_after']['bot.players.ours'] = data['module_origins_after']['bot.rl.actor']
    with pytest.raises(ValueError, match='module'):
        E.validate_result(data, case, policy='p', bank='b', runtime={}, config=config)
