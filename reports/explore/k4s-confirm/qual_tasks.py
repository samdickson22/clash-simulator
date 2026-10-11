"""PREREG-K4S canonical game-qualification task inventory (Sol core r3 finding 15).

The single source of truth for qualify_games.sh (checked by test_qual_tasks.py), check_games.py,
source_binding.py and make_qualification_receipt.py: eleven tasks, each one driver receipt in its group directory,
on its planned five-core slot, with exactly the listed games.
"""
ALL = ('K4-200', 'K4S-200', 'K4-180', 'K4S-180', 'K4-160', 'K4S-160', 'K4S-140', 'K4S-120', 'K4-140', 'K4-120')
QUAL_BASE = 4503605837370496
# name: (group dir, runtime, mode, population, index, arms, slot)
TASKS = {
    't1-nd-p0':   ('t1-nd', 't1', 'nodeadline', 'primary', 0, ('K4-200',), 0),
    't1-nd-g1':   ('t1-nd', 't1', 'nodeadline', 'guard', 1, ('K4-200',), 1),
    'k4s-nd-p0':  ('k4s-nd-p0', 'k4s', 'nodeadline', 'primary', 0, ('K4-200', 'K4S-200'), 2),
    'k4s-nd-g1':  ('k4s-nd-g1', 'k4s', 'nodeadline', 'guard', 1, ('K4-200', 'K4S-200'), 3),
    'k4s-ch-p2':  ('k4s-ch-p2', 'k4s', 'charged', 'primary', 2, ALL, 4),
    'k4s-ch-g3':  ('k4s-ch-g3', 'k4s', 'charged', 'guard', 3, ALL, 5),
    'k4s-zero':   ('k4s-zero', 'k4s', 'zero', 'primary', 4, ('K4S-200', 'K4S-120'), 6),
    't1-inj-p5':  ('t1-inj', 't1', 'injected', 'primary', 5, ('K4-200',), 7),
    't1-inj-g7':  ('t1-inj', 't1', 'injected', 'guard', 7, ('K4-200',), 8),
    'k4s-inj-p5': ('k4s-inj', 'k4s', 'injected', 'primary', 5, ('K4-200',), 9),
    'k4s-inj-g7': ('k4s-inj', 'k4s', 'injected', 'guard', 7, ('K4-200',), 10),
}


def cores(slot): return list(range(5*slot, 5*slot+5))


def game_name(index, arm): return f'qualification-{index:04d}-d27-{arm}.json'


def receipt_name(runtime, mode, population, index): return f'receipt-{runtime}-{mode}-{population}{index}.json'


def expected_games():
    """{(group, file name): (task name, runtime, mode, population, index, arm)} for every required game."""
    out = {}
    for name, (group, runtime, mode, pop, index, arms, slot) in TASKS.items():
        for arm in arms:
            key = (group, game_name(index, arm)); assert key not in out
            out[key] = (name, runtime, mode, pop, index, arm)
    return out


def validate_receipts(G, read, sha):
    """Exactly one receipt per task, matching the task; exact non-empty game list; hashes equal the files.
    Returns (errors, bound) where bound maps (group, game file) -> sha256 from its receipt."""
    import glob
    from pathlib import Path
    errors, bound = [], {}
    expected_receipts = {(g, receipt_name(rt, md, pop, i)): n for n, (g, rt, md, pop, i, arms, s) in TASKS.items()}
    found = {(Path(p).parent.name, Path(p).name) for p in glob.glob(str(Path(G)/'*'/'receipt-*.json'))}
    if found != set(expected_receipts):
        errors.append(f'receipt inventory: missing {sorted(set(expected_receipts)-found)} extra {sorted(found-set(expected_receipts))}')
    for key, name in expected_receipts.items():
        if key not in found: continue
        group, runtime, mode, pop, index, arms, slot = TASKS[name]
        r = read(Path(G)/key[0]/key[1])
        want = dict(runtime=runtime, mode=mode, population=pop, index=index, seed=QUAL_BASE+index, arms=list(arms), cores=cores(slot))
        bad = [k for k, v in want.items() if r.get(k) != v]
        if bad: errors.append(f'receipt {name}: {bad}')
        games = {g['game']+'.json': g['sha256'] for g in r.get('games', [])}
        if set(games) != {game_name(index, a) for a in arms} or len(r.get('games', [])) != len(arms):
            errors.append(f'receipt {name}: game list')
        for gname, h in games.items():
            f = Path(G)/group/'games'/gname
            if not f.exists() or sha(f) != h: errors.append(f'receipt {name}: game hash {gname}')
            bound[(group, gname)] = h
    return errors, bound
