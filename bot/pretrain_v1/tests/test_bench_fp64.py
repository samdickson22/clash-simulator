"""Local fixtures and mocked Mac subprocesses. These checks make no target latency claim."""
import json
from pathlib import Path
import subprocess
import types

import pytest
import torch

from bot.pretrain_v1 import bench_device as D, bench_fp64 as B, bench_load as H, featurize as F
from bot.pretrain_v1.bench_contract import digest, manifest_sha, record_payloads
from bot.pretrain_v1.bench_selected import benchmark_lock
from bot.pretrain_v1.model import PolicyV1
from bot.pretrain_v1.policy import Session, load

BASE = '1ebd0b0a3939761ae2d33eadeed27422eee042f8'
REAL_RECORDS = Path(__file__).parent/'fixtures/stream_actor_live_records.jsonl'
REAL_ANCHOR = Path('/mpac/sdicks02/scratch/pretrain-v1-dev/sweep/anchors/S100/anchor.pt')


@pytest.fixture
def fixture(tmp_path):
    torch.set_num_threads(1)
    torch.manual_seed(4)
    m = PolicyV1(d=24, layers=1, heads=3, ffn=48, drop=.15).eval()
    ck = dict(cfg=m.cfg, model=m.state_dict(), feature_hash=F.feature_hash(), ep=1,
              admission={'eligible': True}, gate_bias=float(m.gate_bias))
    path = tmp_path/'anchor.pt'
    torch.save(ck, path)
    records = tmp_path/'records'
    records.mkdir()
    (records/'records.jsonl').write_bytes(REAL_RECORDS.read_bytes())
    mf = tmp_path/'manifest.json'
    mapping = {'records.jsonl': digest(REAL_RECORDS.read_bytes())}
    mf.write_text(json.dumps(mapping))
    return path, records, mf, dict(source=B.source_sha(), checkpoint=digest(path.read_bytes()),
                                   records=manifest_sha(mapping))


def telemetry(active=False):
    h = H.CanvasdocLoad()
    h.samples = [dict(utc='2026-10-22T00:00:00+00:00', monotonic_s=i, state='absent', error=None,
                      processes=[], cpu_percent_total=0, rss_kib_total=0) for i in (1, 2)]
    if active:
        for s in h.samples:
            s.update(state='present', processes=[dict(pid=10, ppid=1, role='virtual-machine',
                                                      cpu_percent=120., rss_kib=1000)],
                     cpu_percent_total=120., rss_kib_total=1000)
    return h.report()


class FakeLoad:
    def sample(self, force=False):
        pass

    def report(self):
        return telemetry()


def fp64_args(fixture, out, polls=8):
    ck, records, mf, pins = fixture
    model, identity = B.load_candidate(ck, pins['checkpoint'])
    return ['--offline-fp64', '--session', '--ckpt', str(ck), '--records', str(records),
            '--records-manifest', str(mf), '--out', str(out), '--polls', str(polls), '--warmup', '2',
            '--policy-sha256', identity['policy_sha256'],
            *[v for k, sha in pins.items() for v in (f'--{k}-sha256', sha)]]


