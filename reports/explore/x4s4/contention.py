"""X4S-4 pre-declared contention exclusion (PLAN r3 C5 + E7 + R2-9; exploration, NEVER ADOPTABLE). Stdlib only.
r3 after Sol script review r2 (R2-F1, R2-F4, R2-F7). Every read and write goes through x4s4io.

Reads ONLY timing fields: supervisor census samples (utc, psi_some_avg10, foreign_cores_host, reduced_concurrency),
launch.json (utc, workers, lane_width), supervisor-exit.json (utc) of every reporting phase, and for each counted game
its exact st_mtime_ns and top-level `wall_seconds` (parsed with a projection that keeps only that key, so no outcome
field is materialized). The game interval ends at the game file's mtime.

Coverage and validity (Sol F7, R2-F7): every phase must be finished (supervisor-exit.json and SETTLED.json) and have
a census. A sample covers the period since the previous sample (the first: since launch). It is BAD if its memory PSI
avg10 is > 10, missing, non-numeric, non-finite or outside [0, 100]; foreign_cores_host is > 2, missing, non-numeric,
non-finite or outside [0, 1024]; reduced_concurrency is not exactly false; or its time is outside [launch - 1 s,
exit + 1 s] or earlier than the previous sample (chronology). Uncovered time is BAD: launch -> first > 15 s, gaps
> 30 s, last -> exit > 15 s, no census. Census lines that are not strict JSON (NaN/Infinity included) are BAD rows.
A phase launched below its full workers flags all its games (E7). A game is flagged if [mtime - wall_seconds, mtime]
meets any bad period of ANY phase; the union of flagged indices is excluded for every student.

Freeze (Sol F4, R2-F4): schema x4s4.contention.v3. The receipt carries, per phase, the SHA-256 of census, launch,
exit and SETTLED, the block listing, and for every counted game its name, SHA-256, size and exact st_mtime_ns - the
inputs that select the excluded view - plus the SHA-256 of driver/retired.json (which selects the reduced population).
reduce.py re-derives all of it and refuses on any change. The receipt is written once to
<job>/receipts/contention-exclusion.json (exclusive, read-only); its SHA must then be committed before any reduction.
"""
import argparse, datetime, hashlib, json, math, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import x4s4io as io                                  # noqa: E402

SCHEMA = 'x4s4.contention.v3'
PSI_LIMIT, FOREIGN_LIMIT, FOREIGN_MAX = 10.0, 2.0, 1024.0
HEAD_GAP, MID_GAP, TAIL_GAP, SLACK = 15.0, 30.0, 15.0, 1.0
RECEIPT = 'receipts/contention-exclusion.json'


class ContentionError(Exception):
    pass


def ts(s): return datetime.datetime.strptime(s, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=datetime.timezone.utc).timestamp()
def sha_bytes(b): return hashlib.sha256(b).hexdigest()


def wall_only(path):
    """Top-level wall_seconds; every other key is dropped during parsing (outcomes are never materialized)."""
    v = io.project_json(str(path), ('wall_seconds',)).get('wall_seconds')
    if not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v) or v < 0: raise ContentionError(f'{path}: invalid wall_seconds')
    return float(v)


def valid_number(v, lo, hi):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and lo <= v <= hi


def phase_dirs(job):
    base = f'{job}/games'
    out = []
    if not io.lexists(base): return out
    for sid in io.listdir(base):
        for arm in (io.listdir(f'{base}/{sid}') if io.is_real_dir(f'{base}/{sid}') else []):
            p = f'{base}/{sid}/{arm}'
            if not io.is_real_dir(p): continue
            out += [f'{p}/{a}' for a in io.listdir(p) if a.startswith('a') and io.is_real_dir(f'{p}/{a}')]
    return sorted(out)


def counted_games(d):
    """(index, game path) for every block proof of a phase; the game file named by the reporting runner."""
    arm = d.split('/')[-2]
    b = d+'/blocks'
    names = sorted(n for n in io.listdir(b) if n.endswith('.json')) if io.lexists(b) else []
    return [(int(n[:-5]), f'{d}/games/sim-{int(n[:-5]):04d}-d27-{arm}.json') for n in names]


def inventory(job, d):
    """Selection-relevant identity of one phase (re-derived by reduce.py before reduction)."""
    games = []
    for i, g in counted_games(d):
        st = io.stat_leaf(g)
        games.append([i, g.split('/')[-1], io.sha256_file(g), st.st_size, st.st_mtime_ns])
    blocks = sorted(n for n in io.listdir(d+'/blocks') if n.endswith('.json')) if io.lexists(d+'/blocks') else []
    return dict(census_sha256=io.sha256_file(d+'/census.jsonl'), launch_sha256=io.sha256_file(d+'/launch.json'),
                exit_sha256=io.sha256_file(d+'/supervisor-exit.json'), settled_sha256=io.sha256_file(d+'/SETTLED.json'),
                blocks_sha256=sha_bytes(''.join(f'{n} {io.sha256_file(d+"/blocks/"+n)}\n' for n in blocks).encode()),
                games=games)


