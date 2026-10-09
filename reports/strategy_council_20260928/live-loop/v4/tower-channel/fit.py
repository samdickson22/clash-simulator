"""Fit tiny numerical templates ONLY from study-manifest fit matches."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import sys

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[5]/'src'))
from clasher.live.tower_channel import sprite_feature, glyphs

# Manual fit-only annotations: last sampled crop visibly has collapsed stone
# walls AND crossed broken timbers. Crown animations / occlusion are excluded.
RUBBLE = {'1330': [2,4,5], '1240':[2,4], '1304':[4], '1177':[2,4],
          '1332':[2], '1233':[4], '1176':[4,5], '1274':[4], '1184':[2]}


def centers(values, count):
    x = np.array(values, np.float32)
    cv2.setRNGSeed(7309)
    _, _, means = cv2.kmeans(x, min(count,len(x)), None,
                           (cv2.TERM_CRITERIA_EPS+cv2.TERM_CRITERIA_MAX_ITER,40,.001),
                           1,cv2.KMEANS_PP_CENTERS)
    return np.round(means,5).tolist()


def run(a):
    cv2.setNumThreads(1)
    manifest = json.loads((a.root/'manifest.json').read_text())
    alive, rubble, digits = defaultdict(list), defaultdict(list), defaultdict(list)
    inputs = {}
    annotations = []
    for ep in manifest['fit']:
        data = np.load(a.root/(ep+'.npz'))
        sprites, panels = data['sprite'], data['panel']
        info = json.loads((a.root/(ep+'.json')).read_text())
        inputs[ep] = {k:v for k,v in info.items() if k != 'rows'}
        last = info['rows'][-1]['ordinal']
        for i,r in enumerate(info['rows']):
            s = r['slot']
            if r['hp'] is not None and r['hp'] > 0:
                alive[s].append(sprite_feature(sprites[i]))
                gs = glyphs(panels[i],s)
                text = str(int(r['hp']))
                if len(gs) == len(text):
                    for d,g in zip(text,gs):
                        digits[d].append(g)
            if r['ordinal'] == last and s in RUBBLE.get(ep[-4:],[]):
                # Reuse left/right local visual signal within each side only.
                for target in ([1,2] if s < 3 else [4,5]):
                    rubble[target].append(sprite_feature(sprites[i]))
                annotations.append(dict(episode=ep, ordinal=last, slot=s, state='destroyed',
                                        evidence='collapsed stone walls with crossed broken timbers'))
    artifact = dict(schema='clasher.public-tower-templates.v1',
                    manifest_sha256=hashlib.sha256((a.root/'manifest.json').read_bytes()).hexdigest(),
                    parameters=dict(alive_distance=.15, rubble_distance=.055, rubble_margin=.035,
                                    digit_distance=.18, digit_margin=.03, confirmation_frames=3, confirmation_gap_ms=600),
                    sprites=[dict(alive=centers(alive[s],4), destroyed=centers(rubble[s],3) if rubble[s] else []) for s in range(6)],
                    digits={d:centers(v,6) for d,v in digits.items()})
    a.output.write_text(json.dumps(artifact,separators=(',',':'))+'\n')
    a.output.with_name('fit-receipt.json').write_text(json.dumps(dict(manifest_sha256=artifact['manifest_sha256'],
        fitting_episodes=manifest['fit'], inputs=inputs, manual_destruction_annotations=annotations,
        alive_samples={s:len(v) for s,v in alive.items()}, glyph_samples={d:len(v) for d,v in digits.items()},
        model_sha256=hashlib.sha256(a.output.read_bytes()).hexdigest(), validation_payloads_opened=False,
        dev_used_for_fit=False, heldout_payloads_opened=False),indent=2)+'\n')
    print({s:len(v) for s,v in alive.items()}, {d:len(v) for d,v in digits.items()},flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('root',type=Path)
    p.add_argument('output',type=Path)
    run(p.parse_args())
