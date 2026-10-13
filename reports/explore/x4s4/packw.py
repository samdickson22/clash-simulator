"""X4S-4 packing wrapper (r10, Sol r9 R9-F7; exploration, NEVER ADOPTABLE). Stdlib + the frozen packer.

  packw.py --set O|holdout|OW --output <job>/data/<onpolicy|onpolicy-holdout|onpolicy-w>/batch-NNNN

The frozen imitation/exit_r1/pack.py stays byte-identical. This caller authenticates its INPUTS first. Every source
game under the set's raw roots must carry its producer's passed, in-time evidence (studytree.raw_evidence):
  * a label game must be listed with its current manifest SHA in a guarded label receipt of that set;
  * an O_W game must be listed in the guarded O_W selection;
  * the game's own completion must pass rule H-1.
Any game without it refuses the whole pack before the packer opens anything. So does any `game-*` entry that is not
a real directory (SR-3). Immediately before packing, the authenticated inventory must equal exactly the packer's
`game-*/manifest.json` glob. The output must be fresh and lie
under the set's packed root. Runs only under guard.py (require_guard), which accepts the sealed output.
"""
import argparse, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import x4s4io as io, studytree                    # noqa: E402

SETS = {'O': (('raw-O/K4S-120', 'raw-O/S-200'), 'onpolicy'), 'holdout': (('raw-holdout/K4S-120', 'raw-holdout/S-200'), 'onpolicy-holdout'),
        'OW': (('raw-OW',), 'onpolicy-w')}


def authenticate_inputs(job, which):
    """The raw roots of a set, after every game-* directory in them carries producer evidence; else io.Refusal."""
    roots, _ = SETS[which]
    out, n, authed = [], 0, set()
    for rel in roots:
        root = f'{job}/data/{rel}'
        if not io.lexists(root): continue
        for name in sorted(io.listdir(root)):
            if not name.startswith('game-'): continue
            io.require(io.is_real_dir(f'{root}/{name}'), 'provenance',      # SR-3: refuse, never skip, a link or file
                       f'{root}/{name}: not a real directory (the packer would follow it)')
            why = studytree.raw_evidence(job, f'{root}/{name}')
            io.require(why is None, 'provenance', f'{root}/{name}: {why} (R9-F7: no pack without producer evidence)')
            authed.add(f'{root}/{name}'); n += 1
        out.append(root)
    io.require(n > 0, 'provenance', f'no source games for set {which}')
    return out, n, authed


def check_inventory(roots, authed):
    """SR-3: immediately before packing, the authenticated inventory must equal EXACTLY what the frozen packer globs
    (`game-*/manifest.json` under each root)."""
    globbed = {str(p.parent) for r in roots for p in Path(r).glob('game-*/manifest.json')}
    io.require(globbed == set(authed), 'provenance', f'packer inventory differs from the authenticated one: '
               f'{sorted(globbed ^ set(authed))[:5]}')


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument('--set', choices=sorted(SETS), required=True); ap.add_argument('--output', required=True)
    a = ap.parse_args(argv)
    studytree.require_guard('packw')
    job = io.JOB; _, packed = SETS[a.set]
    if not (a.output.startswith(f'{job}/data/{packed}/batch-') and len(a.output.rsplit('/', 1)[1]) == 10):
        raise SystemExit(f'--output must be {job}/data/{packed}/batch-NNNN')
    io.check_writable(a.output, roles=('data',), must_not_exist=True)
    roots, n, authed = authenticate_inputs(job, a.set)
    from imitation.exit_r1.pack import pack                     # the unchanged frozen packer
    check_inventory(roots, authed)                              # SR-3: exactly the authenticated games, right before packing
    result = pack(roots, a.output)
    print(json.dumps(dict(set=a.set, sources=n, roots=roots, output=a.output, pack=result), default=str))


if __name__ == '__main__':
    main()
