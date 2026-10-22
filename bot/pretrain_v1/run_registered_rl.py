"""File entry point: bootstrap engine workers before importing any bot module."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = Path(__file__).resolve().parent


def helper(name, filename):
    spec = importlib.util.spec_from_file_location(name, PACKAGE/filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('audit', 'audit-soak', 'run', 'soak', 'worker', 'evaluate'))
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--worker-spec', type=Path)
    parser.add_argument('--fd', type=int)
    args = parser.parse_args()
    rt = None
    if args.command in ('worker', 'evaluate'):
        config = json.loads(args.config.read_text())
        os.environ.update({k: '1' for k in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS')})
        bootstrap = helper('registered_engine_bootstrap', 'checks/check_ours_producer.py')
        rt, _ = bootstrap.bootstrap(Path(config['runtime']), Path(config['actor_source']),
                                    Path(config['runtime_manifest']['path']))
    else:
        sys.path.insert(0, str(ROOT))
    from bot.pretrain_v1 import rl_driver as D
    config = D.read_config(args.config)
    if args.command in ('audit', 'audit-soak'):
        result = D.audit(config, qualification=args.command == 'audit-soak')
        print(json.dumps(result, indent=2))
        return 0 if result['status'] == 'GO' else 2
    if args.command in ('run', 'soak'):
        if args.out is None:
            parser.error('--out required for run')
        import torch
        math = helper('registered_math_settings', 'checks/qualify_fp64.py')
        with math.math_backend(torch):
            try:
                D.run(config, args.config.resolve(), args.out, qualification=args.command == 'soak')
            except D.CleanupIncomplete as ex:
                # A stuck in-process optimizer/adapter cannot be killed safely
                # as a Python thread. Never leave the owning entry alive or
                # proceed to evaluation after its finite cleanup budget.
                print(str(ex), file=sys.stderr, flush=True)
                os._exit(2)
        if args.command == 'run':
            import subprocess
            subprocess.run([sys.executable, str(Path(__file__).resolve()), 'evaluate', '--config', str(args.out.resolve()/'config.json'),
                            '--out', str(args.out.resolve())], check=True,
                           env=dict(os.environ, CUDA_VISIBLE_DEVICES=''))
    elif args.command == 'evaluate':
        import torch
        from bot.pretrain_v1 import rl_evaluate as E
        torch.set_num_threads(1)
        math = helper('registered_evaluation_math_settings', 'checks/qualify_fp64.py')
        with math.math_backend(torch):
            E.evaluate(config, args.out, rt)
    else:
        from multiprocessing.connection import Connection
        import torch
        math = helper('registered_worker_math_settings', 'checks/qualify_fp64.py')
        with math.math_backend(torch):
            D.worker(config, json.loads(args.worker_spec.read_text()), Connection(args.fd), rt,
                     json.loads((args.out/'runtime.json').read_text()))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
