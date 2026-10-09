"""Small numerical templates from independently inspected round-2 fit pixels."""
import json
from pathlib import Path
import sys
import cv2
import numpy as np
from extract import sha
ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0,str(ROOT/'src'))
from clasher.live.crown_counter import color_feature
from clasher.live.result_screen import text_feature
STUDY = Path(__file__).resolve().parent
OUT = STUDY/'runtime/r3'

def main():
    cv2.setNumThreads(1)
    manifest = json.loads((STUDY/'round2-manifest.json').read_text())
    ep = 'v4-phase-a-1975101330'
    assert ep in manifest['fit'] and ep not in manifest['dev']
    data = dict(schema='clasher.public-score-templates.v1',crowns=[],result=dict(box=[68,490,474,549],size=[160,24],templates={},distance=.10,margin=.03,gap_ms=600,confirmation_frames=2,score_max_age_ms=500))
    # Explicit pixel annotations: HUD can lag the banner, so labels differ.
    labels = [(642,(0,0),(None,1)),(656,(0,0),(None,1)),(697,(0,1),(None,1)),(1071,(1,1),(1,None)),(2670,(1,1),(2,None)),(2710,(2,1),(None,None))]
    for side in range(2):
        hud = dict(box=[489,484 if side==0 else 644,538,563 if side==0 else 722],size=[12,20],templates={},distance=.07,margin=.015)
        banner = dict(box=[178,460 if side==0 else 692,352,503 if side==0 else 736],size=[48,12],templates={},distance=.10,margin=.02)
        for ordinal,counts,banners in labels:
            image = cv2.imread(str(OUT/f'{ep}-{ordinal}.jpg'))
            for region,label in ((hud,counts[side]),(banner,banners[side])):
                if label is not None:
                    f = color_feature(image,region['box'],tuple(region['size']))
                    region['templates'].setdefault(str(label),[]).append(np.round(f,5).tolist())
        data['crowns'].append([hud,banner])
    image = cv2.imread(str(OUT/f'{ep}-3272.jpg'))
    p = data['result']
    p['templates']['ended'] = [np.round(text_feature(image,p['box'],tuple(p['size'])),5).tolist()]
    destination = ROOT/'src/clasher/live/public_score_templates.json'
    destination.write_text(json.dumps(data,separators=(',',':'))+'\n')
    receipt = dict(schema='clasher.public-score-fit.r3',manifest_sha256=sha(STUDY/'round2-manifest.json'),episode=ep,annotations=[dict(ordinal=i,hud=c,banner=b) for i,c,b in labels],terminal_text_ordinal=3272,artifact_sha256=sha(destination),dev_used_for_fit=False,unsupported=['HUD digit 3','own banner 2/3','opponent banner 3','win/loss/draw result text'],training_only=True)
    (OUT/'score-fit-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(receipt,flush=True)

if __name__ == '__main__': main()