def bad_periods(job, d):
    rel = d[len(job)+1:]
    launch = io.read_json(d+'/launch.json', 1 << 20); ex = io.read_json(d+'/supervisor-exit.json', 1 << 20)
    t_launch, t_exit = ts(launch['utc']), ts(ex['utc'])
    out = []
    def add(start, end, why, **kw): out.append(dict(phase=rel, start=start, end=end, why=why, **kw))
    lines = [l for l in io.read_text(d+'/census.jsonl', 256 << 20).splitlines() if l.strip()]
    if not lines:
        add(t_launch, t_exit, 'no_census'); return out, 0
    prev = t_launch
    for k, line in enumerate(lines):
        try:
            r = io.loads_strict(line.encode(), 'census')
            t = ts(r['utc'])
        except (io.Refusal, KeyError, ValueError, TypeError):
            add(prev, prev+MID_GAP, 'invalid_census_row', row=k); continue      # unparseable row: the next gap check covers it
        gap = HEAD_GAP if k == 0 else MID_GAP
        why = []
        if t < prev - SLACK or t < t_launch - SLACK or t > t_exit + SLACK: why.append('chronology')
        if t - prev > gap: add(prev, t, 'census_gap', gap_seconds=t-prev)
        psi, foreign, red = r.get('psi_some_avg10'), r.get('foreign_cores_host'), r.get('reduced_concurrency')
        if not valid_number(psi, 0.0, 100.0): why.append('psi_invalid')
        elif psi > PSI_LIMIT: why.append('psi')
        if not valid_number(foreign, 0.0, FOREIGN_MAX): why.append('foreign_invalid')
        elif foreign > FOREIGN_LIMIT: why.append('foreign')
        if red is not False: why.append('reduced_concurrency')
        if why: add(min(prev, t), max(prev, t), '+'.join(why), psi=psi if valid_number(psi, -1e18, 1e18) else repr(psi),
                    foreign_cores=foreign if valid_number(foreign, -1e18, 1e18) else repr(foreign), reduced_concurrency=red)
        prev = max(prev, t)
    if t_exit - prev > TAIL_GAP: add(prev, t_exit, 'census_tail_gap', gap_seconds=t_exit-prev)
    return out, len(lines)


def retired_sha(job):
    p = f'{job}/driver/retired.json'
    return io.sha256_file(p) if io.lexists(p) else None


def build(job):
    job = str(job)
    phases = phase_dirs(job)
    if not phases: raise ContentionError('no reporting phases')
    for d in phases:
        for n in ('launch.json', 'supervisor-exit.json', 'SETTLED.json', 'census.jsonl'):
            if not io.lexists(f'{d}/{n}'): raise ContentionError(f'{d[len(job)+1:]}: {n} missing (phase unfinished or uncovered)')
    bad, samples, coverage = [], 0, {}
    for d in phases:
        b, n = bad_periods(job, d); bad += b; samples += n
        coverage[d[len(job)+1:]] = dict(census_samples=n, **inventory(job, d))
    flagged, games, capped = {}, 0, []
    for d in phases:
        sid, arm = d.split('/')[-3], d.split('/')[-2]
        launch = io.read_json(d+'/launch.json', 1 << 20)
        phase_capped = launch['workers'] < 50//launch['lane_width']
        if phase_capped: capped.append(d[len(job)+1:])
        for i, g in counted_games(d):
            end = io.stat_leaf(g).st_mtime_ns/1e9; start = end-wall_only(g); games += 1
            if phase_capped or any(start <= p['end'] and p['start'] <= end for p in bad):
                flagged.setdefault(i, []).append(f'{sid}/{arm}')
    return dict(schema=SCHEMA, label='X4S-4 contention exclusion (pre-declared C5), exploration, NEVER ADOPTABLE',
                rule=(f'census sample bad if psi_some_avg10 > {PSI_LIMIT} or invalid, foreign_cores_host > {FOREIGN_LIMIT} or invalid, '
                      f'reduced_concurrency not false, or out of chronology; uncovered time bad (launch->first > {HEAD_GAP}s, gap > '
                      f'{MID_GAP}s, last->exit > {TAIL_GAP}s, no census); game flagged if its phase launched below full workers or '
                      '[mtime - wall_seconds, mtime] meets any bad period; union of flagged indices excluded for all students'),
                capped_phases=capped, phases=sorted(coverage), coverage=coverage, census_samples=samples, bad_periods=bad,
                games_checked=games, excluded_indices=sorted(flagged), retired_sha256=retired_sha(job),
                flagged_by=dict(sorted((str(k), v) for k, v in flagged.items())),
                fields_read='census utc/psi_some_avg10/foreign_cores_host/reduced_concurrency; launch.json utc/workers/lane_width; '
                            'supervisor-exit.json utc; game file st_mtime_ns and top-level wall_seconds only; file SHAs')


def write_once(job, body):
    path = f'{job}/{RECEIPT}'
    digest = io.write_json_once(path, body, roles=('receipts',), mode=0o444)
    return path, digest


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--job', required=True); a = ap.parse_args()
    if a.job != io.JOB: raise SystemExit(f'--job must be {io.JOB}')
    try:
        body = build(a.job)
    except (ContentionError, io.Refusal) as e:
        raise SystemExit(f'contention.py: {e}')
    out, digest = write_once(a.job, body)
    print(json.dumps(dict(receipt=out, excluded=len(body['excluded_indices']), bad_periods=len(body['bad_periods']),
                          games=body['games_checked'], phases=len(body['phases']), sha256=digest,
                          next='copy to reports/explore/x4s4/receipts/, commit, then pass --contention-sha and --freeze-commit to reduce.py')))


if __name__ == '__main__':
    main()
