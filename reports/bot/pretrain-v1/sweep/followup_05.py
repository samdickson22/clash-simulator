"""Independent owner of registered fresh-bank games and prompt scaling readouts on 05."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time

CODE = Path(__file__).resolve().parents[4]
ROOT = Path('/mpac/sdicks02/scratch/pretrain-v1-dev/followup-20261022')
SW = ROOT.parent/'sweep'
R2 = Path('/mpac/sdicks02/scratch/rl-search-prior-20261020-r2')
GPU = '/mpac/sdicks02/jobs/clasher/pretrain-v1'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def copy_selected(remote, local):
    if local.exists():
        d = json.loads((local/'selection.json').read_text())
        assert sha(local/d['file']) == d['sha256'] and not d['smoke']
        return d
    exists = subprocess.run(['timeout', '30', 'ssh', '-o', 'BatchMode=yes', '127x08',
                             'test', '-f', remote+'/selection.json'], capture_output=True)
    if exists.returncode:
        return None
    local.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=local.parent, prefix='.copy-') as td:
        incoming = Path(td)/'selected'
        subprocess.run(['timeout', '180', 'scp', '-rq', '127x08:'+remote, str(incoming)], check=True)
        d = json.loads((incoming/'selection.json').read_text())
        assert d['file'] in ['anchor.pt', 'PROVISIONAL-not-admitted.pt'] and not d['smoke']
        assert sha(incoming/d['file']) == d['sha256']
        incoming.rename(local)
    return d


def scaling_readout(stop):
    """Publish each available fraction promptly while the long game queue runs."""
    specs = [('S25', 'bc-sweep/select-S25', 'bc-sweep/S25'), ('S50', 'bc-sweep/select-S50', 'bc-sweep/S50'),
             ('S100', 'bc-sweep/select-S100', 'bc-v3/s1'), ('M100', 'bc-sweep/select-M', 'bc-sweep/M'),
             ('M50', 'followup-20261022/select-M50', 'followup-20261022/M50'),
             ('M25', 'followup-20261022/select-M25', 'followup-20261022/M25')]
    while not stop.is_set():
        try:
            report = {}
            for name, selected, run in specs:
                local = ROOT/'scaling'/name
                d = copy_selected(GPU+'/'+selected, local)
                if d is None:
                    report[name] = dict(status='pending'); continue
                r = local/'run.json'
                if not r.exists():
                    subprocess.run(['timeout', '30', 'scp', '-q', '127x08:'+GPU+'/'+run+'/run.json', str(r)], check=True)
                counts = json.loads(r.read_text())
                report[name] = dict(status='complete', checkpoint=d['sha256'], selected_epoch=d['ep'],
                                    sample_sizes={k: counts[k] for k in ['rows', 'train_rows', 'train_donors',
                                                  'dev_rows', 'dev_eval_rows', 'steps_per_epoch']}, metrics=d['selection'])
            tmp = ROOT/'scaling-read.tmp'
            tmp.write_text(json.dumps(dict(updated=time.time(), runs=report), indent=1)+'\n')
            tmp.replace(ROOT/'scaling-read.json')
            if all(d['status'] == 'complete' for d in report.values()):
                return
        except Exception as ex:
            with (ROOT/'scaling-read-errors.log').open('a') as f: f.write(f'{time.time()} {ex!r}\n')
        stop.wait(120)


def main():
    assert os.uname().nodename.split('.')[0] == '127x05'
    ROOT.mkdir(parents=True, exist_ok=True)
    lock = (ROOT/'games.lock').open('a'); fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    (ROOT/'games-owner.json').write_text(json.dumps(dict(pid=os.getpid(), code=str(CODE), started=time.time()))+'\n')
    stop = threading.Event()
    watcher = threading.Thread(target=scaling_readout, args=(stop,), daemon=True); watcher.start()

    def execute(args, logfile):
        with (ROOT/logfile).open('a') as f:
            subprocess.run([str(R2/'run.sh')]+args, cwd='/tmp', stdout=f, stderr=subprocess.STDOUT, check=True)

    for phase in ['power-v3', 'next-snapshot']:
        selected = {}
        for size in ['S100', 'M']:
            if phase == 'power-v3':
                local = SW/'anchors'/size
                d = json.loads((local/'selection.json').read_text())
                expected = {'S100': 'e9366c55503f3d826fa6add0beb9880883be9274158e728f03f932dcd19acbc7',
                            'M': 'caa5f58ff250fdd689734ad80eb426e654ab4828ff4b08e655df7265e8486f7e'}
                assert d['sha256'] == expected[size] and sha(local/d['file']) == expected[size]
            else:
                local = ROOT/'next-anchors'/size
                remote = GPU+'/followup-20261022/select-next-'+('M100' if size == 'M' else 'S100')
                while copy_selected(remote, local) is None: time.sleep(60)
                d = json.loads((local/'selection.json').read_text())
            selected[size] = (local/d['file'], ROOT/phase/f'eval-{size}')
        for size in ['S100', 'M']:
            checkpoint, out = selected[size]
            execute([str(CODE/'bot/pretrain_v1/eval_rsim.py'), '--ckpt', str(checkpoint), '--out', str(out),
                     '--arm', f'pv1-{size}', '--workers', '24', '--bank', str(ROOT/f'{phase}-bank.json'),
                     '--paired-only'], f'{phase}-{size}.log')
        execute([str(CODE/'bot/pretrain_v1/compare_arms.py'), '--a', str(selected['M'][1]),
                 '--b', str(selected['S100'][1]), '--out', str(ROOT/f'comparison-{phase}.json')],
                f'{phase}-comparison.log')
    watcher.join()  # Data readout remains owned until both M fractions are available.
    (ROOT/'games-complete.json').write_text(json.dumps(dict(finished=time.time()))+'\n')


if __name__ == '__main__':
    main()
