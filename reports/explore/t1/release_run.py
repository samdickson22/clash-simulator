"""Reviewed separately before use. Never invoke without explicit release authority.

Run the committed driver by absolute path, with cwd canonical R/reports/explore/t1.
The reducer and its imports always come from R, never the driver's checkout.
"""
import argparse
import contextlib
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import signal
import sys

CANONICAL = Path('/mpac/sdicks02/jobs/clasher/t1-20261010-r1/end-a5-release-r1/source')
BLOCK_ROOT = Path('/mpac/sdicks02/jobs/clasher/t1-20261010-r1/release-blocks-0108-r3')
PRIVATE = Path('/mpac/sdicks02/jobs/clasher/t1-20261010-r1/release-private')
PYTHON = '/mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python'
PRIVATE_COMMIT = '9bb349b1d4f467866f802a859c142c4adc7c0402'
PRIVATE_REF = 'refs/private/t1-registration-20261012'
BLIND_SHA = '866e6f7f7e41af4112602a643372d8424d951abb1c6952230d25d106a840d8fa'
SIDECAR_SHA = '16e1b34f7e376e42f3a18a7d9bb8b2ac09613d9f3555bfd2f97f8c7cad388f2e'
R5_SHA = '3b7d2295657be87c76a07dfc9d278e2f96b262d436b04504e4556352d23ba5f9'
COPY_SHA = 'd433dd54556a6040428e0a6791df67db441eb7637c03cae59db8ca8e5b25d3ef'
PINS = {'apt_budget.py': 'c15785357a95baf870b7959de23f7b6cfd84579b78c5722931b7687affbf8618', 'barrier.py': '346d3c053157ef2fea2f8aa5b629dbeb53a5c365036033cd37aea4af85a9b00b', 'check_reference.py': 'c848baa2f674801776543bbd9e0cd9c312c1de66fe017a5c8a583f79d5e64d43', 'common.py': '36e5eec3bf3cd4e285bc4d2c10631038cbe8cad54d2c25a2245336c251ee20c0', 'cpu_accounting.py': '5ecae99d9097c72cc1a6cbf0014c590470115f9a4ae7ff3a197ebb4c6a0dc06f', 'host_audit.py': '5717d01cc2a83adc19a4cf2846f9a95952f2ca73810b879807c5941cdddc0dd7', 'idle_services.py': '911c18aee5af1d61cf66b7e5187af4cb6b3fb58d3143152a3ab385b4a76816b2', 'owned_supervisor.py': 'fcd7aac922281e33ae315fcd91dd2ffd0cea7ca8bdf1d93716a09cd77e782249', 'parent_source_seed.py': '3cf10b3b679408b8f31cff575d11af57d40b7652a046f6bfcaced28f7bc6de1e', 'perception_confirmation.py': '6e2fb8d31f48b47cc76bc8fea98bd191fb7e7c51af4bada01dfbf37fc3365680', 'reduce.py': 'aebb2017d1ee646df72c22d0357c09856753e8fadcb63e6a361505b3543efe79', 'release_reference.py': 'f8b61c603a2680fe40c312019fcd92e6da377ed16decb57778aba40ef8f13555', 'schedule.py': '8478935e2649b2d4b3cf70dc699d9a38a538644fa7196270bdb72943356264be', 'ssh_budget.py': '0c2759f5f09728770bf339441151eb55a1f3cd17d5f04b46109f4e68f2cedd1d', 'ssh_sensitivity.py': 'bb124cc4716d1b902de936866bf28eec9a057128e3f04392f6234650d3a3a0e5', 'ssh_transport.py': '16a211a5fe68b35248d40c303bdd0dfa1e4e900542478edd7e9c51ea5994925f', 'system_bus.py': '785eb2c5fbf6bc35c7d4c5c614b97bf5796b4f516aa0aeeacecbd386b9a04e11', 'plan.json': 'af6aeade7de1a9c5e22fbf17a3cf1d6606652500ec9c35983d21a1cdb3767498'}
MAC_DIRECTORY = 'reports/explore/mac-e4-session/tiers-session-r1'
MAC_SUMMARY_PATH = MAC_DIRECTORY + '/sealed/tiers-summary.json'
MAC_A3P_PATH = MAC_DIRECTORY + '/a3p-poll-check.json'
MAC_MANIFEST_PATH = MAC_DIRECTORY + '/sealed/receipt-manifest.json'
DESCENDANT_ALLOWLIST = frozenset(
    MAC_DIRECTORY + '/' + name for name in (
        'sealed/tiers-summary.json', 'sealed/tiers-complete.json',
        'sealed/receipt-manifest.json', 'sealed/receipt-manifest.sha256',
        'sealed/tiers-identity.json', 'sealed/build-tiers.json',
        'sealed/pre-session-census.json', 'sealed/runtime-versions.json',
        'sealed/exactness-tiers.json', 'sealed/belief-exactness.json',
        'sealed/student-agreement.json', 'a3p-poll-check.json',
        'stage-nocopy-session-verify.json', 'preconditions.json',
        'session-receipt.json', 'private-commit-binding.json',
        'sealed/failure.json', 'sealed/cleanup-failure.json'))
