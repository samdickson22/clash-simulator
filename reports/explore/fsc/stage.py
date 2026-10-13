"""FSC staging on a host (stdlib, python3 -I; exploration, NEVER ADOPTABLE). Every failure raises (exit != 0).

  allowlist BUNDLE OUT          files-from list for the repo copy: exactly the S1 runtime pin's files (no protected path)
  shadowscan BASE_REPO BUNDLE   03 only, read-only: refuse if the source repo holds an unpinned top-level module/package in
                                a runtime import directory that shares a name with a pinned or overlay module
  need BASE BUNDLE              03 only, read-only (lstat): bytes the allowlisted copy will write (pin files, native, inputs)
  nolinks DIR                   refuse if DIR is not canonical or anything under it is a symlink or non-regular file
  install J BUNDLE HOST MANIFEST_SHA256
                                install the overlay into J/repo/reports/explore/{x4s2,fsc}, refusing symlinks and any
                                write outside canonical J; verify the S1 pin (all files), native (all files, listed),
                                checkpoints, X4S2 files at 1501be97f and FSC files; write J/staging.json
"""
import datetime, hashlib, json, os, shutil, socket, stat, subprocess, sys
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
JOBS = {'127x03': '/mpac/sdicks02/jobs-fsc/fsc-03-20261013b', '127x04': '/mpac/sdicks02/jobs-fsc/fsc-04-20261013'}
PROTECTED = ('t1', 'corpus', 'x4s', 'x4s2', 'fsc', 'k4s-confirm', 'jobs-k4s', 'perception')
# Runtime import directories (runtime.sh PYTHONPATH and run.py's sys.path inserts), relative to the repo.
IMPORT_DIRS = ('', 'src', 'engine-rs', 'reports/explore/x4s2', 'reports/explore/s1', 'student-source', 'reports/explore/e1',
               'reports/strategy_council_20260928/engine-speed/stage5', 'reports/strategy_council_20260928/engine-speed',
               'reports/strategy_council_20260928/search-noise-s6', 'reports/strategy_council_20260928/search-noise-s4',
               'reports/perf-audit/quickwins')


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def protected(rel):
    return any(c in PROTECTED or c.startswith(('t1-', 'k4s-')) for c in Path(rel).parts)


def pin_files(bundle):
    path = Path(bundle)/'fsc/s1-runtime-pin-r2.json'
    assert sha(path) == PIN_SHA256
    files = json.loads(path.read_text())['files']
    assert files and not any(protected(f) or f.startswith('/') or '..' in Path(f).parts for f in files)
    return files


def nolinks(d):
    """d must be canonical; nothing at or under d may be a symlink; only regular files and directories."""
    d = Path(d)
    assert os.path.realpath(d) == str(d) and stat.S_ISDIR(os.lstat(d).st_mode), d
    n = 0
    for root, dirs, files in os.walk(d, followlinks=False):
        for name in dirs+files:
            mode = os.lstat(os.path.join(root, name)).st_mode
            assert stat.S_ISDIR(mode) or stat.S_ISREG(mode), os.path.join(root, name)
            n += 1
    return n


def inside(J, path):
    """Refuse a write target unless its existing ancestry resolves under canonical J with no symlink on the way."""
    path = Path(path); assert path.is_absolute() and '..' not in path.parts
    rel = path.relative_to(J)
    cur = Path(J)
    for part in rel.parts:
        cur = cur/part
        if os.path.lexists(cur):
            assert not stat.S_ISLNK(os.lstat(cur).st_mode), cur
    assert os.path.realpath(path.parent).startswith(str(J)+'/') or os.path.realpath(path.parent) == str(J)
    return path


def modules(names):
    return {n[:-3] if n.endswith('.py') else n for n in names}


