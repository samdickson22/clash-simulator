"""Bounded metadata-only04 continuation; no runtime writes or extra connections."""
from pathlib import Path
import datetime, hashlib, json, os, socket, sys
J=Path('/mpac/sdicks02/jobs/clasher')
spool=J/'v4-a21-a2-build-launch-20261011-r1'
attempt=J/'v4-a19-a20-a21-verification-r1/a2-build-bounds-fd9d84e20edf4cb797147730ebcbfebe'
inv=attempt/'verification-0b82c5cb206d4559a3068ab88dcced9f'
sys.path.insert(0,str(J/'v4-a19-a20-a21-combined-r1/code'))
from a19_common import identity,live
import a19_resources as r
def pin(p,limit=16000000):
 if not p.exists():return None
 assert p.stat().st_size<=limit,str(p)
 b=p.read_bytes()
 return dict(path=str(p),sha256=hashlib.sha256(b).hexdigest(),text=b.decode())
def ident(w):
 out=dict(w,live=live(w))
 if out['live']:
  p=Path('/proc')/str(w['pid']); stat=p.joinpath('stat').read_text().rsplit(') ',1)[1].split()
  out.update(affinity=sorted(os.sched_getaffinity(w['pid'])),nice=os.getpriority(os.PRIO_PROCESS,w['pid']),cpu_ticks=int(stat[11])+int(stat[12]))
 return out
result=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),read_only=True,files={})
seeds=[];controls=[]
for name in ('supervisor','controller','observer'):
 w=json.loads((spool/(name+'-launch.json')).read_text())['identity'];controls.append(ident(w))
 if live(w):seeds.append(w)
result['controls']=controls
for name in ('observer-exit.json','observer-return.json','observer-failure.json','controller-exit.json','supervisor-complete.json','observer-request.json','observer.log'):
 result['files']['spool/'+name]=pin(spool/name)
for name in ('complete.json','failure.json','bounds-result.json','request-binding.json','STOP'):
 result['files']['attempt/'+name]=pin(attempt/name)
result['files']['bounds/complete.json']=pin(J/'v4-a1-body-seal-20261009-r4/state/bounds/complete.json')
result['workers']=[]
for folder in sorted((inv/'workers').glob('epoch-*')):
 f=folder/'launch.json'
 if not f.exists():continue
 launch=pin(f);w=json.loads(launch['text'])['identity']
 row=dict(epoch=folder.name,launch=launch,identity=ident(w),exit=pin(folder/'exit.json'),result=pin(folder/'result.json'))
 log=folder/'log'
 if log.exists():
  assert log.stat().st_size<8000000
  row['log']=pin(log,8000000)
 result['workers'].append(row)
result['invocation_metadata']={p.name:pin(p) for p in inv.glob('*.json') if p.name in ('complete.json','verified.json','pool-complete.json','reduce-result.json')}
net={}
def endpoint(s):
 ip,port=s.split(':');return dict(address=socket.inet_ntoa(bytes.fromhex(ip)[::-1]),port=int(port,16))
for line in Path('/proc/net/tcp').read_text().splitlines()[1:]:
 v=line.split()
 if v[3]=='01' and int(v[2].split(':')[1],16)==22:
  net[v[9]]=dict(local=endpoint(v[1]),remote=endpoint(v[2]),inode=v[9])
transports=[]
for p in Path('/proc').iterdir():
 if not p.name.isdigit():continue
 try:
  raw=(p/'cmdline').read_bytes();title=raw.replace(b'\0',b' ').decode(errors='replace').strip()
  if not (title.startswith('ssh: /mpac/sdicks02/jobs/clasher/') and '-a19-r5 [mux]' in title):continue
  w=identity(int(p.name));row=dict(identity=w,title=title,command_sha256=hashlib.sha256(raw).hexdigest(),affinity=sorted(os.sched_getaffinity(w['pid'])),sockets=[],fd_errors=[])
  try:
   for fd in (p/'fd').iterdir():
    try:
     target=os.readlink(fd)
     if target.startswith('socket:[') and target[8:-1] in net:row['sockets'].append(dict(fd=fd.name,**net[target[8:-1]]))
    except OSError as e:row['fd_errors'].append(dict(fd=fd.name,errno=e.errno))
  except OSError as e:row['fd_errors'].append(dict(errno=e.errno))
  row['identity_still_live']=live(w);transports.append(row);seeds.append(w)
 except (OSError,ValueError):continue
result['transports']=transports
result['transient_read_helpers']=[identity(os.getpid()),identity(os.getppid())]
seeds+=result['transient_read_helpers']
result['snapshot']=r.snapshot(seeds)
try:r.check_snapshot(result['snapshot']);result['resource_check']='PASS'
except Exception as e:result['resource_check']=repr(e)
result['08_reported_server_generation']={'pid':2995332,'starttime':'148086709','parent_pid':2995276,'parent_starttime':'148086679','candidate_client_local_port':41072,'source':'coordinator7139/T1 receipts; no08 inspection by this probe','server_pid_to_socket_join':'NOT_PROVEN_EACCES'}
result['end_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
print(json.dumps(result,sort_keys=True))
