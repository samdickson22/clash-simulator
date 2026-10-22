"""Offline FP64 Mac latency handoff. Never selects a serving precision or policy."""
from __future__ import annotations

import argparse
import io
import json
import math
from pathlib import Path
import platform
import subprocess
import sys

from .bench_contract import digest, manifest, manifest_sha, record_payloads, runtime_sha
from .bench_selected import benchmark_lock, contained

SCOPE = 'offline-qualification-only'
ATTENTION = 'mha_fastpath=False,flash=False,mem_efficient=False,math=True'
PACKAGE = Path(__file__).resolve().parent


def source_sha():
    # runtime_sha alone does not cover this runner or the qualification context.
    paths = sorted([*PACKAGE.rglob('*.py'), PACKAGE/'catalog/catalog.json'])
    if any(p.resolve() != p for p in paths):
        raise ValueError('candidate package must contain physical source files')
    return manifest_sha({p.relative_to(PACKAGE).as_posix(): digest(p.read_bytes()) for p in paths})


def load_candidate(path, checkpoint_sha256):
    """Verify the selected FP32 BC bytes and full config before explicit conversion."""
    import torch
    from . import featurize as F
    from .model import PolicyV1
    from .rl_learner import policy_sha256
    raw = Path(path).read_bytes()
    if digest(raw) != checkpoint_sha256:
        raise ValueError('selected checkpoint SHA mismatch')
    ck = torch.load(io.BytesIO(raw), map_location='cpu', weights_only=False)
    if (ck.get('feature_hash') != F.feature_hash() or ck.get('admission', {}).get('eligible') is not True
            or not isinstance(ck.get('ep'), int) or ck['ep'] < 1
            or ck.get('config', {}).get('dtype', 'float32') != 'float32'):
        raise ValueError('require a trained admitted FP32 BC checkpoint with matching features')
    model = PolicyV1(**ck['cfg'])
    if model.cfg != ck['cfg']:
        raise ValueError('require full checkpoint model configuration')
    state = model.state_dict()
    if (set(state) != set(ck['model']) or any(
            not isinstance(ck['model'][k], torch.Tensor) or ck['model'][k].dtype != v.dtype
            or ck['model'][k].shape != v.shape or not bool(torch.isfinite(ck['model'][k]).all())
            for k, v in state.items())):
        raise ValueError('FP32 checkpoint keys/dtypes/shapes/finite values mismatch')
    model.load_state_dict(ck['model'], strict=True)
    if float(model.gate_bias) != ck.get('gate_bias'):
        raise ValueError('checkpoint gate bias mismatch')
    original = policy_sha256(model, F.feature_hash())
    model.double().eval()
    return model, dict(precision='float64', dtype='float64', source_precision='float32', scope=SCOPE, attention=ATTENTION,
                       source_parameter_sha256=original, policy_sha256=policy_sha256(model, F.feature_hash()))


def verified_inputs(checkpoint, records, records_manifest, source, checkpoint_sha256, records_sha256):
    if source_sha() != source:
        raise ValueError('candidate package SHA mismatch')
    if digest(Path(checkpoint).read_bytes()) != checkpoint_sha256:
        raise ValueError('selected checkpoint SHA mismatch')
    frozen = manifest(records_manifest)
    if manifest_sha(frozen) != records_sha256:
        raise ValueError('record manifest SHA mismatch')
    record_payloads(records, frozen)


def physical(path, root):
    p = Path(path).absolute()
    resolved = contained(p, root)
    if '..' in p.parts or p != resolved:
        raise ValueError('benchmark paths must be physical and contain no traversal')
    return resolved


def mac_paths(checkpoint, output, records, records_manifest):
    if platform.system() != 'Darwin':
        raise ValueError('FP64 selected runner requires macOS')
    base = Path.home().resolve()/'clasher-pretrain-bench'
    if base.resolve() != base or not base.is_dir():
        raise ValueError('benchmark root must be a physical directory')
    physical(Path.cwd(), base)
    physical(PACKAGE, base)
    # Reject an old package imported through PYTHONPATH, including lazy imports.
    for name, module in list(sys.modules.items()):
        if name.startswith('bot.pretrain_v1') and getattr(module, '__file__', None):
            if PACKAGE not in Path(module.__file__).resolve().parents:
                raise ValueError('imported candidate package origin mismatch')
    return base, [physical(p, base) for p in (checkpoint, output, records, records_manifest)]


