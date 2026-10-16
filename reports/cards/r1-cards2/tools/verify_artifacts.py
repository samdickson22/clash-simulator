"""Read-only receipt/overlay verification for the two final scratch roots."""
import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--build-receipt', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    expected = json.loads(a.build_receipt.read_text())
    runtime = Path('/mpac/sdicks02/jobs/clasher/cards/runtime')
    cards, live = runtime/'r1-cards2-dev', runtime/'live16402b-dev'
    c = json.loads((cards/'CARDS-RUNTIME-RECEIPT.json').read_text())
    l = json.loads((live/'LIVE16402-RECEIPT.json').read_text())
    assert c['source_commit'] == expected['engine_commit']
    assert sha(cards/'CARDS-RUNTIME-RECEIPT.json') == expected['receipt_sha256']['CARDS-RUNTIME-RECEIPT.json']
    assert sha(live/'LIVE16402-RECEIPT.json') == expected['receipt_sha256']['LIVE16402-RECEIPT.json']
    assert l['base_receipt_sha256'] == sha(cards/'CARDS-RUNTIME-RECEIPT.json')
    for f in c['files']:
        assert sha(Path(c['source_tree'])/f['source']) == f['sha256'], f['source']
        assert sha(cards/f['path']) == f['sha256'], f['path']
        if f['path'] != 'gamedata.json':
            assert sha(live/f['path']) == f['sha256'], f['path']
    for root in (cards, live):
        assert sha(root/'native/clasher_core.abi3.so') == expected['native_sha256']
    assert sha(cards/'gamedata.json') == expected['base_gamedata_sha256']
    assert sha(live/'gamedata.json') == expected['overlay_gamedata_sha256']
    for value in l['inputs'].values():
        assert sha(value['path']) == value['sha256'], value['path']
    repo = Path(__file__).resolve().parents[4]
    for rel, digest in expected['code_sha256'].items():
        assert sha(repo/rel) == digest, rel
    result = dict(status='PASS', engine_commit=c['source_commit'], native_sha256=expected['native_sha256'],
                  card_overlay_files_verified=len(c['files']),
                  live_overlay_source_files_verified=sum(f['path']!='gamedata.json' for f in c['files']),
                  overlay_inputs_verified=len(l['inputs']), code_files_verified=len(expected['code_sha256']),
                  base_gamedata_sha256=sha(cards/'gamedata.json'), live_gamedata_sha256=sha(live/'gamedata.json'),
                  receipt_sha256=expected['receipt_sha256'])
    a.out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=1))


if __name__ == '__main__':
    main()
