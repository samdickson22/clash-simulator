"""Finish the approved01/04 drain, then resume only their missing indices on04."""
import json
from pathlib import Path
import time
from pipeline import ROOT, REPO, command, remote
from bot.deckopt2.run import dump, sha, utc

OLD = (('127x01', 'h01', 2306479), ('127x04', 'h04', 3791184))


def main():
    receipt = ROOT / 'screen-h04-r2.pid.json'
    assert not receipt.exists(), 'existing launch; investigate rather than duplicate'
    while True:
        done = True
        receipts = []
        for host, label, pid in OLD:
            path = ROOT / 'screen' / f'pool-{label}-{pid}.json'
            data = json.loads(remote(host, ['cat', path]))
            assert data['pid'] == pid and data['label'] == label
            assert not data.get('errors'), data
            done = done and bool(data.get('finished_utc'))
            receipts.append(data)
        dump(ROOT / 'drain-r2-status.json', dict(updated_utc=utc(), done=done, pools=receipts))
        if done:
            break
        time.sleep(30)
    for host, _, _ in OLD:
        command(['rsync', '-a', f'{host}:{ROOT}/screen/rows/', str(ROOT / 'screen/rows') + '/'])
    old = json.loads((ROOT / 'screen/routes-r1.json').read_text())
    ownership = set(old['routes']['h01']) | set(old['routes']['h04'])
    others = set(old['routes']['h03a']) | set(old['routes']['h03b'])
    assert not ownership & others
    pending = [i for i in sorted(ownership) if not (ROOT / 'screen/rows' / f'{i:06d}.json').exists()]
    assert old['bank_sha256'] == sha(ROOT / 'screen/bank.json')
    route = ROOT / 'screen/routes-h04-r2.json'
    dump(route, dict(created_utc=utc(), bank_sha256=old['bank_sha256'],
                     routes={'h04-r2': pending}, workers=40,
                     previous_route_sha256=sha(ROOT / 'screen/routes-r1.json'),
                     method='only missing indices previously owned by fully drained h01+h04; other03routes untouched',
                     drain_receipts=receipts), exclusive=True)
    if not pending:
        print('No pending cases in drained routes', utc(), flush=True)
        return
    command(['rsync', '-a', route, f'127x04:{route}'])
    print(remote('127x04', [f'{REPO}/bot/detach.sh', ROOT / 'screen-h04-r2.log', receipt,
                           'bash', ROOT / 'run-pool.sh', ROOT, 'screen', route, 'h04-r2', 40]), flush=True)
    command(['rsync', '-a', f'127x04:{receipt}', str(receipt)])
    with (ROOT / 'PROGRESS.md').open('a') as f:
        f.write(f'\n{utc()}01+04drain finished clean; both old receipts retain every in-flight result. '
                f'Resumed{len(pending)}pending original indices on04h04-r2,40workers/42CPUlease. '
                f'Bank unchanged; routeSHA{sha(route)}.03controllers untouched.\n')


if __name__ == '__main__':
    try:
        main()
    except BaseException as error:
        dump(ROOT / 'drain-r2-error.json', dict(utc=utc(), error=repr(error)))
        raise
