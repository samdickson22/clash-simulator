"""P16 protocol launcher built from run_eval.py's existing command generator.

Launch cells sequentially in each worker. Per-cell outputs are immutable; failed
attempts remain. No summary strength analysis in plumbing mode.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from .paths import COUNCIL, ROOT, SNAPSHOT_ROOT
from .snapshot import provenance

S2902 = COUNCIL/'pilot/v7r4h-launch/runs/s2902/seed-2902/scripted/policy_decisions_001000000.pt'
NATURAL = COUNCIL/'human-prior-p16/checkpoints/human-bc-natural-seed2903.pt'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--checkpoint', type=Path, required=True)
    ap.add_argument('--reference-checkpoint', type=Path, default=S2902)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--seed', type=int, required=True)
    ap.add_argument('--games', type=int, default=32)
    ap.add_argument('--head-to-head', action='store_true')
    ap.add_argument('--legacy', action='store_true')
    ap.add_argument('--plumbing-only', action='store_true')
    ap.add_argument('--cell', type=int)
    args = ap.parse_args()
    spec = importlib.util.spec_from_file_location('p16_protocol', COUNCIL/'human-prior-p16/scripts/run_eval.py')
    protocol = importlib.util.module_from_spec(spec); spec.loader.exec_module(protocol)
    args.output.mkdir(parents=True, exist_ok=True)
    commands = list(protocol.commands(args.checkpoint, args.output, args.games, 0, args.seed))
    for i, (prefix, original) in enumerate(commands):
        if args.cell is not None and args.cell != i:
            continue
        if args.head_to_head and i not in (0, 3):
            continue
        command = [sys.executable, '-B', '-m',
                   'clasher.rl.eval' if args.legacy else 'imitation.evaluation.p16_adapter', *original[4:]]
        if not args.legacy:
            command += ['--reference-checkpoint', str(args.reference_checkpoint),
                        '--adapter-audit-out',str(prefix)+'.legality.json']
        if args.head_to_head:
            at = command.index('--opponent'); command[at+1]='policy'
            at = command.index('--public-script-style'); del command[at:at+2]
            command += ['--opponent-checkpoint', str(args.reference_checkpoint), '--fixed-world']
            # Two roles, 64 worlds each in the full gate (128 games per role).
            at = command.index('--seed'); command[at+1]=str(args.seed+(i//3)*64*1009)
        receipt = Path(str(prefix)+'.adapter.json')
        if receipt.exists():
            saved=json.loads(receipt.read_text())
            if saved['returncode'] != 0:
                raise RuntimeError(f'failed attempt retained: {receipt}; use fresh rerun directory')
            if saved['checkpoint_sha256'] != hashlib.sha256(args.checkpoint.read_bytes()).hexdigest():
                raise ValueError('checkpoint changed')
            continue
        env = dict(os.environ, PYTHONPATH=f'{SNAPSHOT_ROOT}:{ROOT}/src:{ROOT}/engine-rs', CLASHER_ROOT=str(ROOT),
                   OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1')
        with open(str(prefix)+'.log', 'x') as log:
            result=subprocess.run(command, env=env, cwd=SNAPSHOT_ROOT, stdout=log, stderr=subprocess.STDOUT)
        # Normalize the adapter-owned receipts: infrastructure is v4, actor v5.
        if result.returncode == 0:
            summary_path=Path(str(prefix)+'.json')
            summary=json.loads(summary_path.read_text())
            summary['plumbing_only']=args.plumbing_only
            summary['protocol_public_contract_version']=summary['public_contract_version']
            if not args.legacy:
                summary['public_contract_version']=5
                summary['mask_asymmetry']='imitation v5 / P16 scripts and s2902 v4'
                import torch
                state=torch.load(args.checkpoint,map_location='cpu',weights_only=True)
                summary['model_config_sha256']=hashlib.sha256(
                    json.dumps(state['config'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
            summary_path.write_text(json.dumps(summary,indent=2)+'\n')
            games_path=Path(str(prefix)+'.games.json')
            games=json.loads(games_path.read_text())
            for game in games:
                game.update(plumbing_only=args.plumbing_only,imitation_mask=5 if not args.legacy else None,
                            comparator_mask=4, fixed_world=args.head_to_head)
            games_path.write_text(json.dumps(games,indent=2)+'\n')
        value=dict(**provenance(), returncode=result.returncode, command=command, plumbing_only=args.plumbing_only,
                   checkpoint_sha256=hashlib.sha256(args.checkpoint.read_bytes()).hexdigest(),
                   imitation_mask=5 if not args.legacy else None, comparator_mask=4,
                   temperature=1., decision_interval_ticks=5, fixed_world=args.head_to_head,
                   protocol_source_sha256=hashlib.sha256(Path(protocol.__file__).read_bytes()).hexdigest())
        with open(receipt,'x') as stream: json.dump(value,stream,indent=2)
        print(json.dumps({'cell': i, 'returncode': result.returncode, 'plumbing_only': args.plumbing_only}),flush=True)
        if result.returncode:
            raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()
