"""Protocol tests use fake runtime metadata; no frozen runtime or native engine."""
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
from types import ModuleType, SimpleNamespace

import numpy as np
import pytest

# Bind the helper's base class before level_cache replaces its constructor.
from . import bank, fixture_support, profile, report, run


def fake_runtime():
    loader = SimpleNamespace(get_card=lambda _: SimpleNamespace(rarity='common'))
    return SimpleNamespace(R=SimpleNamespace(builder=SimpleNamespace(loader=loader)),
                           PRIOR={'decks': [dict(cards=list(profile.LIVE_DECK), frequency=10)]})


def test_bank_determinism(tmp_path, monkeypatch):
    source = tmp_path / 'reports/live/loop/opponent-decks.jsonl'
    source.parent.mkdir(parents=True)
    source.write_text('\n'.join(json.dumps(dict(run=f'row-{i}', opp_trophies=t,
                      opp_deck=list(profile.LIVE_DECK))) for i, t in enumerate((599, 600, 750))))
    monkeypatch.setattr(bank, 'REPO', tmp_path)
    monkeypatch.setattr(bank, 'utcnow', lambda: '2026-10-16T00:00:00Z')
    path = tmp_path / 'cases.json'
    first = bank.build(fake_runtime(), 1, 8, path)
    raw = path.read_bytes()
    monkeypatch.setattr(bank, 'utcnow', lambda: '2026-10-17T00:00:00Z')
    assert bank.build(fake_runtime(), 1, 8, path) == first
    assert path.read_bytes() == raw
    second = bank.build(fake_runtime(), 1, 8, tmp_path / 'other.json')
    assert first['cases'] == second['cases']
    assert len(first['pool']) == 2
    assert [c['opponent'] for c in first['cases'][:4]] == ['R3a', 'R3a', 'v1', 'v1']
    assert [c['seat'] for c in first['cases'][:4]] == [0, 1, 0, 1]
    with pytest.raises(FileExistsError, match='different bank'):
        bank.build(fake_runtime(), 2, 8, path)


def test_projection_ties():
    catalog = [dict(cards=['A', 'Z'], frequency=2), dict(cards=['A', 'B'], frequency=2),
               dict(cards=['A', 'C'], frequency=1), dict(cards=['Q', 'X'], frequency=100)]
    assert bank.project(['A', 'missing'], catalog) == (['A', 'B'], 1)
    catalog[0]['frequency'] = 3
    assert bank.project(['A', 'missing'], catalog) == (['A', 'Z'], 1)
    assert bank.project(['Q', 'X'], catalog) == (['Q', 'X'], 2)


def test_report_bootstrap(tmp_path):
    rows = tmp_path / 'rows'
    rows.mkdir()
    deltas = []
    for i, (a, b) in enumerate(((0, 1), (.5, .5), (1, 0), (0, .5))):
        deltas.append(b-a)
        for arm, score in [('A', a), ('B', b)]:
            row = dict(arm=arm, index=i, seed=i, seat=i % 2, opponent='R3a' if i < 2 else 'v1',
                       score=score, terminal=True, failures={}, child_exit_code=0,
                       channels={'0': {'rejected': 0}, '1': {'rejected': 0}},
                       profile={'towers': [6, 6]}, towers={'0': [3312, 1930, 2030],
                       '1': [3312, 2030, 1830]}, crowns={'0': 0, '1': 1},
                       cpu_seconds=10, wall_seconds=11, timing={'0': dict(cpu=2, decisions=4),
                       '1': dict(cpu=2, decisions=4)}, command_sha256='same' if i == 0 else arm,
                       play_log=[[100 if arm == 'A' else 110, 'Archers', 1, True]])
            (rows / f'{arm}-{i:05d}.json').write_text(json.dumps(row))
    (rows / 'B-00004.json').write_text(json.dumps(dict(arm='B', index=4, error='test error')))
    result = report.summarize(tmp_path)
    p = result['arms']['B']['paired']
    expected = np.array(deltas)
    rng = np.random.default_rng(0)
    ci = np.percentile(expected[rng.integers(4, size=(20_000, 4))].mean(axis=1), [2.5, 97.5])
    assert p['ci95'] == pytest.approx(ci)
    assert p['mean_delta_score'] == pytest.approx(expected.mean())
    assert p['delta_score_sd'] == pytest.approx(expected.std(ddof=1))
    assert p['pairs'] == 4
    assert p['opponents']['R3a']['pairs'] == 2
    assert p['identical_command_share'] == .25
    assert p['first_difference_tick_median'] == 100
    assert result['arms']['B']['errors'] == 1
    assert result['arms']['A']['cpu_seconds_per_decision'] == .5
    assert result['arms']['A']['damage_dealt'] == 150
    assert '80% power' in report.markdown(result)
    assert report.summarize(tmp_path) == result


def test_tower_curve_and_log_prefix():
    assert report.tower_hp('king', 6) == 3312
    assert report.tower_hp('princess', 6) == 2030
    assert report.tower_hp('princess', 11) == 3052
    assert report.first_difference([], [[7, 'X', 2, True]]) == 7
    assert report.first_difference([], []) is None


def gate_case():
    return dict(index=0, seed=1, seat=0, opponent='v1', decks=[['Own'], ['Enemy']],
                profile=dict(cards=[{'Own': 11}, {'Enemy': 11}], towers=[11, 11]),
                view=dict(own_levels={'Own': 11}, own_tower=11, opp_tower=11))


@pytest.mark.parametrize('extra', [
    ['--workers', '0'], ['--workers', '16'], ['--workers', '-1'],
    ['--work', '2'], ['--base-player', 'K4L-R-gs-rw-fc-t4-p4'],
    ['--all11-gate', '--arms', 'A,B0'], ['--all11-gate', '--arms', 'A'],
    ['--all11-gate', '--arms', 'B'],
])
def test_runner_rejects_unsafe_options(extra, monkeypatch):
    monkeypatch.setenv('PYTHONHASHSEED', '0')
    with pytest.raises(SystemExit) as exc:
        run.parse_args(['--out', 'unused', '--bank', 'unused', *extra])
    assert exc.value.code == 2


def test_runner_gate_and_worker_boundaries(monkeypatch):
    monkeypatch.setenv('PYTHONHASHSEED', '0')
    for workers in (1, 15):
        args = run.parse_args(['--out', 'unused', '--bank', 'unused', '--workers', str(workers),
                               '--arms', 'A,B', '--all11-gate'])
        assert args.workers == workers and args.all11_gate
    monkeypatch.setenv('PYTHONHASHSEED', '1')
    with pytest.raises(SystemExit):
        run.parse_args(['--out', 'unused', '--bank', 'unused'])


@pytest.mark.parametrize('field, value', [
    (('profile', 'cards', 0, 'Own'), 7),
    (('profile', 'cards', 1, 'Enemy'), 5),
    (('profile', 'towers', 0), 6),
    (('profile', 'towers', 1), 6),
    (('view', 'own_tower'), 6),
    (('view', 'opp_tower'), 6),
    (('view', 'own_levels', 'Own'), 7),
    (('view', 'own_levels', 'Extra'), 7),
    (('profile', 'cards', 1), {}),
    (('view', 'own_levels'), {}),
])
def test_all11_requires_both_true_seats_and_full_view(field, value):
    case = gate_case()
    run.validate_all11(case)
    target = case
    for key in field[:-1]:
        target = target[key]
    target[field[-1]] = value
    with pytest.raises(ValueError, match='level-11'):
        run.validate_all11(case)


