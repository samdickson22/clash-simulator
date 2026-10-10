"""OP-6 health ledger; descriptive exclusions never alter primary selection."""
import argparse,os
from fractions import Fraction
from pathlib import Path
from common import read,write,sha,utc
from ssh_budget import lan_connection

def flagged(interference):
 meter=interference.get('ssh_family',{})
 if not meter:return False
 records=meter.get('processes',[])
 if 'source_proven_cpu_ticks' in meter:
  ticks=meter['source_proven_cpu_ticks']
  assert ticks==sum(r.get('source_proven_cpu_ticks',0) for r in records)
 else:
  # Legacy OP-4 complete proofs retain each process's bound LAN source.
  ticks=sum(r['cpu_ticks'] for r in records if lan_connection(r.get('source',{}).get('source')))
 hz=meter.get('clock_ticks_per_second',os.sysconf('SC_CLK_TCK'))
 value=Fraction(ticks)*200>hz*Fraction(str(max(meter['block_seconds'],.001)))
 if 'ssh_flagged' in meter:assert meter['ssh_flagged']==value
 if 'ssh_flagged' in interference:assert interference['ssh_flagged']==value
 return value

def apt_flagged(interference):
 meter=interference.get('ubuntu_apt',{})
 if not meter:
  assert not interference.get('apt_flagged',False),'apt flag lacks meter proof'
  return False
 ticks=meter['cpu_ticks'];records=meter['processes']
 assert ticks==sum(r['cpu_ticks'] for r in records)
 from apt_budget import CGROUPS,METHODS
 for r in records:
  source=r['source'];root=source['root_identity']
  assert source['cgroup'] in CGROUPS and root['real_uid']==root['effective_uid']==0
  assert root['uid_evidence']=='proc/status Uid real/effective'
  assert source['uid_evidence']=='proc/status Uid real/effective'
  if source['member_kind']=='root':assert source['real_uid']==source['effective_uid']==0
  else:
   assert source['member_kind']=='_apt_method' and source['helper_uid'] is not None
   assert source['real_uid']==source['effective_uid']==source['helper_uid']
   assert Path(source['exe_path']).parent==METHODS
   evidence=source['helper_exe_proof'];assert evidence['path']==source['exe_path'] and evidence['evidence']==source['exe_evidence']
   if evidence['evidence']!='proc/exe':
    import errno
    assert evidence['evidence']=='argv0 (proc/exe EACCES, unprivileged)' and evidence['exe_errno']==errno.EACCES
    assert evidence['file_uid']==0 and not evidence['file_mode']&0o022
    assert Path(evidence['argv0']).is_absolute() and '..' not in Path(evidence['argv0']).parts
 hz=meter['clock_ticks_per_second']
 value=Fraction(ticks)*200>hz*Fraction(str(max(meter['block_seconds'],.001)))
 assert meter['apt_flagged']==value and interference.get('apt_flagged',value)==value
 return value

def health_ledger(root,events,blind_sha):
 excluded={r['lost']['id'] for r in events};replacement={r['replacement']['id']:r['replacement'] for r in events if r['replacement'] is not None}
 entries={}
 for path in sorted(root.glob('*/complete.json')):
  proof=read(path);d=proof['descriptor'];identity=d['id']
  if identity in excluded:continue
  logical=d.get('replaces') or identity
  if d.get('replaces'):assert identity in replacement and replacement[identity]['replaces']==logical
  assert logical not in entries,'duplicate logical block in sensitivity ledger'
  if proof['host']!='127x01':assert (path.parent/'hub-ack.json').exists(),'sensitivity source not durable'
  if 'interference_sha256' in proof:assert sha(path.parent/'interference.json')==proof['interference_sha256']
  entries[logical]=dict(id=logical,source_id=identity,population=d['population'],cell=d['cell'],host=proof['host'],ssh_flagged=flagged(proof.get('interference',{})),apt_flagged=apt_flagged(proof.get('interference',{})),ssh_or_apt_flagged=flagged(proof.get('interference',{})) or apt_flagged(proof.get('interference',{})),apt_meter_stop=bool(proof.get('interference',{}).get('ubuntu_apt',{}).get('stop')),ssh_meter_stop=bool(proof.get('interference',{}).get('ssh_family',{}).get('stop')),cpu_accounting_rule=proof.get('interference',{}).get('ubuntu_apt',proof.get('interference',{}).get('ssh_family',{})).get('cpu_accounting_rule','legacy-self-plus-reaped'),complete_sha256=sha(path),interference_sha256=proof.get('interference_sha256'))
 blocks=[entries[k] for k in sorted(entries)]
 return dict(schema='clasher.t1.ssh-sensitivity-ledger.v1',utc=utc(),sealed=True,blind_ledger_sha256=blind_sha,blocks=blocks,flag_counts=flag_counts(blocks))

