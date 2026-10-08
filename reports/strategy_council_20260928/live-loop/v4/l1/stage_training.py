"""Stage only receipt-admitted Phase A train/validation payloads from the hub.

Run under a lease/fleet wrapper. Never traverse/copy heldout payloads.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import shutil

HUB = '/mpac/sdicks02/repos/clasher-v4-data/matches'
FILES = ('receipt.json', 'frames.jsonl', 'hud.jsonl', 'events.jsonl',
         'objects.jsonl.gz', 'rich-objects.jsonl.gz', 'video.mp4')
T6_FILES = ('setup.json', 'commands.jsonl', 'negative-windows.jsonl', 'evaluation-only.jsonl.gz')
OPTIONAL_T6_FILES = ('observation-skips.jsonl',)


def staging_files(rows, *, labels_only=False, all_training_payloads=False):
    if any(r['split'] not in ('train','validation') for r in rows):raise ValueError('Heldout payload staging forbidden')
    if labels_only and all_training_payloads:raise ValueError('Converter staging requires complete media')
    files=[n for n in FILES if not (labels_only and n=='video.mp4')]
    if all_training_payloads:
        files.extend(T6_FILES)
        required=set(files)-{'receipt.json'};allowed=required|set(OPTIONAL_T6_FILES)
        if any(not required<=set(r['files'])<=allowed for r in rows):
            raise ValueError('Converter receipt payload allowlist differs')
        files.extend(OPTIONAL_T6_FILES)
    return files


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''): h.update(b)
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--destination', type=Path, required=True)
    p.add_argument('--split', type=Path, required=True)
    p.add_argument('--partition', type=int, default=0)
    p.add_argument('--partitions', type=int, default=1)
    p.add_argument('--limit', type=int, default=0)
    p.add_argument('--episodes', nargs='+')
    p.add_argument('--labels-only', action='store_true')
    p.add_argument('--all-training-payloads', action='store_true',
                   help='Also copy receipt-pinned train/validation converter inputs; never heldout payloads')
    p.add_argument('--heldout-receipts-only', action='store_true',help='Copy receipt JSON only for formal count admission; never payloads')
    a = p.parse_args()
    if not 0<=a.partition<a.partitions:raise ValueError('Invalid partition')
    if sha(a.split) != '3edbd25bdae8e9b9efd6f0b4341e2caf5214854a74de56d250e81290653b5258':
        raise ValueError('Frozen split mismatch')
    members = {r['seed']: r for r in json.loads(a.split.read_text())['matches']}
    # Only receipt.json is read on the hub, including for heldout.
    script = ('import json,pathlib; print(json.dumps([p.read_text() '
              f'for p in sorted(pathlib.Path({HUB!r}).glob("*/receipt.json"))]))')
    result = subprocess.run(['ssh', '-o', 'BatchMode=yes', '127x01', 'python3 -'],
                            input=script, text=True, capture_output=True, check=True)
    rows = [];heldout_receipts=[]
    for raw in json.loads(result.stdout):
        r=json.loads(raw)
        if r.get('split')=='heldout' and a.heldout_receipts_only:
            m=members[r['seed']]
            if (m['split'],m['decks'])!=(r['split'],r['decks']):raise ValueError('Heldout receipt membership mismatch')
            if '/' in r['episode'] or not r['episode'].startswith('v4-phase-a-'):raise ValueError('Invalid episode')
            heldout_receipts.append((r['episode'],raw))
        if r.get('split') not in ('train', 'validation'): continue
        m = members[r['seed']]
        if (m['split'], m['decks']) != (r['split'], r['decks']): raise ValueError('Membership mismatch')
        if (r['seed'] - 1975100700) % a.partitions != a.partition: continue
        if a.episodes and r['episode'] not in a.episodes: continue
        if '/' in r['episode'] or not r['episode'].startswith('v4-phase-a-'): raise ValueError('Invalid episode')
        rows.append(r)
    if a.limit: rows = rows[:a.limit]
    a.destination.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(a.destination).free<210_000_000_000:
        raise RuntimeError('Need 200 GB free plus 10 GB staging headroom')
    for episode,raw in heldout_receipts:
        root=a.destination/episode;root.mkdir(exist_ok=True);q=root/'receipt.json'
        if q.exists():
            if q.read_text()!=raw:raise ValueError('Heldout receipt changed')
        else:
            with q.open('x') as f:f.write(raw)
    files=staging_files(rows,labels_only=a.labels_only,all_training_payloads=a.all_training_payloads)
    listing = ''.join(f'{r["episode"]}/{n}\n' for r in rows for n in files if n=='receipt.json' or n in r['files'])
    subprocess.run(['rsync', '-a', '--checksum', '--rsync-path=nice -n 10 rsync', '--files-from=-',
                    f'127x01:{HUB}/', str(a.destination) + '/'], input=listing, text=True, check=True)
    for r in rows:
        root = a.destination / r['episode']
        if json.loads((root / 'receipt.json').read_text()) != r: raise ValueError('Receipt changed during copy')
        for n in files:
            if n != 'receipt.json' and n in r['files'] and sha(root / n) != r['files'][n]: raise ValueError(f'Bad copy: {root / n}')
    receipt = dict(matches=len(rows), frames=sum(r['frames'] for r in rows),
                   episodes=[r['episode'] for r in rows], heldout_payloads_opened=False,
                   complete_population=not(a.limit or a.episodes or a.labels_only or a.partitions!=1) and a.heldout_receipts_only,
                   receipt_sha256={r['episode']:sha(a.destination/r['episode']/'receipt.json') for r in rows},
                   heldout_receipt_sha256={ep:sha(a.destination/ep/'receipt.json') for ep,_ in heldout_receipts})
    snapshot=a.destination/'stage-inventory.json';tmp=snapshot.with_suffix('.tmp')
    tmp.write_text(json.dumps(receipt,indent=2)+'\n');tmp.replace(snapshot)
    print(json.dumps(receipt), flush=True)


if __name__ == '__main__': main()
