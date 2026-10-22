"""Read-only authentication of registered evaluation evidence. No engine imports."""
import json
from pathlib import Path

from . import rl_schedule as S


def read(path):
    return json.loads(Path(path).read_text())


def authenticate_run(config, out):
    from . import rl_driver as D
    out = Path(out)
    S.require(config.get('qualification_only', False) is False and config.get('test_only', False) is False
              and not (out/'qualification.json').exists(), 'qualification/test evidence is not registered')
    scope = dict(scope='registered-experiment', counted_registered_prefix=True, maximum_updates=32,
                 minimum_qualification_seconds=None, checkpoint_or_data_promotion_allowed=False, test_only=False)
    S.require(read(out/'scope.json') == scope, 'registered scope mismatch')
    # Recompute gates and all pinned inputs. Saved admission is evidence, never authority.
    admission = D.audit(config)
    S.require(admission['status'] == 'GO', 'registered admission failed: '+repr(admission['failures']))
    S.require(read(out/'admission.json') == admission, 'saved admission/source/config mismatch')
    runtime = dict(D.make_manifest(config), scope='registered-experiment')
    S.require(read(out/'runtime.json') == runtime, 'saved registered runtime mismatch')
    return runtime


def learner(config, runtime):
    from . import rl_learner as L
    return L.Learner(S.pinned(config['anchor']), anchor_sha256=config['anchor']['sha256'],
        model_cfg=read(S.pinned(config['model_cfg'])), runtime_manifest=runtime,
        config=L.LearnerConfig(seed=config['seed'], size=config['size'], precision=config['precision'],
                              microbatch=128, precision_registration=config['precision_registration_id']), device='cpu')


def verify_checkpoint(proof, path, version):
    """Check serialized learner state on CPU without restoring CUDA/process RNGs."""
    import torch
    from . import rl_learner as L
    state = torch.load(path, map_location='cpu', weights_only=False)
    for key, value in dict(format=1, config=proof.config.record(), model_cfg=proof.model.cfg,
            feature_hash=proof.feature_hash, anchor_sha256=proof.anchor_sha256, selection=proof.selection,
            anchor_state_sha256=proof._anchor_state_sha256, runtime_manifest=proof.runtime_manifest,
            provenance_sha256=proof.provenance_sha256, update_index=version, halted_reason=None,
            generated_steps=version*proof.config.steps_per_update, trained_steps=version*proof.config.steps_per_update,
            optimizer_steps=version*proof.config.record()['optimizer_steps_per_update']).items():
        S.require(state.get(key) == value, 'checkpoint '+key+' mismatch')
    for key, model in (('model', proof.model), ('anchor', proof.anchor)):
        expected, actual = model.state_dict(), state[key]
        S.require(set(actual) == set(expected) and all(isinstance(actual[k], torch.Tensor)
                  and actual[k].dtype == t.dtype and actual[k].shape == t.shape
                  and bool(torch.isfinite(actual[k]).all()) for k, t in expected.items()),
                  'checkpoint '+key+' keys/dtypes/shapes/finite mismatch')
        model.load_state_dict(actual, strict=True)
    S.require(L.policy_sha256(proof.anchor, proof.feature_hash) == proof._anchor_state_sha256,
              'checkpoint anchor state hash mismatch')
    policy = L.policy_sha256(proof.model, proof.feature_hash)
    S.require(policy == state['policy_sha256'], 'checkpoint policy state hash mismatch')
    # Reuse the core's participation/shuffle derivation, without resuming a run.
    counters = proof._checkpoint_optimizer_counters(state)
    stored = state['optimizer']
    expected = proof.optimizer.state_dict()
    S.require(stored['param_groups'] == expected['param_groups'], 'checkpoint optimizer configuration mismatch')
    S.require(all(type(pid) is int for pid in stored['state']) and set(stored['state']) == set(counters),
              'checkpoint optimizer initialized parameter set mismatch')
    parameters = dict(zip(expected['param_groups'][0]['params'], proof.model.parameters()))
    for pid, values in stored['state'].items():
        S.require(set(values) == {'step', 'exp_avg', 'exp_avg_sq'}, 'checkpoint optimizer state keys mismatch')
        parameter = parameters[pid]
        for key in ('exp_avg', 'exp_avg_sq'):
            value = values[key]
            S.require(isinstance(value, torch.Tensor) and value.dtype == parameter.dtype
                      and value.shape == parameter.shape and bool(torch.isfinite(value).all()),
                      'checkpoint optimizer moment dtype/shape mismatch')
        step = values['step']
        S.require(isinstance(step, torch.Tensor) and step.dtype == torch.float32 and step.ndim == 0
                  and float(step) == counters[pid], 'checkpoint optimizer step counter mismatch')
    return policy


def phase_manifest(config, out, runtime, version, cases, policy):
    from . import rl_driver as D
    checkpoint = Path(out)/f'checkpoints/update-{version:02d}.pt'
    return dict(assigned=list(range(len(cases))), bank_sha256=S.digest(cases), policy_sha256=policy,
                runtime_manifest=runtime, source_sha256=D.source_digest(),
                config_sha256=D.registration_identity(config), version=version,
                checkpoint=dict(path=str(checkpoint.resolve()), sha256=S.file_sha(checkpoint)))


