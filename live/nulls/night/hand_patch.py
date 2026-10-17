"""05: one-off: rewrite the `hand` field of already-labelled night frames from the raw observation (nextCard fix)."""
import gzip
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from label import NIGHT, hand_from_obs  # noqa: E402

n = 0
for f in NIGHT.glob('i*/*/chunk-*/*.json'):
    if f.name.startswith('raw-'):
        continue
    try:
        rec = json.loads(f.read_text())
    except (OSError, ValueError):
        continue
    if rec.get('purpose') != 'scene' or ((rec.get('hand') or {}).get('ours') or {}).get('slot_names'):
        continue
    try:
        with gzip.open(f.parent / rec['observations'], 'rt') as fh:
            rec['hand'] = hand_from_obs(json.load(fh).get('plain') or {})
    except (OSError, ValueError, KeyError):
        continue
    tmp = f.with_name('.' + f.name + '.part')
    tmp.write_text(json.dumps(rec, separators=(',', ':')))
    os.replace(tmp, f)
    n += 1
print('patched', n)