def validate_result(data, expected):
    from .bench_load import CanvasdocLoad, budget_result
    load, total = data.get('canvasdoc', {}), data.get('total', {})
    samples = load.get('samples', [])
    valid_samples = len(samples) >= 2 and all(
        s.get('state') in ('present', 'absent') and s.get('error') is None
        and all(isinstance(s.get(k), (int, float)) and math.isfinite(s[k]) and s[k] >= 0
                for k in ('cpu_percent_total', 'rss_kib_total'))
        and isinstance(s.get('processes'), list)
        and all(s[k] == sum(row[field] for row in s['processes'])
                for k, field in [('cpu_percent_total', 'cpu_percent'), ('rss_kib_total', 'rss_kib')])
        for s in samples)
    accounting = CanvasdocLoad()
    accounting.samples = samples
    valid_times = all(isinstance(total.get(k), (int, float)) and math.isfinite(total[k]) and total[k] >= 0
                      for k in ('p50', 'p95', 'p99', 'max', 'mean'))
    if (any(data.get(k) != v for k, v in expected.items()) or total.get('n') != 20000
            or not valid_times or not valid_samples or load.get('complete') is not True
            or load.get('classification') != 'shared-load' or load.get('clean_result') is not False
            or data.get('load_classification') != 'shared-load'
            or not isinstance(load.get('idle_observed'), bool)
            or load != accounting.report()
            or data.get('latency_budget') != budget_result(total, load)):
        raise RuntimeError('invalid FP64 benchmark result')


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    sub.add_parser('source-digest')
    run = sub.add_parser('run')
    run.add_argument('checkpoint')
    run.add_argument('output')
    run.add_argument('records')
    run.add_argument('--records-manifest', required=True)
    for name in ('source', 'checkpoint', 'records'):
        run.add_argument(f'--{name}-sha256', required=True)
    run.add_argument('--load-condition', choices=['shared-load', 'canvasdoc-idle'], default='shared-load')
    a = p.parse_args(argv)
    if a.command == 'source-digest':
        print(source_sha())
        return
    root, (ckpt, out, records, mf) = mac_paths(a.checkpoint, a.output, a.records, a.records_manifest)
    if not ckpt.is_file() or not records.is_dir() or not mf.is_file():
        p.error('checkpoint, record directory and manifest must exist')
    with benchmark_lock(root):
        # Reserve before expensive validation. Failed/incomplete attempts cannot be reused.
        out.mkdir(parents=True, exist_ok=False)
        attempt = dict(scope=SCOPE, precision='float64', source_sha256=a.source_sha256,
                       checkpoint_sha256=a.checkpoint_sha256, records_sha256=a.records_sha256,
                       runtime_sha256=runtime_sha(), checkpoint=str(ckpt), records=str(records),
                       records_manifest=str(mf), requested_load_condition=a.load_condition,
                       polls=20000, warmup=200, complete=False)
        def save():
            (out/'attempt.json').write_text(json.dumps(attempt, indent=1)+'\n')
        save()
        def verify():
            verified_inputs(ckpt, records, mf, a.source_sha256, a.checkpoint_sha256, a.records_sha256)
        verify()
        # CPU only, no MPS availability checks or attempted FP64 transfers.
        import torch
        from . import featurize as F
        torch.set_num_threads(1)
        model, identity = load_candidate(ckpt, a.checkpoint_sha256)
        cfg = model.cfg
        del model
        attempt.update(identity)
        save()
        for threads in (1, 4):
            verify()
            result = out/f'cpu-t{threads}.json'
            with (out/f'cpu-t{threads}.log').open('x') as log:
                subprocess.run(['perl', '-e', 'alarm shift; exec @ARGV', '1800', sys.executable, '-B', '-m',
                                'bot.pretrain_v1.bench_device', '--session', '--offline-fp64', '--ckpt', str(ckpt),
                                '--records', str(records), '--records-manifest', str(mf), '--device', 'cpu',
                                '--threads', str(threads), '--polls', '20000', '--warmup', '200',
                                '--source-sha256', a.source_sha256, '--checkpoint-sha256', a.checkpoint_sha256,
                                '--records-sha256', a.records_sha256, '--policy-sha256', identity['policy_sha256'],
                                '--load-condition', a.load_condition, '--out', str(result)],
                               stdout=log, stderr=subprocess.STDOUT, timeout=1830, check=True)
            verify()
            physical(result, root)
            expected = dict(identity, source_sha256=a.source_sha256, runtime_sha256=attempt['runtime_sha256'],
                            records_sha256=a.records_sha256, checkpoint_sha256=a.checkpoint_sha256,
                            schema='clasher.pretrain_v1.bench-device.v1',
                            mode='session', weights='checkpoint', device='cpu', threads=threads, polls=20000,
                            warmup=200, cfg=cfg, feature_hash=F.feature_hash(), requested_load_condition=a.load_condition)
            validate_result(json.loads(result.read_text()), expected)
        unsupported = dict(identity, status='unsupported', device='mps', reason='MPS does not support float64',
                           source_sha256=a.source_sha256, runtime_sha256=attempt['runtime_sha256'],
                           checkpoint_sha256=a.checkpoint_sha256, records_sha256=a.records_sha256,
                           measured=False)
        (out/'mps-unsupported.json').write_text(json.dumps(unsupported, indent=1)+'\n')
        verify()
        attempt['complete'] = True
        save()


if __name__ == '__main__':
    main()
