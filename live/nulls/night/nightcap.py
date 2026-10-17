"""Null's night capture (r2): one offline reference-emulator instance per process (Mac mini).

  nightcap.py run  --inst N     boot instance N (if needed), then capture cards from the shared queue until STOP
  nightcap.py down --inst N     stop instance N (only the PIDs in its receipt)
  nightcap.py status

Per frame: paused native sim, `advance-native` 1-2 ticks, wait for a rendered frame newer than the advance, gRPC
getScreenshot of the full native 1080x2280 RGB888 framebuffer (no crop/resize), observe-rich before + after and plain
observe (hands/elixir). Frames go into chunk dirs under ~/clasher-live/nulls/night/out/<inst>/<run>/ with a manifest
and READY; the 05 puller moves READY chunks off the Mac. Labels are made on 05 (label.py), not here.

Instance N: adb server 5049 (shared, never scans 5555+), console 5596+2N, probe 26795+2N, gRPC 8596+N.
Safety (checked every 3 s by a thread): free disk >= 10 GiB; swap used < 1 GiB and memory pressure normal (else the
highest-numbered live instance stops first); no live driver python process; STOP / STOP-N files.
"""
import argparse
import gzip
import hashlib
import json
import os
import random
import re
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

os.environ['ADB_LOCAL_TRANSPORT_MAX_PORT'] = '5553'  # never scan 5555+ (BlueStacks / live = emulator-5554)
os.environ['ADB_EMU'] = '0'
os.environ['ANDROID_ADB_SERVER_PORT'] = '5049'

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = Path.home() / 'clasher-live/nulls/night'
STATE, OUT = ROOT / 'state', ROOT / 'out'
CACHE = Path.home() / '.cache/clasher-native-reference'
SDK = CACHE / 'android-sdk'
ADB, EMU = str(SDK / 'platform-tools/adb'), str(SDK / 'emulator/emulator')
AVD, PKG = 'clasher_reference_api35', 'nullsroyale.rel.free'
ADB_PORT = 5049
GIB = 1024 ** 3
CARDS = {c['name']: c for c in json.loads((HERE / 'cards.json').read_text())}
BASE = json.loads((HERE / 'base-config.json').read_text())
SUPPORT = ['Knight', 'Zap', 'Fireball', 'Freeze', 'Arrows', 'Skeletons', 'IceSpirits', 'Log']
ID2NAME = {c['id']: n for n, c in CARDS.items()}
NEVER_STARTING = {'Mirror', 'Elixir Collector'}
MIRROR_BASE = 'Knight'  # Mirror replays the owner's last card at +1 level
# ladder PvP arenas (locations.csv rows 2-11, 13, 29) + the reference config's 15000199; rotated per run
LOCATIONS = [15000002, 15000003, 15000004, 15000005, 15000006, 15000007, 15000008, 15000009, 15000010, 15000011,
             15000013, 15000029, 15000199]
LEVELS = [11, 13, 15, 9, 14]  # card/king level per pass (badge digits + HP vary); pass 0 = 11
CLIENT_PIN = dict(apk_version='15.535.13', content='15.535.86')
FRAMES_PER_CHUNK = 24
PNG_EVERY = 50
DISK_FLOOR_GIB, SWAP_LIMIT_GIB = 10.0, 1.0


def ports(i):
    return dict(console=5596 + 2 * i, probe=26795 + 2 * i, grpc=8596 + i)


def utc():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def env():
    return dict(os.environ, ANDROID_AVD_HOME=str(CACHE / 'avd'), ANDROID_HOME=str(SDK), ANDROID_SDK_ROOT=str(SDK))


def adb(serial, *args, check=True, timeout=60):
    r = subprocess.run([ADB, '-P', str(ADB_PORT), '-s', serial, *args], capture_output=True, text=True,
                       timeout=timeout, env=env())
    if check and r.returncode:
        raise RuntimeError(f'adb {args}: {r.returncode} {r.stderr.strip()}')
    return r.stdout.strip()


def atomic_write(path, data, mode='w'):
    tmp = path.with_name('.' + path.name + '.part')
    with open(tmp, mode) as f:
        f.write(data)
    os.replace(tmp, path)


