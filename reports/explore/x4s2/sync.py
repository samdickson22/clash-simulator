"""X4S2 (copied from x4s/sync.py): 05-side incremental mirror of finished games/blocks/receipts (light; rsync pull).

Pulls each host's job directory (excluding runtime inputs) every 90 s into
/mpac/sdicks02/jobs/clasher/x4s2-20261011/mirror/<host>/. A host is retired after
one final pull once its STOP file exists and no supervisor of it is still running,
so no further ssh sessions are opened on a returned host.
"""
import datetime, json, os, signal, subprocess, time
from pathlib import Path

JOB = '/mpac/sdicks02/jobs/clasher/x4s2-20261011'
MIRROR = Path(JOB)/'mirror'
HOSTS = ['127x03', '127x08']
END = datetime.datetime(2026, 10, 11, 13, 50, tzinfo=datetime.timezone.utc)
# Treated as stopped from the supervisor stop time (08's last supervisor stops at 12:15Z, drain <=2 min);
# never contacted after NO_CONTACT (08 must be left alone from 12:30Z; coordinator update 07:28Z, was 09:30Z).
HARD_STOP = {'127x08': datetime.datetime(2026, 10, 11, 12, 15, tzinfo=datetime.timezone.utc),
             '127x03': datetime.datetime(2026, 10, 11, 13, 30, tzinfo=datetime.timezone.utc)}
NO_CONTACT = {'127x08': datetime.datetime(2026, 10, 11, 12, 27, tzinfo=datetime.timezone.utc),
              '127x03': datetime.datetime(2026, 10, 11, 13, 45, tzinfo=datetime.timezone.utc)}
def now(): return datetime.datetime.now(datetime.timezone.utc)
EXCLUDE = ['repo/', 'native/', 'native-source/', 'inputs/', 'corpus/', 'cache/', '*.tmp', 'mirror/']


def utc(): return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def remaining(host):
    return (NO_CONTACT[host]-now()).total_seconds()


def bounded(cmd, host, cap):
    """Run a remote command in its own process group, bounded by the host's no-contact ceiling;
    on timeout kill the whole group (rsync and its ssh child) and reap it."""
    budget = min(cap, remaining(host)-5)
    if budget <= 0:
        raise TimeoutError('no-contact ceiling')
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
    try:
        out, _ = proc.communicate(timeout=budget)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL); proc.communicate()
        raise
    return proc.returncode, out


def remote_state(host):
    # STOP present (or stop time passed)? How many live X4S2 processes? (read-only ps)
    script = (f'cd {JOB} 2>/dev/null || exit 0; s=0; test -e STOP && s=1; '
              f'r=$(ps -eo args | grep -v grep | grep -c "{JOB}"); echo "$s $r"')
    rc, out = bounded(['ssh', '-o', 'ConnectTimeout=20', '-o', 'BatchMode=yes', host, 'nice -n 19 sh -c ' + repr(script)], host, 60)
    out = out.split()
    if len(out) != 2: return (None, None)
    hard = now() >= HARD_STOP[host]
    return (out[0] == '1' or hard, int(out[1]))


def pull(host):
    dest = MIRROR/host; dest.mkdir(parents=True, exist_ok=True)
    cmd = ['nice', '-n', '19', 'rsync', '-a', '--timeout=120', '--rsync-path=nice -n 19 rsync', '-e', 'ssh -o ConnectTimeout=20 -o BatchMode=yes']
    for e in EXCLUDE:
        cmd += ['--exclude', e]
    cmd += [f'{host}:{JOB}/', f'{dest}/']
    return bounded(cmd, host, 900)[0]


def main():
    MIRROR.mkdir(parents=True, exist_ok=True)
    retired = {h for h in HOSTS if (MIRROR/f'retired-{h}').exists()}
    log = MIRROR/'sync-log.jsonl'
    while datetime.datetime.now(datetime.timezone.utc) < END and not (MIRROR/'SYNC-STOP').exists():
        for host in HOSTS:
            if host in retired:
                continue
            if now() >= NO_CONTACT[host]:
                retired.add(host); (MIRROR/f'retired-{host}').write_text(utc()+' no-contact ceiling\n')
                with log.open('a') as f: f.write(json.dumps(dict(utc=utc(), host=host, retired=True, reason='no-contact ceiling'))+'\n')
                continue
            try:
                stopped, running = remote_state(host)
                rc = pull(host)  # bounded() re-checks the ceiling before contacting the host
                if stopped and running == 0 and rc == 0:
                    # Nothing of ours is live there and the post-stop pull succeeded: retire.
                    retired.add(host); (MIRROR/f'retired-{host}').write_text(utc()+' stopped, idle, pulled\n')
                entry = dict(utc=utc(), host=host, rc=rc, stop=stopped, running=running, retired=host in retired)
            except Exception as exc:  # keep mirroring the other host
                entry = dict(utc=utc(), host=host, error=repr(exc))
            with log.open('a') as f:
                f.write(json.dumps(entry)+'\n')
        if len(retired) == len(HOSTS):
            break
        time.sleep(90)
    for host in HOSTS:
        if host not in retired and now() < NO_CONTACT[host]:
            try: pull(host)
            except Exception: pass
    (MIRROR/'sync-exit.json').write_text(json.dumps(dict(utc=utc(), retired=sorted(retired)))+'\n')


if __name__ == '__main__':
    main()
