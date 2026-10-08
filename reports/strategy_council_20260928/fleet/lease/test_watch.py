"""Run on the hub: real subprocesses, isolated fake leases, accelerated test deadlines."""
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

assert os.uname().nodename.split('.')[0] == '127x01'
source = Path(sys.argv[1])
base = Path(tempfile.mkdtemp(prefix='lease-watch-test-', dir='/mpac/sdicks02/jobs/clasher'))
runner = base / 'runner.py'
runner.write_text('''import importlib.util,sys
from pathlib import Path
spec=importlib.util.spec_from_file_location('watch',sys.argv.pop(1));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
m.BASE=Path(sys.argv.pop(1));m.HOST='127x11';m.LEASE=m.BASE/'lease.json'
m.CHECK_INTERVAL=.1;m.POLL_INTERVAL=.02;m.TERM_AFTER=.2;m.KILL_AFTER=.4
original=m.subprocess.check_output
def check(args,**kwargs):
 if args[0]=='nvidia-smi':return '48000\\n'
 if args[0]=='who':return ''
 return original(args,**kwargs)
m.subprocess.check_output=check
sys.exit(m.main())
''')
results = []
for case in ('success', 'refused', 'checkpoint', 'stubborn'):
    b = base / case; (b/'jobs').mkdir(parents=True)
    lease={'project':'clasher','coordinator_thread':'0523ae6f-baa3-4d4e-b233-b392671670db','expected_end_utc':'2099-01-01T00:00Z','max_workers':8,'gpu':True,'shared':True}
    if case == 'refused':lease['refused']=True
    (b/'lease.json').write_text(json.dumps(lease))
    if case in ('success','refused'):
        code="from pathlib import Path; Path('started').write_text('yes')"
    elif case == 'checkpoint':
        code="import signal,time,sys; from pathlib import Path; signal.signal(signal.SIGTERM,lambda *_:(Path('checkpoint').write_text('saved'),sys.exit(0))); Path('started').write_text('yes'); time.sleep(60)"
    else:
        code="import signal,time; from pathlib import Path; signal.signal(signal.SIGTERM,signal.SIG_IGN); Path('started').write_text('yes'); time.sleep(60)"
    proc=subprocess.Popen([sys.executable,str(runner),str(source),str(b),case,sys.executable,'-c',code],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    if case in ('checkpoint','stubborn'):
        deadline=time.monotonic()+5
        while not (b/'started').exists() and time.monotonic()<deadline:time.sleep(.02)
        assert (b/'started').exists()
        lease['reclaim']=True;(b/'lease.json').write_text(json.dumps(lease))
    output,_=proc.communicate(timeout=10)
    receipt=json.loads((b/'jobs'/f'{case}.exit.json').read_text())
    if case=='success':assert proc.returncode==0 and receipt['status']=='pass'
    if case=='refused':assert proc.returncode!=0 and not (b/'started').exists()
    if case=='checkpoint':assert (b/'checkpoint').read_text()=='saved' and not (b/'lease.json').exists()
    if case=='stubborn':assert receipt['exit_code']==-signal.SIGKILL and not (b/'lease.json').exists()
    if 'pid' in receipt:assert not Path('/proc',str(receipt['pid'])).exists()
    results.append({'case':case,'passed':True,'receipt':receipt})
(base/'results.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps({'passed':len(results),'directory':str(base)}))