# ----------------------------------------------------------------------------------------------- host checks
def pid_cmd(pid):
    r = subprocess.run(['ps', '-p', str(pid), '-o', 'command='], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ''


def receipt(i):
    p = STATE / f'inst-{i}.json'
    return json.loads(p.read_text()) if p.exists() else None


def emulator_alive(rec):
    return bool(rec) and AVD in pid_cmd(rec['pid']) and f"-port {rec['console']}" in pid_cmd(rec['pid'])


def live_instances():
    return [i for i in range(8) if emulator_alive(receipt(i))]


def swap_used_gib():
    out = subprocess.check_output(['sysctl', '-n', 'vm.swapusage'], text=True)
    return float(re.search(r'used = ([\d.]+)M', out).group(1)) / 1024


def pressure_level():
    # 1 normal, 2 warn, 4 critical
    return int(subprocess.check_output(['sysctl', '-n', 'kern.memorystatus_vm_pressure_level'], text=True))


def driver_running():
    """A live-driver python process (argv only; shells/grep never match because comm must be python)."""
    out = subprocess.run(['ps', '-axo', 'pid=,comm=,args='], capture_output=True, text=True).stdout
    for line in out.splitlines():
        parts = line.split(None, 2)
        if len(parts) == 3 and 'python' in parts[1].rsplit('/', 1)[-1].lower() \
                and re.search(r'(^|\s|/)drive\.py(\s|$)', parts[2]) and int(parts[0]) != os.getpid():
            return int(parts[0])
    return None


def host_problem(i, strict=False):
    """None if instance i may keep running, else the reason. strict (boot preflight): any breach refuses."""
    if (ROOT / 'STOP').exists() or (ROOT / f'STOP-{i}').exists():
        return 'STOP file'
    pid = driver_running()
    if pid:
        return f'live driver python running (pid {pid})'
    free = shutil.disk_usage('/').free / GIB
    swap, level = swap_used_gib(), pressure_level()
    breach = []
    if free < DISK_FLOOR_GIB:
        breach.append(f'disk {free:.2f} GiB < {DISK_FLOOR_GIB}')
    if swap >= SWAP_LIMIT_GIB or level != 1:
        breach.append(f'memory: swap {swap:.2f} GiB, pressure level {level}')
    if breach:
        live = [k for k in live_instances() if not (STATE / f'stopping-{k}').exists()]
        # shrink from the top: only the highest-numbered live (not already stopping) instance yields; the next
        # one re-checks 3 s later and yields too if the breach persists
        if strict or not live or i >= max(live):
            return '; '.join(breach)
    return None


def children(pid):
    out = subprocess.run(['ps', '-axo', 'pid=,ppid='], capture_output=True, text=True).stdout
    return [int(a) for a, b in (l.split() for l in out.splitlines() if l.strip()) if int(b) == pid]


def headroom():
    return dict(free_gib=round(shutil.disk_usage('/').free / GIB, 2), swap_gib=round(swap_used_gib(), 3),
                pressure=pressure_level(), instances=live_instances())


# ----------------------------------------------------------------------------------------------- emulator
def preflight(i):
    p = ports(i)
    for port in (p['console'], p['console'] + 1, p['probe'], p['grpc']):
        with socket.socket() as s:
            if s.connect_ex(('127.0.0.1', port)) == 0:
                raise SystemExit(f'port {port} busy')
    for line in subprocess.run(['ps', 'axo', 'command='], capture_output=True, text=True).stdout.splitlines():
        if 'qemu-system' in line and AVD in line and '-read-only' not in line:
            raise SystemExit('a writable instance of the reference AVD is running; refusing')
    if not (ROOT / 'GO').exists():
        raise SystemExit('no GO marker (ladder handshake) at ' + str(ROOT / 'GO'))
    if not (Path.home() / 'clasher-live/loop/NULLS-BLOCK').exists():
        raise SystemExit('ladder NULLS-BLOCK marker missing')
    reason = host_problem(i, strict=True)
    if reason:
        raise SystemExit('preflight: ' + reason)
    free = shutil.disk_usage('/').free / GIB
    if free < DISK_FLOOR_GIB + 1.5:
        raise SystemExit(f'preflight: free {free:.2f} GiB leaves no room for another instance overlay')


def up(i, log, guard=None):
    rec = receipt(i)
    if emulator_alive(rec):
        log(f'instance {i} already up (pid {rec["pid"]}): adopting')
        if guard is not None:
            guard.start()
        for fw in ('iptables', 'ip6tables'):  # raises if the offline REJECT rule is gone
            adb(rec['serial'], 'shell', fw, '-C', 'OUTPUT', '-m', 'owner', '--uid-owner', rec['app_uid'], '!', '-o',
                'lo', '-j', 'REJECT')
        return rec
    preflight(i)
    p = ports(i)
    serial = f"emulator-{p['console']}"
    subprocess.run([ADB, '-P', str(ADB_PORT), 'start-server'], env=env(), check=True, capture_output=True)
    elog = open(STATE / f'emulator-{i}.log', 'ab')
    # nice 10 but NOT taskpolicy -b: background QoS pins qemu to the efficiency cores (~1 tick/s in block 1);
    # the ladder is paused tonight, so the Mac's other users only need nice priority over us.
    cmd = ['nice', '-n', '10', EMU, '-avd', AVD, '-port', str(p['console']), '-no-window',
           '-no-audio', '-no-snapshot', '-no-boot-anim', '-gpu', 'host', '-memory', '1536', '-cores', '2',
           '-read-only', '-no-metrics', '-grpc', str(p['grpc']), '-grpc-use-token']
    proc = subprocess.Popen(cmd, env=env(), stdout=elog, stderr=subprocess.STDOUT, start_new_session=True)
    rec = dict(inst=i, pid=proc.pid, serial=serial, **p, command=cmd, started=utc())
    try:
        atomic_write(STATE / f'inst-{i}.json', json.dumps(rec, indent=1))
    except BaseException:
        proc.kill()
        raise
    log(f'emulator pid {proc.pid} console {p["console"]}')
    if guard is not None:
        guard.start()  # monitoring from the moment the PID is recorded
    rec['headroom_at_start'] = headroom()
    t0 = time.time()
    while time.time() - t0 < 300:
        if guard is not None and guard.reason:
            raise Stop(guard.reason)
        if proc.poll() is not None:
            raise RuntimeError('emulator exited during boot')
        r = subprocess.run([ADB, '-P', str(ADB_PORT), '-s', serial, 'shell', 'getprop', 'sys.boot_completed'],
                           capture_output=True, text=True, env=env(), timeout=20)
        if r.stdout.strip() == '1':
            break
        time.sleep(3)
    else:
        raise RuntimeError('boot timeout')
    log(f'booted in {time.time() - t0:.0f} s')
    rec['children'] = children(proc.pid)
    atomic_write(STATE / f'inst-{i}.json', json.dumps(rec, indent=1))
    adb(serial, 'root', check=False)
    time.sleep(2)
    adb(serial, 'wait-for-device')
    adb(serial, 'shell', 'svc', 'wifi', 'disable')
    adb(serial, 'shell', 'svc', 'data', 'disable', check=False)
    dump = adb(serial, 'shell', 'dumpsys', 'package', PKG)
    uid = re.search(r'\b(?:userId|appId)=(\d+)\b', dump).group(1)
    for fw in ('iptables', 'ip6tables'):
        rule = ['OUTPUT', '-m', 'owner', '--uid-owner', uid, '!', '-o', 'lo', '-j', 'REJECT']
        if subprocess.run([ADB, '-P', str(ADB_PORT), '-s', serial, 'shell', fw, '-C', *rule], env=env(),
                          capture_output=True).returncode:
            adb(serial, 'shell', fw, '-A', *rule)
        adb(serial, 'shell', fw, '-C', *rule)  # raises if the REJECT rule is not in place
    adb(serial, 'shell', 'wm', 'size', '1080x1920')
    adb(serial, 'shell', 'am', 'compat', 'disable', 'NATIVE_HEAP_POINTER_TAGGING', PKG)
    adb(serial, 'forward', f"tcp:{p['probe']}", 'tcp:26789')
    adb(serial, 'shell', 'am', 'start', '-n', PKG + '/com.supercell.clashroyale.GameApp')
    rec.update(app_uid=uid, versions=re.findall(r'versionName=(\S+)', dump), firewall='REJECT non-lo',
               wm_size=adb(serial, 'shell', 'wm', 'size'), ready=utc())
    atomic_write(STATE / f'inst-{i}.json', json.dumps(rec, indent=1))
    log(f'setup done: uid {uid} {rec["wm_size"]!r}')
    return rec


def down(i, log=print):
    rec = receipt(i)
    if not rec:
        log(f'no receipt for instance {i}')
        return
    pid = rec['pid']
    (STATE / f'stopping-{i}').write_text(utc())
    if emulator_alive(rec):
        try:
            subprocess.run([ADB, '-P', str(ADB_PORT), '-s', rec['serial'], 'emu', 'kill'], env=env(),
                           capture_output=True, timeout=30)
        except Exception as e:  # noqa: BLE001 - fall through to the PID fallback
            log(f'adb emu kill failed: {e!r}')
        for _ in range(30):
            if not emulator_alive(rec):
                break
            time.sleep(1)
        else:
            for sig in (signal.SIGTERM, signal.SIGKILL):
                if emulator_alive(rec):
                    try:
                        os.kill(pid, sig)
                    except ProcessLookupError:
                        pass
                    time.sleep(5)
    # the launcher's qemu child(ren), recorded at boot; only if still ours (same AVD + console in argv)
    for c in rec.get('children', []):
        cmd = pid_cmd(c)
        if AVD in cmd and str(rec['console']) in cmd:
            try:
                os.kill(c, signal.SIGKILL)
            except ProcessLookupError:
                pass
    try:
        subprocess.run([ADB, '-P', str(ADB_PORT), '-s', rec['serial'], 'forward', '--remove',
                        f"tcp:{rec['probe']}"], env=env(), capture_output=True, timeout=20)
    except Exception as e:  # noqa: BLE001
        log(f'forward remove failed: {e!r}')
    (STATE / f'stopping-{i}').unlink(missing_ok=True)
    rec['stopped'] = utc()
    atomic_write(STATE / f'inst-{i}.json', json.dumps(rec, indent=1))
    if not live_instances():
        try:
            subprocess.run([ADB, '-P', str(ADB_PORT), 'kill-server'], env=env(), capture_output=True, timeout=20)
        except Exception as e:  # noqa: BLE001
            log(f'adb kill-server failed: {e!r}')
        log('last instance down: own adb server 5049 stopped')
    log(f'instance {i} stopped (pid {pid})')


# ----------------------------------------------------------------------------------------------- probe + gRPC
class Probe:
    def __init__(self, port):
        self.port = port

    def __call__(self, command, timeout=60):
        with socket.create_connection(('127.0.0.1', self.port), timeout=timeout) as s:
            s.sendall((command + '\n').encode())
            buf = bytearray()
            while chunk := s.recv(1 << 20):
                buf.extend(chunk)
        out = json.loads(buf)
        if not out.get('ok', False):
            raise RuntimeError(f'probe {command[:60]!r}: {str(out)[:300]}')
        return out


class Grpc:
    W, H = 1080, 2280

    def __init__(self, rec):
        sys.path.insert(0, str(Path.home() / 'clasher-live/nulls/grpc-deps'))
        import grpc
        import importlib.util
        token = None
        for ini in (Path.home() / 'Library/Caches/TemporaryItems/avd/running').glob('pid_*.ini'):
            kv = dict(l.strip().split('=', 1) for l in ini.read_text().splitlines() if '=' in l)
            if kv.get('grpc.port') == str(rec['grpc']) and kv.get('grpc.token'):
                token = kv['grpc.token']
        if not token:
            raise RuntimeError(f"no gRPC discovery file for port {rec['grpc']}")
        spec = importlib.util.spec_from_file_location('emulator_controller_pb2', HERE / 'emulator_controller_pb2.py')
        self.pb = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.pb)
        self.grpc_mod, self.addr = grpc, f"127.0.0.1:{rec['grpc']}"
        self.md = (('authorization', 'Bearer ' + token),)
        self.connect()
        self.req = self.pb.ImageFormat(format=self.pb.ImageFormat.RGB888, width=self.W, height=self.H)

    def connect(self):
        self.channel = self.grpc_mod.insecure_channel(self.addr, options=[('grpc.max_receive_message_length', 32 << 20)])
        self.rpc = self.channel.unary_unary('/android.emulation.control.EmulatorController/getScreenshot',
                                            request_serializer=self.pb.ImageFormat.SerializeToString,
                                            response_deserializer=self.pb.Image.FromString)

    def shot(self):
        try:
            f = self.rpc(self.req, metadata=self.md, timeout=15)
        except self.grpc_mod.RpcError:  # transient (broken pipe): reconnect once, then let it raise
            self.channel.close()
            time.sleep(1)
            self.connect()
            f = self.rpc(self.req, metadata=self.md, timeout=15)
        w, h = f.format.width, f.format.height
        if (w, h) != (self.W, self.H) or len(f.image) != w * h * 3:
            raise RuntimeError(f'gRPC frame {w}x{h} {len(f.image)} B; expected {self.W}x{self.H} RGB888')
        img = cv2.cvtColor(np.frombuffer(f.image, np.uint8).reshape(h, w, 3), cv2.COLOR_RGB2BGR)
        return img, f.timestampUs / 1e6, int(f.seq)


