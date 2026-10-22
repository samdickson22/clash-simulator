"""Wait for CODE93's next-bank evaluator, then expand only its existing work on 05.

No training, selection, bank construction, remote access, or automatic crash recovery.
Missing atomic publications wait. Present invalid evidence and uncertain intents stop.
"""
import argparse
from contextlib import contextmanager
import fcntl
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import time

HERE = Path(__file__).resolve()
CODE = HERE.parents[4]
ROOT = Path('/mpac/sdicks02/scratch/pretrain-v1-dev/followup-20261022')
SNAPSHOT = Path('/mpac/sdicks02/datasets/pretrain-v1/snapshot-20261022-b083')
STORE = 'f-ce6e509ee43a-b-1005dbb4'
MANIFEST_SHA = 'f52562891584db3dffef6c45ced1106a41b712456e67a1cd87ccc084b23dc59a'
BANK_SHA = '10c24cd429416344d6ee69342bc6317a2c90387bb73a97eb38c9dbf4cf30a276'
R2 = Path('/mpac/sdicks02/scratch/rl-search-prior-20261020-r2')
GPU_OUT = Path('/mpac/sdicks02/jobs/clasher/pretrain-v1/followup-20261022')
PYTHON = '/mpac/sdicks02/repos/clasher-bot/.venv/bin/python'
spec = importlib.util.spec_from_file_location('expansion', HERE.with_name('expand_eval_05.py'))
X = importlib.util.module_from_spec(spec)
spec.loader.exec_module(X)


def require(ok, why):
    if not ok:
        raise RuntimeError(why)


def published(path):
    """Catch only absent publication, including rename between the probe and read."""
    try:
        return X.read(path)
    except FileNotFoundError:
        return None


def sync_dir(path):
    fd = os.open(path, os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def exclusive(path, data):
    # Torn or uncertain intents must block restart, even if no child receipt exists.
    with path.open('x') as f:
        json.dump(data, f, sort_keys=True)
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())
    sync_dir(path.parent)


@contextmanager
def locked(path):
    with path.open('a') as f:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield f


def boot_id():
    return Path('/proc/sys/kernel/random/boot_id').read_text().strip()


def process_identity(pid):
    p = X.proc(pid)
    require(p is not None, 'process vanished before receipt')
    return dict(pid=pid, start=p['start'], boot_id=boot_id(),
                argv=[a.decode() for a in p['argv']])


def alive(ident):
    if ident['boot_id'] != boot_id():
        return None
    p = X.same_process(ident)
    return p if p and p['state'] != 'Z' else None


def processes():
    return [p for d in Path('/proc').iterdir() if d.name.isdigit()
            for p in [X.proc(int(d.name))] if p and p['state'] != 'Z']


def children(pid):
    try:
        return [int(x) for x in Path(f'/proc/{pid}/task/{pid}/children').read_text().split()]
    except FileNotFoundError:
        return []


def package_hashes(code):
    return {p.name: X.sha(p) for p in sorted((code/'bot/pretrain_v1').glob('*.py'))}


def verify_source(original):
    code = Path(original['code'])
    head = subprocess.check_output(['git', '-C', str(code), 'rev-parse', 'HEAD'], text=True).strip()
    require(head == original['revision'], 'original revision changed')
    for name, digest in original['files'].items():
        require(X.sha(code/name) == digest, 'original source changed: '+name)
    expected = {Path(n).name: h for n, h in original['files'].items()
                if n.startswith('bot/pretrain_v1/') and n.endswith('.py')}
    require(package_hashes(code) == expected, 'original evaluator package inventory changed')
    return code, expected


def verify_original_owner(original):
    require(boot_id() == original['boot_id'], 'original boot changed; manual recovery required')
    for key in ('owner', 'guard'):
        require(X.same_process(original[key]), key+' identity changed; manual recovery required')
    owner = X.proc(original['owner']['pid'])
    script = str(Path(original['code'])/'reports/bot/pretrain-v1/sweep/followup_05.py').encode()
    require(owner['argv'] == [PYTHON.encode(), b'-B', b'-u', script], 'original owner argv changed')
    require(owner['ppid'] == original['guard']['pid'], 'original owner guard changed')
    guard = X.proc(original['guard']['pid'])
    require(guard['argv'] == [b'bash', str(Path(original['code'])/'bot/pretrain_v1/run_guarded.sh').encode(),
            str(ROOT/'games-owner.log').encode(), b'--'] + owner['argv'], 'original guard argv changed')
    return process_identity(owner['pid'])


