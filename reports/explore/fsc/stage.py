"""FSC staging on a host (stdlib, python3 -I; exploration, NEVER ADOPTABLE).

  install J BUNDLE HOST   install the overlay from BUNDLE into J/repo/reports/explore/{x4s2,fsc}, then verify the
                          whole runtime: S1 pin (all files), native, checkpoints, X4S2 files at 1501be97f, and
                          the FSC edits; write J/staging.json. Writes only under J. Exit 1 on any mismatch.
"""
import datetime, hashlib, json, shutil, socket, subprocess, sys
from pathlib import Path

PIN_SHA256 = 'f81f36558179458ba74edd3a57f44ad3395f4452a93c64d3102c4f4d5048a80d'  # s1-runtime-pin-r2.json
NATIVE = '44874fd6047aa53f8f5c46fd3a77e4e2c8672f98dbcf6d758fbf90ee043a5be2'
INPUTS = {'main02.pt': 'd77005d59d6ed40ce7f9bfcfde569b54958bebf056e00653b10dcee3957272ed',
          'R3a.pt': '37509a4331bd02ae110b76e1825a2adb23fa78e0e70188e199b6ef90d19ade85',
          'R3a-calibration.json': 'e300353346983e888d896b20412d4075496a6f14ef3625cefc7eeadacec5e414'}
# X4S2 files installed unchanged from git 1501be97f.
X4S2 = {'anchor_x.py': 'cf528473278d4fbf9ffd8aecfd4a3350fe1dbb6bbeb0d441870c9f88bad3ec98',
        'sdefault.py': '6da69e5de05b4df564b9c7772466f97af300cf44538a05e1e5c902347759e066',
        'runtime.sh': '21349cdd9d9cbd933ca192306a1704fa9fd5c9ae3d80479105a97b10f13fbdd9',
        'detach.sh': 'd421c9a652d3223046100309bf1e3e21581cd46bef7be25ca291abaf71f03de7',
        'plan.json': '078d5bbce2bc6b402041d772cb5e37738ceb07f61903e71243d0b683c3b9b5b0',
        'plan-ext.json': '31c5cd4a12faf9f5f46f2bf5cee02d89971d0fe9a76ff97c8b48333c3a5b816f',
        'reduce.py': '0abcf12733224550962bd6307c278c2a0649fa4afe01ef04f0b7a1a1b8d78097',
        'leftover.py': 'bb68fe43d2919b504ce57782dba76f165525cfbeb60c37c932340c595833e382'}
JOBS = {'127x03': '/mpac/sdicks02/jobs/clasher/fsc-03-20261013', '127x04': '/mpac/sdicks02/jobs/clasher/fsc-04-20261013'}


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    assert sys.argv[1] == 'install'
    J, bundle, host = Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4]
    assert socket.gethostname() == host and str(J) == JOBS[host]
    manifest = json.loads((bundle/'MANIFEST.json').read_text())
    for rel, h in manifest['files'].items():
        assert sha(bundle/rel) == h, rel
    for name, h in X4S2.items():
        assert manifest['files'][f'x4s2/{name}'] == h, name
    ex = J/'repo/reports/explore'
    assert (J/'repo').is_dir() and not (ex/'fsc').exists()
    (ex/'x4s2').mkdir(exist_ok=False)
    installed = {}
    for name in X4S2:
        installed[f'x4s2/{name}'] = f'x4s2/{name}'
    installed['x4s2/run.py'] = 'fsc/harness/run.py'
    installed['x4s2/supervise.py'] = 'fsc/harness/supervise.py'
    if host == '127x04':
        installed['x4s2/plan.json'] = 'fsc/harness/plan-04.json'  # checkpoint paths -> J04/inputs; nothing else differs
    for rel in manifest['files']:
        if rel.startswith('fsc/'):
            installed[rel] = rel
    for dst, src in sorted(installed.items()):
        (ex/dst).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(bundle/src, ex/dst)
    # Verify the whole runtime as installed.
    for dst, src in installed.items():
        assert sha(ex/dst) == manifest['files'][src], dst
    pin_path = ex/'fsc/s1-runtime-pin-r2.json'
    assert sha(pin_path) == PIN_SHA256
    pin = json.loads(pin_path.read_text())
    bad = [f for f, h in pin['files'].items() if not (J/'repo'/f).is_file() or sha(J/'repo'/f) != h]
    assert not bad, bad[:5]
    assert sha(J/'native/clasher_core.abi3.so') == NATIVE == pin['native_sha256']
    for name, h in INPUTS.items():
        assert sha(J/'inputs'/name) == h, name
    plan = json.loads((ex/'x4s2/plan.json').read_text())
    for key, name in (('policy', 'main02.pt'), ('student', 'R3a.pt')):
        ck = Path(plan[key]['checkpoint'])
        assert sha(ck) == plan[key]['checkpoint_sha256'] == INPUTS[name], key
        if host == '127x04':
            assert ck == J/'inputs'/name
    py = '/mpac/sdicks02/repos/clasher/.venv/bin/python'
    versions = subprocess.run([py, '-I', '-B', '-c', 'import sys,numpy,torch;print(sys.version.split()[0],numpy.__version__,torch.__version__)'],
                              capture_output=True, text=True, timeout=300,
                              env={'CUDA_VISIBLE_DEVICES': '', 'XDG_CACHE_HOME': str(J/'cache'), 'HOME': str(J)}).stdout.strip()
    assert versions, 'runtime python failed to import numpy/torch'
    receipt = dict(utc=datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), host=host, job=str(J),
                   bundle_manifest_sha256=sha(bundle/'MANIFEST.json'), commit=manifest['commit'],
                   s1_pin_files_verified=len(pin['files']), native_sha256=NATIVE, inputs_sha256=INPUTS,
                   installed={dst: manifest['files'][src] for dst, src in sorted(installed.items())},
                   checkpoint_paths={k: plan[k]['checkpoint'] for k in ('policy', 'student')},
                   python_numpy_torch=versions, python_sha256=sha(Path(py).resolve()))
    (J/'staging.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps({k: receipt[k] for k in ('utc', 'host', 'bundle_manifest_sha256', 'commit', 's1_pin_files_verified',
                                              'checkpoint_paths', 'python_numpy_torch')}))


if __name__ == '__main__':
    main()