# ----------------------------------------------------------------------------------------------- capture
class Stop(Exception):
    pass


class Guard:
    """Host checks every 3 s from the moment the emulator PID is recorded. On a breach it flags the runner (which
    stops at its next probe call); if the runner has not brought the instance down within 90 s, the guard does it."""

    def __init__(self, i, log):
        self.i, self.log, self.reason, self.finished = i, log, None, threading.Event()
        self.thread = threading.Thread(target=self._loop, daemon=True)

    def start(self):
        if self.thread.ident is None:
            self.thread.start()

    def _loop(self):
        mem_hits = 0
        while not self.finished.is_set():
            try:
                reason = host_problem(self.i)
                if reason and reason.startswith('memory'):
                    # hysteresis: memory must stay breached ~15 s, and only one instance yields per 90 s (freeing an
                    # emulator takes seconds to show), unless swap >= 2 GiB or pressure is critical
                    mem_hits += 1
                    recent = any(time.time() - f.stat().st_mtime < 90 for f in STATE.glob('yield-*'))
                    critical = swap_used_gib() >= 2 * SWAP_LIMIT_GIB or pressure_level() >= 4
                    if not critical and (mem_hits < 5 or recent):
                        reason = None
                    else:
                        (STATE / f'yield-{self.i}').write_text(utc())
                else:
                    mem_hits = 0
            except Exception as e:  # noqa: BLE001 - an unreadable check is a stop
                reason = f'guard error {e!r}'
            if reason:
                self.reason = reason
                self.log(f'GUARD STOP: {reason}')
                if not self.finished.wait(90):
                    self.log('runner did not stop within 90 s: guard brings the instance down')
                    safe_down(self.i, self.log)
                    os._exit(3)
                return
            self.finished.wait(3)


