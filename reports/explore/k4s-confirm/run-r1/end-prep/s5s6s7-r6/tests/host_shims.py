"""Generated per-test fake-host shims for the S7 gate. The gate and the host program pass explicit environments
(si.run_checked), so every shim reads its settings from `fake.env` (lines `export K=V`) next to itself."""
import os
import shlex
from pathlib import Path

HERE = Path(__file__).resolve().parent

PS = r'''#!/usr/bin/python3
"""Fake ps. Quiet-read format: synthetic lines only. pid/ppid/ni/cls/args format (si.ps_checked: -e -ww -o ...):
the real table with the gate process ($PPID) and its parent forced to FAKE_GATE_NI (default 0), FAKE_CHILD_MARK
processes forced to FAKE_CHILD_NI (default 10), real sshd lines dropped, FAKE_PS_EXTRA lines appended; exits
FAKE_PS_RC (default 0) AFTER printing the full valid table (Sol S7-F2 probe)."""
import os, shlex, subprocess, sys
env = {}
for line in open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "fake.env")):
    if line.startswith("export ") and "=" in line:
        k, v = line[7:].rstrip("\n").split("=", 1)
        env[k] = (shlex.split(v) or [""])[0]
args = sys.argv[1:]
real = "/bin/ps" if os.path.exists("/bin/ps") else "/usr/bin/ps"
if args == ["-eo", "pid=,lstart=,comm=,args="]:
    path = env.get("FAKE_QUIET_PS")
    sys.stdout.write(open(path).read() if path else "    1 Mon Sep 28 15:00:00 2026 systemd /sbin/init\n")
    sys.exit(0)
if args == ["-e", "-ww", "-o", "pid=,ppid=,ni=,cls=,args="]:
    out = subprocess.run([real] + args, stdout=subprocess.PIPE, universal_newlines=True).stdout
    gate = os.getppid()
    rows = []
    for line in out.splitlines():
        parts = line.split(None, 4)
        if len(parts) < 4:
            continue
        rows.append([int(parts[0]), int(parts[1]), parts[2], parts[3], parts[4] if len(parts) > 4 else ""])
    table = {r[0]: r for r in rows}
    gate_parent = table[gate][1] if gate in table else None
    mark = env.get("FAKE_CHILD_MARK", "\0")
    for r in rows:
        if r[4].startswith("sshd: "):
            continue
        if r[0] == gate:
            r[2] = env.get("FAKE_GATE_NI", "0")
        elif r[0] == gate_parent:
            r[2] = env.get("FAKE_PARENT_NI", env.get("FAKE_GATE_NI", "0"))
        elif mark in r[4]:
            r[2] = env.get("FAKE_CHILD_NI", "10")
        print("%7d %7d %3s %3s %s" % tuple(r))
    if env.get("FAKE_PS_EXTRA"):
        sys.stdout.write(open(env["FAKE_PS_EXTRA"]).read())
    sys.stdout.flush()
    sys.exit(int(env.get("FAKE_PS_RC", "0")))
os.execv(real, [real] + args)
'''

HOSTNAME = '''#!/bin/bash
. "$(dirname "$0")/fake.env"
echo "${FAKE_HOST:?FAKE_HOST}"
exit "${FAKE_HOSTNAME_RC:-0}"
'''

SYSTEMCTL = '''#!/bin/bash
. "$(dirname "$0")/fake.env"
case "$1" in
  is-active)
    var="FAKE_ACTIVE_$(printf '%s' "$2" | tr -c 'A-Za-z0-9' '_')"
    state=${!var:-inactive}; echo "$state"; [ "$state" = active ] && exit 0; exit 3 ;;
  list-timers)
    printf 'TZ=%s LC_ALL=%s ARGS=%s\\n' "${TZ:-}" "${LC_ALL:-}" "$*" >> "${FAKE_LOG:-/dev/null}"
    cat "${FAKE_TIMERS:?FAKE_TIMERS}"; exit "${FAKE_TIMERS_RC:-0}" ;;
esac
exit 1
'''

WHO = '''#!/bin/bash
. "$(dirname "$0")/fake.env"
[ -n "${FAKE_WHO:-}" ] && cat "$FAKE_WHO"
exit "${FAKE_WHO_RC:-0}"
'''

PASS = {"nice": '#!/bin/bash\n[ "$1" = -n ] && shift 2\nexec "$@"\n',
        "taskset": '#!/bin/bash\n[ "$1" = -c ] && shift 2\nexec "$@"\n'}

SSH = '''#!/bin/bash
. "%(dir)s/fake.env"
printf 'SSH %%s\\n' "$*" >> "${FAKE_LOG:-/dev/null}"
if [ "$1" = -O ]; then echo "Control socket connect: No such file or directory" >&2; exit "${FAKE_MUX_RC:-255}"; fi
for need in ControlMaster=no ControlPath=none BatchMode=yes StrictHostKeyChecking=yes; do
  case " $* " in *" $need "*) ;; *) exit 97 ;; esac
done
case " $* " in *" -T "*) ;; *) exit 97 ;; esac
exec /usr/bin/python3 -I -B %(remote)s
'''


class Shims:
    def __init__(self, directory, **settings):
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.settings = {}
        for name, text in dict(PASS, ps=PS, hostname=HOSTNAME, systemctl=SYSTEMCTL, who=WHO).items():
            (self.dir / name).write_text(text)
            os.chmod(self.dir / name, 0o755)
        (self.dir / "ssh").write_text(SSH % dict(dir=self.dir, remote=HERE / "fake_remote.py"))
        os.chmod(self.dir / "ssh", 0o755)
        self.set(PATH=str(self.dir) + ":/usr/bin:/bin", **settings)

    def set(self, **settings):
        self.settings.update({k: str(v) for k, v in settings.items()})
        (self.dir / "fake.env").write_text("".join("export %s=%s\n" % (k, shlex.quote(v))
                                                    for k, v in sorted(self.settings.items())))

    def unset(self, *names):
        for name in names:
            self.settings.pop(name, None)
        self.set()

    def path(self, name):
        return str(self.dir / name)
