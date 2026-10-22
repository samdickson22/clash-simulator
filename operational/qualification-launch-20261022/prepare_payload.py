"""Build an explicit directory payload locally. Does not stage, connect or admit."""
import argparse
import os
from pathlib import Path
import subprocess
import operate as O

SOURCE = Path('/mpac/sdicks02/repos/clasher-pv1-input-roots-20261022')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--contract', type=Path, required=True)
    parser.add_argument('--contract-sha256', required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    O.require(O.sha(args.contract) == args.contract_sha256, 'contract changed')
    c, inv = O.read_json(args.contract), O.read_json(O.HERE/'inventory.json')
    O.validate_contract(c, inv, O.package_pin(), c['host'])
    O.check_authority(c, inv)
    O.require(subprocess.check_output(['git', '-C', str(SOURCE), 'rev-parse', 'HEAD'], text=True).strip()
              == inv['source_commit'], 'reviewed checkout HEAD changed')
    actual = {str(p.relative_to(SOURCE)) for p in (SOURCE/'bot/pretrain_v1').rglob('*')
              if p.is_file() and '__pycache__' not in p.parts}
    O.require(actual | {'bot/__init__.py'} == set(inv['source_files']), 'source subtree membership changed')
    out = O.below(args.out, O.HOME)
    with O.parent_fd(out, create=True) as (parent, name):
        os.mkdir(name, 0o755, dir_fd=parent)  # Fresh payload, never retry into an interrupted attempt.
    for phase in ('source', 'inputs'):
        for relative, dst, row in O.payload_rows(inv, c, phase):
            src = SOURCE/relative[len('source/'):] if phase == 'source' else Path(dst)
            O.copy_exact(src, out/relative, row)
    O.write_new(out/'payload.json', dict(status='local-directory-payload-only', contract_sha256=O.digest(c),
                source_files_sha256=O.digest(inv['source_files']), inputs_sha256=O.digest(inv['inputs']),
                extra_files_sha256=O.digest(c['extra_files']), source_commit=inv['source_commit']))
    print(out)


if __name__ == '__main__':
    main()