DOWN_LOCK = threading.Lock()


def safe_down(i, log):
    with DOWN_LOCK:
        down(i, log)


class Capture:
    def __init__(self, i, rec, log, guard):
        self.i, self.rec, self.log, self.guard = i, rec, log, guard
        self.probe = Probe(rec['probe'])
        self.ts_ok = None  # does the gRPC frame timestamp share our clock? decided on the first frame
        self.stats = dict(frames=0, t0=time.time(), stale=0, unsynced=0)

    def check(self):
        if self.guard.reason:
            raise Stop(self.guard.reason)

    def call(self, command, timeout=30):
        self.check()
        return self.probe(command, timeout)

    def wait_ready(self):
        t0 = time.time()
        while time.time() - t0 < 420:
            self.check()
            try:
                a = self.probe('attest', timeout=20)['attestation']
                if a.get('production_ready'):
                    self.attest = a
                    self.log(f'attest ready after {time.time() - t0:.0f} s: '
                             + json.dumps({k: a.get(k) for k in list(a)[:12]})[:400])
                    return a
            except (OSError, ValueError, RuntimeError) as e:
                last = repr(e)[:120]
            time.sleep(4)
        raise RuntimeError('runtime never production_ready')

    def focus_ok(self):
        out = adb(self.rec['serial'], 'shell', 'dumpsys', 'window', timeout=20)
        lines = [l.strip() for l in out.splitlines() if 'mCurrentFocus=' in l]
        if lines and PKG + '/' in lines[0]:
            return True, lines
        # system dialogs (startup ANRs) sit on top of the game: close them, never touch the game itself
        adb(self.rec['serial'], 'shell', 'am', 'broadcast', '-a', 'android.intent.action.CLOSE_SYSTEM_DIALOGS',
            check=False)
        if any('Application Not Responding' in l for l in lines):
            adb(self.rec['serial'], 'shell', 'input', 'keyevent', 'KEYCODE_ENTER', check=False)  # "Wait"
        return False, lines

    def configure(self, cfg):
        for attempt in range(60):
            try:
                r = self.call('configure-native ' + json.dumps(cfg, separators=(',', ':')))
                break
            except RuntimeError as e:
                if 'not initialized' not in str(e) or attempt == 59:
                    raise
                time.sleep(5)
        t0 = time.time()
        while time.time() - t0 < 120:
            s = self.call('status')
            if s.get('nativeRenderLoaded') == r['sequence'] and s.get('nativeRenderReady'):
                break
            time.sleep(.3)
        else:
            raise RuntimeError('native scene did not load')
        p = self.call('pause')
        self.call('speed 1')
        self.call('render on')
        if p['tick'] < 200:
            self.call(f"advance-native {200 - p['tick']}")
        time.sleep(6)  # the stock intro animates on presentation time even while paused
        return r

    def snap(self, t_ready):
        """Frame rendered after t_ready (the advance's completion), with observe-rich before/after."""
        before = self.call('observe-rich')
        t_shot = time.time()
        fresh = False
        for k in range(40):
            if self.ts_ok is False:
                time.sleep(max(0.0, t_ready + 0.25 - time.time()))  # validated fallback: fixed render wait
            img, ts, seq = self.grpc.shot()
            if self.ts_ok is None:
                # emulator frame timestamps should be host unix time; otherwise use the fixed render wait
                self.ts_ok = abs(ts - time.time()) < 5
                self.log(f'gRPC timestamp {"is" if self.ts_ok else "is NOT"} host time (delta {ts - time.time():.3f} s)')
                if not self.ts_ok:
                    continue
            if not self.ts_ok or ts >= t_ready + 0.035:
                fresh = True
                break
            time.sleep(.012)
        after = self.call('observe-rich')
        plain = self.call('observe')
        sync = before['tick'] == after['tick'] == plain['tick'] and all(
            before.get(f) == after.get(f) for f in ('generation', 'stateEpoch', 'count', 'truncated')) \
            and not before.get('truncated') and strip(before['objects']) == strip(after['objects'])
        self.stats['stale'] += not fresh
        self.stats['unsynced'] += not sync
        return img, dict(before=before, after=after, plain=plain), dict(
            sync=sync, render_ts=ts, render_seq=seq, render_wait_s=round(ts - t_ready, 4) if self.ts_ok else None,
            render_fresh=fresh, render_clock='emulator-host' if self.ts_ok else 'fixed-wait-0.25s',
            shot_tries=k + 1, shot_s=round(time.time() - t_shot, 3))


