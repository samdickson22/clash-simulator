"""05-side incremental mirror of finished X4S games/blocks/receipts (light; rsync pull).

Pulls each host's job directory (excluding runtime inputs) every 90 s into
/mpac/sdicks02/jobs/clasher/x4s-20261011/mirror/<host>/. A host is retired after
one final pull once its STOP file exists and no supervisor of it is still running,
so no further ssh sessions are opened on a returned host.
"""
import datetime, json, subprocess, time
from pathlib import Path

JOB = '/mpac/sdicks02/jobs/clasher/x4s-20261011'
MIRROR = Path(JOB)/'mirror'
HOSTS = ['127x03', '127x08']
END = datetime.datetime(2026, 10, 11, 14, 30, tzinfo=datetime.timezone.utc)
HARD_STOP = datetime.datetime(2026, 10, 11, 14, 0, tzinfo=datetime.timezone.utc)
EXCLUDE = ['repo/', 'native/', 'native-source/', 'inputs/', 'corpus/', 'cache/', '*.tmp', 'mirror/']


def utc(): return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def remote_state(host):
    # STOP present (or hard stop passed)? How many live X4S supervisor/runner processes? (read-only ps)
    script = (f'cd {JOB} 2>/dev/null || exit 0; s=0; test -e STOP && s=1; '
              f'r=$(ps -eo args | grep -v grep | grep -c "{JOB}"); echo "$s $r"')
    out = subprocess.run(['ssh', '-o', 'ConnectTimeout=20', '-o', 'BatchMode=yes', host, 'nice -n 19 sh -c ' + repr(script)],
                         capture_output=True, text=True, timeout=60).stdout.split()
    if len(out) != 2: return (None, None)
    hard = datetime.datetime.now(datetime.timezone.utc) >= HARD_STOP
    return (out[0] == '1' or hard, int(out[1]))


def pull(host):
    dest = MIRROR/host; dest.mkdir(parents=True, exist_ok=True)
    cmd = ['nice', '-n', '19', 'rsync', '-a', '--timeout=120', '--rsync-path=nice -n 19 rsync', '-e', 'ssh -o ConnectTimeout=20 -o BatchMode=yes']
    for e in EXCLUDE:
        cmd += ['--exclude', e]
    cmd += [f'{host}:{JOB}/', f'{dest}/']
    return subprocess.run(cmd, capture_output=True, text=True, timeout=900).returncode


def main():
    retired = set()
    log = MIRROR/'sync-log.jsonl'
    while datetime.datetime.now(datetime.timezone.utc) < END and not (MIRROR/'SYNC-STOP').exists():
        for host in HOSTS:
            if host in retired:
                continue
            try:
                stopped, running = remote_state(host)
                rc = pull(host)
                if stopped and running == 0 and rc == 0:
                    # Nothing of ours is live there and the post-stop pull succeeded: retire.
                    retired.add(host)
                entry = dict(utc=utc(), host=host, rc=rc, stop=stopped, running=running, retired=host in retired)
            except Exception as exc:  # keep mirroring the other host
                entry = dict(utc=utc(), host=host, error=repr(exc))
            with log.open('a') as f:
                f.write(json.dumps(entry)+'\n')
        if len(retired) == len(HOSTS):
            break
        time.sleep(90)
    for host in HOSTS:
        if host not in retired:
            try: pull(host)
            except Exception: pass
    (MIRROR/'sync-exit.json').write_text(json.dumps(dict(utc=utc(), retired=sorted(retired)))+'\n')


if __name__ == '__main__':
    main()
