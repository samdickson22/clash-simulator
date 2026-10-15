"""Rewrite only the `truth` field of a VALIDATION dump (dump_records.py) from another label set, e.g. all-Ghost truth
(dense_labels.py --r2 --ghost-all), so dumps of different models are scored against a common truth.

  python live/perception/r2/retruth.py DUMP_IN DUMP_OUT LABELS_DIR
"""
import gzip, json, os, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import common as C  # noqa: E402
import dense_labels as D  # noqa: E402
from sample_records import truth_record  # noqa: E402


def main(src, dst, labels):
    guard = C.HeldoutGuard(); dst = Path(dst); dst.mkdir(parents=True, exist_ok=True)
    for f in sorted(Path(src).glob('*.jsonl.gz')):
        with gzip.open(f, 'rt') as fh:
            head = json.loads(fh.readline())
            if head.get('split') != 'validation':
                raise ValueError(f'{f}: not a validation dump')
            ep = head['episode']; guard.check([ep])
            if guard.split.get(ep) != 'validation':
                raise ValueError(f'{ep}: not a registered validation episode')
            lab = D.load(Path(labels)/f'{ep}.npz')
            ev_rows = [e for e in C.read_jsonl(C.MATCHES/ep/'events.jsonl') if e['accepted'] and e['kind'] != 'champion ability']
            out = dst/f.name; tmp = out.with_suffix('.tmp')
            with gzip.open(tmp, 'wt') as g:
                g.write(json.dumps(dict(head, truth_labels=str(labels)))+'\n')
                for line in fh:
                    r = json.loads(line)
                    r['truth'] = truth_record(lab, ev_rows, int(r['seq']), guard.cards, r['ts'])
                    g.write(json.dumps(r)+'\n')
            os.replace(tmp, out)
        print(ep, flush=True)


if __name__ == '__main__':
    main(*sys.argv[1:4])