@pytest.fixture
def identity_inputs(tmp_path, monkeypatch):
    runtime = tmp_path / 'runtime'
    runtime.mkdir()
    envfile = tmp_path / 'env.sh'
    envfile.write_text('export PYTHONHASHSEED=0\n')
    model = tmp_path / 'models/pool.npz'
    model.parent.mkdir()
    model.write_bytes(b'learned rollout weights')
    repository = tmp_path / 'repo'
    for path in [runtime / 'main02.pt', runtime / 'R3a.pt', runtime / 'gamedata.json',
                 runtime / 'native/clasher_core.abi3.so', runtime / 'src/engine.py',
                 runtime / 'src/clasher/rl/contract_v5_tokens.json',
                 runtime / 'reports/strategy_council_20260928/c56/engine/root-v3/human_deck_catalog.json',
                 repository / 'bot/players/royalesim_vocab.json', repository / 'bot/players/runtime.py',
                 repository / 'bot/live/levels.py']:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{}')
    simulator = tmp_path / 'royalesim.so'
    simulator.write_bytes(b'simulator')
    monkeypatch.setattr(run.util, 'find_spec', lambda _: SimpleNamespace(origin=str(simulator), submodule_search_locations=[]))
    monkeypatch.setattr(run.metadata, 'version', lambda _: 'test-version')
    monkeypatch.setattr(run, 'ENV_PATH', envfile)
    monkeypatch.setattr(run, 'REPO', repository)
    monkeypatch.setenv('CLASHER_BOT_RUNTIME', str(runtime))
    monkeypatch.setenv('CLASHER_ROOT', str(runtime))
    monkeypatch.setenv('CLASHER_EVAL_RUNTIME_ROOT', str(runtime))
    monkeypatch.setenv('CLASHER_DELAY_NATIVE_DIR', str(runtime / 'native'))
    monkeypatch.setenv('CLASHER_LOPP_MODELS', str(model.parent))
    monkeypatch.setenv('CLASHER_BOT_RUNTIME_PINS', 'live16402b-r2')
    monkeypatch.setenv('PYTHONHASHSEED', '0')
    args = SimpleNamespace(base_player=run.BASE_PLAYER, client='16.402', all11_gate=False, arms='A,B')
    rt = SimpleNamespace(root=runtime, pins={'native': 'pin'}, PRIOR={'decks': []},
                         levels_scope={'restricted_sha256': run.digest({'decks': []})},
                         R=SimpleNamespace(config={}), STUDENT=object())
    return SimpleNamespace(args=args, rt=rt, envfile=envfile, model=model, repository=repository)


def identity_for(fixture, manifest=None):
    return run.invocation_identity(fixture.args, fixture.rt, {}, manifest,
        run.runtime_files(fixture.rt.root), run.source_hashes(), 'bank-digest')


def test_runtime_identity_binds_exact_placement_proof_and_installed_data(identity_inputs, tmp_path, monkeypatch):
    f = identity_inputs
    data = tmp_path/'simulator-data'
    for relative in ('calibration.json', 'derived/arena.json', 'derived/cards.json'):
        path = data/relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{}')
    proof = tmp_path/'placement-proof.json'
    value = {'identity': {'data_path': str(data)}}
    proof.write_text(json.dumps(value))
    monkeypatch.setenv('CLASHER_LEVELS_PLACEMENT_PROOF', str(proof))
    first = run.runtime_files(f.rt.root)
    assert first[str(proof.resolve())] == run.hashlib.sha256(proof.read_bytes()).hexdigest()
    assert all(str((data/p).resolve()) in first for p in
               ('calibration.json', 'derived/arena.json', 'derived/cards.json'))
    proof.write_text(json.dumps(value, indent=2))
    second = run.runtime_files(f.rt.root)
    assert first[str(proof.resolve())] != second[str(proof.resolve())]
    (data/'derived/arena.json').write_text('{"changed": true}')
    third = run.runtime_files(f.rt.root)
    assert second[str((data/'derived/arena.json').resolve())] != third[str((data/'derived/arena.json').resolve())]


@pytest.mark.parametrize('relative', [
    'imitation/evaluation/standalone.py', 'imitation/evaluation/d1.py', 'imitation/model/features.py',
    'reports/strategy_council_20260928/imitation/proposals.py',
    'reports/strategy_council_20260928/c56/engine/root-v3/belief.py',
])
def test_serving_python_mutation_changes_identity_and_refuses_resume(identity_inputs, tmp_path, relative):
    f = identity_inputs
    serving = f.rt.root/relative
    serving.parent.mkdir(parents=True, exist_ok=True)
    serving.write_text('original serving implementation\n')
    first = identity_for(f)
    assert str(serving.resolve()) in first['runtime_files']
    case = gate_case()
    path = tmp_path/'A-00000.json'
    path.write_text(json.dumps(with_prior_evidence(dict(clean_row('A', case), **first))))
    assert run.resume_done(path, case, 'A', first)
    serving.write_text('changed serving implementation\n')
    changed = identity_for(f)
    assert changed['runtime_files'] != first['runtime_files']
    assert all(changed[k] == first[k] for k in first if k != 'runtime_files')
    assert all(changed['runtime_files'][str(p.resolve())] == first['runtime_files'][str(p.resolve())]
               for p in (f.rt.root/'main02.pt', f.rt.root/'R3a.pt', f.model, f.rt.root/'gamedata.json'))
    with pytest.raises(ValueError, match='runtime_files'):
        run.resume_done(path, case, 'A', changed)


@pytest.mark.parametrize('relative', ['src/clasher/rl/public_action_mask.py', 'engine-rs/fair_player.py',
    'reports/strategy_council_20260928/imitation/proposals.py',
    'reports/strategy_council_20260928/engine-speed/stage5b-r3/score.py',
    'reports/strategy_council_20260928/c56/engine/root-v3/belief.py'])
def test_paths_setup_selected_engine_root_is_bound(identity_inputs, tmp_path, monkeypatch, relative):
    serving = tmp_path/'selected-engine-root'
    path = serving/relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('original selected serving source\n')
    token = serving/'src/clasher/rl/contract_v5_tokens.json'
    token.parent.mkdir(parents=True, exist_ok=True)
    token.write_text('{}')
    monkeypatch.setenv('CLASHER_EVAL_RUNTIME_ROOT', str(serving))
    first = identity_for(identity_inputs)
    assert str(path.resolve()) in first['runtime_files']
    path.write_text('changed selected serving source\n')
    assert identity_for(identity_inputs)['runtime_files'] != first['runtime_files']


