"""LAN-only train/dev staging with every column SHA verified; no fitting."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import time


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(4*1048576), b''):
            h.update(b)
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--work', required=True)
    p.add_argument('--store', required=True)
    p.add_argument('--source-host', default='127x04')
    p.add_argument('--source-store', default='/mpac/sdicks02/repos/clasher-t11-home-v1/data/v2-store-v1')
    p.add_argument('--reuse', action='store_true')
    a = p.parse_args(); work, store = Path(a.work), Path(a.store)
    before = time.monotonic(); store.mkdir(parents=True, exist_ok=True)
    def sync(names):
        listing = work/'store-files.txt'; listing.write_text('\n'.join(names)+'\n')
        subprocess.run(['rsync', '-rt', '--partial', '--bwlimit=153600', '--files-from='+str(listing),
                        '--rsync-path=nice -n 10 rsync',
                        a.source_host+':'+a.source_store+'/', str(store)+'/'], check=True)
    if not a.reuse:
        sync(['manifest.json', 'mask_table.npy', 'train/manifest.json', 'dev/manifest.json'])
    m = json.loads((store/'manifest.json').read_text())
    pins = json.loads((work/'source/imitation/gate-a-v2/executable-manifest.json').read_text())
    assert sha(store/'manifest.json') == pins['store_manifest_sha256']
    expected = {'manifest.json': pins['store_manifest_sha256'], 'mask_table.npy': m['mask_table_sha256']}
    for role in ('train', 'dev'):
        assert sha(store/role/'manifest.json') == pins['role_manifests'][role]
        expected[role+'/manifest.json'] = pins['role_manifests'][role]
        rm = json.loads((store/role/'manifest.json').read_text())
        for name, value in rm['arrays'].items():
            assert name and '/' not in name and name not in ('.', '..')
            expected[role+'/'+name+'.npy'] = value['sha256']
    if not a.reuse:
        sync(sorted(expected))
    rows = []
    for name, digest in sorted(expected.items()):
        assert sha(store/name) == digest, name
        rows.append(dict(path=name, sha256=digest, bytes=(store/name).stat().st_size))
        print(json.dumps(dict(stage='verified', files=len(rows), total=len(expected), latest=name)), flush=True)
    result = dict(passed=True, store_manifest_sha256=pins['store_manifest_sha256'],
                  source_host=a.source_host, source_store=a.source_store, reuse=a.reuse,
                  files=rows, bytes=sum(r['bytes'] for r in rows),
                  at=datetime.now(timezone.utc).isoformat(), wall_seconds=time.monotonic()-before)
    (work/'ops/store-verified.json').write_text(json.dumps(result, indent=2)+'\n')


if __name__ == '__main__':
    main()
