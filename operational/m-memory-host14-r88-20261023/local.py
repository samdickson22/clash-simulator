import sys
if sys.flags.optimize:raise RuntimeError('R64 requires optimization 0')
sys.dont_write_bytecode=True
import hashlib
from pathlib import Path
R64_GATE_BYTES=(Path(__file__).resolve().parent/'gate.py').read_bytes()
if hashlib.sha256(R64_GATE_BYTES).hexdigest()!='70cc719588df2cf3be9ea7de0b972d84ef8a2bb90be8350020e44314d503564e':raise RuntimeError('R64 gate pin mismatch')
exec(compile(R64_GATE_BYTES,'gate.py','exec'))
R64_DISK('local.py',__file__)
import os,sys,json,hashlib,base64,subprocess,time,signal,selectors,shlex
from pathlib import Path
import socket
assert socket.gethostname().split('.')[0]=='127x05','global dispatch must originate on host05'
B=Path(__file__).resolve().parent;host=sys.argv[1];assert host=='127x14'
pins=json.loads((B/'package-pins.json').read_bytes())
for n,h in pins['helpers'].items():assert hashlib.sha256((B/n).read_bytes()).hexdigest()==h
payload=(B/'payload.b64').read_text();assert hashlib.sha256(payload.encode()).hexdigest()==pins['payload_sha256']
R77_ARGUMENTS(R64_CONTEXT,payload)
code=R64_BOOT('controller.py',R64_CONTEXT,payload)
# This permanent global dispatch intent is created before any SSH, and is never removed or retried.
R64_INTENT(R64_CONTEXT)
out=B.parent/'dispatch'/host;out.parent.mkdir(exist_ok=True);out.mkdir(exist_ok=False)
# The remote controller enters the existing R37 state root, so R37 classifies it as clasher; -I keeps that cwd off sys.path.
cmd=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=12','-o','ConnectionAttempts=1','-o','ServerAliveInterval=5','-o','ServerAliveCountMax=2','-o','ControlMaster=no','-o','ControlPath=none','-o','StrictHostKeyChecking=yes',host,'cd /mpac/sdicks02/jobs/clasher/lease-20261022 && exec taskset -c 0-31 nice -n 15 /bin/python3 -I -B -']
start=time.monotonic();final=None;error=None;captured=[];rc=None
# One bounded SSH, no retry. Codes: controller 0/10-15 pass through; 21 local/SSH deadline or error; 22 no final event;
# 23 final event failed or inconsistent with the SSH status.
with (out/'ssh.stderr').open('xb') as err,(out/'events.jsonl').open('x',buffering=1) as events:
 p=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,text=True)
 def expired(*_):raise TimeoutError('bounded SSH 1600s deadline')
 signal.signal(signal.SIGALRM,expired);signal.alarm(1600)
 try:
  p.stdin.write(code);p.stdin.close()
  for line in p.stdout:
   try:event=json.loads(line)
   except ValueError:events.write(json.dumps({'event':'raw','line':line})+'\n');continue
   if event.get('event')=='artifact':
    name=Path(event['name']);assert not name.is_absolute() and '..' not in name.parts
    dest=out/'artifacts'/name;dest.parent.mkdir(parents=True,exist_ok=True)
    data=base64.b64decode(event['data'])
    with dest.open('xb') as f:f.write(data)
    captured.append([str(name),hashlib.sha256(data).hexdigest()])
   else:
    if event.get('event')=='final':final=event
    events.write(line);print(line.strip(),flush=True)
  rc=p.wait(timeout=10)
 except BaseException as ex:error=repr(ex)
 finally:
  signal.alarm(0)
  if p.poll() is None:
   p.terminate()
   try:p.wait(timeout=5)
   except subprocess.TimeoutExpired:p.kill();p.wait(timeout=5)
status=21 if error else 22 if final is None else rc if rc and rc==final.get('code') else 23 if rc!=final.get('code') or final.get('status')!='pass' else 0
(out/'ssh-exit.json').write_text(json.dumps(dict(returncode=p.returncode,error=error,elapsed=time.monotonic()-start,final_status=final and final.get('status'),final_code=final and final.get('code'),local_status=status,artifacts=captured),indent=2,sort_keys=True)+'\n')
print(json.dumps({'event':'local_result','host':host,'status':'pass' if status==0 else 'failed','code':status}),flush=True)
sys.exit(status)
