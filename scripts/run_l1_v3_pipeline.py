"""Wait for owned collection, stop its emulators, then fit and score frozen splits."""
import argparse
import hashlib
import json
import os
import subprocess
import time
import tomllib

from collect_l1_rendered import REPORT,append,progress
from collect_l1_events_v2 import disk_bytes

ROOT=REPORT.parents[3]
V3=REPORT/'v3'
PY=ROOT/'.venv/bin/python'


def run(name,args):
    progress('v3 starting '+name)
    with (V3/(name+'.log')).open('w') as log:
        child=subprocess.Popen([str(PY),*map(str,args)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        append(V3/'pipeline-processes.jsonl',dict(name=name,pid=child.pid,args=list(map(str,args))))
        if child.wait():raise RuntimeError(f'{name} failed; see retained log')
    if disk_bytes(V3)>2*1024**3 or disk_bytes(REPORT.parent)>5.5*1024**3:
        raise RuntimeError('Post-step storage cap exceeded')
    progress('v3 finished '+name)


def merge():
    output=V3/'dataset-merged';output.mkdir(exist_ok=False)
    (output/'videos').mkdir();(output/'evaluation_only').mkdir()
    matches=[];episodes=[];seeds=set();decks=set();origins={}
    cards=ids=None
    for name in ('dataset','dataset-extra'):
        source=V3/name;manifest=json.loads((source/'manifest.json').read_text())
        if cards is not None and (manifest['cards']!=cards or manifest['ids']!=ids):raise ValueError('Roster changed')
        cards,ids=manifest['cards'],manifest['ids']
        completed={}
        for path in source.glob('episodes-*.jsonl'):
            for line in path.read_text().splitlines():
                row=json.loads(line);completed[row['episode_id']]=row
        origins[name]=hashlib.sha256((source/'manifest.json').read_bytes()).hexdigest()
        for entry in manifest['matches']:
            if entry['episode_id'] not in completed:continue
            if entry['seed'] in seeds:raise ValueError('Seed leak across splits')
            seeds.add(entry['seed'])
            for deck in entry['decks']:
                key=tuple(sorted(deck))
                if key in decks:raise ValueError('Deck leak across splits')
                decks.add(key)
            ep=entry['episode_id'];stats=completed[ep]
            matches.append(dict(entry,capture_protocol=stats.get('capture_protocol',1),source_corpus=name))
            episodes.append(stats)
            os.link(source/'videos'/f'{ep}.mp4',output/'videos'/f'{ep}.mp4')
            dest=output/'evaluation_only'/ep;dest.mkdir()
            for path in (source/'evaluation_only'/ep).iterdir():
                if path.is_file():os.link(path,dest/path.name)
    total=sum(e['accepted_events'] for e in episodes)
    if total<3000:raise ValueError(f'Only {total} accepted deployments; more collection required')
    (output/'manifest.json').write_text(json.dumps(dict(schema='clasher.l1.stream.v3',
        matches=matches,cards=cards,ids=ids,source_manifest_hashes=origins,
        primary_scoring='complete-tail protocol 2 validation/heldout only; decision made before fitting'),indent=2)+'\n')
    for episode in episodes:append(output/'episodes-merged.jsonl',episode)
    (output/'complete.json').write_text(json.dumps(dict(matches=len(matches),deployments=total,hardlinks=True))+'\n')
    progress(f'v3 merged {len(matches)} matches and {total} deployments, preserving original splits and hardlinking media.')
    return output


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--timeout-hours',type=float,default=4)
    a=p.parse_args();deadline=time.monotonic()+a.timeout_hours*3600
    try:
        while not all((V3/f'collection-complete-{s}.json').exists() for s in (0,1)):
            if time.monotonic()>deadline:raise TimeoutError('Collection continuation deadline')
            time.sleep(5)
        for name in ('emulator-host2','emulator-host-second'):
            if not (V3/name/'stop.json').exists():
                run('stop-'+name,['scripts/stop_l1_reference_v3.py',V3/name/'complete.json'])
        data=V3/'dataset-merged'
        if not (data/'complete.json').exists():data=merge()
        audit=V3/'audit';model=V3/'model'
        if not (audit/'summary.json').exists():run('audit',['scripts/audit_l1_stream_v3.py',data,'--output',audit])
        config=tomllib.loads((V3/'config.toml').read_text())
        if not (model/'complete.json').exists():
            run('train',['scripts/train_l1_stream_v3.py','--dataset',data,'--audit',audit,'--output',model,
                '--epochs',config['training']['epochs'],'--steps',config['training']['steps_per_epoch']])
        for split in ('validation','heldout'):
            inputs=V3/f'{split}-inputs.jsonl';inference=V3/f'inference-{split}';evaluation=V3/f'evaluation-{split}'
            if not inputs.exists():
                run('inputs-'+split,['scripts/evaluate_l1_stream_v3.py','--dataset',data,'--audit',audit,
                    '--split',split,'--prepare-inputs','--output',inputs])
            if split=='validation' and not (V3/'boundary-runtime.json').exists():
                run('boundary',['scripts/verify_l1_v3_boundary.py','--inputs',inputs,'--media-root',data,
                    '--model',model/'last.pt','--output',V3/'boundary-runtime.json'])
            if not (inference/'complete.json').exists():
                run('infer-'+split,['scripts/infer_l1_stream_v3.py','--inputs',inputs,'--media-root',data,
                    '--model',model/'last.pt','--output',inference])
            else:
                complete=json.loads((inference/'complete.json').read_text())
                for name in ('frames','candidates'):
                    if hashlib.sha256((inference/(name+'.jsonl')).read_bytes()).hexdigest()!=complete[name+'_sha256']:
                        raise ValueError('Frozen prediction hash changed')
            args=['scripts/evaluate_l1_stream_v3.py','--dataset',data,'--audit',audit,
                '--split',split,'--inference',inference,'--output',evaluation]
            if split=='heldout':args+=['--selection',V3/'evaluation-validation/selection.json']
            if not (evaluation/'metrics.json').exists():run('evaluate-'+split,args)
        run('report',['scripts/report_l1_v3.py'])
        (V3/'pipeline-complete.json').write_text(json.dumps(dict(completed_at=time.time()))+'\n')
    except BaseException as error:
        (V3/'pipeline-error.json').write_text(json.dumps(dict(type=type(error).__name__,error=str(error),at=time.time()))+'\n')
        progress(f'v3 pipeline stopped: {type(error).__name__}: {error}')
        raise


if __name__=='__main__':main()
