import gzip,json,time,hashlib
from pathlib import Path
root=Path('/mpac/sdicks02/repos/clasher');base=root/'reports/explore/loss-review'
exit_file=Path('/mpac/sdicks02/jobs/clasher/loss-review-final-queue-smoke-v1.exit')
for _ in range(60):
    if exit_file.exists():break
    time.sleep(2)
else:raise RuntimeError('smoke timeout')
assert exit_file.read_text().strip()=='0'
results=[]
for delay in (0,27):
    name=f'sim-0000-d{delay}.json.gz'
    with gzip.open(base/'sim-smoke-v2/traces'/name,'rt') as f:old=json.load(f)
    with gzip.open(base/'final-queue-smoke-v1/traces'/name,'rt') as f:new=json.load(f)
    assert old['actions']==new['actions']
    assert old['globals']==new['globals'] and old['entities']==new['entities']
    assert len(new['queues'])==len(new['ticks'])
    assert all(len(q)==8 for q in new['queues'])
    results.append(dict(delay=delay,frames=len(new['ticks']),actions=len(new['actions']),
                        actions_unchanged=True,public_states_unchanged=True,queue_telemetry_complete=True))
(base/'final-telemetry-check.json').write_text(json.dumps(dict(passed=True,checks=results),indent=2)+'\n')
print(json.dumps(dict(passed=True,checks=results)))
