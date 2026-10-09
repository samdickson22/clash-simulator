"""Stop a specified task shard only after verifying its argv and descendants."""
import json
import os
from pathlib import Path
import signal
import sys
import time

base=Path('/mpac/sdicks02/repos/clasher-lease')
label=sys.argv[1]
if not label.startswith('cpu-delay-fixes-'):
    raise ValueError('task label required')
state=json.loads((base/'jobs'/f'{label}.state.json').read_text())
pid=state['pid']
argv=Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0')
if b'clasher.analysis.loss_review.delay_simulate' not in argv:
    raise ValueError('not our simulation process')
if not any(a.startswith(bytes(str(base/'delay-fixes-runtime'), 'utf8')) for a in argv):
    raise ValueError('not our isolated runtime')
def descendants(parent):
    children=[int(x) for x in Path(f'/proc/{parent}/task/{parent}/children').read_text().split()]
    result=[]
    for child in children:
        result.extend(descendants(child)); result.append(child)
    return result
pids=descendants(pid)+[pid]
cpu=0.
for target in pids:
    fields=Path(f'/proc/{target}/stat').read_text().rsplit(')',1)[1].split()
    cpu+=(int(fields[11])+int(fields[12]))/os.sysconf('SC_CLK_TCK')
out_arg=argv[argv.index(b'--out')+1].decode()
completed_cpu=sum(json.loads(p.read_text())['cpu_seconds'] for p in Path(out_arg).glob('games/*.json'))
receipt=dict(completed_game_cpu_seconds=completed_cpu,estimated_unfinished_and_initialization_cpu_seconds=max(0.,cpu-completed_cpu),label=label,utc=time.time(),verified_main_pid=pid,verified_descendants=pids[:-1],
             observed_process_cpu_seconds=cpu,reason='restart stalled GPU guard with one qualifying resume sample; same schedule')
out=base/'delay-fixes-runtime/reports/explore/delay-fixes/receipts'
out.mkdir(parents=True,exist_ok=True)
(out/f'{label}.technical-stop.json').write_text(json.dumps(receipt,indent=2)+'\n')
for target in pids:
    try:
        os.kill(target,signal.SIGCONT)
        os.kill(target,signal.SIGTERM)
    except ProcessLookupError:
        pass
print(json.dumps(receipt))