@pytest.fixture(params=['normal', 'eval_override', 'root_fallback'])
def serving_tokens(identity_inputs, tmp_path, monkeypatch, request):
    f = identity_inputs
    normal = f.rt.root/'src/clasher/rl/contract_v5_tokens.json'
    selected = normal
    if request.param != 'normal':
        serving = tmp_path/'selected-serving-root'
        selected = serving/'src/clasher/rl/contract_v5_tokens.json'
        selected.parent.mkdir(parents=True, exist_ok=True)
        if request.param == 'eval_override':
            monkeypatch.setenv('CLASHER_EVAL_RUNTIME_ROOT', str(serving))
        else:
            monkeypatch.delenv('CLASHER_EVAL_RUNTIME_ROOT')
            monkeypatch.setenv('CLASHER_ROOT', str(serving))
            (serving/'gamedata.json').write_bytes((f.rt.root/'gamedata.json').read_bytes())
    value = dict(tokens=['<pad>', '<unknown>', 'Knight'], cards=['Knight'])
    for path in {normal, selected}:
        path.write_text(json.dumps(value))
    return SimpleNamespace(f=f, normal=normal, selected=selected, value=value)


def test_raw_token_bytes_bind_identity_resume_and_deduplicate_roots(serving_tokens, tmp_path):
    t, f = serving_tokens, serving_tokens.f
    first = identity_for(f)
    token_paths = {str(p.resolve()) for p in (t.normal, t.selected)}
    assert {p for p in first['runtime_files'] if p.endswith('/src/clasher/rl/contract_v5_tokens.json')} == token_paths
    case, path = gate_case(), tmp_path/'A-00000.json'
    path.write_text(json.dumps(with_prior_evidence(dict(clean_row('A', case), **first))))
    assert run.resume_done(path, case, 'A', first)
    raw = t.selected.read_bytes()
    t.selected.write_text(json.dumps(t.value, indent=2)+'\n')
    assert t.selected.read_bytes() != raw and json.loads(raw) == json.loads(t.selected.read_bytes())
    changed = identity_for(f)
    assert all(changed[k] == first[k] for k in first if k != 'runtime_files')
    assert changed['runtime_files'][str(t.selected.resolve())] != first['runtime_files'][str(t.selected.resolve())]
    assert all(changed['runtime_files'][p] == digest for p, digest in first['runtime_files'].items()
               if p != str(t.selected.resolve()))  # Includes unchanged weights and every other raw input.
    with pytest.raises(ValueError, match='runtime_files'):
        run.resume_done(path, case, 'A', changed)


@pytest.mark.parametrize('missing', ['normal', 'selected'])
def test_required_normal_and_selected_token_data_missing_fails_closed(serving_tokens, missing):
    target = getattr(serving_tokens, missing)
    target.unlink()
    with pytest.raises(ValueError, match='required serving contract token data missing'):
        run.runtime_files(serving_tokens.f.rt.root)


def test_raw_token_mutation_during_preparation_stops_before_resume_or_forks(serving_tokens, tmp_path, monkeypatch):
    from bot.players import runtime
    from . import scope, placement
    t, f = serving_tokens, serving_tokens.f
    f.args.all11_gate = True
    args = SimpleNamespace(**vars(f.args), start=0, count=1, workers=1,
                           out=tmp_path/'output', bank=tmp_path/'cases.json')
    args.bank.write_text(json.dumps({'cases': [gate_case()]}))
    monkeypatch.setattr(runtime, 'Runtime', lambda: f.rt)
    monkeypatch.setattr(scope, 'install', lambda _: None)
    monkeypatch.setattr(placement, 'proof', lambda: None)
    monkeypatch.setattr(placement, 'install_runtime', lambda _: None)
    for name, values in {
        'bot.players.royalesim_vocab': dict(load=lambda _: {}),
        'bot.search.lopp': dict(load_model=lambda _: None),
    }.items():
        module = ModuleType(name)
        module.__dict__.update(values)
        monkeypatch.setitem(run.sys.modules, name, module)
    before = identity_for(f)
    def preload(*_):
        t.selected.write_text(json.dumps(t.value, indent=2)+'\n')
        return None
    def forbidden(*_):
        raise AssertionError('raw input preparation fence must precede resume and forks')
    monkeypatch.setattr(run, 'preload_configs', preload)
    monkeypatch.setattr(run, 'resume_done', forbidden)
    monkeypatch.setattr(run, 'run_jobs', forbidden)
    with pytest.raises(ValueError, match='experiment inputs changed while building runtime/preloading'):
        run.experiment(args)
    after = identity_for(f)
    assert json.loads(t.selected.read_bytes()) == t.value
    assert all(after[k] == before[k] for k in before if k != 'runtime_files')


def test_resume_identity_and_legacy_rows(tmp_path, identity_inputs):
    fixture = identity_inputs
    identity = identity_for(fixture)
    runtime = fixture.rt.root
    assert identity['runtime_path'] == str(runtime.resolve())
    case = gate_case()
    path = tmp_path / 'A-00000.json'
    assert not run.resume_done(path, case, 'A', identity)
    row = with_prior_evidence(dict(clean_row('A', case), **identity))
    path.write_text(json.dumps(row))
    assert run.resume_done(path, case, 'A', identity)
    for key, value in [('source_sha256', {'bot/levels/run.py': 'changed'}),
                       ('runtime_pins', 'other'), ('runtime_path', '/different/runtime'),
                       ('all11_gate', True)]:
        with pytest.raises(ValueError, match=key):
            run.resume_done(path, case, 'A', dict(identity, **{key: value}))
    with pytest.raises(ValueError, match='case/arm'):
        run.resume_done(path, case, 'B', identity)
    legacy = dict(row)
    del legacy['runtime_path']
    path.write_text(json.dumps(legacy))
    with pytest.raises(ValueError, match='runtime_path'):
        run.resume_done(path, case, 'A', identity)
    path.write_text(json.dumps(dict(row, error='prior failed attempt')))
    assert not run.resume_done(path, case, 'A', dict(identity, source_sha256={'new': 'code'}))


def test_numbered_launches_preserve_receipts(tmp_path):
    legacy = tmp_path / 'launch.json'
    legacy.write_text('original launch\n')
    (tmp_path / 'launch-00003.json').write_text('{"prior": true}\n')
    first = run.write_launch(tmp_path, {'jobs': 3})
    before = first.read_bytes()
    second = run.write_launch(tmp_path, {'jobs': 0})
    assert first.name == 'launch-00004.json'
    assert second.name == 'launch-00005.json'
    assert first.read_bytes() == before
    assert legacy.read_text() == 'original launch\n'
    assert json.loads(second.read_text())['jobs'] == 0


