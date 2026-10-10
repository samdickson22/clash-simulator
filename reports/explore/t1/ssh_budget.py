"""OP-4 metering with OP-6 caps only for source-proven LAN SSH families."""
import ipaddress,json,os,time,math
from fractions import Fraction
from common import utc
from cpu_accounting import Accounting
from ssh_transport import authenticated
from idle_services import member as idle_member
UID=3822945
AVERAGE_STOP_MIN_SECONDS=60
LAN=ipaddress.ip_network('129.65.221.0/24')

def identity(r):return tuple(r[k] for k in ('pid','start_ticks','uid','cmdline_sha256'))
def generation(r):return (r['pid'],r['start_ticks'])
def lan_connection(value):
 try:
  parts=value.split();return len(parts)==4 and parts[3]=='22' and ipaddress.ip_address(parts[0]) in LAN
 except (AttributeError,ValueError):return False

def ancestor(row,rows):
 bypid={r['pid']:r for r in rows};seen=set()
 for _ in range(64):
  if row['pid'] in seen:return None
  seen.add(row['pid'])
  if authenticated(row) and row['uid']==UID:return row
  row=bypid.get(row['ppid'])
  if row is None:return None
 return None

class Families:
 def __init__(self):self.sources={}
 def apply(self,rows,j):
  for r in rows:
   r.pop('ssh_budget',None)
   if r.get('allowlist_kind')=='ssh_family_budget':r.pop('allowlist_kind',None)
  roots={identity(r):r for r in rows if authenticated(r) and r['uid']==UID}
  self.sources={k:v for k,v in self.sources.items() if k[0]==str(j) and k[1] in roots}
  observed={}
  for r in rows:
   value=r.get('ssh_connection_snapshot')
   if not value:continue
   parent=ancestor(r,rows)
   if parent is None:continue
   key=identity(parent)
   if r is not parent and r.get('ssh_family_parent_snapshot',r.get('ssh_parent_snapshot'))!=list(key):continue
   observed.setdefault(key,set()).add(value)
  for key,values in observed.items():
   # Conflicting source evidence fails back to the identity layer.
   cache_key=(str(j),key);value=next(iter(values)) if len(values)==1 else None
   if cache_key not in self.sources:self.sources[cache_key]=value
   elif self.sources[cache_key]!=value:self.sources[cache_key]=None # conflict persists for this parent generation
  for r in rows:
   parent=ancestor(r,rows);source=self.sources.get((str(j),identity(parent))) if parent else None
   idle=idle_member(r,rows,j)
   if idle or lan_connection(source):
    r['ssh_budget']=dict(source=source,parent_identity=list(identity(parent)) if parent else None,approved_idle_service=idle)
    r['allowlist_kind']='ssh_family_budget';r.pop('op2_denied',None)
  return rows

FAMILIES=Families()

def total_ticks(r):return r['cpu_ticks']+r.get('child_cpu_ticks',0)

def proven(r):return lan_connection(r.get('ssh_budget',{}).get('source'))

def sample(before,after,elapsed,hz=None,accounting=None):
 hz=hz or os.sysconf('SC_CLK_TCK')
 now=time.clock_gettime(time.CLOCK_BOOTTIME)
 born=math.floor((now-elapsed)*hz)
 accounting=accounting or Accounting(before,born,'ssh_budget',sample_baseline=True)
 deltas=accounting.update(after);split=dict(source_proven_cpu_ticks=0,idle_cpu_ticks=0)
 for r in after:
  if r.get('ssh_budget'):split['source_proven_cpu_ticks' if proven(r) else 'idle_cpu_ticks']+=deltas[generation(r)]
 ticks=sum(split.values());denom=hz*Fraction(str(max(elapsed,.001)))
 return dict(cpu_ticks=ticks,seconds=elapsed,core_fraction=ticks/hz/max(elapsed,.001),**split,stop=Fraction(split['source_proven_cpu_ticks'])*2>denom*3 or Fraction(split['idle_cpu_ticks'])*4>denom)

def begin(rows,clock=time.monotonic,hz=None):
 hz=hz or os.sysconf('SC_CLK_TCK');born=math.floor(time.clock_gettime(time.CLOCK_BOOTTIME)*hz)
 return dict(started=clock(),hz=hz,born_since_ticks=born,last={generation(r):total_ticks(r) for r in rows},accounting=Accounting(rows,born,'ssh_budget'),cpu_ticks=0,source_proven_cpu_ticks=0,idle_cpu_ticks=0,processes={})

