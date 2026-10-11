"""OP-1: immutable system-bus admission identity and per-block CPU metering."""
import os,socket
from common import read,write,utc
COMMAND='/usr/bin/dbus-daemon --system --address=systemd: --nofork --nopidfile --systemd-activation --syslog-only'
KEYS=('pid','start_ticks','exe','cmdline_sha256','uid')
def identity(row):return {k:row[k] for k in KEYS}
def matches(row,pin):return all(row.get(k)==v for k,v in pin.items())
def pin(j,rows):
 target=j/'system-bus-admission.json'
 if target.exists():return read(target)['identity']
 candidates=[r for r in rows if r['uid']==103 and r['cmd']==COMMAND and r.get('exe')=='/usr/bin/dbus-daemon']
 assert len(candidates)==1,'exact system dbus admission identity required'
 r=identity(candidates[0]);write(target,dict(utc=utc(),host=socket.gethostname(),identity=r,exe_evidence=candidates[0]['exe_evidence'],coordinator_ruling='OP-1 14:45Z; exact PID/start/exe/cmd SHA; >1% core flags only'))
 return r
def member(row,j):
 target=j/'system-bus-admission.json'
 return target.exists() and matches(row,read(target)['identity'])
def begin(j,rows):
 pinned=read(j/'system-bus-admission.json')['identity'];r=next((r for r in rows if matches(r,pinned)),None)
 assert r is not None,'pinned system bus absent/changed at block entry'
 return dict(identity=pinned,start_cpu_ticks=r['cpu_ticks'],last_cpu_ticks=r['cpu_ticks'],retired=False)
def update(meter,rows):
 r=next((r for r in rows if matches(r,meter['identity'])),None)
 if r is None:meter['retired']=True
 else:meter['last_cpu_ticks']=r['cpu_ticks']
def finish(meter,elapsed):
 ticks=max(0,meter['last_cpu_ticks']-meter['start_cpu_ticks']);hz=os.sysconf('SC_CLK_TCK')
 # Integer tick comparison prevents a float boundary flag at exactly 1%.
 fraction=ticks/hz/max(elapsed,.001)
 return dict(identity=meter['identity'],cpu_ticks=ticks,cpu_seconds=ticks/hz,core_fraction=fraction,retired=meter['retired'],interfered=ticks*100>hz*max(elapsed,.001))