FAILURE_PATHS = frozenset(MAC_DIRECTORY + '/sealed/' + name
                          for name in ('failure.json', 'cleanup-failure.json'))
SCRATCH = Path("/mpac/sdicks02/tmp")


def require(condition, label):
    if not condition:
        raise ValueError(label)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(part)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def without_utc(value):
    masked = {k: v for k, v in value.items() if k != 'utc'}
    return json.dumps(masked, sort_keys=True, separators=(',', ':'), allow_nan=False)


class TerminationSignal(BaseException):
    pass


def raise_on_signal(signum, frame):
    raise TerminationSignal(signum)


@contextlib.contextmanager
def terminating_signals():
    previous_mask = signal.pthread_sigmask(signal.SIG_BLOCK, set())
    previous = {s: signal.signal(s, raise_on_signal) for s in
                (signal.SIGTERM, signal.SIGHUP, signal.SIGINT)}
    try:
        yield
    finally:
        for s, handler in previous.items():
            signal.signal(s, handler)
        signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)


def block_failure_signals():
    signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM, signal.SIGHUP, signal.SIGINT})


@contextlib.contextmanager
def ownership_signals_blocked():
    old = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM, signal.SIGHUP, signal.SIGINT})
    try:
        yield
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, old)


def parent_audit(event, values):
    if event != 'open' or not isinstance(values[0], (str, bytes, os.PathLike)):
        return
    path = Path(os.fsdecode(values[0])).resolve()
    require('games' not in path.parts, 'parent game access refused')
    if path.is_relative_to(BLOCK_ROOT):
        rel = path.relative_to(BLOCK_ROOT)
        require(len(rel.parts) == 2 and rel.name in ('complete.json', 'interference.json'),
                'parent non-health access refused')


def postcheck(output, sidecar):
    emitted = output.with_name(output.name + '.ssh-sensitivity-ledger.json')
    require(without_utc(read(emitted)) == without_utc(sidecar), 'emitted health differs')
    digest = sha(emitted)
    result = read(output)
    for key in ('ssh_sensitivity', 'apt_sensitivity', 'ssh_or_apt_sensitivity'):
        require(result[key]['ledger_sha256'] == digest, 'sensitivity binding differs')
    return digest


def execute_guarded(root, ledger, sidecar, directory, health_fn, barrier_fn, reducer_fn, on_created=None):
    with terminating_signals():
        return _execute_guarded(root, ledger, sidecar, directory, health_fn, barrier_fn, reducer_fn, on_created)


def _execute_guarded(root, ledger, sidecar, directory, health_fn, barrier_fn, reducer_fn, on_created=None):
    """Callbacks permit offline synthetic tests; production supplies pinned R code."""
    stage = 'pre_guard'
    created = False
    try:
        for proof in root.glob('*/complete.json'):
            require(not proof.is_symlink(), 'symlink complete proof')
            interference = proof.parent / 'interference.json'
            require(not interference.is_symlink(), 'symlink interference proof')
        computed = health_fn(root, read(ledger)['events'], sha(ledger))
        require(without_utc(computed) == without_utc(sidecar), 'pre-outcome health differs')
        with ownership_signals_blocked():
            directory.mkdir(mode=0o700, exist_ok=False)
            created = True
            if on_created is not None:
                on_created()
        write(directory / 'pre-guard-ledger.json', computed)
        output = directory / 'reduce.json'
        stage = 'barrier'
        with (directory / 'barrier.stdout').open('x') as out, (directory / 'barrier.stderr').open('x') as err:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                barrier_fn()
        stage = 'reducer'
        with (directory / 'reducer.stdout').open('x') as out, (directory / 'reducer.stderr').open('x') as err:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = reducer_fn(output, out, err)
        require(code == 0, 'reducer exit')
        stage = 'post_check'
        emitted_sha = postcheck(output, sidecar)
        record = dict(passes=True, reducer_exit_code=code, output_sha256=sha(output),
                      pre_guard_ledger_sha256=sha(directory / 'pre-guard-ledger.json'),
                      emitted_ledger_sha256=emitted_sha, sidecar_sha256=SIDECAR_SHA)
        write(directory / 'checked-health.json', record)
        return record
    except BaseException as exc:
        # Exception messages or repr may contain result bytes. Publish type/stage only.
        block_failure_signals()
        if created:
            os.chmod(directory, 0o000)
        raise ReleaseFailure(stage, type(exc).__name__, created) from None