def verify_review(revision):
    head = subprocess.check_output(['git', '-C', str(CODE), 'rev-parse', 'HEAD'], text=True).strip()
    require(len(revision) == 40 and head == revision, 'not the reviewed revision')
    require(not subprocess.check_output(['git', '-C', str(CODE), 'status', '--porcelain'], text=True),
            'reviewed worktree must be clean')
    return {p.name: X.sha(p) for p in (HERE, HERE.with_name('expand_eval_05.py'),
                                      HERE.with_name('next_eval_original.json'))}


def finite_number(value):
    return type(value) in (int, float) and math.isfinite(value)


def registered_config(size):
    d, layers, heads, ffn, drop = (192, 4, 6, 576, 0.0) if size == 'S100' else (320, 6, 8, 1280, 0.1)
    return dict(d=d, layers=layers, heads=heads, ffn=ffn, drop=drop, n_cards=124, n_bodies=183)


def validate_run(size, phase, selected, run, summary, snapshot, rows):
    run_out = GPU_OUT/phase
    require(type(selected['ep']) is int and 0 <= selected['ep'] < 8, 'invalid selection epoch')
    require(selected['selected'] == str(run_out/f"ep{selected['ep']:02d}.pt"),
            'selected checkpoint is outside the exact registered run/epoch')
    require(run['args']['out'] == str(run_out), 'run output is outside the registered directory')
    require(run['rows'] == rows and run['store'] == str(snapshot/STORE)
            and run['args']['store'] == run['store'], 'next run is from another snapshot')
    require(run['cfg'] == registered_config(size), 'run architecture mismatch')
    expected = dict(store=str(snapshot/STORE), out=str(run_out), device='cuda', threads=3,
                    max_gpu_hours=64, dev_cap=400000, hog_share=0.5, max_row_exposure=5.0, drop_ages=0.05,
                    train_frac=1.0, seed=2026102001, bs=512, patience=2, epochs=8, eval_every=1,
                    warmup_steps=0, steps_per_epoch=0, lr=3e-4 if size == 'S100' else 2e-4,
                    wd=1e-4 if size == 'S100' else 0.01, amp='none' if size == 'S100' else 'bf16')
    expected.update({k: v for k, v in registered_config(size).items() if k not in ('n_cards', 'n_bodies')})
    require(run['args'] == expected and all(not isinstance(v, bool) for v in run['args'].values()),
            'registered run configuration mismatch')
    original_files = X.read(HERE.with_name('next_eval_original.json'))['files']
    training_code = {n: original_files['bot/pretrain_v1/'+n] for n in ('train_bc.py', 'model.py', 'featurize.py')}
    require(run['schema'] == 'clasher.pretrain_v1.bc-run.v1' and run['code_sha256'] == training_code
            and run['feature_hash'] == 'ce6e509ee43a2a4a8c484261b5341b9a3f1b0c71a1a77a2024de89a80fa4773d',
            'training source/feature provenance mismatch')
    require(run['seed'] == selected['seed'] == 2026102001 and selected['selection']['seed'] == selected['seed']
            and selected['selection']['ckpt'] == selected['selected']
            and selected['selection']['ep'] == selected['ep'], 'selection/run provenance mismatch')
    require(type(summary['best_ep']) is int and 0 <= summary['best_ep'] < 8
            and finite_number(summary['wall_h']) and summary['wall_h'] > 0
            and finite_number(summary['gate_bias']), 'invalid completed summary')
    require(isinstance(summary['dev_cal'], dict) and all(
        finite_number(summary['dev_cal'].get(k)) and summary['dev_cal'][k] >= 0
        for k in ('dev_cal/all/joint_nll', 'dev_cal/all/ece', 'dev_cal/hog/joint_nll')),
        'invalid completed DEV summary')


