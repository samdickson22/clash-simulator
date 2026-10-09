"""Extract only logged public/own/prior inputs, matched by exact search sequence."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path


def main(a):
    if a.output.exists():
        raise ValueError('Fresh extracted fixture required')
    inputs, unmatched, pins = [], [], {}
    for path in sorted(a.suite.glob('*/latency.jsonl.gz')):
        provenance = json.loads((path.parent/'provenance.json').read_text())
        if provenance.get('source_split') != 'train':
            raise ValueError('Only committed train development receipts may be extracted')
        rows = [json.loads(line) for line in gzip.open(path, 'rt')]
        processed = {row['sequence']: row for row in rows if row['metric'] == 'processed'}
        pins[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
        for row in rows:
            if row['metric'] != 'search' or not row['diagnostic'].get('scores'):
                continue
            if row['sequence'] not in processed:
                unmatched.append([path.parent.name, row['sequence']])
                continue
            public = processed[row['sequence']]
            inputs.append(dict(match=path.parent.name, sequence=row['sequence'], tick=public['tick'],
                public=public['public'], own=public['own'], roots=public['roots'],
                opponent=public['opponent'], revision=public['revision'], pending=public['pending'],
                recorded_delay_ticks=row['diagnostic']['command_delay_ticks'], recorded=row['diagnostic']))
    payload = dict(schema='clasher.live-perf.recorded-inputs.v1', split='train', inputs=inputs,
                   source_hashes=pins, unmatched=unmatched)
    with gzip.open(a.output, 'xb', compresslevel=6) as stream:
        stream.write((json.dumps(payload, indent=2)+'\n').encode())
    print(json.dumps(dict(inputs=len(inputs), unmatched=len(unmatched))), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--suite', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    main(p.parse_args())