class ReleaseFailure(Exception):
    def __init__(self, stage, exception_type, locked):
        self.health = dict(passes=False, stage=stage, exception_type=exception_type,
                           outputs_locked=locked, no_result_reported=True)
        super().__init__('Release failed; health record only')


def run_reducer(argv, here, out, err):
    with subprocess.Popen(argv, cwd=here, stdout=out, stderr=err, start_new_session=True,
                          env={k: v for k, v in os.environ.items() if not k.startswith('PYTHON')}) as child:
        try:
            return child.wait()
        except BaseException:
            block_failure_signals()
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            child.wait()
            raise


def git(*args):
    return subprocess.check_output(['git', '--no-optional-locks', '-C', str(CANONICAL), *args], text=True).strip()


def bound_mac_json(binding, expected_path):
    require(binding['path'] == expected_path, 'Mac binding path differs')
    import re
    require(re.fullmatch('[0-9a-f]{40}', binding['commit']) is not None and
            re.fullmatch('[0-9a-f]{64}', binding['sha256']) is not None, 'Mac full binding required')
    subprocess.run(['git', '--no-optional-locks', '-C', str(CANONICAL),
                    'merge-base', '--is-ancestor', binding['commit'], 'HEAD'], check=True)
    raw = subprocess.check_output(['git', '--no-optional-locks', '-C', str(CANONICAL),
                                   'show', binding['commit'] + ':' + expected_path])
    path = CANONICAL / expected_path
    require(path.resolve() == path and hashlib.sha256(raw).hexdigest() == binding['sha256'] and
            path.read_bytes() == raw, 'Mac binding changed')
    return json.loads(raw)


class A3PRequiresRuling(ValueError):
    pass


def check_mac_a3p(release):
    summary = bound_mac_json(dict(path=release['mac_summary_path'], commit=release['commit'],
                                  sha256=release['mac_summary_sha256']), MAC_SUMMARY_PATH)
    a3p = bound_mac_json(release['a3p_poll_check'], MAC_A3P_PATH)
    seal = bound_mac_json(release['mac_receipt_manifest'], MAC_MANIFEST_PATH)
    require(a3p['receipt_manifest_sha256'] == release['mac_receipt_manifest']['sha256'], 'A3-P seal binding differs')
    require(seal['status'] == 'complete' and seal['files']['tiers-summary.json'] == release['mac_summary_sha256'], 'Mac summary seal differs')
    require(summary['dry_run'] is False and a3p['outcomes_read'] is False, 'Mac route scope')
    tiers = {'K0c', 'S', 'K2', 'K4'}
    require(set(summary['feasibility']) == set(a3p['tiers']) == tiers, 'A3-P tier coverage')
    for tier in sorted(tiers):
        frozen = summary['feasibility'][tier]['feasible']
        row = a3p['tiers'][tier]
        require(type(frozen) is bool and type(row['frozen_feasible']) is bool and
                type(row['feasible_after_a3p']) is bool and type(row['a3p_passes']) is bool, 'A3-P Boolean contract')
        require(row['frozen_feasible'] == frozen and
                row['feasible_after_a3p'] == (frozen and row['a3p_passes']), 'A3-P feasibility binding differs')
        if frozen and not row['feasible_after_a3p']:
            raise A3PRequiresRuling('A3-P requires coordinator ruling before outcome access')


def main():
    with terminating_signals():
        return _main()