def strip(objects):
    """Label-relevant object state (everything the labeller reads), for the before/after comparison."""
    return [(o.get('nativeObjectId'), o.get('owner'), o.get('dataGlobalId'), o.get('x'), o.get('y'), o.get('hp'),
             o.get('attackSequenceStage'), o.get('visibilityState'), json.dumps(o.get('activeEffects'), sort_keys=True),
             (o.get('phaseRuntime') or {}).get('deployRemainingMs'), (o.get('phaseRuntime') or {}).get('attackTimelineMs'))
            for o in objects]


class Run:
    """One scene: `card` for both teams (opposite lanes), then counters to cover attack/damage/stun/freeze/death."""

    def __init__(self, cap, card, location, seed, pass_no, variant='duel', level=None):
        self.cap, self.card, self.info = cap, card, CARDS[card]
        self.variant = variant
        self.base_for = {}
        self.mirror_base = variant.split('of-')[1] if variant.startswith('of-') else MIRROR_BASE
        if self.mirror_base not in CARDS:
            self.mirror_base = MIRROR_BASE
        self.owners = (1, 0) if variant in ('duel', 'mirror') or variant.startswith('of-') else (int(variant[-1]),)
        self.location, self.seed, self.pass_no = location, seed, pass_no
        self.level = level or LEVELS[pass_no % len(LEVELS) if isinstance(pass_no, int) else 0]
        self.id = (f"{card.replace(' ', '')}{'' if variant == 'duel' else '-' + variant}{'' if not level else '-lv' + str(level)}"
                   f"-L{location}-s{seed}-i{cap.i}-p{pass_no}-"
                   f"{time.strftime('%m%d%H%M%S', time.gmtime())}")
        self.dir = OUT / f'i{cap.i}' / self.id
        self.chunk_n, self.chunk, self.chunk_frames = 0, None, 0
        self.events, self.deployed = [], []
        self.frames = 0

    # ---- scene
    def deck(self):
        extra = [self.mirror_base] if self.card == 'Mirror' and self.mirror_base not in SUPPORT else []
        return [self.info['id']] + [CARDS[n]['id'] for n in extra + SUPPORT if n != self.card][:7]

    def config(self, order0, order1):
        c = json.loads(json.dumps(BASE))
        c['rndSeed'] = self.seed
        c['endTick'] = 7200
        c['battle']['location'] = self.location
        c['battle']['lvlcap'] = c['battle']['cardlvlmin'] = self.level
        for owner, order in ((0, order0), (1, order1)):
            c['battle'][f'deck{owner}']['sp'] = [{'d': d} for d in order]
        return c

    def hands(self, plain):
        return {p['owner']: p for p in plain['players']}

    def setup(self):
        """Scene where the target card is in BOTH starting hands. The initial shuffle depends on the seed and deck
        position, so the second try puts the target at a position that was in hand; reseed otherwise."""
        deck = self.deck()
        order = {0: list(deck), 1: list(deck)}
        for attempt in range(8):
            self.cap.configure(self.config(order[0], order[1]))
            plain = self.cap.call('observe')
            hands = self.hands(plain)
            missing = [o for o in self.owners if self.info['id'] not in [c['cardId'] for c in hands[o]['hand']]]
            self.events.append(dict(event='setup', attempt=attempt, seed=self.seed, missing=missing,
                                    hands={o: [c['cardId'] for c in hands[o]['hand']] for o in (0, 1)}))
            if not missing:
                return plain
            for o in missing:
                in_hand = [c['cardId'] for c in hands[o]['hand']]
                # move the target into a deck position whose card was dealt into the hand
                if attempt % 2 == 0 and in_hand:
                    swap_with = order[o].index(in_hand[0])
                    t = order[o].index(self.info['id'])
                    order[o][t], order[o][swap_with] = order[o][swap_with], order[o][t]
            if attempt >= 3 or self.card in NEVER_STARTING:
                # some cards are never dealt into the starting hand (Mirror; Elixir Collector here): cycle them in by
                # playing cheap hand cards behind the owner's king tower (those plays are extra data)
                if all(self.cycle_into_hand(o) for o in missing):
                    return self.cap.call('observe')
                raise RuntimeError(f'{self.card} could not be cycled into hand')
            if attempt % 2 == 1:
                self.seed += 7919
                order = {0: list(deck), 1: list(deck)}
        raise RuntimeError(f'{self.card} never in both starting hands')

    def cycle_into_hand(self, owner, budget_ticks=1500):
        back = (2000, 30500) if owner == 1 else (16000, 1500)
        t_end = None
        while True:
            plain = self.cap.call('observe')
            t_end = t_end or plain['tick'] + budget_ticks
            p = self.hands(plain)[owner]
            if self.info['id'] in [c['cardId'] for c in p['hand']]:
                self.events.append(dict(event='cycled-into-hand', owner=owner, tick=plain['tick']))
                return True
            if plain['tick'] > t_end:
                return False
            playable = sorted((c for c in p['hand'] if c['cardId'] != self.info['id'] and c['cardId'] in ID2NAME
                               and c.get('cost', 99) <= p.get('elixir', 0)), key=lambda c: c.get('cost', 99))
            if playable:
                self.schedule(owner, ID2NAME[playable[0]['cardId']], *back, plain['tick'] + 2)
                self.cap.call('advance-native 6')
            else:
                self.cap.call('advance-native 20')

    # ---- output
    def write(self, img, obs, meta, purpose, stride):
        if self.chunk is None:
            self.chunk_n += 1
            self.chunk = self.dir / f'chunk-{self.chunk_n:06d}'
            self.chunk.mkdir(parents=True)
            self.chunk_frames = 0
        tick = obs['before']['tick']
        stem = f'{self.id}-t{tick:06d}' + ('' if purpose != 'background' else f'-bg{self.frames:03d}')
        ok, jpg = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 95])
        if not ok:
            raise RuntimeError('jpeg encode failed')
        files = {stem + '.jpg': jpg.tobytes()}
        if self.frames % PNG_EVERY == 0:
            files[stem + '.png'] = cv2.imencode('.png', img, [cv2.IMWRITE_PNG_COMPRESSION, 3])[1].tobytes()
        files[stem + '.obs.json.gz'] = gzip.compress(json.dumps(obs, separators=(',', ':')).encode(), 4)
        for name, data in files.items():
            atomic_write(self.chunk / name, data, 'wb')
        hands = self.hands(obs['plain'])
        rec = dict(version='night-raw-1', frame=stem + '.jpg', png=(stem + '.png') if stem + '.png' in files else None,
                   observations=stem + '.obs.json.gz', run=self.id, card=self.card, card_id=self.info['id'],
                   card_kind=self.info['kind'], variant=self.variant, level=self.level, purpose=purpose, tick=tick, tick_stride=stride, time_scale=0.0,
                   stepping='paused advance-native, frame rendered after the advance', frame_shape=list(img.shape[:2]),
                   wm_size=self.cap.rec.get('wm_size'), location=self.location, seed=self.seed, pass_no=self.pass_no,
                   instance=self.cap.i, wall_epoch=time.time(), client=CLIENT_PIN,
                   hand={o: dict(slots=[c['cardId'] for c in hands[o]['hand']], next=hands[o].get('next'),
                                 elixir=hands[o].get('elixir')) for o in (0, 1)},
                   deployments=self.deployed, **meta)
        atomic_write(self.chunk / (stem + '.json'), json.dumps(rec, separators=(',', ':')))
        self.frames += 1
        self.chunk_frames += 1
        self.cap.stats['frames'] += 1
        if self.chunk_frames >= FRAMES_PER_CHUNK:
            self.seal()

    def seal(self):
        if self.chunk is None:
            return
        atomic_write(self.chunk / 'events.json', json.dumps(self.events))
        self.events = []
        files = {p.name: dict(bytes=p.stat().st_size, sha256=hashlib.sha256(p.read_bytes()).hexdigest())
                 for p in sorted(self.chunk.iterdir()) if not p.name.startswith('.')}
        atomic_write(self.chunk / 'manifest.json', json.dumps(dict(run=self.id, files=files)))
        atomic_write(self.chunk / 'READY', utc() + '\n')
        self.chunk = None

    # ---- play
    def schedule(self, owner, card, x, y, tick):
        cid = CARDS[card]['id']
        r = self.cap.call(f'replay-schedule-card {owner} {cid} {int(x)} {int(y)} {tick}')
        d = dict(owner=owner, card=card, card_id=cid, x=int(x), y=int(y), tick=tick, sequence=r['sequence'])
        self.deployed.append(d)
        self.events.append(dict(event='schedule', **d))
        return d

    def can_play(self, plain, owner, card):
        p = self.hands(plain)[owner]
        c = next((c for c in p['hand'] if c['cardId'] == CARDS[card]['id']), None)
        return c is not None and p.get('elixir', 0) >= c.get('cost', CARDS[card]['cost'])

    def mirror_pick(self, plain, owner):
        """Troop in hand for Mirror to copy: the configured base if dealt, else the cheapest troop in hand."""
        hand = [ID2NAME.get(c['cardId']) for c in self.hands(plain)[owner]['hand']]
        troops = [n for n in hand if n and n != 'Mirror' and CARDS[n]['kind'] == 'troop' and CARDS[n]['cost'] <= 5]
        if self.mirror_base in troops:
            return self.mirror_base
        return min(troops, key=lambda n: CARDS[n]['cost']) if troops else None

    def base_spot(self, owner):
        return (3500, 19500) if owner == 1 else (14500, 12500)

    def target_spot(self, owner):
        k = self.info['kind']
        if self.variant == 'mirror' and k == 'troop':  # same lane, close: the two teams meet and overlap at the river
            return (3500, 18500) if owner == 1 else (3500, 13500)
        if self.variant != 'duel' and k == 'troop':  # centre: swarm splits to both lanes and spreads
            return (9000, 19500) if owner == 1 else (9000, 12500)
        if k == 'spell':  # onto the opposing princess tower in the lane the other team's target walks down
            return (3500, 6500) if owner == 1 else (14500, 25500)
        if k == 'building':
            return (6000, 20500) if owner == 1 else (12000, 11500)  # clear of the princess towers
        return (3500, 19500) if owner == 1 else (14500, 12500)

    def go(self, max_ticks=900):
        cap = self.cap
        plain = self.setup()
        bg_obs = None
        for b in range(6):  # paused empty-arena backgrounds for the 05 labeller (idle tower/flag flicker included)
            time.sleep(.3)
            img, obs, meta = cap.snap(time.time())
            self.write(img, obs, meta, 'background', 0)
        # wait (uncaptured) for elixir to cover the target for both teams
        for _ in range(60):
            plain = cap.call('observe')
            if self.card == 'Mirror':
                bases = {o: self.mirror_pick(plain, o) for o in self.owners}
                if all(b and self.hands(plain)[o].get('elixir', 0) >= 2 * CARDS[b]['cost'] + 1
                       for o, b in bases.items()):
                    self.base_for = bases
                    break
            elif all(self.can_play(plain, o, self.card) for o in self.owners):
                break
            cap.call('advance-native 20')
        plain = cap.call('observe')  # fresh tick (the wait loop may have ended on an advance)
        tick0 = plain['tick']
        for owner in self.owners:
            if self.card == 'Mirror':  # base card first; Mirror (+1 level copy) once the base has landed
                self.schedule(owner, self.base_for.get(owner, self.mirror_base), *self.base_spot(owner), tick0 + 2)
                self.schedule(owner, self.card, *self.base_spot(owner), tick0 + 40)
            else:
                self.schedule(owner, self.card, *self.target_spot(owner), tick0 + 2)
        ours = set()  # native ids of objects spawned after deploy (target bodies + children)
        static = {o['nativeObjectId'] for o in cap.call('observe-rich')['objects']}
        counters = {0: [], 1: []}  # counters already used against owner's target
        last_hp, last_eff, gone, prev = {}, {}, {}, {}
        stride, tick, stalls = 1, tick0, 0
        end_after = None
        while tick - tick0 < max_ticks:
            cap.check()
            r = cap.call(f'advance-native {stride}')
            t_ready = time.time()
            img, obs, meta = cap.snap(t_ready)
            rich = obs['before']
            if rich['tick'] == tick and tick != tick0:
                stalls += 1
                if stalls >= 3:  # simulation no longer advances (battle over): end the run, keep what we have
                    self.events.append(dict(event='tick-stalled', tick=tick))
                    self.cap.log(f'{self.id}: tick stalled at {tick}; ending run')
                    break
                continue
            stalls = 0
            tick = rich['tick']
            objs = {o['nativeObjectId']: o for o in rich['objects'] if not o.get('null')}
            new = {k for k in objs if k not in static}
            ours |= new
            for k in list(prev):
                if k in ours and k not in objs and k not in gone:
                    gone[k] = tick
            # adaptive stride: 1 tick for spawn/deploy, hits landing, effect onset and deaths; 2 while attacking or
            # under an effect; 4 for plain walking/idle (near-duplicate frames otherwise)
            fast = medium = False
            for k, o in objs.items():
                ph = o.get('phaseRuntime') or {}
                hp, hp0, mhp = o.get('hp'), last_hp.get(k), o.get('maxHp') or 1
                if hp is not None and hp0 is not None and hp0 - hp > 0.005 * mhp:
                    fast = True  # a hit landed (building decay is < 0.5 %/tick)
                last_hp[k] = hp
                if k not in new:
                    continue
                effs = {e.get('name') for e in (o.get('activeEffects') or [])}
                if k not in prev or (ph.get('deployRemainingMs') or 0) > 0 or effs - last_eff.get(k, set()):
                    fast = True
                last_eff[k] = effs
                if effs or (ph.get('loadRemainingMs') or 0) > 0 or (ph.get('attackTimelineMs') or 0) > 0:
                    medium = True
            if any(tick - t <= 12 for t in gone.values()):
                fast = True  # death animations
            if self.variant == 'mirror':
                mine = [objs[k] for k in new if not objs[k].get('projectile') and objs[k].get('hp') is not None]
                if any(a.get('owner') != b.get('owner') and abs(a['x'] - b['x']) + abs(a['y'] - b['y']) < 2000
                       for a in mine for b in mine):
                    fast = True  # opposing bodies overlapping: every tick
            self.write(img, obs, meta, 'scene', stride)
            prev = objs
            scheduled = self.counter(obs['plain'], objs, new, counters, tick)
            # 1-tick steps for deploy/attack/damage/effects/death and right after a schedule (never skip its boundary)
            stride = 1 if fast or scheduled or tick - tick0 < 30 else 2 if medium else 4
            # never step past a pending deployment's boundary tick (execute tick - 1)
            for d in self.deployed:
                if d['tick'] - 1 > tick:
                    stride = min(stride, d['tick'] - 1 - tick)
            if tick - tick0 > 60 and not new:
                end_after = end_after or tick + 30
            if end_after and tick >= end_after:
                break
        self.seal()
        statuses = [cap.call(f"replay-schedule-status {d['sequence']}") for d in self.deployed]
        statuses = [dict(d, state=s.get('state'), error=s.get('error')) for d, s in zip(self.deployed, statuses)]
        failed = [s for s in statuses if s['state'] != 'succeeded']
        self.events.append(dict(event='run-end', tick=tick, frames=self.frames, statuses=statuses,
                                all_succeeded=not failed))
        if any(s['card'] == self.card and s['state'] != 'succeeded' for s in statuses):
            self.cap.log(f'{self.id}: target deployment not executed: {failed}')
        atomic_write(self.dir / 'DONE.json', json.dumps(dict(run=self.id, frames=self.frames, end=utc(),
                                                            events=self.events)))
        return self.frames

    def counter(self, plain, objs, new, counters, tick):
        """Per target side, the other team answers in turn: Zap (stun), Freeze, Knight (melee fight), Fireball."""
        scheduled = False
        if self.info['kind'] == 'spell' or self.variant not in ('duel', 'mirror'):
            return scheduled
        for target_owner in (0, 1):
            mine = [objs[k] for k in new if objs[k].get('owner') == target_owner and not objs[k].get('projectile')
                    and objs[k].get('hp') is not None
                    and not ((objs[k].get('phaseRuntime') or {}).get('deployRemainingMs') or 0) > 0]
            if not mine:
                continue
            used = counters[target_owner]
            if used and tick - used[-1][1] < 70:
                continue
            engaged = any(o.get('attackSequenceStage') not in (None, 0) or (o.get('hp') or 0) < (o.get('maxHp') or 0)
                          for o in mine)
            # buildings need a target to show attack poses: send the Knight first, immediately
            plan = ['Knight', 'Zap', 'Freeze', 'Fireball'] if self.info['kind'] == 'building' else \
                ['Zap', 'Freeze', 'Knight', 'Fireball']
            nxt = next((c for c in plan if c not in [u[0] for u in used]), None)
            if nxt is None or (nxt == 'Zap' and not engaged and tick - min(d['tick'] for d in self.deployed) < 160):
                continue
            o = mine[0]
            x, y = o['x'], o['y']
            if nxt == 'Knight':  # towards the target, inside the knight owner's own half (legal deploy zone)
                y = max(y + 1500, 17500) if target_owner == 0 else min(y - 1500, 14500)
            if self.can_play(plain, 1 - target_owner, nxt):
                self.schedule(1 - target_owner, nxt, min(17500, max(500, x)), min(31500, max(500, y)), tick + 2)
                used.append((nxt, tick))
                scheduled = True
            elif tick - (used[-1][1] if used else 0) > 200:
                used.append((nxt + '-skipped', tick))
        return scheduled


