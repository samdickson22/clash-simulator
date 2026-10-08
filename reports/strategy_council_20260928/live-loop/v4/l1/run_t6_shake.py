"""Resumable stage wrapper; validation only, no heldout code path."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time


def run(args):
    print('RUN',args,flush=True);subprocess.run([sys.executable,*map(str,args)],check=True)


def canonical_inputs(rows):
    return [dict(row,timestamp_ms=int(row['timestamp_ms'])) for row in rows]


def main():
    p=argparse.ArgumentParser();p.add_argument('--dataset',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--pixel-cache-mib',type=int,default=4096)
    p.add_argument('--epochs',type=int,default=1);p.add_argument('--steps',type=int,default=40);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=True)
    deadline=time.monotonic()+3600
    while not (a.dataset/'complete.json').exists():
        if time.monotonic()>deadline:raise TimeoutError('Converter not complete in one hour')
        time.sleep(10)
    manifest=json.loads((a.dataset/'manifest.json').read_text())
    if any(e['split'] not in ('train','validation') for e in manifest['matches']):raise ValueError('Heldout forbidden')
    model=a.output/'model';inference=a.output/'validation-inference';evaluation=a.output/'validation-evaluation'
    if not (model/'complete.json').exists():
        run(['scripts/train_l1_stream_v3.py','--dataset',a.dataset,'--audit',a.dataset/'audit','--output',model,'--device','cuda','--pixel-cache-mib',a.pixel_cache_mib,'--epochs',a.epochs,'--steps',a.steps])
    inputs=a.output/'validation-inputs.jsonl'
    if not inputs.exists():run(['scripts/evaluate_l1_stream_v3.py','--dataset',a.dataset,'--audit',a.dataset/'audit','--split','validation','--prepare-inputs','--output',inputs])
    # The unchanged public contract requires integer milliseconds. Preserve raw
    # producer timestamps; canonicalization matches v3 sample_inputs exactly.
    rows=[json.loads(x) for x in inputs.read_text().splitlines()]
    if any(r['timestamp_ms']!=int(r['timestamp_ms']) for r in rows):
        original=a.output/'validation-inputs-producer-ms.jsonl'
        if not original.exists():original.write_bytes(inputs.read_bytes())
        rows=canonical_inputs(rows)
        inputs.write_text(''.join(json.dumps(r)+'\n' for r in rows))
    if not (inference/'complete.json').exists():run(['scripts/infer_l1_stream_v3.py','--inputs',inputs,'--media-root',a.dataset,'--model',model/'last.pt','--output',inference,'--device','cuda'])
    if not (evaluation/'metrics.json').exists():run(['scripts/evaluate_l1_stream_v3.py','--dataset',a.dataset,'--audit',a.dataset/'audit','--split','validation','--inference',inference,'--output',evaluation])
    # Additional opponent-only slice uses exactly the unchanged historical matcher.
    from evaluate_l1_stream_v3 import read,replay,score_events
    from clasher.rl.live_inference_contract import parse_public_vision_frame
    from dataclasses import replace
    frames=[parse_public_vision_frame(x) for x in read(inference/'frames.jsonl')];cues=read(inference/'candidates.jsonl')
    selection=json.loads((evaluation/'selection.json').read_text());prediction=replay(frames,cues,selection['thresholds'])
    scored=[replace(f,timestamp_ms=round(c['available_timestamp_ms']),play_events=tuple(e for e in f.play_events if e.player_id==0)) for f,c in zip(prediction,cues)]
    truth=[r for e in manifest['matches'] if e['split']=='validation' for r in read(a.dataset/'audit'/e['episode_id']/'events.jsonl') if r['player_id']==0]
    metrics=dict(opponent=score_events(scored,truth),all_sides=json.loads((evaluation/'metrics.json').read_text()),
                 inference=json.loads((inference/'timing.json').read_text()),epochs=a.epochs,steps_per_epoch=a.steps,heldout_opened=False)
    (a.output/'complete.json').write_text(json.dumps(metrics,indent=2)+'\n')

if __name__=='__main__':
    sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'scripts'));main()
