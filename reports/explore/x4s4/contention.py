"""X4S-4 pre-declared contention exclusion (PLAN r3 C5 + E7 + R2-9; exploration, NEVER ADOPTABLE). Stdlib only.
r2 after Sol script review r1 (F4, F7, F10).

Reads ONLY timing fields: supervisor census samples (utc, psi_some_avg10, foreign_cores_host,
reduced_concurrency), launch.json (utc, workers, lane_width), supervisor-exit.json (utc) of every reporting phase,
and for each reporting game its file mtime and `wall_seconds`. Game JSONs are parsed with an object_pairs_hook that
keeps only the key `wall_seconds` at every level, so no outcome field is ever materialized. The unchanged
x4s3/run.py writes no end timestamp, so the game interval ends at the game file's mtime (written once and fsynced).

Coverage (Sol F7): every phase must be finished (supervisor-exit.json and the driver's SETTLED.json present) and have
a census. A census sample covers the period since the previous sample of its phase (the first sample: since the
phase launch). It is BAD if memory PSI avg10 > 10 or unreadable (None), foreign_cores_host > 2 or unreadable (None;
R2-9: host-wide, outside the X4S-4 tree), or reduced_concurrency is true (E7 yield window). Uncovered time is BAD:
launch -> first sample > 15 s, consecutive samples > 30 s apart, last sample -> supervisor exit > 15 s, or a phase
with no samples at all (launch -> exit). A phase launched with fewer than its full workers flags all of its games
(E7). A game is flagged if [mtime - wall_seconds, mtime] intersects any bad period of ANY phase (contention is
host-wide). The union of flagged seed indices (over all students and arms) is excluded for every student.

Freeze (Sol F4): the receipt carries schema x4s4.contention.v2 and a per-phase source inventory (SHA-256 of census,
launch, exit, SETTLED and of the sorted block-proof and game listings). It is written once to
<job>/receipts/contention-exclusion.json (confined, O_EXCL, mode 0444). Its SHA must be committed before any
reduction; reduce.py re-authenticates the receipt, the commit and the inventory before reading any game.
"""
import argparse, datetime, hashlib, json, os, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import confine                                   # noqa: E402

SCHEMA = 'x4s4.contention.v2'
PSI_LIMIT, FOREIGN_LIMIT = 10.0, 2.0
HEAD_GAP, MID_GAP, TAIL_GAP = 15.0, 30.0, 15.0
RECEIPT = Path('receipts')/'contention-exclusion.json'


class ContentionError(Exception):
    pass


def ts(s): return datetime.datetime.strptime(s, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=datetime.timezone.utc).timestamp()
def sha_bytes(b): return hashlib.sha256(b).hexdigest()
def sha_file(p): return sha_bytes(Path(p).read_bytes())


def _keep_wall(pairs):
    return {k: v for k, v in pairs if k == 'wall_seconds'}


def wall_only(path):
    """Top-level wall_seconds; every other key is dropped during parsing (outcomes are never materialized)."""
    return float(json.loads(Path(path).read_text(), object_pairs_hook=_keep_wall)['wall_seconds'])


def listing_sha(paths):
    """SHA of the sorted 'name sha256' listing of files (block proofs or game files)."""
    return sha_bytes(''.join(f'{p.name} {sha_file(p)}\n' for p in sorted(paths)).encode())


def phase_dirs(job):
    return sorted(d for d in (Path(job)/'games').glob('*/*/a*') if d.is_dir() and not d.is_symlink())


def counted_games(d):
    """(index, game path) for every block proof of a phase; the game file named by the reporting runner."""
    arm = d.parent.name
    return [(int(p.stem), d/'games'/f'sim-{int(p.stem):04d}-d27-{arm}.json') for p in sorted((d/'blocks').glob('*.json'))]


def inventory(job, d):
    """Source identity of one phase (re-verified by reduce.py before reduction)."""
    games = counted_games(d)
    return dict(census_sha256=sha_file(d/'census.jsonl'), launch_sha256=sha_file(d/'launch.json'),
                exit_sha256=sha_file(d/'supervisor-exit.json'), settled_sha256=sha_file(d/'SETTLED.json'),
                blocks=len(games), blocks_sha256=listing_sha(list((d/'blocks').glob('*.json'))),
                games_sha256=listing_sha([g for _, g in games]))