def gates(root, snapshot):
    """All gates are read only. No partially present publication means ready."""
    ready = published(snapshot/'STORE-READY.json')
    scaling = published(root/'scaling-read.json')
    if ready is None or scaling is None:
        return None
    require((ready['batches'], ready['matches'], ready['rows']) == (83, 41328, 8143577),
            'snapshot counts changed')
    require(ready['store_name'] == STORE and ready['manifest_sha256'] == MANIFEST_SHA,
            'snapshot identity changed')
    require(X.sha(snapshot/STORE/'MANIFEST.jsonl') == MANIFEST_SHA, 'snapshot manifest changed')
    require(X.sha(snapshot/'input.json') == ready['input_sha256'], 'snapshot input changed')
    require(len(X.read(snapshot/'input.json')) == 83, 'snapshot input batch count changed')
    names = {'S25', 'S50', 'S100', 'M25', 'M50', 'M100'}
    require(set(scaling['runs']) == names, 'scaling run set changed')
    if not all(d['status'] == 'complete' for d in scaling['runs'].values()):
        return None
    bank = root/'next-snapshot-bank.json'
    require(X.sha(bank) == BANK_SHA, 'next bank changed')
    cases = X.read(bank)['cases']
    require(len(cases) == len({c['index'] for c in cases}) == 1600, 'next bank case count changed')
    selected = {}
    for size, phase in [('S100', 'next-S100'), ('M', 'next-M100')]:
        anchor = root/'next-anchors'/size
        d = published(anchor/'selection.json')
        # These are copies of the existing 08 publisher's completed run receipts.
        run = published(root/'next-run-receipts'/size/'run.json')
        summary = published(root/'next-run-receipts'/size/'summary.json')
        if d is None or run is None or summary is None:
            return None
        require(d['file'] == 'anchor.pt' and d['smoke'] is False and d['admitted'] is True
                and d['eligible'] > 0 and d['selection']['eligible'] is True,
                'next selection is not an admitted full-DEV anchor')
        require(X.sha(anchor/'anchor.pt') == d['sha256'], 'next checkpoint hash mismatch')
        validate_run(size, phase, d, run, summary, snapshot, ready['rows'])
        selected[size] = dict(checkpoint=str(anchor/'anchor.pt'), checkpoint_sha256=d['sha256'],
                              selection_sha256=X.sha(anchor/'selection.json'),
                              run_sha256=X.sha(root/'next-run-receipts'/size/'run.json'),
                              summary_sha256=X.sha(root/'next-run-receipts'/size/'summary.json'))
    return dict(bank_sha256=BANK_SHA, ready_sha256=X.sha(snapshot/'STORE-READY.json'), selected=selected)


def evaluator_argv(code, root, size):
    return [PYTHON, '-B', str(code/'bot/pretrain_v1/eval_rsim.py'),
            '--ckpt', str(root/'next-anchors'/size/'anchor.pt'),
            '--out', str(root/'next-snapshot'/f'eval-{size}'), '--arm', 'pv1-'+size,
            '--workers', '24', '--bank', str(root/'next-snapshot-bank.json'), '--paired-only']


def matching_parent(procs, argv, owner_pid):
    target = [a.encode() for a in argv]
    matches = [p for p in procs if p['argv'] == target and p['ppid'] == owner_pid]
    require(len(matches) <= 1, 'multiple matching legacy parents')
    if not matches:
        return None
    parent = matches[0]
    kids = [p for p in procs if p['ppid'] == parent['pid']]
    if len(kids) != 24:
        return None  # Original evaluator may still be in admission or finishing.
    require(all(p['argv'] == target for p in kids), 'unexpected evaluator child')
    require(set(children(parent['pid'])) == {p['pid'] for p in kids}, 'worker set changed; wait and inspect')
    return parent


def check_manifest(code, root, size, evidence, expected_code):
    out = root/'next-snapshot'/f'eval-{size}'
    path = out/'manifest.json'
    if published(path) is None:
        return None
    man, cases = X.validate(code/'bot/pretrain_v1/eval_rsim.py', out, 'pv1-'+size)
    sel = evidence['selected'][size]
    require(man['ckpt'] == sel['checkpoint'] and man['ckpt_sha256'] == sel['checkpoint_sha256'],
            'manifest checkpoint mismatch')
    require(man['bank_path'] == str(root/'next-snapshot-bank.json') and man['bank_sha256'] == BANK_SHA,
            'manifest bank mismatch')
    require(man['code_sha256'] == expected_code, 'manifest original source mismatch')
    require(man['assigned'] == [c['index'] for c in X.read(root/'next-snapshot-bank.json')['cases']]
            and len(cases) == 1600, 'assigned bank changed')
    return man, cases


