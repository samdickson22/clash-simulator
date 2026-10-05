"""Verify L1 image/label pairing receipts and freeze media-only heldout inputs."""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import cv2

from clasher.rl.live_inference_contract import assert_no_privileged_payload
from clasher.vision.l1_perception import clock_digits


def audit(dataset):
    if not (dataset/'complete.json').exists():
        raise ValueError('Incomplete collection')
    rows=[json.loads(l) for l in (dataset/'labels.jsonl').read_text().splitlines()]
    manifest=json.loads((dataset/'manifest.json').read_text())
    entries={e['episode_id']:e for e in manifest['matches']}
    is_v1=manifest['schema']=='clasher.l1.dataset.v2'
    receipts=[json.loads(l) for l in (dataset/'pairing.jsonl').read_text().splitlines()]
    if len(rows)!=len(receipts): raise ValueError('Pairing count differs')
    seen=set(); counts=Counter(); classes=Counter(); durations=[]; hidden=0; size=0
    inputs=[]
    for row,receipt in zip(rows,receipts):
        key=(row['episode_id'],row['frame_id'])
        if key in seen or key!=(receipt['episode_id'],receipt['frame_id']):
            raise ValueError('Pair identity mismatch')
        seen.add(key)
        if row['episode_id'] not in entries or entries[row['episode_id']]['split']!=row['split']:
            raise ValueError('Frame is outside its manifest split')
        if row['timestamp_ms']!=int(row['frame_id'])*50:
            raise ValueError('Native media timestamp differs')
        raw=(dataset/row['image']).read_bytes();size+=len(raw)
        if hashlib.sha256(raw).hexdigest()!=receipt['jpeg_sha256']:
            raise ValueError('Image checksum mismatch')
        if not receipt['paused'] or not receipt['before_after_equal'] or str(receipt['tick'])!=row['frame_id']:
            raise ValueError('Pairing receipt failed')
        assert_no_privileged_payload(row['targets'])
        if is_v1:
            if not receipt.get('visible_clock_verified') or receipt['visible_clock_seconds']!=row['targets']['visible_clock_seconds']:
                raise ValueError('Missing visible clock pairing check')
            if receipt.get('transport')!='GrpcScreenStream':raise ValueError('Unqualified v1 capture path')
            if any(e.get('visibility') not in ('visible','occluded','uncertain') for e in row['targets']['entities']):
                raise ValueError('Missing per-object visibility assessment')
        im=cv2.imread(str(dataset/row['image']))
        if im.shape!=(1140,540,3):raise ValueError('Image geometry changed')
        # Interior of the private HUD must remain black after JPEG coding.
        if im[8:135,8:532].max()>3:raise ValueError('Opponent HUD pixels present')
        hidden+=int(not clock_digits(im))
        durations.append(receipt['capture_seconds'])
        counts[row['split']]+=1
        classes.update(f'{e["player_id"]}:{e["card"]}' for e in row['targets']['entities'])
        if row['split']=='heldout':
            inputs.append({k:row[k] for k in ('episode_id','frame_id','timestamp_ms','image')})
    if hidden: raise ValueError('Clock hidden on accepted frames')
    roles={}; seeds=set()
    for e in manifest['matches']:
        if e['seed'] in seeds:raise ValueError('Repeated seed')
        seeds.add(e['seed'])
        for deck in e['decks']:
            key=tuple(sorted(deck))
            if key in roles and roles[key]!=e['split']:raise ValueError('Deck leakage')
            roles[key]=e['split']
    (dataset/'heldout-inputs.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in inputs))
    result=dict(frames=len(rows),jpeg_bytes=size,split_frames=dict(counts),
                body_labels=dict(classes),pairing_passed=len(receipts),hidden_clock_frames=hidden,
                distinct_seeds=len(seeds),distinct_decks=len(roles),seed_deck_split_disjoint=True,
                mean_capture_seconds=sum(durations)/len(durations),
                max_capture_seconds=max(durations),
                visibility_counts=dict(Counter(e.get('visibility','unassessed') for row in rows for e in row['targets']['entities'])),
                labels_sha256=hashlib.sha256((dataset/'labels.jsonl').read_bytes()).hexdigest(),
                pairing_sha256=hashlib.sha256((dataset/'pairing.jsonl').read_bytes()).hexdigest(),
                screen_tick_limit='No native compositor fence exists; paused observe equality plus visible-clock readiness and visual spot checks.')
    (dataset/'audit.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('dataset',type=Path)
    print(json.dumps(audit(p.parse_args().dataset)))
