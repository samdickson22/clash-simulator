"""OP-7: kernel-cgroup-proven Ubuntu apt maintenance, with exact CPU budgets."""
import errno, json, math, os, shlex, stat, time
from fractions import Fraction
from pathlib import Path
from common import utc
from ssh_budget import generation, total_ticks
from cpu_accounting import Accounting

CGROUPS = {'/system.slice/apt-daily.service', '/system.slice/apt-daily-upgrade.service'}
DIRECT = {'/usr/lib/apt/apt.systemd.daily', '/usr/bin/unattended-upgrade',
          '/usr/bin/apt-get', '/usr/lib/update-notifier/apt-check', '/usr/bin/dpkg'}
SHELLS = {'/bin/sh', '/bin/bash', '/usr/bin/sh', '/usr/bin/bash'}
PYTHONS = {'/usr/bin/python', '/usr/bin/python3'}
METHODS = Path('/usr/lib/apt/methods')

def apt_uid(passwd=Path('/etc/passwd')):
    try:
        rows=[line.split(':') for line in passwd.read_text().splitlines() if line.split(':',1)[0]=='_apt']
        return int(rows[0][2]) if len(rows)==1 and len(rows[0])==7 and int(rows[0][2])>0 else None
    except (OSError,ValueError,IndexError):
        return None

def capture_uids(proc):
    try:
        fields=[line.split()[1:] for line in (Path(proc)/'status').read_text().splitlines() if line.startswith('Uid:')]
        values=tuple(map(int,fields[0])) if len(fields)==1 else ()
        return values[:2] if len(values)==4 else None
    except (OSError,ValueError):
        return None

def root_uid(row):
    return row.get('apt_uid_snapshot') in ((0,0),[0,0])

def helper_exe(exe, error, argv0):
    if exe:
        path=Path(exe)
        return dict(path=exe,evidence='proc/exe') if path.is_absolute() and path.parent==METHODS and '..' not in path.parts else None
    if error!=errno.EACCES or not argv0:
        return None
    path=Path(argv0)
    if not path.is_absolute() or '..' in path.parts:
        return None
    try:
        target=path.resolve(strict=True)
        file=target.stat()
        if target.parent!=METHODS or file.st_uid!=0 or file.st_mode&0o022 or not stat.S_ISREG(file.st_mode):
            return None
        return dict(path=str(target),evidence='argv0 (proc/exe EACCES, unprivileged)',argv0=argv0,file_uid=file.st_uid,file_mode=stat.S_IMODE(file.st_mode),file_device=file.st_dev,file_inode=file.st_ino,exe_errno=error)
    except OSError:
        return None

def helper(row):
    uid=row.get('apt_helper_uid_snapshot')
    if uid is None or row.get('apt_uid_snapshot') not in ((uid,uid),[uid,uid]):
        return False
    proof=row.get('apt_helper_exe_snapshot')
    if not proof or Path(proof.get('path','')).parent!=METHODS:
        return False
    if proof.get('evidence')=='proc/exe':
        return True
    return (proof.get('evidence')=='argv0 (proc/exe EACCES, unprivileged)'
            and proof.get('exe_errno')==errno.EACCES and proof.get('file_uid')==0
            and not proof.get('file_mode',0o777)&0o022)

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
    if not root_uid(row) or row.get('apt_cgroup_snapshot') not in CGROUPS:
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
    """Unproven apt commands receive no compute-name loophole, including bad quotes."""
    try:
        argv = shlex.split(row['cmd'])
    except ValueError:
        argv = row['cmd'].split()
    names = {Path(command).name for command in DIRECT}
    if not argv:
        return False
    return (Path(argv[0]).name in names or Path(argv[0]).parent==METHODS
            or (len(argv)>1 and argv[0] in SHELLS|PYTHONS and Path(argv[1]).name in names))

def source(row, rows):
    if not (root_uid(row) or helper(row)) or row.get('apt_cgroup_snapshot') not in CGROUPS:
        return None
    cgroup = row['apt_cgroup_snapshot']
    exe_proof=row.get('apt_helper_exe_snapshot') if not root_uid(row) else None
    member=dict(real_uid=row['apt_uid_snapshot'][0],effective_uid=row['apt_uid_snapshot'][1],uid_evidence='proc/status Uid real/effective',member_kind='root' if root_uid(row) else '_apt_method',helper_uid=row.get('apt_helper_uid_snapshot'),exe_path=exe_proof['path'] if exe_proof else row.get('exe'),exe_evidence=exe_proof['evidence'] if exe_proof else row.get('exe_evidence'),helper_exe_proof=exe_proof)
    bypid = {r['pid']: r for r in rows}
    seen = set()
    for _ in range(64):
        if row['pid'] in seen or not (root_uid(row) or helper(row)) or row.get('apt_cgroup_snapshot') != cgroup:
            return None
        seen.add(row['pid'])
        if root_command(row):
            return dict(cgroup=cgroup, **member, root_identity=dict(**{k: row[k] for k in
                        ('pid', 'ppid', 'pgid', 'start_ticks', 'uid', 'cmdline_sha256')},real_uid=0,effective_uid=0,uid_evidence='proc/status Uid real/effective'))
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

def sample(before, after, elapsed, hz=None, accounting=None):
    hz = hz or os.sysconf('SC_CLK_TCK')
    born = math.floor((time.clock_gettime(time.CLOCK_BOOTTIME) - elapsed) * hz)
    accounting = accounting or Accounting(before, born, 'apt_budget', sample_baseline=True)
    ticks = sum(accounting.update(after).values())
    denominator = hz * Fraction(str(max(elapsed, .001)))
    return dict(cpu_ticks=ticks, seconds=elapsed,
                core_fraction=ticks / hz / max(elapsed, .001),
                stop=Fraction(ticks) * 2 > denominator * 3)

def begin(rows, clock=time.monotonic, hz=None):
    hz = hz or os.sysconf('SC_CLK_TCK')
    born=math.floor(time.clock_gettime(time.CLOCK_BOOTTIME) * hz)
    return dict(started=clock(), hz=hz,
                born_since_ticks=born,
                last={generation(row): total_ticks(row) for row in rows},
                accounting=Accounting(rows, born, 'apt_budget'),
                cpu_ticks=0, processes={})

def update(meter, rows):
    deltas = meter['accounting'].update(rows)
    for row in rows:
        if not row.get('apt_budget'):
            continue
        delta = deltas[generation(row)]
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
                cpu_accounting_rule='OP-7-observed-child-credit-v1',
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
