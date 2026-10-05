"""Live frozen-v5 comparison, with no mutations to either baseline or fixtures."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest
from clasher.rl import council_pilot as cp

KIT = Path(__file__).resolve().parent
RC = KIT.parents[1]
V5 = RC / 'm0/runtime-snapshots/pilot-runtime-v5'
V6 = V5.with_name('pilot-runtime-v6')
ADMITTED = V5.with_name('native-final-v7')
ADMISSION = json.loads((RC / 'm0/readiness/tier-a-fresh-v7/admission.json').read_text())
spec = importlib.util.spec_from_file_location('clasher.rl._council_v5_reference', V5 / 'src/clasher/rl/council_pilot.py')
old = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = old
spec.loader.exec_module(old)


def scope(module, root):
    return module.verify_pilot_source_scope(pilot_root=root, admitted_root=ADMITTED,
        admitted_pins=ADMISSION['source_pins'],
        pilot_pins=json.loads((root / 'pilot-source-pins.json').read_text()))


@pytest.mark.parametrize('seed', [2901, 2902])
@pytest.mark.parametrize('phase', ['smoke', 'nominal', 'nominal-league'])
def test_v7r4h_command_and_bindings_byte_identical(seed, phase):
    path = KIT.with_name('v7r4h-launch') / 'configs' / f'council-pilot-v7r4h-seed{seed}.toml'
    previous, current = old.load_pilot_config(path), cp.load_pilot_config(path)
    kwargs = dict(config_path=path, admission=Path(current.nominal_admission_path), seed=seed,
        arm='scripted', phase=phase, pool_path=Path('/tmp/pool.json'), initialization=Path('/tmp/init.pt'))
    assert '\0'.join(cp.training_command(current, **kwargs)).encode() == '\0'.join(old.training_command(previous, **kwargs)).encode()
    assert json.dumps(cp.training_recipe(current), sort_keys=True) == json.dumps(old.training_recipe(previous), sort_keys=True)
    assert json.dumps(scope(cp, V5), sort_keys=True).encode() == json.dumps(scope(old, V5), sort_keys=True).encode()


@pytest.mark.parametrize('seed', [2901, 2902])
def test_v7r5_cli_and_source_bindings(seed):
    path = KIT / 'configs' / f'council-pilot-v7r5-seed{seed}.toml'
    config = cp.load_pilot_config(path)
    argv = cp.training_command(config, config_path=path, admission=Path(config.nominal_admission_path),
        seed=seed, arm='scripted', phase='nominal', pool_path=Path('/tmp/pool.json'), initialization=Path('/tmp/init.pt'))
    for flag, value in [('recurrent-update-mode', 'stored-state'), ('tbptt-chunk', '32'), ('tbptt-burn-in', '16')]:
        assert argv[argv.index('--' + flag) + 1] == value
    report = scope(cp, V6)
    assert len(report['admission_bound']) == 342
    assert len(report['training_only']) == 10
    assert 'src/clasher/rl/tbptt.py' in report['training_only_changed']


def test_tbptt_exceptions_cannot_override_admission_imports(monkeypatch):
    original = cp._imports_from_training_only
    def importing_ppo(*args, **kwargs):
        result = original(*args, **kwargs)
        result.setdefault('src/clasher/rl/train_recurrent.py', set()).add('ppo_update')
        return result
    monkeypatch.setattr(cp, '_imports_from_training_only', importing_ppo)
    with pytest.raises(ValueError, match='admission-bound definition .* changed'):
        scope(cp, V6)
