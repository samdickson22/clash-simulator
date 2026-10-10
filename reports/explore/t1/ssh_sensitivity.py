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
  entries[logical]=dict(id=logical,source_id=identity,population=d['population'],cell=d['cell'],host=proof['host'],ssh_flagged=flagged(proof.get('interference',{})),complete_sha256=sha(path),interference_sha256=proof.get('interference_sha256'))
 return dict(schema='clasher.t1.ssh-sensitivity-ledger.v1',utc=utc(),sealed=True,blind_ledger_sha256=blind_sha,blocks=[entries[k] for k in sorted(entries)])

def analyze(rows,ledger,reps,seed,stats_fn,rng_factory):
 entries={r['id']:r for r in ledger['blocks']}
 assert set(entries)=={r['id'] for group in rows.values() for r in group}
 rng=rng_factory(seed);out={}
 for population,group in rows.items():
  for row in group:
   entry=entries[row['id']]
   assert entry['complete_sha256']==row['complete_sha256'] and entry['ssh_flagged']==flagged(row['interference'])
  retained=[r for r in group if not entries[r['id']]['ssh_flagged']]
  out[population]=dict(total=len(group),excluded=len(group)-len(retained),retained=len(retained),excluded_by_cell={str(c):sum(entries[r['id']]['ssh_flagged'] for r in group if r['cell']==c) for c in sorted({r['cell'] for r in group})},status='DESCRIPTIVE_ONLY' if retained else 'NO_UNFLAGGED_BLOCKS',statistics=stats_fn(retained,rng,reps) if retained else None)
 return dict(status='DESCRIPTIVE_ONLY',selection_eligible=False,rule='exclude source-proven LAN SSH >0.5% block average; retained empirical stratum weights',bootstrap_seed=seed,populations=out)

def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--ledger',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 events=read(a.ledger)['events'] if a.ledger else []
 result=health_ledger(a.root,events,sha(a.ledger) if a.ledger else None);write(a.out,result)
 print('SSH sensitivity health ledger written; outcomes SEALED')
if __name__=='__main__':main()
