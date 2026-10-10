"""Mechanical blind host-loss inventory and cell-preserving replacement dispatch."""
import argparse
from pathlib import Path
from common import read,write,utc,plan,sha
from schedule import replacement,assign_hosts


def inventory(phases,dispatches,hub):
 losses=[];unstarted=[];seen=set();history=[]
 for dispatch in dispatches:history.extend(read(dispatch)['blocks'])
 for phase in phases:
  # A completed stop receipt, or coordinator-authenticated crash receipt, proves
  # the supervisor is dead before we classify its never-started queue.
  exitpath=phase/'supervisor-exit.json'
  if not exitpath.exists():
   exitpath=phase/'HOST-LOSS.json';r=read(exitpath)
   from barrier import COORDINATOR
   assert r['coordinator_thread']==COORDINATOR and r['authorization_message_id'] and r['supervisor_dead'] is True
  receipt=read(exitpath);host=receipt['host'];launch=read(phase/'launch.json')
  matching=[p for p in dispatches if sha(p)==launch['dispatch_sha256']];assert len(matching)==1
  for d in read(matching[0])['blocks']:
   if d['host']!=host:continue
   assert d['id'] not in seen;seen.add(d['id'])
   durable=hub/d['id']/'complete.json'
   if durable.exists():
    proof=read(durable);assert proof['descriptor']['seed']==d['seed'] and len(proof['games'])==8
    assert all(sha(durable.parent/'games'/name)==h for name,h in proof['games'].items())
    if host!='127x01':assert (durable.parent/'hub-ack.json').exists()
    continue
   started=(phase/'pids'/f"{d['id']}.json").exists() or (phase/'descriptors'/f"{d['id']}.json").exists()
   if not started:unstarted.append(dict(d));continue
   # This includes completed blocks not yet durable off-host; never inspect outcomes.
   losses.append(dict(descriptor=d,reason=receipt.get('reason') or 'host_lost',utc=receipt['utc'],evidence_sha256=sha(exitpath)))
 return losses,unstarted,history


def main():
 p=argparse.ArgumentParser();p.add_argument('--source-phases',type=Path,nargs='+',required=True);p.add_argument('--dispatches',type=Path,nargs='+',required=True);p.add_argument('--hub',type=Path,required=True);p.add_argument('--ledger',type=Path,required=True);p.add_argument('--dispatch-out',type=Path,required=True);p.add_argument('--hosts',nargs='+',required=True);p.add_argument('--stop-file',type=Path,required=True);a=p.parse_args()
 ledger=read(a.ledger)['events'] if a.ledger.exists() else [];rows=[]
 try:
  assert len(a.hosts)>=2 and set(a.hosts)<=set(plan()['compute']['hosts']),'fewer than two named hosts; stop and amend'
  losses,unstarted,history=inventory(a.source_phases,a.dispatches,a.hub)
  for item in losses:
   lost=item['descriptor']
   if any(e['lost']['id']==lost['id'] for e in ledger):continue
   r=replacement(lost,ledger)
   ledger.append(dict(utc=item['utc'],lost=lost,replacement=r,reason=item['reason'],evidence_sha256=item['evidence_sha256']))
   write(a.ledger,dict(utc=utc(),sealed=True,events=ledger))
   if r is not None:rows.append(r)
  # Recovered queue comes first, with the original seeds and arm rotation intact.
  rows=unstarted+rows;assign_hosts(rows,a.hosts,history)
  write(a.ledger,dict(utc=utc(),sealed=True,events=ledger))
 except AssertionError as e:
  a.stop_file.write_text(utc()+' '+str(e)+'\n');raise
 write(a.dispatch_out,dict(utc=utc(),hosts=a.hosts,blocks=rows,never_started_redispatched=[d['id'] for d in unstarted],source_receipts={str(p):sha(p/'supervisor-exit.json' if (p/'supervisor-exit.json').exists() else p/'HOST-LOSS.json') for p in a.source_phases},sealed=True))
if __name__=='__main__':main()