@pytest.fixture
def launcher(tmp_path):
    """Run a launcher copy with only the two external absolute paths replaced.

    Even a failed rejection cannot source the real env or reach a CPU wrapper.
    The fake lease wrapper captures argv and exits without launching Python.
    """
    bindir = tmp_path / 'bin'
    bindir.mkdir()
    hostname = bindir / 'hostname'
    hostname.write_text('#!/bin/sh\nprintf "%s\\n" "$TEST_HOST"\n')
    hostname.chmod(0o755)
    envfile = tmp_path / 'env.sh'
    envfile.write_text('printf sourced > "$SOURCE_MARKER"\nexport REPO="$TEST_REPO" PY=unused-python\n')
    wrapper = tmp_path / 'cpu_job.sh'
    wrapper.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$CAPTURE"\nexit 37\n')
    wrapper.chmod(0o755)
    script = tmp_path / 'run.sh'
    source = (Path(run.__file__).with_name('run.sh')).read_text()
    source = source.replace('/mpac/sdicks02/jobs/clasher/bot-levels/dev/env.sh', str(envfile))
    source = source.replace('/mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh', str(wrapper))
    script.write_text(source)

    def invoke(host, n, *args):
        env = dict(os.environ, PATH=f'{bindir}:{os.defpath}', TEST_HOST=host, TEST_REPO=str(tmp_path),
                   SOURCE_MARKER=str(tmp_path / 'sourced'), CAPTURE=str(tmp_path / 'argv'))
        result = subprocess.run(['bash', str(script), str(n), *args], env=env,
                                capture_output=True, text=True, timeout=5)
        return result, tmp_path / 'sourced', tmp_path / 'argv'
    return invoke


@pytest.mark.parametrize('host,n,extra', [
    ('127x05', 2, []), ('127x09', 2, []), ('127x18', 2, []), ('127x02', 2, []),
    ('127x01', 0, []), ('127x01', 16, []), ('127x01', '999999999999999999999', []),
    ('127x01', 2, ['--workers', '15']), ('127x01', 2, ['--workers=15']),
])
def test_launcher_rejects_before_env_or_lease(launcher, host, n, extra):
    result, sourced, capture = launcher(host, n, *extra)
    assert result.returncode == 2
    assert not sourced.exists() and not capture.exists()


@pytest.mark.parametrize('host', ['127x01', '127x03', '127x04', '127x08'])
def test_launcher_reserves_parent_and_preserves_status(launcher, host):
    result, sourced, capture = launcher(host, 15, '--arms', 'A,B', '--all11-gate')
    assert result.returncode == 37
    assert sourced.exists()
    argv = capture.read_text().splitlines()
    assert argv[:7] == ['16', 'nice', '-n', '10', 'unused-python', '-m', 'bot.levels.run']
    assert argv[7:] == ['--arms', 'A,B', '--all11-gate', '--workers', '15']


@pytest.fixture
def level_cache(tmp_path, monkeypatch):
    from . import configs
    names = ('Own', 'Enemy', 'Legend', 'Unsupported')
    rarities = dict(Own='common', Enemy='rare', Legend='legendary', Unsupported='common')
    loader = SimpleNamespace(get_card=lambda card: SimpleNamespace(rarity=rarities[card]))
    rt = SimpleNamespace(pins={}, R=SimpleNamespace(config={'cards': {n: {} for n in names}},
                                                   builder=SimpleNamespace(loader=loader)))
    lc = configs.LevelConfigs(rt, cache=tmp_path)
    lc.dir.mkdir(parents=True)
    for level in (4, 5, 6, 7, 9, 11):
        lc.path(level).write_text(json.dumps(dict(level=level,
            cards={n: dict(card={}, tables={}) for n in names if n != 'Unsupported'},
            errors={'Unsupported': 'unexportable'})))
    (lc.dir / 'supported.json').write_text(json.dumps(dict(cards=['Enemy', 'Legend', 'Own'],
        unsupported={'Unsupported': 'unexportable'}, comparison='native-json-v1',
        reference_sha256=hashlib.sha256(json.dumps(rt.R.config, sort_keys=True).encode()).hexdigest())))
    monkeypatch.setattr(configs, 'LevelConfigs', lambda _: lc)
    return rt, lc


def test_parent_preloads_only_fair_levels_from_existing_supported(level_cache):
    rt, lc = level_cache
    before = {p.name: p.read_bytes() for p in lc.dir.iterdir()}
    case = gate_case()
    case['view']['own_levels'] = {'Own': 7, 'Enemy': 6}
    case['profile']['cards'][1]['Enemy'] = 13  # Hidden truth must not request L13.
    manifest = run.preload_configs(rt, [(case, 'B', None)], False)
    assert rt._level_configs is lc
    assert set(lc.levels) == {4, 5, 6, 7, 9, 11}
    assert json.loads((lc.dir / 'supported.json').read_text())['cards'] == ['Enemy', 'Legend', 'Own']
    assert manifest['supported']['data']['comparison'] == 'native-json-v1'
    assert manifest['exports']['5']['errors'] == {'Unsupported': 'unexportable'}
    assert not lc.path(13).exists()
    assert {p.name: p.read_bytes() for p in lc.dir.iterdir()} == before
    with pytest.raises(ValueError, match='cannot build'):
        lc.load(13)  # The inherited instance cannot export an unexpected level either.
    assert not lc.path(13).exists()


def test_all11_preload_does_not_consult_opponent_prior(level_cache, monkeypatch):
    rt, lc = level_cache
    def forbidden(_):
        raise AssertionError('all11 must not consult the opponent prior')
    monkeypatch.setattr(profile, 'OpponentEstimate', forbidden)
    run.preload_configs(rt, [(gate_case(), 'B', None)], True)
    assert set(lc.levels) == {11}


@pytest.mark.parametrize('fault', ['missing', 'incomplete'])
def test_preload_refuses_missing_or_incomplete_exports(level_cache, fault):
    rt, lc = level_cache
    if fault == 'missing':
        lc.path(9).unlink()
    else:
        data = json.loads(lc.path(7).read_text())
        del data['cards']['Enemy']
        lc.path(7).write_text(json.dumps(data))
    case = gate_case()
    case['view']['own_levels'] = {'Own': 7}
    with pytest.raises(ValueError, match='missing|incomplete'):
        run.preload_configs(rt, [(case, 'B', None)], False)
    assert not hasattr(rt, '_level_configs')
    if fault == 'missing':
        assert not lc.path(9).exists()


def test_non_B_jobs_do_not_touch_export_cache(monkeypatch):
    from . import configs
    def forbidden(_):
        raise AssertionError('A/B0 must not initialize the B export cache')
    monkeypatch.setattr(configs, 'LevelConfigs', forbidden)
    run.preload_configs(SimpleNamespace(), [(gate_case(), 'A', None), (gate_case(), 'B0', None)], False)


def test_preload_preserves_known_errors_for_root_fail_closed(level_cache):
    rt, lc = level_cache
    data = json.loads(lc.path(5).read_text())
    del data['cards']['Enemy']
    data['errors']['Enemy'] = 'known unsupported level export'
    lc.path(5).write_text(json.dumps(data))
    case = gate_case()
    case['view']['own_levels'] = {'Own': 7}
    manifest = run.preload_configs(rt, [(case, 'B', None)], False)
    assert manifest['exports']['5']['errors']['Enemy'] == 'known unsupported level export'
    assert 'Enemy' not in lc.levels[5]['cards']
    assert lc.entry('Enemy', 5) is None  # Readiness must not turn an error into a fallback export.


