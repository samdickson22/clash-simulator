"""One exclusive host, five-core slots, one-second stop census, sealed logs."""
import argparse,json,os,resource,signal,socket,subprocess,time
from pathlib import Path
from collections import Counter
import system_bus
import ssh_budget
from common import utc,read,write,sha,plan
from host_audit import admission,processes,census,console,memory
from pin import verify
from idle_services import begin as idle_begin,update as idle_update,finish as idle_finish


def stop_children(active):
 # Only groups created by this supervisor; never pattern-based signals.
 for r in active.values():
  child=r['process']
  if child.poll() is None:
   try:os.killpg(child.pid,signal.SIGTERM)
   except ProcessLookupError:pass

def main():
 p=argparse.ArgumentParser();p.add_argument('--job',type=Path,required=True);p.add_argument('--dispatch',type=Path,required=True);p.add_argument('--attempt');p.add_argument('--phase',choices=['smoke','reporting','replacement','corpus'],required=True);a=p.parse_args();j=a.job;cfg=plan();host=socket.gethostname();hc=cfg['compute']['hosts'][host]
 assert os.sched_getaffinity(0)=={hc['supervisor_cpu']};assert os.getpriority(os.PRIO_PROCESS,0)==10 and os.sched_getscheduler(0)==os.SCHED_OTHER
 from owned_supervisor import pin as pin_supervisor,add_worker
 pin_supervisor(j,processes(),a.phase)
 r=admission(j);write(j/f'host-admission-{a.phase}.json',r);assert r['admitted']
 for tag in ('TESTS-PASS','QUALIFIED','BELIEF-QUALIFIED'):assert (j/tag).exists(),tag
 if a.phase not in ('smoke','corpus'):
  from barrier import reporting_release
  m=reporting_release(j/'repo',j/'FROZEN-T1.json',j/'REPORTING-AUTHORIZATION.json')
  assert host in m['qualified_hosts'] and (j/'SMOKE-PASS').exists()
 verify(j)
 rows=[x for x in read(a.dispatch)['blocks'] if x['host']==host]
 assert rows and len({x['id'] for x in rows})==len(rows)
 assert (a.phase=='replacement')==bool(a.attempt),'replacement rounds need distinct attempt names'
 if a.attempt:
  import re
  assert re.fullmatch(r'r[0-9]+',a.attempt)
 out=j/(a.phase+'-'+a.attempt if a.attempt else a.phase);out.mkdir(exist_ok=True);claim=out/'launch-claim';claim.mkdir() # No automatic re-launch, even after a crash.
 slots=cfg['compute']['console_slots'] if r['console']['positive'] else cfg['compute']['slots'];active={};done=[];failures=[];idx=0;reason=None;interrupted=False;overload=0.;before=processes();last=time.monotonic();t=last
 def caught(sig,frame):
  nonlocal interrupted
  interrupted=True;stop_children(active)
 signal.signal(signal.SIGTERM,caught);signal.signal(signal.SIGINT,caught)
 launch=dict(utc=utc(),host=host,phase=a.phase,slots=slots,who=r['console']['who'],runtime_pin_sha256=sha(j/'runtime-pin.json'),dispatch_sha256=sha(a.dispatch),supervisor_pid=os.getpid(),supervisor_pgid=os.getpgrp())
 write(out/'launch.json',launch)
 while idx<len(rows) or active:
  now=time.monotonic();after,foreign,foreign_active,foreign_cpu=census(j,before,block_ids=[r['descriptor']['id'] for r in active.values()]);sample_now=time.monotonic();dt=max(sample_now-last,.001);last=sample_now;ssh_sample=ssh_budget.sample(before,after,dt);before=after
  for live in active.values():
   idle_update(live['idle_meter'],after);system_bus.update(live['system_bus_meter'],after)
   ssh_budget.update(live['ssh_meter'],after)
   live['allowlist_counts'].update(r['allowlist_kind'] for r in after if r.get('allowlist_kind'))
  c=console();overload=overload+dt if c['positive'] and foreign_cpu/dt>1 else 0.
  # Console activity below the registered one-core threshold is recorded. Other jobs are disallowed immediately.
  foreign_jobs=[x for x in foreign if not (c['positive'] and x.get('tty',0))]
  foreign_jobs_active=[x for x in foreign_active if not (c['positive'] and x.get('tty',0))]
  budget_reason=ssh_budget.stop_reason(c,foreign_jobs,foreign_jobs_active,ssh_sample,[ssh_budget.finish(r['ssh_meter'],time.monotonic()-r['started']) for r in active.values()])
  reason=('signal' if interrupted else 'owned_STOP' if (j/'STOP').exists() or (j/f'STOP-{host}').exists() else 'memory_floor' if memory()<24*2**30 else budget_reason)
  unacked=[x for pattern in ('reporting/*/complete.json','replacement-r*/*/complete.json') for x in j.glob(pattern) if host!='127x01' and not (x.parent/'hub-ack.json').exists() and time.time()-x.stat().st_mtime>1800]
  if unacked:reason='offhost_copy_over_30min'
  if reason:write(out/'stop-reason.json',dict(utc=utc(),reason=reason,foreign=foreign,foreign_active=foreign_active,console=c,ssh_family_sample=ssh_sample));stop_children(active)
  for slot,row in list(active.items()):
   child=row['process'];rc=child.poll()
   if rc is None:continue
   row['log'].close();folder=out/row['descriptor']['id'];good=rc==0 and (folder/'local-complete.json').exists()
   elapsed=time.monotonic()-row['started'];interference=idle_finish(row['idle_meter'],elapsed)
   interference['ssh_family']=ssh_budget.finish(row['ssh_meter'],elapsed)
   interference['ssh_flagged']=interference['ssh_family']['ssh_flagged']
   interference['interfered']|=interference['ssh_family']['interfered']
   interference['system_dbus']=system_bus.finish(row['system_bus_meter'],elapsed)
   interference['interfered']|=interference['system_dbus']['interfered']
   interference['allowlist_observations']=dict(row['allowlist_counts'])
   write(folder/'interference.json',dict(utc=utc(),descriptor=row['descriptor'],**interference))
   if good:
    proof=read(folder/'local-complete.json');proof['interference']=interference;proof['interference_sha256']=sha(folder/'interference.json');write(folder/'complete.json',proof)
    if host=='127x01' and a.phase!='corpus':
     hub=j/'hub-blocks';hub.mkdir(exist_ok=True);(hub/row['descriptor']['id']).symlink_to(folder)
   (done if good else failures).append(row['descriptor'])
   write(out/'exits'/f"{row['descriptor']['id']}.json",dict(utc=utc(),descriptor=row['descriptor'],pid=child.pid,pgid=child.pid,returncode=rc,complete=good,reason=reason,interference=interference))
   del active[slot]
  if reason:
   if not active:break
  else:
   for slot in range(slots):
    if slot in active or idx>=len(rows):continue
    desc=rows[idx];idx+=1;folder=out/desc['id'];assert not folder.exists(),'interrupted block cannot be reused'
    descfile=out/'descriptors'/f"{desc['id']}.json";write(descfile,desc)
    cores=hc['physical_cpus'][5*slot:5*slot+5];cmd=['taskset','-c',','.join(map(str,cores)),'bash',str(j/'repo/reports/explore/t1/runtime.sh'),'reports/explore/t1/corpus_game.py' if a.phase=='corpus' else 'reports/explore/t1/run.py','--block',str(descfile),'--out',str(folder),'--cores',','.join(map(str,cores))]
    if a.phase=='smoke':cmd.append('--smoke')
    log=(out/f"{desc['id']}.log").open('x');child=subprocess.Popen(cmd,stdout=log,stderr=log,start_new_session=True)
    add_worker(j,child.pid)
    ssh_rows=processes();ssh_meter=ssh_budget.begin(ssh_rows)
    active[slot]=dict(ssh_meter=ssh_meter,process=child,descriptor=desc,log=log,idle_meter=idle_begin(j,processes()),system_bus_meter=system_bus.begin(j,processes()),allowlist_counts=Counter(),started=time.monotonic())
    write(out/'pids'/f"{desc['id']}.json",dict(utc=utc(),pid=child.pid,pgid=child.pid,command=cmd,cores=cores,descriptor=desc))
  progress=dict(utc=utc(),host=host,phase=a.phase,complete_local_blocks=len(done),complete_local_games=(1 if a.phase=='corpus' else 8)*len(done),failed_blocks=len(failures),queued=len(rows)-idx,inflight=len(active),console=c,console_over_one_core_seconds=overload,memavailable_GiB=memory()/2**30,reason=reason,sealed=True)
  write(j/'progress.json',progress)
  with (out/'census.jsonl').open('a') as f:f.write(json.dumps(progress)+'\n')
  mhz=[];cpu=None
  for line in Path('/proc/cpuinfo').read_text().splitlines():
   if line.startswith('processor'):cpu=int(line.split(':',1)[1])
   elif line.startswith('cpu MHz') and cpu in hc['physical_cpus'][:5*slots]:mhz.append(dict(cpu=cpu,mhz=float(line.split(':',1)[1])))
  with (out/'mhz.jsonl').open('a') as f:f.write(json.dumps(dict(utc=progress['utc'],slots=slots,physical_core_mhz=mhz))+'\n')
  time.sleep(1)
 usage=resource.getrusage(resource.RUSAGE_CHILDREN);parent=resource.getrusage(resource.RUSAGE_SELF)
 write(out/'supervisor-exit.json',dict(utc=utc(),host=host,reason=reason,completed=done,failed=failures,unstarted=rows[idx:],wall_seconds=time.monotonic()-t,whole_tree_cpu_seconds=usage.ru_utime+usage.ru_stime+parent.ru_utime+parent.ru_stime))
 verify(j)
 if reason or failures:raise SystemExit(1)
if __name__=='__main__':main()