def bad_periods(job, d):
    """Bad census periods of one phase, including uncovered time (Sol F7)."""
    rel = str(d.relative_to(job))
    launch = json.loads((d/'launch.json').read_text()); ex = json.loads((d/'supervisor-exit.json').read_text())
    t_launch, t_exit = ts(launch['utc']), ts(ex['utc'])
    rows = [json.loads(line) for line in (d/'census.jsonl').read_text().splitlines() if line.strip()]
    out = []
    def add(start, end, why, **kw): out.append(dict(phase=rel, start=start, end=end, why=why, **kw))
    if not rows:
        add(t_launch, t_exit, 'no_census'); return out, 0
    prev = t_launch
    for k, r in enumerate(rows):
        t = ts(r['utc'])
        if t < prev - 1.0: raise ContentionError(f'{rel}: census not in time order at row {k}')
        gap = HEAD_GAP if k == 0 else MID_GAP
        if t - prev > gap: add(prev, t, 'census_gap', gap_seconds=t-prev)
        psi, foreign = r.get('psi_some_avg10'), r.get('foreign_cores_host')
        why = [w for w, bad in (('psi_unreadable', psi is None), ('psi', psi is not None and psi > PSI_LIMIT),
                                ('foreign_unreadable', foreign is None), ('foreign', foreign is not None and foreign > FOREIGN_LIMIT),
                                ('reduced_concurrency', r.get('reduced_concurrency') is not False)) if bad]
        if why: add(prev, t, '+'.join(why), psi=psi, foreign_cores=foreign, reduced_concurrency=r.get('reduced_concurrency'))
        prev = max(prev, t)
    if t_exit - prev > TAIL_GAP: add(prev, t_exit, 'census_tail_gap', gap_seconds=t_exit-prev)
    return out, len(rows)


def build(job):
    job = Path(job)
    phases = phase_dirs(job)
    if not phases: raise ContentionError('no reporting phases')
    for d in phases:
        for n in ('launch.json', 'supervisor-exit.json', 'SETTLED.json', 'census.jsonl'):
            if not (d/n).is_file() or (d/n).is_symlink(): raise ContentionError(f'{d.relative_to(job)}: {n} missing (phase unfinished or uncovered)')
    bad, samples, coverage = [], 0, {}
    for d in phases:
        b, n = bad_periods(job, d); bad += b; samples += n
        coverage[str(d.relative_to(job))] = dict(census_samples=n, **inventory(job, d))
    flagged, games, capped = {}, 0, []
    for d in phases:
        sid, arm = d.parent.parent.name, d.parent.name
        launch = json.loads((d/'launch.json').read_text())
        phase_capped = launch['workers'] < 50//launch['lane_width']
        if phase_capped: capped.append(str(d.relative_to(job)))
        for i, g in counted_games(d):
            end = os.stat(g).st_mtime; start = end-wall_only(g); games += 1
            if phase_capped or any(start <= p['end'] and p['start'] <= end for p in bad):
                flagged.setdefault(i, []).append(f'{sid}/{arm}')
    return dict(schema=SCHEMA, label='X4S-4 contention exclusion (pre-declared C5), exploration, NEVER ADOPTABLE',
                rule=(f'census sample bad if psi_some_avg10 > {PSI_LIMIT} or unreadable, foreign_cores_host > {FOREIGN_LIMIT} or '
                      f'unreadable, or reduced_concurrency; uncovered time bad (launch->first > {HEAD_GAP}s, gap > {MID_GAP}s, '
                      f'last->exit > {TAIL_GAP}s, no census); game flagged if its phase launched below full workers or '
                      '[mtime - wall_seconds, mtime] meets any bad period; union of flagged indices excluded for all students'),
                capped_phases=capped, phases=sorted(coverage), coverage=coverage, census_samples=samples, bad_periods=bad,
                games_checked=games, excluded_indices=sorted(flagged),
                flagged_by=dict(sorted((str(k), v) for k, v in flagged.items())),
                fields_read='census utc/psi_some_avg10/foreign_cores_host/reduced_concurrency; launch.json utc/workers/lane_width; '
                            'supervisor-exit.json utc; game file mtime and top-level wall_seconds only; file SHAs')


def write_once(job, body):
    out = confine.writable(str(Path(job)/RECEIPT), roles=('receipts',), must_not_exist=True)
    data = (json.dumps(body, indent=2)+'\n').encode()
    fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o444)
    with os.fdopen(fd, 'wb') as f:
        f.write(data); f.flush(); os.fsync(f.fileno())
    return out, sha_bytes(data)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--job', type=Path, required=True); a = ap.parse_args()
    if a.job != confine.JOB: raise SystemExit(f'--job must be {confine.JOB}')
    try:
        body = build(a.job)
    except ContentionError as e:
        raise SystemExit(f'contention.py: {e}')
    out, digest = write_once(a.job, body)
    print(json.dumps(dict(receipt=str(out), excluded=len(body['excluded_indices']), bad_periods=len(body['bad_periods']),
                          games=body['games_checked'], phases=len(body['phases']), sha256=digest,
                          next='copy to reports/explore/x4s4/receipts/, commit, then pass --contention-sha and --freeze-commit to reduce.py')))


if __name__ == '__main__':
    main()