def _main():
    audit = parent_audit
    sys.addaudithook(audit)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release', type=Path, required=True)
    parser.add_argument('--release-sha256', required=True)
    parser.add_argument('--r5', type=Path, required=True)
    parser.add_argument('--copy-receipt', type=Path, required=True)
    parser.add_argument('--private-name', required=True)
    args = parser.parse_args()
    os.umask(0o077)
    owns_output = False
    driver_sha = sha(Path(__file__))
    try:
        require(__debug__ and sys.version_info[:3] == (3, 12, 12), 'interpreter version')
        options = sys.orig_argv[1:sys.orig_argv.index(sys.argv[0])]
        require(sys.executable == PYTHON and sys.flags.dont_write_bytecode and '-B' in options and
                os.environ.get('PYTHONDONTWRITEBYTECODE') == '1', 'interpreter flags')
        require(importlib.metadata.version('numpy') == '2.2.6', 'numpy version')
        require(Path.cwd() == CANONICAL / 'reports/explore/t1', 'canonical cwd')
        require(git('status', '--porcelain', '--ignored') == '', 'canonical checkout dirty')
        head = git('rev-parse', 'HEAD')
        require(git('rev-parse', PRIVATE_REF) == PRIVATE_COMMIT, 'private ref changed')
        require(set(git('diff', '--no-renames', '--name-only', PRIVATE_COMMIT, 'HEAD').splitlines()) <= DESCENDANT_ALLOWLIST,
                'unapproved descendant diff')
        for commit in (PRIVATE_COMMIT, head):
            require(git('for-each-ref', '--contains', commit, 'refs/remotes') == '', 'private ancestry on remote ref')
        subprocess.run(['git', '-C', str(CANONICAL), 'merge-base', '--is-ancestor', PRIVATE_COMMIT, head], check=True)
        require(sha(args.release) == args.release_sha256, 'release receipt pin')
        require(sha(args.r5) == R5_SHA, 'sealed R5 pin')
        release = read(args.release)
        require(release['amendment_1_prerelease'] == read(args.r5)['amendment_1_prerelease'], 'R5 envelope')
        if release['reason'] == 'committed_mac_summary':
            require(not (set(git('diff', '--no-renames', '--name-only', PRIVATE_COMMIT, 'HEAD').splitlines()) & FAILURE_PATHS), 'Mac failure path requires ruling')
            check_mac_a3p(release)
        here = CANONICAL / 'reports/explore/t1'
        for name, digest in PINS.items():
            require(sha(here / name) == digest, 'reviewed code pin')
        ledger = here / 'receipts/blind-ledger-final-op7-r3.json'
        sidecar_path = here / 'receipts/PC4/ssh-sensitivity-pc4-landed.json'
        require(sha(ledger) == BLIND_SHA and sha(sidecar_path) == SIDECAR_SHA, 'blind/PC4 pin')
        require(BLOCK_ROOT.is_dir() and not BLOCK_ROOT.is_symlink(), 'C2 root')
        require(sha(args.copy_receipt) == COPY_SHA, 'C2 receipt pin')
        copy = read(args.copy_receipt)
        require(copy['destination'] == str(BLOCK_ROOT) and copy['exit_code'] == 0 and
                copy['complete_proofs'] == 3072 and copy['verified_game_files'] == 24576 and
                copy['verified_hub_ack'] == 1100 and copy['game_parse_or_summary'] is False and
                copy['complete_proof_set_sha256'] == 'd0f010695064c0b5d397ce8f24afede30a679a571a989daa4e058c1571c23fe0', 'C2 binding')
        require(Path(args.private_name).name == args.private_name and args.private_name not in ('.', '..'), 'private name')
        require(PRIVATE.is_dir() and not PRIVATE.is_symlink() and PRIVATE.stat().st_mode & 0o777 == 0o700, 'private parent')
        directory = PRIVATE / args.private_name
        sys.path.insert(0, str(here))
        from ssh_sensitivity import health_ledger
        from barrier import outcome_release
        from common import ROOT
        require(ROOT == CANONICAL, 'imported repository root')
        argv = [PYTHON, '-B', str(here / 'reduce.py'), '--root', str(BLOCK_ROOT),
                '--release', str(args.release), '--ledger', str(ledger), '--out', str(directory / 'reduce.json')]
        if release['reason'] == 'committed_mac_summary':
            argv += ['--mac-summary', str(CANONICAL / release['mac_summary_path'])]
        before = set(SCRATCH.glob('t1-release-recheck-*/check.json'))
        def barrier():
            outcome_release(CANONICAL, args.release)
        def reducer(output, out, err):
            return run_reducer(argv, here, out, err)
        def on_created():
            nonlocal owns_output
            owns_output = True
        record = execute_guarded(BLOCK_ROOT, ledger, read(sidecar_path), directory, health_ledger, barrier, reducer, on_created)
        fresh = set(SCRATCH.glob('t1-release-recheck-*/check.json')) - before
        require(len(fresh) == 2, 'parent/reducer barrier checks not both retained')
        record.update(driver_sha256=driver_sha, canonical_HEAD=head, sys_executable=sys.executable, version=sys.version,
                      driver_argv=sys.orig_argv, reducer_argv=argv, release_receipt_sha256=args.release_sha256,
                      barrier_exit_code=0, fresh_checks={str(p): sha(p) for p in sorted(fresh)},
                      root=str(BLOCK_ROOT), blind_ledger_sha256=BLIND_SHA, output_path=str(directory / 'reduce.json'))
        require(git('rev-parse', 'HEAD') == head and git('status', '--porcelain', '--ignored') == '', 'canonical state changed')
        write(directory / 'release-health-receipt.json', record)
        # Only the checked health receipt is visible; stdout/results remain private.
        print(json.dumps(record))
        return 0
    except BaseException as exc:
        block_failure_signals()
        if owns_output:
            os.chmod(directory, 0o000)
        health = exc.health if isinstance(exc, ReleaseFailure) else dict(passes=False, stage='preflight_or_record', exception_type=type(exc).__name__, no_result_reported=True)
        health.update(driver_sha256=driver_sha, outputs_locked=owns_output or health.get('outputs_locked', False))
        print(json.dumps(health))
        return 1


if __name__ == '__main__':
    sys.exit(main())