def test_partial_L11_cannot_shrink_supported_manifest(level_cache):
    rt, lc = level_cache
    support_raw = (lc.dir / 'supported.json').read_bytes()
    data = json.loads(lc.path(11).read_text())
    del data['cards']['Enemy']
    lc.path(11).write_text(json.dumps(data))
    with pytest.raises(ValueError, match='incomplete L11'):
        run.preload_configs(rt, [(gate_case(), 'B', None)], True)
    assert (lc.dir / 'supported.json').read_bytes() == support_raw


def forbid_cache_writers(patch, lc):
    def forbidden(*args, **kwargs):
        raise AssertionError('preload must never invoke a writer, even to repair stale/missing support')
    for name in ('write_text', 'write_bytes', 'mkdir', 'replace', 'rename', 'unlink'):
        patch.setattr(Path, name, forbidden)
    patch.setattr(type(lc), 'supported', forbidden)
    patch.setattr(type(lc), 'build', forbidden)
    return forbidden


def test_preload_existing_only_no_writes_or_later_disk_reads(level_cache):
    rt, lc = level_cache
    before = {p.name: p.read_bytes() for p in lc.dir.iterdir()}
    support_path = lc.dir / 'supported.json'
    original_read = Path.read_bytes
    reads = Counter()
    def counted_read(path):
        reads[path] += 1
        return original_read(path)
    with pytest.MonkeyPatch.context() as patch:
        forbidden = forbid_cache_writers(patch, lc)
        patch.setattr(Path, 'read_bytes', counted_read)
        manifest = run.preload_configs(rt, [(gate_case(), 'B', None)], True)
        assert reads == {support_path: 1, lc.path(11): 1}
        assert manifest['supported']['raw_sha256'] == hashlib.sha256(before['supported.json']).hexdigest()
        assert manifest['supported']['data'] == json.loads(before['supported.json'])
        assert manifest['supported']['loaded_sha256'] == run.digest(json.loads(before['supported.json']))
        assert manifest['exports']['11']['raw_sha256'] == hashlib.sha256(before['L11.json']).hexdigest()
        assert manifest['exports']['11']['loaded_sha256'] == run.digest(json.loads(before['L11.json']))
        patch.setattr(Path, 'read_bytes', forbidden)
        patch.setattr(Path, 'read_text', forbidden)
        assert lc.supported() == frozenset(('Enemy', 'Legend', 'Own'))
        assert lc.check11() == (['Enemy', 'Legend', 'Own'], {'Unsupported': 'unexportable'})
        assert lc.entry('Enemy', 11) is not None
        assert lc.entry('Unsupported', 11) is None
        with pytest.raises(ValueError, match='unregistered'):
            lc.load(8)
        with pytest.raises(ValueError, match='cannot build'):
            lc.build(8)
    assert {p.name: p.read_bytes() for p in lc.dir.iterdir()} == before


@pytest.mark.parametrize('fault', ['missing', 'malformed', 'stale_reference', 'stale_comparison',
    'missing_card', 'duplicate_card', 'wrong_unsupported', 'numeric_L11_difference', 'side_table_difference'])
def test_preload_bad_support_or_L11_never_repairs_cache(level_cache, fault):
    rt, lc = level_cache
    path = lc.dir / 'supported.json'
    support = json.loads(path.read_bytes())
    if fault == 'missing':
        path.unlink()
    elif fault == 'malformed':
        path.write_text('{')
    elif fault in ('numeric_L11_difference', 'side_table_difference'):
        data = json.loads(lc.path(11).read_bytes())
        if fault == 'numeric_L11_difference':
            data['cards']['Enemy']['card']['damage'] = 99
        else:
            data['cards']['Enemy']['tables']['death_children'] = {'Skeleton': {'damage': 99}}
        lc.path(11).write_text(json.dumps(data))
    else:
        if fault == 'stale_reference':
            support['reference_sha256'] = '0' * 64
        elif fault == 'stale_comparison':
            support['comparison'] = 'old'
        elif fault == 'missing_card':
            support['cards'].remove('Enemy')
        elif fault == 'duplicate_card':
            support['cards'].append('Enemy')
        else:
            support['unsupported'] = {}
        path.write_text(json.dumps(support))
    before = {p.name: p.read_bytes() for p in lc.dir.iterdir()}
    with pytest.MonkeyPatch.context() as patch:
        forbid_cache_writers(patch, lc)
        with pytest.raises(ValueError, match='supported|JSON|property name'):
            run.preload_configs(rt, [(gate_case(), 'B', None)], True)
    assert not hasattr(rt, '_level_configs')
    assert {p.name: p.read_bytes() for p in lc.dir.iterdir()} == before


def test_preload_support_raw_identity_and_registered_reads_are_frozen(level_cache, identity_inputs, tmp_path):
    rt, lc = level_cache
    first = run.preload_configs(rt, [(gate_case(), 'B', None)], True)
    old = identity_for(identity_inputs, first)
    row = tmp_path / 'support-row.json'
    row.write_text(json.dumps(with_prior_evidence(dict(clean_row('B', gate_case()), **old))))
    path = lc.dir / 'supported.json'
    raw = path.read_bytes()
    path.write_bytes(raw + b'\n')  # Same data, different provenance; never rewritten by the reader.
    assert lc.supported() == frozenset(first['supported']['data']['cards'])
    second = run.preload_configs(rt, [(gate_case(), 'B', None)], True)
    assert first['supported']['data'] == second['supported']['data']
    assert first['supported']['loaded_sha256'] == second['supported']['loaded_sha256']
    assert first['supported']['raw_sha256'] != second['supported']['raw_sha256']
    assert path.read_bytes() == raw + b'\n'
    with pytest.raises(ValueError, match='level_cache'):
        run.resume_done(row, gate_case(), 'B', identity_for(identity_inputs, second))


@pytest.mark.parametrize('gate, problem', [(False, None), (True, None), (True, 'error'),
    (True, 'native'), (True, 'rejected'), (True, 'nonterminal'), (True, 'prior_before'), (True, 'prior_after'),
    (True, 'error_with_prior_drift')])