def shadowscan(base_repo, bundle):
    base_repo = Path(base_repo); assert os.path.realpath(base_repo) == str(base_repo)
    pinned = set(pin_files(bundle))
    known = {}  # module/package name -> pinned or overlay dirs
    for f in list(pinned)+[f'reports/explore/x4s2/{n}' for n in ('anchor_x.py', 'sdefault.py', 'run.py', 'supervise.py')]:
        parent, name = os.path.split(f)
        if parent in IMPORT_DIRS and name.endswith('.py'):
            known.setdefault(name[:-3], set()).add(parent)
        for d in IMPORT_DIRS:  # packages: first component below an import dir
            prefix = d+'/' if d else ''
            if f.startswith(prefix) and '/' in f[len(prefix):]:
                known.setdefault(f[len(prefix):].split('/')[0], set()).add(d)
    clashes = []
    for d in IMPORT_DIRS:
        src = base_repo/d
        if not src.is_dir() or protected(d):
            continue
        for entry in os.scandir(src):  # top level only; never descends into other trees
            rel = f'{d}/{entry.name}' if d else entry.name
            if protected(rel):
                continue
            is_mod = entry.name.endswith('.py') and entry.is_file(follow_symlinks=False)
            is_pkg = entry.is_dir(follow_symlinks=False) and (Path(entry.path)/'__init__.py').is_file()
            if (is_mod and rel not in pinned) or (is_pkg and not any(p.startswith(rel+'/') for p in pinned)):
                name = entry.name[:-3] if is_mod else entry.name
                if name in known:
                    clashes.append(rel)
    assert not clashes, ('unpinned module shadows a runtime module', clashes)
    return dict(shadowscan='ok', import_dirs=len(IMPORT_DIRS))


