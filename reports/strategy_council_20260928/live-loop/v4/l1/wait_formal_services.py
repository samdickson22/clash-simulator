"""Bounded lease-supervised wait for fresh cache services, then the formal client."""
import json
from pathlib import Path
import re
import subprocess
import sys
import time


def main():
    # Forward only the existing formal-client CLI; it authenticates all inputs.
    args=sys.argv[1:]
    if args.count('--services')!=1:raise ValueError('One service plan required')
    plan=json.loads(Path(args[args.index('--services')+1]).read_text())
    remote=plan['remote']
    if len(remote)!=2 or {r['host'] for r in remote}!={'127x01','127x03'}:
        raise ValueError('Two approved home services required')
    for r in remote:
        if re.fullmatch(r'v4-cache-transport-server-[a-zA-Z0-9-]+',r['label']) is None:
            raise ValueError('Invalid service label')
    deadline=time.monotonic()+1800
    while time.monotonic()<deadline:
        states=[]
        for r in remote:
            code='''from pathlib import Path
import json
p=Path('/mpac/sdicks02/jobs/clasher')
n=LABEL
print(json.dumps(dict(ready=(p/(n+'.ready.json')).exists(),exited=(p/(n+'.exit')).exists())))
'''.replace('LABEL',repr(r['label']))
            response=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10',r['host'],'python3 -'],
                input=code,text=True,capture_output=True,check=True,timeout=20)
            state=json.loads(response.stdout)
            if state['exited']:raise RuntimeError('Cache service exited before formal start: '+r['label'])
            states.append(dict(host=r['host'],**state))
        print(json.dumps(dict(time=time.time(),services=states)),flush=True)
        if all(r['ready'] for r in states):
            raise SystemExit(subprocess.call([sys.executable,'-B',str(Path(__file__).with_name('formal_cache_client_v4.py')),*args]))
        time.sleep(30)
    raise TimeoutError('Cache services did not become ready within30 minutes')


if __name__=='__main__':main()
