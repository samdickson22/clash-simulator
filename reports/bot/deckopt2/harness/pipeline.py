"""Light coordinator for the approved sequential screens and fresh validation.

Uses existing frozen game pools; never changes a bank or reruns an outcome.
Any unclean row stops progression. STOP-PIPELINE pauses orchestration only.
"""
import json
import os
from pathlib import Path
import shlex
import subprocess
import time

from bot.deckopt2.run import dump, sha, utc
from clean import read_rows

ROOT = Path('/mpac/sdicks02/jobs/clasher/bot-deckopt2')
REPO = '/mpac/sdicks02/repos/clasher-bot-deckopt2'
PY = '/mpac/sdicks02/repos/clasher-bot/.venv/bin/python'
HOSTS = ('127x01', '127x03', '127x04')
VARIANT = '190e15df6ecea88da441ef29f2c45da56316558a5174516054997191dc5de968'
POOLS = (('127x04', 'h04', 40), ('127x03', 'h03a', 4),
         ('127x03', 'h03b', 4), ('127x01', 'h01', 4))
FILES = ('budget.py', 'instrument.py', 'execute.py', 'extend.py', 'pool.py',
         'clean.py', 'routes.py', 'run-pool.sh', 'projected_fast.py', 'projected_entry.py', 'variant-A-copies-only.json',
         'variant-B-full-budget.json', 'collection-final.json',
         'collection-B-musketeer-wild.json', 'inventory-B-musketeer-approved.json',
         'upgrade-source-gamedata.json', 'manifest.json')


def command(argv):
    result = subprocess.run(list(map(str, argv)), stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True)
    if result.returncode:
        raise RuntimeError((argv, result.returncode, result.stdout[-10000:]))
    return result.stdout


def remote(host, argv):
    return command(['ssh', host, shlex.join(list(map(str, argv)))])


