"""Continue only this task's collector at completed or empty-warmup boundaries."""
import argparse
import json
from pathlib import Path
import subprocess
import time

from collect_l1_rendered import REPORT,append,progress
from certify_l1_timing_v3 import verify_owner
from smoke_reference_battle import request


def running(pid):
    p=subprocess.run(['ps','-p',str(pid),'-o','stat=,command='],capture_output=True,text=True)
    if p.returncode or not p.stdout.strip() or p.stdout.lstrip().startswith('Z'):return False
    if 'scripts/collect_l1_stream_v3.py' not in p.stdout:raise ValueError('Collector PID changed identity')
    return True


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--pid',type=int,required=True)
    p.add_argument('--shard',type=int,required=True);p.add_argument('--ownership',type=Path,required=True)
    a=p.parse_args();root=REPORT/'v3';deadline=time.monotonic()+10800
    while running(a.pid):
        if time.monotonic()>deadline:raise TimeoutError('Owned collection wait expired')
        time.sleep(5)
    receipt=json.loads(a.ownership.read_text());verify_owner(receipt)
    for label in ('dataset','dataset-extra'):
        data=root/label
        if (data/f'complete-{a.shard}.json').exists():continue
        manifest=json.loads((data/'manifest.json').read_text())
        done_path=data/f'episodes-{a.shard}.jsonl'
        done={json.loads(l)['episode_id'] for l in done_path.read_text().splitlines()} if done_path.exists() else set()
        for i,entry in enumerate(manifest['matches']):
            if i%2!=a.shard or entry['episode_id'] in done:continue
            partial=data/'evaluation_only'/entry['episode_id']
            if partial.exists():
                if (partial/'frames.jsonl').exists() or (data/'videos'/f"{entry['episode_id']}.mp4").exists():
                    raise ValueError('Partial recorded episode requires explicit audit; refusing automatic replay')
                request(receipt['probe_port'],'pause')
                partial.rename(root/f"rejected-empty-{label}-{entry['episode_id']}-{time.time_ns()}")
                progress(f"v3 preserved empty warmup for {entry['episode_id']}; resuming the same frozen episode.")
        command=[str(REPORT.parents[3]/'.venv/bin/python'),'-u','scripts/collect_l1_stream_v3.py',
            '--ownership',str(a.ownership),'--output',str(data),'--shard',str(a.shard),'--shards','2']
        if label=='dataset-extra':command.extend(['--adaptive-minimum','3000'])
        with (root/f'continuation-{label}-{a.shard}.log').open('w') as log:
            child=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
            append(root/'continuation-processes.jsonl',dict(pid=child.pid,shard=a.shard,dataset=label,command=command))
            if child.wait():raise RuntimeError(f'{label} shard {a.shard} failed; evidence preserved')
    (root/f'collection-complete-{a.shard}.json').write_text(json.dumps(dict(status='complete',shard=a.shard))+'\n')
    progress(f'v3 shard {a.shard} finished both frozen collection plans; emulator remains owned and paused.')


if __name__=='__main__':main()