def test_real_session_fp64_checkpoint_conversion_and_history(tmp_path, monkeypatch):
    if not REAL_ANCHOR.exists():
        pytest.skip('retained trained BC fixture unavailable')
    records = tmp_path/'records'
    records.mkdir()
    (records/'records.jsonl').write_bytes(REAL_RECORDS.read_bytes())
    mapping = {'records.jsonl': digest(REAL_RECORDS.read_bytes())}
    mf = tmp_path/'manifest.json'
    mf.write_text(json.dumps(mapping))
    pins = dict(source=B.source_sha(), checkpoint=digest(REAL_ANCHOR.read_bytes()), records=manifest_sha(mapping))
    f = REAL_ANCHOR, records, mf, pins
    monkeypatch.setattr(D, 'CanvasdocLoad', FakeLoad)
    seen = []
    original = Session.step
    def step(self, record, *args, **kwargs):
        assert next(self.m.parameters()).dtype == torch.float64
        assert not torch.backends.mha.get_fastpath_enabled()
        assert not torch.backends.cuda.flash_sdp_enabled()
        assert not torch.backends.cuda.mem_efficient_sdp_enabled()
        assert torch.backends.cuda.math_sdp_enabled()
        result = original(self, record, *args, **kwargs)
        seen.append((record['tick'], result.status, self.hist))
        return result
    monkeypatch.setattr(Session, 'step', step)
    out = tmp_path/'result.json'
    before = torch.backends.mha.get_fastpath_enabled()
    D.main(fp64_args(f, out))
    assert torch.backends.mha.get_fastpath_enabled() == before
    data = json.loads(out.read_text())
    assert data['total']['n'] == data['polls'] == 8 and len(seen) == 10
    assert len({t for t, _, _ in seen}) == 10
    assert data['source_parameter_sha256'] != data['policy_sha256']
    assert data['scope'] == B.SCOPE and data['dtype'] == 'float64'
    assert data['checkpoint_sha256'] == pins['checkpoint']
    # Conversion is in memory only. Production still loads the unchanged FP32 file.
    model, _ = load(REAL_ANCHOR)
    assert next(model.parameters()).dtype == torch.float32
    assert digest(REAL_ANCHOR.read_bytes()) == pins['checkpoint']


@pytest.mark.parametrize('corrupt', ['dtype', 'cfg', 'feature', 'untrained', 'admission', 'bias', 'nonfinite'])
def test_conversion_rejects_wrong_source(fixture, corrupt):
    path, _, _, _ = fixture
    ck = torch.load(path, weights_only=False)
    if corrupt == 'dtype':
        ck['model']['cls'] = ck['model']['cls'].double()
    elif corrupt == 'cfg':
        del ck['cfg']['drop']
    elif corrupt == 'feature':
        ck['feature_hash'] = 'old'
    elif corrupt == 'untrained':
        ck['ep'] = 0
    elif corrupt == 'admission':
        ck['admission']['eligible'] = False
    elif corrupt == 'bias':
        ck['gate_bias'] += 1
    else:
        ck['model']['cls'].fill_(float('nan'))
    torch.save(ck, path)
    with pytest.raises(ValueError):
        B.load_candidate(path, digest(path.read_bytes()))


def test_full_cfg_and_source_policy_identity(fixture):
    path, _, _, pins = fixture
    m, identity = B.load_candidate(path, pins['checkpoint'])
    assert m.cfg['drop'] == .15 and all(t.dtype == torch.float64 for t in m.state_dict().values())
    assert identity['policy_sha256'] != identity['source_parameter_sha256']
    with pytest.raises(ValueError, match='checkpoint SHA'):
        B.load_candidate(path, '0'*64)
    with pytest.raises(RuntimeError, match='not admitted'):
        ck = torch.load(path, weights_only=False)
        ck['model'] = m.state_dict()
        torch.save(ck, path)
        load(path)


def test_explicit_flag_requires_checkpoint_session_and_pins(fixture, tmp_path, monkeypatch):
    args = fp64_args(fixture, tmp_path/'out')
    for flag in ['--session', '--ckpt', '--records-manifest', '--policy-sha256']:
        bad = list(args)
        i = bad.index(flag)
        del bad[i:i+(1 if flag == '--session' else 2)]
        with pytest.raises(SystemExit):
            D.main(bad)
    monkeypatch.setattr(torch.mps, 'synchronize', lambda: pytest.fail('MPS called'))
    with pytest.raises(SystemExit):
        D.main(args+['--device', 'mps'])


def test_digest_and_record_freshness(fixture):
    ck, records, mf, pins = fixture
    def verify():
        B.verified_inputs(ck, records, mf, pins['source'], pins['checkpoint'], pins['records'])
    verify()
    for key in ('source', 'checkpoint', 'records'):
        old = pins[key]
        pins[key] = '0'*64
        with pytest.raises(ValueError):
            verify()
        pins[key] = old
    (records/'records.jsonl').write_bytes(b'changed')
    with pytest.raises(ValueError, match='bytes changed'):
        verify()


