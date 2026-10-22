"""Drain an old static evaluator between attempts, then share its unchanged cases.

Run under the frozen R2 run.sh and the usual host guard. Never edits the evaluator,
manifest, checkpoint, bank or sealed rows. An interrupted attempt remains a failure.
"""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import sys
import time
import traceback
from types import SimpleNamespace


def read(p):
    return json.loads(Path(p).read_text())


def save(p, value):
    p = Path(p)
    q = p.with_name(p.name + f'.{os.getpid()}.tmp')
    q.write_text(json.dumps(value, indent=1) + '\n')
    q.replace(p)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def proc(pid):
    try:
        fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
        return dict(pid=pid, state=fields[0], ppid=int(fields[1]), start=fields[19],
                    argv=Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0')[:-1])
    except FileNotFoundError:
        return None


def same_process(identity):
    now = proc(identity['pid'])
    return now if now and now['start'] == identity['start'] else None


def identity(pid, code, out, parent=None):
    d = proc(pid)
    assert d and str(code).encode() in d['argv'] and str(out).encode() in d['argv'], 'wrong process'
    if parent is not None:
        assert d['ppid'] == parent, 'wrong parent'
    return {k: d[k] for k in ('pid', 'start')}


def send(ident, sig):
    if same_process(ident):
        os.kill(ident['pid'], sig)


def wait_stopped(ident):
    for _ in range(1000):
        d = same_process(ident)
        if not d or d['state'] in ('T', 't', 'Z'):
            return d
        time.sleep(.001)
    raise RuntimeError('process did not stop')


def active_attempts(out, pid):
    active = []
    for p in (out/'rows').glob('*.attempt'):
        try:
            owner_pid = read(p).get('pid')
        except FileNotFoundError:
            # Other running workers may seal/unlink while this worker is stopped.
            continue
        if owner_pid == pid:
            active.append(p)
    return active


def drain(code, out, parent, receipt, timeout=1800):
    """Stop each worker, inspect after it stops, retire only outside an attempt.

    Keep the legacy parent stopped until the replacement seals every assigned row.
    On recovery, process start times prevent signalling a reused PID.
    """
    if receipt.exists():
        state = read(receipt)
        assert state['code'] == str(code) and state['out'] == str(out)
        assert state['parent']['pid'] == parent
    else:
        p = identity(parent, code, out)
        children = [int(x) for x in Path(f'/proc/{parent}/task/{parent}/children').read_text().split()]
        assert children, 'legacy evaluator has no workers'
        state = dict(code=str(code), out=str(out), parent=p,
                     children=[identity(x, code, out, parent) for x in children], retired=[], created=time.time())
        save(receipt, state)
    assert same_process(state['parent']), 'legacy parent disappeared; manual recovery required'
    send(state['parent'], signal.SIGSTOP)
    wait_stopped(state['parent'])
    deadline = time.monotonic() + timeout
    try:
        while len(state['retired']) < len(state['children']):
            for child in state['children']:
                if child['pid'] in state['retired']:
                    continue
                current = same_process(child)
                if not current or current['state'] == 'Z':
                    # A genuine crash leaves its marker for the original no-retry accounting.
                    state['retired'].append(child['pid']); save(receipt, state)
                    continue
                send(child, signal.SIGSTOP)
                current = wait_stopped(child)
                if current and active_attempts(out, child['pid']):
                    send(child, signal.SIGCONT)
                    continue
                # No marker after SIGSTOP means no game can have started unsealed.
                send(child, signal.SIGTERM)
                send(child, signal.SIGCONT)
                for _ in range(1000):
                    current = same_process(child)
                    if not current or current['state'] == 'Z':
                        break
                    time.sleep(.001)
                else:
                    raise RuntimeError('idle worker did not terminate')
                state['retired'].append(child['pid']); save(receipt, state)
            if time.monotonic() > deadline:
                raise TimeoutError('drain timed out; parent remains stopped for recovery')
            time.sleep(.01)
    finally:
        # Never leave an unfinished game suspended if this owner encounters an error.
        for child in state['children']:
            if child['pid'] not in state['retired']:
                send(child, signal.SIGCONT)
    state['drained'] = time.time(); save(receipt, state)
    return state


def claimed_cases(cases, out, arm):
    """The lock stays held across the generator yield and the complete game/seal.

    A crashed worker releases its kernel lock. Its .attempt is then consumed by the
    unchanged evaluator as an infrastructure failure, never retried as a game.
    """
    claims = out/'expansion-claims'
    claims.mkdir(exist_ok=True)
    for case in cases:
        with (claims/f"{case['index']:04}.lock").open('a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                continue
            try:
                yield case
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)


def validate(code, out, expected_arm=None):
    man = read(out/'manifest.json')
    assert man['paired_only'] and man['arm'] in ('pv1-S100', 'pv1-M')
    assert expected_arm is None or man['arm'] == expected_arm, 'unexpected arm'
    assert sha(man['ckpt']) == man['ckpt_sha256']
    assert sha(man['bank_path']) == man['bank_sha256']
    actual = {p.name: sha(p) for p in sorted(code.parent.glob('*.py'))}
    assert actual == man['code_sha256'], 'frozen evaluator package changed'
    bank = read(man['bank_path'])
    by_index = {c['index']: c for c in bank['cases']}
    assert len(by_index) == len(bank['cases'])
    cases = [by_index[i] for i in man['assigned']]
    assert len(set(man['assigned'])) == len(cases)
    return man, cases


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--code', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--legacy-parent', type=int, required=True)
    ap.add_argument('--workers', type=int, default=64)
    ap.add_argument('--expected-arm', choices=('pv1-S100', 'pv1-M'))
    a = ap.parse_args()
    assert os.uname().nodename.split('.')[0] == '127x05'
    assert 1 <= a.workers <= 72
    out, code = a.out.resolve(), a.code.resolve()
    owner = (out/'expansion-owner.lock').open('a')
    fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
    man, cases = validate(code, out, a.expected_arm)
    spec = importlib.util.spec_from_file_location('frozen_eval', code)
    E = importlib.util.module_from_spec(spec); spec.loader.exec_module(E)
    assert 'bot' not in sys.modules
    assert not (out/'expansion-pool-intent.json').exists(), 'previous replacement pool needs explicit recovery'
    state = drain(code, out, a.legacy_parent, out/'expansion-drain.json')
    # Retired workers free their entire RSS before the larger pool is admitted.
    while E.mem_available() < (28 + 1.1*a.workers)*E.GiB or os.getloadavg()[0] + a.workers > 90:
        print('EXPANSION_ADMISSION_HOLD', flush=True); time.sleep(10)
    save(out/'expansion-owner.json', dict(pid=os.getpid(), workers=a.workers, started=time.time(),
                                       source=sha(__file__), manifest=sha(out/'manifest.json')))
    intent = out/'expansion-pool-intent.json'
    with intent.open('x') as f:
        json.dump(dict(pid=os.getpid(), started=time.time(), workers=a.workers), f)
    children = []
    for w in range(a.workers):
        pid = os.fork()
        if pid == 0:
            # Do not keep the owner lock inherited if the parent crashes.
            owner.close()
            try:
                args = SimpleNamespace(out=str(out), arm=man['arm'], ckpt=man['ckpt'])
                # Rotate traversal, then rely on per-case exclusive kernel locks.
                order = cases[w::a.workers] + [c for i,c in enumerate(cases) if i % a.workers != w]
                E.worker(0, 1, args, claimed_cases(order, out, man['arm']))
            except BaseException:
                traceback.print_exc(); os._exit(1)
            os._exit(0)
        children.append(pid)
    statuses = [os.waitpid(p, 0)[1] for p in children]
    assert all(s == 0 for s in statuses), 'replacement worker failed; parent remains stopped'
    # Apply the original retained-row/provenance checks without starting another game.
    for case in cases:
        r = read(out/'rows'/f"{case['index']:04}-{man['arm']}.json")
        assert r.get('ckpt_sha256') == man['ckpt_sha256'] and r.get('bank_sha256') == man['bank_sha256']
        assert E.same_case(r, case) and r.get('runtime_pins') == man['runtime_pins']
        if not r.get('error') and not r.get('invalid'):
            assert E.origins_valid(r.get('module_origins_after'))[0]
    assert not list((out/'rows').glob('*.attempt')), 'unsealed attempts remain'
    validate(code, out, a.expected_arm)
    save(out/'expansion-complete.json', dict(finished=time.time(), workers=a.workers, rows=len(cases)))
    send(state['parent'], signal.SIGCONT)


if __name__ == '__main__':
    main()
