"""Exact coordinator-approved idle service identities and per-block CPU meter."""
import argparse,hashlib,json,os,socket
from pathlib import Path
from common import plan,read,write,utc,sha
SERVICE_PIDS={'127x03':2180947,'127x08':3550685}

def identity(row):return {k:row[k] for k in ('pid','ppid','pgid','start_ticks','cmdline_sha256','uid')}
def matches(row,pin):return all(row.get(k)==v for k,v in pin.items())
def pins(j):return read(j/'idle-services.json')['services'] if (j/'idle-services.json').exists() else []

def member(row,rows,j):
 bypid={r['pid']:r for r in rows}
 for service in pins(j):
  for pin in service['wrapper_trio']:
   if matches(row,pin):return True
  root=service['service'];live=bypid.get(root['pid'])
  if live is None or not matches(live,root):continue
  ancestor=row
  for _ in range(16):
   ancestor=bypid.get(ancestor['ppid'])
   if ancestor is None:break
   if ancestor['pid']==live['pid']:return True
 return False

def begin(j,rows):
 bypid={r['pid']:r for r in rows};meters=[]
 for service in pins(j):
  pin=service['service'];r=bypid.get(pin['pid'])
  cpu=r['cpu_ticks'] if r and matches(r,pin) else 0
  meters.append(dict(name=service['name'],pin=pin,start_cpu_ticks=cpu,last_cpu_ticks=cpu,new_children=[],retired=r is None))
 return meters

def update(meters,rows):
 bypid={r['pid']:r for r in rows}
 for m in meters:
  pin=m['pin'];r=bypid.get(pin['pid'])
  if r is None:m['retired']=True;continue
  if not matches(r,pin):raise RuntimeError('idle service identity changed')
  m['last_cpu_ticks']=r['cpu_ticks']
  for child in rows:
   ancestor=child
   for _ in range(16):
    ancestor=bypid.get(ancestor['ppid'])
    if ancestor is None:break
    if ancestor['pid']==r['pid']:
     key=dict(pid=child['pid'],start_ticks=child['start_ticks'],cmdline_sha256=child['cmdline_sha256'])
     if key not in m['new_children']:m['new_children'].append(key)
     break

def finish(meters,elapsed):
 hz=os.sysconf('SC_CLK_TCK');records=[]
 for m in meters:
  seconds=max(0,m['last_cpu_ticks']-m['start_cpu_ticks'])/hz;fraction=seconds/max(elapsed,.001)
  records.append(dict(name=m['name'],service=m['pin'],cpu_seconds=seconds,block_seconds=elapsed,core_fraction=fraction,new_children=m['new_children'],retired=m['retired'],interfered=fraction>.01 or bool(m['new_children'])))
 return dict(services=records,interfered=any(r['interfered'] for r in records))

def main():
 from host_audit import processes
 p=argparse.ArgumentParser();p.add_argument('--job',type=Path,required=True);a=p.parse_args();j=a.job;host=socket.gethostname();assert host in SERVICE_PIDS
 target=j/'idle-services.json';assert not target.exists(),'admission identities cannot be silently refreshed'
 rows=processes();byid={r['pid']:r for r in rows};r=byid[SERVICE_PIDS[host]]
 assert 'validation_cache_service_renewal_v4.py' in r['cmd']
 process=[r];parent=byid[r['ppid']];assert Path(parent['cmd'].split()[0]).name=='time';process.append(parent)
 wrapper=byid[parent['ppid']];assert Path(wrapper['cmd'].split()[0]).name=='bash' and 'fleet_run.sh --worker v4-validation-cache-renewed-20261010-' in wrapper['cmd'];process.append(wrapper)
 assert len({r['pgid'] for r in process})==1
 name='v4-validation-cache-renewed-20261010-'+('03r1' if host=='127x03' else '08r1');prefix=Path('/mpac/sdicks02/jobs/clasher')/name
 write(target,dict(utc=utc(),host=host,coordinator_ruling='2026-10-10 14:35Z user instruction',services=[dict(name=name,service=identity(r),wrapper_trio=[identity(x) for x in process],wrapper_artifacts={str(prefix)+s:sha(str(prefix)+s) for s in ('.pid','.ready.json','.token')},commands=[x['cmd'] for x in process],idle_cpu_threshold=.01,new_children_always_flag=True)]))
 print(json.dumps(dict(utc=utc(),host=host,service_pid=r['pid'],wrapper_pgids=[x['pgid'] for x in process],pinned=True)))
if __name__=='__main__':main()