def authenticate_checkpoints(config, out, runtime, versions, *, completed):
    """Verify the ledger chain, then load each requested policy with the strict CPU loader."""
    from . import rl_learner as L
    out = Path(out)
    expected = learner(config, runtime)
    initial_policy = expected.policy_sha256
    versions = set(versions) | {0}
    last = 32 if completed else max(versions)
    previous, ledgers = None, {}
    for version in range(last+1):
        directory = out/'checkpoints'
        path = directory/f'update-{version:02d}.pt'
        ledger = read(path.with_suffix('.json'))
        for key, value in dict(schema=1, test_only=False, version=version,
                config=dict(wait_seconds=config['wait_seconds'], test_only=False),
                learner_config=expected.config.record(), anchor_sha256=expected.anchor_sha256,
                model_cfg=expected.model.cfg, model_cfg_sha256=S.digest(expected.model.cfg),
                feature_hash=expected.feature_hash, runtime_manifest=runtime,
                provenance_sha256=expected.provenance_sha256, previous_checkpoint_sha256=previous,
                engine_resume_qualified=False).items():
            S.require(ledger.get(key) == value, f'checkpoint ledger {version} {key} mismatch')
        S.require(ledger['learner_checkpoint'] == dict(file=path.name, sha256=S.file_sha(path)),
                  'checkpoint file/ledger mismatch')
        ledgers[version] = ledger
        previous = S.digest(ledger)
    policies = {}
    for version in sorted(versions):
        # Verify raw state before load_state_dict can silently cast its dtype.
        proof = expected if version == 0 else learner(config, runtime)
        policy = verify_checkpoint(proof, out/f'checkpoints/update-{version:02d}.pt', version)
        S.require(policy == ledgers[version]['policy_sha256'], 'checkpoint policy/version mismatch')
        if version == 0:
            S.require(policy == initial_policy, 'update00 is not the verified own BC start')
        policies[version] = policy
        del proof
    if completed:
        final = read(out/'checkpoints/final-manifest.json')
        saved = read(out/'completed.json')
        S.require(saved['status'] == 'training_complete' and saved['optimizer_resume_proof'] is True
                  and saved['final'] == final, 'completion record/final ledger mismatch')
        for key in ('test_only', 'version', 'config', 'learner_config', 'anchor_sha256', 'model_cfg',
                    'model_cfg_sha256', 'feature_hash', 'runtime_manifest', 'provenance_sha256', 'policy_sha256'):
            S.require(final[key] == ledgers[32][key], 'final checkpoint identity mismatch: '+key)
        S.require(final['checkpoint_sha256'] == previous and final['generated'] == final['accepted'] ==
                  final['trained'] == 8388608 and final['discarded'] == 0 and final['updates'] == 32,
                  'unequal/incomplete training budget or final checkpoint chain')
    return policies


def validate_origins(origins, config):
    """Validate retained module locations against pinned file bytes, without importing them."""
    from . import rl_driver as D
    required = {'bot', 'clasher', 'bot.pretrain_v1', 'bot.pretrain_v1.rl_evaluate',
                'bot.pretrain_v1.rl_driver', 'bot.pretrain_v1.sim_ours', 'bot.pretrain_v1.model',
                'bot.players.ours', 'bot.rl.actor'}
    S.require(isinstance(origins, dict) and required <= set(origins), 'missing evaluation module origins')
    lineage = read(S.pinned(config['runtime_manifest']))
    candidate = D.ROOT/'bot/pretrain_v1'
    candidate_files = {str(p.relative_to(candidate)): S.file_sha(p) for p in candidate.rglob('*.py')}
    for name, value in origins.items():
        S.require(isinstance(value, str), 'invalid evaluation module origin')
        if name == 'clasher' or name.startswith('clasher.'):
            root, files = Path(config['runtime']).resolve(), lineage['files']
        elif name == 'bot.pretrain_v1' or name.startswith('bot.pretrain_v1.'):
            root, files = candidate, candidate_files
        else:
            S.require(name == 'bot' or name.startswith('bot.'), 'unexpected module origin')
            root, files = Path(config['actor_source']).resolve(), lineage['source_files']
        path = Path(value).resolve()
        S.require(path.is_relative_to(root), 'evaluation module outside registered root: '+name)
        relative = str(path.relative_to(root))
        S.require(relative in files and S.file_sha(path) == files[relative], 'unregistered evaluation module: '+name)
        module = name.removeprefix('bot.pretrain_v1.').replace('.', '/') if root == candidate else name.replace('.', '/')
        if name == 'bot.pretrain_v1':
            module = ''
        allowed = {module+'.py', module+'/__init__.py'} if module else {'__init__.py'}
        S.require(relative in allowed or path.suffix == '.so' and str(Path(relative).parent) == str(Path(module).parent)
                  and path.name.startswith(Path(module).name+'.'), 'evaluation module name/path mismatch: '+name)
