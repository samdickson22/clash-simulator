"""qualify_games.sh launches exactly qual_tasks.TASKS (names, runtimes, modes, populations, indices, arms, slots)."""
import shlex
from pathlib import Path
from qual_tasks import TASKS, ALL, cores


def test_launcher_matches_canonical_tasks():
    lines = [l for l in (Path(__file__).parent/'qualify_games.sh').read_text().splitlines() if l.startswith('L ')]
    seen = {}
    for l in lines:
        t = shlex.split(l.replace('$ALL', ' '.join(ALL)))
        name, core_s, runtime = t[1], t[2], t[3]
        opts = t[4:]; get = lambda k: opts[opts.index(k)+1]
        arms = tuple(opts[opts.index('--arms')+1:opts.index('--out')])
        seen[name] = (Path(get('--out')).name, runtime, get('--mode'), get('--population'), int(get('--index')), arms, list(map(int, core_s.split(','))))
    assert set(seen) == set(TASKS)
    for name, (group, runtime, mode, pop, index, arms, slot) in TASKS.items():
        assert seen[name] == (group, runtime, mode, pop, index, arms, cores(slot)), name