def analyze(rows,ledger,reps,seed,stats_fn,rng_factory,flag_key='ssh_flagged',flag_fn=flagged,rule='exclude source-proven LAN SSH >0.5% block average; retained empirical stratum weights'):
 entries={r['id']:r for r in ledger['blocks']}
 assert set(entries)=={r['id'] for group in rows.values() for r in group}
 rng=rng_factory(seed);out={}
 for population,group in rows.items():
  for row in group:
   entry=entries[row['id']]
   assert entry['complete_sha256']==row['complete_sha256'] and entry[flag_key]==flag_fn(row['interference'])
  retained=[r for r in group if not entries[r['id']][flag_key]]
  out[population]=dict(total=len(group),excluded=len(group)-len(retained),retained=len(retained),excluded_by_cell={str(c):sum(entries[r['id']][flag_key] for r in group if r['cell']==c) for c in sorted({r['cell'] for r in group})},status='DESCRIPTIVE_ONLY' if retained else 'NO_UNFLAGGED_BLOCKS',statistics=stats_fn(retained,rng,reps) if retained else None)
 return dict(status='DESCRIPTIVE_ONLY',selection_eligible=False,rule=rule,bootstrap_seed=seed,populations=out)

def analyze_apt(rows,ledger,reps,seed,stats_fn,rng_factory):
 return analyze(rows,ledger,reps,seed,stats_fn,rng_factory,flag_key='apt_flagged',flag_fn=apt_flagged,rule='exclude source-proven Ubuntu apt maintenance >0.5% block average; retained empirical stratum weights')

def union_flagged(interference):
 return flagged(interference) | apt_flagged(interference)

def flag_counts(blocks):
 def counts(rows):
  return dict(total=len(rows),ssh=sum(r['ssh_flagged'] for r in rows),apt=sum(r['apt_flagged'] for r in rows),both=sum(r['ssh_flagged'] and r['apt_flagged'] for r in rows),either=sum(r['ssh_flagged'] or r['apt_flagged'] for r in rows),apt_meter_stop=sum(r['apt_meter_stop'] for r in rows),ssh_meter_stop=sum(r['ssh_meter_stop'] for r in rows))
 return {p:dict(**counts([r for r in blocks if r['population']==p]),by_cell={str(c):counts([r for r in blocks if r['population']==p and r['cell']==c]) for c in sorted({r['cell'] for r in blocks if r['population']==p})}) for p in sorted({r['population'] for r in blocks})}

def analyze_union(rows,ledger,reps,seed,stats_fn,rng_factory):
 return analyze(rows,ledger,reps,seed,stats_fn,rng_factory,flag_key='ssh_or_apt_flagged',flag_fn=union_flagged,rule='exclude blocks flagged by source-proven LAN SSH OR Ubuntu apt maintenance >0.5% block average; retained empirical stratum weights')

def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--ledger',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 events=read(a.ledger)['events'] if a.ledger else []
 result=health_ledger(a.root,events,sha(a.ledger) if a.ledger else None);write(a.out,result)
 print('SSH sensitivity health ledger written; outcomes SEALED')
if __name__=='__main__':main()