def test_physical_paths_root_and_platform(tmp_path, monkeypatch):
    monkeypatch.setattr(B.platform, 'system', lambda: 'Linux')
    with pytest.raises(ValueError, match='macOS'):
        B.mac_paths('a', 'b', 'c', 'd')
    root = tmp_path/'clasher-pretrain-bench'
    root.mkdir()
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    monkeypatch.setattr(B.platform, 'system', lambda: 'Darwin')
    monkeypatch.chdir(root)
    with pytest.raises(ValueError, match='outside benchmark'):
        B.mac_paths('a', 'b', 'c', 'd')  # Candidate package was not staged under root.
    child = root/'child'
    child.mkdir()
    (root/'alias').symlink_to(child, target_is_directory=True)
    for path in (root/'..'/'clasher-pretrain-bench'/'new', root/'alias'/'new', tmp_path/'outside'):
        with pytest.raises(ValueError):
            B.physical(path, root)
    other = tmp_path/'real'
    other.mkdir()
    linkhome = tmp_path/'home'
    linkhome.mkdir()
    (linkhome/'clasher-pretrain-bench').symlink_to(other, target_is_directory=True)
    monkeypatch.setattr(Path, 'home', lambda: linkhome)
    with pytest.raises(ValueError, match='root must be a physical'):
        B.mac_paths('a', 'b', 'c', 'd')


def test_shared_lock_regular_symlink_fifo_and_contention(tmp_path):
    import os
    target = tmp_path/'selected-benchmark.lock'
    target.symlink_to(tmp_path/'outside')
    with pytest.raises(OSError):
        benchmark_lock(tmp_path)
    assert not (tmp_path/'outside').exists()
    target.unlink()
    os.mkfifo(target)
    with pytest.raises(ValueError, match='regular file'):
        benchmark_lock(tmp_path)
    target.unlink()
    with benchmark_lock(tmp_path):
        with pytest.raises(BlockingIOError):
            benchmark_lock(tmp_path)
    with benchmark_lock(tmp_path):
        pass


def fake_result(expected, active=False):
    load = telemetry(active)
    total = dict(n=20000, p50=12., p95=20., p99=40., max=55., mean=15.)
    return dict(expected, total=total, canvasdoc=load, load_classification='shared-load',
                latency_budget=H.budget_result(total, load))


@pytest.mark.parametrize('active', [False, True])
def test_telemetry_and_budget_validate_without_clean_claim(active):
    result = fake_result({'dtype': 'float64'}, active)
    B.validate_result(result, {'dtype': 'float64'})
    assert result['canvasdoc']['idle_observed'] is (not active)
    for field, value in [('total', dict(result['total'], n=1)), ('dtype', 'float32'),
                         ('canvasdoc', dict(result['canvasdoc'], complete=False)),
                         ('canvasdoc', dict(result['canvasdoc'], idle_observed=active)),
                         ('latency_budget', {})]:
        bad = dict(result)
        bad[field] = value
        with pytest.raises(RuntimeError):
            B.validate_result(bad, {'dtype': 'float64'})
    result['total']['p95'] = 31
    result['latency_budget'] = H.budget_result(result['total'], result['canvasdoc'])
    B.validate_result(result, {'dtype': 'float64'})  # Valid failure measurement stays a failure.
    assert not result['latency_budget']['latency_passes']


@pytest.fixture
def runner(fixture, tmp_path, monkeypatch):
    ck, records, mf, pins = fixture
    root = tmp_path
    out = root/'attempt'
    # Containment itself is tested above; only subprocess orchestration is mocked here.
    monkeypatch.setattr(B, 'mac_paths', lambda *a: (root, [ck, out, records, mf]))
    args = ['run', str(ck), str(out), str(records), '--records-manifest', str(mf),
            *[v for k, sha in pins.items() for v in (f'--{k}-sha256', sha)]]
    calls = []
    def run(cmd, **kw):
        calls.append(cmd)
        assert kw['timeout'] == 1830 and kw['check'] is True
        assert cmd[:4] == ['perl', '-e', 'alarm shift; exec @ARGV', '1800']
        assert cmd[cmd.index('--polls')+1] == '20000' and cmd[cmd.index('--warmup')+1] == '200'
        assert '--session' in cmd and '--offline-fp64' in cmd
        model, identity = B.load_candidate(ck, pins['checkpoint'])
        expected = dict(identity, source_sha256=pins['source'], runtime_sha256=B.runtime_sha(),
                        records_sha256=pins['records'], checkpoint_sha256=pins['checkpoint'],
                        schema='clasher.pretrain_v1.bench-device.v1',
                        mode='session', weights='checkpoint', device='cpu',
                        threads=int(cmd[cmd.index('--threads')+1]), polls=20000, warmup=200,
                        cfg=model.cfg, feature_hash=F.feature_hash(), requested_load_condition='shared-load')
        Path(cmd[cmd.index('--out')+1]).write_text(json.dumps(fake_result(expected)))
    monkeypatch.setattr(B.subprocess, 'run', run)
    return args, out, calls, run


