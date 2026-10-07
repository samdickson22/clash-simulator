"""Owned offline renderer utilities, shared only by collection and evaluation."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT/'scripts'))
from smoke_reference_battle import request
from l1_native_capture_v3 import consistent_observation
ADB = Path.home()/'.cache/clasher-native-reference/android-sdk/platform-tools/adb'
PROTO = HERE.parent/'l1/v1/grpc'
PIN = '864227bf7208aa9c06cd976db3fa0734a32277b0552f92e496ad283a917b4a93'


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')
    tmp.replace(path)


def append(path, value):
    with Path(path).open('a') as f: f.write(json.dumps(value, separators=(',', ':'), allow_nan=False)+'\n')


def sha(path):
    with Path(path).open('rb') as f: return hashlib.file_digest(f, 'sha256').hexdigest()


class Renderer:
    def __init__(self, path):
        self.owner = json.loads(Path(path).read_text())
        os.environ['ANDROID_ADB_SERVER_PORT'] = str(self.owner['adb_port'])
        self.discovery = Path.home()/f"Library/Caches/TemporaryItems/avd/running/pid_{self.owner['pid']}.ini"
        self.verify()

    def adb(self, *args):
        return subprocess.run([str(ADB), '-P', str(self.owner['adb_port']), '-s', self.owner['serial'], *args],
                              capture_output=True, text=True, check=True, timeout=30, close_fds=False).stdout

    def verify(self):
        cmd = subprocess.check_output(['/bin/ps', '-p', str(self.owner['pid']), '-o', 'command='], text=True, close_fds=False)
        if self.owner.get('process_start'):
            assert subprocess.check_output(['/bin/ps','-p',str(self.owner['pid']),'-o','lstart='],text=True,close_fds=False).strip()==self.owner['process_start']
        assert 'clasher_reference_api35' in cmd and '-port '+self.owner['serial'].split('-')[1] in cmd
        assert '-gpu '+self.owner['render_backend'] in cmd and '-read-only' in cmd
        for firewall in ('iptables', 'ip6tables'):
            self.adb('shell', firewall, '-C', 'OUTPUT', '-m', 'owner', '--uid-owner', str(self.owner['app_uid']), '!', '-o', 'lo', '-j', 'REJECT')
        att = self.call('attest')
        assert hashlib.sha256(json.dumps(att,sort_keys=True,separators=(',', ':')).encode()).hexdigest() == PIN

    def call(self, command):
        try: return request(self.owner['probe_port'], command)
        except ConnectionRefusedError:
            # Refusal means no bytes reached the server. Never retry a lost mutation response.
            mapping = self.adb('forward', '--list')
            rows = [r.split() for r in mapping.splitlines() if len(r.split()) == 3 and r.split()[1] == f"tcp:{self.owner['probe_port']}"]
            expected = [self.owner['serial'], f"tcp:{self.owner['probe_port']}", 'tcp:26789']
            if rows and rows != [expected]: raise RuntimeError('Foreign forward on owned probe port')
            if not rows: self.adb('forward', '--no-rebind', expected[1], expected[2])
            return request(self.owner['probe_port'], command)

    def configure(self, config, tick=340):
        seq = self.call('configure-native '+json.dumps(config,separators=(',', ':')))['sequence']
        deadline = time.monotonic()+45
        while time.monotonic() < deadline:
            s = self.call('status')
            if s['nativeRenderLoaded'] == seq and s['nativeRenderReady']: break
            time.sleep(.1)
        else: raise TimeoutError('Renderer load')
        at = self.call('pause')['tick']
        self.call('speed 4'); self.call('render on')
        while at < tick: at = self.call(f'advance-native {min(1000,tick-at)}')['tick']
        self.call('speed 1')
        return self.call('observe')

    def observe(self): return consistent_observation(self.call)

    def atomic(self):
        begin=time.perf_counter_ns();value=self.call('observe-atomic');end=time.perf_counter_ns()
        if value.get('atomic') is not True:raise ValueError('Atomic capture unavailable')
        ordinary,rich=value['ordinary'],value['rich']
        for frame in (ordinary,rich):
            if frame.get('truncated') or frame['count']!=frame['returned']:raise ValueError('Incomplete atomic observation')
            if any(frame[k]!=value[k] for k in ('generation','stateEpoch','tick')):raise ValueError('Atomic identity mismatch')
        key=[ordinary[k] for k in ('generation','stateEpoch','tick','steps')]
        return ordinary,rich,dict(start_ns=begin,end_ns=end,before=key,after=key,atomic_probe=True,no_logic_step_during_observation=True)

    def rich(self):return self.atomic()[1]


from input_channel import GrpcInput as PixelGrpcInput


class GrpcInput(PixelGrpcInput):
    """Evaluation adapter. Pixel actors use input_channel.GrpcInput directly."""
    def __init__(self, renderer):
        super().__init__(renderer.owner['grpc_port'], PROTO, renderer.discovery)
