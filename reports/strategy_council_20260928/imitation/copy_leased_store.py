"""Copy a certified store on a leased receiver, inside its lease-aware wrapper.

Stage this file and verify_artifacts.py in data/imitation-copy-v1/. Launch only
after inspecting the live lease and hub readiness receipt. No training starts.
"""
import datetime as dt
import hashlib
import json
from pathlib import Path
import shlex
import signal
import socket
import subprocess
import time

from verify_artifacts import sha, verify

BASE = Path('/mpac/sdicks02/repos/clasher-lease')
SOURCE = Path('/mpac/sdicks02/repos/clasher/reports/strategy_council_20260928/imitation/data')
HOSTS = {'127x11', '127x13', '127x14'}
COORDINATOR = '0523ae6f-baa3-4d4e-b233-b392671670db'
active_child = None


def stop(signum, frame):
    if active_child is not None and active_child.poll() is None:
        active_child.terminate()
        try:
            active_child.wait(timeout=20)
        except subprocess.TimeoutExpired:
            active_child.kill()
            active_child.wait()
    raise SystemExit(128 + signum)


def run(args):
    global active_child
    print(shlex.join(map(str, args)), flush=True)
    active_child = subprocess.Popen(list(map(str, args)), stdout=subprocess.PIPE, text=True)
    output, _ = active_child.communicate()
    code = active_child.returncode
    active_child = None
    if code:
        raise subprocess.CalledProcessError(code, args, output)
    return output


def remote_read(path):
    return run(['ssh', '-o', 'BatchMode=yes', '127x01', shlex.join(['cat', str(path)])])


def lease(host):
    value = json.loads((Path('/mpac/sdicks02/fleet-leases') / (host + '.json')).read_text())
    assert value['project'] == 'clasher' and value['coordinator_thread'] == COORDINATOR
    assert not value.get('refused') and not value.get('reclaim')
    assert dt.datetime.fromisoformat(value['expected_end_utc'].replace('Z', '+00:00')) > dt.datetime.now(dt.timezone.utc)
    return value


def main():
    started = time.monotonic()
    host = socket.gethostname().split('.')[0]
    assert host in HOSTS
    assert Path(__file__).resolve().parent == BASE / 'data/imitation-copy-v1'
    lease(host)
    ready = json.loads(remote_read(Path('/mpac/sdicks02/jobs/clasher') / f'lease-ready-{host}.json'))
    assert ready['qualified']
    certificate = remote_read(SOURCE / 'receipts/T3-PASS.json')
    cert = json.loads(certificate)
    assert cert['passed'] and cert['roundtrip_exact']
    assert cert['roundtrip_perspectives'] == 805 and cert['store'] == str(SOURCE / 'c56-store-v1')
    manifest_text = remote_read(SOURCE / 'c56-store-v1/manifest.json')
    manifest = json.loads(manifest_text)
    digest = hashlib.sha256(manifest_text.encode()).hexdigest()
    assert manifest['passed'] and manifest['roles'] == cert['roles']
    assert cert['store_manifest_sha256'] == digest
    files = ['manifest.json', 'plan.json', 'mask_table.npy']
    for role, expected in manifest['role_manifests'].items():
        assert role in {'train', 'dev', 'eval', 'eval_ood'}
        text = remote_read(SOURCE / 'c56-store-v1' / role / 'manifest.json')
        assert hashlib.sha256(text.encode()).hexdigest() == expected
        local = json.loads(text)
        files.append(f'{role}/manifest.json')
        for name in local['arrays']:
            assert name and '/' not in name and name not in {'.', '..'}
            files.append(f'{role}/{name}.npy')
    work = Path(__file__).resolve().parent
    listing = work / 'store-files.txt'
    listing.write_text('\n'.join(files) + '\n')
    target = BASE / 'data/c56-store-v1'
    target.mkdir(parents=True, exist_ok=True)
    source = f'127x01:{SOURCE}/c56-store-v1/'
    run(['rsync', '-cr', '--partial', '--files-from', listing, source, str(target) + '/'])
    lease(host)
    difference = run(['rsync', '-crni', '--files-from', listing, source, str(target) + '/'])
    (work / 'checksum-dry-run.txt').write_text(difference)
    assert not difference, difference[:2000]
    assert sha(target / 'manifest.json') == digest
    verify(target, 'store')
    lease(host)
    assert remote_read(SOURCE / 'receipts/T3-PASS.json') == certificate
    (target / 'T3-PASS.json').write_text(certificate)
    result = json.loads((target / f'copy-verified-{host}.json').read_text())
    result.update(certificate_sha256=sha(target / 'T3-PASS.json'),
                  checksum_dry_run_equal=True, transferred_files=len(files),
                  total_wall_seconds=time.monotonic() - started,
                  finished_utc=dt.datetime.now(dt.timezone.utc).isoformat())
    temporary = work / 'receipt.tmp'
    temporary.write_text(json.dumps(result, indent=2) + '\n')
    temporary.replace(work / 'receipt.json')
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, stop)
    main()