def queue():
    """Items are 'Card' (duel: both teams, counters) or 'Card#solo1' / 'Card#solo0' (one team alone, centre
    deploy so swarms split to both lanes and spread: clean swarm boxes)."""
    q = json.loads((HERE / 'queue.json').read_text())
    order = [n for n in q['order'] if n.split('#')[0] in CARDS]
    solo = [f'{n}#solo{t}' for n in q.get('solo', []) if n in CARDS for t in (1, 0)]
    rest = sorted(n for n, c in CARDS.items() if c['in_nulls'] and n not in order)
    skip = set(q.get('skip', []))
    return [n for n in order + solo + rest if n.split('#')[0] not in skip]


def claim(i):
    """Passes 0-1 over the full queue, then queue.json `targeted` (pass 'T': items 'Card[#variant][@LEVEL]', in
    order, repeats allowed as 'Card#v@15*3'), then further full passes."""
    claims = STATE / 'claims'
    claims.mkdir(parents=True, exist_ok=True)
    cards = queue()
    targeted = []
    for it in json.loads((HERE / 'queue.json').read_text()).get('targeted', []):
        base, _, rep_n = it.partition('*')
        targeted += [f'{base}~{r}' for r in range(int(rep_n or 1))]
    order = [(p, c) for p in (0, 1) for c in cards] + [('T', c) for c in targeted] + \
        [(p, c) for p in range(2, 50) for c in cards]
    for pass_no, card in order:
        if True:
            try:
                (claims / f'p{pass_no}-{card}').mkdir()
            except FileExistsError:
                continue
            (claims / f'p{pass_no}-{card}' / f'i{i}').write_text(utc())
            return card, pass_no
    return None, None


