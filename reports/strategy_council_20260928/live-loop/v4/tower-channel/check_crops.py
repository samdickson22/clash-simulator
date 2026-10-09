"""Fit-only diagnostic before freezing. Never used to inspect dev crops."""
import json
from pathlib import Path
import sys
from collections import Counter
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'src'))
from clasher.live.tower_channel import TowerChannel
root = Path(sys.argv[1])
channel = TowerChannel()
counts = Counter()
errors = []
for ep in json.loads((root/'manifest.json').read_text())['fit']:
    data = np.load(root/(ep+'.npz'))
    sprites, panels = data['sprite'], data['panel']
    for i,r in enumerate(json.loads((root/(ep+'.json')).read_text())['rows']):
        if r['hp'] is None:
            continue
        state,_,hp,fraction = channel.read_crop(sprites[i],panels[i],r['slot'])
        counts['truth'] += 1
        counts[state] += 1
        if r['slot']%3 == 0:
            continue
        counts['princess_truth'] += 1
        if hp is not None:
            counts['number_read'] += 1
            counts['number_exact'] += hp == r['hp']
            if hp != r['hp'] and len(errors)<15:
                errors.append(dict(episode=ep,slot=r['slot'],ordinal=r['ordinal'],truth=r['hp'],read=hp))
        if fraction is not None:
            counts['bar_read'] += 1
            counts['bar_within_5pct'] += abs(fraction-r['hp']/3052) <= .05
print(json.dumps(dict(counts=dict(counts),errors=errors),indent=2))
