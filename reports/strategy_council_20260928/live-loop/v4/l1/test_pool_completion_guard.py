"""Pool producer format rejection tests; synthetic metadata only."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
from formal_guard import digest,pool_completion


def main(root):
    root.mkdir();checks=0
    def put(name,value): (root/name).write_text(json.dumps(value))
    state=dict(started=100,claims={},draining=False,stop_reason='heldout count coverage reached',last_completion={'time':200})
    stats=dict(matches=641,hub_verified_matches=641,heldout_matches=64,heldout_opponent_events=1520,fps_pass_matches=638,emulator_hours=15.5)
    put('pool-state.json',state);put('phase-a-results.json',dict(status={'phase_a':stats}))
    for name,value in [('T1-PROGRESS.md','complete'),('pool-events.jsonl','{}\n'),
                       ('pool-phase-a-20261007-retry2-once.exit','0\n'),('mac-processes-after-stop.txt',' 0\n')]:
        (root/name).write_text(value)
    proof=dict(schema='clasher.t1.phase-a-completion.coordinator-mirror.v1',created_utc='1970-01-01T00:05:00Z',
               stop_reason=state['stop_reason'],pool_exit='0',mac_qemu_or_pool_processes_now=0,coverage_met=True,
               **stats,sha256={p.name:digest(p) for p in root.iterdir()})
    path=root/'T1-PHASE-A-COMPLETE.json';put(path.name,proof)
    def run():return pool_completion(root/'pool-state.json',path)
    def refuse():
        nonlocal checks
        try:run()
        except ValueError:checks+=1
        else:raise AssertionError('Invalid completion accepted')
    assert run()['mode']=='pool-coordinator-mirror';checks+=1
    for key,value in [('pool_exit','1'),('mac_qemu_or_pool_processes_now',1),('mac_qemu_or_pool_processes_now',False),
                      ('coverage_met',False),('stop_reason','signal'),('matches',640),('created_utc','1970-01-01T00:02:00Z')]:
        bad=deepcopy(proof);bad[key]=value;put(path.name,bad);refuse()
    put(path.name,proof)
    file=root/'pool-events.jsonl';original=file.read_bytes();file.write_bytes(original+b'changed');refuse();file.write_bytes(original)
    for key,value in [('claims',{'renderer':'active'}),('draining',True),('stop_reason',None)]:
        bad=deepcopy(state);bad[key]=value;put('pool-state.json',bad)
        updated=deepcopy(proof);updated['sha256']['pool-state.json']=digest(root/'pool-state.json');put(path.name,updated);refuse()
    put('pool-state.json',state);put(path.name,proof)
    print(json.dumps(dict(checks=checks,passed=True,scope='synthetic producer metadata only')))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);main(p.parse_args().output)
