"""Audit pairing/split/storage and annotate observed deployment-clock cues."""
import argparse
from collections import Counter,defaultdict
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

from clasher.vision.l1_events_v2 import CARDS,clock_markers
from collect_l1_events_v2 import disk_bytes
from collect_l1_rendered import REPORT,append,progress


def read(path):return [json.loads(l) for l in path.read_text().splitlines()]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dataset',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--fit-offsets',action='store_true')
    a=p.parse_args();cv2.setNumThreads(1)
    manifest=json.loads((a.dataset/'manifest.json').read_text())
    roles={e['episode_id']:e['split'] for e in manifest['matches']}
    rows=read(a.dataset/'inputs.jsonl');events=read(a.dataset/'evaluation_only/events.jsonl')
    lookup={(r['episode_id'],int(r['frame_id'])):r for r in rows}
    if len(lookup)!=len(rows):raise ValueError('Duplicate frames')
    offsets=defaultdict(list);annotations=[]
    cache={}
    for e in events:
        if a.fit_offsets and roles[e['episode_id']]!='train':continue
        clock_ticks=[];clock_observations=[]
        for tick in range(e['tick'],e['tick']+11):
            row=lookup.get((e['episode_id'],tick))
            if row is None:continue
            key=e['episode_id'],tick
            if key not in cache:
                cache[key]=clock_markers(cv2.imread(str(a.dataset/row['image'])))
            options=[m for m in cache[key] if m['player_id']==e['player_id'] and
                     np.hypot(m['px']-e['pixel'][0],m['py']-e['pixel'][1])<60]
            if options:
                m=min(options,key=lambda m:np.hypot(m['px']-e['pixel'][0],m['py']-e['pixel'][1]))
                clock_ticks.append(tick);clock_observations.append(m)
                if roles[e['episode_id']]=='train' and e['card'] not in ('Fireball','Log','Zap'):
                    offsets[str(e['player_id'])].append(np.array(e['pixel'])-[m['px'],m['py']])
                    offsets[f'{e["player_id"]}:{e["card"]}'].append(np.array(e['pixel'])-[m['px'],m['py']])
        annotations.append(dict(**e,clock_visible_ticks=clock_ticks,clock_observations=clock_observations,
            visual_cue_annotation='pixel gold-rim/color/Hough detector; model-assisted, not manual certification',
            unit_spawn='native body labels are weak; see visual review',
            spell_projectile_area='see per-event visual review'))
    if a.fit_offsets:
        learned={key:np.median(value,axis=0).tolist() for key,value in offsets.items() if len(value)>=3}
        learned.setdefault('0',[0.,-8.]);learned.setdefault('1',[0.,20.])
        a.output.write_text(json.dumps(dict(offsets=learned,counts={k:len(v) for k,v in offsets.items()},
            split='train',method='median true placement minus detected clock center; only matched training cues'),indent=2)+'\n')
        print(json.dumps(learned),flush=True);return
    a.output.mkdir(parents=True,exist_ok=False)
    manual={}
    for source in (REPORT/'v2/body-cue-review.jsonl',REPORT/'v2/spell-cue-review.jsonl'):
        if source.exists():
            for r in read(source):manual[r['episode_id'],r['tick'],r['player_id']]=r
    for annotation in annotations:
        key=annotation['episode_id'],annotation['tick'],annotation['player_id']
        if key in manual:
            annotation['manual_review']=manual[key]
            annotation['visual_cues']=manual[key]['visual_cues']
        append(a.output/'event-cues.jsonl',annotation)
    failures=[]
    receipts=read(a.dataset/'pairing.jsonl')
    if len(receipts)!=len(rows):failures.append('pairing count mismatch')
    for r in receipts:
        row=lookup[r['episode_id'],int(r['frame_id'])]
        if hashlib.sha256((a.dataset/row['image']).read_bytes()).hexdigest()!=r['jpeg_sha256']:
            failures.append('JPEG hash mismatch')
        if not r['before_after_equal'] or r['screenshot_produced_at']<r['capture_barrier']:
            failures.append('pairing barrier failure')
    tail=REPORT/'v2/tail-windows'
    supplements={}
    if (tail/'complete.json').exists():
        supplements={(r['episode_id'],r['tick']):r for r in read(tail/'frames.jsonl')}
        for r in supplements.values():
            if hashlib.sha256((tail/r['image']).read_bytes()).hexdigest()!=r['jpeg_sha256'] or not r['before_after_equal']:
                failures.append('supplement pairing/hash failure')
    truncated=[];recaptured=[]
    for e in events:
        missing=[t for t in range(e['tick']-6,e['tick']+31) if (e['episode_id'],t) not in lookup]
        if missing:
            key=dict(episode_id=e['episode_id'],tick=e['tick'],player_id=e['player_id'],missing_ticks=missing)
            truncated.append(key)
            if all((e['episode_id'],t) in supplements for t in range(e['tick']-6,e['tick']+31)):
                recaptured.append(key)
            else:failures.append(f'missing event window {e["episode_id"]}:{e["tick"]}')
    decks=[tuple(sorted(d)) for e in manifest['matches'] for d in e['decks']]
    seeds=[e['seed'] for e in manifest['matches']]
    if len(set(decks))!=len(decks) or len(set(seeds))!=len(seeds):failures.append('split identity overlap')
    coverage={split:Counter(f'{e["player_id"]}:{e["card"]}' for e in events if roles[e['episode_id']]==split)
              for split in ('train','validation','heldout')}
    missing={split:[f'{side}:{card}' for side in (0,1) for card in CARDS if not counts[f'{side}:{card}']]
             for split,counts in coverage.items()}
    result=dict(frames=len(rows),events=len(events),matches=len(manifest['matches']),
        split_frames=dict(Counter(r['split'] for r in rows)),coverage=coverage,missing_card_sides=missing,
        deployment_windows=len(events),negative_windows=sum(w['negative'] for w in read(a.dataset/'evaluation_only/windows.jsonl')),
        manual_event_reviews=sum((e['episode_id'],e['tick'],e['player_id']) in manual for e in events),
        original_truncated_windows=truncated,separately_recaptured_windows=recaptured,
        supplemental_frames=len(supplements),
        dataset_bytes=disk_bytes(a.dataset),v2_bytes=disk_bytes(REPORT/'v2'),live_loop_bytes=disk_bytes(REPORT.parent),
        paused_state_pairing=True,render_tick_certified=False,failures=failures,
        inputs_sha256=hashlib.sha256((a.dataset/'inputs.jsonl').read_bytes()).hexdigest(),
        events_sha256=hashlib.sha256((a.dataset/'evaluation_only/events.jsonl').read_bytes()).hexdigest())
    (a.output/'audit.json').write_text(json.dumps(result,indent=2)+'\n')
    progress(f'v2 dataset audit: {len(rows)} frames, {len(events)} events, {len(failures)} pairing/split failures; missing card-sides {missing}.')


if __name__=='__main__':main()