def install(J, bundle, host, manifest_sha):
    J, bundle = Path(J), Path(bundle)
    assert socket.gethostname() == host and str(J) == JOBS[host] and bundle == J/'bundle'
    assert sha(bundle/'MANIFEST.json') == manifest_sha
    manifest = json.loads((bundle/'MANIFEST.json').read_text())
    listed = {str(p.relative_to(bundle)) for p in bundle.rglob('*') if p.is_file()} - {'MANIFEST.json'}
    assert listed == set(manifest['files'])
    for rel, h in manifest['files'].items():
        assert sha(bundle/rel) == h, rel
    for name, h in X4S2.items():
        assert manifest['files'][f'x4s2/{name}'] == h, name
    nolinks(J)
    pin = pin_files(bundle)
    ex = J/'repo/reports/explore'
    assert (J/'repo').is_dir() and not os.path.lexists(ex/'fsc') and not os.path.lexists(ex/'x4s2')
    installed = {f'x4s2/{name}': f'x4s2/{name}' for name in X4S2}
    installed['x4s2/run.py'] = 'fsc/harness/run.py'
    installed['x4s2/supervise.py'] = 'fsc/harness/supervise.py'
    if host == '127x04':
        installed['x4s2/plan.json'] = 'fsc/harness/plan-04.json'  # checkpoint paths -> J04/inputs; nothing else differs
    for rel in manifest['files']:
        if rel.startswith('fsc/'):
            installed[rel] = rel
    for dst, src in sorted(installed.items()):
        target = inside(J, ex/dst)
        target.parent.mkdir(parents=True, exist_ok=True)
        inside(J, target)
        assert not os.path.lexists(target)
        shutil.copyfile(bundle/src, target, follow_symlinks=False)
    # Verify the whole runtime as installed; nothing in J may be a symlink.
    entries = nolinks(J)
    for dst, src in installed.items():
        assert sha(ex/dst) == manifest['files'][src], dst
    pinj = json.loads((bundle/'fsc/s1-runtime-pin-r2.json').read_text())
    bad = [f for f in pin if not (J/'repo'/f).is_file() or sha(J/'repo'/f) != pinj['files'][f]]
    assert not bad, bad[:5]
    repo_files = {str(p.relative_to(J/'repo')) for p in (J/'repo').rglob('*') if p.is_file()}
    extra = repo_files - set(pin) - {f'reports/explore/{d}' for d in installed}
    assert not extra, sorted(extra)[:5]  # the repo holds exactly the pin plus the overlay
    native = {str(p.relative_to(J/'native')): sha(p) for p in sorted((J/'native').rglob('*')) if p.is_file()}
    assert native.get('clasher_core.abi3.so') == NATIVE == pinj['native_sha256']
    assert sorted(p.name for p in (J/'inputs').iterdir()) == sorted(INPUTS)
    for name, h in INPUTS.items():
        assert sha(J/'inputs'/name) == h, name
    plan = json.loads((ex/'x4s2/plan.json').read_text())
    for key, name in (('policy', 'main02.pt'), ('student', 'R3a.pt')):
        ck = Path(plan[key]['checkpoint'])
        assert sha(ck) == plan[key]['checkpoint_sha256'] == INPUTS[name], key
        if host == '127x04':
            assert ck == J/'inputs'/name
    py = '/mpac/sdicks02/repos/clasher/.venv/bin/python'
    probe = subprocess.run([py, '-I', '-B', '-c', 'import sys,numpy,torch;print(sys.version.split()[0],numpy.__version__,torch.__version__)'],
                           capture_output=True, text=True, timeout=300,
                           env={'CUDA_VISIBLE_DEVICES': '', 'XDG_CACHE_HOME': str(J/'cache'), 'HOME': str(J/'cache')})
    assert probe.returncode == 0 and len(probe.stdout.split()) == 3, (probe.returncode, probe.stderr[-500:])
    receipt = dict(utc=datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), host=host, job=str(J),
                   bundle_manifest_sha256=manifest_sha, commit=manifest['commit'], s1_pin_files_verified=len(pin),
                   repo_files=len(repo_files), entries_checked_no_symlinks=entries, native_files=native,
                   native_sha256=NATIVE, inputs_sha256=INPUTS,
                   installed={dst: manifest['files'][src] for dst, src in sorted(installed.items())},
                   checkpoint_paths={k: plan[k]['checkpoint'] for k in ('policy', 'student')},
                   python_numpy_torch=probe.stdout.strip(), python_sha256=sha(Path(py).resolve()))
    out = inside(J, J/'staging.json'); assert not os.path.lexists(out)
    out.write_text(json.dumps(receipt, indent=2)+'\n')
    nolinks(J)
    return {k: receipt[k] for k in ('utc', 'host', 'bundle_manifest_sha256', 'commit', 's1_pin_files_verified', 'repo_files',
                                    'native_files', 'checkpoint_paths', 'python_numpy_torch')}


def main():
    cmd = sys.argv[1]
    if cmd == 'allowlist':
        out = Path(sys.argv[3]); assert not os.path.lexists(out)
        out.write_text(''.join(f+'\n' for f in sorted(pin_files(sys.argv[2]))))
        result = dict(allowlist=str(out), files=len(pin_files(sys.argv[2])))
    elif cmd == 'shadowscan':
        result = shadowscan(sys.argv[2], sys.argv[3])
    elif cmd == 'need':
        base = Path(sys.argv[2]); assert os.path.realpath(base) == str(base)
        total = sum(os.lstat(base/'repo'/f).st_size for f in pin_files(sys.argv[3]))
        for root, dirs, files in os.walk(base/'native', followlinks=False):
            total += sum(os.lstat(os.path.join(root, f)).st_size for f in files)
        total += sum(os.lstat(base/'inputs'/n).st_size for n in INPUTS)
        result = dict(need_bytes=total, need_GiB=-(-total//2**30))
    elif cmd == 'nolinks':
        result = dict(nolinks=sys.argv[2], entries=nolinks(sys.argv[2]))
    elif cmd == 'install':
        result = install(*sys.argv[2:6])
    else:
        raise SystemExit(f'unknown command {cmd}')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
