"""FSC continuation worklist (stdlib, python3 -I; exploration, NEVER ADOPTABLE). Read-only except OUT.

  remaining.py ORIG_WL EXT_WL OUT PHASE_DIR...
Writes the blocks of ORIG_WL that have no proof in any PHASE_DIR (never-started and interrupted blocks, which are rerun
in a fresh instance), in ORIG_WL order, followed by every block of EXT_WL (which must be untouched in every PHASE_DIR).
"""
import json, os, sys
from pathlib import Path


def main():
    orig, ext, out, phases = json.loads(Path(sys.argv[1]).read_text()), json.loads(Path(sys.argv[2]).read_text()), Path(sys.argv[3]), [Path(p) for p in sys.argv[4:]]
    assert phases and orig['range'] == ext['range'] == 'reporting' and not os.path.lexists(out)
    key = lambda b: (b['pop'], b['index'])
    keys = [key(b) for b in orig['blocks']+ext['blocks']]
    assert len(keys) == len(set(keys)), 'ORIG and EXT overlap'
    proven, touched = set(), set()
    for ph in phases:
        sched = json.loads((ph/'schedule.json').read_text())
        assert {(c[0], c[1]) for c in sched['cases']} <= set(keys), ph
        for p in (ph/'blocks').glob('*') if (ph/'blocks').is_dir() else []:
            k = (p.name[0], int(p.name[1:5]))
            touched.add(k)
            if p.suffix == '.json' and not p.name.endswith('.json.tmp'):
                proven.add(k)
    assert not touched & {key(b) for b in ext['blocks']}, 'EXT blocks already touched'
    left = [b for b in orig['blocks'] if key(b) not in proven]
    rerun = [b['index'] for b in left if key(b) in touched]
    out.write_text(json.dumps(dict(range='reporting', blocks=left+ext['blocks'])))
    print(json.dumps(dict(orig=len(orig['blocks']), proven=len(proven), rerun_interrupted=rerun,
                          never_started=len(left)-len(rerun), ext=len(ext['blocks']), total=len(left)+len(ext['blocks']))))


if __name__ == '__main__':
    main()
