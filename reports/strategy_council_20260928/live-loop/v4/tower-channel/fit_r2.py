"""Fit-only rubble, King activation, and side-specific HP glyph revision."""
import argparse
from collections import defaultdict,Counter
import json
from pathlib import Path
import sys
import cv2
import numpy as np
from extract import sha
from fit import centers
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'src'))
from clasher.live.tower_channel import sprite_feature,activation_feature,glyphs,number_family,TowerChannel


def main(a):
    cv2.setNumThreads(1)
    m=json.loads((a.root/'manifest.json').read_text());base=json.loads(a.base.read_text())
    rubble=defaultdict(list);activate=defaultdict(lambda:defaultdict(list));digits=defaultdict(lambda:defaultdict(list));sample_counts=Counter();truth_events=[]
    for ep in m['fit']:
        d=np.load(a.root/(ep+'.npz'));sprites,panels=d['sprite'],d['panel'];rows=json.loads((a.root/(ep+'.json')).read_text())['rows'];events=json.loads((a.root/(ep+'.truth.json')).read_text())['events'];truth_events+=events;event_by_slot={e['slot']:e for e in events}
        for i,r in enumerate(rows):
            s=r['slot']
            if r['state']=='destroyed' and r['tick'] >= event_by_slot[s]['destruction_tick']+20:
                # Exclude collapse/crown transition; use stable rubble >=1s later.
                rubble[s].append(sprite_feature(sprites[i]));sample_counts['destroyed_'+str(s)]+=1
            if r['state']=='alive' and r['active'] is not None:
                activate[s]['active' if r['active'] else 'sleeping'].append(activation_feature(sprites[i]));sample_counts['activation_'+str(s)+'_'+str(r['active'])]+=1
            if r['hp'] is not None and r['hp']>0 and s in (1,2,3):
                gs=glyphs(panels[i],s);text=str(r['hp'])
                if len(gs)==len(text):
                    for ch,g in zip(text,gs):digits[number_family(s)][ch].append(g)
    # Preserve round-1 living templates and own-princess OCR.
    for s in (1,2,4,5):
        values=rubble[s]+rubble[2 if s==1 else 1 if s==2 else 5 if s==4 else 4]
        base['sprites'][s]['destroyed']=centers(values,8) if values else []
    base['activation']={s:{state:centers(v,6) for state,v in table.items()} for s,table in activate.items() if len(table)==2}
    base['digits_by_family']={family:{d:centers(v,8) for d,v in table.items()} for family,table in digits.items()}
    base['number_enabled']={'opp_princess':True,'own_king':True}
    base['parameters'].update(activation_distance=.08,activation_margin=.02,opp_princess_digit_distance=.14,opp_princess_digit_margin=.035,own_king_digit_distance=.14,own_king_digit_margin=.035)
    base['manifest_sha256']=sha(a.root/'manifest.json');base['round']=2
    a.output.write_text(json.dumps(base,separators=(',',':'))+'\n')
    channel=TowerChannel(a.output);counts=defaultdict(Counter)
    for ep in m['fit']:
        d=np.load(a.root/(ep+'.npz'));sprites,panels=d['sprite'],d['panel'];rows=json.loads((a.root/(ep+'.json')).read_text())['rows']
        for i,r in enumerate(rows):
            if r['hp'] is None or r['hp']<=0:continue
            state,c,hp,b=channel.read_crop(sprites[i],panels[i],r['slot'])
            family=number_family(r['slot']);counts[family]['eligible']+=1
            if hp is not None:counts[family]['accepted']+=1;counts[family]['exact']+=hp==r['hp']
    # Predeclared >=99% accepted accuracy gate applies separately on fit AND dev.
    for family in ('opp_princess','own_king'):
        c=counts[family]
        base['number_enabled'][family]=bool(c['accepted'] and c['exact']/c['accepted']>=.99)
    a.output.write_text(json.dumps(base,separators=(',',':'))+'\n')
    receipt=dict(manifest_sha256=base['manifest_sha256'],model_sha256=sha(a.output),fit_episodes=m['fit'],destruction_events=len(truth_events),samples=dict(sample_counts),glyph_samples={f:{d:len(v) for d,v in table.items()} for f,table in digits.items()},fit_numbers={f:dict(c) for f,c in counts.items()},number_enabled=base['number_enabled'],dev_pixels_opened=False,dev_used_for_fit=False,validation_payloads_opened=False,heldout_payloads_opened=False)
    a.output.with_name('round2-fit-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(receipt,flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('base',type=Path);p.add_argument('output',type=Path);main(p.parse_args())
