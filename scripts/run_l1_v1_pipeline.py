"""Resume-safe L1 v1 collection waiter, audit, training and heldout evaluation."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback
import zipfile

ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/'reports/strategy_council_20260928/live-loop/l1'
V1=REPORT/'v1'
PY=ROOT/'.venv/bin/python'
ADB=Path.home()/'.cache/clasher-native-reference/android-sdk/platform-tools/adb'


def progress(message):
    with (REPORT/'PROGRESS.md').open('a') as f:f.write(f'\n{time.strftime("%Y-%m-%d %H:%M:%S")}: v1 {message}\n')
    print(message,flush=True)


def run(name,arguments):
    done=V1/(name+'-complete.json')
    if done.exists():return
    progress('Starting '+name)
    with (V1/(name+'.log')).open('w') as log:
        result=subprocess.run([str(PY),*map(str,arguments)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
    if result.returncode:raise RuntimeError(f'{name} exited {result.returncode}; see {name}.log')
    done.write_text(json.dumps(dict(exit_code=0,completed_at=time.time()))+'\n')
    progress('Completed '+name)


def stop_owned(folder):
    if (folder/'stop.json').exists():return
    r=json.loads((folder/'complete.json').read_text())
    command=subprocess.check_output(['ps','-p',str(r['pid']),'-o','command='],text=True)
    if 'clasher_reference_api35' not in command or f"-port {r['serial'].split('-')[-1]}" not in command:
        raise ValueError('Refuse to signal changed emulator identity')
    for firewall in ('iptables','ip6tables'):
        subprocess.run([str(ADB),'-s',r['serial'],'shell',firewall,'-C','OUTPUT','-m','owner',
                        '--uid-owner',str(r['app_uid']),'!','-o','lo','-j','REJECT'],check=True,capture_output=True)
    subprocess.run([str(ADB),'-s',r['serial'],'emu','kill'],check=True,capture_output=True)
    (folder/'stop.json').write_text(json.dumps(dict(pid=r['pid'],at=time.time(),firewall_rechecked=True))+'\n')
    progress(f'Stopped owned {r["serial"]}, PID {r["pid"]}')


def merge():
    output=V1/'dataset-merged'
    if (output/'complete.json').exists():return output
    output.mkdir(exist_ok=False);(output/'frames').mkdir();(output/'evaluation_only').mkdir()
    matches=[];rows=[];receipts=[];events=[];truth=[];episodes=[]
    policy=json.loads((V1/'collection-plan.json').read_text())
    def split(seed):
        return ('heldout' if seed in policy['heldout_seeds'] else
                'validation' if seed in policy['validation_seeds'] else 'train')
    for name in ('dataset','dataset-second2'):
        p=V1/name
        if not (p/'complete.json').exists():raise ValueError('Cannot merge unfinished shard')
        read=lambda name:[json.loads(l) for l in (p/name).read_text().splitlines()]
        ep=read('episodes.jsonl');accepted={e['episode_id'] for e in ep};episodes.extend(ep)
        matches.extend(e for e in json.loads((p/'manifest.json').read_text())['matches'] if e['episode_id'] in accepted)
        part=read('labels.jsonl')
        if any(r['episode_id'] not in accepted for r in part):raise ValueError('Incomplete episode in completed shard')
        for r in part:
            os.link(p/r['image'],output/r['image'])
        rows.extend(part);receipts.extend(read('pairing.jsonl'))
        events.extend(read('evaluation_only/events.jsonl'));truth.extend(read('evaluation_only/truth.jsonl'))
    for entry in matches:entry['split']=split(entry['seed'])
    roles={e['episode_id']:e['split'] for e in matches}
    for row in rows:row['split']=roles[row['episode_id']]
    for episode in episodes:episode['split']=roles[episode['episode_id']]
    if not 10000<=len(rows)<=20000:raise ValueError(f'Data scale gate failed: {len(rows)} frames')
    for name,data in [('labels.jsonl',rows),('pairing.jsonl',receipts),('episodes.jsonl',episodes),
                      ('evaluation_only/events.jsonl',events),('evaluation_only/truth.jsonl',truth)]:
        (output/name).write_text(''.join(json.dumps(r,separators=(',',':'))+'\n' for r in data))
    manifest=json.loads((V1/'dataset/manifest.json').read_text());manifest['matches']=matches
    manifest['shards']=['dataset','dataset-second2'];manifest['frames']=len(rows)
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (output/'complete.json').write_text(json.dumps(dict(status='complete',frames=len(rows),matches=len(matches)))+'\n')
    progress(f'Merged {len(rows)} frames from {len(matches)} episodes using hardlinks; no duplicated JPEG bytes')
    return output


def main():
    plan=json.loads((V1/'collection-plan.json').read_text())
    for name,pid in [('dataset',plan['primary_collector_pid']),('dataset-second2',plan['secondary_collector_pid'])]:
        while not (V1/name/'complete.json').exists():
            if shutil.disk_usage(V1).free<10*1024**3:raise RuntimeError('Free disk below v1 10 GiB stop floor')
            check=subprocess.run(['ps','-p',str(pid),'-o','command='],capture_output=True,text=True)
            if check.returncode or 'collect_l1_rendered.py' not in check.stdout:
                raise RuntimeError(f'Owned collector {pid} ended without complete.json')
            time.sleep(15)
    dataset=merge()
    run('audit',['scripts/audit_l1_dataset.py',dataset])
    stop_owned(V1/'emulator-second')
    run('stream-benchmark',['scripts/benchmark_l1_stream.py','--ownership',V1/'emulator-grpc-auth2/complete.json',
                           '--dataset',dataset,'--proto',V1/'grpc','--output',V1/'stream-timing.json'])
    stop_owned(V1/'emulator-grpc-auth2')
    # Allow emulator shutdown to release its memory before MPS allocation.
    time.sleep(5)
    sources=[*sorted((ROOT/'src/clasher/vision').glob('*.py')),*sorted((ROOT/'scripts').glob('*l1*.py'))]
    (V1/'producer-sources.json').write_text(json.dumps({str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},indent=2)+'\n')
    with zipfile.ZipFile(V1/'producer-sources.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for p in sources:archive.write(p,p.relative_to(ROOT))
    run('train',['scripts/train_l1_perception.py','--dataset',dataset,'--output',V1/'model','--epochs',6,
                 '--imgsz',640,'--batch',16,'--v1-augmentation','--initialize',REPORT/'model/detector/weights/best.pt'])
    run('infer',['scripts/infer_l1_perception.py','--inputs',dataset/'heldout-inputs.jsonl','--image-root',dataset,
                 '--model',V1/'model/detector/weights/best.pt','--hud',V1/'model/hud.npz',
                 '--calibration',REPORT/'calibration.json','--output',V1/'inference','--v1','--imgsz',640,'--hp-model',V1])
    run('evaluate',['scripts/evaluate_l1_v1.py','--dataset',dataset,'--predictions',V1/'inference/frames.jsonl',
                    '--prior',V1/'public-deck-prior.json','--output',V1/'evaluation'])
    run('report',['scripts/report_l1_v1.py'])
    (V1/'complete.json').write_text(json.dumps(dict(status='complete',at=time.time()))+'\n')
    progress('Collection, audit, training, inference, evaluation, stream benchmark and RESULTS-v1.md completed. Final verification still required.')


if __name__=='__main__':
    try:main()
    except BaseException as e:
        (V1/'pipeline-failure.json').write_text(json.dumps(dict(error=str(e),traceback=traceback.format_exc(),at=time.time()),indent=2)+'\n')
        progress('Pipeline stopped: '+str(e))
        raise