def test_runner_cpu1_cpu4_and_bound_unsupported_mps(runner, monkeypatch):
    args, out, calls, _ = runner
    monkeypatch.setattr(torch.mps, 'synchronize', lambda: pytest.fail('MPS called'))
    B.main(args)
    assert [c[c.index('--threads')+1] for c in calls] == ['1', '4']
    attempt = json.loads((out/'attempt.json').read_text())
    assert attempt['complete'] is True
    unsupported = json.loads((out/'mps-unsupported.json').read_text())
    assert unsupported['status'] == 'unsupported' and unsupported['measured'] is False
    assert 'polls' not in unsupported and 'total' not in unsupported
    assert unsupported['source_sha256'] == attempt['source_sha256']
    assert unsupported['policy_sha256'] == attempt['policy_sha256']
    with pytest.raises(FileExistsError):
        B.main(args)
    assert len(calls) == 2


@pytest.mark.parametrize('failure', ['timeout', 'policy', 'records', 'runtime', 'polls', 'mode', 'dtype', 'telemetry'])
def test_runner_refuses_failed_child_and_preserves_attempt(runner, monkeypatch, failure):
    args, out, calls, run = runner
    def bad(cmd, **kwargs):
        if failure == 'timeout':
            raise subprocess.TimeoutExpired(cmd, kwargs['timeout'])
        run(cmd, **kwargs)
        path = Path(cmd[cmd.index('--out')+1])
        data = json.loads(path.read_text())
        key = {'policy': 'policy_sha256', 'records': 'records_sha256', 'runtime': 'runtime_sha256'}.get(failure, failure)
        if failure == 'telemetry':
            data['canvasdoc']['samples'][0]['cpu_percent_total'] = 9
        else:
            data[key] = 'wrong'
        path.write_text(json.dumps(data))
    monkeypatch.setattr(B.subprocess, 'run', bad)
    with pytest.raises((RuntimeError, subprocess.TimeoutExpired)):
        B.main(args)
    assert not json.loads((out/'attempt.json').read_text())['complete']
    with pytest.raises(FileExistsError):
        B.main(args)


def test_default_fp32_result_matches_exact_base(fixture, tmp_path, monkeypatch):
    source = subprocess.check_output(['git', 'show', f'{BASE}:bot/pretrain_v1/bench_device.py'], text=True)
    old = types.ModuleType('bot.pretrain_v1._base_bench_device')
    old.__package__ = 'bot.pretrain_v1'
    exec(compile(source, '<base:bench_device.py>', 'exec'), old.__dict__)
    ck, records, mf, _ = fixture
    original_step = Session.step
    traces = []
    def step(self, *args, **kw):
        d = original_step(self, *args, **kw)
        traces[-1].append((d.action, d.status, d.p_wait, d.p_wait5, d.value))
        return d
    monkeypatch.setattr(Session, 'step', step)
    results = []
    for module in (old, D):
        traces.append([])
        monkeypatch.setattr(module, 'CanvasdocLoad', FakeLoad)
        # Deterministic clock keeps the comparison byte exact, including component times.
        tick = iter(range(10000))
        monkeypatch.setattr(module.time, 'perf_counter', lambda: next(tick)/1000)
        monkeypatch.setattr(module, 'load_avg', lambda: [1, 2, 3])
        target = tmp_path/f'{len(results)}.json'
        module.main(['--session', '--ckpt', str(ck), '--records', str(records), '--records-manifest', str(mf),
                     '--polls', '8', '--warmup', '2', '--out', str(target)])
        results.append(target.read_bytes())
    assert traces[0] == traces[1]
    assert results[0] == results[1]
    assert 'precision' not in json.loads(results[1])


