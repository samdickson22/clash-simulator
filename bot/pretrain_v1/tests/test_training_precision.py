"""Configuration-only admission checks. No registered update or GPU execution."""
from dataclasses import replace

import pytest
import torch

from bot.pretrain_v1 import rl_learner as L
from bot.pretrain_v1.tests.test_rl_learner import admitted, cpu_threads


@pytest.mark.parametrize('size', ('S100', 'M'))
@pytest.mark.parametrize('seed', L.SEEDS)
def test_registered_fp64_requires_explicit_identity_and_keeps_equal_budget(size, seed):
    base = L.LearnerConfig(seed=seed, size=size)
    with pytest.raises(L.ContractError, match='explicit training precision registration'):
        replace(base, precision='float64')
    actual = replace(base, precision='float64', precision_registration=L.FP64_TRAINING_REGISTRATION)
    old = base.record()
    new = actual.record()
    assert new.pop('precision_registration') == L.FP64_TRAINING_REGISTRATION
    assert new.pop('dtype') == 'float64'
    assert old.pop('dtype') == 'float32'
    assert new == old
    assert (actual.steps_per_update, actual.updates, actual.batch_size, actual.microbatch) == (262144, 32, 2048, 128)
    assert not actual.test_only


@pytest.mark.parametrize('fields', (
    dict(steps_per_update=2048), dict(updates=4), dict(batch_size=1024), dict(microbatch=64),
    dict(precision_registration='other'), dict(precision='float32'), dict(test_only=True),
))
def test_registration_does_not_bypass_other_production_guards(fields):
    config = dict(seed=L.SEEDS[0], size='M', precision='float64',
                  precision_registration=L.FP64_TRAINING_REGISTRATION)
    config.update(fields)
    with pytest.raises(L.ContractError):
        L.LearnerConfig(**config)


def test_default_and_qualification_records_keep_prior_schema():
    default = L.LearnerConfig(seed=L.SEEDS[0], size='M')
    qualified = replace(default, precision='float64', test_only=True)
    for config in (default, qualified):
        assert 'precision_registration' not in config.record()
        assert 'precision' not in config.record()
    assert qualified.record()['dtype'] == 'float64'
    assert default.record()['dtype'] == 'float32'


def test_registration_is_bound_into_checkpoint_without_casting_or_resume_escape(admitted, tmp_path):
    config = L.LearnerConfig(seed=L.SEEDS[0], size='M', precision='float64',
                             precision_registration=L.FP64_TRAINING_REGISTRATION)
    # Toy fixture weights, no optimizer update or generated environment data.
    original = L.Learner(**admitted, config=config)
    assert all(p.dtype == torch.float64 for m in (original.model, original.anchor) for p in m.parameters())
    assert all(p is q for p, q in zip(original.model.parameters(), original.optimizer.param_groups[0]['params']))
    path = tmp_path/'registered.pt'
    original.save_checkpoint(path)
    stored = torch.load(path, map_location='cpu', weights_only=False)
    assert stored['config']['precision_registration'] == L.FP64_TRAINING_REGISTRATION
    assert stored['generated_steps'] == stored['trained_steps'] == stored['optimizer_steps'] == 0
    restored = L.Learner(**admitted, config=config)
    restored.load_checkpoint(path)
    assert restored.policy_sha256 == original.policy_sha256
    stored['config'].pop('precision_registration')
    altered = tmp_path/'missing-registration.pt'
    torch.save(stored, altered)
    with pytest.raises(L.ContractError, match='checkpoint config mismatch'):
        L.Learner(**admitted, config=config).load_checkpoint(altered)
    qualification = replace(config, precision_registration='', test_only=True)
    with pytest.raises(L.ContractError, match='checkpoint config mismatch'):
        L.Learner(**admitted, config=qualification).load_checkpoint(path)
