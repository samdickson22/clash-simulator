"""K4S runner r1: final durability/ACK pass, counted inventory and reporting-completion receipt (local only; never
contacts a host; outcome-blind: game files are hashed, never parsed; complete.json is read only for its descriptor,
host and games {name: sha256} map, which carry no outcome).

Inputs: rounds/history.json (phases, namespaces, dispatches), phase-meta/<host>-<phase>/supervisor-exit.json (copied
from each host after its supervisor exited), the 05 hub copies <job>/hub-blocks/<phase>/<id>/, ledger/blind-ledger.json.
Checks, per completed block of every phase and host:
  - hub copy present; hub-ack.json bound (hub 127x05, source host, job, phase, block, complete_sha256 == sha(complete.json));
  - hub-ack.returned.json bound (hub_ack_sha256, complete_sha256, source_host);
  - complete.json descriptor == the supervisor-exit completed descriptor; host matches; len(games) == len(order);
  - games/ holds exactly the listed files and each file's sha256 equals the listed value.
Then: no completed block is a ledger loss; every completed id appears once; the logical coverage (replaces or id) is
exactly primary 0..2999 and guard 0..899. Writes counted-inventory.json ({host, phase, descriptor} rows, the frozen
end_evidence format) and REPORTING-COMPLETION.json. Any failure: no completion receipt is written; exit 2.
Usage: final_pass.py OUTDIR"""
import hashlib,json,os,re,subprocess,sys
from pathlib import Path

L=Path('/mpac/sdicks02/k4s-runner/run-r1')
SELF=Path(__file__).resolve()
JOBROOT={'127x03':'/mpac/sdicks02/jobs/clasher','127x04':'/mpac/sdicks02/jobs-k4s'}
COUNTS={'primary':3000,'guard':900}

def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()

def need(c,m):
 if not c:raise ValueError(m)

