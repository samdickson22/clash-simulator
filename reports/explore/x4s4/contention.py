"""X4S-4 pre-declared contention exclusion (PLAN r3 C5 + E7 + R2-9; exploration, NEVER ADOPTABLE). Stdlib only.

Reads ONLY timing fields: supervisor census samples (utc, psi_some_avg10, foreign_cores_host,
reduced_concurrency) and launch.json (workers, lane_width) of every reporting phase, and for each reporting
game its file mtime and `wall_seconds`. Game JSONs are parsed with an object_pairs_hook that keeps only the
key `wall_seconds` at every level, so no outcome field is ever materialized. The unchanged x4s3/run.py writes no
end timestamp, so the game interval ends at the game file's mtime (written once and fsynced; never copied in place).
A census sample is bad if memory PSI avg10 > 10, foreign_cores_host > 2 (R2-9: host-wide, outside the X4S-4 tree),
or reduced_concurrency is true (E7 yield window); it covers the period since the previous sample of its phase. A
phase launched with fewer than its full workers flags all of its games (E7). A game is flagged if
[mtime - wall_seconds, mtime] intersects any bad period. The union of flagged seed indices (over all students and
arms) is excluded for every student.
Writes <job>/receipts/contention-exclusion.json with O_EXCL; commit it (SHA) before any reduction.
"""
import argparse, datetime, hashlib, json, os
from pathlib import Path

PSI_LIMIT, FOREIGN_LIMIT = 10.0, 2.0


def ts(s): return datetime.datetime.strptime(s, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=datetime.timezone.utc).timestamp()


def _keep_wall(pairs):
    return {k: v for k, v in pairs if k == 'wall_seconds'}


def wall_only(path):
    """Top-level wall_seconds; every other key is dropped during parsing (outcomes are never materialized)."""
    return float(json.loads(path.read_text(), object_pairs_hook=_keep_wall)['wall_seconds'])


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--job', type=Path, required=True); a = ap.parse_args()
    out = a.job/'receipts'/'contention-exclusion.json'
    phases = sorted(d for d in (a.job/'games').glob('*/*/a*') if d.is_dir())
    bad, samples = [], 0
    for d in phases:
        prev = None
        for line in (d/'census.jsonl').read_text().splitlines():
            r = json.loads(line); t = ts(r['utc']); samples += 1
            psi = r.get('psi_some_avg10') or 0.0
            foreign = r.get('foreign_cores_host')
            yielded = bool(r.get('reduced_concurrency'))
            if psi > PSI_LIMIT or (foreign is not None and foreign > FOREIGN_LIMIT) or yielded:
                bad.append(dict(phase=str(d.relative_to(a.job)), start=prev if prev is not None else t-12.0, end=t,
                                psi=psi, foreign_cores=foreign, reduced_concurrency=yielded))
            prev = t
    flagged, games, capped = {}, 0, []
    for d in phases:
        sid, arm = d.parent.parent.name, d.parent.name
        launch = json.loads((d/'launch.json').read_text())
        phase_capped = launch['workers'] < 50//launch['lane_width']
        if phase_capped: capped.append(str(d.relative_to(a.job)))
        for proof in sorted((d/'blocks').glob('*.json')):
            i = int(proof.stem); g = d/'games'/f'sim-{i:04d}-d27-{arm}.json'
            end = os.stat(g).st_mtime; start = end-wall_only(g); games += 1
            if phase_capped or any(start <= b['end'] and b['start'] <= end for b in bad):
                flagged.setdefault(i, []).append(f'{sid}/{arm}')
    body = dict(label='X4S-4 contention exclusion (pre-declared C5), exploration, NEVER ADOPTABLE',
                rule=f'census bad if psi_some_avg10 > {PSI_LIMIT} or foreign_cores_host > {FOREIGN_LIMIT} or reduced_concurrency; '
                     'game flagged if its phase launched below full workers or [mtime - wall_seconds, mtime] meets a bad census period; '
                     'union of flagged indices excluded for all students', capped_phases=capped,
                phases=[str(d.relative_to(a.job)) for d in phases], census_samples=samples, bad_periods=bad, games_checked=games,
                excluded_indices=sorted(flagged), flagged_by=dict(sorted((str(k), v) for k, v in flagged.items())),
                fields_read='census utc/psi_some_avg10/foreign_cores_host/reduced_concurrency; launch.json workers/lane_width; '
                            'game file mtime and top-level wall_seconds only')
    data = (json.dumps(body, indent=2)+'\n').encode()
    fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o444)
    with os.fdopen(fd, 'wb') as f: f.write(data)
    print(json.dumps(dict(excluded=len(flagged), bad_periods=len(bad), games=games, sha256=hashlib.sha256(data).hexdigest())))


if __name__ == '__main__':
    main()