def test_child_passes_gate_flag_and_records_diagnostics(tmp_path, monkeypatch, gate, problem):
    root = SimpleNamespace(stats={'roots': 3}, _cfg={0: (object(), object(), {'changed': 2})})
    rt = SimpleNamespace(PRIOR={'decks': []})
    player = SimpleNamespace(level_root=root, rt=rt)
    calls, played = [], []
    failures = Counter()
    def make_arm(rt, arm, **kwargs):
        calls.append((arm, kwargs))
        return player
    def play(*args, **kwargs):
        played.append(True)
        if problem == 'error_with_prior_drift':
            rt.PRIOR['changed'] = True
        if problem in ('error', 'error_with_prior_drift'):
            raise ValueError('missing exact export for playable card')
        if problem == 'native':
            failures['serial'] += 1
        if problem == 'prior_after':
            rt.PRIOR['changed'] = True
        return dict(winner=0, terminal=problem != 'nonterminal',
                    channels={'0': {'rejected': int(problem == 'rejected')}, '1': {'rejected': 0}},
                    play_log={0: [[100, 'Own', 1, True]], 1: []})
    for name, values in {
        'bot.search.lopp': dict(FAILURES=failures),
        'bot.levels.player': dict(make_arm_player=make_arm),
        'bot.eval.headline': dict(make_player=lambda *_: SimpleNamespace(rt=rt if problem != 'prior_before'
                                               else SimpleNamespace(PRIOR={'changed': True}))),
        'bot.players.royalesim_match': dict(play_match=play),
    }.items():
        module = ModuleType(name)
        module.__dict__.update(values)
        monkeypatch.setitem(run.sys.modules, name, module)
    monkeypatch.setattr(run, 'source_hashes', lambda: {'source': 'same'})
    def exit_child(status):
        raise SystemExit(status)
    monkeypatch.setattr(run.os, '_exit', exit_child)
    args = SimpleNamespace(base_player=run.BASE_PLAYER, client='16.402', all11_gate=gate)
    identity = dict(base_player=args.base_player, client=args.client, all11_gate=gate,
                    source_sha256={'source': 'same'}, runtime_pins='test', runtime_path='/test/runtime',
                    levels_scope={'restricted_sha256': run.digest(rt.PRIOR)})
    path = tmp_path / 'row.json'
    with pytest.raises(SystemExit) as exc:
        run.child(rt, {}, gate_case(), 'B', args, path, identity)
    assert exc.value.code == int(problem is not None)
    row = json.loads(path.read_text())
    assert calls[0][1]['parity_all11'] is gate
    assert row['all11_gate'] is gate
    assert row['level_diagnostics'] == dict(stats={'roots': 3}, seat_configs={'0': {'changed': 2}})
    assert ('error' in row) is (problem in ('error', 'prior_before', 'prior_after', 'error_with_prior_drift'))
    assert bool(played) is (problem != 'prior_before')
    assert run.prior_evidence_ok(row) is (problem not in ('prior_before', 'prior_after', 'error_with_prior_drift'))
    run.record_exit(path, gate_case(), 'B', identity, 123, int(problem is not None) << 8)
    saved = json.loads(path.read_text())
    if problem in ('error', 'error_with_prior_drift'):
        assert saved['traceback'] == row['traceback']
        assert saved['error'] == row['error']
        assert 'missing exact export' in saved['error']
    if problem == 'error_with_prior_drift':
        assert 'controller prior mismatch' in saved['controller_prior_error']
    assert saved['level_diagnostics'] == row['level_diagnostics']
    assert run.level_diagnostics(SimpleNamespace(level_root=SimpleNamespace())) == dict(stats={}, seat_configs={})


def test_source_identity_includes_launcher_and_python(tmp_path, monkeypatch):
    levels = tmp_path / 'bot/levels'
    levels.mkdir(parents=True)
    (levels / 'run.py').write_text('python source')
    script = levels / 'run.sh'
    script.write_text('shell source')
    for relative in ('bot/players/royalesim_match.py', 'bot/search/players.py',
                     'bot/search/lopp.py', 'bot/search/lopp_fast.py', 'bot/live/levels.py'):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('hook')
    monkeypatch.setattr(run, 'REPO', tmp_path)
    before = run.source_hashes()
    assert {'bot/levels/run.py', 'bot/levels/run.sh'} <= before.keys()
    script.write_text('changed launcher')
    assert run.source_hashes() != before


@pytest.mark.parametrize('target', ['model', 'envfile', 'runtime_source', 'factory_source', 'b0_source', 'behavior', 'prior', 'scope'])
def test_resume_binds_content_and_behavior(tmp_path, identity_inputs, monkeypatch, target):
    f = identity_inputs
    original = identity_for(f)
    path = tmp_path / 'row.json'
    path.write_text(json.dumps(with_prior_evidence(dict(clean_row('A', gate_case()), **original))))
    if target in ('model', 'envfile'):
        getattr(f, target).write_bytes(b'tampered')
    elif target == 'runtime_source':
        (f.rt.root / 'src/engine.py').write_text('changed runtime implementation')
    elif target == 'factory_source':
        (f.repository / 'bot/players/runtime.py').write_text('changed factory dependency')
    elif target == 'b0_source':
        (f.repository / 'bot/live/levels.py').write_text('changed B0 root')
    elif target == 'behavior':
        monkeypatch.setenv('CLASHER_FASTPREP_VERIFY', '1')
    elif target == 'prior':
        f.rt.PRIOR['decks'].append({'cards': ['Other'], 'frequency': 1})
    else:
        f.rt.levels_scope['restricted_sha256'] = 'changed receipt'
    with pytest.raises(ValueError, match='identity differs'):
        run.resume_done(path, gate_case(), 'A', identity_for(f))


def test_cache_identity_binds_loaded_bytes_and_freezes_later_reads(level_cache, identity_inputs, tmp_path):
    rt, lc = level_cache
    jobs = [(gate_case(), 'B', None)]
    manifest = run.preload_configs(rt, jobs, True)
    old = identity_for(identity_inputs, manifest)
    path = tmp_path / 'row.json'
    path.write_text(json.dumps(with_prior_evidence(dict(clean_row('B', gate_case()), **old))))
    loaded = lc.load(11)
    raw = lc.path(11).read_bytes()
    assert manifest['exports']['11']['raw_sha256'] == run.hashlib.sha256(raw).hexdigest()
    assert manifest['exports']['11']['loaded_sha256'] == run.digest(loaded)
    changed = dict(loaded, provenance_note='changed disk artifact')
    lc.path(11).write_text(json.dumps(changed))
    assert lc.load(11) is loaded and 'provenance_note' not in loaded
    current = run.preload_configs(rt, jobs, True)
    assert current['exports']['11']['loaded_sha256'] != manifest['exports']['11']['loaded_sha256']
    with pytest.raises(ValueError, match='level_cache'):
        run.resume_done(path, gate_case(), 'B', identity_for(identity_inputs, current))


def test_requested_cases_cannot_hide_duplicate_or_missing_indices():
    case = gate_case()
    with pytest.raises(ValueError, match='unique'):
        run.select_cases({'cases': [case, dict(case)]}, 0, 2)
    with pytest.raises(ValueError, match='full requested'):
        run.select_cases({'cases': [case, dict(case, index=2)]}, 0, 2)
    assert run.select_cases({'cases': [dict(case, index=1), case]}, 0, 2)[0]['index'] == 0


def with_prior_evidence(row):
    expected = row.setdefault('levels_scope', {'restricted_sha256': run.digest({'decks': []})})['restricted_sha256']
    row['controller_prior_sha256'] = {phase: {'0': expected, '1': expected} for phase in ('before', 'after')}
    return row


def clean_row(arm, case):
    return with_prior_evidence(dict(case, arm=arm, score=1., terminal=True, failures={}, child_exit_code=0,
                channels={'0': {'rejected': 0}, '1': {'rejected': 0}}, command_sha256='identical',
                level_diagnostics=dict(stats={'roots': 4 if arm == 'B' else 0})))