def load_evaluator(code):
    spec = importlib.util.spec_from_file_location('original_eval', code/'bot/pretrain_v1/eval_rsim.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def rows_complete(out, man, cases, evaluator):
    complete = True
    for case in cases:
        row = published(out/'rows'/f"{case['index']:04}-{man['arm']}.json")
        if row is None:
            complete = False
            continue
        require(row.get('arm') == man['arm'] and row.get('ckpt_sha256') == man['ckpt_sha256']
                and row.get('bank_sha256') == man['bank_sha256'] and evaluator.same_case(row, case)
                and row.get('runtime_pins') == man['runtime_pins'], 'sealed row provenance mismatch')
        if not row.get('error') and not row.get('invalid'):
            require(evaluator.origins_valid(row.get('module_origins_after'))[0], 'sealed row module provenance')
    return complete and not list((out/'rows').glob('*.attempt'))


def phase_binding(size, evidence, manifest_path, sources, revision):
    return dict(size=size, evidence=evidence, manifest_sha256=X.sha(manifest_path),
                sources=sources, revision=revision)


def reuse_phase(state, size, binding, complete, procs):
    intent_path = state/f'{size}-intent.json'
    done_path = state/f'{size}-complete.json'
    intent, done = published(intent_path), published(done_path)
    if intent is None:
        require(done is None, 'completion without phase intent')
        return False
    require(intent['binding'] == binding, 'phase intent binding mismatch')
    # No inference from sealed rows alone after a controller launch. A crash after
    # completion but before this receipt also requires manual recovery.
    require(done is not None and done['binding'] == binding and complete,
            'uncertain phase intent; manual recovery required, no new controller')
    require(done['intent_sha256'] == X.sha(intent_path), 'phase intent changed')
    require(not alive(done['controller']), 'completed phase still has surviving controller')
    parent = alive(intent['parent'])
    require(not parent or parent['state'] not in ('T', 't'), 'legacy parent still stopped')
    target = [a.encode() for a in done['controller']['argv']]
    require(not any(p['argv'] == target for p in procs), 'surviving replacement pool; manual recovery required')
    return True


def python_script(argv):
    """Recognize the executed Python script, never a shell guard's later arguments."""
    args = [a.decode() for a in argv]
    if not args or not Path(args[0]).name.startswith('python'):
        return None
    i = 1
    while i < len(args) and args[i] in ('-B', '-u', '-s', '-E', '-I'):
        i += 1
    return Path(args[i]).name if i < len(args) and not args[i].startswith('-') else None


def no_pool(procs, root):
    for p in procs:
        script = python_script(p['argv'])
        if script == 'expand_eval_05.py':
            raise RuntimeError('live expansion controller/pool; wait for it to finish')
        if p['pid'] != os.getpid() and script == HERE.name:
            raise RuntimeError('another next-bank waiter exists')


def start_phase(state, size, binding, parent, command, logfile):
    intent = state/f'{size}-intent.json'
    exclusive(intent, dict(binding=binding, waiter=process_identity(os.getpid()),
                           parent=process_identity(parent['pid']), command=command, created=time.time()))
    # Durable intent precedes the only Popen. Inheritable lock descriptors are never passed.
    with logfile.open('a') as log:
        child = subprocess.Popen(command, cwd='/tmp', stdout=log, stderr=subprocess.STDOUT, close_fds=True)
        ident = process_identity(child.pid)
        exclusive(state/f'{size}-controller.json', ident)
        rc = child.wait()
    require(rc == 0, 'expansion failed; manual recovery required, legacy parent may be stopped')
    return ident


def run(revision):
    require(os.uname().nodename.split('.')[0] == '127x05', '05 CPU only')
    require(os.getpriority(os.PRIO_PROCESS, 0) >= 10, 'nice must be >=10')
    sources = verify_review(revision)
    original = X.read(HERE.with_name('next_eval_original.json'))
    code, expected_code = verify_source(original)
    state = ROOT/'next-expansion'
    state.mkdir(exist_ok=True)
    with locked(state/'waiter.lock'):
        for size in ('S100', 'M'):
            if (state/f'{size}-intent.json').exists():
                X.read(state/f'{size}-intent.json')
                require((state/f'{size}-complete.json').exists(),
                        'uncertain phase intent; manual recovery required, no new controller')
        no_pool(processes(), ROOT)
        exclusive(state/f'owner-{os.getpid()}-{time.time_ns()}.json',
                  dict(process=process_identity(os.getpid()), sources=sources, revision=revision,
                       original_owner=original['owner'], original_boot_id=original['boot_id']))
        evaluator = load_evaluator(code)
        for size in ('S100', 'M'):
            while True:
                verify_review(revision)
                verify_source(original)
                evidence = gates(ROOT, SNAPSHOT)
                if evidence is None:
                    print('WAIT ready/selection/run/scaling publication', flush=True)
                    time.sleep(30)
                    continue
                checked = check_manifest(code, ROOT, size, evidence, expected_code)
                if checked is None:
                    verify_original_owner(original)
                    print('WAIT original '+size+' manifest', flush=True)
                    time.sleep(10)
                    continue
                man, cases = checked
                require(evaluator.external_identity() == man['external_sha256'], 'frozen runtime changed')
                reference = X.read(evaluator.bank_path())['cases']
                require(evaluator.control_pins(reference) == man['runtime_pins'], 'control runtime pins changed')
                out = ROOT/'next-snapshot'/f'eval-{size}'
                binding = phase_binding(size, evidence, out/'manifest.json', sources, revision)
                complete = rows_complete(out, man, cases, evaluator)
                procs = processes()
                if reuse_phase(state, size, binding, complete, procs):
                    break
                # A completed unexpanded phase is reusable only with full integrity checks
                # and no expansion/drain artifacts, which could hide a surviving child.
                no_pool(procs, ROOT)
                if complete:
                    require(not any(out.glob('expansion-*.json')), 'unowned expansion artifacts')
                    print('VALIDATED original completed '+size, flush=True)
                    break
                verify_original_owner(original)
                parent = matching_parent(procs, evaluator_argv(code, ROOT, size), original['owner']['pid'])
                if parent is None:
                    print('WAIT original '+size+' live workers', flush=True)
                    time.sleep(5)
                    continue
                require(os.getpriority(os.PRIO_PROCESS, parent['pid']) >= 10, 'legacy nice changed')
                require(not any(out.glob('expansion-*.json')), 'unowned expansion artifacts')
                require(parent['state'] not in ('T', 't'), 'legacy parent unexpectedly stopped')
                command = [str(R2/'run.sh'), str(HERE.with_name('expand_eval_05.py')),
                           '--code', str(code/'bot/pretrain_v1/eval_rsim.py'), '--out', str(out),
                           '--legacy-parent', str(parent['pid']), '--workers', '64', '--expected-arm', 'pv1-'+size]
                ident = start_phase(state, size, binding, parent, command, state/f'{size}-controller.log')
                verify_review(revision)
                verify_source(original)
                require(gates(ROOT, SNAPSHOT) == evidence, 'phase input receipts changed during expansion')
                require(check_manifest(code, ROOT, size, evidence, expected_code) is not None,
                        'manifest disappeared after expansion')
                require(phase_binding(size, evidence, out/'manifest.json', sources, revision) == binding,
                        'phase manifest changed during expansion')
                require(evaluator.external_identity() == man['external_sha256'], 'runtime changed during expansion')
                reference = X.read(evaluator.bank_path())['cases']
                require(evaluator.control_pins(reference) == man['runtime_pins'],
                        'control runtime pins changed during expansion')
                require(rows_complete(out, man, cases, evaluator), 'expansion returned without validated rows')
                require(published(out/'expansion-complete.json') is not None, 'missing controller completion')
                live_parent = X.same_process(parent)
                require(not live_parent or live_parent['state'] not in ('T', 't'), 'legacy parent not resumed')
                exclusive(state/f'{size}-complete.json', dict(binding=binding, controller=ident,
                          intent_sha256=X.sha(state/f'{size}-intent.json'), finished=time.time()))
                break
        print('COMPLETE both next-bank phases validated; comparison remains CODE93-owned', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reviewed-revision', required=True)
    args = parser.parse_args()
    run(args.reviewed_revision)
