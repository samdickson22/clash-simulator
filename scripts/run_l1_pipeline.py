"""Run the bounded L1 training/evaluation continuation under pilot/detach.sh."""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path


ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/'reports/strategy_council_20260928/live-loop/l1'


def log(message):
    print(message,flush=True)
    with (REPORT/'PROGRESS.md').open('a') as f:
        f.write(f'\n{time.strftime("%Y-%m-%d %H:%M:%S")}: {message}\n')


def run(name,*args):
    log('Starting '+name)
    with (REPORT/(name+'.log')).open('w') as target:
        subprocess.run([sys.executable,*map(str,args)],cwd=ROOT,stdout=target,stderr=subprocess.STDOUT,check=True)
    log('Completed '+name)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--collector-pid',type=int,required=True)
    p.add_argument('--epochs',type=int,default=40)
    args=p.parse_args()
    dataset=REPORT/'dataset';model=REPORT/'model';inference=REPORT/'inference'
    deadline=time.monotonic()+2400
    while not (dataset/'complete.json').exists():
        result=subprocess.run(['ps','-p',str(args.collector_pid),'-o','command='],text=True,capture_output=True)
        if result.returncode or 'scripts/collect_l1_rendered.py' not in result.stdout:
            raise RuntimeError('Owned collector ended without completion')
        if time.monotonic()>deadline:raise TimeoutError('Bounded collection wait expired')
        time.sleep(10)
    support=REPORT/'support-dataset'
    run('support','scripts/collect_l1_rendered.py','--output',support,'--matches',1,
        '--ticks',1200,'--cadence',40,'--seed-base',261004902,'--training-only','--prioritize-card','Tesla')
    main_manifest=json.loads((dataset/'manifest.json').read_text())
    extra_manifest=json.loads((support/'manifest.json').read_text())
    if any(e['episode_id'] in {r['episode_id'] for r in main_manifest['matches']} for e in extra_manifest['matches']):
        raise ValueError('Support episode identity collision')
    held_decks={tuple(sorted(d)) for e in main_manifest['matches'] if e['split']!='train' for d in e['decks']}
    if any(tuple(sorted(d)) in held_decks for e in extra_manifest['matches'] for d in e['decks']):
        raise ValueError('Support deck overlaps validation/heldout')
    for image in (support/'frames').glob('*.jpg'):
        os.link(image,dataset/'frames'/image.name)
    for name in ('labels.jsonl','pairing.jsonl','episodes.jsonl','evaluation_only/truth.jsonl','evaluation_only/events.jsonl'):
        with (dataset/name).open('ab') as target:target.write((support/name).read_bytes())
    main_manifest['matches'].extend(extra_manifest['matches'])
    main_manifest['support_collection']='Training-only class coverage addition; seed 261004902, 1200-tick cap, Tesla priority. Original heldout unchanged.'
    (dataset/'manifest.json').write_text(json.dumps(main_manifest,indent=2)+'\n')
    complete=json.loads((dataset/'complete.json').read_text());extra=json.loads((support/'complete.json').read_text())
    complete['matches']+=extra['matches'];complete['jpeg_bytes']+=extra['jpeg_bytes']
    (dataset/'complete.json').write_text(json.dumps(complete,indent=2)+'\n')
    log('Merged independent training-only Tesla coverage. Heldout frames and labels unchanged.')
    run('audit','scripts/audit_l1_dataset.py',dataset)
    run('train','scripts/train_l1_perception.py','--dataset',dataset,'--output',model,'--epochs',args.epochs)
    run('infer','scripts/infer_l1_perception.py','--inputs',dataset/'heldout-inputs.jsonl',
        '--image-root',dataset,'--model',model/'detector/weights/best.pt','--hud',model/'hud.npz',
        '--calibration',REPORT/'calibration.json','--output',inference)
    run('evaluate','scripts/evaluate_l1_perception.py','--dataset',dataset,
        '--predictions',inference/'frames.jsonl','--prior',REPORT/'public-deck-prior.json',
        '--output',REPORT/'evaluation')
    (REPORT/'pipeline-complete.json').write_text(json.dumps(dict(status='complete'))+'\n')
    log('L1 artifacts ready for final audit. Emulator still owned for capture-inclusive timing.')


if __name__=='__main__':
    main()