@pytest.mark.parametrize('problem', ['missing', 'duplicate', 'nonterminal', 'error', 'native', 'rejected', 'hash', 'bypass', 'prior', 'diagnostics'])
def test_named_all11_checks_fail_closed(problem):
    rows = [clean_row(arm, gate_case()) for arm in ('A', 'B')]
    assert all(run.parity_checks(rows, [0]).values())
    if problem == 'missing':
        rows.pop()
    elif problem == 'duplicate':
        rows.append(dict(rows[0]))
    elif problem == 'nonterminal':
        rows[1]['terminal'] = False
    elif problem == 'error':
        rows[1]['error'] = 'exception'
    elif problem == 'native':
        rows[1]['failures']['serial'] = 1
    elif problem == 'rejected':
        rows[1]['channels']['1']['rejected'] = 1
    elif problem == 'hash':
        rows[1]['command_sha256'] = 'different'
    elif problem == 'bypass':
        rows[1]['level_diagnostics']['stats']['roots'] = 0
    elif problem == 'prior':
        rows[1]['controller_prior_sha256']['after']['1'] = 'different'
    else:
        del rows[1]['channels']
    assert not all(run.parity_checks(rows, [0]).values())


def test_parent_preserves_error_row_and_returns_nonzero(tmp_path, monkeypatch):
    case = gate_case()
    path = tmp_path / 'row.json'
    error = dict(case, arm='A', error='specific native error', traceback='the complete original traceback')
    path.write_text(json.dumps(error))
    monkeypatch.setattr(run.os, 'fork', lambda: 12345)
    monkeypatch.setattr(run.os, 'waitpid', lambda *_: (12345, 1 << 8))
    monkeypatch.setattr(run.signal, 'pthread_sigmask', lambda *_: set())
    assert run.run_jobs(None, None, [(case, 'A', path)], SimpleNamespace(workers=1), {}) == 1
    saved = json.loads(path.read_text())
    assert saved['error'] == error['error'] and saved['traceback'] == error['traceback']
    assert saved['child_exit_code'] == 1


def test_cleanup_signals_only_verified_children_and_escalates(monkeypatch):
    states = {111: 'running', 222: 'exited'}
    signals = []
    def waitpid(pid, options):
        assert options == os.WNOHANG
        if pid not in states:
            raise ChildProcessError()
        if states[pid] == 'exited':
            del states[pid]
            return pid, 0
        if states[pid] == 'killed':
            del states[pid]
            return pid, signal.SIGKILL
        return 0, 0
    def kill(pid, sig):
        assert pid in states
        signals.append((pid, sig))
        if sig == signal.SIGKILL:
            states[pid] = 'killed'
    monkeypatch.setattr(run.os, 'waitpid', waitpid)
    monkeypatch.setattr(run.os, 'kill', kill)
    remaining, statuses = run.cleanup_children({111: None, 222: None, 999: None}, grace=0, kill_wait=.1)
    assert not remaining
    assert signals == [(111, signal.SIGTERM), (111, signal.SIGKILL)]
    assert set(statuses) == {111, 222}


def test_main_handles_SIGTERM_and_restores_handler(monkeypatch):
    monkeypatch.setenv('PYTHONHASHSEED', '0')
    previous = signal.getsignal(signal.SIGTERM)
    def terminate(_):
        signal.getsignal(signal.SIGTERM)(signal.SIGTERM, None)
    monkeypatch.setattr(run, 'experiment', terminate)
    assert run.main(['--out', 'unused', '--bank', 'unused']) == 128 + signal.SIGTERM
    assert signal.getsignal(signal.SIGTERM) == previous


@pytest.mark.parametrize('tamper', ['cache', 'model', 'envfile'])
def test_all_done_resume_still_builds_and_validates_complete_identity(identity_inputs, tmp_path, monkeypatch, tamper):
    from bot.players import runtime
    from . import scope, placement
    f = identity_inputs
    f.args.all11_gate = True
    args = SimpleNamespace(**vars(f.args), start=0, count=1, workers=1,
                           out=tmp_path / 'output', bank=tmp_path / 'cases.json')
    args.bank.write_text(json.dumps({'cases': [gate_case()]}))
    order, manifest, launches = [], {'exports': {'11': {'loaded_sha256': 'original'}}}, []
    monkeypatch.setattr(runtime, 'Runtime', lambda: (order.append('runtime') or f.rt))
    monkeypatch.setattr(placement, 'proof', lambda: order.append('proof'))
    monkeypatch.setattr(scope, 'install', lambda _: order.append('scope'))
    monkeypatch.setattr(placement, 'install_runtime', lambda _: order.append('placement'))
    for name, values in {
        'bot.players.royalesim_vocab': dict(load=lambda _: (order.append('vocab') or {})),
        'bot.search.lopp': dict(load_model=lambda _: order.append('model')),
    }.items():
        module = ModuleType(name)
        module.__dict__.update(values)
        monkeypatch.setitem(run.sys.modules, name, module)
    monkeypatch.setattr(run, 'preload_configs', lambda *_: (order.append('preload') or manifest))
    original_resume = run.resume_done
    def resume(*values):
        order.append('resume')
        return original_resume(*values)
    monkeypatch.setattr(run, 'resume_done', resume)
    def jobs(rt, vocab, planned, options, identity):
        launches.append(len(planned))
        for case, arm, path in planned:
            run.write_json(path, with_prior_evidence(dict(clean_row(arm, case), **identity)))
        return 0
    monkeypatch.setattr(run, 'run_jobs', jobs)
    assert run.experiment(args) == 0
    order.clear()
    assert run.experiment(args) == 0
    assert order.index('proof') < order.index('runtime') < order.index('scope') < order.index('placement') < order.index('preload') < order.index('resume')
    assert launches == [2, 0]
    if tamper == 'cache':
        manifest['exports']['11']['loaded_sha256'] = 'changed'
    else:
        getattr(f, tamper).write_bytes(b'changed content after successful experiment')
    with pytest.raises(ValueError, match='identity differs'):
        run.experiment(args)


@pytest.mark.parametrize('fault', ['missing', 'mismatch'])
def test_primary_bank_scope_rejected_before_installation_resume_or_forks(identity_inputs, tmp_path, monkeypatch, fault):
    from bot.players import runtime
    from . import scope, placement
    f = identity_inputs
    args = SimpleNamespace(**vars(f.args), start=0, count=1, workers=1,
                           out=tmp_path/'output', bank=tmp_path/'cases.json')
    bank = {'cases': [gate_case()]}
    if fault == 'mismatch':
        bank['scope'] = dict(f.rt.levels_scope, restricted_sha256='different')
    args.bank.write_text(json.dumps(bank))
    monkeypatch.setattr(runtime, 'Runtime', lambda: f.rt)
    monkeypatch.setattr(scope, 'install', lambda _: None)
    monkeypatch.setattr(placement, 'proof', lambda: None)
    def forbidden(*args, **kwargs):
        raise AssertionError('scope validation must precede actor installation, resume and forks')
    monkeypatch.setattr(placement, 'install_runtime', forbidden)
    monkeypatch.setattr(run, 'resume_done', forbidden)
    monkeypatch.setattr(run, 'run_jobs', forbidden)
    with pytest.raises(ValueError, match='registered bank scope'):
        run.experiment(args)