def main(argv):
 out=Path(argv[1]);out.mkdir(parents=True,exist_ok=True)
 utc=lambda:subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip()
 started=utc()
 hist=json.loads((L/'rounds'/'history.json').read_text())
 phases=[e['phase'] for e in hist];need(phases==['reporting','replacement-r1','replacement-r2','replacement-r3','replacement-r4'],f'history phases {phases}')
 ledger_raw=(L/'ledger'/'blind-ledger.json').read_bytes();ledger=json.loads(ledger_raw)
 lost={e['lost']['id'] for e in ledger['events']}
 rows=[];seen=set();logical={'primary':set(),'guard':set()};per={};exits={}
 for e in hist:
  ph,ns=e['phase'],e['namespace']
  disp_raw=(L/'dispatch'/e['dispatch_file']).read_bytes();need(hashlib.sha256(disp_raw).hexdigest()==e['dispatch_sha256'],f'{ph} dispatch sha')
  for h in ('127x03','127x04'):
   meta=L/'phase-meta'/f'{h}-{ph}'
   ex_path=meta/'supervisor-exit.json';ex_raw=ex_path.read_bytes();ex=json.loads(ex_raw)
   need(ex.get('host')==h,f'{h} {ph} exit host');need(all(isinstance(ex.get(k),list) for k in ('completed','failed','unstarted')),f'{h} {ph} exit lists')
   launch=json.loads((meta/'launch.json').read_text());need(launch.get('dispatch_sha256')==e['dispatch_sha256'],f'{h} {ph} launch dispatch')
   exits[f'{h}/{ph}']=dict(sha256=hashlib.sha256(ex_raw).hexdigest(),utc=ex.get('utc'),reason=ex.get('reason'),completed=len(ex['completed']),failed=len(ex['failed']),unstarted=len(ex['unstarted']))
   job=f'{JOBROOT[h]}/{ns}';hub=Path(job)/'hub-blocks'/ph
   n=0;games=0
   for d in ex['completed']:
    bid=d['id'];need(bid not in seen,f'duplicate completed id {bid}');need(bid not in lost,f'completed block {bid} is a ledger loss')
    bd=hub/bid;cp=bd/'complete.json';need(cp.is_file(),f'{h} {ph} {bid} no hub copy')
    cs=sha(cp);proof=json.loads(cp.read_bytes())
    ack=json.loads((bd/'hub-ack.json').read_bytes());ret=json.loads((bd/'hub-ack.returned.json').read_bytes());ah=sha(bd/'hub-ack.json')
    need(ack.get('hub')=='127x05' and ack.get('source_host')==h and ack.get('job')==job and ack.get('phase')==ph and ack.get('block')==bid and ack.get('complete_sha256')==cs,f'{bid} hub-ack binding')
    need(ret.get('hub_ack_sha256')==ah and ret.get('complete_sha256')==cs and ret.get('source_host')==h,f'{bid} returned binding')
    need(proof.get('descriptor')==d,f'{bid} descriptor != exit descriptor');need(proof.get('host')==h,f'{bid} proof host')
    gm=proof.get('games');need(isinstance(gm,dict) and len(gm)==len(d['order']),f'{bid} games map')
    present=sorted(os.listdir(bd/'games'));need(present==sorted(gm),f'{bid} games/ != listed')
    for name,hv in gm.items():need(sha(bd/'games'/name)==hv,f'{bid} game {name} sha mismatch')
    pop=d['population'];lid=d.get('replaces') or bid
    need(pop in logical and re.fullmatch(pop+r'-[0-9]{4}',lid) is not None and lid not in logical[pop],f'{bid} logical {lid}')
    logical[pop].add(lid);seen.add(bid);n+=1;games+=len(gm)
    rows.append(dict(host=h,phase=ph,descriptor=d))
   per[f'{h}/{ph}']=dict(counted=n,games_hashed=games)
 for pop,c in COUNTS.items():need(logical[pop]=={f'{pop}-{i:04d}' for i in range(c)},f'{pop} logical coverage {len(logical[pop])}/{c}')
 inv=dict(schema='clasher.k4s.counted-inventory.v1',study='PREREG-K4S',sealed=True,outcomes_read=False,blocks=rows)
 inv_raw=(json.dumps(inv,indent=1)+'\n').encode();(out/'counted-inventory.json').write_bytes(inv_raw)
 hosts_phases={h:[ph for ph in phases if per[f'{h}/{ph}']['counted']>0] for h in ('127x03','127x04')}
 last_exit=max(v['utc'] for v in exits.values())
 done=utc();need(done>=last_exit,'completion precedes a supervisor exit')
 comp=dict(schema='clasher.k4s.reporting-completion.v1',study='PREREG-K4S',reporting_complete=True,outcomes_sealed=True,
   counted_primary_blocks=len(logical['primary']),counted_guard_blocks=len(logical['guard']),counted_host_phases=hosts_phases,
   completed_at_utc=done,last_supervisor_exit_utc=last_exit,
   blind_ledger_sha256=hashlib.sha256(ledger_raw).hexdigest(),blind_ledger_events=len(ledger['events']),
   counted_inventory_sha256=hashlib.sha256(inv_raw).hexdigest(),counted_blocks=len(rows),
   dispatches={e['phase']:e['dispatch_sha256'] for e in hist},supervisor_exits=exits,per_host_phase=per,
   durability=dict(checked_from=started,checked_to=done,hub='127x05',checks='hub-ack + returned bindings, descriptor == exit, games/ == listed, every game sha256'),
   frozen_freeze_commit='391d2006',frozen_manifest_sha256='416f6e51e32e1900faaf8ceaf329287475a6a621fb1dc2d1b6def50ebb528ed1',
   script=SELF.name,script_sha256=sha(SELF),outcomes_read=False)
 (out/'REPORTING-COMPLETION.json').write_text(json.dumps(comp,indent=1)+'\n')
 print(json.dumps(dict(ok=True,counted=len(rows),primary=len(logical['primary']),guard=len(logical['guard']),completed_at_utc=done,
   inventory_sha256=comp['counted_inventory_sha256'],per=per)))
 return 0

if __name__=='__main__':
 try:sys.exit(main(sys.argv))
 except Exception as e:
  print(json.dumps(dict(ok=False,error=f'{type(e).__name__}: {e}')));sys.exit(2)