def test_manifest_pipeline_filters_unique_ticks_and_rejects_symlinks(fixture):
    _, records, mf, _ = fixture
    lines = REAL_RECORDS.read_text().splitlines()
    # Duplicate and backward ticks cannot consume the Session decision budget.
    (records/'records.jsonl').write_text('\n'.join([lines[0], lines[0], lines[1], lines[0], *lines[2:]])+'\n')
    mf.write_text(json.dumps({'records.jsonl': digest((records/'records.jsonl').read_bytes())}))
    gs = D.games(records, 10, mf)
    assert len(gs) == 1 and len(gs[0]) == len(lines)
    assert [r['tick'] for r in gs[0]] == [json.loads(line)['tick'] for line in lines]
    target = records/'records.jsonl'
    raw = target.read_bytes()
    target.unlink()
    elsewhere = records.parent/'external.jsonl'
    elsewhere.write_bytes(raw)
    target.symlink_to(elsewhere)
    with pytest.raises(ValueError, match='physical file'):
        record_payloads(records, mf)


def test_runner_rechecks_bindings_after_child(runner, monkeypatch):
    args, out, _, run = runner
    ck = Path(args[1])
    def mutate(cmd, **kwargs):
        run(cmd, **kwargs)
        ck.write_bytes(b'changed during child')
    monkeypatch.setattr(B.subprocess, 'run', mutate)
    with pytest.raises(ValueError, match='checkpoint SHA'):
        B.main(args)
    assert not json.loads((out/'attempt.json').read_text())['complete']


def test_fp64_child_rejects_wrong_expected_policy(fixture, tmp_path):
    args = fp64_args(fixture, tmp_path/'out')
    args[args.index('--policy-sha256')+1] = '0'*64
    with pytest.raises(ValueError, match='converted policy SHA'):
        D.main(args)
    assert not (tmp_path/'out').exists()


def test_fresh_import_through_source_symlink_is_rejected(tmp_path):
    import os
    import shutil
    import sys
    root = tmp_path/'clasher-pretrain-bench'
    code = root/'physical-code'
    package = code/'bot/pretrain_v1'
    shutil.copytree(B.PACKAGE, package, ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache'))
    alias = root/'alias-code'
    alias.symlink_to(code, target_is_directory=True)
    script = '''
from pathlib import Path
from bot.pretrain_v1 import bench_fp64 as B
root = Path.cwd()
Path.home = classmethod(lambda cls: root.parent)
B.platform.system = lambda: 'Darwin'
assert 'alias-code' in B.__file__
assert Path(B.__file__).resolve() != Path(B.__file__)
for verify in [B.source_sha, lambda: B.mac_paths('checkpoint', 'output', 'records', 'manifest')]:
    try:
        verify()
    except ValueError as ex:
        assert 'physical' in str(ex), str(ex)
    else:
        raise AssertionError('symlinked source import was accepted')
'''
    env = dict(os.environ, PYTHONPATH=str(alias), CUDA_VISIBLE_DEVICES='')
    subprocess.run([sys.executable, '-B', '-c', script], cwd=root, env=env, check=True, timeout=30)


def test_module_file_alias_is_rejected_even_with_physical_package(tmp_path, monkeypatch):
    root = tmp_path/'clasher-pretrain-bench'
    package = root/'code/bot/pretrain_v1'
    package.mkdir(parents=True)
    alias = root/'alias-code'
    alias.symlink_to(root/'code', target_is_directory=True)
    monkeypatch.setattr(B, 'PACKAGE', package)
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    monkeypatch.setattr(B.platform, 'system', lambda: 'Darwin')
    monkeypatch.chdir(root)
    # Isolate origin checks from the real modules already loaded by this test process.
    modules = {'bot.pretrain_v1.alias': types.SimpleNamespace(__file__=str(alias/'bot/pretrain_v1/model.py'))}
    monkeypatch.setattr(B, 'sys', types.SimpleNamespace(modules=modules))
    with pytest.raises(ValueError, match='physical'):
        B.mac_paths('checkpoint', 'output', 'records', 'manifest')