def registered_report(tmp_path, cases=2, gate=False):
    rows = tmp_path / 'rows'
    rows.mkdir()
    bank = tmp_path / 'cases.json'
    case_rows = [dict(gate_case(), index=i, seed=i+1) for i in range(cases)]
    bank.write_text(json.dumps({'cases': case_rows}))
    prior = {'decks': []}
    rt = SimpleNamespace(root=Path('/test/runtime'), PRIOR=prior, R=SimpleNamespace(config={}),
        pins={name: run.digest(name) for name in ('native_sha256', 'v1_sha256', 'r3a_sha256')},
        levels_scope={'restricted_sha256': run.digest(prior)})
    args = SimpleNamespace(base_player=run.BASE_PLAYER, client='16.402', all11_gate=gate, arms='A,B')
    entry = dict(raw_sha256=run.digest('raw fixture'), loaded_sha256=run.digest('loaded fixture'))
    identity = run.invocation_identity(args, rt, {}, {'supported': entry, 'exports': {'11': entry}},
        {'/test/runtime/source.py': run.digest('runtime source')},
        {'bot/live/levels.py': run.digest('B0 source')}, run.hashlib.sha256(bank.read_bytes()).hexdigest())
    launch = dict(args=dict(bank=str(bank), start=0, count=cases, arms='A,B', all11_gate=gate),
                  bank_path=str(bank), bank_sha256=run.hashlib.sha256(bank.read_bytes()).hexdigest(),
                  identity=identity, expected=[dict(arm=a, index=i) for i in range(cases) for a in ('A', 'B')])
    run.write_json(tmp_path / 'launch-00001.json', launch)
    run.write_json(tmp_path / 'launch-00001-result.json', {'exit_code': 0})
    for case in case_rows:
        for arm in ('A', 'B'):
            run.write_json(rows / f"{arm}-{case['index']:05d}.json", with_prior_evidence(dict(clean_row(arm, case), **identity)))
    return rows


def test_report_exposes_missing_rows_pairs_and_failures(tmp_path):
    rows = registered_report(tmp_path)
    assert report.summarize(tmp_path)['quality_ok']
    (rows / 'B-00001.json').unlink()
    path = rows / 'A-00000.json'
    row = json.loads(path.read_text())
    row['failures']['serial'] = 2
    row['channels']['0']['rejected'] = 1
    run.write_json(path, row)
    result = report.summarize(tmp_path)
    assert not result['quality_ok']
    assert result['coverage']['missing_rows'] == [dict(arm='B', index=1)]
    assert result['arms']['A']['native_failures'] == 2
    assert result['arms']['A']['rejections'] == 1
    assert result['arms']['B']['paired']['expected_pairs'] == 2
    assert result['arms']['B']['paired']['missing_indices'] == [0, 1]
    assert report.main([str(tmp_path)]) == 1
    assert 'rejected deployments=1' in report.markdown(result)


def test_report_and_runner_share_named_parity_checks(tmp_path):
    rows = registered_report(tmp_path, gate=True)
    result = report.summarize(tmp_path)
    assert result['quality_ok'] and all(result['all11_checks'].values())
    path = rows / 'B-00000.json'
    row = json.loads(path.read_text())
    row['level_diagnostics']['stats']['roots'] = 0
    run.write_json(path, row)
    result = report.summarize(tmp_path)
    assert not result['quality_ok'] and not result['all11_checks']['b_roots_exercised']


@pytest.mark.parametrize('kind', ['missing', 'empty', 'partial', 'legacy', 'missing_source', 'empty_runtime', 'missing_cache', 'empty_cache_digests'])
def test_report_requires_substantive_v2_identity(tmp_path, kind):
    rows = registered_report(tmp_path)
    assert report.summarize(tmp_path)['quality_ok']
    path = tmp_path / 'launch-00001.json'
    launch = json.loads(path.read_text())
    if kind == 'missing':
        del launch['identity']
    elif kind == 'empty':
        launch['identity'] = {}
    elif kind == 'partial':
        launch['identity'] = {'protocol': 'levels-harness-v2'}
    elif kind == 'legacy':
        launch['identity']['protocol'] = 'levels-harness-v1'
        for row_path in rows.glob('*.json'):
            row = json.loads(row_path.read_text())
            row['protocol'] = 'levels-harness-v1'
            run.write_json(row_path, row)
    elif kind == 'missing_source':
        del launch['identity']['source_sha256']
    elif kind == 'empty_runtime':
        launch['identity']['runtime_files'] = {}
    elif kind == 'missing_cache':
        del launch['identity']['level_cache']
    else:
        launch['identity']['level_cache'] = {'supported': {}, 'exports': {'11': {}}}
    run.write_json(path, launch)
    result = report.summarize(tmp_path)
    assert not result['quality_ok']
    assert result['coverage']['problems']  # Failure is provenance validation, even if remaining fields match rows.
    if kind in ('missing', 'empty', 'partial', 'legacy'):
        assert result['arms']['A']['games'] == 2  # Legacy data remains readable, explicitly unverified.


@pytest.mark.parametrize('arm', ['A', 'B0', 'B'])
@pytest.mark.parametrize('field', ['failures', 'channels', 'child_exit_code'])
def test_primary_resume_requires_complete_diagnostics(tmp_path, identity_inputs, arm, field):
    f = identity_inputs
    f.args.arms = 'A,B0,B'
    identity = identity_for(f)
    path = tmp_path / f'{arm}-00000.json'
    row = with_prior_evidence(dict(clean_row(arm, gate_case()), **identity))
    run.write_json(path, row)
    assert run.resume_done(path, gate_case(), arm, identity)
    del row[field]
    run.write_json(path, row)
    assert not run.resume_done(path, gate_case(), arm, identity)
    assert run.row_issues(row)['missing_diagnostics'] == 1


@pytest.mark.parametrize('field', ['failures', 'channels', 'child_exit_code'])
def test_primary_report_requires_complete_diagnostics(tmp_path, field):
    rows = registered_report(tmp_path, gate=False)
    path = rows / 'A-00000.json'
    row = json.loads(path.read_text())
    del row[field]
    run.write_json(path, row)
    result = report.summarize(tmp_path)
    assert not result['quality_ok'] and result['all11_checks'] is None
    assert result['arms']['A']['missing_diagnostics'] == 1
    assert result['arms']['A']['games'] == 1
    assert result['arms']['B']['paired']['missing_indices'] == [0]


@pytest.mark.parametrize('field,value', [('failures', None), ('channels', {'0': {'rejected': 0}}),
                                       ('child_exit_code', None), ('child_exit_code', False)])
def test_primary_diagnostic_evidence_must_be_well_formed(field, value):
    row = clean_row('A', gate_case())
    row[field] = value
    assert run.row_issues(row)['missing_diagnostics'] == 1


def test_B0_receipt_requires_actual_root_dependency(tmp_path):
    registered_report(tmp_path)
    identity = json.loads((tmp_path / 'launch-00001.json').read_text())['identity']
    identity['arms'].append('B0')
    assert not run.identity_problems(identity)
    del identity['source_sha256']['bot/live/levels.py']
    assert 'missing B0 root source identity' in run.identity_problems(identity)