def run(i):
    STATE.mkdir(parents=True, exist_ok=True)
    (OUT / f'i{i}').mkdir(parents=True, exist_ok=True)
    logf = open(STATE / f'night-{i}.log', 'a')

    def log(msg):
        line = f'{utc()} i{i} {msg}'
        print(line, flush=True)
        logf.write(line + '\n')
        logf.flush()

    import fcntl
    lockf = open(STATE / f'lock-{i}', 'w')
    try:  # one runner per instance for the whole boot/capture/teardown
        fcntl.flock(lockf, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        log('another runner holds this instance; exiting')
        return
    atomic_write(STATE / f'runner-{i}.pid', str(os.getpid()))
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    guard = Guard(i, log)
    rec = None
    keep_up = False
    try:
        rec = up(i, log, guard)
        guard.start()
        cap = Capture(i, rec, log, guard)
        cap.wait_ready()
        for k in range(60):
            cap.check()
            ok, lines = cap.focus_ok()
            if ok:
                break
            log(f'focus not on game: {lines}')
            time.sleep(5)
        else:
            raise RuntimeError('game never focused')
        cap.grpc = Grpc(rec)
        n_runs = 0
        while True:
            cap.check()
            if (ROOT / f'RELOAD-{i}').exists():
                (ROOT / f'RELOAD-{i}').unlink()
                log('RELOAD: leaving the emulator up for a new runner')
                keep_up = True
                break
            card, pass_no = claim(i)
            if card is None:
                log('queue exhausted')
                break
            item, _, rep_i = card.partition('~')
            name_var, _, lvl = item.partition('@')
            name, _, variant = name_var.partition('#')
            pnum = pass_no if isinstance(pass_no, int) else 100 + int(rep_i or 0)
            location = LOCATIONS[(random.Random(name).randrange(1000) + pnum) % len(LOCATIONS)]  # stable per card+pass
            seed = 20261017 + 1000 * pnum + random.Random(card).randrange(1000)
            r = Run(cap, name, location, seed, pass_no, variant=variant or 'duel', level=int(lvl) if lvl else None)
            t0, f0 = time.time(), cap.stats['frames']
            log(f'start {r.id} ({r.info["kind"]})')
            try:
                n = r.go()
            except (Stop, KeyboardInterrupt):
                r.seal()
                raise
            except Exception as e:  # noqa: BLE001 - one bad scene must not end the night; log and continue
                r.seal()
                log(f'run {r.id} FAILED: {e!r}')
                (STATE / 'claims' / f'p{pass_no}-{card}' / 'FAILED').write_text(repr(e))
                n_runs += 1
                if n_runs > 3 and cap.stats['frames'] == 0:
                    raise
                continue
            dt = time.time() - t0
            n_runs += 1
            log(f'done {r.id}: {n} frames in {dt:.0f} s ({n / dt:.2f} fps); total {cap.stats["frames"]}; '
                f'{json.dumps(headroom())}')
    except Stop as e:
        log(f'stopping: {e}')
    except KeyboardInterrupt:
        log('SIGTERM/interrupt')
    except Exception as e:  # noqa: BLE001
        log(f'FATAL {e!r}')
        raise
    finally:
        if not keep_up:
            safe_down(i, log)
        guard.finished.set()


def status():
    for i in range(8):
        rec = receipt(i)
        if rec:
            print(i, 'alive' if emulator_alive(rec) else 'down', rec.get('pid'), rec.get('started'), rec.get('stopped'))
    print(json.dumps(headroom()))


def start(i):
    """Detached runner (own session: survives the ssh/T3 session); prints its PID."""
    STATE.mkdir(parents=True, exist_ok=True)
    out = open(STATE / f'runner-{i}.out', 'ab')
    proc = subprocess.Popen(['nice', '-n', '5', sys.executable, '-B', str(Path(__file__).resolve()), 'run', '--inst', str(i)],
                            stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True,
                            env=dict(os.environ, PYTHONHASHSEED='0', NUMPY_MADVISE_HUGEPAGE='0'))
    print('runner pid', proc.pid)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('action', choices=['start', 'run', 'down', 'status'])
    ap.add_argument('--inst', type=int, default=0)
    a = ap.parse_args()
    if a.inst not in range(4):
        raise SystemExit('instances 0..3 only')
    {'start': lambda: start(a.inst), 'run': lambda: run(a.inst), 'down': lambda: down(a.inst),
     'status': status}[a.action]()
