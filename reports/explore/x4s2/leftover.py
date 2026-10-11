"""X4S2: worklist of a stopped phase's never-started blocks (no .started marker), in the original order.
Blocks with a marker but no proof stay retired. Usage: leftover.py WORKLIST PHASE_DIR OUT (stdlib)."""
import json, sys
from pathlib import Path


def main():
    work, phase, out = json.loads(Path(sys.argv[1]).read_text()), Path(sys.argv[2]), Path(sys.argv[3])
    sched = json.loads((phase/'schedule.json').read_text())
    assert {(c[0], c[1]) for c in sched['cases']} == {(b['pop'], b['index']) for b in work['blocks']}
    left = [b for b in work['blocks'] if not (phase/'blocks'/f"{b['pop']}{b['index']:04d}.started").exists()]
    for b in left:
        assert not (phase/'blocks'/f"{b['pop']}{b['index']:04d}.json").exists()
    out.write_text(json.dumps(dict(range=work['range'], blocks=left)))
    print(json.dumps(dict(source=str(phase), blocks=len(work['blocks']), leftover=len(left))))


if __name__ == '__main__':
    main()