def update(meter,rows):
 deltas=meter['accounting'].update(rows)
 children={}
 for r in rows:children.setdefault(r['ppid'],[]).append(r)
 for r in rows:
  if not r.get('ssh_budget'):continue
  delta=deltas[generation(r)];meter['cpu_ticks']+=delta
  meter['source_proven_cpu_ticks' if proven(r) else 'idle_cpu_ticks']+=delta
  key=identity(r);record=meter['processes'].setdefault(key,dict(pid=r['pid'],start_ticks=r['start_ticks'],uid=r['uid'],cmdline_sha256=r['cmdline_sha256'],cmd=r['cmd'],cpu_ticks=0,source=r['ssh_budget'],child_commands=[]))
  record['cpu_ticks']+=delta
  record['source_proven_cpu_ticks']=record.get('source_proven_cpu_ticks',0)+(delta if proven(r) else 0)
  record['observed_self_cpu_ticks']=r['cpu_ticks'];record['observed_reaped_child_cpu_ticks']=r.get('child_cpu_ticks',0)
  for child in children.get(r['pid'],[]):
   value=dict(pid=child['pid'],start_ticks=child['start_ticks'],cmdline_sha256=child['cmdline_sha256'],cmd=child['cmd'])
   if value not in record['child_commands']:record['child_commands'].append(value)
 meter['last']={generation(r):total_ticks(r) for r in rows}

def finish(meter,elapsed):
 ticks=meter['cpu_ticks'];hz=meter['hz'];denom=hz*Fraction(str(max(elapsed,.001)))
 records=[dict(r,cpu_seconds=r['cpu_ticks']/hz) for r in meter['processes'].values()]
 # Older serialized meters have no split: retain their original tighter caps.
 proven_ticks=meter.get('source_proven_cpu_ticks',0);idle_ticks=meter.get('idle_cpu_ticks',ticks)
 assert proven_ticks+idle_ticks==ticks
 return dict(cpu_ticks=ticks,cpu_seconds=ticks/hz,clock_ticks_per_second=hz,block_seconds=elapsed,core_fraction=ticks/hz/max(elapsed,.001),source_proven_cpu_ticks=proven_ticks,idle_cpu_ticks=idle_ticks,ssh_flagged=Fraction(proven_ticks)*200>denom,interfered=Fraction(ticks)*200>denom,stop=elapsed>=AVERAGE_STOP_MIN_SECONDS and (Fraction(proven_ticks)*10>denom or Fraction(idle_ticks)*50>denom),average_stop_min_seconds=AVERAGE_STOP_MIN_SECONDS,operational_rule='OP-6',cpu_accounting_rule='OP-7-observed-child-credit-v1',processes=records)

def stop_reason(console,foreign,foreign_active,sample_result,block_results):
 if console['positive']:return 'console_user'
 if foreign:return 'foreign_compute'
 if foreign_active:return 'foreign_active'
 if sample_result['stop']:return 'ssh_family_sample_budget'
 if any(r['stop'] for r in block_results):return 'ssh_family_average_budget'
 return None

def record(j,rows,block_ids):
 family=[r for r in rows if r.get('ssh_budget') or ancestor(r,rows) is not None or idle_member(r,rows,j)]
 if not family:return
 receipt=dict(utc=utc(),block_ids=list(block_ids),processes=[dict(pid=r['pid'],start_ticks=r['start_ticks'],cmdline_sha256=r['cmdline_sha256'],cmd=r['cmd'],cpu_ticks=r['cpu_ticks'],reaped_child_cpu_ticks=r.get('child_cpu_ticks',0),budgeted=bool(r.get('ssh_budget')),captured_source=r.get('ssh_connection_snapshot'),parent_identity=list(identity(ancestor(r,rows))) if ancestor(r,rows) else None,source=r.get('ssh_budget'),child_commands=[dict(pid=c['pid'],start_ticks=c['start_ticks'],cmdline_sha256=c['cmdline_sha256'],cmd=c['cmd']) for c in rows if c['ppid']==r['pid']]) for r in family])
 with (j/'ssh-family-occurrences.jsonl').open('a') as f:f.write(json.dumps(receipt)+'\n')