def sync_rows():
    for relative in ('screen', 'new-cards/screen', 'final-validation/validation'):
        dest = ROOT / relative
        if not (dest / 'bank.json').exists():
            continue
        (dest / 'rows').mkdir(exist_ok=True)
        for host in HOSTS:
            # Some hosts have no results in a newly registered stage yet.
            result = subprocess.run(['rsync', '-a', '--ignore-missing-args',
                                     f'{host}:{dest}/rows/', str(dest / 'rows') + '/'],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if result.returncode not in (0, 23):
                raise RuntimeError(('rsync', host, relative, result.stderr))


def complete(root, stage):
    data, rows = read_rows(root, stage)
    expected = len(data['cases']) * len(data['candidates']) * len(data['players'])
    return len(rows) == expected


def prep(command_name):
    assert sha(ROOT / 'variant-B-full-budget.json') == VARIANT
    host = '127x03'
    command(['rsync', '-a', *[ROOT / f for f in FILES], f'{host}:{ROOT}/'])
    command(['rsync', '-a', str(ROOT / 'screen') + '/', f'{host}:{ROOT}/screen/'])
    if command_name == 'select':
        command(['rsync', '-a', str(ROOT / 'new-cards') + '/', f'{host}:{ROOT}/new-cards/'])
    shell = ('source ' + shlex.quote(str(ROOT / 'env.sh')) + '; export PYTHONPATH=' +
             shlex.quote(REPO) + '; exec /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 2 '
             'nice -n 15 ' + shlex.join([PY, str(ROOT / 'extend.py'), command_name]))
    result = remote(host, ['bash', '-c', shell])
    print(result, flush=True)
    subdir = 'new-cards' if command_name == 'new-screen' else 'final-validation'
    command(['rsync', '-a', f'{host}:{ROOT}/{subdir}/', str(ROOT / subdir) + '/'])
    if command_name == 'select':
        command(['rsync', '-a', f'{host}:{ROOT}/selection.json', str(ROOT) + '/'])
    with (ROOT / 'PROGRESS.md').open('a') as f:
        f.write(f'\n{utc()} automatic approved progression: {command_name}; {result.strip()}. '
                'Prior stage complete and clean; bank drawn before any next-stage game.\n')


def launch(relative, stage):
    root = ROOT / relative
    route = root / stage / 'routes-auto-v1.json'
    if not route.exists():
        command([PY, ROOT / 'routes.py', '--root', root, '--stage', stage,
                 '--out', route, '--weights', 'h04:40,h03a:6,h03b:6,h01:2'])
    for host in HOSTS:
        command(['rsync', '-a', *[ROOT / f for f in FILES], f'{host}:{ROOT}/'])
        command(['rsync', '-a', str(root) + '/', f'{host}:{root}/'])
        if stage == 'validation':
            command(['rsync', '-a', str(ROOT / 'projected-parity') + '/', f'{host}:{ROOT}/projected-parity/'])
    for host, label, workers in POOLS:
        receipt = root / f'{stage}-{label}-auto-v1.pid.json'
        # Presence records an attempted launch; failures require investigation,
        # never automatic duplicate launches or silent selective retries.
        if receipt.exists():
            continue
        output = remote(host, [f'{REPO}/bot/detach.sh',
                               root / f'{stage}-{label}-auto-v1.log', receipt,
                               'bash', ROOT / 'run-pool.sh', root, stage, route, label, workers])
        command(['rsync', '-a', f'{host}:{receipt}', str(receipt)])
        print(host, label, output.strip(), flush=True)
    with (ROOT / 'PROGRESS.md').open('a') as f:
        f.write(f'\n{utc()} {relative}/{stage} auto-v1 launched via separate detach sessions, '
                'fixed shared admission, 52 total workers, at most40perhost (04:40,03:4+4,01:4). '
                f'Route SHA{sha(route)}; bank SHA{sha(root / stage / "bank.json")}.\n')


def main():
    dump(ROOT / 'pipeline-process.json', dict(pid=os.getpid(), started_utc=utc(),
                                            source_sha256=sha(__file__), variant_sha256=VARIANT))
    while not (ROOT / 'STOP-PIPELINE').exists():
        sync_rows()
        current = 'reference screen'
        if complete(ROOT, 'screen'):
            if not (ROOT / 'new-cards/screen/bank.json').exists():
                prep('new-screen')
            launch_if_needed(ROOT / 'new-cards', 'screen', 'new-cards')
            current = 'budget screen'
            if complete(ROOT / 'new-cards', 'screen'):
                if not (ROOT / 'final-validation/validation/bank.json').exists():
                    prep('select')
                # Capacity is currently saturated on all authorized hosts.
                # Give the true-deck variant the released screening allocation;
                # its result governs the incoming full-pool live bundle.
                full = ROOT / 'fullpool'
                full_done = (full / 'VALIDATION-READY.json').exists()
                full_failed = (full / 'STOP').exists() or (full / 'pipeline-error.json').exists()
                parity_ready = (ROOT / 'final-validation/implementation.json').exists()
                if not parity_ready:
                    current = 'waiting for projected LD/fc-c4 parity receipt'
                elif not full_done:
                    current = 'true-deck validation first; projected validation bank registered'
                else:
                    # Full-pool goes live00:00Z. Projected validation is optional,
                    # off the critical path, and requires a fresh idle-CPU audit.
                    dump(ROOT / 'PROJECTED-IDLE-ONLY.json', dict(utc=utc(),
                         state='not run; optional after true-deck completion and idle-capacity audit',
                         bank_sha256=sha(ROOT / 'final-validation/validation/bank.json')))
                    current = 'true-deck complete; projected optional idle-only, not admitted'
                    dump(ROOT / 'pipeline-status.json', dict(updated_utc=utc(), stage=current))
                    return
                if complete(ROOT / 'final-validation', 'validation'):
                    command([PY, ROOT / 'refresh.py'])
                    dump(ROOT / 'VALIDATION-READY.json', dict(utc=utc(),
                         bank_sha256=sha(ROOT / 'final-validation/validation/bank.json')))
                    print('VALIDATION READY FOR REVIEW', utc(), flush=True)
                    return
        dump(ROOT / 'pipeline-status.json', dict(updated_utc=utc(), stage=current,
                                                variant_sha256=VARIANT))
        time.sleep(60)


def launch_if_needed(root, stage, relative):
    if all((root / f'{stage}-{label}-auto-v1.pid.json').exists() for _, label, _ in POOLS):
        return
    launch(relative, stage)


if __name__ == '__main__':
    try:
        main()
    except BaseException as error:
        dump(ROOT / 'pipeline-error.json', dict(utc=utc(), error=repr(error)))
        raise
