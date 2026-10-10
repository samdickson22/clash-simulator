"""OP-7: kernel-cgroup-proven Ubuntu apt maintenance, with exact CPU budgets."""
import json, math, os, shlex, time
from fractions import Fraction
from pathlib import Path
from common import utc
from ssh_budget import generation, increment, total_ticks

CGROUPS = {'/system.slice/apt-daily.service', '/system.slice/apt-daily-upgrade.service'}
DIRECT = {'/usr/lib/apt/apt.systemd.daily', '/usr/bin/unattended-upgrade',
          '/usr/bin/apt-get', '/usr/lib/update-notifier/apt-check', '/usr/bin/dpkg'}
SHELLS = {'/bin/sh', '/bin/bash', '/usr/bin/sh', '/usr/bin/bash'}
PYTHONS = {'/usr/bin/python', '/usr/bin/python3'}

def capture_cgroup(proc):
    try:
        lines = (Path(proc) / 'cgroup').read_text().splitlines()
    except OSError:
        return None
    paths = []
    for line in lines:
        fields = line.split(':', 2)
        if len(fields) == 3 and (fields[:2] == ['0', ''] or fields[1] == 'name=systemd'):
            paths.append(fields[2])
    return paths[0] if len(set(paths)) == 1 else None

def root_command(row):
    if row['uid'] != 0 or row.get('apt_cgroup_snapshot') not in CGROUPS:
        return False
    try:
        argv = shlex.split(row['cmd'])
    except ValueError:
        return False
    if not argv:
        return False
    if argv[0] in DIRECT:
        return True
    if len(argv) > 1 and argv[0] in SHELLS:
        return argv[1] == '/usr/lib/apt/apt.systemd.daily'
    if len(argv) > 1 and argv[0] in PYTHONS:
        return argv[1] in {'/usr/bin/unattended-upgrade', '/usr/lib/update-notifier/apt-check'}
    return False

def apt_command(row):
    """Unproven apt commands receive no boot-service or compute-name loophole."""
    try:
        argv = shlex.split(row['cmd'])
    except ValueError:
        return False
    names = {Path(command).name for command in DIRECT}
    if not argv:
        return False
    return Path(argv[0]).name in names or (len(argv)>1 and argv[0] in SHELLS|PYTHONS and Path(argv[1]).name in names)

def source(row, rows):
    if row['uid'] != 0 or row.get('apt_cgroup_snapshot') not in CGROUPS:
        return None
    cgroup = row['apt_cgroup_snapshot']
    bypid = {r['pid']: r for r in rows}
    seen = set()
    for _ in range(64):
        if row['pid'] in seen or row['uid'] != 0 or row.get('apt_cgroup_snapshot') != cgroup:
            return None
        seen.add(row['pid'])
        if root_command(row):
            return dict(cgroup=cgroup, root_identity={k: row[k] for k in
                        ('pid', 'ppid', 'pgid', 'start_ticks', 'uid', 'cmdline_sha256')})
        row = bypid.get(row['ppid'])
        if row is None:
            return None
    return None

def apply(rows):
    for row in rows:
        row.pop('apt_budget', None)
        if row.get('allowlist_kind') == 'ubuntu_apt_budget':
            row.pop('allowlist_kind')
    for row in rows:
        evidence = source(row, rows)
        if evidence:
            row['apt_budget'] = evidence
            row['allowlist_kind'] = 'ubuntu_apt_budget'
    return rows

def sample(before, after, elapsed, hz=None):
    hz = hz or os.sysconf('SC_CLK_TCK')
    old = {generation(row): total_ticks(row) for row in before}
    born = math.floor((time.clock_gettime(time.CLOCK_BOOTTIME) - elapsed) * hz)
    ticks = sum(increment(row, old, born) for row in after if row.get('apt_budget'))
    denominator = hz * Fraction(str(max(elapsed, .001)))
    return dict(cpu_ticks=ticks, seconds=elapsed,
                core_fraction=ticks / hz / max(elapsed, .001),
                stop=Fraction(ticks) * 2 > denominator * 3)

def begin(rows, clock=time.monotonic, hz=None):
    hz = hz or os.sysconf('SC_CLK_TCK')
    return dict(started=clock(), hz=hz,
                born_since_ticks=math.floor(time.clock_gettime(time.CLOCK_BOOTTIME) * hz),
                last={generation(row): total_ticks(row) for row in rows},
                cpu_ticks=0, processes={})

def update(meter, rows):
    for row in rows:
        if not row.get('apt_budget'):
            continue
        delta = increment(row, meter['last'], meter['born_since_ticks'])
        meter['cpu_ticks'] += delta
        key = (row['pid'], row['start_ticks'], row['uid'], row['cmdline_sha256'])
        record = meter['processes'].setdefault(key, dict(
            pid=row['pid'], start_ticks=row['start_ticks'], uid=row['uid'],
            cmdline_sha256=row['cmdline_sha256'], cmd=row['cmd'],
            source=row['apt_budget'], cpu_ticks=0, child_commands=[]))
        record['cpu_ticks'] += delta
        record['observed_self_cpu_ticks'] = row['cpu_ticks']
        record['observed_reaped_child_cpu_ticks'] = row.get('child_cpu_ticks', 0)
        for child in rows:
            if child['ppid'] == row['pid']:
                value = {k: child[k] for k in ('pid', 'start_ticks', 'cmdline_sha256', 'cmd')}
                if value not in record['child_commands']:
                    record['child_commands'].append(value)
    meter['last'] = {generation(row): total_ticks(row) for row in rows}

def finish(meter, elapsed):
    ticks, hz = meter['cpu_ticks'], meter['hz']
    denominator = hz * Fraction(str(max(elapsed, .001)))
    assert ticks == sum(row['cpu_ticks'] for row in meter['processes'].values())
    flagged = Fraction(ticks) * 200 > denominator
    return dict(cpu_ticks=ticks, cpu_seconds=ticks / hz, clock_ticks_per_second=hz,
                block_seconds=elapsed, core_fraction=ticks / hz / max(elapsed, .001),
                apt_flagged=flagged, interfered=flagged,
                stop=elapsed >= 60 and Fraction(ticks) * 10 > denominator,
                average_stop_min_seconds=60, operational_rule='OP-7',
                processes=list(meter['processes'].values()))

def stop_reason(sample_result, block_results):
    if sample_result['stop']:
        return 'ubuntu_apt_sample_budget'
    if any(result['stop'] for result in block_results):
        return 'ubuntu_apt_average_budget'
    return None

def record(job, rows, block_ids):
    records = []
    for row in rows:
        if row.get('apt_budget'):
            records.append(dict(
                **{k: row[k] for k in ('pid', 'start_ticks', 'uid', 'cmdline_sha256', 'cmd', 'cpu_ticks')},
                reaped_child_cpu_ticks=row.get('child_cpu_ticks', 0), source=row['apt_budget'],
                child_commands=[{k: child[k] for k in ('pid', 'start_ticks', 'cmdline_sha256', 'cmd')}
                                for child in rows if child['ppid'] == row['pid']]))
    if records:
        with (job / 'ubuntu-apt-occurrences.jsonl').open('a') as handle:
            handle.write(json.dumps(dict(utc=utc(), block_ids=list(block_ids), processes=records)) + '\n')
